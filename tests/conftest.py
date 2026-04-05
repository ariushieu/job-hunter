"""
Shared test fixtures for Job Hunter tests.
"""

import os
import tempfile

import pytest

from src.scraper import Job


# ──────────────────────────────────────────────
# Ensure test environment (no real Telegram sends)
# ──────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    """Set safe env vars so tests never hit real Telegram."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token_000000:AAAAAAAAAAAAAAAAAAAAAAAA")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")


# ──────────────────────────────────────────────
# Job fixtures
# ──────────────────────────────────────────────
@pytest.fixture
def sample_job() -> Job:
    return Job(
        title="Intern Java Spring Boot Developer",
        link="https://itviec.com/it-jobs/intern-java-spring-boot-abc-company",
        source="itviec",
        found_at="2026-04-05T10:00:00+00:00",
    )


@pytest.fixture
def sample_job_topcv() -> Job:
    return Job(
        title="Thực tập sinh Java (Spring Boot)",
        link="https://www.topcv.vn/viec-lam/thuc-tap-java-spring-boot-123456",
        source="topcv",
        found_at="2026-04-05T11:00:00+00:00",
    )


@pytest.fixture
def sample_jobs(sample_job, sample_job_topcv) -> list[Job]:
    return [
        sample_job,
        sample_job_topcv,
        Job(
            title="Java Intern - Backend Team",
            link="https://www.vietnamworks.com/java-intern-backend-123",
            source="vietnamworks",
            found_at="2026-04-05T12:00:00+00:00",
        ),
    ]


# ──────────────────────────────────────────────
# Temp database path
# ──────────────────────────────────────────────
@pytest.fixture
def tmp_db_path(tmp_path) -> str:
    """Return a temporary database file path."""
    return str(tmp_path / "test_jobs.json")
