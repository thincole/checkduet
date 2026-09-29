"""
Shopee API Headers
User-Agent giả lập Android app Shopee (appver=33731) và Desktop Web
Hỗ trợ đa quốc gia: VN, PH, ID, TH, MY, SG
"""

APP_UA = "Android app Shopee appver=33731 app_type=1"
WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

REGIONS = {
    "VN": {
        "name": "Việt Nam (VN)",
        "flag": "🇻🇳",
        "domain": "shopee.vn",
        "video_domain": "sv.shopee.vn",
        "short_domain": "vn.shp.ee",
        "lang": "vi",
        "accept_lang": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    },
    "PH": {
        "name": "Philippines (PH)",
        "flag": "🇵🇭",
        "domain": "shopee.ph",
        "video_domain": "sv.shopee.ph",
        "short_domain": "ph.shp.ee",
        "lang": "en",
        "accept_lang": "en-PH,en;q=0.9,en-US;q=0.8",
    },
    "ID": {
        "name": "Indonesia (ID)",
        "flag": "🇮🇩",
        "domain": "shopee.co.id",
        "video_domain": "sv.shopee.co.id",
        "short_domain": "id.shp.ee",
        "lang": "id",
        "accept_lang": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    },
    "TH": {
        "name": "Thái Lan (TH)",
        "flag": "🇹🇭",
        "domain": "shopee.co.th",
        "video_domain": "sv.shopee.co.th",
        "short_domain": "th.shp.ee",
        "lang": "th",
        "accept_lang": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    },
    "MY": {
        "name": "Malaysia (MY)",
        "flag": "🇲🇾",
        "domain": "shopee.com.my",
        "video_domain": "sv.shopee.com.my",
        "short_domain": "my.shp.ee",
        "lang": "en",
        "accept_lang": "en-MY,en;q=0.9,ms;q=0.8,en-US;q=0.7",
    },
    "SG": {
        "name": "Singapore (SG)",
        "flag": "🇸🇬",
        "domain": "shopee.sg",
        "video_domain": "sv.shopee.sg",
        "short_domain": "sg.shp.ee",
        "lang": "en",
        "accept_lang": "en-SG,en;q=0.9,en-US;q=0.8",
    },
}


def get_region(country: str = "VN") -> dict:
    code = (country or "VN").upper().strip()
    return REGIONS.get(code, REGIONS["VN"])


DEFAULT_HEADERS = {
    "User-Agent": APP_UA,
    "shopee_app_version": "33731",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Language": "vi",
    "Connection": "keep-alive",
}


def build_headers(cookie: str = "", country: str = "VN") -> dict:
    """Tạo headers đầy đủ với cookie và ngôn ngữ quốc gia."""
    reg = get_region(country)
    headers = DEFAULT_HEADERS.copy()
    headers["Accept-Language"] = reg["accept_lang"]
    if cookie:
        headers["Cookie"] = cookie
    return headers


def timeline_headers(cookie: str = "", country: str = "VN") -> dict:
    """Headers cho sv.shopee.{domain}/api/v2/timeline/me."""
    reg = get_region(country)
    headers = {
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/json; charset=UTF-8",
        "Host": reg["video_domain"],
        "language": reg["lang"],
        "User-Agent": APP_UA,
        "X-SAP-Type": "1",
        "cache-control": "no-cache, no-store",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def web_headers(cookie: str = "", country: str = "VN") -> dict:
    """Headers trình duyệt desktop cho shopee.{domain}/api/v4/search/search_hint."""
    reg = get_region(country)
    base = f"https://{reg['domain']}"
    headers = {
        "accept": "application/json",
        "origin": base,
        "referer": f"{base}/",
        "x-api-source": "pc",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": WEB_UA,
        "accept-language": reg["accept_lang"],
    }
    if cookie:
        headers["cookie"] = cookie
    return headers
