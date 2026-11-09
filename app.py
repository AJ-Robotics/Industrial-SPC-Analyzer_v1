"""Industrial SPC Analyzer - application entry point.

Bootstraps the local config DB, optional demo seed, login, and the main window.
"""

import os
import sys
import traceback

# Ensure the application root is on sys.path so absolute imports resolve
# regardless of the current working directory or frozen (PyInstaller) mode.
if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from PySide6.QtWidgets import QApplication, QMessageBox

from config import constants, settings
from database import sqlite_db, demo_seed
from database.repositories import SettingsRepository
from controller import Controller
from ui.login import LoginDialog
from ui.main_window import MainWindow
from utils import logger


def _install_excepthook():
    def hook(exc_type, exc_value, tb):
        logger.exception("Unhandled exception",
                         exc_info=(exc_type, exc_value, tb))
        try:
            QMessageBox.critical(
                None, "Unexpected Error",
                "An unexpected error occurred:\n\n"
                f"{exc_type.__name__}: {exc_value}\n\n"
                "The error was logged to the application log.")
        except Exception:  # noqa: BLE001
            pass
    sys.excepthook = hook


def main():
    # first-run initialization
    sqlite_db.init_db()
    sqlite_db.seed_defaults()
    demo_seed.seed_demo_if_empty()

    # load settings into cache
    settings_repo = SettingsRepository()
    settings.set_values(settings_repo.load_all())

    app = QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setStyle("Fusion")

    # industrial style palette
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F5F6FA"))
    palette.setColor(QPalette.WindowText, QColor("#1B3A57"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.Button, QColor("#E5EAF0"))
    palette.setColor(QPalette.ButtonText, QColor("#1B3A57"))
    app.setPalette(palette)
    app.setStyleSheet("QPushButton{padding:6px 12px;}")

    _install_excepthook()

    logger.info("Application startup: %s %s", constants.APP_NAME,
                constants.APP_VERSION)

    # login / main-window loop (supports logout → re-login)
    while True:
        login = LoginDialog()
        if login.exec() != LoginDialog.Accepted:
            logger.info("Application quit at login.")
            return 0
        user = login.user

        controller = Controller()
        controller._current_user = user.get("username", "")

        window = MainWindow(controller=controller, user=user)
        window.show()
        app.exec()

        if not window.logged_out:
            break

    logger.info("Application shutdown.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
