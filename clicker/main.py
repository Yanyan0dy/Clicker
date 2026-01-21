"""应用入口。"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from .controller import Controller
from .view import MainWindow


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    window = MainWindow()
    Controller(window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

