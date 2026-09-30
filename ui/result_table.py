"""
Result Table Widget — QTableWidget hiển thị kết quả video
"""

import webbrowser
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu, QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor


COLUMNS = [
    ("Profile ID",   "profile_id",    100),
    ("Video ID",     "video_id",      120),
    ("Duet",         "allow_duet",     70),
    ("Stitch",       "allow_stitch",   70),
    ("Lượt xem",    "play_count",    100),
    ("Lượt thích",  "like_count",    100),
    ("Bình luận",   "comment_count",  90),
    ("Mô tả",        "description",   280),
    ("Tên SP",       "product_name",  220),
    ("Link SP",      "product_url",   230),
    ("Giá (đ)",      "product_price",  90),
    ("Đã bán",       "product_sold",   80),
    ("Link video",   "share_url",     200),
]

VIRAL_COLUMNS = [
    ("Profile ID",   "profile_id",     95),
    ("Video ID",     "video_id",      110),
    ("Duet",         "allow_duet",     70),
    ("Điểm duet",    "duet_score",     90),
    ("View/ngày",    "views_per_day", 100),
    ("Lượt xem",     "play_count",    100),
    ("Lượt thích",   "like_count",     90),
    ("Tương tác %",  "engagement",     85),
    ("Ngày đăng",    "post_date",      90),
    ("Mô tả",        "description",   250),
    ("Tên SP",       "product_name",  220),
    ("Link SP",      "product_url",   230),
    ("Giá (đ)",      "product_price",  90),
    ("Đã bán",       "product_sold",   80),
    ("Link video",   "share_url",     200),
]

INT_FIELDS = ("play_count", "like_count", "comment_count", "share_count", "views_per_day",
              "product_price", "product_sold", "duet_score")

COLOR_ALLOW = QColor("#1a7a3c")   # xanh đậm
COLOR_DENY  = QColor("#c0392b")   # đỏ
COLOR_ROW_ALLOW = QColor("#e8f5e9")
COLOR_ROW_DENY  = QColor("#ffffff")


class NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        return (self.data(Qt.ItemDataRole.UserRole) or 0) < (other.data(Qt.ItemDataRole.UserRole) or 0)


