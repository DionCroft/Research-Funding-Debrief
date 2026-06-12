"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FundingOpportunity:
    """Standard internal representation of a funding opportunity."""

    source: str
    external_id: str
    title: str
    funder: str | None = None
    summary: str | None = None
    amount: str | None = None
    status: str | None = None
    opening_date: str | None = None
    closing_date: str | None = None
    published_date: str | None = None
    url: str | None = None
    matched_keywords: list[str] = field(default_factory=list)
    relevance_score: int = 0
    first_seen_at: str | None = None
    last_seen_at: str | None = None

    def display_funder(self) -> str:
        """Return a display-safe funder value."""

        return self.funder or "Unknown"
