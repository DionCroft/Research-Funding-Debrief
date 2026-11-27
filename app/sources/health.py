"""Fetch funding sources independently and record what each check established."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.models import FundingOpportunity
from app.sources.base import FundingSource


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceCheck:
    status: Literal["healthy", "empty", "failed"]
    checked_at: str


def fetch_sources(
    sources: Iterable[FundingSource],
) -> tuple[list[FundingOpportunity], dict[str, SourceCheck]]:
    opportunities: list[FundingOpportunity] = []
    checks: dict[str, SourceCheck] = {}
    for source in sources:
        status: Literal["healthy", "empty", "failed"]
        try:
            found = source.fetch()
        except Exception:
            logger.exception("Funding source check failed: %s", source.name)
            status = "failed"
        else:
            opportunities.extend(found)
            status = "healthy" if found else "empty"
            if not found:
                logger.warning("Funding source returned no records: %s", source.name)
        checks[source.name] = SourceCheck(
            status, datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
    return opportunities, checks
