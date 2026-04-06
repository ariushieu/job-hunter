# 🔍 Job Hunter - Automated Java Intern Job Finder

Công cụ tự động tìm kiếm việc làm **Intern Java Spring Boot** từ các trang tuyển dụng Việt Nam và gửi thông báo qua Telegram Bot.

## ✨ Tính năng

- 🤖 Tự động cào job từ 3 nguồn: ITviec, TopCV, VietnamWorks
- 🎯 Filter thông minh: chỉ lấy vị trí Intern/Fresher Java/Spring Boot
- 🛡️ Bypass anti-bot với Playwright + stealth (giả lập hành vi người thật)
- 🔔 Gửi thông báo batch qua Telegram Bot (10 jobs/message)
- 💾 Lọc trùng lặp với TinyDB (không gửi lại job cũ)
- 🐳 Deploy dễ dàng với Docker
- ⏰ Chạy tự động mỗi 4 tiếng với crontab
- 📊 Summary report sau mỗi lần chạy

## 🚀 Quick Start

### 1. Chuẩn bị

**Yêu cầu:**

- Docker & Docker Compose
- Telegram Bot Token (tạo từ [@BotFather](https://t.me/BotFather))
- Telegram Chat ID (lấy từ [@userinfobot](https://t.me/userinfobot))

### 2. Clone & Setup

```bash
git clone https://github.com/your-username/job-hunter.git
cd job-hunter

# Tạo file .env từ template
cp .env.example .env

# Chỉnh sửa .env với thông tin thật
nano .env
```

**File `.env`:**

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

### 3. Chạy thử local

```bash
# Build image
docker build -t job-hunter .

# Chạy 1 lần
docker run --rm \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  job-hunter
```

Kiểm tra Telegram để xem thông báo job mới!

## 🐳 Deploy lên VPS

### Option 1: GitHub Actions (Recommended)

**Setup GitHub Secrets:**

Vào `Settings` → `Secrets and variables` → `Actions` → `New repository secret`:

```
DOCKER_USERNAME=your_dockerhub_username
DOCKER_PASSWORD=your_dockerhub_password
VPS_HOST=your_vps_ip
VPS_USERNAME=root
VPS_SSH_KEY=<paste your private SSH key>
```

**Deploy:**

```bash
git push origin master
```

GitHub Actions sẽ tự động:

1. Run tests
2. Build & push Docker image
3. SSH vào VPS và setup crontab

**Tạo `.env` trên VPS (chỉ cần 1 lần):**

```bash
ssh root@your_vps_ip
mkdir -p ~/job-hunter
nano ~/job-hunter/.env
# Paste TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID
```

### Option 2: Manual Deploy

```bash
# SSH vào VPS
ssh root@your_vps_ip

# Pull image
docker pull your_dockerhub_username/job-hunter:latest

# Tạo folders
mkdir -p ~/job-hunter/data ~/job-hunter/logs

# Tạo .env
nano ~/job-hunter/.env

# Setup crontab (chạy mỗi 4 tiếng)
crontab -e
```

Thêm dòng này vào crontab:

```bash
0 */4 * * * docker run --rm --env-file ~/job-hunter/.env -v ~/job-hunter/data:/app/data -v ~/job-hunter/logs:/app/logs your_dockerhub_username/job-hunter:latest >> ~/job-hunter/logs/cron.log 2>&1
```

## 📊 Monitoring

### Xem logs

```bash
# Log của app
tail -f ~/job-hunter/logs/job_hunter.log

# Log của cron
tail -f ~/job-hunter/logs/cron.log

# Xem database
cat ~/job-hunter/data/jobs.json | jq
```

### Test thủ công

```bash
docker run --rm \
  --env-file ~/job-hunter/.env \
  -v ~/job-hunter/data:/app/data \
  -v ~/job-hunter/logs:/app/logs \
  your_dockerhub_username/job-hunter:latest
```

## 🛠️ Development

### Local setup

```bash
# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Install Playwright browsers
playwright install chromium

# Run tests
pytest -v

# Run app
python -m src.main
```

### Project structure

```
job-hunter/
├── src/
│   ├── main.py          # Orchestrator chính
│   ├── scraper.py       # Playwright crawl engine
│   ├── database.py      # TinyDB wrapper
│   ├── notifier.py      # Telegram Bot client
│   └── config.py        # Configuration & constants
├── tests/               # Unit tests
├── data/                # TinyDB storage (gitignored)
├── logs/                # Log files (gitignored)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🔧 Configuration

### Job filter rules

Filter trong `src/scraper.py`:

```python
# Job MUST contain tech keywords
TECH_KEYWORDS = ["java", "spring", "backend", "back-end", "developer", "engineer", "lập trình"]

# Job MUST contain level keywords (intern/fresher only)
LEVEL_KEYWORDS = ["intern", "thực tập", "fresher"]

# Job MUST NOT contain these (auto-reject)
EXCLUDE_KEYWORDS = ["senior", "lead", "manager", "principal", "architect", "staff", "expert", "trưởng"]
```

### Search strategy

- **ITviec**: Search broad "java spring boot" → filter local (narrow search returns only senior jobs)
- **TopCV**: Direct URL `/tim-viec-lam-java` → filter local (Vue.js SPA)
- **VietnamWorks**: Search broad "java" → filter local (React/Next.js SPA)

### Search keywords

Chỉnh sửa trong `src/scraper.py` (mỗi site có keywords riêng):

```python
# ITviec
search_keywords = ["java spring boot", "java spring", "java intern"]

# TopCV
search_keywords = ["java", "java-spring", "java-spring-boot"]

# VietnamWorks
search_keywords = ["java", "java spring boot"]
```

### Cron schedule

Mặc định: mỗi 4 tiếng (0:00, 4:00, 8:00, 12:00, 16:00, 20:00)

Thay đổi trong crontab:

```bash
# Mỗi 2 tiếng
0 */2 * * * ...

# Mỗi 6 tiếng
0 */6 * * * ...

# Mỗi ngày lúc 9:00 sáng
0 9 * * * ...
```

## 🏗️ Architecture

### Scraping Strategy

**ITviec (Cloudflare protected):**

- Playwright + stealth patches
- Human-like scroll to bypass CF sensor
- Search broad keywords → filter local
- Selector: `h3[data-url]` (data-url attribute contains job link)

**TopCV (Vue.js SPA):**

- Direct URL search (search box unreliable)
- Wait for `networkidle` (AJAX completion)
- Extract from `a[href*='/viec-lam/'][href*='.html']`
- Search broad → filter local

**VietnamWorks (React/Next.js SPA):**

- Wait for `networkidle` (client-side hydration)
- Selector: `.new-job-card` (rendered after React hydration)
- Search broad → filter local

### Filter Logic

```
1. Check EXCLUDE_KEYWORDS → reject if match (senior, lead, etc.)
2. Check TECH_KEYWORDS → reject if no match (java, spring, etc.)
3. Check LEVEL_KEYWORDS → reject if no match (intern, fresher)
4. Accept job
```

### Data Flow

```
Cron (every 4h)
  ↓
Docker run
  ↓
Scraper.scrape_all()
  ├─ ITviec → 0-20 jobs
  ├─ TopCV → 0-50 jobs
  └─ VietnamWorks → 0-50 jobs
  ↓
Filter duplicates (by link)
  ↓
Database.save_if_new()
  ↓
Notifier.send_jobs() (batch 10/msg)
  ↓
Notifier.send_summary()
```

## 📊 Performance

**Typical run:**

- Duration: ~2-3 minutes
- CPU spike: ~40% (Playwright rendering)
- Memory: ~500MB peak
- Disk: <1MB per run (logs + DB)

**Success rate (as of Apr 2026):**

- ITviec: ~70% (Cloudflare sometimes blocks)
- TopCV: ~50% (Vue.js rendering issues)
- VietnamWorks: ~60% (React hydration timing)

## 🐛 Troubleshooting

### Playwright error: Executable doesn't exist

```bash
# Rebuild image với Playwright version mới nhất
docker build --no-cache -t job-hunter .
```

### Telegram không nhận được tin nhắn

- Kiểm tra `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` trong `.env`
- Đảm bảo đã `/start` bot trên Telegram
- Kiểm tra logs: `tail -f ~/job-hunter/logs/job_hunter.log`

### Không tìm thấy job nào

**Nguyên nhân phổ biến:**

1. **Selector outdated**: Các trang web thường xuyên thay đổi HTML structure
   - Kiểm tra logs: `tail -f ~/job-hunter/logs/job_hunter.log`
   - Tìm dòng "Strategy X: found Y containers" → nếu Y > 0 nhưng scraped = 0 → selector bị lỗi

2. **Filter quá strict**: Job bị reject vì không match filter rules
   - Xem logs: `[Source] Skipping irrelevant: {title}`
   - Nếu thấy nhiều jobs bị skip → cân nhắc nới lỏng filter

3. **Anti-bot block**: Site phát hiện và block bot
   - ITviec: Cloudflare challenge → logs sẽ có "challenge detected"
   - TopCV/VietnamWorks: Timeout hoặc empty response

**Debug:**

```bash
# Chạy thử và xem logs chi tiết
docker run --rm \
  --env-file ~/job-hunter/.env \
  -v ~/job-hunter/data:/app/data \
  -v ~/job-hunter/logs:/app/logs \
  qhieu05/job-hunter:latest | grep -E "Strategy|Scraped|Skipping"
```

### Crontab không chạy

```bash
# Kiểm tra crontab đã setup chưa
crontab -l

# Kiểm tra cron service
systemctl status cron

# Xem log của cron
tail -f ~/job-hunter/logs/cron.log
```

## 📝 License

MIT License - feel free to use and modify!

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

## 📧 Contact

Có vấn đề? Tạo issue trên GitHub hoặc liên hệ qua Telegram.

---

**⭐ Nếu project hữu ích, đừng quên star repo nhé!**
