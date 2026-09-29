"""
Database SQLite (data/shopee.db): lưu video đã quét + nguồn đã quét, dùng lại cho các lần sau.
An toàn đa luồng: 1 kết nối dùng chung, mọi thao tác đi qua khóa.
"""

import json
import os
import sqlite3
import threading
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "shopee.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id      TEXT NOT NULL,
    country       TEXT NOT NULL,
    profile_id    TEXT,
    allow_duet    INTEGER,
    play_count    INTEGER,
    product_sold  INTEGER,
    create_time   INTEGER,
    first_seen    INTEGER,
    last_seen     INTEGER,
    data          TEXT,
    PRIMARY KEY (video_id, country)
);
CREATE INDEX IF NOT EXISTS idx_videos_country_duet ON videos(country, allow_duet);
CREATE TABLE IF NOT EXISTS scanned (
    kind          TEXT NOT NULL,      -- 'creator' | 'hashtag'
    key           TEXT NOT NULL,
    country       TEXT NOT NULL,
    last_scanned  INTEGER,
    PRIMARY KEY (kind, key, country)
);
"""

# Trường tính lại mỗi lần nạp (phụ thuộc thời điểm) — không cần lưu
_DERIVED = ("age_days", "views_per_day", "engagement", "post_date", "duet_score")


class VideoDB:
    def __init__(self, path: str = DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._con = sqlite3.connect(path, check_same_thread=False)
        self._con.executescript(_SCHEMA)
        self._con.commit()

    def upsert_video(self, v: dict, country: str):
        vid = str(v.get("video_id") or "")
        if not vid:
            return
        now = int(time.time())
        data = json.dumps({k: val for k, val in v.items() if k not in _DERIVED}, ensure_ascii=False)
        with self._lock:
            self._con.execute(
                """INSERT INTO videos (video_id, country, profile_id, allow_duet, play_count, product_sold,
                                       create_time, first_seen, last_seen, data)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(video_id, country) DO UP