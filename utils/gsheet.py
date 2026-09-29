"""
Xuất kết quả sang Google Sheet bằng service account (file JSON).
Người dùng chia sẻ Google Sheet cho email service account (quyền Người chỉnh sửa).
Dữ liệu được ghi tiếp vào 1 tab cố định, bỏ qua video đã có (so theo cột Video ID).
"""

import json
import re

import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound

HEADERS = ["Profile ID", "Creator", "Video ID", "Duet", "Lượt xem", "View/ngày", "Lượt thích",
           "Bình luận", "Ngày đăng", "Mô tả", "Tên SP", "Giá (đ)", "Đã bán", "Link video", "Link SP"]
VIDEO_ID_COL = HEADERS.index("Video ID") + 1


def sa_email(cred_path: str) -> str:
    """Email service account trong file JSON ('' nếu file không hợp lệ)."""
    try:
        with open(cred_path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return ""
    return d.get("client_email", "") if d.get("type") == "service_account" else ""


def sheet_key(sheet: str) -> str:
    """Nhận link Google Sheet hoặc ID, trả về ID."""
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", sheet or "")
    return m.group(1) if m else (sheet or "").strip()


def _text(s) -> str:
    """Chặn công thức: ô bắt đầu bằng = + - @ sẽ bị Sheets hiểu là công thức."""
    s = str(s or "")
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def _url(url) -> str:
    """URL đầy đủ dạng chữ — Sheets tự tạo link, người dùng đọc và copy được cả đường dẫn."""
    url = str(url or "")
    return url if url.startswith(("https://", "http://")) else ""


def to_rows(videos: list) -> list:
    rows = []
    for v in videos:
        rows.append([
            _text(v.get("profile_id")),
            _text(v.get("display_name") or v.get("username")),
            _text(v.get("video_id")),
            "YES" if v.get("allow_duet") else "NO",
            int(v.get("play_count") or 0),
            int(v.get("views_per_day") or 0),
            int(v.get("like_count") or 0),
            int(v.get("comment_count") or 0),
            _text(v.get("post_date")),
            _text(v.get("description")),
            _text(v.get("product_name")),
            int(v.get("product_price") or 0),
            int(v.get("product_sold") or 0),
            _url(v.get("share_url")),
            _url(v.get("product_url")),
        ])
    return rows


def _friendly(e: Exception, cred_path: str) -> str:
    email = sa_email(cred_path) or "email service account"
    text = str(e)
    if isinstance(e, SpreadsheetNotFound) or "PERMISSION_DENIED" in text and "caller does not have" in text:
        return f"Không mở được sheet. Hãy bấm Chia sẻ trên Google Sheet và thêm {email} với quyền Người chỉnh sửa."
    if "SERVICE_DISABLED" in text or "has not been used" in text or "is disabled" in text:
        return ("Project Google Cloud của file JSON chưa bật Google Sheets API. Vào console.cloud.google.com → "
                "APIs & Services → Library → Google Sheets API → Enable.")
    if isinstance(e, APIError) and "404" in text:
        return "Không tìm thấy sheet — kiểm tra lại link Google Sheet."
    if isinstance(e, (OSError, ValueError)):
        return f"Không đọc được file JSON: {e}"
    return text


def _open(cred_path: str, sheet: str):
    if not sa_email(cred_path):
        raise ValueError("file không phải service account JSON")
    gc = gspread.service_account(filename=cred_path)
    return gc.open_by_key(sheet_key(sheet))


def ping(cred_path: str, sheet: str) -> dict:
    try:
        sh = _open(cred_path, sheet)
        return {"ok": True, "name": sh.title, "url": sh.url}
    except Exception as e:
        return {"ok": False, "error": _friendly(e, cred_path)}


def _prepare_tab(sh, tab: str):
    """Lấy tab (tạo nếu chưa có) và đảm bảo dòng 1 là HEADERS. Trả về (ws, lỗi)."""
    try:
        ws = sh.worksheet(tab)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=1000, cols=len(HEADERS))
    header = ws.row_values(1)
    if not any(h.strip() for h in header):
        ws.update(values=[HEADERS], range_name="A1")
        ws.format("1:1", {"textFormat": {"bold": True},
                          "backgroundColor": {"red": 0.99, "green": 0.9, "blue": 0.88}})
        ws.freeze(rows=1)
    elif header[:len(HEADERS)] != HEADERS:
        return None, (f"Tab “{tab}” đang có dữ liệu với cấu trúc cột khác. "
                      "Chọn tab khác trong Cài đặt (hoặc để trống ô Tab để dùng tab theo quốc gia).")
    return ws, ""


def new_videos(videos: list, existing_ids: set) -> tuple[list, int]:
    """Bỏ video đã có trong sheet và video lặp trong chính lô này. Trả về (video mới, số bị bỏ)."""
    seen, out, skipped = set(existing_ids), [], 0
    for v in videos:
        vid = str(v.get("video_id") or "").strip()
        if not vid or vid in seen:
            skipped += 1
            continue
        seen.add(vid)
        out.append(v)
    return out, skipped


def push(videos: list, cred_path: str, sheet: str, tab: str) -> dict:
    """
    Ghi tiếp videos vào tab cố định, lọc trùng theo Video ID với dữ liệu đã có.
    Trả về {ok, added, skipped, total, sheet, url} hoặc {ok: False, error}.
    """
    try:
        sh = _open(cred_path, sheet)
        ws, err = _prepare_tab(sh, tab)
        if err:
            return {"ok": False, "error": err}
        existing = {x.strip() for x in ws.col_values(VIDEO_ID_COL)[1:] if x.strip()}
        fresh, skipped = new_videos(videos, existing)
        if fresh:
            ws.append_rows(to_rows(fresh), table_range="A1",
                           value_input_option=gspread.utils.ValueInputOption.user_entered)
        return {"ok": True, "added": len(fresh), "skipped": skipped, "total": len(existing) + len(fresh),
                "sheet": tab, "url": f"{sh.url}#gid={ws.id}"}
    except Exception as e:
        return {"ok": False, "error": _friendly(e, cred_path)}
