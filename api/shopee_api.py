"""
Shopee API Wrapper
Bao gồm: sign request, search_shop, get_all_videos, resolve_short_link
"""

import json
import os
import re
import shutil
import subprocess
import time
import uuid
import requests
from typing import Callable, Optional
from urllib.parse import quote, unquote

from .headers import build_headers, timeline_headers, web_headers, get_region, REGIONS, APP_UA

DEFAULT_SIGN_API_KEY = ""   # Nhập API key trong tab Cài đặt (lưu ở settings.json, không đưa lên Git)
DEFAULT_SIGN_API_URL = "https://credit.toolshopee.vn/api/sign"
PHONE_SIGN_URL       = "http://127.0.0.1:8080"
DEBUG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug")


def parse_cookies(text: str) -> list[str]:
    """Mỗi dòng 1 cookie (1 tài khoản); bỏ dòng trống và dòng bắt đầu bằng #."""
    return [c.strip() for c in (text or "").splitlines() if c.strip() and not c.strip().startswith("#")]


class ShopeeAPI:
    def __init__(self, cookie: str = "", delay_ms: int = 500,
                 sign_api_key: str = "", sign_api_url: str = DEFAULT_SIGN_API_URL,
                 country: str = "VN"):
        self.country      = (country or "VN").upper().strip()
        self.region       = get_region(self.country)
        self.sv_host      = f"https://{self.region['video_domain']}"
        self.base_host    = f"https://{self.region['domain']}"
        self.delay_sec    = delay_ms / 1000.0
        self.sign_api_key = (sign_api_key or DEFAULT_SIGN_API_KEY).strip()
        self.sign_api_url = (sign_api_url or DEFAULT_SIGN_API_URL).strip()
        self.last_error   = ""
        self.request_count = 0   # số request đã ký ≈ số credit đã dùng
        self._debug_saved = False
        self.on_log: Optional[Callable[[str], None]] = None
        self.session      = requests.Session()
        self.set_cookie(cookie)

    def set_cookie(self, cookie: str):
        """Nhận 1 hoặc nhiều cookie (mỗi dòng 1 tài khoản). Dùng dòng đầu, chết thì xoay sang dòng sau."""
        self.cookies = parse_cookies(cookie)
        self.dead_cookies: dict[int, str] = {}   # vị trí (0-based) → lý do
        self.cookie_idx = 0
        self._use_cookie(0)

    def _use_cookie(self, idx: int):
        self.cookie_idx = idx
        self.cookie = self.cookies[idx] if self.cookies else ""
        self.session.headers.update(build_headers(self.cookie, country=self.country))

    def _rotate_cookie(self, reason: str) -> bool:
        """Đánh dấu cookie hiện tại chết, chuyển sang cookie còn sống kế tiếp. False nếu hết cookie."""
        n = len(self.cookies)
        cur = self.cookie_idx
        self.dead_cookies[cur] = reason
        for step in range(1, n):
            j = (cur + step) % n
            if j not in self.dead_cookies:
                self._log(f"  🍪 Cookie #{cur + 1} lỗi ({reason}) → chuyển sang cookie #{j + 1}/{n}")
                self._use_cookie(j)
                return True
        self._log(f"  🍪 Cookie #{cur + 1} lỗi ({reason}) — không còn cookie nào dùng được")
        return False

    def _log(self, msg: str):
        if self.on_log:
            self.on_log(msg)

    def set_country(self, country: str):
        self.country   = (country or "VN").upper().strip()
        self.region    = get_region(self.country)
        self.sv_host   = f"https://{self.region['video_domain']}"
        self.base_host = f"https://{self.region['domain']}"
        self.session.headers.update(build_headers(self.cookie, country=self.country))

    # ------------------------------------------------------------------
    # Sign API & Phone Sign (SPSign 127.0.0.1:8080)
    # ------------------------------------------------------------------
    def is_phone_sign(self) -> bool:
        """Kiểm tra có đang cấu hình dùng Phone Sign (SPSign trên điện thoại qua ADB) hay không."""
        u = (self.sign_api_url or "").lower()
        return "127.0.0.1" in u or "localhost" in u or ":8080" in u

    def _phone_base_url(self) -> str:
        u = (self.sign_api_url or PHONE_SIGN_URL).strip().rstrip("/")
        if not self.is_phone_sign():
            return PHONE_SIGN_URL
        for suffix in ("/api/sign", "/api/send", "/api/debug_info", "/api/get_app_cookie"):
            if u.endswith(suffix):
                u = u[:-len(suffix)]
        return u or PHONE_SIGN_URL

    @staticmethod
    def find_adb() -> str:
        """Tìm đường dẫn adb.exe trên máy."""
        w = shutil.which("adb")
        if w:
            return w
        candidates = [
            r"E:\0 - Post SP phone\adb.exe",
            r"C:\platform-tools\adb.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return "adb"

    def connect_adb_spsign(self) -> tuple[bool, str]:
        """Tự động forward cổng 8080 qua ADB, mở app Shopee nếu cần và kiểm tra SPSign."""
        base = self._phone_base_url()
        try:
            r = requests.post(f"{base}/api/debug_info", json={}, timeout=2)
            d = r.json()
            if r.status_code == 200 and d.get("code") == 0 and d.get("sdk_loaded"):
                return True, f"Đã kết nối SPSign ({d.get('brand', '')} {d.get('model', '')} - Android ID: {d.get('android_id', '')})"
        except Exception:
            pass

        adb = self.find_adb()
        kw = {" capture_output": True, "text": True, "timeout": 8}
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            dev_out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=6, creationflags=creationflags).stdout
            serials = [
                line.split()[0] for line in dev_out.splitlines()[1:]
                if line.strip() and "\tdevice" in line
            ]
            if not serials:
                return False, "Không tìm thấy điện thoại Android nào đang cắm cáp và bật USB Debugging."
            serial = serials[0]
            subprocess.run([adb, "-s", serial, "forward", "tcp:8080", "tcp:8080"],
                           capture_output=True, text=True, timeout=6, creationflags=creationflags)
        except Exception as e:
            return False, f"Lỗi chạy ADB: {e}"

        try:
            r = requests.post(f"{base}/api/debug_info", json={}, timeout=2)
            d = r.json()
            if r.status_code == 200 and d.get("code") == 0:
                return True, f"Đã kết nối SPSign ({d.get('brand', '')} {d.get('model', '')} - Android ID: {d.get('android_id', '')})"
        except Exception:
            pass

        # Mở app Shopee trên điện thoại để khởi chạy XposedSignServer
        pkg_map = {
            "VN": "com.shopee.vn", "PH": "com.shopee.ph", "ID": "com.shopee.id",
            "TH": "com.shopee.th", "MY": "com.shopee.my", "SG": "com.shopee.sg",
        }
        pkg = pkg_map.get(self.country, "com.shopee.vn")
        try:
            subprocess.run([adb, "-s", serial, "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"],
                           capture_output=True, text=True, timeout=6, creationflags=creationflags)
        except Exception:
            pass

        for _ in range(6):
            time.sleep(1)
            try:
                r = requests.post(f"{base}/api/debug_info", json={}, timeout=2)
                d = r.json()
                if r.status_code == 200 and d.get("code") == 0:
                    return True, f"Đã mở Shopee & kết nối SPSign ({d.get('brand', '')} {d.get('model', '')} - Android ID: {d.get('android_id', '')})"
            except Exception:
                continue
        return False, "Không kết nối được SPSign cổng 8080 trên điện thoại. Hãy kiểm tra LSPosed đã bật module SPSign cho Shopee chưa."

    def get_cookie_from_phone(self) -> tuple[bool, str]:
        """Lấy cookie sạch đang đăng nhập trực tiếp từ app Shopee trên điện thoại qua SPSign."""
        ok, msg = self.connect_adb_spsign()
        if not ok:
            return False, msg
        base = self._phone_base_url()
        try:
            r = requests.post(f"{base}/api/get_app_cookie", json={}, timeout=5)
            d = r.json()
        except Exception as e:
            return False, f"Lỗi đọc cookie từ SPSign: {e}"
        ck = (d.get("clean_cookie") or d.get("cookie") or "").strip()
        if not ck or not d.get("logged_in", True):
            return False, d.get("message") or "App Shopee trên điện thoại chưa đăng nhập tài khoản!"
        return True, ck

    def _get_phone_signature(self, url: str, body: str = "", keep_sz_token: bool = False) -> dict:
        """Ký request qua SPSign trên điện thoại (http://127.0.0.1:8080) hoàn toàn miễn phí."""
        base = self._phone_base_url()
        sign_url = f"{base}/?url={quote(url, safe='')}&body={quote(body or '', safe='')}"
        for attempt in range(2):
            try:
                resp = requests.post(sign_url, timeout=10)
                data = resp.json()
                if resp.status_code == 200 and data.get("code") in (0, None):
                    sig = data.get("data") or {}
                    if isinstance(sig, dict):
                        if not keep_sz_token:
                            # Loại bỏ af-ac-enc-sz-token bản cũ để tương thích với luồng appver=29531 không bị 418
                            sig.pop("af-ac-enc-sz-token", None)
                        return {str(k): str(v) for k, v in sig.items()}
                self.last_error = f"SPSign lỗi: {data.get('message') or data}"
            except Exception as e:
                if attempt == 0:
                    ok, _ = self.connect_adb_spsign()
                    if ok:
                        continue
                self.last_error = f"SPSign lỗi kết nối ({base}): {e}"
        return {}

    def get_signature(self, url: str, body: str = "", keep_sz_token: bool = False) -> dict:
        """Lấy signature headers từ Phone Sign (SPSign) hoặc Sign API. Trả về {} nếu lỗi."""
        if self.is_phone_sign():
            return self._get_phone_signature(url, body, keep_sz_token=keep_sz_token)
        if not self.sign_api_key:
            # Nếu không có API key nhưng có điện thoại cắm SPSign thì tự động dùng SPSign
            sig = self._get_phone_signature(url, body, keep_sz_token=keep_sz_token)
            if sig:
                return sig
            return {}
        try:
            resp = requests.post(
                self.sign_api_url,
                json={"url": url, "body": body},
                headers={"Content-Type": "application/json", "X-API-Key": self.sign_api_key},
                timeout=20,
            )
            data = resp.json()
        except Exception as e:
            self.last_error = f"Sign API lỗi kết nối: {e}"
            return {}
        if resp.status_code != 200 or data.get("code") not in (0, None):
            self.last_error = f"Sign API: HTTP {resp.status_code} — {data.get('msg') or data.get('message') or data}"
            return {}
        sig = data.get("data")
        if isinstance(sig, dict) and isinstance(sig.get("headers"), dict):
            sig = sig["headers"]
        return sig if isinstance(sig, dict) else {}

    def check_key(self) -> tuple[bool, str]:
        """Kiểm tra kết nối SPSign điện thoại hoặc kiểm tra API key qua /api/me."""
        if self.is_phone_sign():
            return self.connect_adb_spsign()
        me_url = self.sign_api_url.rsplit("/", 1)[0] + "/me"
        try:
            resp = requests.get(me_url, headers={"X-API-Key": self.sign_api_key}, timeout=20)
            data = resp.json()
        except Exception as e:
            return False, f"Lỗi kết nối: {e}"
        if resp.status_code == 200 and data.get("code") in (0, None):
            return True, json.dumps(data.get("data", data), ensure_ascii=False)
        return False, data.get("msg") or f"HTTP {resp.status_code}"

    # ------------------------------------------------------------------
    # Resolve short link / profile / username → profile_id
    # ------------------------------------------------------------------
    def resolve_short_link(self, url: str) -> str:
        """
        Chuyển link rút gọn, profile URL hoặc username thành profile_id.
        Hỗ trợ:
          - Số ID thuần: 1677860631
          - Link rút gọn: https://vn.shp.ee/r3kjewd?smtt=0.0.9 (redirect sang /me/1677860631)
          - Video Profile: https://sv.shopee.vn/me/1677860631 hoặc /profile/957965727
          - Web URL: https://shopee.vn/anhhng600
          - Username: anhhng600, jr8lj6r23c
        """
        raw = url.strip()
        if not raw:
            return ""

        # 1. Đã là ID số thuần
        if re.match(r"^\d+$", raw):
            return raw

        # 2. Tìm ID trực tiếp trong chuỗi (/me/ID, /profile/ID, /creator/ID, /user/ID)
        m = re.search(r"/(?:profile|me|creator|user)/(\d+)", raw)
        if m:
            return m.group(1)

        # 3. Tham số ID của chính profile (không dùng shareUserId: đó là người chia sẻ)
        m_param = re.search(r"[?&](?:request_user_id|userid|user_id)=(\d+)", raw, re.IGNORECASE)
        if m_param:
            return m_param.group(1)

        # 4. Link rút gọn: 301 → shopee.vn/universal-link?redir=<URL mã hóa chứa /me/ID hoặc /profile/ID>.
        # Không đọc HTML: trang chủ luôn chứa một userid cố định, gây nhận nhầm.
        if raw.startswith(("http://", "https://")):
            target = raw
            try:
                for _ in range(5):
                    resp = requests.get(target, allow_redirects=False, timeout=12,
                                        headers={"User-Agent": APP_UA})
                    loc = resp.headers.get("Location") or ""
                    if not loc:
                        break
                    decoded = unquote(unquote(loc))
                    m2 = re.search(r"/(?:profile|me|creator|user)/(\d+)", decoded)
                    if m2:
                        return m2.group(1)
                    target = loc
            except Exception:
                pass

            # 5. Link trang shop dạng https://shopee.vn/<username>
            m3 = re.match(r"https?://(?:www\.)?shopee\.[a-z.]+/([A-Za-z0-9._]+)/?(?:\?.*)?$", raw)
            if m3 and m3.group(1) not in ("universal-link", "search", "product", "mall"):
                return self.get_userid_by_username(m3.group(1))
            return ""

        # 6. Username shop thuần
        if re.fullmatch(r"[A-Za-z0-9._]{3,40}", raw):
            return self.get_userid_by_username(raw)
        return ""

    def get_userid_by_username(self, username: str) -> str:
        """GET {base_host}/api/v4/shop/get_shop_base?username=... → data.userid (= ID profile video)."""
        url = (f"{self.base_host}/api/v4/shop/get_shop_base?entry_point=ShopByPDP"
               f"&need_cancel_rate=true&request_source=shop_home_page"
               f"&username={quote(username)}&version=1")
        self.last_error = ""
        try:
            resp = requests.get(url, headers=web_headers(self.cookie, country=self.country), timeout=15)
            data = resp.json()
        except Exception:
            return ""
        userid = str((data.get("data") or {}).get("userid") or "")
        if not userid and data.get("error") == 90309999:
            # Shopee trả về lỗi anti-bot (không phải "shop không tồn tại")
            self.last_error = (f"Shopee đang chặn tra cứu username (HTTP {resp.status_code}, anti-bot). "
                               "Hãy nhập ID số hoặc link profile (…/profile/<ID>) thay vì username.")
        return userid

    # ------------------------------------------------------------------
    # Tìm kiếm shop/creator theo keyword
    # ------------------------------------------------------------------
    def search_shop(self, keyword: str) -> list:
        """
        GET shopee.vn/api/v4/search/search_hint?search_type=3&keyword=...&version=2&scene=3
        Trả về list dict: {profile_id, username, display_name, follower}
        """
        url = (f"{self.base_host}/api/v4/search/search_hint?search_type=3"
               f"&keyword={quote(keyword)}&version=2&scene=3")
        try:
            resp = requests.get(url, headers=web_headers(self.cookie, country=self.country), timeout=15)
            data = resp.json()
        except Exception:
            return []

        results, seen = [], set()
        entries = list(data.get("keywords") or [])
        if isinstance(data.get("shop_hint"), dict):
            entries.append({"shop_info": data["shop_hint"]})
        for item in entries:
            info = item.get("creator_info") or item.get("shop_info")
            if not isinstance(info, dict):
                continue
            pid = str(info.get("userid") or info.get("user_id") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            results.append({
                "profile_id":   pid,
                "username":     info.get("username", ""),
                "display_name": info.get("nickname") or info.get("shop_name") or info.get("name") or "",
                "follower":     info.get("follower_count") or 0,
            })
        return results

    # ------------------------------------------------------------------
    # Đổi tên hashtag → hashtag_id theo quốc gia (không cần ký, không tốn credit)
    # ------------------------------------------------------------------
    def hashtag_id_by_name(self, name: str) -> tuple[str, str, int] | None:
        """
        GET {sv_host}/api/v2/hashtag/detail?hashtag_name=%23<tên>
        Trả về (tên chuẩn, hashtag_id, post_count) hoặc None.
        """
        tag = name.lstrip("#").strip()
        if not tag:
            return None
        url = f"{self.sv_host}/api/v2/hashtag/detail?hashtag_name={quote('#' + tag)}"
        try:
            data = requests.get(url, headers=web_headers(self.cookie, country=self.country), timeout=12).json()
        except Exception:
            return None
        h = (data.get("data") or {}).get("hashtag") or {}
        hid = str(h.get("hashtag_id") or "")
        if data.get("code") != 0 or not hid or int(h.get("post_count") or 0) <= 0:
            return None
        return h.get("content") or tag, hid, int(h.get("post_count") or 0)

    def top_hashtags(self, names: list, top_n: int = 10) -> list:
        """Resolve nhiều tên → (tên, id), bỏ trùng theo id, xếp theo post_count giảm dần, lấy top_n."""
        out, seen = [], set()
        for name in names:
            r = self.hashtag_id_by_name(name)
            if not r or r[1] in seen:
                continue
            seen.add(r[1])
            out.append(r)
        out.sort(key=lambda x: -x[2])
        return [(content, hid) for content, hid, _ in out[:top_n]]

    # ------------------------------------------------------------------
    # Lấy toàn bộ video của 1 profile (có phân trang)
    # ------------------------------------------------------------------
    def get_all_videos(
        self,
        profile_id: str,
        max_videos: int = 0,
        on_progress: Optional[Callable[[int], None]] = None,
        stop_flag: Optional[Callable[[], bool]] = None,
    ) -> list:
        """
        GET {sv_host}/api/v2/timeline/me?limit=48&page_context=...&request_user_id=...
        """
        def make_url(page_context: str) -> str:
            return (f"{self.sv_host}/api/v2/timeline/me?limit=48"
                    f"&page_context={quote(page_context)}"
                    f"&request_user_id={profile_id}"
                    f"&need_total_count=0&need_product_v2=true")
        return self._paged_feed(make_url, profile_id, max_videos, on_progress, stop_flag,
                                debug_name=f"timeline_{profile_id}")

    def get_hashtag_videos(
        self,
        hashtag_id: str,
        hashtag_name: str,
        max_videos: int = 12,
        stop_flag: Optional[Callable[[], bool]] = None,
    ) -> list:
        """
        GET {sv_host}/api/v2/hashtag/post/list?hashtag_id=...&hashtag_name=%23...&limit=12&page_context=...
        Video mới nhất có gắn hashtag, cấu trúc item giống timeline.
        """
        name = hashtag_name if hashtag_name.startswith("#") else f"#{hashtag_name}"

        def make_url(page_context: str) -> str:
            ctx = f"&page_context={quote(page_context)}" if page_context else ""
            return (f"{self.sv_host}/api/v2/hashtag/post/list?hashtag_id={hashtag_id}"
                    f"&hashtag_name={quote(name)}&limit=12{ctx}&need_product_v2=true")
        return self._paged_feed(make_url, None, max_videos, None, stop_flag,
                                debug_name=f"hashtag_{hashtag_id}")

    def _paged_feed(self, make_url, profile_id, max_videos, on_progress, stop_flag, debug_name) -> list:
        """GET có ký, phân trang theo data.page.page_context. Mỗi trang ≈ 1 credit."""
        self.last_error = ""
        page_context = ""
        all_videos   = []

        while True:
            if stop_flag and stop_flag():
                break

            url = make_url(page_context)
            data = self._signed_get(url, debug_name)
            if data is None:
                break

            raw_data = data.get("data") or {}
            videos = raw_data.get("list") or []

            for v in videos:
                all_videos.append(self._parse_video(v, profile_id))
                if on_progress:
                    on_progress(len(all_videos))
                if max_videos > 0 and len(all_videos) >= max_videos:
                    return all_videos

            page = raw_data.get("page") or {}
            page_context = page.get("page_context") or ""
            has_more     = page.get("has_more", False)
            if not has_more or not page_context or not videos:
                break

            time.sleep(self.delay_sec)

        return all_videos

    def _signed_get(self, url: str, debug_name: str) -> dict | None:
        """
        Gửi GET đã ký tới sv host. Trả về JSON, hoặc None và đặt last_error.
        Nếu lỗi do cookie (hết hạn / captcha / bị chặn) thì xoay sang cookie khác và gửi lại.
        """
        while True:
            data, cookie_problem = self._signed_get_once(url, debug_name)
            if data is not None:
                self.last_error = ""   # lỗi của cookie trước đã được xử lý bằng cookie mới
                return data
            if not cookie_problem:
                return None
            if not self._rotate_cookie(cookie_problem):
                self.last_error = (f"Tất cả {len(self.cookies)} cookie đều lỗi "
                                   f"(lần cuối: {self.last_error}). Vui lòng thay cookie mới.")
                return None

    def _signed_get_once(self, url: str, debug_name: str) -> tuple[dict | None, str]:
        """1 lần gửi. Trả về (data, "") khi thành công, (None, lý do) khi lỗi do cookie, (None, "") lỗi khác."""
        is_timeline = "/timeline/me" in url
        if is_timeline:
            # Endpoint /api/v2/timeline/me yêu cầu appver >= 29910 (appver <= 29900 bị trả code=400002)
            appver = "36448" if (self.is_phone_sign() or not self.sign_api_key) else "33731"
            keep_sz_token = True
        else:
            # Endpoint /hashtag/post/list dùng appver=29531 để vượt qua kiểm tra Captcha Video (418)
            appver = "29531"
            keep_sz_token = False

        cookie = re.sub(r"shopee_app_version=\d+", f"shopee_app_version={appver}", self.cookie or "")
        cookie = re.sub(r"version%3D\d+", f"version%3D{appver}", cookie)
        cookie = re.sub(r"appver%3D\d+", f"appver%3D{appver}", cookie)
        if "shopee_app_version=" not in cookie:
            cookie = (cookie + f"; shopee_app_version={appver}").strip("; ")

        headers = timeline_headers(cookie, country=self.country, appver=appver)
        headers["client-request-id"] = str(uuid.uuid4())
        headers.update(self.get_signature(url, keep_sz_token=keep_sz_token))
        self.request_count += 1
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            text = resp.text
            data = resp.json()
        except Exception as e:
            self.last_error = f"Lỗi request: {e}"
            return None, ""

        self._save_debug(debug_name, data)

        if data.get("is_login") is False or data.get("2") is False:
            self.last_error = "Cookie chưa đăng nhập hoặc đã hết hạn. Vui lòng thay cookie mới."
            return None, "hết hạn"

        text_low = text.lower()[:2000]
        is_captcha = (
            "captcha" in text_low
            or "mfreyj" in text_low
            or data.get("challenge_type") == 1
            or data.get("4") == 1
            or isinstance(data.get("6"), dict)
        )
        if is_captcha:
            if self.is_phone_sign() or not self.sign_api_key:
                self.last_error = (
                    "Tài khoản Shopee đang bị Captcha ở mục Live & Video! "
                    "Hãy mở tab 'Live & Video' trên app Shopee điện thoại, kéo giải hình Captcha "
                    "rồi bấm '📲 Lấy Cookie từ Điện thoại (SPSign)' lại."
                )
            else:
                self.last_error = (
                    "Cookie bị Captcha ở mục Shopee Video! Hãy mở tab 'Live & Video' trên app Shopee "
                    "của tài khoản này, kéo giải Captcha rồi lấy lại cookie mới."
                )
            return None, "captcha"

        err_code = data.get("error") or data.get("3")
        if resp.status_code != 200 or (not data.get("data") and err_code):
            has_signer = bool(self.sign_api_key or self.is_phone_sign())
            self.last_error = (
                f"HTTP {resp.status_code}, error={err_code} — "
                + ("chưa có API key ký request (hoặc chưa kết nối SPSign)" if not has_signer
                   else "cookie hết hạn hoặc bị chặn")
            )
            # Không có key thì lỗi không phải do cookie → đổi cookie cũng vô ích
            return None, ("bị chặn" if has_signer and self.cookie else "")
        if data.get("code") not in (0, None):
            self.last_error = f"Shopee trả lỗi code={data.get('code')} {data.get('msg') or ''}".strip()
            return None, ""
        return data, ""

    def _save_debug(self, name: str, data: dict):
        """Lưu response thô đầu tiên để đối chiếu cấu trúc JSON thật."""
        if self._debug_saved:
            return
        self._debug_saved = True
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            with open(os.path.join(DEBUG_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Parse 1 video object từ API response
    # ------------------------------------------------------------------
    @staticmethod
    def _all_products(content: dict) -> list:
        """Mọi sản phẩm gắn trong video: [[shop_id, item_id, tên], ...] (không trùng item_id)."""
        products = content.get("products") or {}
        pv2 = content.get("product_v2") or {}
        # enhanced_item_list chỉ có chi tiết SP chính; items / item_list liệt kê đủ mọi SP gắn (không tên)
        cands = (list(products.get("enhanced_item_list") or []) + list(products.get("items") or [])
                 + list(products.get("item_list") or []))
        cands += [products.get("anchor_product") or {},
                  {"shop_id": pv2.get("shop_id"), "item_id": pv2.get("item_id"), "name": pv2.get("item_name")}]
        out, seen = [], set()
        for it in cands:
            shop_id, item_id = it.get("shop_id"), it.get("item_id")
            if not shop_id or not item_id or str(item_id) in seen:
                continue
            seen.add(str(item_id))
            out.append([str(shop_id), str(item_id), it.get("name") or ""])
        return out

    def _main_product(self, content: dict) -> dict:
        """
        Sản phẩm chính gắn trong video: ưu tiên anchor_product (sản phẩm ghim),
        lấy chi tiết từ enhanced_item_list, dự phòng product_v2.
        Giá Shopee lưu theo đơn vị 1/100000 đồng.
        """
        products = content.get("products") or {}
        anchor   = products.get("anchor_product") or {}
        items    = products.get("enhanced_item_list") or []
        pv2      = content.get("product_v2") or {}

        item = next((it for it in items if anchor.get("item_id") and it.get("item_id") == anchor.get("item_id")),
                    items[0] if items else None)
        if item:
            shop_id, item_id = item.get("shop_id"), item.get("item_id")
            name  = item.get("name") or anchor.get("name") or ""
            price = item.get("price") or anchor.get("price")
            sold  = item.get("historical_sold") or item.get("sold")
            image = item.get("image") or anchor.get("image")
        elif anchor:
            shop_id, item_id = anchor.get("shop_id"), anchor.get("item_id")
            name, price, sold, image = anchor.get("name") or "", anchor.get("price"), None, anchor.get("image")
        elif pv2.get("item_id"):
            shop_id, item_id = pv2.get("shop_id"), pv2.get("item_id")
            name  = pv2.get("item_name") or ""
            price = (pv2.get("item_price") or {}).get("price")
            sold  = (pv2.get("sell_stat") or {}).get("historical_sold")
            image = (pv2.get("item_image") or {}).get("image_id")
        else:
            return {"product_name": "", "product_url": "", "product_price": 0,
                    "product_sold": 0, "product_count": 0, "product_image": ""}

        try:
            price_vnd = int(price or 0) // 100000
        except (TypeError, ValueError):
            price_vnd = 0
        try:
            sold = int(sold or 0)
        except (TypeError, ValueError):
            sold = 0
        return {
            "product_name":  name,
            "product_url":   f"{self.base_host}/product/{shop_id}/{item_id}" if shop_id and item_id else "",
            "product_price": price_vnd,
            "product_sold":  sold,
            "product_count": products.get("count") or len(items) or 1,
            "product_image": self._image_url(image),
        }

    def _parse_video(self, v: dict, profile_id: str) -> dict:
        """
        Item timeline: meta{post_id, user_name, count_info{views,likes,comments}, ctime(ms)},
        content{caption, video{video_id, cover, url}}, allow_info{allow_duet, allow_stitch}
        """
        meta    = v.get("meta") or {}
        counts  = meta.get("count_info") or {}
        content = v.get("content") or {}
        video   = content.get("video") or {}
        allow   = v.get("allow_info") or {}
        profile_id = str(profile_id or meta.get("user_id") or "")

        caption = content.get("caption") or ""
        hashtags = []
        for h in content.get("hashtags") or []:
            try:
                name = caption[h["start"]:h["start"] + h["length"]]
            except (KeyError, TypeError):
                continue
            if h.get("hashtag_id") and name.startswith("#"):
                hashtags.append((str(h["hashtag_id"]), name.lower()))

        def num(val):
            try:
                return int(val or 0)
            except (TypeError, ValueError):
                return 0

        create_time = num(meta.get("ctime") or meta.get("ptime"))
        if create_time > 10**12:
            create_time //= 1000

        # Creator/shop liên quan để quét lan: người được tag, tác giả nhạc gốc, chủ shop sản phẩm gắn
        related = []
        for m in content.get("mentions") or []:
            related.append((m.get("user_id") or m.get("userid"), "mention"))
        related.append(((content.get("music") or {}).get("author_id"), "music"))
        for it in (content.get("products") or {}).get("enhanced_item_list") or []:
            related.append((it.get("shop_user_id"), "product_shop"))
        related_ids = sorted({(str(uid), kind) for uid, kind in related
                              if uid and str(uid) != str(profile_id)})

        product = self._main_product(content)
        prod_items = self._all_products(content)
        prod_urls = []
        for sid, iid, _name in prod_items:
            if sid and iid:
                u = f"{self.base_host}/product/{sid}/{iid}"
                if u not in prod_urls:
                    prod_urls.append(u)
        main_u = product.get("product_url")
        if main_u and main_u not in prod_urls:
            prod_urls.insert(0, main_u)

        video_id = video.get("video_id") or meta.get("post_id") or ""
        return {
            **product,
            "product_items": prod_items,
            "product_urls":  prod_urls,
            "all_product_urls": "\n".join(prod_urls),
            "related_ids":   related_ids,
            "hashtags":      hashtags,
            "profile_id":    profile_id,
            "username":      meta.get("user_name") or "",
            "display_name":  meta.get("shopee_nick_name") or "",
            "post_id":       meta.get("post_id") or "",
            "video_id":      str(video_id),
            "allow_duet":    bool(allow.get("allow_duet")),
            "allow_stitch":  bool(allow.get("allow_stitch")),
            "video_url":     video.get("url") or "",
            "thumbnail":     self._image_url(video.get("cover"), "@resize_ss480x640!@crop_w480_h640_cT"),
            "description":   content.get("caption") or "",
            "play_count":    num(counts.get("views")),
            "like_count":    num(counts.get("likes")),
            "comment_count": num(counts.get("comments")),
            "share_count":   num(counts.get("shares")),
            "create_time":   create_time,
            "share_url":     self._video_link(meta.get("post_id"), profile_id),
        }

    def _image_url(self, image_id: str | None, suffix: str = "") -> str:
        """Mã ảnh Shopee → URL CDN (ảnh bìa video, ảnh sản phẩm)."""
        if not image_id:
            return ""
        if image_id.startswith("http"):
            return image_id
        cc = self.country.lower()
        if suffix:
            return f"https://down-bs-{cc}.img.susercontent.com/{image_id}{suffix}"
        return f"https://down-{cc}.img.susercontent.com/file/{image_id}"

    def _video_link(self, post_id: str | None, profile_id: str) -> str:
        """
        Link mở đúng video trong app Shopee (điện thoại đã cài app sẽ mở bằng app).
        Cùng dạng link dài mà app tạo khi bấm Chia sẻ video, trước khi rút gọn.
        """
        if not post_id:
            return f"{self.sv_host}/profile/{profile_id}"
        video_url = (f"{self.sv_host}/share-video/{post_id}?fromShareLink=share-marker"
                     f"&contentType=0&jumpType=share&pid=sv&share_obj=video&myVideo=false")
        return f"{self.base_host}/universal-link?redir={quote(video_url, safe='')}"
