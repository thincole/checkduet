"""
Mở danh sách video trên điện thoại: xuất trang HTML, phát qua Wi-Fi nội bộ, hiện mã QR.
"""

import os
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QApplication,
)

from utils.html_export import build_html, export_html

try:
    import qrcode
except ImportError:  # app vẫn chạy được, chỉ không có mã QR
    qrcode = None


def lan_ip() -> str:
    """IP của máy trong mạng nội bộ (không gửi gói tin nào ra ngoài)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class PageServer:
    """HTTP server chỉ trả đúng 1 trang HTML ở '/'; mọi đường dẫn khác 404."""

    def __init__(self, html: str):
        body = html.encode("utf-8")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.split("?")[0] not in ("/", "/index.html"):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = None
        for port in (8765, 8766, 8767, 0):
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
                break
            except OSError:
                continue
        if self.httpd is None:
            raise OSError("Không mở được cổng cho máy chủ trang điện thoại")
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


def qr_pixmap(text: str, size: int = 260) -> QPixmap | None:
    if qrcode is None:
        return None
    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    cell = max(size // n, 1)
    pm = QPixmap(n * cell, n * cell)
    pm.fill(QColor("white"))
    p = QPainter(pm)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("black"))
    for y, row in enumerate(matrix):
        for x, on in enumerate(row):
            if on:
                p.drawRect(x * cell, y * cell, cell, cell)
    p.end()
    return pm


class PhoneDialog(QDialog):
    def __init__(self, parent, html: str, file_path: str, count: int):
        super().__init__(parent)
        self.setWindowTitle("📱 Mở danh sách trên điện thoại")
        self.file_path = file_path
        self.server = PageServer(html)
        self.url = f"http://{lan_ip()}:{self.server.port}/"

        lay = QVBoxLayout(self)
        head = QLabel(f"<b>{count} video</b> — quét mã QR bằng camera điện thoại")
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(head)

        pm = qr_pixmap(self.url)
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if pm:
            qr_label.setPixmap(pm)
        else:
            qr_label.setText("(Chưa cài thư viện qrcode — gõ địa chỉ bên dưới vào trình duyệt điện thoại)")
        lay.addWidget(qr_label)

        url_label = QLabel(f'<a href="{self.url}" style="font-size:16px">{self.url}</a>')
        url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        url_label.setOpenExternalLinks(True)
        lay.addWidget(url_label)

        hint = QLabel(
            "• Điện thoại và máy tính phải dùng <b>cùng mạng Wi-Fi</b>.<br>"
            "• Nếu Windows hỏi tường lửa: chọn <b>Cho phép</b> (mạng Riêng tư).<br>"
            "• Trên điện thoại, bấm <b>▶ Mở trong app Shopee</b> ở từng video.<br>"
            "• Trang chỉ truy cập được khi cửa sổ này còn mở."
        )
        hint.setStyleSheet("color:#555; font-size:12px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        row = QHBoxLayout()
        b_copy = QPushButton("📋 Copy địa chỉ")
        b_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.url))
        b_file = QPushButton("🌐 Mở trên máy tính")
        b_file.clicked.connect(lambda: webbrowser.open(self.url))
        b_close = QPushButton("Đóng")
        b_close.setObjectName("btn_stop")
        b_close.clicked.connect(self.accept)
        for b in (b_copy, b_file, b_close):
            row.addWidget(b)
        lay.addLayout(row)

        saved = QLabel(f"Đã lưu file: {file_path}")
        saved.setStyleSheet("color:#888; font-size:11px;")
        saved.setWordWrap(True)
        lay.addWidget(saved)
        self.setMinimumWidth(420)

    def done(self, result):
        self.server.stop()
        super().done(result)


def open_phone_page(parent, videos: list, export_dir: str, title: str, prefix: str = "duet_list"):
    """Xuất HTML + mở hộp thoại QR. Dùng chung cho tab Scanner và Viral Finder."""
    if not videos:
        QMessageBox.information(parent, "Không có dữ liệu", "Chưa có video nào trong bảng để xuất!")
        return
    html = build_html(videos, title)
    path = export_html(videos, export_dir, prefix=prefix, title=title)
    try:
        dlg = PhoneDialog(parent, html, os.path.abspath(path), len(videos))
    except OSError as e:
        QMessageBox.warning(parent, "Không mở được máy chủ", f"{e}\nFile HTML đã lưu tại:\n{path}")
        return
    dlg.exec()
