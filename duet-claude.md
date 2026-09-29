# SHOPEE DUET CHECKER — TÀI LIỆU KỸ THUẬT ĐÃ KIỂM CHỨNG

> Tổng hợp toàn bộ thuật toán, quy trình, endpoint và code cốt lõi của `shopee-duet-checker`, dựa trên các lần chạy thật với Shopee (VN) ngày **2026-09-23**.
> Tài liệu này **bổ sung và sửa** `duet.md`: phần nào trong `duet.md` là suy đoán thì được đánh dấu rõ ở mục 0.
> Không chứa cookie hay giá trị API key. Hai thứ này nằm trong `settings.json` trên máy.

---

## MỤC LỤC
0. [Những điểm sửa so với duet.md](#0-những-điểm-sửa-so-với-duetmd)
1. [Kiến trúc & cấu trúc thư mục](#1-kiến-trúc--cấu-trúc-thư-mục)
2. [Kết quả phân tích tool gốc](#2-kết-quả-phân-tích-tool-gốc)
3. [Xác thực: cookie + chữ ký request](#3-xác-thực-cookie--chữ-ký-request)
4. [Danh mục endpoint (đã / chưa dùng được)](#4-danh-mục-endpoint)
5. [Cấu trúc JSON của 1 video](#5-cấu-trúc-json-của-1-video)
6. [Thuật toán](#6-thuật-toán)
7. [Quy trình sử dụng](#7-quy-trình-sử-dụng)
8. [Cấu hình settings.json](#8-cấu-hình-settingsjson)
9. [Bảng lỗi & cách xử lý](#9-bảng-lỗi--cách-xử-lý)
10. [Chi phí credit](#10-chi-phí-credit)
11. [Hạn chế & hướng phát triển](#11-hạn-chế--hướng-phát-triển)
12. [Bảo mật](#12-bảo-mật)
13. [Nhật ký lỗi đã sửa](#13-nhật-ký-lỗi-đã-sửa)
14. [Phụ lục: code cốt lõi](#14-phụ-lục-code-cốt-lõi)

---

## 0. NHỮNG ĐIỂM SỬA SO VỚI duet.md

| duet.md ghi | Thực tế đã kiểm chứng |
|---|---|
| Gọi `timeline/me` với cookie là đủ | **Sai.** Nếu thiếu header chữ ký, Shopee trả `418` (anti-bot, error `90309999`). Mỗi request phải được ký qua Sign API (mục 3.2). |
| Tham số `userid=<id>` | **Sai.** Tham số đúng là `request_user_id=<id>`, kèm `need_total_count=0&need_product_v2=true`. |
| Danh sách video ở `data.videos`, phân trang ở `data.page_context` / `data.has_more` | **Sai.** Danh sách nằm ở `data.list`, phân trang nằm ở `data.page.page_context` và `data.page.has_more`. |
| Cờ duet ở `allow_duet` / `interaction_permission.allow_duet` | Cờ duet nằm ở **`allow_info.allow_duet`** (mục 5). |
| `search_hint` dùng để tìm shop theo tên | Chỉ trả về **gợi ý từ khóa**. Với username hay từ khóa đều không có `creator_info` / `shop_info`, dù có cookie. Muốn đổi username → ID thì dùng `shop/get_shop_base` (mục 4.4). |
| Cách 2 (feed For You) và Cách 3 (hashtag) là phương án có sẵn | Tool gốc **không có** 2 cách này. Qua file HAR bắt từ app: feed hashtag (GET) **chạy được**, còn feed Thịnh hành / For You (POST) **bị chặn 418** (mục 4). |
| Payload giải nén bằng ZSTD thông thường | Phải giải nén dạng streaming với `max_window_size = 2^31`, nếu không sẽ lỗi "Unknown frame descriptor" (mục 2.1). |

---

## 1. KIẾN TRÚC & CẤU TRÚC THƯ MỤC

```
shopee-duet-checker/
├── main.py                  # Entry point PyQt6
├── run.bat                  # Double-click: kiểm tra Python, tự cài thư viện, chạy app
├── requirements.txt         # PyQt6, requests, urllib3
├── settings.json            # Cấu hình người dùng (cookie, API key...) — KHÔNG chia sẻ
├── log.txt                  # Nhật ký hoạt động (ghi từ tab Scanner)
├── debug/                   # Response thô đầu tiên của mỗi lần quét (để đối chiếu cấu trúc)
├── results/                 # File export CSV / JSON
├── api/
│   ├── headers.py           # REGIONS (VN/PH/ID/TH/MY/SG), header app / web
│   └── shopee_api.py        # Ký request, resolve input, timeline, hashtag, parse video + sản phẩm
├── workers/
│   ├── scanner_worker.py    # QThread: quét creator/hashtag tuần tự (tab Scanner)
│   └── multi_scanner.py     # Quét Viral Finder song song nhiều luồng, mỗi luồng 1 cookie
├── ui/
│   ├── main_window.py       # Cửa sổ chính, tab Scanner + Cài đặt, log
│   ├── viral_tab.py         # Tab 🔥 Viral Finder
│   ├── result_table.py      # Bảng kết quả (cột cấu hình được, sort số, menu chuột phải, visible_videos())
│   ├── windows_tab.py       # 🪟 Tab đếm cửa sổ sản phẩm
│   ├── phone_dialog.py      # 📱 Phát trang danh sách qua Wi-Fi + mã QR
│   └── gsheet_action.py     # 📊 Nút xuất Google Sheet (dùng chung 2 tab)
├── utils/
│   ├── viral.py             # enrich() + filter_viral(): chấm điểm viral
│   ├── exporter.py          # Xuất CSV (UTF-8 BOM), JSON, TXT
│   ├── html_export.py       # Trang HTML danh sách video cho điện thoại
│   ├── windows_store.py     # Kho đếm cửa sổ SP (SQLite: bảng products/product_videos) + đọc link SP
│   ├── video_store.py       # Kho video đầy đủ theo quốc gia (SQLite: bảng videos)
│   └── gsheet.py            # Ghi Google Sheet bằng service account (gspread)
└── config/
    └── settings.py          # DEFAULTS + load/save settings.json
```

**Luồng dữ liệu:**
```
UI (Scanner / Viral Finder)
   └─► ScannerWorker (QThread)
         └─► ShopeeAPI
               ├─ resolve_short_link / get_userid_by_username   (không cần ký)
               ├─ get_all_videos (timeline)   ─┐
               └─ get_hashtag_videos           ├─► _paged_feed ─► _signed_get ─► get_signature (Sign API)
                                               ┘                               └─► sv.shopee.vn
         ◄── video dict (_parse_video + _main_product)
   ◄── signal video_found ─► enrich() ─► filter_viral() ─► ResultTable ─► export
```

---

## 2. KẾT QUẢ PHÂN TÍCH TOOL GỐC

### 2.1. Giải nén payload Nuitka
| Bước | Chi tiết |
|---|---|
| Vị trí payload | Resource `RCDATA` ID 27, offset file `0x26328` (156456), kích thước 24.628.184 byte |
| Header | 3 byte `KAY` (`4B 41 59`), theo sau là frame ZSTD (`28 B5 2F FD`) |
| Giải nén | `zstandard.ZstdDecompressor(max_window_size=2**31).decompressobj()`, đọc từng khối 64 KB → **86.227.139 byte** |
| Cấu trúc payload | Lặp lại: `tên file UTF-16LE` + `\0\0` + `u64 size` (little-endian) + `dữ liệu` |
| Kết quả | 56 file. `main.exe` = 17.103.872 byte (chương trình chính), cùng python312.dll, libcrypto/libssl, các module .pyd |

### 2.2. Logic tool gốc rút ra từ chuỗi hằng trong `main.exe`
- Module `GetVideos`: `resolve_input`, `fetchVideosByUserId`, `getVideosFromShop`, `get_x_sap_ri` (lấy chữ ký), `gen_request_id`.
- Timeline URL: `/api/v2/timeline/me?limit=48&page_context=` + `&request_user_id=` + `&need_total_count=0&need_product_v2=true`.
- Header timeline: `Accept-Encoding`, `Content-Type: application/json; charset=UTF-8`, `Cookie`, `Host`, `language: vi`, `User-Agent`, `X-SAP-Type: 1`, `cache-control: no-cache, no-store`, `client-request-id`.
- Tool **thay `shopee_app_version=\d+` trong cookie thành `shopee_app_version=33731`** trước khi gửi.
- Ký request: `POST https://credit.toolshopee.vn/api/sign`, body JSON `{url, body}`, header `X-API-Key`. Response `{code, data}`, trong đó `data` là các header chữ ký.
- search_hint gọi tới `shopee.vn` (không phải sv.) kèm `&version=2&scene=3` và header Chrome desktop.
- Các thông báo lỗi: "Cookie bị captcha! Vui lòng thay cookie mới.", "Cookie hết hạn hoặc bị chặn...".
- Module `KEY`: kiểm tra bản quyền bằng cách băm SHA-256 địa chỉ MAC rồi đối chiếu với một Google Sheet.

---

## 3. XÁC THỰC: COOKIE + CHỮ KÝ REQUEST

### 3.1. Cookie
- Lấy từ trình duyệt **đã đăng nhập** `shopee.vn`: F12 → Network → một request bất kỳ → `Cookie` trong Request Headers.
- Nếu Shopee trả captcha: mở shopee.vn bằng tài khoản đó, giải captcha, lướt vài trang, rồi copy cookie mới.
- **Nhiều cookie (xoay vòng):** ô Cookie trong Cài đặt nhận **mỗi dòng 1 cookie (1 tài khoản)**; dòng trống và dòng bắt đầu bằng `#` được bỏ qua (`parse_cookies`). Ô này tắt tự xuống dòng để mỗi cookie nằm trên 1 dòng, và có dòng đếm "🍪 N cookie".
  - Khi quét, app dùng cookie #1. Nếu một request bị lỗi **do cookie** (`is_login:false` → "hết hạn", có `captcha` → "captcha", HTTP 418 / `error` khi đã có API key → "bị chặn"), app đánh dấu cookie đó chết, **chuyển sang cookie còn sống kế tiếp và gửi lại đúng request đó** (`_signed_get` → `_signed_get_once` + `_rotate_cookie`).
  - Lỗi không phải do cookie (như `code=400002` hay lỗi mạng) thì **không** đổi cookie. Khi tất cả cookie đều chết, app báo "Tất cả N cookie đều lỗi…".
  - Log ghi từng lần đổi: `🍪 Cookie #1 lỗi (captcha) → chuyển sang cookie #2/3`. Cuối lượt quét có tổng kết: `🍪 Cookie lỗi trong lần quét này: #1 (captcha), #2 (hết hạn)`.
  - Mỗi lần gửi lại tốn thêm khoảng 1 credit (vì phải ký lại request).
  - ✅ Đã kiểm tra bằng phản hồi giả lập: A (captcha) → B (hết hạn) → C (tốt) → quét tiếp bình thường.
- **Bắt buộc:** thay `shopee_app_version` trong cookie cho khớp với `appver` của User-Agent. Nếu lệch (ví dụ cookie `29531`, UA `33731`), timeline trả `{"code":400002}`.
  ```python
  cookie = re.sub(r"shopee_app_version=\d+", "shopee_app_version=33731", cookie)
  ```

### 3.2. Sign API
| | |
|---|---|
| Ký | `POST {sign_api_url}` (mặc định `https://credit.toolshopee.vn/api/sign`) |
| Header | `Content-Type: application/json`, `X-API-Key: <key>` |
| Body | `{"url": "<URL đầy đủ sẽ gọi>", "body": "<chuỗi body, GET thì để ''>"}`. **`body` phải là chuỗi.** Truyền object sẽ bị trả `code:-1, msg:"JsonObject"` |
| Response | `{"code":0, "data":{ "x-sap-ri": "...(52)", "<8 hex>": "...(28)", "<8 hex>": "...(~550)", "<8 hex>": "...(28)" }, "time_ms":...}` |
| Dùng | Gộp toàn bộ `data` vào header của request gửi tới Shopee |
| Kiểm tra key | `GET {base}/api/me` + `X-API-Key` → `{"api_key","credits","is_active","username"}`. Key sai → `401 {"code":1,"msg":"Invalid API key"}` |
| Phạm vi | **Chỉ GET ký đúng.** Với POST (feed Thịnh hành / For You), Shopee vẫn trả 418 dù đã có chữ ký (đã thử thêm `x-csrftoken`) |

Tên của 3 header chữ ký (dạng 8 ký tự hex) **thay đổi sau mỗi lần ký**. Không hard-code tên, cứ gộp nguyên `data` vào header.

### 3.3. Header gửi tới sv.shopee.vn (`api/headers.py → timeline_headers`)
```python
{
  "Accept-Encoding": "gzip, deflate",
  "Content-Type": "application/json; charset=UTF-8",
  "Host": "sv.shopee.vn",                 # theo REGIONS[country]["video_domain"]
  "language": "vi",
  "User-Agent": "Android app Shopee appver=33731 app_type=1",
  "X-SAP-Type": "1",
  "cache-control": "no-cache, no-store",
  "Cookie": "<cookie đã thay app_version>",
  "client-request-id": "<uuid4>",
  # + các header chữ ký từ Sign API
}
```

---

## 4. DANH MỤC ENDPOINT

Nguồn: chuỗi hằng trong tool gốc, file HAR bắt từ app Shopee (appver 38132), và các lần gọi thật.
**Lưu ý:** trong HAR, app gọi qua `dem.shopee.com` / `patronus.idata.shopeemobile.com`, nhưng header `:authority` luôn là **`sv.shopee.vn`**. Tool gọi thẳng `sv.shopee.vn`.

| # | Endpoint | Ký? | Trạng thái | Dùng trong app |
|---|---|---|---|---|
| 4.1 | `GET /api/v2/timeline/me` | Có | ✅ | Quét video của 1 creator |
| 4.2 | `GET /api/v2/hashtag/post/list` | Có | ✅ | Feed hashtag (Viral Finder) |
| 4.3 | `GET /api/v2/timeline/single?post_id=` | Có | Có trong HAR, chưa thử | — |
| 4.4 | `GET shopee.vn/api/v4/shop/get_shop_base?username=` | Không | ✅ | Đổi username → ID |
| 4.5 | `GET shopee.vn/api/v4/search/search_hint` | Không | ⚠️ Chỉ trả gợi ý từ khóa | Không dùng để tìm creator |
| 4.6 | Link rút gọn `vn.shp.ee/xxx` | Không | ✅ | Đổi link → ID |
| 4.7 | `offer_link` `s.shopee.vn/xxx` | Không | ✅ | (Có thể đổi ra link sản phẩm) |
| 4.8 | `POST /api/v2/timeline/unify/friends` (tab Thịnh hành) | Có | ❌ 418 | — |
| 4.9 | `POST /api/v2/mix/unify/foryou` (For You) | Có | ❌ (cùng loại POST) | — |
| 4.10 | Link mở video trong app: `shopee.vn/universal-link?redir=…/share-video/<post_id>` | Không | ✅ Đã thử trên iPhone | Cột "Link video" |
| 4.11 | `POST /api/v2/timeline/unify/common` ("Video về sản phẩm", `data.page.total` = số cửa sổ) | Có | ❌ 418 | — |
| 4.12 | `GET shopee.vn/api/v4/pdp/get?item_id=&shop_id=` (`data.featured_videos`) | Có | ❌ 418 | — |

### 4.1. Timeline creator
```
GET https://sv.shopee.vn/api/v2/timeline/me?limit=48&page_context=<quote(ctx)>&request_user_id=<ID>&need_total_count=0&need_product_v2=true
```
- Response: `{code:0, data:{list:[...48], page:{has_more, page_context:'{"last_ptime":1787547186986}'}, post_user_same_with_shop_item_user}}`
- Thứ tự: mới nhất trước (video ghim có `is_pinned: true` đứng đầu).
- Đã quét thật: profile 564151869 → 1.457 video, 868 video có duet. Profile 957965727 → 2/48 video có duet.

### 4.2. Feed hashtag
```
GET https://sv.shopee.vn/api/v2/hashtag/post/list?hashtag_id=<ID>&hashtag_name=%23<tên>&limit=12[&page_context=<quote(ctx)>]&need_product_v2=true
```
- Response: `{data:{list:[...12], page:{has_more, total:12, page_context:'{"offset":12,"last_post_id":"2833527972087269"}'}}}`
- Mỗi item có cấu trúc **giống hệt** item timeline, nên dùng chung `_parse_video`. `profile_id` lấy từ `meta.user_id`.
- `hashtag_id` lấy từ `content.hashtags[]` của bất kỳ video nào; tên hashtag = `caption[start:start+length]`.

**Đổi tên hashtag → hashtag_id theo quốc gia (không cần ký, không tốn credit):**
```
GET {sv_host}/api/v2/hashtag/detail?hashtag_name=%23<tên>
→ data.hashtag.{hashtag_id, content, post_count, view_count}
```
- Chỉ cần **tên**, trả về `hashtag_id` đúng theo miền quốc gia (`sv.shopee.ph`, `sv.shopee.co.id`…) và `post_count` để xếp độ phổ biến. **hashtag_id khác nhau giữa các nước.**
- `ShopeeAPI.hashtag_id_by_name(name)` và `top_hashtags(names, top_n)` dùng endpoint này (bỏ trùng theo id, xếp theo post_count).
- **Tab Viral Finder tự nạp 10 hashtag phổ biến nhất của quốc gia đang chọn**: khi đổi quốc gia (`HashtagLoader` chạy nền), đổ vào ô Hashtag nguồn; kết quả lưu cache `hashtags_by_country` nên lần sau tức thì. Nút "🔄 Tải hashtag phổ biến" để tải lại. Kho tên ứng viên là `HASHTAG_POOL` trong `ui/viral_tab.py`.
- ✅ Đã kiểm chứng resolve cho VN/PH/ID/TH/MY/SG: mỗi nước ra top 10 riêng (VN: ShopeeVideo, LuotVuiMuaLien…; PH: fyp, shopeeph…; ID: RacunShopee…).

**Hashtag mặc định VN** (thu từ dữ liệu thật, định dạng `#tên | hashtag_id`):
```
#xuhuong | 3703041052169415997
#shoppeviral | 10690181938538577588
#koluytin | 12679141696368787294
#hangmoive | 15423165041123344691
#shoppevideo | 6990407457976101562
#shopeevideo | 11432692145916448940
#luotvuimualien | 14424821104542133142
#luotvuimoingay | 10615268217078616384
#shopeecreator | 13421368463034645024
```
Một số hashtag khác đã thấy: `#videohangthoitrang 13701932958680688829`, `#thoitranghottrend 1075060637146047645`, `#sandealcungkol 4886845933514239310`, `#hot 2825616498025315981`, `#sacdep 5092121070192849288`, `#shoppecreator 15672545009574792007`.

### 4.4. Username → ID profile (không cần ký, không tốn credit)
```
GET https://shopee.vn/api/v4/shop/get_shop_base?entry_point=ShopByPDP&need_cancel_rate=true&request_source=shop_home_page&username=<username>&version=1
→ {"error":0, "data":{"shopid":1601848268, "userid":1602789128, "name":"thumn933", ...}}
```
- **`data.userid` = ID profile video** (trùng với `meta.user_id` trong timeline). Không dùng `shopid`.
- Username không tồn tại → `{"error":1000000,"error_msg":"service_err"}`.
- Header: `web_headers()` (Chrome desktop + cookie).

### 4.5. search_hint
```
GET https://shopee.vn/api/v4/search/search_hint?search_type=3&keyword=<kw>&version=2&scene=3
```
Trả về `keywords[]` là các gợi ý từ khóa. Với username thì mảng rỗng, với từ khóa chủ đề cũng không có `creator_info` / `shop_info`, dù có cookie. Endpoint này **không dùng được** để tìm creator.

### 4.6. Link rút gọn profile / video
```
GET https://vn.shp.ee/r3kjewd?smtt=0.0.9   (allow_redirects=False)
→ 301 Location: https://shopee.vn/universal-link?redir=https%3A%2F%2Fsv.shopee.vn%2Fme%2F1677860631%3F...%26shareUserId%3D...
```
- Giải mã URL (`unquote` 2 lần), lấy ID từ `/me/<ID>` hoặc `/profile/<ID>`.
- `shareUserId` là **người chia sẻ link**, KHÔNG phải chủ profile. Ví dụ link `0jww2l6y` → profile 957965727, trong khi shareUserId = 993607333.
- Link hết hạn hoặc không hợp lệ → `307 → https://shopee.vn` (trang chủ).

### 4.7. offer_link (link affiliate của creator) → link sản phẩm
```
GET https://s.shopee.vn/4L9y1kdkkb (allow_redirects=False)
→ 301 https://shopee.vn/opaanlp/505944179/27640602184?__mobile__=1&credential_token=...
                              └─shop_id─┘└──item_id──┘
→ https://shopee.vn/product/505944179/27640602184
```
Trong app **không cần mở link**: `shop_id` / `item_id` có sẵn trong dữ liệu video (mục 5). Mở `offer_link` có thể bị ghi nhận là 1 click affiliate cho creator.

### 4.10. Link mở đúng video trong app Shopee (điện thoại)
Khi bấm "Chia sẻ" một video, app gọi `POST ug-api.sv.shopee.vn/api/v1/share/short_url_v2` để rút gọn link dài sau (lấy từ HAR):
```
https://shopee.vn/universal-link?redir=https://sv.shopee.vn/share-video/<post_id>?fromShareLink=share-marker
    &shareUserId=<người chia sẻ>&contentType=0&jumpType=share&pid=sv&c=share_web&share_obj=video&myVideo=false
```
Tool tự dựng link này từ `meta.post_id`, không cần gọi API và không tốn credit. Tool bỏ `shareUserId` và `c` (hai tham số ghi nhận người chia sẻ), và mã hóa `redir` một lần:
```python
video_url = f"{sv_host}/share-video/{post_id}?fromShareLink=share-marker&contentType=0&jumpType=share&pid=sv&share_obj=video&myVideo=false"
share_url = f"{base_host}/universal-link?redir={quote(video_url, safe='')}"
```
- `shopee.vn/universal-link` là link app (Android App Link / iOS Universal Link). Điện thoại đã cài Shopee sẽ mở thẳng video trong app.
- Trên PC, link mở web Shopee (sv.shopee.vn chỉ là trang vỏ, không xem được video).
- ✅ **Đã kiểm chứng 2026-09-23:** gửi link qua Zalo, bấm trên iPhone thì mở đúng video trong app Shopee (tab "Cho bạn"), hiện đủ sản phẩm gắn kèm và nút Chia sẻ / Duet.

### 4.8–4.9. Feed Thịnh hành / For You (POST, chưa dùng được)
Body của tab Thịnh hành, lấy từ HAR (referer `trending_page`):
```json
{"limit":6,"page_context":null,"device_id":"<base64>","rec_request_info":"{\"dayPages\":1,\"sessionPages\":1,\"interactDataFromVideo\":[],\"interactDataFromCard\":[],\"sessionCards\":0}",
 "page_no":1,"request_type":0,"ext_info":[{"key":"ads_entrance","value":"29"}],"lang":"vi","scene":1,"support_multi_type":1,"need_product_v2":true,"ug_param":"{\"is_merge_reward\":1}"}
```
- Response: `data.list[]` gồm `{biz_id, biz_type, biz_data, recommendation}`. `biz_type=1` là video (`biz_data` có cấu trúc như item timeline), `biz_type=2` là livestream.
- Dữ liệu trong HAR có video 0,9–2,4 triệu view, và một video For You **17,6 triệu view có bật duet**. Đây là nguồn viral tốt nhất, nhưng **đã ký mà vẫn 418**. App thật còn gửi thêm `af-ac-enc-sz-token`, `requestinfo-enc`, `client-info`, `sfid`, `did`… mà Sign API không tạo ra.

---

## 5. CẤU TRÚC JSON CỦA 1 VIDEO

| Trường app (`_parse_video`) | Đường dẫn JSON | Ghi chú |
|---|---|---|
| `profile_id` | tham số truyền vào, hoặc `meta.user_id` | |
| `username` / `display_name` | `meta.user_name` / `meta.shopee_nick_name` | |
| `post_id` | `meta.post_id` | Base64, vd `z8SF9-wuCACfZRk5AAAAAA==` |
| `video_id` | `content.video.video_id` | vd `vn-11110124-6v8h6-memcyd14hloi41` |
| **`allow_duet`** | **`allow_info.allow_duet`** | |
| `allow_stitch` | `allow_info.allow_stitch` | |
| `play_count` | `meta.count_info.views` | |
| `like_count` | `meta.count_info.likes` | |
| `comment_count` | `meta.count_info.comments` | |
| `share_count` | `meta.count_info.shares` | Thường không có |
| `create_time` | `meta.ctime` (ms, nên ÷1000) | dự phòng `meta.ptime` |
| `description` | `content.caption` | |
| `video_url` | `content.video.url` | Link mp4 (`down-*-vn.vod.susercontent.com`) |
| `thumbnail` | `content.video.cover` | Mã ảnh |
| `hashtags` | `content.hashtags[] {hashtag_id, start, length, is_official}` | Tên = `caption[start:start+length]` |
| `related_ids` | `content.mentions[].user_id`, `content.music.author_id`, `content.products.enhanced_item_list[].shop_user_id` | Dùng để quét lan |
| `share_url` | tự dựng từ `meta.post_id` (mục 4.10) | Link mở đúng video trong app. Nếu không có `post_id` thì dùng link profile |

**Sản phẩm gắn trong video** (`_main_product`). Theo dữ liệu thật, khoảng 80–100% video có gắn:

| Trường app | Nguồn | Ghi chú |
|---|---|---|
| `product_name` | `enhanced_item_list[i].name` | ưu tiên item trùng `anchor_product.item_id` (sản phẩm ghim) |
| `product_url` | tự dựng `{base_host}/product/{shop_id}/{item_id}` | Link sản phẩm gốc, không phải affiliate |
| `product_price` | `price ÷ 100000` | Shopee lưu giá nhân 100.000 (`23208000000` → 232.080đ) |
| `product_sold` | `historical_sold` (dự phòng `sold`) | |
| `product_count` | `content.products.count` | Số sản phẩm gắn trong video |
| (dự phòng) | `content.product_v2 {item_id, shop_id, item_name, item_price.price, sell_stat.historical_sold}` | |

Các trường khác có trong `enhanced_item_list`: `price_before_discount`, `discount`, `rating_star`, `review_num`, `shop_location`, `stock`, `voucher_list`, `offer_link` (link affiliate của creator, có khi chỉ là `true`), `is_official_shop`, `is_preferred_plus_seller`.

---

## 6. THUẬT TOÁN

### 6.1. Đổi input → ID profile (`resolve_short_link`)
```
1. Chuỗi toàn số                          → trả luôn
2. Có /profile|me|creator|user/<số>        → lấy số
3. Có ?request_user_id|userid|user_id=<số> → lấy số   (KHÔNG dùng shareUserId)
4. Là URL: đi theo redirect thủ công (tối đa 5 bước, UA app),
   unquote(unquote(Location)) rồi tìm /me|profile/<số>
5. URL dạng shopee.vn/<username>           → get_shop_base
6. Username thuần [A-Za-z0-9._]{3,40}      → get_shop_base → data.userid
7. Không ra                                → "" (worker báo "Không tìm thấy shop")
```
**Không bao giờ** tìm `userid` trong HTML. Trang shopee.vn luôn chứa hằng số `1448992801`, nên mọi input sẽ ra cùng một ID sai.

### 6.2. Request có ký + phân trang (`_signed_get`, `_paged_feed`)
```
lặp:
  url  = make_url(page_context)
  hdr  = timeline_headers(cookie đã thay app_version) + client-request-id + get_signature(url)
  request_count += 1                      # ≈ credit
  resp = GET url
  kiểm tra lỗi theo thứ tự: is_login==False → captcha → HTTP≠200 / error → code≠0
  parse data.list → video dict
  dừng nếu đủ max_videos / has_more=false / page_context rỗng / list rỗng / stop_flag
  sleep(delay_ms)
```

### 6.3. Chấm điểm viral (`utils/viral.py`)
```
age_days      = max((now - create_time) / 86400, 0.5)     # tránh chia cho số quá nhỏ
views_per_day = play_count / age_days                      # "tốc độ viral"
engagement %  = (likes + comments + shares) * 100 / views
duet_score    = int( sqrt(views_per_day * (product_sold + 1)) )   # "đáng làm duet"
post_date     = YYYY-MM-DD
```
- **duet_score** là trung bình nhân của tốc độ view và sức bán → cần **cả hai** đều cao. Video nhiều view nhưng sản phẩm bán yếu (hoặc không gắn SP) sẽ bị điểm thấp. Đây là cột dùng để lọc "video đáng làm duet".
- Lọc (`filter_viral`): chỉ lấy video có duet (tùy chọn), `views ≥ min`, `likes ≥ min`, `views_per_day ≥ min`, **`product_sold ≥ min_sold`**, `age_days ≤ N` (0 = mọi lúc). Sắp xếp giảm dần theo **`sort_by`** (`duet_score` mặc định, hoặc `views_per_day`) rồi `play_count`, cắt Top N. Lọc chạy lại ngay khi đổi tiêu chí, không cần quét lại.
- UI Viral Finder có thêm ô **"Đã bán ≥"** và ô chọn **"Xếp theo: Điểm duet / View/ngày"**; bảng có cột **Điểm duet**.
- Ô **"🎯 Mục tiêu"** ở đầu phần tiêu chí (`viral_mode`):
  - **🎬 Video viral CÓ Duet** (`duet`): bật "Chỉ video CÓ duet", xếp theo Điểm duet.
  - **👁 Video viral theo View** (`view`): hiện mọi video (có hoặc không duet), xếp theo View/ngày.
  - Đổi mục tiêu chỉ đặt lại 2 ô trên rồi lọc lại ngay, không cần quét lại; các ngưỡng số (Lượt xem, View/ngày, Đã bán…) giữ nguyên. Vẫn chỉnh tay từng ô được sau đó. Tiêu đề bảng đổi theo mục tiêu.

### 6.4. Quét lan tự động có ngân sách (`workers/scanner_worker.py`)
```
seed_creators  = danh sách người dùng nhập
seed_tags      = danh sách (hashtag_id, #tên)
creator_score  = {}   # id → tổng (views+1) của các video chứa id đó
tag_score      = {}   # hashtag_id → tổng (views+1)

while chưa dừng:
    if request_count ≥ budget: dừng
    task = seed_creators.pop(0)  nếu còn
         | seed_tags.pop(0)      nếu còn
         | nguồn có điểm cao nhất (creator hoặc hashtag) chưa quét   ← khi bật quét lan
         | hết → dừng
    creator → get_all_videos(id, max_videos = N video mới nhất)
    hashtag → get_hashtag_videos(id, name, max_videos = M)
    với mỗi video:
        cộng điểm cho: chủ video, related_ids (tag / nhạc / shop sản phẩm), hashtags
        bỏ qua nếu video_id đã thấy (tránh trùng giữa hashtag và timeline)
        phát video → UI enrich + lọc viral
```
- Ưu tiên theo **tổng view** giúp đi theo hướng có video viral.
- `stop_flag` của từng lần quét cũng kiểm tra ngân sách, nên không vượt budget quá 1 request.
- **Quét song song nhiều luồng** (`workers/multi_scanner.py`, `MultiScanWorker`): ô "Chạy song song" trong Viral Finder (`viral_threads`). Mỗi luồng dùng 1 cookie khác nhau, cùng lấy việc từ hàng đợi chung dưới 1 khóa (`threading.Lock`/`Condition`), dedup video và điểm lan dùng chung, ngân sách credit dùng chung. Kết thúc khi hết ngân sách hoặc mọi luồng rảnh và không còn nguồn để lan.
  - **Nhanh hơn theo thời gian thực, KHÔNG giảm credit** (vẫn đúng số request). Số luồng giới hạn ≤ số cookie.
  - ✅ Đã kiểm chứng (đồ thị giả lập): 8 luồng nhanh **x5.7** so với 1 luồng, cùng tập video, cùng số credit, không quét trùng creator; dừng giữa chừng kết thúc sạch.
- Kết quả thật: 8 credit, 9 hashtag mặc định, không có creator nguồn → 59 video, 13 video có duet (23–155 nghìn view). Riêng 5 hashtag đầu đã mở ra 75 creator và 110 hashtag mới.
- Quét lan chỉ theo creator (nguồn là shop của sản phẩm gắn) cho kết quả kém hơn: 4 creator → 167 video, 7 có duet. Nguyên nhân là shop bán hàng thường tắt duet.

---

## 7. QUY TRÌNH SỬ DỤNG

### 7.1. Cài đặt lần đầu
1. Double-click `run.bat`. File này kiểm tra Python, tự `pip install -r requirements.txt` nếu thiếu, rồi chạy `main.py`.
2. Mở tab **⚙️ Cài đặt**, chọn quốc gia, dán Cookie, nhập API Key → bấm **Kiểm tra key** (hiện số credit) → **💾 Lưu cài đặt**.

### 7.2. Tab 🔍 Scanner: quét shop/creator cụ thể
- Mỗi dòng 1 nguồn: link profile `sv.shopee.vn/profile/<ID>` hoặc `/me/<ID>`, link rút gọn `vn.shp.ee/...`, ID, link shop `shopee.vn/<username>` hoặc username.
- **Không nhập từ khóa chủ đề** (ví dụ "review gia dụng"), vì không đổi được ra shop.
- Bấm **▶ Bắt đầu Scan**, rồi có thể tick "Chỉ hiện video CÓ duet", bấm tiêu đề cột để sắp xếp, xuất CSV/JSON, hoặc copy URL.
- Log ghi song song vào `log.txt` (nút "Mở log.txt").

### 7.3. Tab 🔥 Viral Finder: tự tìm video viral có duet
1. **Hashtag nguồn:** có sẵn 9 hashtag. Thêm theo dạng `#tên | hashtag_id` (lấy ID từ JSON trong `debug/` hoặc CSV).
2. **KOC/Shop nguồn:** tùy chọn.
3. **Quét lan:** bật "Lan theo hashtag" và/hoặc "Lan theo creator/shop liên quan".
4. **Ngân sách:** 50–100 credit mỗi lần là hợp lý. Mỗi hashtag quét 12–24 video; mỗi creator quét 48 video mới nhất.
5. **Tiêu chí viral nên dùng:** "Đăng trong: Mọi lúc" (hoặc 180 ngày), View/ngày ≥ 20–50, Lượt xem ≥ 10.000, "Chỉ video CÓ duet". Video có duet và nhiều view thường **không phải video mới trong tuần**, nên giữ mặc định 7 ngày sẽ ra rất ít kết quả.
6. Xem bảng (xếp theo View/ngày) → **💾 Export CSV**, **📊 Google Sheet**, **📋 Copy link viral** hoặc **📱 Điện thoại**.
7. Bảng **cập nhật ngay trong lúc quét**: video đạt tiêu chí hiện dần (gom khoảng 0,4 giây một lần vẽ). Bảng giữ nguyên vị trí cuộn, và giữ cách sắp xếp nếu bạn đã bấm tiêu đề cột.
8. Nếu "Viral: 0" dù đã quét nhiều video, dòng thống kê hiện màu đỏ, nói lý do và ngưỡng thực tế cao nhất (ví dụ "cao nhất chỉ 190 view/ngày"). Hạ tiêu chí thì bảng lọc lại ngay, không cần quét lại. Khi bảng rỗng, các nút xuất sẽ hỏi có muốn xuất **video có duet** hoặc **tất cả video đã quét** không.

### 7.4. Mở video đã quét bằng app Shopee trên điện thoại
1. Trong bảng kết quả: **📋 Copy URL duet** (Scanner), **📋 Copy link viral** (Viral Finder), hoặc chuột phải → **Copy link**.
2. Gửi danh sách link sang điện thoại (Zalo "Cloud của tôi", Messenger, Telegram Saved Messages, email…).
3. Trên điện thoại, bấm từng link. Máy đã cài Shopee sẽ mở thẳng video trong app, rồi dùng nút Duet của app.
4. Nếu link mở trong trình duyệt nhúng của Zalo/Messenger: chọn "Mở bằng trình duyệt" / "Open in Chrome/Safari" để hệ điều hành chuyển sang app Shopee.
5. Link chỉ đúng với dữ liệu quét **sau** bản sửa này. Kết quả cũ (CSV/JSON trước đó) vẫn là link profile.

### 7.5. 📱 Trang danh sách trên điện thoại (Wi-Fi + QR)
- Nút **📱 Điện thoại** (ở cả 2 tab) lấy **các dòng đang hiện trong bảng**, theo đúng thứ tự sắp xếp và bộ lọc hiện tại.
- App xuất `results/<scanner|viral>_list_<thời gian>.html` và phát trang đó qua `http://<IP máy tính>:8765/`, rồi hiện mã QR.
- Điện thoại **cùng mạng Wi-Fi** quét QR → trang mở trong Safari/Chrome → bấm **▶ Mở trong app Shopee** → app mở đúng video.
- Mỗi thẻ gồm ảnh bìa, huy hiệu Duet, hạng #, creator, caption, 👁 view · 🔥 view/ngày · ❤ like · 📅 ngày đăng, sản phẩm (ảnh, tên, giá, đã bán), nút "Sản phẩm".
- Trang nhớ video đã mở (`localStorage`): hiện "Đã mở x/y", có ô "Ẩn video đã mở" và nút "Xóa đánh dấu".
- **Máy chủ chỉ trả đúng trang `/`**; mọi đường dẫn khác 404, nên không lộ `settings.json`, CSV hay JSON ra mạng nội bộ. Máy chủ dừng khi đóng hộp thoại.
- Lần đầu chạy, Windows có thể hỏi tường lửa cho `python`/`pythonw`: chọn Cho phép (mạng Riêng tư).
- Toàn bộ caption và tên sản phẩm đều được escape HTML. Đã kiểm tra với `<script>`.
- Gửi file HTML qua Zalo thì trên iPhone thường không bấm được link, vì vậy mới dùng cách Wi-Fi + QR.
- Ảnh: bìa video `https://down-bs-vn.img.susercontent.com/<cover>@resize_ss480x640!@crop_w480_h640_cT`, sản phẩm `https://down-vn.img.susercontent.com/file/<image>`.

### 7.6. 📊 Xuất Google Sheet (service account)
- Nút **📊 Google Sheet** (ở cả 2 tab) **ghi tiếp** các dòng đang hiện vào **một tab cố định**, và **lọc trùng theo Video ID** trước khi ghi:
  - Tab: ô "Tab ghi dữ liệu" trong Cài đặt. Để trống thì dùng **mã quốc gia đang chọn** (`VN`, `PH`…). Nếu tab chưa có, app tự tạo.
  - Tab trống thì app ghi dòng tiêu đề (in đậm, cố định). Tab đã có dòng 1 khác `HEADERS` thì **báo lỗi, không ghi**, để tránh ghi đè dữ liệu khác.
  - App đọc cột C (Video ID) đang có, bỏ các video đã có và video lặp trong chính lần xuất, rồi `append_rows` phần còn lại.
  - Thông báo kết quả: "Ghi thêm X video mới, bỏ qua Y video trùng. Tổng trong tab: Z". Dòng này cũng được ghi vào log.
  - Scanner và Viral dùng chung tab, nên Google Sheet là **danh sách tổng không trùng**.
  - ✅ Đã kiểm chứng: ghi 5 → ghi lại 5 cũ + 3 mới (thêm 3, bỏ 5) → lô có lặp (thêm 2, bỏ 1) → 10 dòng, không trùng. Tab có cột khác bị từ chối.
- Cấu hình (tab Cài đặt → Google Sheet):
  - **File JSON:** service account (mặc định `F:\MMO\GemPhoneFarm.json`). App hiện **email service account** kèm nút Copy.
  - **Link Google Sheet:** mặc định `https://docs.google.com/spreadsheets/d/1P3WvAU8Dlwvqebvpp2g0J610Su0TsCCjCAecLJ4zM-Y` (sheet "ShopeeDuet"). Nhận cả link lẫn ID.
  - Sheet phải được **chia sẻ cho email service account với quyền Người chỉnh sửa**, và project Google Cloud phải bật **Google Sheets API**.
  - Service account không có dung lượng Drive, nên **không tự tạo file sheet**. Phải dùng sheet có sẵn do bạn tạo.
- Cột: Profile ID, Creator, Video ID, Duet, Lượt xem, View/ngày, Lượt thích, Bình luận, Ngày đăng, Mô tả, Tên SP, Giá (đ), Đã bán, **Link video** (`=HYPERLINK(…,"▶ Mở video")`), **Link SP** (`=HYPERLINK(…,"🛒 Sản phẩm")`).
- Ghi bằng `USER_ENTERED`, nên số giữ kiểu số. **Link video / Link SP là URL đầy đủ dạng chữ** (không phải công thức HYPERLINK): Sheets tự tạo link bấm được, đồng thời đọc và copy được cả đường dẫn. Ô văn bản bắt đầu bằng `= + - @` được thêm `'` phía trước để **chặn chèn công thức**.
- Dòng tiêu đề in đậm, tô màu và được cố định (freeze).
- ✅ Đã kiểm chứng 2026-09-24: ping sheet "ShopeeDuet" thành công; ghi thử 5 dòng vào tab test, đọc lại đúng (công thức, kiểu số, freeze, chặn `=1+1`), rồi xóa tab test.
- Lỗi thường gặp được app diễn giải: chưa chia sẻ sheet cho email service account; chưa bật Sheets API; sai link; file không phải service account.

### 7.7. 🪟 Tab "Cửa sổ SP": đếm số video affiliate gắn sản phẩm
- **Số cửa sổ chính xác** nằm ở `POST /api/v2/timeline/unify/common` (body có `ext_info` = `shop_id`, `item_id`, `from_pdp_top`; `rcmd_source:11`; `strategy_id:"126"`; referer `pdp_buyer_show_landing_page`), trường `data.page.total`. Theo HAR, ổ cứng `141872172/14227187261` có `total = 2`. Tuy nhiên endpoint này và `pdp/get` đều **bị 418** vì Sign API không ký được (mục 4.11–4.12).
- **Cách đang dùng (phương án 2): đếm từ video đã quét.**
  - Mỗi video quét được ở Scanner hoặc Viral đều được ghi vào kho `data/product_windows.json`, dạng `item_id → {shop_id, name, videos: [post_id…]}`. Kho **cộng dồn qua mọi lần chạy** và không đếm trùng video.
  - Tính **mọi sản phẩm** gắn trong video (`_all_products`): `enhanced_item_list` (có tên, chỉ SP chính) + `items` + `item_list` (đủ mọi SP, không tên) + `anchor_product` + `product_v2`. SP phụ chưa có tên sẽ tự điền khi gặp nó làm SP chính ở video khác.
  - Số cửa sổ = số video trong kho gắn SP đó, tức là **số tối thiểu**; quét càng nhiều càng sát.
- **Giao diện:** ô dán link (`/product/<shop>/<item>`, `…-i.<shop>.<item>`, `/opaanlp/…`, `s.shopee.vn/…`) → 🔢 Đếm cửa sổ. Để trống thì hiện mọi sản phẩm đã gặp, xếp theo số cửa sổ giảm dần. Bảng có 3 cột **Tên SP | Link SP | Số cửa sổ**, nhấp đúp để mở sản phẩm. Có 💾 Export CSV (`cua_so_sp_<thời gian>.csv`) và 🗑 Xóa dữ liệu đếm.
- Nếu sau này Sign API ký được request POST ở trên, chỉ cần thay nguồn đếm bằng `data.page.total` (1 credit mỗi sản phẩm).

### 7.75. Kho video (SQLite — lưu để dùng lại, tiết kiệm credit)
- **Dùng SQLite `data/shopee_duet.db`** (không phải JSON) để không phải ghi lại cả file mỗi lần lưu và không phình to; `sqlite3` có sẵn trong Python, không cần cài thêm. WAL mode, ghi từng dòng, upsert theo khóa.
- Bảng: `videos(country, video_id, data JSON, updated)` (khóa `(country, video_id)`, index theo `country`); `products(item_id, shop_id, name)` + `product_videos(item_id, video_id)` cho tab Cửa sổ SP. `VideoStore` và `WindowsStore` dùng chung file DB.
- **Tự nhập một lần** từ file cũ `videos_<CC>.json` / `product_windows.json` nếu có, rồi đổi tên thành `.imported`.
- Mọi video quét được (Scanner + Viral Finder) lưu đầy đủ theo từng quốc gia, khóa theo `video_id` nên **không trùng**; quét lại thì cập nhật (`INSERT OR REPLACE`). Ghi được gom vào bộ đệm, flush 1 lần khi `save()` (lúc quét xong / đóng app).
- **Mở app / đổi quốc gia:** Viral Finder tự đổ video đã lưu của nước đó vào bảng ngay, **không tốn credit** (`_load_country_cache`). Dòng thống kê ghi "Kho: N video".
- **Quét mới không xóa kho:** kết quả quét gộp/cập nhật vào kho hiện có (trước đây bấm Quét là xóa sạch danh sách). Nhờ vậy các lần quét cộng dồn dần thành kho lớn.
- Kho lưu khi quét xong và khi đóng app. `VideoStore.clear(country)` để xóa nếu cần.
- Nguồn dữ liệu chuẩn trong tab là `_videos_by_id` (dedup theo video_id); `_refresh` dựng lại `_videos` từ đó rồi lọc.
- Lưu ý: kho là số liệu tại thời điểm quét; muốn cập nhật view/lượt bán mới thì quét lại (sẽ ghi đè theo video_id).

### 7.8. Cột kết quả
- **Scanner:** Profile ID, Video ID, Duet, Stitch, Lượt xem, Lượt thích, Bình luận, Mô tả, **Tên SP, Link SP, Giá (đ), Đã bán**, Link video.
- **Viral:** Profile ID, Video ID, Duet, View/ngày, Lượt xem, Lượt thích, Tương tác %, Ngày đăng, Mô tả, **Tên SP, Link SP, Giá (đ), Đã bán**, Link video.
- Các cột số sắp xếp theo giá trị số. Menu chuột phải có: mở/copy link video, copy Video ID, **mở/copy link sản phẩm**, copy tất cả link duet.
- CSV (UTF-8 BOM, mở tốt bằng Excel): thêm `views_per_day, engagement, post_date, product_name, product_url, product_price, product_sold, product_count, video_url`.

---

## 8. CẤU HÌNH settings.json

| Khóa | Mặc định | Ý nghĩa |
|---|---|---|
| `country` | `VN` | Thị trường đang chọn: VN / PH / ID / TH / MY / SG (xem `REGIONS` trong `api/headers.py`). Ô chọn có ở cả 3 tab Scanner, Viral Finder, Cài đặt — đổi ở đâu cũng đồng bộ 3 nơi |
| `cookie` | | Cookie của quốc gia đang chọn (giữ cho tương thích cũ). **Mỗi dòng 1 tài khoản**, tự xoay vòng khi cookie lỗi |
| `cookies_by_country` | `{}` | Cookie **riêng theo từng quốc gia**: `{"VN": "...", "PH": "..."}`. Đổi quốc gia thì ô Cookie nạp đúng cookie nước đó |
| `sign_api_url` | `https://credit.toolshopee.vn/api/sign` | |
| `sign_api_key` | | API key ký request |
| `delay_ms` | 500 | Nghỉ giữa các trang |
| `max_videos_per_shop` | 0 | Giới hạn video/shop ở tab Scanner (0 = không giới hạn) |
| `filter_duet_only` | false | Checkbox ở tab Scanner |
| `export_path` | `results` | Thư mục export |
| `viral_seeds` | | Creator nguồn |
| `viral_hashtags` | (rỗng → dùng DEFAULT_HASHTAGS) | `#tên \| id` mỗi dòng |
| `viral_crawl` / `viral_crawl_hashtags` | true / true | Lan theo creator / hashtag |
| `viral_credit_budget` | 50 | Ngân sách credit |
| `viral_videos_per_hashtag` | 24 | |
| `viral_videos_per_creator` | 48 | |
| `viral_max_age_days` | 0 | 0 = mọi lúc (khuyến nghị) |
| `viral_min_views` / `viral_min_likes` / `viral_min_vpd` | 10000 / 0 / 20 | Video có duet thực tế chỉ đạt khoảng 30–190 view/ngày; ngưỡng 1000 sẽ lọc hết |
| `viral_duet_only` / `viral_top_n` | true / 100 | |
| `gsheet_credentials` | `F:\MMO\GemPhoneFarm.json` | File JSON service account |
| `gsheet_sheet` | link sheet "ShopeeDuet" | Link hoặc ID Google Sheet |
| `gsheet_tab` | (trống) | Tab ghi tiếp dữ liệu. Để trống thì dùng mã quốc gia |

---

## 9. BẢNG LỖI & CÁCH XỬ LÝ

| Hiện tượng | Response | Nguyên nhân | Xử lý |
|---|---|---|---|
| 418 kèm captcha | `{is_login:true, challenge_type:1, captcha:{...}, error:90309999}` | Cookie bị gắn cờ | Giải captcha trên trình duyệt, lấy cookie mới |
| 418 dạng số | `{"0":2,"2":true,...,"error":90309999}` | Thiếu hoặc sai chữ ký (hoặc request POST) | Kiểm tra API key; chỉ dùng endpoint GET |
| `is_login: false` | | Cookie hết hạn | Lấy cookie mới |
| `{"code":400002}` | HTTP 200 | `shopee_app_version` trong cookie lệch UA, hoặc ID sai | Đã tự thay app version; kiểm tra lại ID |
| 0 video, không lỗi | | (lỗi cũ) đọc sai `data.list` / `data.page` | Đã sửa |
| Nhiều link ra cùng một ID | `1448992801` | (lỗi cũ) nhặt userid từ HTML trang chủ | Đã bỏ cách đọc HTML |
| Link rút gọn không ra ID | `307 → https://shopee.vn` | Link hết hạn hoặc không phải link profile | Lấy lại link từ nút Chia sẻ, hoặc dùng ID |
| Username không ra ID | `{"error":1000000,"error_msg":"service_err"}` | Sai username / tài khoản không còn | Kiểm tra lại |
| Sign API `Invalid API key` | `401 {"code":1}` | Key sai / hết hạn | Liên hệ bên cấp key |
| Sign API `JsonObject` | `{"code":-1}` | Gửi `body` dạng object | `body` phải là chuỗi |
| Viral Finder báo "Thiếu nguồn" dù có hashtag | | (lỗi cũ) dòng `#...` bị coi là comment | Đã sửa `_parse_tags` |

---

## 10. CHI PHÍ CREDIT

- **≈ 1 credit cho mỗi request được ký** (`request_count`, hiện trong log "Đã dùng ≈ N credit"). Đây là ước tính theo số lần gọi Sign API.
- 1 trang timeline = 48 video. 1 trang hashtag = 12 video.
- Quét toàn bộ 1 creator có 1.457 video ≈ 31 credit. Viral Finder 50 credit ≈ 50 trang.
- **Không tốn credit:** đổi username (`get_shop_base`), đổi link rút gọn, search_hint, `/api/me`, lọc/sắp xếp/xuất trong app.

---

## 11. HẠN CHẾ & HƯỚNG PHÁT TRIỂN

1. **Feed Thịnh hành / For You (POST) bị 418.** Đây là nguồn viral tốt nhất. Muốn dùng cần Sign API hỗ trợ ký POST, hoặc tái tạo đủ các header thiết bị của app (`af-ac-enc-sz-token`, `requestinfo-enc`, `sfid`, `did`...).
2. **Feed hashtag xếp theo video mới đăng**, nên nhiều video mới 0 view. Hiệu quả tới từ việc lan sang creator có video viral.
3. **Chưa có endpoint đổi tên hashtag → hashtag_id.** Hiện chỉ lấy ID từ video đã quét hoặc từ HAR.
4. ~~Không có link cho từng video~~ → Đã giải quyết: dựng link `universal-link` từ `post_id` (mục 4.10), đã thử trên iPhone. Có thể thêm mã QR cho từng video để quét bằng điện thoại.
5. `timeline/single?post_id=` (có trong HAR) có thể dùng để làm mới lượt xem của một video cụ thể. Chưa thử.
6. Có thể thêm: đổi `offer_link` → link sản phẩm cho link dán vào tay; lọc theo `product_sold` / giá; tự thu `hashtag_id` từ kết quả vào danh sách nguồn.

---

## 12. BẢO MẬT

- **Không chia sẻ:** `settings.json` (cookie + API key), `log.txt`, thư mục `debug/`, file HAR (chứa cookie, token đăng nhập, `x-csrftoken`, device id), **file JSON service account** (chứa private key: ai có file này đều ghi được vào mọi sheet đã chia sẻ cho email đó).
- Thư viện: `requirements.txt` gồm PyQt6, requests, urllib3, **qrcode**, **gspread**. `run.bat` tự cài nếu thiếu.
- Hiện có **API key được ghi cứng** trong `api/shopee_api.py` (`DEFAULT_SIGN_API_KEY`) và `config/settings.py` (`DEFAULTS["sign_api_key"]`). Nên xóa trước khi chia sẻ hay đưa mã nguồn lên Git.
- Tài liệu này không chứa cookie hay giá trị key.

---

## 13. NHẬT KÝ LỖI ĐÃ SỬA

| # | Lỗi | Sửa |
|---|---|---|
| 1 | `_parse_video` crash khi field `null`, làm chết worker và UI kẹt | Dùng `(v.get(x) or {})`; worker bắt exception, luôn emit `all_done` |
| 2 | Sắp xếp Lượt xem theo chuỗi (`9,000 > 500 > 125,000`) | `NumericItem.__lt__` so theo `UserRole` |
| 3 | Menu chuột phải lấy sai video sau khi sort | Lưu dict video vào `UserRole+1` của ô cột 0 |
| 4 | Insert dòng khi đang sort làm lệch cột | Tắt sort khi fill dòng |
| 5 | Lỗi API bị nuốt, báo "0 video" | `last_error` + log rõ từng loại lỗi |
| 6 | Cookie/delay chưa bấm Lưu thì không có tác dụng | `_runtime()` đọc trực tiếp giá trị trên UI |
| 7 | Tham số `userid`, thiếu chữ ký, sai header | Làm lại theo tool gốc (`request_user_id`, Sign API, `X-SAP-Type`...) |
| 8 | `400002` | Thay `shopee_app_version` trong cookie thành 33731 |
| 9 | Đọc sai `data.list` / `data.page`, sai field video | Làm lại theo JSON thật |
| 10 | Link rút gọn → cùng ID `1448992801` | Theo redirect + unquote, bỏ đọc HTML, bỏ `shareUserId` |
| 11 | Username không ra ID | Dùng `shop/get_shop_base` |
| 12 | Hashtag nguồn bị lọc mất (coi `#` là comment) | `_parse_tags` không dùng `_lines` |

---

## 14. PHỤ LỤC: CODE CỐT LÕI

Code đầy đủ nằm trong repo. Dưới đây là các đoạn quan trọng nhất (bản rút gọn).

### 14.1. Ký request (`api/shopee_api.py`)
```python
def get_signature(self, url: str, body: str = "") -> dict:
    resp = requests.post(self.sign_api_url, json={"url": url, "body": body},
                         headers={"Content-Type": "application/json", "X-API-Key": self.sign_api_key},
                         timeout=20)
    data = resp.json()
    if resp.status_code != 200 or data.get("code") not in (0, None):
        self.last_error = f"Sign API: HTTP {resp.status_code} — {data.get('msg')}"
        return {}
    sig = data.get("data")
    if isinstance(sig, dict) and isinstance(sig.get("headers"), dict):
        sig = sig["headers"]
    return sig if isinstance(sig, dict) else {}
```

### 14.2. GET có ký + kiểm tra lỗi
```python
def _signed_get(self, url: str, debug_name: str) -> dict | None:
    cookie = re.sub(r"shopee_app_version=\d+", "shopee_app_version=33731", self.cookie)
    headers = timeline_headers(cookie, country=self.country)
    headers["client-request-id"] = str(uuid.uuid4())
    headers.update(self.get_signature(url))
    self.request_count += 1
    resp = requests.get(url, headers=headers, timeout=20)
    text, data = resp.text, resp.json()
    self._save_debug(debug_name, data)
    if data.get("is_login") is False:            -> lỗi "Cookie chưa đăng nhập / hết hạn"
    if "captcha" in text.lower()[:2000]:         -> lỗi "Cookie bị captcha"
    if resp.status_code != 200 or (not data.get("data") and data.get("error")):  -> lỗi 418 / chặn
    if data.get("code") not in (0, None):        -> lỗi "Shopee trả lỗi code=..."
    return data
```

### 14.3. Timeline & hashtag dùng chung phân trang
```python
def get_all_videos(self, profile_id, max_videos=0, on_progress=None, stop_flag=None):
    def make_url(ctx):
        return (f"{self.sv_host}/api/v2/timeline/me?limit=48&page_context={quote(ctx)}"
                f"&request_user_id={profile_id}&need_total_count=0&need_product_v2=true")
    return self._paged_feed(make_url, profile_id, max_videos, on_progress, stop_flag, f"timeline_{profile_id}")

def get_hashtag_videos(self, hashtag_id, hashtag_name, max_videos=12, stop_flag=None):
    name = hashtag_name if hashtag_name.startswith("#") else f"#{hashtag_name}"
    def make_url(ctx):
        c = f"&page_context={quote(ctx)}" if ctx else ""
        return (f"{self.sv_host}/api/v2/hashtag/post/list?hashtag_id={hashtag_id}"
                f"&hashtag_name={quote(name)}&limit=12{c}&need_product_v2=true")
    return self._paged_feed(make_url, None, max_videos, None, stop_flag, f"hashtag_{hashtag_id}")

def _paged_feed(self, make_url, profile_id, max_videos, on_progress, stop_flag, debug_name):
    page_context, out = "", []
    while not (stop_flag and stop_flag()):
        data = self._signed_get(make_url(page_context), debug_name)
        if data is None: break
        raw = data.get("data") or {}
        videos = raw.get("list") or []
        for v in videos:
            out.append(self._parse_video(v, profile_id))
            if max_videos > 0 and len(out) >= max_videos: return out
        page = raw.get("page") or {}
        page_context = page.get("page_context") or ""
        if not page.get("has_more") or not page_context or not videos: break
        time.sleep(self.delay_sec)
    return out
```

### 14.4. Username → ID
```python
def get_userid_by_username(self, username: str) -> str:
    url = (f"{self.base_host}/api/v4/shop/get_shop_base?entry_point=ShopByPDP"
           f"&need_cancel_rate=true&request_source=shop_home_page&username={quote(username)}&version=1")
    data = requests.get(url, headers=web_headers(self.cookie, country=self.country), timeout=15).json()
    return str((data.get("data") or {}).get("userid") or "")
```

### 14.5. Link rút gọn → ID
```python
target = raw
for _ in range(5):
    resp = requests.get(target, allow_redirects=False, timeout=12, headers={"User-Agent": APP_UA})
    loc = resp.headers.get("Location") or ""
    if not loc: break
    m = re.search(r"/(?:profile|me|creator|user)/(\d+)", unquote(unquote(loc)))
    if m: return m.group(1)
    target = loc
```

### 14.6. Parse video (rút gọn)
```python
meta, content = v.get("meta") or {}, v.get("content") or {}
video, allow  = content.get("video") or {}, v.get("allow_info") or {}
counts        = meta.get("count_info") or {}
profile_id    = str(profile_id or meta.get("user_id") or "")
ct = int(meta.get("ctime") or meta.get("ptime") or 0); ct = ct // 1000 if ct > 10**12 else ct
hashtags = [(str(h["hashtag_id"]), caption[h["start"]:h["start"]+h["length"]].lower())
            for h in content.get("hashtags") or []]
related  = mentions.user_id + music.author_id + products.enhanced_item_list[].shop_user_id  (≠ profile_id)
return {**self._main_product(content),
        "profile_id": profile_id, "video_id": video.get("video_id") or meta.get("post_id"),
        "allow_duet": bool(allow.get("allow_duet")), "allow_stitch": bool(allow.get("allow_stitch")),
        "play_count": counts.get("views"), "like_count": counts.get("likes"),
        "comment_count": counts.get("comments"), "create_time": ct,
        "description": content.get("caption"), "video_url": video.get("url"),
        "hashtags": hashtags, "related_ids": related,
        "share_url": self._video_link(meta.get("post_id"), profile_id)}   # mục 4.10
```

### 14.7. Sản phẩm chính
```python
products = content.get("products") or {}
anchor   = products.get("anchor_product") or {}
items    = products.get("enhanced_item_list") or []
item = next((it for it in items if it.get("item_id") == anchor.get("item_id")), items[0] if items else None)
# ... dự phòng anchor, rồi content.product_v2
product_url   = f"{self.base_host}/product/{shop_id}/{item_id}"
product_price = int(price) // 100000
product_sold  = item.get("historical_sold") or item.get("sold")
product_count = products.get("count") or len(items) or 1
```

### 14.8. Chấm điểm viral
```python
def enrich(v, now=None):
    now = now or time.time(); ct = v.get("create_time") or 0; views = v.get("play_count") or 0
    if ct > 0:
        age = max((now - ct) / 86400, 0.5)
        v["age_days"] = round(age, 1); v["views_per_day"] = int(views / age)
        v["post_date"] = datetime.fromtimestamp(ct).strftime("%Y-%m-%d")
    inter = (v.get("like_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0)
    v["engagement"] = round(inter * 100 / views, 2) if views else 0.0
    return v

def filter_viral(videos, max_age_days=0, min_views=0, min_likes=0, min_views_per_day=0, duet_only=True, top_n=0):
    out = [v for v in videos
           if (not duet_only or v.get("allow_duet"))
           and (v.get("play_count") or 0) >= min_views
           and (v.get("like_count") or 0) >= min_likes
           and (v.get("views_per_day") or 0) >= min_views_per_day
           and (max_age_days <= 0 or (v.get("age_days") is not None and v["age_days"] <= max_age_days))]
    out.sort(key=lambda x: (x.get("views_per_day") or 0, x.get("play_count") or 0), reverse=True)
    return out[:top_n] if top_n > 0 else out
```

### 14.9. Vòng lặp quét lan (worker, rút gọn)
```python
while not self._stop:
    if self.credit_budget and api.request_count >= self.credit_budget: break
    if seed_creators:   task = ("creator", *seed_creators.pop(0))
    elif seed_tags:     task = ("tag", *seed_tags.pop(0))
    else:               task = self._next_discovered()          # max điểm trong creator_score ∪ tag_score
    if not task: break
    videos = api.get_all_videos(...) if task[0] == "creator" else api.get_hashtag_videos(...)
    for v in videos:
        w = (v.get("play_count") or 0) + 1
        for uid in [v["profile_id"], *[u for u, _ in v["related_ids"]]]:
            if uid not in scanned_creators: creator_score[uid] = creator_score.get(uid, 0) + w
        for tid, name in v["hashtags"]:
            if tid not in scanned_tags: tag_score[tid] = tag_score.get(tid, 0) + w; tag_names.setdefault(tid, name)
        if v["video_id"] not in seen_videos: seen_videos.add(v["video_id"]); emit(v)
```
