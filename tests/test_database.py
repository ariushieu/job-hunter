"""
Unit tests for the database module (TinyDB deduplication).
"""

import pytest

from src.database import JobDatabase
from src.scraper import Job


class TestJobDatabase:
    """Test the dedup logic - this is the core business logic."""

    def test_new_job_is_detected(self, tmp_db_path, sample_job):
        """A brand new job should be detected as new."""
        db = JobDatabase(tmp_db_path)
        assert db.is_new(sample_job) is True
        db.close()

    def test_saved_job_is_not_new(self, tmp_db_path, sample_job):
        """After saving, the same job should NOT be new."""
        db = JobDatabase(tmp_db_path)

        db.save(sample_job)
        assert db.is_new(sample_job) is False

        db.close()

    def test_save_if_new_returns_true_for_new(self, tmp_db_path, sample_job):
        """save_if_new should return True and save a new job."""
        db = JobDatabase(tmp_db_path)

        result = db.save_if_new(sample_job)
        assert result is True
        assert db.count() == 1

        db.close()

    def test_save_if_new_returns_false_for_duplicate(self, tmp_db_path, sample_job):
        """save_if_new should return False for a duplicate job."""
        db = JobDatabase(tmp_db_path)

        db.save_if_new(sample_job)
        result = db.save_if_new(sample_job)
        assert result is False
        assert db.count() == 1  # Still only 1 record

        db.close()

    def test_different_links_are_different_jobs(self, tmp_db_path):
        """Two jobs with different links should both be saved."""
        db = JobDatabase(tmp_db_path)

        job1 = Job(title="Same Title", link="https://example.com/job-1", source="itviec")
        job2 = Job(title="Same Title", link="https://example.com/job-2", source="itviec")

        assert db.save_if_new(job1) is True
        assert db.save_if_new(job2) is True
        assert db.count() == 2

        db.close()

    def test_same_link_different_title_is_duplicate(self, tmp_db_path):
        """Dedup is by link, not title. Same link = duplicate."""
        db = JobDatabase(tmp_db_path)

        job1 = Job(title="Title Version 1", link="https://example.com/job-1", source="itviec")
        job2 = Job(title="Title Version 2", link="https://example.com/job-1", source="itviec")

        assert db.save_if_new(job1) is True
        assert db.save_if_new(job2) is False
        assert db.count() == 1

        db.close()

    def test_multiple_jobs_batch(self, tmp_db_path, sample_jobs):
        """Save a batch of jobs and verify count."""
        db = JobDatabase(tmp_db_path)

        saved = 0
        for job in sample_jobs:
            if db.save_if_new(job):
                saved += 1

        assert saved == len(sample_jobs)
        assert db.count() == len(sample_jobs)

        db.close()

    def test_get_all_returns_saved_data(self, tmp_db_path, sample_job):
        """get_all should return the data we saved."""
        db = JobDatabase(tmp_db_path)

        db.save(sample_job)
        all_jobs = db.get_all()

        assert len(all_jobs) == 1
        assert all_jobs[0]["title"] == sample_job.title
        assert all_jobs[0]["link"] == sample_job.link
        assert all_jobs[0]["source"] == sample_job.source

        db.close()

    def test_persistence_across_reopens(self, tmp_db_path, sample_job):
        """Data should persist after closing and reopening the DB."""
        # First session: save
        db1 = JobDatabase(tmp_db_path)
        db1.save(sample_job)
        db1.close()

        # Second session: verify
        db2 = JobDatabase(tmp_db_path)
        assert db2.is_new(sample_job) is False
        assert db2.count() == 1
        db2.close()

    def test_empty_db_count(self, tmp_db_path):
        """A fresh database should have 0 records."""
        db = JobDatabase(tmp_db_path)
        assert db.count() == 0
        db.close()

    def test_creates_parent_directory(self, tmp_path):
        """Database should create parent dirs if they don't exist."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "jobs.json")
        db = JobDatabase(deep_path)
        assert db.count() == 0
        db.close()
