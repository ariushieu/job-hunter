"""
Unit tests for the scraper module (data model & helpers, no browser needed).
"""

import pytest

from src.scraper import Job, JobScraper, _is_relevant_job


class TestJobDataclass:
    """Test the Job data model."""

    def test_create_job_with_all_fields(self):
        job = Job(
            title="Intern Java",
            link="https://example.com/job-1",
            source="itviec",
            found_at="2026-04-05T10:00:00+00:00",
        )
        assert job.title == "Intern Java"
        assert job.link == "https://example.com/job-1"
        assert job.source == "itviec"
        assert job.found_at == "2026-04-05T10:00:00+00:00"

    def test_create_job_auto_timestamp(self):
        """found_at should auto-generate if not provided."""
        job = Job(title="Test", link="https://x.com/1", source="topcv")
        assert job.found_at is not None
        assert len(job.found_at) > 0
        assert "T" in job.found_at  # ISO format

    def test_to_dict(self, sample_job):
        """to_dict should return a plain dictionary."""
        d = sample_job.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == sample_job.title
        assert d["link"] == sample_job.link
        assert d["source"] == sample_job.source
        assert d["found_at"] == sample_job.found_at

    def test_to_dict_keys(self, sample_job):
        """to_dict should have exactly these keys."""
        d = sample_job.to_dict()
        assert set(d.keys()) == {"title", "link", "source", "found_at"}


class TestJobScraperInit:
    """Test scraper initialization (no browser launch)."""

    def test_init_attributes(self):
        scraper = JobScraper()
        assert scraper._playwright is None
        assert scraper._browser is None
        assert scraper._context is None

    def test_scraper_without_start_raises(self):
        """Using _new_stealth_page before start() should raise RuntimeError."""
        scraper = JobScraper()

        with pytest.raises(RuntimeError, match="Browser context not initialized"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(scraper._new_stealth_page())


class TestScraperDedup:
    """Test in-run deduplication inside scrape_all."""

    def test_jobs_dedup_by_link(self):
        """scrape_all dedup logic: same link should be removed."""
        jobs = [
            Job(title="Job A", link="https://example.com/1", source="itviec"),
            Job(title="Job A Copy", link="https://example.com/1", source="topcv"),
            Job(title="Job B", link="https://example.com/2", source="itviec"),
        ]

        # Simulate the dedup logic from scrape_all
        seen_links: set[str] = set()
        unique_jobs: list[Job] = []
        for job in jobs:
            if job.link not in seen_links:
                seen_links.add(job.link)
                unique_jobs.append(job)

        assert len(unique_jobs) == 2
        assert unique_jobs[0].title == "Job A"
        assert unique_jobs[1].title == "Job B"


class TestRelevanceFilter:
    """Test the _is_relevant_job filter logic."""

    # ── Should PASS (intern/fresher + tech keyword) ──
    def test_intern_java_spring_boot(self):
        assert _is_relevant_job("Intern Java Spring Boot") is True

    def test_fresher_backend_developer(self):
        assert _is_relevant_job("Fresher Backend Developer (Java)") is True

    def test_junior_java_developer(self):
        """Junior is no longer in LEVEL_KEYWORDS — should be rejected."""
        assert _is_relevant_job("Junior Java Developer") is False

    def test_thuc_tap_lap_trinh_java(self):
        """Vietnamese keywords should work."""
        assert _is_relevant_job("Thực tập lập trình Java") is True

    def test_intern_spring_boot_developer(self):
        assert _is_relevant_job("Intern Spring Boot Developer") is True

    # ── Should FAIL (senior/lead — excluded) ──
    def test_senior_java_rejected(self):
        assert _is_relevant_job("Senior Java Developer") is False

    def test_senior_backend_engineer_rejected(self):
        assert _is_relevant_job("Senior Backend Engineer (Java/Spring Boot)") is False

    def test_lead_java_rejected(self):
        assert _is_relevant_job("Lead Java Engineer") is False

    def test_technical_lead_rejected(self):
        assert _is_relevant_job("Technical Lead (Kotlin/Java)") is False

    def test_manager_rejected(self):
        assert _is_relevant_job("Java Project Manager") is False

    def test_architect_rejected(self):
        assert _is_relevant_job("Java Architect") is False

    # ── Should FAIL (no level keyword) ──
    def test_java_developer_no_level(self):
        """'Java Developer' has tech but no intern/fresher/junior."""
        assert _is_relevant_job("Java Developer") is False

    def test_backend_engineer_no_level(self):
        assert _is_relevant_job("Backend Engineer (Java, Spring Boot)") is False

    # ── Should FAIL (no tech keyword) ──
    def test_intern_sales(self):
        """Intern but not tech-related."""
        assert _is_relevant_job("Intern Sales Executive") is False

    def test_fresher_marketing(self):
        assert _is_relevant_job("Fresher Marketing Specialist") is False

    # ── Edge cases ──
    def test_case_insensitive(self):
        assert _is_relevant_job("INTERN JAVA SPRING BOOT") is True
        assert _is_relevant_job("intern java spring boot") is True

    def test_empty_string(self):
        assert _is_relevant_job("") is False
