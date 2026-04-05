# Job Hunter Automation - Implementation Plan

## Context

Xây dựng công cụ tự động tìm kiếm job **Intern Java Spring Boot** từ các trang tuyển dụng Việt Nam (ITviec, TopCV), gửi thông báo qua Telegram Bot. Tool chạy trên Ubuntu VPS mỗi 4 tiếng qua Docker + crontab.

**Quyết định thiết kế quan trọng:**
- **V1.0 tập trung ITviec + TopCV** + fallback VietnamWorks/CareerBuilder nếu cần. Google Search để sau.
- Chỉ cần lấy **Title + Link** cho V1
- Dùng `playwright-stealth` để bypass anti-bot (ITviec block 403 rất gắt, TopCV là Vue.js SPA)
- **Giả lập hành vi người thật là ưu tiên số 1**: random delay, random UA, scroll từ từ sau load, viewport ngẫu nhiên
- **TopCV**: tương tác như người thật - vào trang chủ → gõ search → nhấn Enter (KHÔNG truy cập URL trực tiếp)
- **ITviec**: scroll nhẹ sau load trang để bypass Cloudflare sensor
- **Fallback**: nếu ITviec quá gắt → cào VietnamWorks hoặc CareerBuilder thay thế

---

## Kiến trúc tổng quan

```
D:/job-hunter/
├── plan/
│   └── 20260405-job-hunter-automation.md
├── src/
│   ├── __init__.py
│   ├── main.py          # Điều phối chính
│   ├── scraper.py        # Logic crawl (Playwright + stealth)
│   ├── notifier.py       # Gửi Telegram via httpx
│   ├── database.py       # TinyDB check trùng
│   └── config.py         # Load .env, constants
├── .env                  # Bot Token, Chat ID (KHÔNG push git)
├── .env.example          # Template cho người dùng
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md             # Hướng dẫn setup
```

---

## Chi tiết từng module

### 1. `src/config.py` - Cấu hình

```
- Load biến môi trường từ .env bằng python-dotenv
- Constants:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  SEARCH_KEYWORDS = ["intern java", "intern java spring boot", "intern spring boot"]
  REQUEST_DELAY_RANGE = (3, 7)  # giây, random giữa mỗi action
  USER_AGENTS = [list 10+ UA strings phổ biến]
  VIEWPORT_SIZES = [(1366,768), (1920,1080), (1440,900), ...]
  DB_PATH = "data/jobs.json"
```

### 2. `src/scraper.py` - Crawl Engine

**Anti-detection strategy (ưu tiên cao nhất):**
- `playwright-stealth`: patch navigator.webdriver, plugins, languages, WebGL, chrome.runtime, etc.
- Random User-Agent mỗi session (10+ UA thực tế từ Chrome/Firefox/Edge mới nhất)
- Random viewport size từ pool kích thước phổ biến
- Random delay 3-7s giữa các action (uniform distribution)
- **Human-like scroll**: sau khi load trang, scroll xuống từ từ (200-400px mỗi bước, delay 0.5-1.5s) để trigger Cloudflare sensor
- **Mouse movement nhẹ**: di chuột random trên page trước khi extract data
- Chạy headless Chromium (có thể chuyển headed để debug)

**Cấu trúc class:**
```python
class JobScraper:
    async def _create_stealth_browser() -> (Browser, Page)
    async def _random_delay(min_s, max_s)
    async def _human_scroll(page)          # Scroll từ từ giả lập đọc
    async def _human_mouse_move(page)      # Di chuột random nhẹ
    async def scrape_itviec() -> List[Job]
    async def scrape_topcv() -> List[Job]
    async def scrape_vietnamworks() -> List[Job]  # Fallback
    async def scrape_careerbuilder() -> List[Job] # Fallback
    async def scrape_all() -> List[Job]
```

**ITviec crawling (khó nhất - Cloudflare):**
- URL: `https://itviec.com/it-jobs?query=intern+java+spring+boot`
- ITviec block 403 với HTTP đơn giản → BẮT BUỘC dùng Playwright + stealth
- **Chiến lược bypass Cloudflare:**
  1. Load page, đợi networkidle
  2. **Scroll nhẹ** xuống 2-3 lần (quan trọng nhất để bypass Cloudflare sensor)
  3. Đợi thêm 2-3s cho CF challenge pass
  4. Mới bắt đầu extract data
- CSS selectors (cần verify lúc implement, có fallback chain):
  - Job container: `.job-card`, `.job_content`, `div[class*="job"]`
  - Job title: `h3 a`, `.job-title a`, `a[data-controller]`
  - Job link: href từ title anchor (prefix `https://itviec.com`)
- Fallback: nếu selector chính fail → thử selector phụ → log warning, skip
- **Nếu vẫn bị block**: log warning, bỏ qua ITviec lần này, cào VietnamWorks thay thế

**TopCV crawling (tương tác như người thật):**
- **KHÔNG truy cập URL search trực tiếp** (dễ bị detect)
- **Chiến lược tương tác thật:**
  1. Vào `https://www.topcv.vn` (trang chủ)
  2. Đợi page load xong
  3. Scroll nhẹ, di chuột
  4. Tìm ô search (input box), click vào
  5. Gõ keyword "Java Intern" từ từ (giả lập typing, delay 50-150ms/ký tự)
  6. Nhấn Enter hoặc click nút tìm kiếm
  7. Đợi kết quả load (Vue.js render)
  8. Extract data từ danh sách kết quả