class ResultTable(QTableWidget):
    row_count_changed = pyqtSignal(int)   # tổng số dòng
    videos_deleted    = pyqtSignal(list)  # danh sách video dict bị xóa

    def __init__(self, parent=None, columns: list | None = None):
        super().__init__(parent)
        self.columns = columns or COLUMNS
        self._all_data: list[dict] = []
        self._user_sorted = False   # người dùng đã bấm tiêu đề cột để sắp xếp
        self._setup_table()

    def _setup_table(self):
        self.setColumnCount(len(self.columns))
        self.setHorizontalHeaderLabels([c[0] for c in self.columns])
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(False)
        self.setSortingEnabled(True)
        self.setWordWrap(False)

        header = self.horizontalHeader()
        for i, (_, field, width) in enumerate(self.columns):
            header.resizeSection(i, width)
            if field == "description":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        header.sectionClicked.connect(lambda _: setattr(self, "_user_sorted", True))

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def add_video(self, v: dict):
        """Thêm 1 video vào cuối bảng."""
        self._all_data.append(v)
        # Sorting must be off while filling, otherwise Qt moves the row mid-fill
        sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        row = self.rowCount()
        self.insertRow(row)
        self._fill_row(row, v)
        self.setSortingEnabled(sorting)
        self.row_count_changed.emit(self.rowCount())

    def _row_data(self, row: int) -> dict | None:
        item = self.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole + 1) if item else None

    def _fill_row(self, row: int, v: dict):
        bg = COLOR_ROW_ALLOW if v.get("allow_duet") else COLOR_ROW_DENY

        for col, (_, field, _) in enumerate(self.columns):
            if field == "allow_duet":
                text = "✅ YES" if v.get("allow_duet") else "❌ NO"
                color = COLOR_ALLOW if v.get("allow_duet") else COLOR_DENY
                item = QTableWidgetItem(text)
                item.setForeground(color)
                font = QFont()
                font.setBold(True)
                item.setFont(font)
            elif field == "allow_stitch":
                text = "✅" if v.get("allow_stitch") else "❌"
                item = QTableWidgetItem(text)
            elif field in INT_FIELDS:
                try:
                    val = int(v.get(field) or 0)
                except (TypeError, ValueError):
                    val = 0
                item = NumericItem(f"{val:,}")
                item.setData(Qt.ItemDataRole.UserRole, val)
            elif field == "engagement":
                val = float(v.get(field) or 0)
                item = NumericItem(f"{val:.2f}%")
                item.setData(Qt.ItemDataRole.UserRole, val)
            else:
                item = QTableWidgetItem(str(v.get(field, "")))

            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole + 1, v)
            item.setBackground(bg)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.setItem(row, col, item)

    def set_videos(self, videos: list):
        """
        Thay toàn bộ nội dung bảng. Giữ thứ tự truyền vào, trừ khi người dùng đã bấm
        tiêu đề cột (khi đó sắp xếp lại theo cột đó). Giữ vị trí cuộn.
        """
        header = self.horizontalHeader()
        sec = header.sortIndicatorSection() if self._user_sorted else -1
        order = header.sortIndicatorOrder()
        scroll = self.verticalScrollBar().value()

        self.setUpdatesEnabled(False)
        self.setSortingEnabled(False)
        self._all_data = list(videos)
        self.setRowCount(len(videos))
        for row, v in enumerate(videos):
            self._fill_row(row, v)
        # Bật lại sorting sẽ sắp xếp theo sort indicator; -1 = giữ nguyên thứ tự truyền vào
        header.setSortIndicator(sec, order)
        self.setSortingEnabled(True)
        self.verticalScrollBar().setValue(scroll)
        self.setUpdatesEnabled(True)
        self.row_count_changed.emit(len(videos))

    def clear_results(self):
        self._all_data.clear()
        self.setRowCount(0)
        self._user_sorted = False
        self.row_count_changed.emit(0)

    def filter_duet_only(self, enabled: bool):
        """Ẩn/hiện các row không có duet."""
        for row in range(self.rowCount()):
            v = self._row_data(row) or {}
            self.setRowHidden(row, enabled and not v.get("allow_duet"))

    def visible_videos(self) -> list:
        """Các dòng đang hiện, đúng thứ tự đang sắp xếp trên bảng."""
        out = []
        for row in range(self.rowCount()):
            if not self.isRowHidden(row):
                v = self._row_data(row)
                if v:
                    out.append(v)
        return out

    def get_all_data(self) -> list:
        return self._all_data.copy()

    def get_duet_allowed(self) -> list:
        return [v for v in self._all_data if v.get("allow_duet")]

    # ------------------------------------------------------------------
    # Context menu chuột phải
    # ------------------------------------------------------------------
    def _context_menu(self, pos):
        row = self.rowAt(pos.y())
        v = self._row_data(row) if row >= 0 else None
        if not v:
            return

        menu = QMenu(self)

        act_open  = menu.addAction("🔗 Mở link video")
        act_copy  = menu.addAction("📋 Copy link")
        act_copy_id = menu.addAction("📋 Copy Video ID")
        act_open_sp = act_copy_sp = act_copy_all_sp = None

        prod_urls = list(v.get("product_urls") or [])
        if not prod_urls:
            for it in (v.get("product_items") or []):
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    sid, iid = str(it[0]).strip(), str(it[1]).strip()
                    if sid and iid:
                        u = f"https://shopee.vn/product/{sid}/{iid}"
                        if u not in prod_urls:
                            prod_urls.append(u)
        main_u = v.get("product_url")
        if main_u and main_u not in prod_urls:
            prod_urls.insert(0, main_u)

        if prod_urls:
            menu.addSeparator()
            act_open_sp = menu.addAction("🛒 Mở link sản phẩm")
            act_copy_sp = menu.addAction("📋 Copy link sản phẩm")
            if len(prod_urls) > 1:
                act_copy_all_sp = menu.addAction(f"📋 Copy tất cả link SP ({len(prod_urls)} sản phẩm)")
        menu.addSeparator()
        act_copy_all = menu.addAction("📋 Copy tất cả link duet")

        # Nút xóa dòng
        menu.addSeparator()
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()), reverse=True)
        if row >= 0 and row not in selected_rows:
            selected_rows = [row]
        count = len(selected_rows)
        del_label = f"🗑 Xóa {count} video đã chọn" if count > 1 else "🗑 Xóa video này"
        act_delete = menu.addAction(del_label)

        action = menu.exec(QCursor.pos())

        if action is None:
            return
        if action == act_delete:
            self.delete_selected_rows(selected_rows)
        elif action == act_open_sp:
            webbrowser.open(main_u or prod_urls[0])
        elif action == act_copy_sp:
            QApplication.clipboard().setText(main_u or prod_urls[0])
        elif action == act_copy_all_sp:
            QApplication.clipboard().setText("\n".join(prod_urls))
        elif action == act_open:
            webbrowser.open(v.get("share_url", ""))
        elif action == act_copy:
            QApplication.clipboard().setText(v.get("share_url", ""))
        elif action == act_copy_id:
            QApplication.clipboard().setText(v.get("video_id", ""))
        elif action == act_copy_all:
            urls = "\n".join(
                x["share_url"] for x in self._all_data if x.get("allow_duet")
            )
            QApplication.clipboard().setText(urls)

    def delete_selected_rows(self, rows: list[int] | None = None):
        """Xóa các dòng được chọn khỏi bảng và phát tín hiệu videos_deleted."""
        if rows is None:
            rows = sorted(set(idx.row() for idx in self.selectedIndexes()), reverse=True)
        if not rows:
            return

        count = len(rows)
        msg = f"Bạn có chắc muốn xóa {count} video đã chọn không?" if count > 1 else "Bạn có chắc muốn xóa video này không?"
        ret = QMessageBox.question(
            self, "Xác nhận xóa", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        deleted_videos = []
        for r in rows:
            v = self._row_data(r)
            if v:
                deleted_videos.append(v)

        del_ids = {v.get("video_id") for v in deleted_videos if v.get("video_id")}
        self._all_data = [v for v in self._all_data if v.get("video_id") not in del_ids]

        sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        for r in rows:
            self.removeRow(r)
        self.setSortingEnabled(sorting)

        self.row_count_changed.emit(self.rowCount())
        if deleted_videos:
            self.videos_deleted.emit(deleted_videos)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_rows()
        else:
            super().keyPressEvent(event)
