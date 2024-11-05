import datetime
from hashlib import md5
import os
import platform
import random
import re
import socket
import struct
import sys
import time

from PyQt6.QtCore import QThread

class ChallengeException (Exception):
    def __init__(self):
        pass

class LoginException (Exception):
    def __init__(self):
        pass

class DrcomClientThread(QThread):
    SERVER = '10.100.61.3'
    CONTROL_CHECK_STATUS = b'\x20'
    ADAPTER_NUM = b'\x03'
    IP_DOG = b'\x01'
    PRIMARY_DNS = '10.10.10.10'
    DHCP_SERVER = '0.0.0.0'
    AUTH_VERSION = b'\x68\x00'
    KEEP_ALIVE_VERSION = b'\xdc\x02'

    nic_name = ''  # Indicate your nic, e.g. 'eth0.2'.nic_name
    bind_ip = '0.0.0.0'

    salt = ''
    IS_TEST = True
    # specified fields based on version
    CONF = "/etc/drcom.conf"
    UNLIMITED_RETRY = True
    EXCEPTION = False
    DEBUG = True  # log saves to file
    LOG_PATH = '/var/log/drcom_client.log'

    def __init__(self, username, password, host_ip, host_mac, host_name, host_os):
        super().__init__()

        self.username = username
        self.password = password
        self.host_ip = host_ip
        self.host_mac = host_mac
        self.host_name = host_name
        self.host_os = host_os

        self.switch_on = True

        if self.nic_name != '':
            self.bind_ip = self.__bind_nic()

        if self.IS_TEST:
            self.DEBUG = True
            self.LOG_PATH = os.path.dirname(__file__) + '/drcom_client.log'

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.bind_ip, 61440))
        self.socket.settimeout(3)

    def __bind_nic(self):
        try:
            import fcntl
            def get_ip_address(ifname):
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                return socket.inet_ntoa(fcntl.ioctl(
                    s.fileno(),
                    0x8915,  # SIOCGIFADDR
                    struct.pack('256s', ifname[:15])
                )[20:24])

            return get_ip_address(self.nic_name)
        except ImportError as e:
            print('Indicate nic feature need to be run under Unix based system.')
            return '0.0.0.0'
        except IOError as e:
            print(self.nic_name + ' is unacceptable !')
            return '0.0.0.0'
        finally:
            return '0.0.0.0'

    def __challenge(self, ran):
        while True:
            t = struct.pack("<H", int(ran) % 0xFFFF)
            self.socket.sendto(b"\x01\x02" + t + b"\x09" + b"\x00" * 15, (self.SERVER, 61440))
            try:
                data, address = self.socket.recvfrom(1024)
                self.__log('[challenge] recv', data.hex())
            except():
                self.__log('[challenge] timeout, retrying...')
                continue

            if address == (self.SERVER, 61440):
                break
            else:
                self.__log(f"Wrong address: {address}")
                exit()
        self.__log('[DEBUG] challenge:\n' + data.hex())
        if data[0] != 2:
            raise ChallengeException
        self.__log('[challenge] challenge packet sent.')
        return data[4:8]

    @staticmethod
    def __checksum(s):
        ret = 1234
        for i in re.findall(b'....', s):
            ret ^= int(i[::-1].hex(), 16)
        ret = (1968 * ret) & 0xffffffff
        return struct.pack('<I', ret)

    @staticmethod
    def __daemon():
        if platform.uname().system != 'Windows':
            with open('/var/run/jludrcom.pid', 'w') as f:
                f.write(str(os.getpid()))

    @staticmethod
    def __dump(n):
        s = '%x' % n
        if len(s) & 1:
            s = '0' + s
        return bytes.fromhex(s)

    def __empty_socket_buffer(self):
        # empty buffer for some fucking schools
        self.__log('starting to empty socket buffer')
        try:
            while True:
                data, address = self.socket.recvfrom(1024)
                self.__log('recived sth unexpected', data.hex())
                if self.socket == '':
                    break
        except socket.timeout as timeout_err:
            # get exception means it has done.
            self.__log(f'exception in empty_socket_buffer {timeout_err}')
        self.__log('emptyed')

    def __keep_alive1(self, tail):
        foo = struct.pack('!H', int(time.time()) % 0xFFFF)
        data = b'\xff' + self.__md5sum(b'\x03\x01' + self.salt + self.password) + b'\x00\x00\x00'
        data += tail
        data += foo + b'\x00\x00\x00\x00'
        self.__log('[keep_alive1] send', data.hex())

        self.socket.sendto(data, (self.SERVER, 61440))
        while True:
            data, address = self.socket.recvfrom(1024)
            if data[0] == 7:
                break
            else:
                self.__log('[keep-alive1]recv/not expected', data.hex())
        self.__log('[keep-alive1] recv', data.hex())

    def __keep_alive2(self, package_tail):
        ran = random.randint(0, 0xFFFF)
        ran += random.randint(1, 10)
        # 2014/10/15 add by latyas, maybe svr sends back a file packet
        svr_num = 0
        packet = self.__keep_alive_package_builder(svr_num, b'\x00' * 4, 1, True)
        while True:
            self.__log('[keep-alive2] send1', packet.hex())
            self.socket.sendto(packet, (self.SERVER, 61440))
            data, address = self.socket.recvfrom(1024)
            self.__log('[keep-alive2] recv1', data.hex())
            if data.startswith(b'\x07\x00\x28\x00') or data.startswith(
                    b'\x07' + svr_num.to_bytes(1, 'big') + b'\x28\x00'):
                break
            elif data[0] == 0x07 and data[2] == 0x10:
                self.__log('[keep-alive2] recv file, resending..')
                svr_num = svr_num + 1
                packet = self.__keep_alive_package_builder(svr_num, b'\x00' * 4, 1, False)
            else:
                self.__log('[keep-alive2] recv1/unexpected', data.hex())

        # log('[keep-alive2] recv1',data.hex())

        ran += random.randint(1, 10)
        packet = self.__keep_alive_package_builder(svr_num, b'\x00' * 4, 1, False)
        self.__log('[keep-alive2] send2', packet.hex())
        self.socket.sendto(packet, (self.SERVER, 61440))
        while True:
            data, address = self.socket.recvfrom(1024)
            if data[0] == 7:
                svr_num = svr_num + 1
                break
            else:
                self.__log('[keep-alive2] recv2/unexpected', data.hex())

        self.__log('[keep-alive2] recv2', data.hex())
        tail = data[16:20]

        ran += random.randint(1, 10)
        packet = self.__keep_alive_package_builder(svr_num, tail, 3, False)
        self.__log('[keep-alive2] send3', packet.hex())
        self.socket.sendto(packet, (self.SERVER, 61440))
        while True:
            data, address = self.socket.recvfrom(1024)
            if data[0] == 7:
                svr_num = svr_num + 1
                break
            else:
                self.__log('[keep-alive2] recv3/unexpected', data.hex())

        self.__log('[keep-alive2] recv3', data.hex())
        tail = data[16:20]
        self.__log("[keep-alive2] keep-alive2 loop was in daemon.")

        i = svr_num
        while True:
            try:
                ran += random.randint(1, 10)
                packet = self.__keep_alive_package_builder(i, tail, 1, False)
                # log('DEBUG: keep_alive2,packet 4\n',packet.hex())
                self.__log('[keep_alive2] send', str(i), packet.hex())
                self.socket.sendto(packet, (self.SERVER, 61440))
                data, address = self.socket.recvfrom(1024)
                self.__log('[keep_alive2] recv', data.hex())
                tail = data[16:20]
                # log('DEBUG: keep_alive2,packet 4 return\n',data.hex())

                ran += random.randint(1, 10)
                packet = self.__keep_alive_package_builder(i + 1, tail, 3, False)
                # log('DEBUG: keep_alive2,packet 5\n',packet.hex())
                self.socket.sendto(packet, (self.SERVER, 61440))
                self.__log('[keep_alive2] send', str(i + 1), packet.hex())
                data, address = self.socket.recvfrom(1024)
                self.__log('[keep_alive2] recv', data.hex())
                tail = data[16:20]
                # log('DEBUG: keep_alive2,packet 5 return\n',data.hex())
                i = (i + 2) % 0xFF

                time.sleep(20)

                self.__keep_alive1(package_tail)
            except():
                continue

    def __keep_alive_package_builder(self, number, tail: bytes, packet_type=1, first=False):
        data = b'\x07' + number.to_bytes(1, 'big') + b'\x28\x00\x0b' + packet_type.to_bytes(1, 'big')
        if first:
            data += b'\x0f\x27'
        else:
            data += self.KEEP_ALIVE_VERSION
        data += b'\x2f\x12' + b'\x00' * 6
        data += tail
        data += b'\x00' * 4
        # data += struct.pack("!H",0xdc02)z
        if packet_type == 3:
            foo = b''.join([int(i).to_bytes(1, 'big') for i in self.host_ip.split('.')])  # host_ip
            # CRC
            # edited on 2014/5/12, filled zeros to checksum
            # crc = packet_CRC(data+foo)
            crc = b'\x00' * 4
            # data += struct.pack("!I",crc) + foo + b'\x00' * 8
            data += crc + foo + b'\x00' * 8
        else:  # packet type = 1
            data += b'\x00' * 16
        return data

    def __log(self, *args):
        print(*args)
        if self.DEBUG and platform.uname().system != 'Windows':
            formatted_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(self.LOG_PATH, 'a') as f:
                f.write(formatted_time + '\t')
                for arg in args:
                    f.write(str(arg) + ' ')
                f.write('\n')

    def __login(self):
        i = 0
        while True:
            self.salt = self.__challenge(time.time() + random.randint(0xF, 0xFF))
            self.__log('[salt] ', self.salt)
            packet = self.__mkpkt()  # 生成数据包
            self.__log('[login] send', packet.hex())
            self.socket.sendto(packet, (self.SERVER, 61440))
            data, address = self.socket.recvfrom(1024)
            self.__log('[login] recv', data.hex())
            self.__log('[login] packet sent.')
            if address == (self.SERVER, 61440):
                if data[0] == 4:
                    self.__log('[login] loged in')
                    break
                else:
                    self.__log(f'[login] login failed. data[0] = {data[0]} type={type(data[0])}')
                    exit(2)
            else:
                if i >= 5 and self.UNLIMITED_RETRY == False:
                    self.__log('[login] exception occured.')
                    sys.exit(1)
                else:
                    exit(2)

        self.__log('[login] login sent')
        # 0.8 changed:
        return data[23:39]
        # return data[-22:-6]

    @staticmethod
    def __md5sum(s):
        m = md5()
        m.update(s)
        return m.digest()

    def __mkpkt(self):
        data = b'\x03\x01\x00' + (len(self.username) + 20).to_bytes(1, 'big')
        data += self.__md5sum(b'\x03\x01' + self.salt + self.password)
        data += self.username.ljust(36, b'\x00')
        data += self.CONTROL_CHECK_STATUS
        data += self.ADAPTER_NUM
        data += self.__dump(int(data[4:10].hex(), 16) ^ self.host_mac).rjust(6, b'\x00')  # mac xor md51
        data += self.__md5sum(b"\x01" + self.password + self.salt + b'\x00' * 4)  # md52
        data += b'\x01'  # number of ip
        data += b''.join([int(x).to_bytes(1, 'big') for x in self.host_ip.split('.')])
        data += b'\x00' * 4  # your ipaddress 2
        data += b'\x00' * 4  # your ipaddress 3
        data += b'\x00' * 4  # your ipaddress 4
        data += self.__md5sum(data + b'\x14\x00\x07\x0b')[:8]  # md53
        data += self.IP_DOG
        data += b'\x00' * 4  # delimeter
        data += self.host_name.ljust(32, b'\x00')
        data += b''.join([int(i).to_bytes(1, 'big') for i in self.PRIMARY_DNS.split('.')])  # primary dns
        data += b''.join([int(i).to_bytes(1, 'big') for i in self.DHCP_SERVER.split('.')])  # DHCP dns
        data += b'\x00\x00\x00\x00'  # secondary dns:0.0.0.0
        data += b'\x00' * 8  # delimeter
        data += b'\x94\x00\x00\x00'  # unknow
        data += b'\x06\x00\x00\x00'  # os major
        data += b'\x02\x00\x00\x00'  # os minor
        data += b'\xf0\x23\x00\x00'  # OS build
        data += b'\x02\x00\x00\x00'  # os unknown
        data += b'\x44\x72\x43\x4f\x4d\x00\xcf\x07\x68'
        data += b'\x00' * 55  # unknown string
        data += b'\x33\x64\x63\x37\x39\x66\x35\x32\x31\x32\x65\x38\x31\x37\x30\x61\x63\x66\x61\x39\x65\x63\x39\x35\x66\x31\x64\x37\x34\x39\x31\x36\x35\x34\x32\x62\x65\x37\x62\x31'
        data += b'\x00' * 24
        data += self.AUTH_VERSION
        data += b'\x00' + len(self.password).to_bytes(1, 'big')
        data += self.__ror(self.__md5sum(b'\x03\x01' + self.salt + self.password), self.password)
        data += b'\x02\x0c'
        data += self.__checksum(data + b'\x01\x26\x07\x11\x00\x00' + self.__dump(self.host_mac))
        data += b'\x00\x00'  # delimeter
        data += self.__dump(self.host_mac)
        if (len(self.password) / 4) != 4:
            data += b'\x00' * (len(self.password) // 4)  # strange。。。
        data += b'\x60\xa2'  # unknown, filled numbers randomly =w=
        data += b'\x00' * 28
        self.__log('[mkpkt]', data.hex())
        return data

    @staticmethod
    def __ror(md5: bytes, pwd: bytes):
        ret = b''
        for i in range(len(pwd)):
            x = md5[i] ^ pwd[i]
            ret += (((x << 3) & 0xFF) + (x >> 5)).to_bytes(1, 'big')
        return ret

    def run(self):
        self.switch_on = True

        if not self.IS_TEST:
            self.__daemon()
            with open(self.CONF) as f:
                exec(f.read(), globals())

        self.__log("auth svr:", self.SERVER, "\nusername:", self.username, "\npassword:", self.password, "\nmac:",
                   str(hex(self.host_mac)))
        self.__log(self.bind_ip)

        try:
            package_tail = self.__login()
        except LoginException:
            self.__log("登录失败!")
            return
        self.__log('package_tail', package_tail.hex())

        ## keep alive
        self.__empty_socket_buffer()
        self.__keep_alive1(package_tail)
        self.__keep_alive2(package_tail)

    def stop(self):
        self.switch_on = False