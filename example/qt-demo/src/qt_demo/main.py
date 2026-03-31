from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


def create_window() -> QWidget:
    window = QWidget()
    window.setWindowTitle("uvpack Qt demo")

    label = QLabel("Hello from uvpack Qt demo!")
    label.setAlignment(Qt.AlignCenter)

    button = QPushButton("Close")
    button.clicked.connect(window.close)  # type: ignore[arg-type]

    layout = QVBoxLayout()
    layout.addWidget(label)
    layout.addWidget(button, alignment=Qt.AlignCenter)

    window.setLayout(layout)
    window.resize(400, 200)
    return window


def main() -> int:
    """
    CLI entry point used by [project.scripts].

    Creates a QApplication (if needed) and shows a single window.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = create_window()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

