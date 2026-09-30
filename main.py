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
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            crash_file = os.path.join(os.path.dirname(__file__), "crash.log")
            with open(crash_file, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            _app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Lỗi khởi động",
                f"Ứng dụng gặp lỗi khi khởi động:\n\n{e}\n\nXem chi tiết tại file crash.log"
            )
        except Exception:
            pass
        sys.exit(1)
