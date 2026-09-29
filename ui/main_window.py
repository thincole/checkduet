"""
Main Window — PyQt6 UI chính
Shopee Duet Checker Tool
"""

import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTextEdit, QLineEdit,
    QCheckBox, QSpinBox, QFileDialog, QSplitter,
    QGroupBox, QFormLayout, QProgressBar, QApplication,
    QMessageBox, QStatusBar, QComboBox,
)
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QFont, QIcon

from ui.result_table import ResultTable
from ui.viral_tab import ViralTab
from workers.scanner_worker import ScannerWorker
from api.shopee_api import ShopeeAPI, DEFAULT_SIGN_API_URL, parse_cookies
from api.headers import REGIONS, get_region
from utils.exporter import export_csv, export_json, export_duet_urls
from utils import gsheet
from ui.phone_dialog import open_phone_page
from ui.gsheet_action import export_gsheet
from ui.windows_tab import WindowsTab
from utils.windows_store import WindowsStore
from utils.video_store import VideoStore
from utils.version_mgr import get_current_version
import config.settings as cfg_mgr

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log.txt")

# ────────────────────────── Stylesheet ──────────────────────────
STYLE = """
QMainWindow { background: #f5f6fa; }

#header {
    font-size: 20px;
    font-weight: bold;
    color: white;
    padding: 14px 20px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #667eea, stop:0.5 #764ba2, stop:1 #f093fb);
    border-radius: 8px;
    margin-bottom: 6px;
}

QPushButton {
    background: #667eea;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover  { background: #5a6fd6; }
QPushButton:pressed{ background: #4a5bc6; }
QPushButton:disabled { background: #b0b0b0; }

QPushButton#btn_stop {
    background: #e74c3c;
}
QPushButton#btn_stop:hover { background: #c0392b; }

QPushButton#btn_export {
    background: #27ae60;
}
QPushButton#btn_export:hover { background: #1e8449; }

QTextEdit, QLineEdit {
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 6px;
    background: white;
    font-size: 12px;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    background: white;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QTabBar::tab {
    padding: 8px 20px;
    font-size: 13px;
    font-weight: bold;
}
QTabBar::tab:selected { color: #667eea; border-bottom: 2px solid #667eea; }

QProgressBar {
    border: 1px solid #ddd;
    border-radius: 4px;
    height: 18px;
    text-align: center;
}
QProgressBar::chunk { background: #667eea; border-radius: 4px; }

QStatusBar { background: #ecf0f1; font-size: 12px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg     = cfg_mgr.load()
        self._active_country = self.cfg.get("country", "VN")
        # Cookie lưu riêng theo quốc gia; chuyển đổi từ cấu hình cookie đơn lẻ cũ
        self.cookies_by_country = dict(self.cfg.get("cookies_by_country") or {})
        if not self.cookies_by_country and self.cfg.get("cookie"):
            self.cookies_by_country[self._active_country] = self.cfg["cookie"]
        self.windows_store = WindowsStore()
        self.video_store = VideoStore()
        self.worker: ScannerWorker | None = None
        self._results: list = []

        self.version = get_current_version()
        self.setWindowTitle(f"Shopee Duet Checker v{self.version} — By Thinaptm")
        self.resize(self.cfg.get("window_width", 1100),
                    self.cfg.get("window_height", 700))
        self.setStyleSheet(STYLE)
        self._build_ui()

    # ──────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # Header
        header = QLabel(f"🔍 Shopee Duet Checker v{self.version}")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(header)

        # Tabs
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Sẵn sàng.")

        tabs = QTabWidget()
        scanner_tab  = self._build_tab_scanner()
        settings_tab = self._build_tab_settings()
        status = lambda m: self.status.showMessage(m, 5000)
        self.viral_tab = ViralTab(self.cfg, self._runtime, status, windows_store=self.windows_store,
                                  video_store=self.video_store, on_country_change=self._on_country_changed)
        self.windows_tab = WindowsTab(self.windows_store, self._runtime, status)
        tabs.addTab(scanner_tab, "🔍 Scanner")
        tabs.addTab(self.viral_tab, "🔥 Viral Finder")
        tabs.addTab(self.windows_tab, "🪟 Cửa sổ SP")
        tabs.addTab(settings_tab, "⚙️ Cài đặt")
        tabs.currentChanged.connect(
            lambda i: self.windows_tab.refresh() if tabs.widget(i) is self.windows_tab
            and not self.windows_tab.txt_links.toPlainText().strip() else None)
        root.addWidget(tabs)

    def _runtime(self) -> dict:
        """Giá trị cài đặt hiện tại trên UI (kể cả khi chưa bấm Lưu)."""
        country = self.cbo_country.currentData() if hasattr(self, "cbo_country") else self.cfg.get("country", "VN")
        return {
            "country":      country or "VN",
            "base_host":    f"https://{get_region(country or 'VN')['domain']}",
            "cookie":       self.txt_cookie.toPlainText().strip(),
            "delay_ms":     self.spin_delay.value(),
            "max_videos":   self.spin_max.value(),
            "sign_api_key": self.txt_api_key.text().strip(),
            "sign_api_url": self.txt_sign_url.text().strip() or DEFAULT_SIGN_API_URL,
            "export_path":  self._get_export_dir(),
            "gsheet_credentials": self.txt_gsheet_cred.text().strip(),
            "gsheet_sheet":       self.txt_gsheet_sheet.text().strip(),
            "gsheet_tab":         self.txt_gsheet_tab.text().strip() or (country or "VN"),
        }

    # ──────────────────── Tab Scanner ─────────────────────────
    def _build_tab_scanner(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Top: Input + Controls ──
        top = QWidget()
        top_lay = QVBoxLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)

        # Input group
        grp_input = QGroupBox("Danh sách Shop / Profile")
        g_lay = QVBoxLayout(grp_input)

        # Hàng chọn quốc gia
        cbo_row = QHBoxLayout()
        lbl_cbo = QLabel("🌏 Quốc gia mục tiêu:")
        lbl_cbo.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50;")
        self.cbo_country = QComboBox()
        self.cbo_country.setMinimumWidth(240)
        for code, info in REGIONS.items():
            self.cbo_country.addItem(f"{info['flag']} {info['name']}", code)
        cur_idx = self.cbo_country.findData(self.cfg.get("country", "VN"))
        if cur_idx >= 0:
            self.cbo_country.setCurrentIndex(cur_idx)
        self.cbo_country.currentIndexChanged.connect(
            lambda _i: self._on_country_changed(self.cbo_country.currentData()))
        cbo_row.addWidget(lbl_cbo)
        cbo_row.addWidget(self.cbo_country)
        cbo_row.addStretch()
        g_lay.addLayout(cbo_row)

        cur_reg = REGIONS.get(self.cfg.get("country", "VN"), REGIONS["VN"])
        self.lbl_hint = QLabel()
        self.lbl_hint.setStyleSheet("color: #666; font-size: 11px;")
        self._update_hint(cur_reg)
        g_lay.addWidget(self.lbl_hint)

        self.txt_shops = QTextEdit()
        self._update_placeholder(cur_reg)
        self.txt_shops.setFixedHeight(130)
        g_lay.addWidget(self.txt_shops)

        # Buttons import / clear
        btn_row = QHBoxLayout()
        btn_import = QPushButton("📂 Import file .txt")
        btn_import.clicked.connect(self._import_file)
        btn_clear = QPushButton("🗑 Xóa danh sách")
        btn_clear.clicked.connect(self.txt_shops.clear)
        btn_row.addWidget(btn_import)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        g_lay.addLayout(btn_row)

        top_lay.addWidget(grp_input)

        # Filter + controls
        ctrl_row = QHBoxLayout()

        self.chk_filter = QCheckBox("Chỉ hiện video CÓ duet")
        self.chk_filter.setChecked(self.cfg.get("filter_duet_only", False))
        self.chk_filter.toggled.connect(self._on_filter_changed)

        self.btn_start = QPushButton("▶ Bắt đầu Scan")
        self.btn_start.clicked.connect(self._start_scan)

        self.btn_stop = QPushButton("⏹ Dừng")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_scan)

        self.btn_export_csv  = QPushButton("💾 Export CSV")
        self.btn_export_csv.setObjectName("btn_export")
        self.btn_export_csv.clicked.connect(self._export_csv)

        self.btn_export_json = QPushButton("💾 Export JSON")
        self.btn_export_json.setObjectName("btn_export")
        self.btn_export_json.clicked.connect(self._export_json)

        self.btn_copy_urls = QPushButton("📋 Copy URL duet")
        self.btn_copy_urls.clicked.connect(self._copy_duet_urls)

        self.btn_phone = QPushButton("📱 Điện thoại")
        self.btn_phone.setToolTip("Xuất trang danh sách các video đang hiện và mở trên điện thoại bằng mã QR")
        self.btn_phone.clicked.connect(self._open_phone)

        self.btn_gsheet = QPushButton("📊 Google Sheet")
        self.btn_gsheet.setObjectName("btn_export")
        self.btn_gsheet.setToolTip("Ghi các video đang hiện vào Google Sheet (tab mới mỗi lần)")
        self.btn_gsheet.clicked.connect(self._export_gsheet)

        ctrl_row.addWidget(self.chk_filter)
        ctrl_row.addStretch()
        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_stop)
        ctrl_row.addWidget(self.btn_export_csv)
        ctrl_row.addWidget(self.btn_export_json)
        ctrl_row.addWidget(self.btn_gsheet)
        ctrl_row.addWidget(self.btn_copy_urls)
        ctrl_row.addWidget(self.btn_phone)

        top_lay.addLayout(ctrl_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(False)
        top_lay.addWidget(self.progress_bar)

        # Stats label
        self.lbl_stats = QLabel("Video: 0  |  ✅ Duet: 0  |  ❌ No duet: 0")
        self.lbl_stats.setStyleSheet("font-weight: bold; color: #333; padding: 4px;")
        top_lay.addWidget(self.lbl_stats)

        splitter.addWidget(top)

        # ── Bottom: Table + Log ──
        bottom = QSplitter(Qt.Orientation.Horizontal)

        # Result table
        grp_table = QGroupBox("Kết quả")
        t_lay = QVBoxLayout(grp_table)
        self.result_table = ResultTable()
        self.result_table.row_count_changed.connect(self._update_stats)
        t_lay.addWidget(self.result_table)
        bottom.addWidget(grp_table)

        # Log panel
        grp_log = QGroupBox("Log")
        grp_log.setFixedWidth(280)
        l_lay = QVBoxLayout(grp_log)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-size: 11px; font-family: Consolas;")
        btn_log_row = QHBoxLayout()
        btn_clear_log = QPushButton("🗑 Xóa")
        btn_clear_log.clicked.connect(self.txt_log.clear)
        btn_open_log = QPushButton("📄 Mở log.txt")
        btn_open_log.clicked.connect(self._open_log_file)
        btn_log_row.addWidget(btn_clear_log)
        btn_log_row.addWidget(btn_open_log)

        l_lay.addWidget(self.txt_log)
        l_lay.addLayout(btn_log_row)
        bottom.addWidget(grp_log)

        bottom.setSizes([820, 280])
        splitter.addWidget(bottom)
        splitter.setSizes([260, 440])

        layout.addWidget(splitter)
        return widget

    # ──────────────────── Tab Settings ────────────────────────
    def _build_tab_settings(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        grp = QGroupBox("Cài đặt")
        form = QFormLayout(grp)
        form.setSpacing(12)

        # Quốc gia
        self.cbo_country_settings = QComboBox()
        for code, info in REGIONS.items():
            self.cbo_country_settings.addItem(f"{info['flag']} {info['name']}", code)
        cur_idx_s = self.cbo_country_settings.findData(self.cfg.get("country", "VN"))
        if cur_idx_s >= 0:
            self.cbo_country_settings.setCurrentIndex(cur_idx_s)
        self.cbo_country_settings.currentIndexChanged.connect(
            lambda _i: self._on_country_changed(self.cbo_country_settings.currentData()))
        form.addRow("🌏 Quốc gia mục tiêu:", self.cbo_country_settings)

        lbl_version = QLabel(f"<b>v{self.version}</b>")
        lbl_version.setStyleSheet("color: #4f46e5; font-size: 13px;")
        form.addRow("📌 Phiên bản:", lbl_version)

        # Cookie
        self.txt_cookie = QTextEdit()
        self.txt_cookie.setPlaceholderText(
            "Mỗi dòng 1 cookie (1 tài khoản Shopee). Khi quét, cookie đang dùng bị hết hạn / captcha / "
            "bị chặn sẽ tự chuyển sang cookie ở dòng tiếp theo.")
        self.txt_cookie.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.txt_cookie.setFixedHeight(110)
        self.txt_cookie.setPlainText(self.cookies_by_country.get(self._active_country, ""))
        form.addRow("Cookie:", self.txt_cookie)
        self.lbl_cookie_count = QLabel()
        self.lbl_cookie_count.setStyleSheet("color: #666; font-size: 11px;")
        self.txt_cookie.textChanged.connect(self._update_cookie_count)
        self._update_cookie_count()
        form.addRow("", self.lbl_cookie_count)

        btn_cookie_file = QPushButton("📂 Load từ file cookie")
        btn_cookie_file.clicked.connect(self._load_cookie_file)
        form.addRow("", btn_cookie_file)

        # Sign API
        self.txt_sign_url = QLineEdit(self.cfg.get("sign_api_url", DEFAULT_SIGN_API_URL))
        form.addRow("Sign API URL:", self.txt_sign_url)

        key_row = QHBoxLayout()
        self.txt_api_key = QLineEdit(self.cfg.get("sign_api_key", ""))
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("API key của bạn (dùng để ký request timeline)")
        btn_show_key = QPushButton("👁")
        btn_show_key.setFixedWidth(36)
        btn_show_key.setCheckable(True)
        btn_show_key.toggled.connect(lambda on: self.txt_api_key.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        btn_check_key = QPushButton("Kiểm tra key")
        btn_check_key.clicked.connect(self._check_key)
        key_row.addWidget(self.txt_api_key)
        key_row.addWidget(btn_show_key)
        key_row.addWidget(btn_check_key)
        form.addRow("API Key:", key_row)

        # Delay
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(100, 10000)
        self.spin_delay.setSingleStep(100)
        self.spin_delay.setSuffix(" ms")
        self.spin_delay.setValue(self.cfg.get("delay_ms", 500))
        form.addRow("Delay giữa requests:", self.spin_delay)

        # Max videos
        self.spin_max = QSpinBox()
        self.spin_max.setRange(0, 100000)
        self.spin_max.setSingleStep(48)
        self.spin_max.setSpecialValueText("Không giới hạn")
        self.spin_max.setValue(self.cfg.get("max_videos_per_shop", 0))
        form.addRow("Giới hạn video/shop:", self.spin_max)

        # Export path
        path_row = QHBoxLayout()
        self.txt_export_path = QLineEdit(self.cfg.get("export_path", "results"))
        btn_browse_export = QPushButton("📂")
        btn_browse_export.setFixedWidth(36)
        btn_browse_export.clicked.connect(self._browse_export)
        path_row.addWidget(self.txt_export_path)
        path_row.addWidget(btn_browse_export)
        form.addRow("Thư mục export:", path_row)

        layout.addWidget(grp)

        # Google Sheet
        grp_gs = QGroupBox("📊 Google Sheet (service account)")
        gs_form = QFormLayout(grp_gs)
        gs_form.setSpacing(10)

        cred_row = QHBoxLayout()
        self.txt_gsheet_cred = QLineEdit(self.cfg.get("gsheet_credentials", ""))
        self.txt_gsheet_cred.setPlaceholderText(r"F:\...\service-account.json")
        self.txt_gsheet_cred.textChanged.connect(self._update_sa_email)
        btn_cred = QPushButton("📂")
        btn_cred.setFixedWidth(36)
        btn_cred.clicked.connect(self._browse_gsheet_cred)
        cred_row.addWidget(self.txt_gsheet_cred)
        cred_row.addWidget(btn_cred)
        gs_form.addRow("File JSON:", cred_row)

        email_row = QHBoxLayout()
        self.lbl_sa_email = QLabel()
        self.lbl_sa_email.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        btn_copy_email = QPushButton("📋 Copy email")
        btn_copy_email.clicked.connect(
            lambda: QApplication.clipboard().setText(gsheet.sa_email(self.txt_gsheet_cred.text().strip())))
        email_row.addWidget(self.lbl_sa_email, 1)
        email_row.addWidget(btn_copy_email)
        gs_form.addRow("Email chia sẻ:", email_row)
        self._update_sa_email()

        self.txt_gsheet_sheet = QLineEdit(self.cfg.get("gsheet_sheet", ""))
        self.txt_gsheet_sheet.setPlaceholderText("https://docs.google.com/spreadsheets/d/.../edit")
        gs_form.addRow("Link Google Sheet:", self.txt_gsheet_sheet)

        self.txt_gsheet_tab = QLineEdit(self.cfg.get("gsheet_tab", ""))
        self.txt_gsheet_tab.setPlaceholderText("Để trống = tab theo quốc gia đang chọn (VN, PH, ...)")
        gs_form.addRow("Tab ghi dữ liệu:", self.txt_gsheet_tab)

        gs_btns = QHBoxLayout()
        btn_test_gs = QPushButton("🔌 Kiểm tra kết nối")
        btn_test_gs.clicked.connect(self._test_gsheet)
        gs_btns.addWidget(btn_test_gs)
        gs_btns.addStretch()
        gs_form.addRow("", gs_btns)
        gs_help = QLabel(
            "Kết nối 1 lần:\n"
            "1. Mở Google Sheet → bấm Chia sẻ → thêm 'Email chia sẻ' ở trên với quyền Người chỉnh sửa.\n"
            "2. Project Google Cloud của file JSON phải bật Google Sheets API.\n"
            "3. Kiểm tra kết nối → Lưu cài đặt.\n"
            "Mỗi lần xuất: ghi tiếp vào tab trên, tự bỏ qua video đã có (so theo Video ID)."
        )
        gs_help.setStyleSheet("color: #666; font-size: 11px;")
        gs_form.addRow("", gs_help)
        layout.addWidget(grp_gs)

        btn_save = QPushButton("💾 Lưu cài đặt")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        return widget

    # ──────────────────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────────────────

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file danh sách shop", "",
            "Text files (*.txt);;All files (*.*)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            current = self.txt_shops.toPlainText().strip()
            self.txt_shops.setPlainText(
                (current + "\n" + content).strip()
            )
            self.cfg["last_import_path"] = path

    def _load_cookie_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file cookie", "",
            "Text files (*.txt);;JSON files (*.json);;All files (*.*)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            self.txt_cookie.setPlainText(content)

    def _browse_export(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục export")
        if path:
            self.txt_export_path.setText(path)

    def _update_hint(self, reg: dict):
        self.lbl_hint.setText(
            f"Nhập mỗi dòng 1 shop — khu vực {reg['name']}:\n"
            f"  • Profile URL:  https://{reg['video_domain']}/profile/12345678\n"
            f"  • Short link:   https://{reg['short_domain']}/xxxxx\n"
            f"  • Profile ID:   12345678\n"
            f"  • Username shop: tenshop\n"
            f"⚠️ Lưu ý: Cookie phải lấy từ trình duyệt đã đăng nhập tại https://{reg['domain']}!"
        )

    def _update_placeholder(self, reg: dict):
        self.txt_shops.setPlaceholderText(
            f"https://{reg['video_domain']}/profile/12345678\n"
            f"https://{reg['short_domain']}/0jww2l6y\n"
            "12345678\n"
            "tenshop_abc"
        )

    def _country_combos(self) -> list:
        names = ["cbo_country", "cbo_country_settings"]
        combos = [getattr(self, n) for n in names if hasattr(self, n)]
        if hasattr(self, "viral_tab") and getattr(self.viral_tab, "cbo_country", None) is not None:
            combos.append(self.viral_tab.cbo_country)
        return combos

    def _on_country_changed(self, code: str):
        """Đổi thị trường ở bất kỳ tab nào: đồng bộ mọi combo + tráo cookie theo quốc gia."""
        code = code or "VN"
        prev = self._active_country
        if code == prev:
            return
        # Lưu cookie đang gõ vào quốc gia cũ, nạp cookie của quốc gia mới
        if hasattr(self, "txt_cookie"):
            self.cookies_by_country[prev] = self.txt_cookie.toPlainText().strip()
        self._active_country = code
        self.cfg["country"] = code
        for cb in self._country_combos():
            i = cb.findData(code)
            if i >= 0 and cb.currentIndex() != i:
                cb.blockSignals(True)
                cb.setCurrentIndex(i)
                cb.blockSignals(False)
        if hasattr(self, "txt_cookie"):
            self.txt_cookie.blockSignals(True)
            self.txt_cookie.setPlainText(self.cookies_by_country.get(code, ""))
            self.txt_cookie.blockSignals(False)
            self._update_cookie_count()
        if hasattr(self, "viral_tab"):
            self.viral_tab.load_hashtags(code)
            self.viral_tab._load_country_cache(code)
        reg = REGIONS.get(code, REGIONS["VN"])
        self._update_hint(reg)
        self._update_placeholder(reg)
        self.status.showMessage(f"🌐 Đã chọn thị trường: {reg['name']} ({reg['domain']}) — cookie riêng của nước này", 4000)

    def _save_settings(self):
        self.cfg["country"]             = self._active_country
        # Lưu cookie đang gõ vào đúng quốc gia đang chọn
        self.cookies_by_country[self._active_country] = self.txt_cookie.toPlainText().strip()
        self.cfg["cookies_by_country"]  = self.cookies_by_country
        self.cfg["cookie"]              = self.cookies_by_country.get(self._active_country, "")
        self.cfg["delay_ms"]            = self.spin_delay.value()
        self.cfg["max_videos_per_shop"] = self.spin_max.value()
        self.cfg["export_path"]         = self.txt_export_path.text().strip()
        self.cfg["filter_duet_only"]    = self.chk_filter.isChecked()
        self.cfg["sign_api_url"]        = self.txt_sign_url.text().strip() or DEFAULT_SIGN_API_URL
        self.cfg["sign_api_key"]        = self.txt_api_key.text().strip()
        self.cfg["gsheet_credentials"]  = self.txt_gsheet_cred.text().strip()
        self.cfg["gsheet_sheet"]        = self.txt_gsheet_sheet.text().strip()
        self.cfg["gsheet_tab"]          = self.txt_gsheet_tab.text().strip()
        self.viral_tab.save_to_cfg()
        cfg_mgr.save(self.cfg)
        self.status.showMessage("✅ Đã lưu cài đặt.", 3000)

    def _update_cookie_count(self):
        n = len(parse_cookies(self.txt_cookie.toPlainText()))
        self.lbl_cookie_count.setText(
            f"🍪 {n} cookie" + (" — dùng lần lượt, cookie lỗi sẽ tự chuyển sang dòng tiếp theo" if n > 1 else ""))

    def _browse_gsheet_cred(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file JSON service account", "",
                                              "JSON files (*.json);;All files (*.*)")
        if path:
            self.txt_gsheet_cred.setText(path)

    def _update_sa_email(self, *_):
        email = gsheet.sa_email(self.txt_gsheet_cred.text().strip())
        self.lbl_sa_email.setText(email or "⚠️ Chưa có file JSON service account hợp lệ")

    def _test_gsheet(self):
        rt = self._runtime()
        if not rt["gsheet_credentials"] or not rt["gsheet_sheet"]:
            QMessageBox.warning(self, "Thiếu thông tin", "Chọn file JSON và dán link Google Sheet trước!")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = gsheet.ping(rt["gsheet_credentials"], rt["gsheet_sheet"])
        finally:
            QApplication.restoreOverrideCursor()
        if res.get("ok"):
            QMessageBox.information(self, "Kết nối thành công", f"Đã kết nối sheet: {res.get('name')}")
        else:
            QMessageBox.warning(self, "Kết nối thất bại", str(res.get("error") or res))

    def _open_phone(self):
        open_phone_page(self, self.result_table.visible_videos(), self._get_export_dir(),
                        title="Shopee Duet Checker — Scanner", prefix="scanner_list")

    def _export_gsheet(self):
        rt = self._runtime()
        msg = export_gsheet(self, self.result_table.visible_videos(),
                            rt["gsheet_credentials"], rt["gsheet_sheet"], rt["gsheet_tab"])
        if msg:
            self.log(msg)

    def _check_key(self):
        rt = self._runtime()
        if not rt["sign_api_key"]:
            QMessageBox.warning(self, "Thiếu API key", "Vui lòng nhập API key!")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ok, msg = ShopeeAPI(sign_api_key=rt["sign_api_key"],
                                sign_api_url=rt["sign_api_url"]).check_key()
        finally:
            QApplication.restoreOverrideCursor()
        if ok:
            QMessageBox.information(self, "API key hợp lệ", msg)
        else:
            QMessageBox.warning(self, "API key không hợp lệ", msg)

    def _on_filter_changed(self, checked: bool):
        self.result_table.filter_duet_only(checked)

    def _update_stats(self, total: int):
        allowed = len(self.result_table.get_duet_allowed())
        denied  = total - allowed
        self.lbl_stats.setText(
            f"Video: {total}  |  ✅ Duet: {allowed}  |  ❌ No duet: {denied}"
        )
        self.status.showMessage(
            f"Đang scan... {total} video tìm thấy, {allowed} cho phép duet."
        )

    # ──────────────────────────────────────────────────────────
    # Scan
    # ──────────────────────────────────────────────────────────

    def _parse_shop_list(self) -> list:
        """Parse text input thành list (profile_id, display_name)."""
        lines  = self.txt_shops.toPlainText().strip().splitlines()
        result = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result.append((line, ""))
        return result

    def _start_scan(self):
        rt = self._runtime()
        cookie = rt["cookie"]
        if not cookie:
            QMessageBox.warning(self, "Thiếu Cookie",
                                "Vui lòng nhập Cookie trong tab Cài đặt!")
            return

        shop_list = self._parse_shop_list()
        if not shop_list:
            QMessageBox.warning(self, "Danh sách trống",
                                "Vui lòng nhập ít nhất 1 shop/profile!")
            return

        # Clear kết quả cũ
        self.result_table.clear_results()
        self._results.clear()
        self.txt_log.clear()

        # UI state
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)

        self.log(f"🚀 Bắt đầu scan {len(shop_list)} shop...")
        self.log("─" * 40)

        # Tạo worker
        self.worker = ScannerWorker(
            shop_list   = shop_list,
            cookie      = cookie,
            delay_ms    = rt["delay_ms"],
            max_videos  = rt["max_videos"],
            filter_duet = False,  # luôn lấy hết, filter ở UI
            sign_api_key = rt["sign_api_key"],
            sign_api_url = rt["sign_api_url"],
            country      = rt.get("country", "VN"),
        )
        self.worker.progress.connect(self.log)
        self.worker.video_found.connect(self._on_video_found)
        self.worker.shop_done.connect(self._on_shop_done)
        self.worker.all_done.connect(self._on_all_done)
        self.worker.error.connect(lambda msg: self.log(f"❌ ERROR: {msg}"))
        self.worker.start()

    def _stop_scan(self):
        if self.worker:
            self.worker.stop()
        self.btn_stop.setEnabled(False)
        self.log("⏹ Đang dừng...")

    def _on_video_found(self, v: dict):
        self._results.append(v)
        self.windows_store.add_video(v)
        self.video_store.add_video(v, self._active_country)
        self.result_table.add_video(v)
        if self.chk_filter.isChecked():
            self.result_table.filter_duet_only(True)

    def _on_shop_done(self, profile_id: str, total: int, allow: int, deny: int):
        pass  # đã log trong worker

    def _on_all_done(self, total: int, allow: int):
        self.windows_store.save()
        self.video_store.save()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status.showMessage(
            f"✅ Hoàn thành! {total} video | {allow} cho phép duet."
        )
        self.log("─" * 40)

    def log(self, msg: str):
        self.txt_log.append(msg)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {msg}\n")
        except Exception:
            pass

    def _open_log_file(self):
        try:
            if not os.path.exists(LOG_FILE):
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("=== Shopee Duet Checker Log ===\n\n")
            os.startfile(LOG_FILE)
        except Exception as e:
            QMessageBox.information(self, "Lỗi mở file", f"Không thể mở file log: {e}")

    # ──────────────────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────────────────

    def _get_export_dir(self) -> str:
        return self.txt_export_path.text().strip() or \
               self.cfg.get("export_path", "results")

    def _export_csv(self):
        if not self._results:
            QMessageBox.information(self, "Không có dữ liệu", "Chưa có kết quả nào!")
            return
        path = export_csv(self._results, self._get_export_dir())
        self.status.showMessage(f"✅ Đã export CSV: {path}", 5000)
        self.log(f"💾 Exported CSV: {path}")

    def _export_json(self):
        if not self._results:
            QMessageBox.information(self, "Không có dữ liệu", "Chưa có kết quả nào!")
            return
        path = export_json(self._results, self._get_export_dir())
        self.status.showMessage(f"✅ Đã export JSON: {path}", 5000)
        self.log(f"💾 Exported JSON: {path}")

    def _copy_duet_urls(self):
        allowed = self.result_table.get_duet_allowed()
        if not allowed:
            QMessageBox.information(self, "Không có dữ liệu",
                                    "Không có video nào cho phép duet!")
            return
        urls = "\n".join(v["share_url"] for v in allowed)
        QApplication.clipboard().setText(urls)
        self.status.showMessage(
            f"📋 Đã copy {len(allowed)} URL duet vào clipboard.", 3000
        )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        self.viral_tab.shutdown()
        self.viral_tab.save_to_cfg()
        self.windows_store.close()
        self.video_store.close()
        self.cfg["window_width"]  = self.width()
        self.cfg["window_height"] = self.height()
        cfg_mgr.save(self.cfg)
        event.accept()