- CSS selectors:
  - Search input: `#keyword`, `input[name="keyword"]`, `input[placeholder*="tìm"]`
  - Job container: `.job-item`, `div[class*="job-item"]`
  - Job title: `.job-item__title`, `h3.title`, `a[class*="title"]`
  - Job link: href từ `.job-item a` (prefix `https://www.topcv.vn` nếu relative)
- Handle empty results: check text "0 việc làm" → log info, return []

**VietnamWorks fallback:**
- URL: `https://www.vietnamworks.com/intern-java-jobs`
- Server-rendered, ít anti-bot hơn ITviec
- CSS selectors: verify khi implement

**CareerBuilder.vn fallback:**
- URL: `https://careerbuilder.vn/viec-lam/intern-java-k-vi.html`
- Tương tự VietnamWorks, dùng khi cần thêm nguồn

**Data model:**
```python
@dataclass
class Job:
    title: str
    link: str
    source: str        # "itviec" | "topcv" | "vietnamworks" | "careerbuilder"
    found_at: str      # ISO datetime
```

### 3. `src/database.py` - Dedup với TinyDB

```python
class JobDatabase:
    def __init__(db_path)        # TinyDB file
    def is_new(job: Job) -> bool # Check by link (unique key)
    def save(job: Job)           # Insert job record
    def get_all() -> List        # Debug/export
```

- Dùng `link` làm unique key (URL không đổi cho cùng 1 job post)
- TinyDB lưu file JSON tại `data/jobs.json`

### 4. `src/notifier.py` - Telegram Bot

```python
class TelegramNotifier:
    def __init__(bot_token, chat_id)
    async def send_job(job: Job)        # Gửi 1 job
    async def send_jobs(jobs: List[Job]) # Gửi batch, có rate limit
    async def send_summary(total, new)   # Tổng kết mỗi lần chạy
```

- Dùng `httpx.AsyncClient` gọi `https://api.telegram.org/bot<TOKEN>/sendMessage`
- Format message: Markdown với title bold, link clickable, source tag
- Rate limit: delay 1s giữa mỗi message (Telegram limit ~30 msg/s)
- Gửi summary cuối: "Tìm thấy X job mới / tổng Y job"

### 5. `src/main.py` - Orchestrator

```python
async def main():
    1. Load config
    2. Init database, notifier
    3. scraper.scrape_all() → List[Job]
    4. Filter qua database.is_new()
    5. Save new jobs to database
    6. notifier.send_jobs(new_jobs)
    7. notifier.send_summary()
    8. Log kết quả
```

---

## Error Handling & Logging

- **Logging**: `logging` module, format `[%(asctime)s] %(levelname)s - %(message)s`
  - Log to stdout (Docker sẽ capture) + file `logs/job_hunter.log`
- **Try-catch strategy**:
  - Mỗi site scrape trong try-except riêng → 1 site fail không ảnh hưởng site khác
  - Selector fail → log warning, thử fallback selector, cuối cùng skip
  - Network error → log error, retry 1 lần sau 10s, rồi skip
  - Telegram fail → log error nhưng không crash (jobs vẫn saved to DB)

---

## Deployment

### Dockerfile
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN playwright install chromium
CMD ["python", "-m", "src.main"]
```

### docker-compose.yml
- Mount volume cho `data/` (persist TinyDB) và `logs/`
- Load `.env` file

### Crontab trên Ubuntu VPS
```bash
# Chạy mỗi 4 tiếng
0 */4 * * * cd /path/to/job-hunter && docker compose run --rm job-hunter >> /var/log/job-hunter.log 2>&1
```

---

## Files cần tạo

| # | File | Mục đích |
|---|------|----------|
| 1 | `requirements.txt` | Dependencies |
| 2 | `src/__init__.py` | Package init |
| 3 | `src/config.py` | Config & constants |
| 4 | `src/scraper.py` | Playwright crawl engine |
| 5 | `src/database.py` | TinyDB dedup |
| 6 | `src/notifier.py` | Telegram notification |
| 7 | `src/main.py` | Orchestrator |
| 8 | `.env.example` | Template env vars |
| 9 | `.gitignore` | Ignore .env, data/, logs/, __pycache__ |
| 10 | `Dockerfile` | Container build |
| 11 | `docker-compose.yml` | Container orchestration |

---

## Dependencies (requirements.txt)

```
playwright==1.52.0
playwright-stealth==1.0.6
tinydb==4.8.2
httpx==0.28.1
python-dotenv==1.1.0
```

---

## Verification / Test Plan

1. **Unit test nhanh**: Chạy `python -m src.main` local, verify:
   - Log output hiện đúng flow
   - Playwright mở browser, truy cập ITviec/TopCV không bị block
   - Jobs được parse đúng (title + link)
   - TinyDB file tạo đúng tại `data/jobs.json`
   - Lần chạy thứ 2: không gửi lại job cũ (dedup hoạt động)

2. **Telegram test**: Tạo bot test, verify message format đẹp trên app

3. **Docker test**: `docker compose build && docker compose run --rm job-hunter`
   - Verify Playwright chạy được trong container
   - Verify volume mount persist data

4. **Error resilience**: Thử disconnect network giữa chừng → verify script không crash, log error rõ ràng
