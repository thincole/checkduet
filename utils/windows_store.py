"""
Kho đếm "cửa sổ" sản phẩm (SQLite): sản phẩm → tập video (đã quét) có gắn sản phẩm đó.
Dùng chung data/shopee_duet.db với video_store. Đây là số TỐI THIỂU: chỉ tính video đã quét.
"""

import json
import os
import re
import sqlite3
import time

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

_PATTERNS = (r"/product/(\d+)/(\d+)", r"-i\.(\d+)\.(\d+)", r"/opaanlp/(\d+)/(\d+)")


def parse_product_link(text: str) -> tuple[str, str] | None:
    """Link sản phẩm → (shop_id, item_id). Link rút gọn s.shopee.vn được mở 1 lần để đọc redirect."""
    text = (text or "").strip()
    for pat in _PATTERNS:
        m = re.search(pat, text)
        if m:
            return m.group(1), m.group(2)
    if re.match(r"https?://(s\.shopee\.|shp\.ee|[a-z]{2}\.shp\.ee)", text):
        try:
            loc = requests.get(text, allow_redirects=False, timeout=12,
                               headers={"User-Agent": "Mozilla/5.0"}).headers.get("Location") or ""
        except requests.RequestException:
            return None
        for pat in _PATTERNS:
            m = re.search(pat, loc)
            if m:
                return m.group(1), m.group(2)
    return None


class WindowsStore:
    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "shopee_duet.db")
        self._conn = sqlite3.connect(self.db_path, timeout=30.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS products (item_id TEXT PRIMARY KEY, shop_id TEXT, name TEXT)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS product_videos (item_id TEXT, video_id TEXT, "
            "PRIMARY KEY (item_id, video_id))")
        try:
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pv_video ON product_videos(video_id)")
        except sqlite3.OperationalError:
            pass
        self._conn.commit()
        self._pend_prod: dict[str, tuple] = {}     # item_id → (shop_id, name)
        self._pend_link: set[tuple] = set()         # (item_id, video_id)
        self._last_save_ts: float = time.time()
        self._migrate_json()

    def _migrate_json(self):
        path = os.path.join(self.data_dir, "product_windows.json")
        try:
            raw = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            return
        for item_id, e in raw.items():
            self._conn.execute("INSERT OR IGNORE INTO products(item_id, shop_id, name) VALUES (?,?,?)",
                               (str(item_id), str(e.get("shop_id", "")), e.get("name", "")))
            self._conn.executemany("INSERT OR IGNORE INTO product_videos(item_id, video_id) VALUES (?,?)",
                                   [(str(item_id), str(vid)) for vid in e.get("videos") or []])
        self._conn.commit()
        try:
            os.replace(path, path + ".imported")
        except OSError:
            pass

    def add_video(self, v: dict):
        vid = str(v.get("post_id") or v.get("video_id") or "")
        if not vid:
            return
        for shop_id, item_id, name in v.get("product_items") or []:
            item_id = str(item_id)
            prev = self._pend_prod.get(item_id)
            # giữ tên nếu đã có; chỉ ghi tên khi có tên mới
            self._pend_prod[item_id] = (str(shop_id), name or (prev[1] if prev else ""))
            self._pend_link.add((item_id, vid))
        now = time.time()
        if len(self._pend_link) >= 2000 or (now - self._last_save_ts) >= 300.0:
            self.save()

    def maybe_save(self, max_items: int = 2000, max_age_sec: float = 300.0):
        if (self._pend_prod or self._pend_link) and (
            len(self._pend_link) >= max_items or (time.time() - self._last_save_ts) >= max_age_sec
        ):
            self.save()

    def save(self):
        if self._pend_prod:
            for item_id, (shop_id, name) in self._pend_prod.items():
                self._conn.execute(
                    "INSERT INTO products(item_id, shop_id, name) VALUES (?,?,?) "
                    "ON CONFLICT(item_id) DO UPDATE SET shop_id=excluded.shop_id, "
                    "name=CASE WHEN excluded.name!='' THEN excluded.name ELSE products.name END",
                    (item_id, shop_id, name))
        if self._pend_link:
            self._conn.executemany(
                "INSERT OR IGNORE INTO product_videos(item_id, video_id) VALUES (?,?)", list(self._pend_link))
        if self._pend_prod or self._pend_link:
            self._conn.commit()
            self._pend_prod.clear()
            self._pend_link.clear()
            self._last_save_ts = time.time()

    def count(self, item_id: str) -> tuple[str, int]:
        self.save()
        row = self._conn.execute("SELECT name FROM products WHERE item_id=?", (str(item_id),)).fetchone()
        n = self._conn.execute(
            "SELECT COUNT(*) FROM product_videos WHERE item_id=?", (str(item_id),)).fetchone()[0]
        return (row[0] if row else ""), n

    def all_rows(self) -> list[tuple[str, str, str, int]]:
        """[(shop_id, item_id, name, count)] giảm dần theo count."""
        self.save()
        cur = self._conn.execute(
            "SELECT p.shop_id, p.item_id, p.name, COUNT(pv.video_id) AS n "
            "FROM products p LEFT JOIN product_videos pv ON pv.item_id=p.item_id "
            "GROUP BY p.item_id ORDER BY n DESC")
        return [(r[0], r[1], r[2], r[3]) for r in cur]

    def product_count(self) -> int:
        self.save()
        return self._conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    def video_total(self) -> int:
        self.save()
        return self._conn.execute("SELECT COUNT(DISTINCT video_id) FROM product_videos").fetchone()[0]

    def delete_video(self, video_id: str):
        self.delete_videos([video_id])

    def delete_videos(self, video_ids):
        clean = list({str(v) for v in video_ids if v})
        if not clean:
            return
        if self._pend_link:
            clean_set = set(clean)
            self._pend_link = {(iid, v) for iid, v in self._pend_link if v not in clean_set}
        # Xóa theo lô 900 ID mỗi câu lệnh IN (...) kết hợp index idx_pv_video cực nhanh
        for i in range(0, len(clean), 900):
            chunk = clean[i:i + 900]
            placeholders = ",".join("?" * len(chunk))
            self._conn.execute(
                f"DELETE FROM product_videos WHERE video_id IN ({placeholders})",
                chunk
            )
        self._conn.commit()

    def clear(self):
        self._pend_prod.clear()
        self._pend_link.clear()
        self._conn.execute("DELETE FROM products")
        self._conn.execute("DELETE FROM product_videos")
        self._conn.commit()

    def close(self):
        self.save()
        self._conn.close()
