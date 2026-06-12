"""SQLite persistence for funding opportunities."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.config import DEFAULT_DATABASE_PATH
from app.models import FundingOpportunity


logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class OpportunityDatabase:
    """Small SQLite wrapper for opportunity deduplication."""

    def __init__(self, database_path: Path | str = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)

    def initialise(self) -> None:
        """Create the database and opportunities table if needed."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    funder TEXT,
                    summary TEXT,
                    amount TEXT,
                    status TEXT,
                    opening_date TEXT,
                    closing_date TEXT,
                    published_date TEXT,
                    url TEXT,
                    matched_keywords TEXT NOT NULL DEFAULT '[]',
                    relevance_score INTEGER NOT NULL DEFAULT 0,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    UNIQUE(source, external_id)
                )
                """
            )
            connection.commit()

    def store_opportunity(self, opportunity: FundingOpportunity) -> bool:
        """Store an opportunity.

        Returns True when the opportunity is newly inserted, or False when it
        was already known and only last_seen_at was updated.
        """

        now = utc_now_iso()
        opportunity.first_seen_at = opportunity.first_seen_at or now
        opportunity.last_seen_at = now

        try:
            with self._connect() as connection:
                try:
                    connection.execute(
                        """
                        INSERT INTO opportunities (
                            source,
                            external_id,
                            title,
                            funder,
                            summary,
                            amount,
                            status,
                            opening_date,
                            closing_date,
                            published_date,
                            url,
                            matched_keywords,
                            relevance_score,
                            first_seen_at,
                            last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        self._to_row(opportunity),
                    )
                    connection.commit()
                    return True
                except sqlite3.IntegrityError:
                    existing = connection.execute(
                        """
                        SELECT first_seen_at
                        FROM opportunities
                        WHERE source = ? AND external_id = ?
                        """,
                        (opportunity.source, opportunity.external_id),
                    ).fetchone()
                    if existing:
                        opportunity.first_seen_at = existing["first_seen_at"]

                    connection.execute(
                        """
                        UPDATE opportunities
                        SET title = ?,
                            funder = ?,
                            summary = ?,
                            amount = ?,
                            status = ?,
                            opening_date = ?,
                            closing_date = ?,
                            published_date = ?,
                            url = ?,
                            matched_keywords = ?,
                            relevance_score = ?,
                            last_seen_at = ?
                        WHERE source = ? AND external_id = ?
                        """,
                        (
                            opportunity.title,
                            opportunity.funder,
                            opportunity.summary,
                            opportunity.amount,
                            opportunity.status,
                            opportunity.opening_date,
                            opportunity.closing_date,
                            opportunity.published_date,
                            opportunity.url,
                            json.dumps(opportunity.matched_keywords),
                            opportunity.relevance_score,
                            opportunity.last_seen_at,
                            opportunity.source,
                            opportunity.external_id,
                        ),
                    )
                    connection.commit()
                    return False
        except sqlite3.Error:
            logger.exception("Database error while storing opportunity: %s", opportunity.title)
            raise

    def store_opportunities(
        self, opportunities: Iterable[FundingOpportunity]
    ) -> tuple[list[FundingOpportunity], list[FundingOpportunity]]:
        """Store opportunities and split them into new and already-known lists."""

        new_opportunities: list[FundingOpportunity] = []
        known_opportunities: list[FundingOpportunity] = []

        for opportunity in opportunities:
            if self.store_opportunity(opportunity):
                new_opportunities.append(opportunity)
            else:
                known_opportunities.append(opportunity)

        return new_opportunities, known_opportunities

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_row(opportunity: FundingOpportunity) -> tuple[object, ...]:
        return (
            opportunity.source,
            opportunity.external_id,
            opportunity.title,
            opportunity.funder,
            opportunity.summary,
            opportunity.amount,
            opportunity.status,
            opportunity.opening_date,
            opportunity.closing_date,
            opportunity.published_date,
            opportunity.url,
            json.dumps(opportunity.matched_keywords),
            opportunity.relevance_score,
            opportunity.first_seen_at,
            opportunity.last_seen_at,
        )
