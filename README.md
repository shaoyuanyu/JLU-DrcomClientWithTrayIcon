# JLU Drcom client with tray icon on Linux

All the functional codes are from [here](https://github.com/drcoms/jlu-drcom-client/blob/master/jlu-drcom-py3/newclinet-py3.py).

My work is packaging these codes into a PyQt6 Application **with tray icon**.

## Configure

Set your configuration in `main()` function of `main.py`:

```python3
drcomClientThread = DrcomClientThread(
    b'XXXXX',               # username
    b'XXXXX',               # password
    '100.100.100.100',      # host ip (which jlu distribute to you)
    0x112288776655,         # host mac (the hex MAC address of your pc)
    b'YOUR_PC_NAME',        # host name (whatever, e.g."user 1")
    b'Linux'                # host operating system (whatever, e.g."ubuntu")
)
```

## Auto Launch

### systemd

Firstly, switch to root user:

```bash
$ su
```

Then run following commands (don't forget to complement `[Service].ExecStart`):

```bash
$ cat > /etc/systemd/system/jlu-drcom-client.service << EOF
[Unit]
Description=run jlu drcom client
After=network-online.target nftables.service iptables.service
[Service]
ExecStart=/example_path/
[Install]
WantedBy=multi-user.target
EOF
$ systemctl daemon-reload
$ systemctl enable jlu-drcom-client.service
```

Reboot and the client would launch automatically.

### other

There are also other methods you can use to set auto launching, depending on your system/distribution.