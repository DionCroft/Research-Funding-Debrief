"""SQLite persistence for funding opportunities."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from app.config import DEFAULT_DATABASE_PATH
from app.models import FundingOpportunity


logger = logging.getLogger(__name__)


ADDITIONAL_COLUMNS: dict[str, str] = {
    "funding_type": "TEXT",
    "eligibility": "TEXT",
    "location": "TEXT",
    "categories": "TEXT NOT NULL DEFAULT '[]'",
    "bid_summary": "TEXT NOT NULL DEFAULT '[]'",
    "content_hash": "TEXT",
    "last_alerted_at": "TEXT",
    "status_changed_at": "TEXT",
    "last_change_summary": "TEXT NOT NULL DEFAULT '[]'",
}


@dataclass
class StoreResult:
    """Result of storing an opportunity."""

    opportunity: FundingOpportunity
    status: str
    changes: list[str]

    @property
    def is_new(self) -> bool:
        return self.status == "new"

    @property
    def is_changed(self) -> bool:
        return self.status == "changed"


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
                    funding_type TEXT,
                    eligibility TEXT,
                    location TEXT,
                    opening_date TEXT,
                    closing_date TEXT,
                    published_date TEXT,
                    url TEXT,
                    categories TEXT NOT NULL DEFAULT '[]',
                    matched_keywords TEXT NOT NULL DEFAULT '[]',
                    bid_summary TEXT NOT NULL DEFAULT '[]',
                    relevance_score INTEGER NOT NULL DEFAULT 0,
                    content_hash TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_alerted_at TEXT,
                    status_changed_at TEXT,
                    last_change_summary TEXT NOT NULL DEFAULT '[]',
                    UNIQUE(source, external_id)
                )
                """
            )
            self._migrate(connection)
            connection.commit()

    def store_opportunity(self, opportunity: FundingOpportunity) -> StoreResult:
        """Store an opportunity.

        Returns a StoreResult describing whether the opportunity is new,
        changed, or already known.
        """

        now = utc_now_iso()
        opportunity.first_seen_at = opportunity.first_seen_at or now
        opportunity.last_seen_at = now
        content_hash = compute_content_hash(opportunity)

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
                            funding_type,
                            eligibility,
                            location,
                            opening_date,
                            closing_date,
                            published_date,
                            url,
                            categories,
                            matched_keywords,
                            bid_summary,
                            relevance_score,
                            content_hash,
                            first_seen_at,
                            last_seen_at,
                            last_change_summary
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        self._to_insert_row(opportunity, content_hash, []),
                    )
                    connection.commit()
                    return StoreResult(opportunity=opportunity, status="new", changes=[])
                except sqlite3.IntegrityError:
                    existing = connection.execute(
                        """
                        SELECT *
                        FROM opportunities
                        WHERE source = ? AND external_id = ?
                        """,
                        (opportunity.source, opportunity.external_id),
                    ).fetchone()
                    if existing:
                        opportunity.first_seen_at = existing["first_seen_at"]

                    changes = _change_summary(existing, opportunity, content_hash) if existing else []
                    status_changed_at = (
                        now
                        if changes and any(change.startswith("Status") for change in changes)
                        else existing["status_changed_at"]
                        if existing
                        else None
                    )

                    connection.execute(
                        """
                        UPDATE opportunities
                        SET title = ?,
                            funder = ?,
                            summary = ?,
                            amount = ?,
                            status = ?,
                            funding_type = ?,
                            eligibility = ?,
                            location = ?,
                            opening_date = ?,
                            closing_date = ?,
                            published_date = ?,
                            url = ?,
                            categories = ?,
                            matched_keywords = ?,
                            bid_summary = ?,
                            relevance_score = ?,
                            content_hash = ?,
                            last_seen_at = ?,
                            last_change_summary = ?,
                            status_changed_at = ?
                        WHERE source = ? AND external_id = ?
                        """,
                        (
                            opportunity.title,
                            opportunity.funder,
                            opportunity.summary,
                            opportunity.amount,
                            opportunity.status,
                            opportunity.funding_type,
                            opportunity.eligibility,
                            opportunity.location,
                            opportunity.opening_date,
                            opportunity.closing_date,
                            opportunity.published_date,
                            opportunity.url,
                            json.dumps(opportunity.categories),
                            json.dumps(opportunity.matched_keywords),
                            json.dumps(opportunity.bid_summary),
                            opportunity.relevance_score,
                            content_hash,
                            opportunity.last_seen_at,
                            json.dumps(changes),
                            status_changed_at,
                            opportunity.source,
                            opportunity.external_id,
                        ),
                    )
                    connection.commit()
                    opportunity.change_summary = changes
                    if changes:
                        return StoreResult(
                            opportunity=opportunity,
                            status="changed",
                            changes=changes,
                        )
                    return StoreResult(opportunity=opportunity, status="known", changes=[])
        except sqlite3.Error:
            logger.exception("Database error while storing opportunity: %s", opportunity.title)
            raise

    def store_opportunities(
        self, opportunities: Iterable[FundingOpportunity]
    ) -> tuple[list[FundingOpportunity], list[FundingOpportunity], list[FundingOpportunity]]:
        """Store opportunities and split them into new, changed, and known lists."""

        new_opportunities: list[FundingOpportunity] = []
        changed_opportunities: list[FundingOpportunity] = []
        known_opportunities: list[FundingOpportunity] = []

        for opportunity in opportunities:
            result = self.store_opportunity(opportunity)
            if result.is_new:
                new_opportunities.append(opportunity)
            elif result.is_changed:
                changed_opportunities.append(opportunity)
            else:
                known_opportunities.append(opportunity)

        return new_opportunities, changed_opportunities, known_opportunities

    def seen_timestamps(self, source: str, external_id: str) -> tuple[str | None, str | None]:
        """Return stored first/last seen timestamps for an opportunity."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT first_seen_at, last_seen_at
                FROM opportunities
                WHERE source = ? AND external_id = ?
                """,
                (source, external_id),
            ).fetchone()

        if not row:
            return None, None
        return row["first_seen_at"], row["last_seen_at"]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_insert_row(
        opportunity: FundingOpportunity,
        content_hash: str,
        changes: list[str],
    ) -> tuple[object, ...]:
        return (
            opportunity.source,
            opportunity.external_id,
            opportunity.title,
            opportunity.funder,
            opportunity.summary,
            opportunity.amount,
            opportunity.status,
            opportunity.funding_type,
            opportunity.eligibility,
            opportunity.location,
            opportunity.opening_date,
            opportunity.closing_date,
            opportunity.published_date,
            opportunity.url,
            json.dumps(opportunity.categories),
            json.dumps(opportunity.matched_keywords),
            json.dumps(opportunity.bid_summary),
            opportunity.relevance_score,
            content_hash,
            opportunity.first_seen_at,
            opportunity.last_seen_at,
            json.dumps(changes),
        )

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(opportunities)").fetchall()
        }
        for column, definition in ADDITIONAL_COLUMNS.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE opportunities ADD COLUMN {column} {definition}"
                )


