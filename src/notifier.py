"""
Notifier module - Send job alerts to Telegram via Bot API using httpx.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from src.scraper import Job

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramNotifier:
    """Send job notifications to a Telegram chat."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._api_base = TELEGRAM_API_BASE.format(token=bot_token)

    def _format_job_message(self, job: Job) -> str:
        """Format a single job into a Telegram-friendly message (MarkdownV2)."""
        # Escape special chars for MarkdownV2
        title = self._escape_md(job.title)
        source = self._escape_md(job.source.upper())

        return (
            f"🔔 *Job Intern mới\\!*\n\n"
            f"📌 *{title}*\n"
            f"🏢 Nguồn: `{source}`\n"
            f"🔗 [Xem chi tiết]({job.link})"
        )

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        special_chars = r"_*[]()~`>#+-=|{}.!"
        escaped = ""
        for char in text:
            if char in special_chars:
                escaped += f"\\{char}"
            else:
                escaped += char
        return escaped

    async def send_message(self, text: str, parse_mode: str | None = "MarkdownV2") -> bool:
        """Send a single message to the configured chat. Returns True on success."""
        url = f"{self._api_base}/sendMessage"
        payload: dict = {
            "chat_id": self._chat_id,
            "text": text,
            "disable_web_page_preview": False,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    logger.debug("Telegram message sent successfully")
                    return True
                else:
                    logger.error(
                        "Telegram API error: %d - %s",
                        response.status_code,
                        response.text,
                    )
                    return False

        except httpx.TimeoutException:
            logger.error("Telegram API timeout")
            return False
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)
            return False

    async def send_job(self, job: Job) -> bool:
        """Send a single job notification."""
        message = self._format_job_message(job)
        return await self.send_message(message)

    async def send_jobs(self, jobs: list[Job]) -> int:
        """Send multiple job notifications with rate limiting. Returns count of sent."""
        sent_count = 0

        for i, job in enumerate(jobs):
            success = await self.send_job(job)
            if success:
                sent_count += 1

            # Rate limit: ~1 message per second (Telegram allows ~30/s but be safe)
            if i < len(jobs) - 1:
                await asyncio.sleep(1.0)

        logger.info("Sent %d/%d job notifications", sent_count, len(jobs))
        return sent_count

    async def send_summary(self, total_scraped: int, new_count: int, total_in_db: int) -> bool:
        """Send a run summary message."""
        text = (
            f"📊 *Job Hunter \\- Tổng kết*\n\n"
            f"🔍 Đã quét: `{total_scraped}` jobs\n"
            f"🆕 Job mới: `{new_count}`\n"
            f"💾 Tổng trong DB: `{total_in_db}`\n\n"
            f"⏰ Lần chạy tiếp: ~4 tiếng nữa"
        )
        return await self.send_message(text)

    async def send_error_report(self, error_msg: str) -> bool:
        """Send an error notification (plain text, no markdown)."""
        text = f"⚠️ Job Hunter - Lỗi:\n\n{error_msg}"
        return await self.send_message(text, parse_mode=None)
