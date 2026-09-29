"""
Tab "🪟 Cửa sổ SP" — đếm số video (đã quét) gắn từng sản phẩm.
"""

import csv
import os
import webbrowser
from datetime import datetime
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox, QApplication,
)

from ui.result_table import NumericItem
from utils.windows_store import WindowsStore, parse_product_link


class WindowsTab(QWidget):
    def __init__(self, store: WindowsStore, get_runtime: Callable[[], dict], log_status: Callable[[str], None]):
        super().__init__()
        self.store = store
        self.get_runtime = get_runtime
        self.log_status = log_status
        self._rows: list[tuple[str, str, int]] = []   # (tên, link, số cửa sổ)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        grp = QGroupBox("Link sản phẩm (mỗi dòng 1 link — để trống = xem tất cả sản phẩm đã gặp)")
        g = QVBoxLayout(grp)
        self.txt_links = QTextEdit()
        self.txt_links.setPlaceholderText("https://shopee.vn/product/141872172/14227187261\n"
                                          "https://shopee.vn/Ten-san-pham-i.141872172.14227187261\n"
                                          "https://s.shopee.vn/4L9y1kdkkb")
        self.txt_links.setFixedHeight(110)
        g.addWidget(self.txt_links)
        row = QHBoxLayout()
        btn_count = QPushButton("🔢 Đếm cửa sổ")
        btn_count.clicked.connect(self.refresh)
        btn_export = QPushButton("💾 Export CSV")
        btn_export.setObjectName("btn_export")
        btn_export.clicked.connect(self._export)
        btn_clear = QPushButton("🗑 Xóa dữ liệu đếm")
        btn_clear.setObjectName("btn_stop")
        btn_clear.clicked.connect(self._clear)
        row.addWidget(btn_count)
        row.addWidget(btn_export)
        row.addStretch()
        row.addWidget(btn_clear)
        g.addLayout(row)
        root.addWidget(grp)

        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #555; padding: 4px;")
        root.addWidget(self.lbl_info)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tên SP", "Link SP", "Số cửa sổ"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.resizeSection(1, 330)
        h.resizeSection(2, 100)
        self.table.cellDoubleClicked.connect(self._open_row)
        self.table.setToolTip("Nhấp đúp để mở sản phẩm")
        root.addWidget(self.table)
        self._update_info()

    # ──────────────────────────────────────────────────────────
    def _update_info(self):
        self.lbl_info.setText(
            f"Kho dữ liệu: {self.store.product_count():,} sản phẩm từ {self.store.video_total():,} video đã quét "
            "(cộng dồn mọi lần quét ở Scanner và Viral Finder). "
            "Số cửa sổ = số video đã quét có gắn sản phẩm → là số tối thiểu, quét càng nhiều càng sát."
        )

    def refresh(self):
        base = self.get_runtime().get("base_host", "https://shopee.vn")
        lines = [l.strip() for l in self.txt_links.toPlainText().splitlines() if l.strip()]
        rows, bad = [], []
        if lines:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                for line in lines:
                    ids = parse_product_link(line)
                    if not ids:
                        bad.append(line)
                        continue
                    shop_id, item_id = ids
                    name, n = self.store.count(item_id)
                    rows.append((name or "(chưa gặp trong video đã quét)", f"{base}/product/{shop_id}/{item_id}", n))
            finally:
                QApplication.restoreOverrideCursor()
        else:
            rows = [(name or "(chưa có tên — nhấp đúp để mở)", f"{base}/product/{shop}/{item}", n)
                    for shop, item, name, n in self.store.all_rows()]

        self._rows = rows
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, (name, link, n) in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(link))
            cnt = NumericItem(f"{n:,}")
            cnt.setData(Qt.ItemDataRole.UserRole, n)
            cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 2, cnt)
        self.table.setSortingEnabled(True)
        self._update_info()
        if bad:
            QMessageBox.warning(self, "Không đọc được link",
                                "Không nhận ra các link sau:\n" + "\n".join(bad[:15]))

    def _open_row(self, row: int, _col: int):
        item = self.table.item(row, 1)
        if item and item.text().startswith("http"):
            webbrowser.open(item.text())

    def _export(self):
        if not self._rows:
            QMessageBox.information(self, "Không có dữ liệu", "Bấm 'Đếm cửa sổ' trước!")
            return
        export_dir = self.get_runtime()["export_path"]
        os.makedirs(export_dir, exist_ok=True)
        path = os.path.join(export_dir, f"cua_so_sp_{datetime.now():%Y%m%d_%H%M%S}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Tên SP", "Link SP", "Số cửa sổ"])
            w.writerows(self._rows)
        self.log_status(f"✅ Đã export: {path}")

    def _clear(self):
        if QMessageBox.question(self, "Xóa dữ liệu đếm",
                                "Xóa toàn bộ dữ liệu đếm cửa sổ đã tích lũy?") != QMessageBox.StandardButton.Yes:
            return
        self.store.clear()
        self.table.setRowCount(0)
        self._rows = []
        self._update_info()
