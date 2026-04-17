import sys

from PySide6.QtWidgets import QApplication

from filtre_app.ui.main_window import MicrophoneFilterApp


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = MicrophoneFilterApp()
    window.show()
    return app.exec()
