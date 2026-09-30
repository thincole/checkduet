"""
Viral Finder Tab — quét nhiều KOC/shop, xếp hạng video đang viral có duet
"""

from typing import Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QTextEdit,
    QPushButton, QSpinBox, QCheckBox, QSplitter, QFormLayout, QGridLayout,
    QMessageBox, QApplication, QProgressBar, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from api.headers import REGIONS
from api.shopee_api import ShopeeAPI
from ui.result_table import ResultTable, VIRAL_COLUMNS
from workers.scanner_worker import ScannerWorker
from workers.multi_scanner import MultiScanWorker
from utils.viral import enrich, filter_viral
from utils.exporter import export_csv
from ui.phone_dialog import open_phone_page
from ui.gsheet_action import export_gsheet

# Kho tên hashtag ứng viên; app tự đổi sang hashtag_id đúng theo quốc gia rồi lấy top theo post_count.
# Gồm tag Shopee Video quốc tế + tag đặc thù từng thị trường.
HASHTAG_POOL = [
    "shopeevideo", "shoppevideo", "shopeecreator", "shopeefinds", "shopeehaul", "shopeefashion",
    "shopeestyle", "shopeebeauty", "shopeetechfinds", "fyp", "foryou", "viral", "review", "unboxing",
    # VN
    "xuhuong", "hangmoive", "koluytin", "luotvuimualien", "luotvuimoingay", "shoppeviral",
    # ID / regional
    "racunshopee",
    # per-country
    "shopeeph", "shopeemy", "shopeesg", "shopeeth", "shopeevn",
]


class HashtagLoader(QThread):
    """Nền: đổi tên hashtag → id theo quốc gia, lấy top N (không tốn credit)."""
    done = pyqtSignal(str, list)   # country, [(name, id)]

    def __init__(self, country: str, cookie: str, names: list, top_n: int = 10, parent=None):
        super().__init__(parent)
        self.country, self.cookie, self.names, self.top_n = country, cookie, names, top_n

    def run(self):
        try:
            api = ShopeeAPI(cookie=self.cookie, country=self.country)
            tags = api.top_hashtags(self.names, self.top_n)
        except Exception:
            tags = []
        self.done.emit(self.country, tags)


