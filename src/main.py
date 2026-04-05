"""
Main orchestrator - Coordinates scraping, deduplication, and notification.

Usage:
    python -m src.main
"""

import asyncio
import logging
import sys

from src import config
from src.scraper import JobScraper
from src.database import JobDatabase
from src.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


async def run() -> None:
    """Main pipeline: scrape → dedup → notify."""
    # ── Step 1: Setup ──────────────────────────
    config.setup_logging()
    logger.info("=" * 60)
    logger.info("Job Hunter started")
    logger.info("=" * 60)

    if not config.validate_config():
        logger.critical("Invalid configuration. Check your .env file.")
        sys.exit(1)

    db = JobDatabase(config.DB_PATH)
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    scraper = JobScraper()

    try:
        # ── Step 2: Scrape all sources ─────────
        await scraper.start()
        all_jobs = await scraper.scrape_all()

        # ── Step 3: Filter new jobs via DB ─────
        new_jobs = []
        for job in all_jobs:
            if db.save_if_new(job):
                new_jobs.append(job)

        logger.info(
            "Results: %d total scraped, %d new, %d already in DB",
            len(all_jobs), len(new_jobs), db.count(),
        )

        # ── Step 4: Send Telegram notifications ─
        if new_jobs:
            logger.info("Sending %d new job notifications...", len(new_jobs))
            sent = await notifier.send_jobs(new_jobs)
            logger.info("Successfully sent %d/%d notifications", sent, len(new_jobs))
        else:
            logger.info("No new jobs found this run")

        # ── Step 5: Send summary ───────────────
        await notifier.send_summary(
            total_scraped=len(all_jobs),
            new_count=len(new_jobs),
            total_in_db=db.count(),
        )

    except Exception as e:
        logger.critical("Pipeline failed: %s", e, exc_info=True)
        # Try to send error notification (best effort)
        try:
            await notifier.send_error_report(str(e))
        except Exception:
            logger.error("Could not send error report to Telegram")

    finally:
        await scraper.stop()
        db.close()

    logger.info("Job Hunter finished")
    logger.info("=" * 60)


def main() -> None:
    """Entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
