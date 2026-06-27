from PySide6.QtWidgets import QWidget, QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, Qt, QIcon, QAction
from vcd.gui.constants import get_app_icon


class TrayManager:
    def __init__(self, window: QWidget):
        self._win = window
        self._tray = QSystemTrayIcon(window)
        if not get_app_icon().isNull():
            self._tray.setIcon(get_app_icon())
        else:
            px = QPixmap(20, 20)
            px.fill(Qt.transparent)
            pp = QPainter(px)
            pp.setRenderHint(QPainter.Antialiasing)
            pp.setBrush(QColor(56, 189, 248))
            pp.setPen(Qt.NoPen)
            pp.drawEllipse(2, 2, 16, 16)
            pp.end()
            self._tray.setIcon(QIcon(px))
        menu = QMenu()
        a_show = QAction("Open VCD", window)
        a_show.triggered.connect(window.show)
        a_show.triggered.connect(window.raise_)
        a_quit = QAction("Quit", window)
        a_quit.triggered.connect(QApplication.quit)
        menu.addAction(a_show)
        menu.addSeparator()
        menu.addAction(a_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activate)
        self._tray.show()

    def _on_activate(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self._win.isVisible():
                self._win.hide()
            else:
                self._win.show()
                self._win.raise_()

    def notify(self, title: str, msg: str, error: bool = False):
        if QSystemTrayIcon.isSystemTrayAvailable():
            kind = QSystemTrayIcon.Critical if error else QSystemTrayIcon.Information
            self._tray.showMessage(title, msg, kind, 5000)

    def set_tip(self, text: str):
        self._tray.setToolTip(text)

    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()
