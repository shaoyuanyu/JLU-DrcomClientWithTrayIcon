# JLU Drcom client with tray icon on Linux

![client-icon](jlu-drcom.svg)

All the functional codes are from [here](https://github.com/drcoms/jlu-drcom-client/blob/master/jlu-drcom-py3/newclinet-py3.py).

My work is packaging these codes into a PyQt6 Application **with tray icon**.

## Configure

### main.py

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

### run.sh

Replace the relative path in `run.sh` with absolute path of `main.py`.

## Auto Launch

### add to desktop

Switch to root user:

```bash
$ su
```

Complement the value `code_path` in `Exec` and `Icon`.

```bash
$ cat /usr/share/applications/jlu-drcom-client.desktop << EOF
[Desktop Entry]
Name=JLU-Drcom-Client
Comment=jlu drcom client with tray icon
Exec=/code_path/run.sh
Terminal=false
Type=Application
Icon=/code_path/icon.on.png
Categories=Network;
EOF
```

Then use your desktop tool to set auto launching. (For GNOME, use `GNOME Tweaks Tool`)

### (Deprecated) add systemd service

Tip:
Using this method may encounter some issues with environment variables.

Firstly, switch to root user:

```bash
$ su
```

Then run following commands (don't forget to complement `[Service].ExecStart`):

```bash
$ cat > /usr/lib/systemd/system/jlu-drcom-client.service << EOF
[Unit]
Description=run jlu drcom client
After=network.target
[Service]
ExecStart=/bin/bash /code_path/run.sh
[Install]
WantedBy=multi-user.target
EOF

$ systemctl daemon-reload

$ systemctl enable jlu-drcom-client.service
```

Reboot and the client would launch automatically.

### other

There are also other methods you can use to set auto launching, depending on your system/distribution.