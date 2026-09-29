"""
HTML export — trang danh sách video cho điện thoại.
Mỗi thẻ có nút mở thẳng video trong app Shopee (universal link) và link sản phẩm.
"""

import os
from datetime import datetime
from html import escape


def _num(n) -> str:
    try:
        return f"{int(n or 0):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def _safe_url(u) -> str:
    u = str(u or "")
    return escape(u, quote=True) if u.startswith(("https://", "http://")) else ""


def _card(v: dict, idx: int) -> str:
    vid      = escape(str(v.get("video_id") or idx), quote=True)
    duet     = bool(v.get("allow_duet"))
    creator  = escape(v.get("display_name") or v.get("username") or str(v.get("profile_id") or ""))
    caption  = escape(v.get("description") or "")
    cover    = _safe_url(v.get("thumbnail"))
    link     = _safe_url(v.get("share_url"))
    p_url    = _safe_url(v.get("product_url"))
    p_img    = _safe_url(v.get("product_image"))
    p_name   = escape(v.get("product_name") or "")

    stats = [f"👁 {_num(v.get('play_count'))}"]
    if v.get("views_per_day"):
        stats.append(f"🔥 {_num(v.get('views_per_day'))}/ngày")
    stats.append(f"❤ {_num(v.get('like_count'))}")
    if v.get("post_date"):
        stats.append(f"📅 {escape(v['post_date'])}")

    product = ""
    if p_name:
        product = f"""
      <div class="prod">
        {f'<img src="{p_img}" loading="lazy" alt="">' if p_img else ''}
        <div class="pinfo">
          <div class="pname">{p_name}</div>
          <div class="pmeta"><b>{_num(v.get('product_price'))}đ</b> · Đã bán {_num(v.get('product_sold'))}</div>
        </div>
      </div>"""

    buttons = f'<a class="btn primary" href="{link}" data-open="{vid}">▶ Mở trong app Shopee</a>' if link else ""
    if p_url:
        buttons += f'<a class="btn" href="{p_url}">🛒 Sản phẩm</a>'

    return f"""
  <article class="card" id="v-{vid}">
    <div class="cover">
      {f'<img src="{cover}" loading="lazy" alt="">' if cover else ''}
      <span class="badge {'ok' if duet else 'no'}">{'✅ Duet' if duet else '❌ No duet'}</span>
      <span class="rank">#{idx}</span>
      <span class="opened-tag">Đã mở</span>
    </div>
    <div class="body">
      <div class="creator">{creator}</div>
      <div class="caption">{caption}</div>
      <div class="stats">{' · '.join(stats)}</div>{product}
      <div class="actions">{buttons}</div>
    </div>
  </article>"""


