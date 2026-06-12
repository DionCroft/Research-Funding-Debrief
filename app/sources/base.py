"""Base interface for funding sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import FundingOpportunity


class FundingSource(ABC):
    """Abstract base class for all funding sources."""

    name: str

    @abstractmethod
    def fetch(self) -> list[FundingOpportunity]:
        """Fetch and parse funding opportunities."""