class ViralTab(QWidget):
    def __init__(self, cfg: dict, get_runtime: Callable[[], dict], log_status: Callable[[str], None],
                 windows_store=None, video_store=None, on_country_change: Callable[[str], None] | None = None):
        """
        get_runtime() trả về dict: cookie, delay_ms, max_videos, sign_api_key, sign_api_url, export_path, country
        windows_store: kho đếm cửa sổ sản phẩm (mọi video quét được đều được ghi vào)
        video_store: kho lưu đầy đủ video theo quốc gia (mở app là có sẵn, không tốn credit)
        on_country_change(code): báo MainWindow đổi thị trường (đồng bộ combo + cookie)
        """
        super().__init__()
        self.cfg = cfg
        self.windows_store = windows_store
        self.video_store = video_store
        self.get_runtime = get_runtime
        self.log_status = log_status
        self.on_country_change = on_country_change
        self.worker: MultiScanWorker | None = None
        self._videos_by_id: dict[str, dict] = {}   # nguồn dữ liệu chuẩn, dedup theo video_id
        self._videos: list[dict] = []
        self._tag_loader: HashtagLoader | None = None
        self._hashtags_by_country = dict(cfg.get("hashtags_by_country") or {})
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(400)
        self._refresh_timer.timeout.connect(self._refresh)
        self._build_ui()

    # ──────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        top = QWidget()
        top_lay = QVBoxLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)

        # ── Chọn thị trường ──
        c_row = QHBoxLayout()
        lbl_c = QLabel("🌏 Quốc gia mục tiêu:")
        lbl_c.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        self.cbo_country = QComboBox()
        self.cbo_country.setMinimumWidth(240)
        for code, info in REGIONS.items():
            self.cbo_country.addItem(f"{info['flag']} {info['name']}", code)
        idx_c = self.cbo_country.findData(self.cfg.get("country", "VN"))
        if idx_c >= 0:
            self.cbo_country.setCurrentIndex(idx_c)
        self.cbo_country.currentIndexChanged.connect(
            lambda _i: self.on_country_change and self.on_country_change(self.cbo_country.currentData()))
        c_row.addWidget(lbl_c)
        c_row.addWidget(self.cbo_country)
        c_row.addStretch()
        top_lay.addLayout(c_row)

        # ── Nguồn ──
        src_row = QHBoxLayout()
        grp_seeds = QGroupBox("KOC / Shop nguồn (tùy chọn — link, ID hoặc username)")
        s_lay = QVBoxLayout(grp_seeds)
        self.txt_seeds = QTextEdit()
        self.txt_seeds.setPlaceholderText("https://sv.shopee.vn/profile/957965727\n957965727\ntenshop")
        self.txt_seeds.setPlainText(self.cfg.get("viral_seeds", ""))
        s_lay.addWidget(self.txt_seeds)
        src_row.addWidget(grp_seeds, 2)

        grp_tags = QGroupBox("#️⃣ Hashtag nguồn (#tên | hashtag_id)")
        t_lay = QVBoxLayout(grp_tags)
        self.txt_tags = QTextEdit()
        t_lay.addWidget(self.txt_tags)
        tag_btn = QHBoxLayout()
        self.lbl_tag_status = QLabel()
        self.lbl_tag_status.setStyleSheet("color: #666; font-size: 11px;")
        self.btn_reload_tags = QPushButton("🔄 Tải hashtag phổ biến")
        self.btn_reload_tags.setToolTip("Tải 10 hashtag phổ biến nhất của quốc gia đang chọn (không tốn credit)")
        self.btn_reload_tags.clicked.connect(lambda: self.load_hashtags(self.cbo_country.currentData(), force=True))
        tag_btn.addWidget(self.lbl_tag_status, 1)
        tag_btn.addWidget(self.btn_reload_tags)
        t_lay.addLayout(tag_btn)
        src_row.addWidget(grp_tags, 2)

        grp_kw = QGroupBox("🕸 Quét lan tự động")
        k_lay = QVBoxLayout(grp_kw)
        self.chk_crawl_tags = QCheckBox("Lan theo hashtag trong video")
        self.chk_crawl_tags.setChecked(self.cfg.get("viral_crawl_hashtags", True))
        self.chk_crawl = QCheckBox("Lan theo creator / shop liên quan")
        self.chk_crawl.setChecked(self.cfg.get("viral_crawl", True))
        k_lay.addWidget(self.chk_crawl_tags)
        k_lay.addWidget(self.chk_crawl)
        hint = QLabel("Ưu tiên hashtag/creator xuất hiện trong video nhiều view.")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        k_lay.addWidget(hint)
        kw_form = QFormLayout()
        self.spin_budget = QSpinBox()
        self.spin_budget.setRange(1, 100000)
        self.spin_budget.setValue(self.cfg.get("viral_credit_budget", 50))
        self.spin_budget.setSuffix(" credit")
        kw_form.addRow("Ngân sách tối đa:", self.spin_budget)
        self.spin_per_tag = QSpinBox()
        self.spin_per_tag.setRange(12, 1200)
        self.spin_per_tag.setSingleStep(12)
        self.spin_per_tag.setValue(self.cfg.get("viral_videos_per_hashtag", 24))
        self.spin_per_tag.setSuffix(" video")
        kw_form.addRow("Mỗi hashtag quét:", self.spin_per_tag)
        self.spin_per_creator = QSpinBox()
        self.spin_per_creator.setRange(48, 4800)
        self.spin_per_creator.setSingleStep(48)
        self.spin_per_creator.setValue(self.cfg.get("viral_videos_per_creator", 48))
        self.spin_per_creator.setSuffix(" video mới nhất")
        kw_form.addRow("Mỗi creator quét:", self.spin_per_creator)
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 20)
        self.spin_threads.setValue(self.cfg.get("viral_threads", 1))
        self.spin_threads.setSuffix(" luồng")
        kw_form.addRow("Chạy song song:", self.spin_threads)
        k_lay.addLayout(kw_form)
        self.lbl_credit = QLabel("1 trang hashtag (12 video) hoặc 1 trang creator (48 video) ≈ 1 credit.\n"
                                 "Nhiều luồng = nhanh hơn, KHÔNG giảm credit; tối đa = số cookie đang có.")
        self.lbl_credit.setStyleSheet("color: #c0392b; font-size: 11px;")
        self.lbl_credit.setWordWrap(True)
        k_lay.addWidget(self.lbl_credit)
        src_row.addWidget(grp_kw, 2)
        top_lay.addLayout(src_row)

        # ── Bộ lọc viral ──
        grp_f = QGroupBox("Tiêu chí viral (đổi là lọc lại ngay, không cần quét lại)")
        grid = QGridLayout(grp_f)

        def spin(maximum, value, step, suffix="", special=None):
            s = QSpinBox()
            s.setRange(0, maximum)
            s.setSingleStep(step)
            s.setValue(value)
            if suffix:
                s.setSuffix(suffix)
            if special:
                s.setSpecialValueText(special)
            s.valueChanged.connect(self._refresh)
            return s

        self.spin_age  = spin(3650, self.cfg.get("viral_max_age_days", 7), 1, " ngày", "Mọi lúc")
        self.spin_views = spin(1_000_000_000, self.cfg.get("viral_min_views", 10000), 5000)
        self.spin_likes = spin(100_000_000, self.cfg.get("viral_min_likes", 0), 100)
        self.spin_vpd  = spin(100_000_000, self.cfg.get("viral_min_vpd", 1000), 500)
        self.spin_sold = spin(100_000_000, self.cfg.get("viral_min_sold", 0), 100)
        self.spin_top  = spin(100_000, self.cfg.get("viral_top_n", 100), 10, special="Tất cả")
        self.chk_duet  = QCheckBox("Chỉ video CÓ duet")
        self.chk_duet.setChecked(self.cfg.get("viral_duet_only", True))
        self.chk_duet.toggled.connect(self._refresh)
        self.cbo_sort = QComboBox()
        self.cbo_sort.addItem("Điểm duet (view + bán chạy)", "duet_score")
        self.cbo_sort.addItem("View/ngày", "views_per_day")
        idx = self.cbo_sort.findData(self.cfg.get("viral_sort_by", "duet_score"))
        self.cbo_sort.setCurrentIndex(idx if idx >= 0 else 0)
        self.cbo_sort.currentIndexChanged.connect(self._refresh)

        # Mục tiêu tìm kiếm: chọn nhanh, tự đặt lại bộ lọc bên dưới
        self.cbo_mode = QComboBox()
        self.cbo_mode.addItem("🎬 Video viral CÓ Duet", "duet")
        self.cbo_mode.addItem("👁 Video viral theo View", "view")
        self.cbo_mode.setCurrentIndex(0 if self.cfg.get("viral_mode", "duet") == "duet" else 1)
        self.cbo_mode.currentIndexChanged.connect(self._on_mode_changed)

        grid.addWidget(QLabel("🎯 Mục tiêu:"), 0, 0);        grid.addWidget(self.cbo_mode, 0, 1, 1, 3)
        grid.addWidget(QLabel("Đăng trong:"), 1, 0);        grid.addWidget(self.spin_age, 1, 1)
        grid.addWidget(QLabel("Lượt xem ≥"), 1, 2);         grid.addWidget(self.spin_views, 1, 3)
        grid.addWidget(QLabel("View/ngày ≥"), 1, 4);        grid.addWidget(self.spin_vpd, 1, 5)
        grid.addWidget(QLabel("Đã bán ≥"), 2, 0);           grid.addWidget(self.spin_sold, 2, 1)
        grid.addWidget(QLabel("Lượt thích ≥"), 2, 2);       grid.addWidget(self.spin_likes, 2, 3)
        grid.addWidget(QLabel("Top:"), 2, 4);               grid.addWidget(self.spin_top, 2, 5)
        grid.addWidget(QLabel("Xếp theo:"), 3, 0);          grid.addWidget(self.cbo_sort, 3, 1, 1, 3)
        grid.addWidget(self.chk_duet, 3, 4, 1, 2)
        top_lay.addWidget(grp_f)

        # ── Nút ──
        btn_row = QHBoxLayout()
        self.lbl_stats = QLabel("Kho: 0 video | Có duet: 0 | Hiện trong bảng: 0")
        self.lbl_stats.setWordWrap(True)
        self.lbl_stats.setToolTip("Bảng chỉ hiện video có duet đạt tiêu chí viral bên trên. "
                                  "Muốn xem mọi video có duet: đặt Lượt xem ≥ 0 và View/ngày ≥ 0.")
        self.lbl_stats.setStyleSheet("font-weight: bold; color: #333; padding: 4px;")
        self.btn_start = QPushButton("🔥 Tìm video viral")
        self.btn_start.clicked.connect(self._start)
        self.btn_stop = QPushButton("⏹ Dừng")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        btn_export = QPushButton("💾 Export CSV")
        btn_export.setObjectName("btn_export")
        btn_export.clicked.connect(self._export)
        btn_copy = QPushButton("📋 Copy link viral")
        btn_copy.clicked.connect(self._copy_links)
        btn_gsheet = QPushButton("📊 Google Sheet")
        btn_gsheet.setObjectName("btn_export")
        btn_gsheet.setToolTip("Ghi danh sách viral đang hiện vào Google Sheet (tab mới mỗi lần)")
        btn_gsheet.clicked.connect(self._export_gsheet)
        btn_phone = QPushButton("📱 Điện thoại")
        btn_phone.setToolTip("Xuất trang danh sách và mở trên điện thoại bằng mã QR")
        btn_phone.clicked.connect(self._open_phone)
        btn_row.addWidget(self.lbl_stats)
        btn_row.addStretch()
        for b in (self.btn_start, self.btn_stop, btn_export, btn_gsheet, btn_copy, btn_phone):
            btn_row.addWidget(b)
        top_lay.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        top_lay.addWidget(self.progress_bar)

        splitter.addWidget(top)

        # ── Bảng + log ──
        bottom = QSplitter(Qt.Orientation.Horizontal)
        self.grp_table = QGroupBox("Video đáng làm duet")
        grp_t = self.grp_table
        t_lay = QVBoxLayout(grp_t)
        self.table = ResultTable(columns=VIRAL_COLUMNS)
        self.table.videos_deleted.connect(self._on_viral_videos_deleted)
        t_lay.addWidget(self.table)
        bottom.addWidget(grp_t)

        grp_log = QGroupBox("Log")
        grp_log.setFixedWidth(280)
        l_lay = QVBoxLayout(grp_log)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-size: 11px; font-family: Consolas;")
        l_lay.addWidget(self.txt_log)
        bottom.addWidget(grp_log)
        bottom.setSizes([820, 280])

        splitter.addWidget(bottom)
        splitter.setSizes([330, 400])
        root.addWidget(splitter)

        # Nạp hashtag cho quốc gia hiện tại: dùng cache, nếu chưa có thì tải nền
        self.load_hashtags(self.cfg.get("country", "VN"))
        # Nạp video đã lưu của quốc gia hiện tại (không tốn credit)
        self._load_country_cache(self.cfg.get("country", "VN"))

    def _load_country_cache(self, country: str):
        """Đổ video đã lưu trong kho của quốc gia vào bảng (mở app / đổi nước là có ngay)."""
        self._videos_by_id = {}
        if self.video_store is not None:
            for v in self.video_store.list(country):
                vid = str(v.get("video_id") or "")
                if vid:
                    self._videos_by_id[vid] = enrich(v)
        self._refresh()

    # ──────────────────────────────────────────────────────────
    def load_hashtags(self, country: str, force: bool = False):
        """Đổ 10 hashtag phổ biến của quốc gia vào ô. Ưu tiên cache; chưa có (hoặc force) thì tải nền."""
        country = country or "VN"
        cached = self._hashtags_by_country.get(country)
        if cached and not force:
            self.txt_tags.setPlainText(cached)
            self.lbl_tag_status.setText(f"Hashtag {country} (đã lưu)")
            return
        # Bỏ qua cấu hình cũ viral_hashtags cho VN ở lần đầu nếu có
        if not force and country == self.cfg.get("country") and self.cfg.get("viral_hashtags") and not self._hashtags_by_country:
            self.txt_tags.setPlainText(self.cfg["viral_hashtags"])
        if self._tag_loader and self._tag_loader.isRunning():
            self._tag_loader.done.disconnect()
            self._tag_loader.terminate()
        self.lbl_tag_status.setText(f"⏳ Đang tải hashtag phổ biến của {country}...")
        self.btn_reload_tags.setEnabled(False)
        cookie = self.get_runtime().get("cookie", "")
        self._tag_loader = HashtagLoader(country, cookie, HASHTAG_POOL, top_n=10)
        self._tag_loader.done.connect(self._on_hashtags_loaded)
        self._tag_loader.start()

    def _on_hashtags_loaded(self, country: str, tags: list):
        self.btn_reload_tags.setEnabled(True)
        if not tags:
            self.lbl_tag_status.setText(f"⚠️ Không tải được hashtag {country} (kiểm tra mạng)")
            return
        text = "\n".join(f"#{name} | {hid}" for name, hid in tags)
        self._hashtags_by_country[country] = text
        self.cfg["hashtags_by_country"] = self._hashtags_by_country
        # Chỉ đổ vào ô nếu người dùng vẫn đang ở quốc gia này
        if self.cbo_country.currentData() == country:
            self.txt_tags.setPlainText(text)
            self.lbl_tag_status.setText(f"✅ {len(tags)} hashtag phổ biến của {country}")

    # ──────────────────────────────────────────────────────────
    def save_to_cfg(self):
        self.cfg["viral_seeds"]           = self.txt_seeds.toPlainText().strip()
        self.cfg["viral_crawl"]           = self.chk_crawl.isChecked()
        self.cfg["viral_crawl_hashtags"]  = self.chk_crawl_tags.isChecked()
        # Lưu hashtag đang gõ vào đúng quốc gia đang chọn
        self._hashtags_by_country[self.cbo_country.currentData()] = self.txt_tags.toPlainText().strip()
        self.cfg["hashtags_by_country"]   = self._hashtags_by_country
        self.cfg["viral_hashtags"]        = self.txt_tags.toPlainText().strip()
        self.cfg["viral_credit_budget"]   = self.spin_budget.value()
        self.cfg["viral_videos_per_hashtag"] = self.spin_per_tag.value()
        self.cfg["viral_videos_per_creator"] = self.spin_per_creator.value()
        self.cfg["viral_threads"]         = self.spin_threads.value()
        self.cfg["viral_max_age_days"]    = self.spin_age.value()
        self.cfg["viral_min_views"]       = self.spin_views.value()
        self.cfg["viral_min_likes"]       = self.spin_likes.value()
        self.cfg["viral_min_vpd"]         = self.spin_vpd.value()
        self.cfg["viral_min_sold"]        = self.spin_sold.value()
        self.cfg["viral_sort_by"]         = self.cbo_sort.currentData()
        self.cfg["viral_mode"]            = self.cbo_mode.currentData()
        self.cfg["viral_duet_only"]       = self.chk_duet.isChecked()
        self.cfg["viral_top_n"]           = self.spin_top.value()

    def log(self, msg: str):
        self.txt_log.append(msg)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _parse_tags(self) -> list:
        tags = []
        for line in self.txt_tags.toPlainText().splitlines():
            if "|" not in line:
                continue
            name, tid = (p.strip() for p in line.split("|", 1))
            if tid.isdigit() and name:
                tags.append((tid, name if name.startswith("#") else f"#{name}"))
        return tags

    @staticmethod
    def _lines(text: str) -> list:
        return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]

    def _start(self):
        rt = self.get_runtime()
        if not rt["cookie"]:
            QMessageBox.warning(self, "Thiếu Cookie", "Vui lòng nhập Cookie trong tab Cài đặt!")
            return
        seeds = self._lines(self.txt_seeds.toPlainText())
        tags = self._parse_tags()
        if not seeds and not tags:
            QMessageBox.warning(self, "Thiếu nguồn",
                                "Nhập ít nhất 1 KOC/shop hoặc 1 hashtag (dạng #ten | hashtag_id)!")
            return

        # Giữ lại video đã có trong kho; quét mới gộp/cập nhật vào, không xóa
        self.txt_log.clear()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        kept = len(self._videos_by_id)
        self.log(f"🔥 Bắt đầu: {len(seeds)} creator, {len(tags)} hashtag, "
                 f"ngân sách {self.spin_budget.value()} credit"
                 + (f" (đã có {kept} video trong kho)" if kept else ""))

        self.worker = MultiScanWorker(
            shop_list       = [(s, "") for s in seeds],
            cookie          = rt["cookie"],
            delay_ms        = rt["delay_ms"],
            max_videos      = self.spin_per_creator.value(),
            sign_api_key    = rt["sign_api_key"],
            sign_api_url    = rt["sign_api_url"],
            country         = rt.get("country", "VN"),
            hashtags        = tags,
            hashtag_videos  = self.spin_per_tag.value(),
            crawl_creators  = self.chk_crawl.isChecked(),
            crawl_hashtags  = self.chk_crawl_tags.isChecked(),
            credit_budget   = self.spin_budget.value(),
            num_threads     = self.spin_threads.value(),
        )
        self.worker.progress.connect(self.log)
        self.worker.video_found.connect(self._on_video)
        self.worker.all_done.connect(self._on_done)
        self.worker.error.connect(lambda m: self.log(f"❌ ERROR: {m}"))
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.stop()
        self.btn_stop.setEnabled(False)
        self.log("⏹ Đang dừng...")

    def _on_video(self, v: dict):
        vid = str(v.get("video_id") or "")
        if not vid:
            return
        self._videos_by_id[vid] = enrich(v)   # dedup/cập nhật theo video_id
        if self.windows_store is not None:
            self.windows_store.add_video(v)
        if self.video_store is not None:
            self.video_store.add_video(v, self.cbo_country.currentData())
        # Gom nhiều video về cùng lúc thành 1 lần vẽ lại bảng
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _on_done(self, total: int, allow: int):
        self._refresh_timer.stop()
        if self.windows_store is not None:
            self.windows_store.save()
        if self.video_store is not None:
            self.video_store.save()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._refresh()
        self.log_status(f"🔥 Xong: {total} video mới quét, kho có {len(self._videos_by_id)} video.")

    def _on_viral_videos_deleted(self, deleted_videos: list):
        country = ((self.get_runtime() or {}).get("country", "VN")) if self.get_runtime else "VN"
        for v in deleted_videos:
            vid = v.get("video_id")
            if vid:
                if vid in self._videos_by_id:
                    del self._videos_by_id[vid]
                if self.video_store:
                    self.video_store.delete_video(vid, country)
                if self.windows_store:
                    self.windows_store.delete_video(vid)
        self._refresh()
        self.log_status(f"🗑 Đã xóa {len(deleted_videos)} video khỏi danh sách.")

    def _on_mode_changed(self, *_):
        """Đổi mục tiêu: đặt lại lọc duet và cách xếp cho phù hợp, rồi lọc lại bảng."""
        duet_mode = self.cbo_mode.currentData() == "duet"
        for w in (self.chk_duet, self.cbo_sort):
            w.blockSignals(True)
        self.chk_duet.setChecked(duet_mode)
        self.cbo_sort.setCurrentIndex(self.cbo_sort.findData("duet_score" if duet_mode else "views_per_day"))
        for w in (self.chk_duet, self.cbo_sort):
            w.blockSignals(False)
        self._refresh()

    def _current(self) -> list:
        return filter_viral(
            self._videos,
            max_age_days      = self.spin_age.value(),
            min_views         = self.spin_views.value(),
            min_likes         = self.spin_likes.value(),
            min_views_per_day = self.spin_vpd.value(),
            min_sold          = self.spin_sold.value(),
            duet_only         = self.chk_duet.isChecked(),
            sort_by           = self.cbo_sort.currentData(),
            top_n             = self.spin_top.value(),
        )

    def _refresh(self, *_):
        self._videos = list(self._videos_by_id.values())   # dựng lại từ nguồn chuẩn (dedup)
        result = self._current()
        self.table.set_videos(result)
        label = "Điểm duet" if self.cbo_sort.currentData() == "duet_score" else "View/ngày"
        what = "Video viral CÓ Duet" if self.cbo_mode.currentData() == "duet" else "Video viral theo View"
        self.grp_table.setTitle(f"{what} (xếp theo {label})")
        duet = sum(1 for v in self._videos if v.get("allow_duet"))
        text = f"Kho: {len(self._videos)} video | Có duet: {duet} | Hiện trong bảng: {len(result)}"
        hint = self._diagnose() if self._videos and not result else ""
        self.lbl_stats.setText(text + (f"  —  {hint}" if hint else ""))
        self.lbl_stats.setStyleSheet(
            f"font-weight: bold; padding: 4px; color: {'#c0392b' if hint else '#333'};")

    def _diagnose(self) -> str:
        """Giải thích vì sao không video nào đạt tiêu chí, kèm ngưỡng thực tế cao nhất."""
        pool = filter_viral(self._videos, max_age_days=self.spin_age.value(),
                            duet_only=self.chk_duet.isChecked())
        if not pool:
            what = "có duet" if self.chk_duet.isChecked() else ""
            return f"không có video {what} trong khoảng 'Đăng trong' đã chọn".replace("  ", " ")
        best_vpd = max(v.get("views_per_day") or 0 for v in pool)
        best_views = max(v.get("play_count") or 0 for v in pool)
        return (f"tiêu chí quá cao: cao nhất chỉ {best_vpd:,} view/ngày, {best_views:,} lượt xem "
                f"→ hạ 'View/ngày ≥' / 'Lượt xem ≥'")

    def _export_source(self) -> list:
        """Video để xuất: danh sách viral đang hiện; nếu rỗng thì hỏi xuất video có duet / tất cả."""
        result = self.table.visible_videos()
        if result:
            return result
        if not self._videos:
            QMessageBox.information(self, "Không có dữ liệu", "Chưa quét video nào!")
            return []
        duet = [v for v in self._videos if v.get("allow_duet")]
        box = QMessageBox(self)
        box.setWindowTitle("Không có video đạt tiêu chí viral")
        box.setText(f"Không video nào đạt tiêu chí hiện tại ({self._diagnose()}).\n\n"
                    f"Bạn muốn xuất danh sách nào?")
        b_duet = box.addButton(f"Video có duet ({len(duet)})", QMessageBox.ButtonRole.AcceptRole)
        b_all = box.addButton(f"Tất cả đã quét ({len(self._videos)})", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Hủy", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        chosen = duet if box.clickedButton() == b_duet else self._videos if box.clickedButton() == b_all else []
        key = self.cbo_sort.currentData()
        return sorted(chosen, key=lambda x: (x.get(key) or 0, x.get("play_count") or 0), reverse=True)

    def _export(self):
        result = self._export_source()
        if not result:
            return
        path = export_csv(result, self.get_runtime()["export_path"], prefix="viral")
        self.log(f"💾 Exported {len(result)} video: {path}")
        self.log_status(f"✅ Đã export: {path}")

    def _copy_links(self):
        result = self._export_source()
        if not result:
            return
        QApplication.clipboard().setText("\n".join(v["share_url"] for v in result))
        self.log_status(f"📋 Đã copy {len(result)} link video.")

    def _open_phone(self):
        result = self._export_source()
        if result:
            open_phone_page(self, result, self.get_runtime()["export_path"],
                            title="Shopee Duet Checker — Video viral có duet", prefix="viral_list")

    def _export_gsheet(self):
        result = self._export_source()
        if not result:
            return
        rt = self.get_runtime()
        msg = export_gsheet(self, result, rt["gsheet_credentials"], rt["gsheet_sheet"], rt["gsheet_tab"])
        if msg:
            self.log(msg)

    def shutdown(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(8000)
        if self._tag_loader and self._tag_loader.isRunning():
            self._tag_loader.wait(3000)