def compute_content_hash(opportunity: FundingOpportunity) -> str:
    """Hash fields that should trigger a changed-opportunity alert."""

    payload = {
        "title": opportunity.title,
        "funder": opportunity.funder,
        "summary": opportunity.summary,
        "amount": opportunity.amount,
        "status": opportunity.status,
        "funding_type": opportunity.funding_type,
        "eligibility": opportunity.eligibility,
        "location": opportunity.location,
        "opening_date": opportunity.opening_date,
        "closing_date": opportunity.closing_date,
        "published_date": opportunity.published_date,
        "url": opportunity.url,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return sha256(encoded).hexdigest()


def _change_summary(
    existing: sqlite3.Row | None,
    opportunity: FundingOpportunity,
    new_hash: str,
) -> list[str]:
    if not existing:
        return []
    old_hash = existing["content_hash"]
    if not old_hash or old_hash == new_hash:
        return []

    watched_fields = {
        "title": ("Title", opportunity.title),
        "status": ("Status", opportunity.status),
        "amount": ("Amount", opportunity.amount),
        "opening_date": ("Opening date", opportunity.opening_date),
        "closing_date": ("Closing date", opportunity.closing_date),
        "funding_type": ("Funding type", opportunity.funding_type),
        "eligibility": ("Eligibility", opportunity.eligibility),
        "url": ("URL", opportunity.url),
    }
    changes: list[str] = []
    for column, (label, new_value) in watched_fields.items():
        old_value = existing[column]
        if (old_value or "") != (new_value or ""):
            changes.append(f"{label} changed")

    return changes or ["Details changed"]
