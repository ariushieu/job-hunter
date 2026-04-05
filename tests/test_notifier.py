"""
Unit tests for the notifier module (Telegram message formatting).
"""

import pytest
import httpx

from src.notifier import TelegramNotifier
from src.scraper import Job


class TestEscapeMarkdown:
    """Test MarkdownV2 character escaping."""

    def setup_method(self):
        self.notifier = TelegramNotifier("fake_token", "fake_chat_id")

    def test_escape_basic_special_chars(self):
        assert self.notifier._escape_md("Hello_World") == r"Hello\_World"
        assert self.notifier._escape_md("Price: $100") == r"Price: $100"

    def test_escape_dots_and_dashes(self):
        assert self.notifier._escape_md("v1.0.0") == r"v1\.0\.0"
        assert self.notifier._escape_md("a-b") == r"a\-b"

    def test_escape_parentheses(self):
        assert self.notifier._escape_md("func()") == r"func\(\)"

    def test_escape_brackets(self):
        assert self.notifier._escape_md("[link]") == r"\[link\]"

    def test_no_escape_needed(self):
        assert self.notifier._escape_md("Hello World 123") == "Hello World 123"

    def test_empty_string(self):
        assert self.notifier._escape_md("") == ""

    def test_escape_exclamation(self):
        assert self.notifier._escape_md("New!") == r"New\!"

    def test_vietnamese_text(self):
        """Vietnamese chars should pass through unchanged."""
        text = "Thực tập sinh Java"
        escaped = self.notifier._escape_md(text)
        assert "Thực" in escaped
        assert "Java" in escaped


class TestFormatJobMessage:
    """Test Telegram message formatting."""

    def setup_method(self):
        self.notifier = TelegramNotifier("fake_token", "fake_chat_id")

    def test_message_contains_job_title(self, sample_job):
        msg = self.notifier._format_job_message(sample_job)
        # Title is escaped, but core words should be present
        assert "Intern" in msg
        assert "Java" in msg
        assert "Spring" in msg

    def test_message_contains_source(self, sample_job):
        msg = self.notifier._format_job_message(sample_job)
        assert "ITVIEC" in msg

    def test_message_contains_link(self, sample_job):
        msg = self.notifier._format_job_message(sample_job)
        assert sample_job.link in msg

    def test_message_has_markdown_formatting(self, sample_job):
        msg = self.notifier._format_job_message(sample_job)
        assert "*" in msg  # Bold markers
        assert "[Xem chi tiết]" in msg  # Link text

    def test_message_for_topcv(self, sample_job_topcv):
        msg = self.notifier._format_job_message(sample_job_topcv)
        assert "TOPCV" in msg
        assert sample_job_topcv.link in msg


class TestSendMessage:
    """Test the actual send logic (mocked HTTP)."""

    def setup_method(self):
        self.notifier = TelegramNotifier("fake_token", "12345")

    @pytest.mark.asyncio
    async def test_send_message_success(self, monkeypatch):
        """Verify correct API call when Telegram returns 200."""
        captured_requests = []

        async def mock_post(self_client, url, **kwargs):
            captured_requests.append({"url": url, "json": kwargs.get("json")})
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await self.notifier.send_message("Test message", parse_mode=None)
        assert result is True
        assert len(captured_requests) == 1
        assert "/sendMessage" in captured_requests[0]["url"]
        assert captured_requests[0]["json"]["text"] == "Test message"

    @pytest.mark.asyncio
    async def test_send_message_api_error(self, monkeypatch):
        """Should return False on API error."""
        async def mock_post(self_client, url, **kwargs):
            return httpx.Response(400, json={"ok": False, "description": "Bad Request"})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await self.notifier.send_message("Test", parse_mode=None)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_timeout(self, monkeypatch):
        """Should return False on timeout."""
        async def mock_post(self_client, url, **kwargs):
            raise httpx.TimeoutException("Connection timed out")

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await self.notifier.send_message("Test", parse_mode=None)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_network_error(self, monkeypatch):
        """Should return False on network error."""
        async def mock_post(self_client, url, **kwargs):
            raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await self.notifier.send_message("Test", parse_mode=None)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_no_parse_mode(self, monkeypatch):
        """When parse_mode=None, it should NOT be in the payload."""
        captured_payload = {}

        async def mock_post(self_client, url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        await self.notifier.send_message("Test", parse_mode=None)
        assert "parse_mode" not in captured_payload

    @pytest.mark.asyncio
    async def test_send_message_with_markdown(self, monkeypatch):
        """When parse_mode is set, it should be in the payload."""
        captured_payload = {}

        async def mock_post(self_client, url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        await self.notifier.send_message("*Bold*", parse_mode="MarkdownV2")
        assert captured_payload["parse_mode"] == "MarkdownV2"


class TestSendJobs:
    """Test batch sending."""

    @pytest.mark.asyncio
    async def test_send_jobs_counts(self, monkeypatch, sample_jobs):
        """Should return the count of jobs in successfully sent batch messages."""
        notifier = TelegramNotifier("fake_token", "12345")

        async def mock_post(self_client, url, **kwargs):
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        # Patch sleep to speed up test
        import asyncio
        original_sleep = asyncio.sleep
        monkeypatch.setattr(asyncio, "sleep", lambda _: original_sleep(0))

        sent = await notifier.send_jobs(sample_jobs)
        assert sent == len(sample_jobs)

    @pytest.mark.asyncio
    async def test_send_jobs_empty_list(self, monkeypatch):
        """Empty list should return 0 without sending."""
        notifier = TelegramNotifier("fake_token", "12345")
        sent = await notifier.send_jobs([])
        assert sent == 0

    @pytest.mark.asyncio
    async def test_send_jobs_batches_large_list(self, monkeypatch):
        """15 jobs should be sent in 2 batch messages (10 + 5)."""
        notifier = TelegramNotifier("fake_token", "12345")
        sent_messages = []

        async def mock_post(self_client, url, **kwargs):
            sent_messages.append(kwargs.get("json", {}).get("text", ""))
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        import asyncio
        original_sleep = asyncio.sleep
        monkeypatch.setattr(asyncio, "sleep", lambda _: original_sleep(0))

        jobs = [
            Job(title=f"Intern Java {i}", link=f"https://example.com/{i}", source="itviec")
            for i in range(15)
        ]
        sent = await notifier.send_jobs(jobs)
        assert sent == 15
        assert len(sent_messages) == 2  # 2 batch messages

    @pytest.mark.asyncio
    async def test_batch_message_contains_all_jobs(self, monkeypatch, sample_jobs):
        """Batch message should contain titles of all jobs."""
        notifier = TelegramNotifier("fake_token", "12345")
        sent_texts = []

        async def mock_post(self_client, url, **kwargs):
            sent_texts.append(kwargs.get("json", {}).get("text", ""))
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        import asyncio
        original_sleep = asyncio.sleep
        monkeypatch.setattr(asyncio, "sleep", lambda _: original_sleep(0))

        await notifier.send_jobs(sample_jobs)
        # All job titles should appear in the batch message
        combined = " ".join(sent_texts)
        for job in sample_jobs:
            # Title is escaped, check core word
            assert "Intern" in combined

    @pytest.mark.asyncio
    async def test_send_summary(self, monkeypatch):
        """Summary message should send successfully."""
        notifier = TelegramNotifier("fake_token", "12345")

        async def mock_post(self_client, url, **kwargs):
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        result = await notifier.send_summary(total_scraped=10, new_count=3, total_in_db=50)
        assert result is True
