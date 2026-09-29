"""
Kho video (SQLite): lưu đầy đủ mọi video đã quét, theo từng quốc gia.
Dùng data/shopee_duet.db — ghi từng dòng (upsert theo video_id), không rewrite cả file,
mở app là có sẵn dữ liệu cũ (không tốn credit). Tự nhập từ file .json cũ nếu có.
"""

import glob
import json
import os
import sqlite3
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class VideoStore:
    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "shopee_duet.db")
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")   # ghi nhanh, không khóa cả file
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS videos ("
            "video_id TEXT NOT NULL, country TEXT NOT NULL, data TEXT NOT NULL, updated REAL, "
            "PRIMARY KEY (country, video_id))"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_country ON videos(country)")
        self._conn.commit()
        self._pending: dict[tuple, tuple] = {}   # (country, vid) → (data_json, ts); gom lại, flush 1 lần
        self._migrate_json()

    # ------------------------------------------------------------------
    def _migrate_json(self):
        """Nhập một lần từ các file videos_<CC>.json cũ rồi đổi tên .imported."""
        for path in glob.glob(os.path.join(self.data_dir, "videos_*.json")):
            cc = os.path.basename(path)[len("videos_"):-len(".json")].upper()
            try:
                data = json.load(open(path, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            rows = [(str(v["video_id"]), cc, json.dumps(v, ensure_ascii=False), time.time())
                    for v in data if v.get("video_id")]
            if rows:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO videos(video_id, country, data, updated) VALUES (?,?,?,?)", rows)
                self._conn.commit()
            try:
                os.replace(path, path + ".imported")
            except OSError:
                pass

    # ------------------------------------------------------------------
    def list(self, country: str) -> list[dict]:
        cc = (country or "VN").upper()
        cur = self._conn.execute("SELECT data FROM videos WHERE country=?", (cc,))
        out = []
        for (blob,) in cur:
            try:
                out.append(json.loads(blob))
            except ValueError:
                pass
        # gộp cả phần đang chờ ghi (chưa flush) của nước này
        for (c, _vid), (blob, _ts) in self._pending.items():
            if c == cc:
                try:
                    out.append(json.loads(blob))
                except ValueError:
                    pass
        return out

    def add_video(self, v: dict, country: str) -> bool:
        """Thêm/cập nhật 1 video vào bộ đệm (flush khi save). True nếu là video_id mới."""
        vid = str(v.get("video_id") or "")
        if not vid:
            return False
        cc = (country or "VN").upper()
        key = (cc, vid)
        is_new = key not in self._pending and not self._exists(cc, vid)
        self._pending[key] = (json.dumps(v, ensure_ascii=False), time.time())
        return is_new

    def _exists(self, cc: str, vid: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM videos WHERE country=? AND video_id=? LIMIT 1", (cc, vid)).fetchone() is not None

    def count(self, country: str) -> int:
        cc = (country or "VN").upper()
        n = self._conn.execute("SELECT COUNT(*) FROM videos WHERE country=?", (cc,)).fetchone()[0]
        n += sum(1 for (c, vid) in self._pending if c == cc and not self._exists(cc, vid))
        return n

    def save(self):
        if not self._pending:
            return
        rows = [(vid, cc, blob, ts) for (cc, vid), (blob, ts) in self._pending.items()]
        self._conn.executemany(
            "INSERT OR REPLACE INTO videos(video_id, country, data, updated) VALUES (?,?,?,?)", rows)
        self._conn.commit()
        self._pending.clear()

    def clear(self, country: str):
        cc = (country or "VN").upper()
        self._pending = {k: v for k, v in self._pending.items() if k[0] != cc}
        self._conn.execute("DELETE FROM videos WHERE country=?", (cc,))
        self._conn.commit()

    def close(self):
        self.save()
        self._conn.close()
