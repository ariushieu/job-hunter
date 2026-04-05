"""
Configuration module - Load environment variables and define constants.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Load .env file
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ──────────────────────────────────────────────
# Telegram Bot (from .env - NEVER hardcode)
# ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ──────────────────────────────────────────────
# Search keywords
# ──────────────────────────────────────────────
SEARCH_KEYWORDS: list[str] = [
    "intern java spring boot",
    "intern java",
    "intern spring boot",
    "thực tập java",
]

# ──────────────────────────────────────────────
# Anti-detection: delay & timing
# ──────────────────────────────────────────────
ACTION_DELAY_MIN: float = 3.0   # seconds between major actions
ACTION_DELAY_MAX: float = 7.0
TYPING_DELAY_MIN: int = 50      # ms per keystroke
TYPING_DELAY_MAX: int = 150
SCROLL_STEP_MIN: int = 200      # px per scroll step
SCROLL_STEP_MAX: int = 400
SCROLL_DELAY_MIN: float = 0.5   # seconds between scroll steps
SCROLL_DELAY_MAX: float = 1.5
PAGE_LOAD_TIMEOUT: int = 30000  # ms

# ──────────────────────────────────────────────
# Anti-detection: User-Agent pool
# ──────────────────────────────────────────────
USER_AGENTS: list[str] = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# ──────────────────────────────────────────────
# Anti-detection: viewport pool
# ──────────────────────────────────────────────
VIEWPORT_SIZES: list[dict[str, int]] = [
    {"width": 1366, "height": 768},
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
    {"width": 1600, "height": 900},
    {"width": 1280, "height": 800},
    {"width": 1680, "height": 1050},
]

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DB_PATH: str = str(BASE_DIR / "data" / "jobs.json")

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
LOG_DIR: Path = BASE_DIR / "logs"
LOG_FILE: str = str(LOG_DIR / "job_hunter.log")
LOG_FORMAT: str = "[%(asctime)s] %(levelname)s - %(name)s - %(message)s"
LOG_LEVEL: int = logging.INFO


def setup_logging() -> None:
    """Configure logging to stdout + file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=handlers,
    )


def validate_config() -> bool:
    """Check that required env vars are set. Returns True if valid."""
    logger = logging.getLogger(__name__)
    valid = True

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in .env")
        valid = False

    if not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID is not set in .env")
        valid = False

    return valid
