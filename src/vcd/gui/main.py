import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from vcd.gui.views.main_window import MainWindow
from vcd.gui.models.history_db import JobHistoryDB
from vcd.gui.models.queue_manager import QueueManager
from vcd.gui.managers.settings_manager import SettingsManager
from vcd.gui.managers.tray_manager import TrayManager
from vcd.gui.controllers.main_controller import MainController
from vcd.gui.constants import get_app_icon, THEME

try:
    from vcd.core import media as core
except Exception:
    core = None


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("IAUCourseExp.VCD.v03")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("VCD")
    app.setWindowIcon(get_app_icon())
    app.setStyleSheet(THEME)

    history_db = JobHistoryDB()
    queue_manager = QueueManager()
    settings_manager = SettingsManager()

    win = MainWindow()

    tray = None
    if TrayManager.available():
        tray = TrayManager(win)
        tray.set_tip("VCD v0.3 — Vadana Class Downloader")

    controller = MainController(win, history_db, queue_manager, settings_manager, tray)

    win.show()

    if core is None:
        QMessageBox.critical(win, "Missing vcd_core.py", "vcd_core module not found.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
