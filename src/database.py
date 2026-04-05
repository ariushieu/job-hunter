"""
Database module - TinyDB-based deduplication for job listings.
"""

import logging
from pathlib import Path

from tinydb import TinyDB, Query

from src.scraper import Job

logger = logging.getLogger(__name__)


class JobDatabase:
    """Persistent job storage with deduplication by link URL."""

    def __init__(self, db_path: str) -> None:
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db = TinyDB(db_path, indent=2, ensure_ascii=False, encoding="utf-8")
        self._table = self._db.table("jobs")
        self._query = Query()

        logger.info("Database opened: %s (%d records)", db_path, len(self._table))

    def is_new(self, job: Job) -> bool:
        """Check if a job has NOT been seen before (by link URL)."""
        result = self._table.search(self._query.link == job.link)
        return len(result) == 0

    def save(self, job: Job) -> None:
        """Insert a job record. Caller should check is_new() first."""
        self._table.insert(job.to_dict())
        logger.debug("Saved job: %s (%s)", job.title[:50], job.source)

    def save_if_new(self, job: Job) -> bool:
        """Save job only if it's new. Returns True if saved, False if duplicate."""
        if self.is_new(job):
            self.save(job)
            return True
        return False

    def get_all(self) -> list[dict]:
        """Return all stored job records (for debugging/export)."""
        return self._table.all()

    def count(self) -> int:
        """Return the total number of stored jobs."""
        return len(self._table)

    def close(self) -> None:
        """Close the database."""
        self._db.close()
        logger.info("Database closed")
