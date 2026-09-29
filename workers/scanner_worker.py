"""
Scanner Worker — QThread xử lý scan shop + check duet ở background

Chế độ crawl (Viral Finder): quét nguồn (creator + hashtag), rồi tự lan sang
creator/shop liên quan và hashtag xuất hiện trong video, ưu tiên theo tổng view
của video chứa chúng, dừng khi hết ngân sách credit.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from api.shopee_api import ShopeeAPI


class ScannerWorker(QThread):
    # Signals
    progress    = pyqtSignal(str)        # log message
    video_found = pyqtSignal(dict)       # 1 video đã parse xong
    shop_done   = pyqtSignal(str, int, int, int)  # profile_id, total, allow, deny
    all_done    = pyqtSignal(int, int)   # total_videos, total_allow
    error       = pyqtSignal(str)        # thông báo lỗi

    def __init__(
        self,
        shop_list:     list,
        cookie:        str,
        delay_ms:      int  = 500,
        max_videos:    int  = 0,
        filter_duet:   bool = False,
        sign_api_key:  str  = "",
        sign_api_url:  str  = "",
        country:       str  = "VN",
        hashtags:      list | None = None,   # [(hashtag_id, "#name")]
        hashtag_videos: int = 24,
        crawl_creators: bool = False,
        crawl_hashtags: bool = False,
        credit_budget: int  = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.shop_list   = list(shop_list)   # list of (profile_id, display_name)
        self.cookie      = cookie
        self.delay_ms    = delay_ms
        self.max_videos  = max_videos
        self.filter_duet = filter_duet
        self.sign_api_key = sign_api_key
        self.sign_api_url = sign_api_url
        self.country     = (country or "VN").upper().strip()
        self.hashtags    = list(hashtags or [])
        self.hashtag_videos = hashtag_videos
        self.crawl_creators = crawl_creators
        self.crawl_hashtags = crawl_hashtags
        self.credit_budget  = credit_budget
        self._stop       = False

    def stop(self):
        self._stop = True

    def run(self):
        self.total_videos = 0
        self.total_allow  = 0
        self.api = None
        try:
            self._scan()
        except Exception as e:
            self.error.emit(str(e))
        used = self.api.request_count if self.api else 0
        if self.api and self.api.dead_cookies:
            dead = ", ".join(f"#{i + 1} ({why})" for i, why in sorted(self.api.dead_cookies.items()))
            self.progress.emit(f"🍪 Cookie lỗi trong lần quét này: {dead} — nên thay trong tab Cài đặt")
        self.progress.emit(
            f"\n🎉 Hoàn thành! Tổng: {self.total_videos} video | "
            f"Cho phép duet: {self.total_allow} | Đã dùng ≈ {used} credit"
        )
        self.all_done.emit(self.total_videos, self.total_allow)

    # ──────────────────────────────────────────────────────────
    def _budget_left(self) -> bool:
        return not self.credit_budget or self.api.request_count < self.credit_budget

    def _scan(self):
        api = self.api = ShopeeAPI(cookie=self.cookie, delay_ms=self.delay_ms,
                                   sign_api_key=self.sign_api_key, sign_api_url=self.sign_api_url,
                                   country=self.country)
        self.progress.emit(f"🌐 Khu vực hoạt động: {self.country} ({api.sv_host})")
        api.on_log = self.progress.emit
        if len(api.cookies) > 1:
            self.progress.emit(f"🍪 {len(api.cookies)} cookie — tự đổi khi cookie đang dùng bị lỗi")
        if not self.sign_api_key:
            self.progress.emit("⚠️ Chưa có API key ký request — Shopee có thể trả về lỗi 418.")

        self._seen_videos: set[str] = set()
        self._scanned_creators: set[str] = set()
        self._scanned_tags: set[str] = set()
        self._creator_score: dict[str, int] = {}
        self._tag_score: dict[str, int] = {}
        self._tag_names: dict[str, str] = {}

        seed_creators = list(self.shop_list)
        seed_tags = list(self.hashtags)
        n = 0

        while not self._stop:
            if not self._budget_left():
                self.progress.emit(f"🛑 Đã dùng hết ngân sách {self.credit_budget} credit.")
                break

            task = None
            if seed_creators:
                pid, label = seed_creators.pop(0)
                task = ("creator", pid, label or pid)
            elif seed_tags:
                tid, name = seed_tags.pop(0)
                task = ("tag", tid, name)
            else:
                task = self._next_discovered()
                if not task:
                    if self.crawl_creators or self.crawl_hashtags:
                        self.progress.emit("🕸 Hết nguồn liên quan để quét lan.")
                    break

            n += 1
            kind, key, label = task
            if kind == "creator":
                self._do_creator(n, key, label)
            else:
                self._do_tag(n, key, label)

        if self._stop:
            self.progress.emit("⏹ Đã dừng.")

    def _next_discovered(self):
        best = None
        if self.crawl_creators:
            pend = {k: s for k, s in self._creator_score.items() if k not in self._scanned_creators}
            if pend:
                k = max(pend, key=pend.get)
                best = (pend[k], ("creator", k, f"🕸 creator {k} (điểm {pend[k]:,})"))
        if self.crawl_hashtags:
            pend = {k: s for k, s in self._tag_score.items() if k not in self._scanned_tags}
            if pend:
                k = max(pend, key=pend.get)
                if best is None or pend[k] > best[0]:
                    best = (pend[k], ("tag", k, self._tag_names.get(k, k)))
        return best[1] if best else None

    # ──────────────────────────────────────────────────────────
    def _do_creator(self, n: int, profile_id: str, label: str):
        self.progress.emit(f"[{n}] 🔍 Creator: {label}")
        if not profile_id.isdigit():
            resolved = self.api.resolve_short_link(profile_id)
            if not resolved:
                self.progress.emit(
                    f"  ⚠️ Không tìm thấy shop '{profile_id}'. "
                    "Hãy nhập link profile, ID hoặc đúng username shop."
                )
                return
            profile_id = resolved
        if profile_id in self._scanned_creators:
            self.progress.emit("  ↪ Đã quét rồi, bỏ qua.")
            return
        self._scanned_creators.add(profile_id)

        def on_progress(count):
            if count % 48 == 0:
                self.progress.emit(f"  📹 Đã lấy {count} video...")

        videos = self.api.get_all_videos(
            profile_id  = profile_id,
            max_videos  = self.max_videos,
            on_progress = on_progress,
            stop_flag   = lambda: self._stop or not self._budget_left(),
        )
        if self.api.last_error:
            self.progress.emit(f"  ❌ {self.api.last_error}")
        allow, deny = self._emit(videos)
        self.shop_done.emit(profile_id, allow + deny, allow, deny)
        self.progress.emit(f"  ✅ {allow + deny} video | ✅ Duet: {allow} | ❌ No duet: {deny}")

    def _do_tag(self, n: int, tag_id: str, name: str):
        self._scanned_tags.add(tag_id)
        self.progress.emit(f"[{n}] #️⃣ Hashtag: {name}")
        videos = self.api.get_hashtag_videos(
            tag_id, name, max_videos=self.hashtag_videos,
            stop_flag=lambda: self._stop or not self._budget_left(),
        )
        if self.api.last_error:
            self.progress.emit(f"  ❌ {self.api.last_error}")
        allow, deny = self._emit(videos)
        self.progress.emit(f"  ✅ {allow + deny} video mới | ✅ Duet: {allow}")

    def _emit(self, videos: list) -> tuple[int, int]:
        """Phát video chưa thấy, cập nhật điểm lan. Trả về (allow, deny)."""
        allow = deny = 0
        new_creators = new_tags = 0
        for v in videos:
            weight = (v.get("play_count") or 0) + 1

            if self.crawl_creators:
                cands = [v.get("profile_id")] + [uid for uid, _ in v.get("related_ids") or []]
                for uid in cands:
                    if uid and uid not in self._scanned_creators:
                        new_creators += uid not in self._creator_score
                        self._creator_score[uid] = self._creator_score.get(uid, 0) + weight
            if self.crawl_hashtags:
                for tid, name in v.get("hashtags") or []:
                    if tid not in self._scanned_tags:
                        new_tags += tid not in self._tag_score
                        self._tag_score[tid] = self._tag_score.get(tid, 0) + weight
                        self._tag_names.setdefault(tid, name)

            key = v.get("video_id") or ""
            if key in self._seen_videos:
                continue
            self._seen_videos.add(key)
            if self.filter_duet and not v["allow_duet"]:
                continue
            self.video_found.emit(v)
            self.total_videos += 1
            if v["allow_duet"]:
                allow += 1
                self.total_allow += 1
            else:
                deny += 1
        if new_creators or new_tags:
            self.progress.emit(f"  🕸 Tìm thêm {new_creators} creator, {new_tags} hashtag")
        return allow, deny
