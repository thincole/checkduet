"""
Shopee Duet Checker — Entry Point
"""

import sys
import os

# Thêm thư mục gốc vào path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from utils.version_mgr import get_current_version


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Shopee Duet Checker")
    app.setApplicationVersion(get_current_version())
    app.setOrganizationName("Thinaptm")

    # App icon
    icon_path = os.path.join(os.path.dirname(__file__), "icons", "app.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