def build_html(videos: list, title: str = "Video Shopee có Duet") -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    duet = sum(1 for v in videos if v.get("allow_duet"))
    cards = "".join(_card(v, i + 1) for i, v in enumerate(videos))
    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
  :root {{ --bg:#f4f5f7; --card:#fff; --text:#1d1d1f; --muted:#6b6f76; --line:#e6e7ea;
          --brand:#ee4d2d; --ok:#1a7a3c; --no:#c0392b; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#111214; --card:#1c1d20; --text:#f2f2f3; --muted:#9a9ca3; --line:#2c2d31; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
         font:15px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  header {{ position:sticky; top:0; z-index:5; background:var(--card); border-bottom:1px solid var(--line);
           padding:12px 16px; }}
  h1 {{ font-size:17px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .tools {{ display:flex; gap:12px; align-items:center; margin-top:8px; font-size:14px; flex-wrap:wrap; }}
  .tools label {{ display:flex; gap:6px; align-items:center; }}
  main {{ display:grid; gap:12px; padding:12px 16px 40px; grid-template-columns:minmax(0, 1fr);
         max-width:1100px; margin:0 auto; }}
  @media (min-width:640px) {{ main {{ grid-template-columns:repeat(2, minmax(0, 1fr)); }} }}
  @media (min-width:960px) {{ main {{ grid-template-columns:repeat(3, minmax(0, 1fr)); }} }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden;
          display:flex; flex-direction:column; min-width:0; }}
  .cover {{ position:relative; aspect-ratio:3/4; background:#000; max-height:420px; }}
  .cover img {{ width:100%; height:100%; object-fit:cover; display:block; }}
  .badge, .rank, .opened-tag {{ position:absolute; font-size:12px; font-weight:600; padding:3px 8px;
                                border-radius:999px; background:rgba(0,0,0,.65); color:#fff; }}
  .badge {{ top:8px; left:8px; }} .badge.ok {{ background:var(--ok); }} .badge.no {{ background:var(--no); }}
  .rank {{ top:8px; right:8px; }}
  .opened-tag {{ bottom:8px; left:8px; display:none; background:#444; }}
  .body {{ padding:10px 12px 12px; display:flex; flex-direction:column; gap:6px; flex:1; }}
  .creator {{ font-weight:600; }}
  .caption {{ color:var(--muted); font-size:13px; display:-webkit-box; -webkit-line-clamp:2;
             -webkit-box-orient:vertical; overflow:hidden; overflow-wrap:anywhere; }}
  .stats {{ font-size:13px; }}
  .prod {{ display:flex; gap:8px; align-items:center; border:1px solid var(--line); border-radius:8px; padding:6px; }}
  .prod img {{ width:48px; height:48px; object-fit:cover; border-radius:6px; flex:none; }}
  .pinfo {{ min-width:0; }}
  .pname {{ font-size:13px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
           overflow:hidden; overflow-wrap:anywhere; }}
  .pmeta {{ font-size:13px; color:var(--muted); }} .pmeta b {{ color:var(--brand); }}
  .actions {{ display:flex; gap:8px; margin-top:auto; padding-top:4px; }}
  .btn {{ flex:1; text-align:center; text-decoration:none; padding:11px 8px; border-radius:8px; font-weight:600;
         font-size:14px; border:1px solid var(--line); color:var(--text); }}
  .btn.primary {{ background:var(--brand); border-color:var(--brand); color:#fff; flex:2; }}
  .card.opened {{ opacity:.55; }}
  .card.opened .opened-tag {{ display:inline-block; }}
  body.hide-opened .card.opened {{ display:none; }}
  .empty {{ text-align:center; color:var(--muted); padding:40px 16px; }}
</style>
</head>
<body>
<header>
  <h1>{escape(title)}</h1>
  <div class="sub">{len(videos)} video · {duet} có duet · xuất lúc {now}</div>
  <div class="tools">
    <label><input type="checkbox" id="hide"> Ẩn video đã mở</label>
    <span class="sub" id="progress"></span>
    <a href="#" id="reset" class="sub">Xóa đánh dấu</a>
  </div>
</header>
<main>{cards or '<div class="empty">Không có video nào.</div>'}
</main>
<script>
  (function () {{
    var KEY = "sdc_opened";
    function load() {{ try {{ return JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ return {{}}; }} }}
    function save(o) {{ try {{ localStorage.setItem(KEY, JSON.stringify(o)); }} catch (e) {{}} }}
    var opened = load();
    var cards = document.querySelectorAll(".card");
    function refresh() {{
      var n = 0;
      cards.forEach(function (c) {{
        var on = !!opened[c.id];
        c.classList.toggle("opened", on);
        if (on) n++;
      }});
      document.getElementById("progress").textContent = "Đã mở " + n + "/" + cards.length;
    }}
    document.querySelectorAll("[data-open]").forEach(function (a) {{
      a.addEventListener("click", function () {{
        opened["v-" + a.getAttribute("data-open")] = 1; save(opened); refresh();
      }});
    }});
    var hide = document.getElementById("hide");
    hide.addEventListener("change", function () {{ document.body.classList.toggle("hide-opened", hide.checked); }});
    document.getElementById("reset").addEventListener("click", function (e) {{
      e.preventDefault(); opened = {{}}; save(opened); refresh();
    }});
    refresh();
  }})();
</script>
</body>
</html>
"""


def export_html(videos: list, export_dir: str = "results", prefix: str = "duet_list",
                title: str = "Video Shopee có Duet") -> str:
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(export_dir, f"{prefix}_{ts}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_html(videos, title))
    return path
