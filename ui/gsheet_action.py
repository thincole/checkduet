"""
Nút "📊 Google Sheet" — dùng chung cho tab Scanner và Viral Finder.
"""

import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from utils import gsheet


def export_gsheet(parent, videos: list, cred_path: str, sheet: str, tab: str) -> str:
    """Trả về thông báo để ghi log ("" nếu không làm gì)."""
    if not videos:
        QMessageBox.information(parent, "Không có dữ liệu", "Chưa có video nào trong bảng để xuất!")
        return ""
    if not cred_path or not sheet:
        QMessageBox.warning(parent, "Chưa cấu hình Google Sheet",
                            "Vào tab ⚙️ Cài đặt → mục Google Sheet: chọn file JSON và dán link sheet.")
        return ""

    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        res = gsheet.push(videos, cred_path, sheet, tab)
    finally:
        QApplication.restoreOverrideCursor()

    if not res.get("ok"):
        QMessageBox.warning(parent, "Xuất Google Sheet thất bại", res.get("error") or str(res))
        return f"❌ Google Sheet: {res.get('error')}"

    summary = (f"Ghi thêm {res.get('added', 0)} video mới vào tab “{res.get('sheet')}”, "
               f"bỏ qua {res.get('skipped', 0)} video trùng. Tổng trong tab: {res.get('total', 0)}.")
    box = QMessageBox(parent)
    box.setWindowTitle("Đã xuất Google Sheet")
    box.setText(summary)
    btn_open = box.addButton("📊 Mở Google Sheet", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() == btn_open and res.get("url"):
        webbrowser.open(res["url"])
    return f"📊 Google Sheet: {summary}"
