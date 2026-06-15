"""Generate the static live funding snapshot used by the GitHub Pages front page."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_config
from app.filters import score_opportunities
from app.models import FundingOpportunity
from app.report import EXPIRING_SOON_DAYS, parse_opportunity_date
from app.sources.registry import SOURCE_FACTORIES, build_sources


OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "live-updates.json"
MAX_ITEMS = 8
TOPIC_CATEGORY_COUNT = 30


def main() -> int:
    config = load_config()
    fetched: list[FundingOpportunity] = []
    source_names = list(SOURCE_FACTORIES)

    for source in build_sources(source_names, config):
        fetched.extend(source.fetch())

    scored = score_opportunities(fetched, config.keywords)
    today = date.today()
    active = [opportunity for opportunity in scored if not _is_closed(opportunity)]
    closing_soon = [
        opportunity
        for opportunity in active
        if _days_left(opportunity, today) is not None
        and 0 <= _days_left(opportunity, today) <= EXPIRING_SOON_DAYS
    ]
    relevant = [
        opportunity
        for opportunity in active
        if opportunity.relevance_score >= config.relevant_score_threshold
    ]
    featured = _unique(closing_soon + relevant + active)[:MAX_ITEMS]

    payload = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {
            "trackedCalls": len(active),
            "closingSoon": len(closing_soon),
            "sourcesScanned": len(source_names),
            "topicCategories": TOPIC_CATEGORY_COUNT,
        },
        "items": [_serialise_opportunity(opportunity, today) for opportunity in featured],
        "sourceCounts": Counter(opportunity.source for opportunity in scored),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


def _serialise_opportunity(opportunity: FundingOpportunity, today: date) -> dict[str, object]:
    days_left = _days_left(opportunity, today)
    if days_left is not None and 0 <= days_left <= EXPIRING_SOON_DAYS:
        status = "Closing soon"
    else:
        status = opportunity.status or "Open"

    return {
        "status": status,
        "title": opportunity.title,
        "source": opportunity.source,
        "deadline": opportunity.closing_date or "No deadline parsed",
        "urgency": _urgency_label(days_left),
        "url": opportunity.url or "",
        "topics": opportunity.categories[:3],
    }


def _unique(opportunities: list[FundingOpportunity]) -> list[FundingOpportunity]:
    seen: set[tuple[str, str]] = set()
    unique_opportunities: list[FundingOpportunity] = []
    for opportunity in sorted(opportunities, key=_sort_key):
        key = (opportunity.source, opportunity.external_id)
        if key in seen:
            continue
        seen.add(key)
        unique_opportunities.append(opportunity)
    return unique_opportunities


def _sort_key(opportunity: FundingOpportunity) -> tuple[int, int, str]:
    closing = parse_opportunity_date(opportunity.closing_date)
    ordinal = closing.toordinal() if closing else date.max.toordinal()
    return (ordinal, -opportunity.relevance_score, opportunity.title.lower())


def _days_left(opportunity: FundingOpportunity, today: date) -> int | None:
    closing = parse_opportunity_date(opportunity.closing_date)
    if not closing:
        return None
    return (closing - today).days


def _urgency_label(days_left: int | None) -> str:
    if days_left is None:
        return "Deadline not parsed"
    if days_left < 0:
        return "Deadline passed"
    if days_left == 0:
        return "Closes today"
    if days_left == 1:
        return "1 day left"
    return f"{days_left} days left"


def _is_closed(opportunity: FundingOpportunity) -> bool:
    return "closed" in (opportunity.status or "").lower()


if __name__ == "__main__":
    raise SystemExit(main())
