"""
Config Manager — đọc/ghi settings.json
"""

import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")

DEFAULTS = {
    "country":             "VN",
    "cookie":              "",
    "cookies_by_country":  {},
    "delay_ms":            500,
    "max_videos_per_shop": 0,
    "filter_duet_only":    False,
    "export_path":         "results",
    "proxy":               "",
    "last_import_path":    "",
    "last_export_path":    "",
    "window_width":        1100,
    "window_height":       700,
    "sign_api_url":        "https://credit.toolshopee.vn/api/sign",
    "sign_api_key":        "Gte3Ka4W2Y2RTJ7MdcqFYua6nnMOImWx7BU2e2ZcseG5gBvU",
    "viral_seeds":         "",
    "viral_crawl":         True,
    "viral_crawl_hashtags": True,
    "viral_hashtags":      "",
    "hashtags_by_country": {},
    "viral_credit_budget": 50,
    "viral_videos_per_hashtag": 24,
    "viral_videos_per_creator": 48,
    "viral_threads":       1,
    "viral_max_age_days":  0,
    "viral_min_views":     10000,
    "viral_min_likes":     0,
    "viral_min_vpd":       20,
    "viral_min_sold":      0,
    "viral_sort_by":       "duet_score",
    "viral_mode":          "duet",   # "duet" = video CÓ duet, "view" = video nhiều view
    "viral_duet_only":     True,
    "viral_top_n":         100,
    "gsheet_credentials":  r"F:\MMO\GemPhoneFarm.json",
    "gsheet_sheet":        "https://docs.google.com/spreadsheets/d/1P3WvAU8Dlwvqebvpp2g0J610Su0TsCCjCAecLJ4zM-Y",
    "gsheet_tab":          "",   # trống = dùng mã quốc gia (VN, PH...)
}


def load() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = DEFAULTS.copy()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return DEFAULTS.copy()


def save(cfg: dict):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Config] Save error: {e}")
