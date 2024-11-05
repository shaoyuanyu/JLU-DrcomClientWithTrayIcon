from DrcomClientThread import DrcomClientThread

import sys
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction

def create_tray_icon(app):
    # 创建托盘图标
    tray_icon = QSystemTrayIcon(QIcon("icon.on.png"), app)
    tray_icon.setToolTip("JLU Drcom Client")

    # 创建菜单
    menu = QMenu()

    # exit 选项
    exit_action = QAction("退出", app)
    exit_action.triggered.connect(app.quit)
    menu.addAction(exit_action)

    tray_icon.setContextMenu(menu)
    tray_icon.show()

def main():
    drcomClientThread = DrcomClientThread(
        b'XXXXX',
        b'XXXXX',
        '100.100.100.100',
        0x112288776655,
        b'YOUR_PC_NAME',
        b'Linux'
    )

    app = QApplication(sys.argv)
    create_tray_icon(app)

    drcomClientThread.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()