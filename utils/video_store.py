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
        self._conn = sqlite3.connect(self.db_path, timeout=30.0)
        self._conn.execute("PRAGMA journal_mode=WAL")   # ghi nhanh, không khóa cả file
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS videos ("
            "video_id TEXT NOT NULL, country TEXT NOT NULL, data TEXT NOT NULL, updated REAL, "
            "PRIMARY KEY (country, video_id))"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_country ON videos(country)")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS scanned_creators ("
            "country TEXT NOT NULL, profile_id TEXT NOT NULL, video_count INTEGER DEFAULT 0, updated REAL, "
            "PRIMARY KEY (country, profile_id))"
        )
        self._conn.commit()
        self._pending: dict[tuple, tuple] = {}   # (country, vid) → (data_json, ts); gom lại, flush định kỳ
        self._last_save_ts = time.time()
        self._saved_since_ckpt = 0
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
        """Thêm/cập nhật 1 video vào bộ đệm và tự động ghi xuống đĩa mỗi 100 video hoặc mỗi 30 giây."""
        vid = str(v.get("video_id") or "")
        if not vid:
            return False
        cc = (country or "VN").upper()
        key = (cc, vid)
        now = time.time()
        self._pending[key] = (json.dumps(v, ensure_ascii=False), now)
        if len(self._pending) >= 100 or (now - self._last_save_ts) >= 30.0:
            self.save()
        return True

    def maybe_save(self, max_items: int = 100, max_age_sec: float = 30.0):
        """Ghi xuống đĩa nếu đã đủ 100 video mới hoặc đã qua 30 giây."""
        if self._pending and (len(self._pending) >= max_items or (time.time() - self._last_save_ts) >= max_age_sec):
            self.save()

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
        self._saved_since_ckpt += len(rows)
        self._pending.clear()
        self._last_save_ts = time.time()
        if self._saved_since_ckpt >= 1000:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
            self._saved_since_ckpt = 0

    def delete_video(self, vid: str, country: str):
        self.delete_videos([vid], country)

    def delete_videos(self, vids, country: str):
        cc = (country or "VN").upper()
        clean = list({str(v) for v in vids if v})
        if not clean:
            return
        for vid in clean:
            self._pending.pop((cc, vid), None)
        for i in range(0, len(clean), 900):
            chunk = clean[i:i + 900]
            placeholders = ",".join("?" * len(chunk))
            self._conn.execute(
                f"DELETE FROM videos WHERE country=? AND video_id IN ({placeholders})",
                [cc, *chunk]
            )
        self._conn.commit()

    def clear(self, country: str):
        cc = (country or "VN").upper()
        self._pending = {k: v for k, v in self._pending.items() if k[0] != cc}
        self._conn.execute("DELETE FROM videos WHERE country=?", (cc,))
        self._conn.commit()

    def mark_creator_scanned(self, profile_id: str, country: str, video_count: int = 0):
        """Đánh dấu 1 Profile ID đã cào xong để các phiên sau không cào trùng lại."""
        pid = str(profile_id or "").strip()
        if not pid:
            return
        cc = (country or "VN").upper()
        self._conn.execute(
            "INSERT OR REPLACE INTO scanned_creators(country, profile_id, video_count, updated) VALUES (?,?,?,?)",
            (cc, pid, int(video_count or 0), time.time())
        )
        self._conn.commit()

    def get_scanned_creators(self, country: str) -> set[str]:
        """Lấy tập hợp các Profile ID đã cào xong của quốc gia này."""
        cc = (country or "VN").upper()
        cur = self._conn.execute("SELECT profile_id FROM scanned_creators WHERE country=?", (cc,))
        return {str(r[0]) for r in cur if r[0]}

    def close(self):
        self.save()
        self._conn.close()
