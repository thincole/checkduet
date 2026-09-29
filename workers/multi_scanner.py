"""
Multi Scanner Worker — quét Viral Finder song song bằng nhiều luồng, mỗi luồng 1 cookie.
Tăng tốc theo thời gian thực (KHÔNG giảm credit: vẫn đúng số request, mỗi request ≈ 1 credit).

Kiến trúc: 1 QThread điều phối + N luồng công nhân dùng chung hàng đợi/điểm số/dedup dưới 1 khóa.
Kết thúc khi hết ngân sách, hoặc mọi luồng rảnh và không còn nguồn để lan.
"""

import threading

from PyQt6.QtCore import QThread, pyqtSignal
from api.shopee_api import ShopeeAPI, parse_cookies


class MultiScanWorker(QThread):
    progress    = pyqtSignal(str)
    video_found = pyqtSignal(dict)
    all_done    = pyqtSignal(int, int)
    error       = pyqtSignal(str)

    def __init__(self, shop_list, cookie, delay_ms=500, max_videos=0,
                 sign_api_key="", sign_api_url="", country="VN",
                 hashtags=None, hashtag_videos=24, crawl_creators=False,
                 crawl_hashtags=False, credit_budget=0, num_threads=1, parent=None):
        super().__init__(parent)
        self.seed_creators = [(str(p), n) for p, n in shop_list]
        self.seed_tags = list(hashtags or [])
        self.cookies = parse_cookies(cookie) or [""]
        self.delay_ms = delay_ms
        self.max_videos = max_videos
        self.sign_api_key = sign_api_key
        self.sign_api_url = sign_api_url
        self.country = (country or "VN").upper().strip()
        self.hashtag_videos = hashtag_videos
        self.crawl_creators = crawl_creators
        self.crawl_hashtags = crawl_hashtags
        self.credit_budget = credit_budget
        self.num_threads = max(1, min(num_threads, len(self.cookies)))
        self._stop = False

        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.total_videos = 0
        self.total_allow = 0
        self.request_count = 0
        self._seen_videos: set[str] = set()
        self._scanned_creators: set[str] = set()
        self._scanned_tags: set[str] = set()
        self._creator_score: dict[str, int] = {}
        self._tag_score: dict[str, int] = {}
        self._tag_names: dict[str, str] = {}
        self._idle = 0
        self._finished_flag = False

    def stop(self):
        self._stop = True
        with self.cond:
            self.cond.notify_all()

    # ──────────────────────────────────────────────────────────
    def run(self):
        try:
            self.progress.emit(f"🌐 Khu vực: {self.country} | 🧵 {self.num_threads} luồng / "
                               f"{len(self.cookies)} cookie")
            if not self.sign_api_key:
                self.progress.emit("⚠️ Chưa có API key ký request — Shopee có thể trả về lỗi 418.")
            threads = []
            for i in range(self.num_threads):
                t = threading.Thread(target=self._worker, args=(i,), daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
        except Exception as e:
            self.error.emit(str(e))
        if self._stop:
            self.progress.emit("⏹ Đã dừng.")
        self.progress.emit(
            f"\n🎉 Hoàn thành! Tổng: {self.total_videos} video | "
            f"Cho phép duet: {self.total_allow} | Đã dùng ≈ {self.request_count} credit")
        self.all_done.emit(self.total_videos, self.total_allow)

    def _budget_left(self) -> bool:
        return not self.credit_budget or self.request_count < self.credit_budget

    def _next_task(self):
        """Lấy việc kế tiếp (đang giữ lock). Trả về task hoặc None nếu tạm hết."""
        if self.seed_creators:
            pid, label = self.seed_creators.pop(0)
            return ("creator", pid, label or pid)
        if self.seed_tags:
            tid, name = self.seed_tags.pop(0)
            return ("tag", tid, name)
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
        if best:
            # đánh dấu đã nhận ngay để luồng khác không lấy trùng
            kind, key, _ = best[1]
            (self._scanned_creators if kind == "creator" else self._scanned_tags).add(key)
            return best[1]
        return None

    def _worker(self, idx: int):
        api = ShopeeAPI(cookie="\n".join(self.cookies), delay_ms=self.delay_ms,
                        sign_api_key=self.sign_api_key, sign_api_url=self.sign_api_url,
                        country=self.country)
        if api.cookies:
            api._use_cookie(idx % len(api.cookies))   # mỗi luồng bắt đầu bằng 1 cookie khác nhau
        api.on_log = self.progress.emit

        while True:
            with self.cond:
                while True:
                    if self._stop or not self._budget_left() or self._finished_flag:
                        return
                    task = self._next_task()
                    if task is not None:
                        break
                    # Không có việc: chờ luồng khác lan thêm, hoặc kết thúc khi mọi luồng rảnh
                    self._idle += 1
                    if self._idle >= self.num_threads:
                        self._finished_flag = True
                        self.cond.notify_all()
                        return
                    self.cond.wait(timeout=2.0)
                    self._idle -= 1
                    if self._finished_flag or self._stop:
                        return

            # Quét ngoài lock (phần chậm: mạng)
            kind, key, label = task
            before = api.request_count
            if kind == "creator":
                self._do_creator(api, key, label)
            else:
                self._do_tag(api, key, label)
            with self.cond:
                self.request_count += api.request_count - before
                self.cond.notify_all()   # có thể vừa lan thêm nguồn → đánh thức luồng rảnh

    # ──────────────────────────────────────────────────────────
    def _do_creator(self, api, profile_id, label):
        self.progress.emit(f"🔍 Creator: {label}")
        if not profile_id.isdigit():
            resolved = api.resolve_short_link(profile_id)
            if not resolved:
                self.progress.emit(f"  ⚠️ Không tìm thấy shop '{profile_id}'.")
                return
            with self.lock:
                if resolved in self._scanned_creators:
                    return
                self._scanned_creators.add(resolved)
            profile_id = resolved
        else:
            with self.lock:
                self._scanned_creators.add(profile_id)

        videos = api.get_all_videos(profile_id, max_videos=self.max_videos,
                                    stop_flag=lambda: self._stop or not self._budget_left())
        if api.last_error:
            self.progress.emit(f"  ❌ {api.last_error}")
        allow, deny = self._emit(videos)
        self.progress.emit(f"  ✅ {label}: {allow + deny} video | ✅ Duet: {allow}")

    def _do_tag(self, api, tag_id, name):
        self.progress.emit(f"#️⃣ Hashtag: {name}")
        videos = api.get_hashtag_videos(tag_id, name, max_videos=self.hashtag_videos,
                                        stop_flag=lambda: self._stop or not self._budget_left())
        if api.last_error:
            self.progress.emit(f"  ❌ {api.last_error}")
        allow, deny = self._emit(videos)
        self.progress.emit(f"  ✅ {name}: {allow + deny} video mới | ✅ Duet: {allow}")

    def _emit(self, videos):
        """Phát video chưa thấy, cập nhật điểm lan (an toàn luồng). Trả về (allow, deny)."""
        allow = deny = new_c = new_t = 0
        with self.lock:
            for v in videos:
                weight = (v.get("play_count") or 0) + 1
                if self.crawl_creators:
                    for uid in [v.get("profile_id")] + [u for u, _ in v.get("related_ids") or []]:
                        if uid and uid not in self._scanned_creators:
                            new_c += uid not in self._creator_score
                            self._creator_score[uid] = self._creator_score.get(uid, 0) + weight
                if self.crawl_hashtags:
                    for tid, name in v.get("hashtags") or []:
                        if tid not in self._scanned_tags:
                            new_t += tid not in self._tag_score
                            self._tag_score[tid] = self._tag_score.get(tid, 0) + weight
                            self._tag_names.setdefault(tid, name)
                vid = v.get("video_id") or ""
                if vid in self._seen_videos:
                    continue
                self._seen_videos.add(vid)
                emit = v
                is_allow = bool(v.get("allow_duet"))
                self.total_videos += 1
                if is_allow:
                    allow += 1
                    self.total_allow += 1
                else:
                    deny += 1
                # phát tín hiệu ngoài vùng gom điểm để UI nhận dần
                self.video_found.emit(emit)
        if new_c or new_t:
            self.progress.emit(f"  🕸 Tìm thêm {new_c} creator, {new_t} hashtag")
        return allow, deny
