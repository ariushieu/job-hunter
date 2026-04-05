# 🔍 Job Hunter - Automated Java Intern Job Finder

Công cụ tự động tìm kiếm việc làm **Intern Java Spring Boot** từ các trang tuyển dụng Việt Nam và gửi thông báo qua Telegram Bot.

## ✨ Tính năng

- 🤖 Tự động cào job từ 4 nguồn: ITviec, TopCV, VietnamWorks, CareerBuilder
- 🛡️ Bypass anti-bot với Playwright + stealth (giả lập hành vi người thật)
- 🔔 Gửi thông báo real-time qua Telegram Bot
- 💾 Lọc trùng lặp với TinyDB (không gửi lại job cũ)
- 🐳 Deploy dễ dàng với Docker
- ⏰ Chạy tự động mỗi 4 tiếng với crontab

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

### Search keywords

Chỉnh sửa trong `src/config.py`:

```python
SEARCH_KEYWORDS = [
    "intern java spring boot",
    "intern java",
    "thực tập java",
]
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

- Các trang web thường xuyên thay đổi HTML structure
- Kiểm tra logs để xem site nào bị fail
- Có thể cần update CSS selectors trong `src/scraper.py`

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
