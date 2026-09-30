"""
Exporter — xuất kết quả ra CSV / JSON
"""

import csv
import json
import os
from datetime import datetime


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def export_csv(results: list, export_dir: str = "results", prefix: str = "duet_check") -> str:
    """Xuất kết quả ra CSV. Trả về đường dẫn file."""
    _ensure_dir(export_dir)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(export_dir, f"{prefix}_{ts}.csv")

    fieldnames = [
        "profile_id", "video_id", "allow_duet", "allow_stitch",
        "play_count", "like_count", "comment_count", "share_count",
        "views_per_day", "engagement", "post_date",
        "description", "product_name", "product_url", "all_product_urls",
        "product_price", "product_sold", "product_count",
        "share_url", "video_url", "create_time",
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            r = dict(row)
            if not r.get("all_product_urls"):
                urls = list(r.get("product_urls") or [])
                if not urls:
                    for it in (r.get("product_items") or []):
                        if isinstance(it, (list, tuple)) and len(it) >= 2:
                            sid, iid = str(it[0]).strip(), str(it[1]).strip()
                            if sid and iid:
                                u = f"https://shopee.vn/product/{sid}/{iid}"
                                if u not in urls:
                                    urls.append(u)
                if not urls and r.get("product_url"):
                    urls.append(r["product_url"])
                r["all_product_urls"] = "\n".join(urls)
            writer.writerow(r)

    return path


def export_json(results: list, export_dir: str = "results") -> str:
    """Xuất kết quả ra JSON. Trả về đường dẫn file."""
    _ensure_dir(export_dir)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(export_dir, f"duet_check_{ts}.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return path


def export_duet_urls(results: list, export_dir: str = "results") -> str:
    """Xuất danh sách URL của video cho phép duet ra TXT."""
    _ensure_dir(export_dir)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(export_dir, f"duet_allowed_urls_{ts}.txt")

    urls = [r["share_url"] for r in results if r.get("allow_duet")]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(urls))

    return path
