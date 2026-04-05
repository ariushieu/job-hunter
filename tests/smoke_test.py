"""
Smoke test - Quick end-to-end verification that the tool works.

This test actually launches a browser and attempts to scrape.
Run manually to verify scraper works on your machine/VPS:

    python -m tests.smoke_test

Requirements:
    - Playwright browsers installed: playwright install chromium
    - .env configured with real TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
      (or set DRY_RUN=true to skip Telegram)
"""

import asyncio
import logging
import os
import sys
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.scraper import JobScraper
from src.database import JobDatabase
from src.notifier import TelegramNotifier


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)
logger = logging.getLogger("smoke_test")


async def smoke_test() -> None:
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    logger.info("=" * 60)
    logger.info("SMOKE TEST - Job Hunter")
    logger.info("DRY_RUN=%s", dry_run)
    logger.info("=" * 60)

    results: dict[str, str] = {}

    # ── Test 1: Config ─────────────────────────
    logger.info("\n--- Test 1: Configuration ---")
    try:
        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            results["config"] = "PASS"
            logger.info("PASS - Env vars loaded")
        elif dry_run:
            results["config"] = "PASS (dry run)"
            logger.info("PASS - Dry run mode, env vars optional")
        else:
            results["config"] = "FAIL"
            logger.error("FAIL - Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    except Exception as e:
        results["config"] = f"FAIL: {e}"
        logger.error("FAIL - %s", e)

    # ── Test 2: Database ───────────────────────
    logger.info("\n--- Test 2: Database (TinyDB) ---")
    try:
        from src.scraper import Job

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_db = f.name

        db = JobDatabase(tmp_db)
        test_job = Job(title="Smoke Test Job", link="https://test.com/smoke", source="test")

        assert db.save_if_new(test_job) is True, "First save should return True"
        assert db.save_if_new(test_job) is False, "Duplicate save should return False"
        assert db.count() == 1, "Should have exactly 1 record"

        db.close()
        os.unlink(tmp_db)

        results["database"] = "PASS"
        logger.info("PASS - Save, dedup, count all working")
    except Exception as e:
        results["database"] = f"FAIL: {e}"
        logger.error("FAIL - %s", e)

    # ── Test 3: Scraper (LIVE browser) ─────────
    logger.info("\n--- Test 3: Scraper (live browser) ---")
    scraper = JobScraper()
    try:
        await scraper.start()
        logger.info("PASS - Browser launched successfully")

        # Try each site individually
        for site_name, scrape_fn in [
            ("ITviec", scraper.scrape_itviec),
            ("TopCV", scraper.scrape_topcv),
            ("VietnamWorks", scraper.scrape_vietnamworks),
            ("CareerBuilder", scraper.scrape_careerbuilder),
        ]:
            try:
                logger.info("  Scraping %s...", site_name)
                jobs = await scrape_fn()
                status = f"PASS ({len(jobs)} jobs)"
                logger.info("  %s - %s: %d jobs found", status, site_name, len(jobs))
                if jobs:
                    for j in jobs[:5]:  # Show first 5, full links
                        logger.info("    - %s", j.title)
                        logger.info("      %s", j.link)
            except Exception as e:
                status = f"FAIL: {e}"
                logger.error("  FAIL - %s: %s", site_name, e)

            results[f"scraper_{site_name.lower()}"] = status

    except Exception as e:
        results["scraper"] = f"FAIL: {e}"
        logger.error("FAIL - Could not start browser: %s", e)
    finally:
        await scraper.stop()

    # ── Test 4: Telegram ───────────────────────
    logger.info("\n--- Test 4: Telegram Notification ---")
    if dry_run:
        results["telegram"] = "SKIPPED (dry run)"
        logger.info("SKIPPED - Dry run mode")
    elif not config.TELEGRAM_BOT_TOKEN:
        results["telegram"] = "SKIPPED (no token)"
        logger.info("SKIPPED - No bot token configured")
    else:
        try:
            notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
            success = await notifier.send_message(
                "🧪 *Smoke Test* \\- Job Hunter hoạt động\\!",
                parse_mode="MarkdownV2",
            )
            if success:
                results["telegram"] = "PASS"
                logger.info("PASS - Message sent to Telegram")
            else:
                results["telegram"] = "FAIL - API returned error"
                logger.error("FAIL - Telegram API rejected the message")
        except Exception as e:
            results["telegram"] = f"FAIL: {e}"
            logger.error("FAIL - %s", e)

    # ── Summary ────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("SMOKE TEST RESULTS")
    logger.info("=" * 60)

    all_pass = True
    for test_name, result in results.items():
        icon = "✅" if "PASS" in result else "⏭️" if "SKIP" in result else "❌"
        logger.info("  %s %s: %s", icon, test_name, result)
        if "FAIL" in result:
            all_pass = False

    logger.info("=" * 60)
    if all_pass:
        logger.info("Overall: ALL TESTS PASSED")
    else:
        logger.warning("Overall: SOME TESTS FAILED - check logs above")

    return all_pass


if __name__ == "__main__":
    success = asyncio.run(smoke_test())
    sys.exit(0 if success else 1)
