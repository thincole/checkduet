"""
Viral scoring — tính tốc độ view và lọc video "đang viral"
"""

import time
from datetime import datetime


def enrich(v: dict, now: float | None = None) -> dict:
    """Thêm age_days, views_per_day, engagement, post_date, duet_score vào video dict."""
    now = now or time.time()
    ct = v.get("create_time") or 0
    views = v.get("play_count") or 0
    if ct > 0:
        age = max((now - ct) / 86400, 0.5)  # tránh chia cho số quá nhỏ với video vừa đăng
        v["age_days"] = round(age, 1)
        v["views_per_day"] = int(views / age)
        v["post_date"] = datetime.fromtimestamp(ct).strftime("%Y-%m-%d")
    else:
        v["age_days"] = None
        v["views_per_day"] = 0
        v["post_date"] = ""
    inter = (v.get("like_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0)
    v["engagement"] = round(inter * 100 / views, 2) if views else 0.0
    # Điểm duet: trung bình nhân của tốc độ view và sức bán → cần CẢ HAI đều cao.
    # Video không gắn sản phẩm bán chạy sẽ bị điểm thấp dù nhiều view.
    vpd = v.get("views_per_day") or 0
    sold = v.get("product_sold") or 0
    v["duet_score"] = int((vpd * (sold + 1)) ** 0.5)
    return v


def filter_viral(videos: list, max_age_days: int = 0, min_views: int = 0,
                 min_likes: int = 0, min_views_per_day: int = 0, min_sold: int = 0,
                 duet_only: bool = True, sort_by: str = "views_per_day", top_n: int = 0) -> list:
    """Lọc và xếp hạng. sort_by: 'views_per_day' hoặc 'duet_score'."""
    out = []
    for v in videos:
        if duet_only and not v.get("allow_duet"):
            continue
        if (v.get("play_count") or 0) < min_views:
            continue
        if (v.get("like_count") or 0) < min_likes:
            continue
        if (v.get("views_per_day") or 0) < min_views_per_day:
            continue
        if (v.get("product_sold") or 0) < min_sold:
            continue
        if max_age_days > 0:
            age = v.get("age_days")
            if age is None or age > max_age_days:
                continue
        out.append(v)
    key = sort_by if sort_by in ("views_per_day", "duet_score") else "views_per_day"
    out.sort(key=lambda x: (x.get(key) or 0, x.get("play_count") or 0), reverse=True)
    return out[:top_n] if top_n > 0 else out
