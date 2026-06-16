"""Generate the static live funding snapshot used by the GitHub Pages front page."""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.categories import category_names
from app.config import load_config
from app.database import OpportunityDatabase
from app.filters import score_opportunities
from app.models import FundingOpportunity
from app.report import EXPIRING_SOON_DAYS, parse_opportunity_date
from app.sources.registry import SOURCE_FACTORIES, build_sources


OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "live-updates.json"
RSS_OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "live-updates.xml"
SITE_URL = "https://dioncroft.github.io/Research-Funding-Debrief/"
MAX_ITEMS = 60
NEW_DAYS = 7
SOURCE_LABELS = {
    "Find a Grant": "GOV.UK Find a Grant",
}
OPPORTUNITY_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Research grants": ("research grant", "researcher-led", "research programme", "research"),
    "Innovation grants": ("innovation", "competition", "innovate"),
    "Fellowships": ("fellowship", "professorship"),
    "Studentships / PhD funding": ("studentship", "doctoral", "phd", "ph.d"),
    "Knowledge Transfer Partnerships": ("knowledge transfer", "ktp"),
    "Industry collaboration": ("industry", "business collaboration", "collaboration"),
    "Capital / equipment funding": ("capital", "equipment", "infrastructure", "facility"),
    "Travel / networking funding": ("travel", "networking", "workshop", "conference"),
    "Commercialisation / spinout support": (
        "commercialisation",
        "commercialization",
        "spinout",
        "spin-out",
        "entrepreneur",
        "translation",
    ),
}


def main() -> int:
    config = load_config()
    database = OpportunityDatabase(config.database_path)
    database.initialise()
    fetched: list[FundingOpportunity] = []
    source_names = list(SOURCE_FACTORIES)

    for source in build_sources(source_names, config):
        fetched.extend(source.fetch())

    scored = score_opportunities(fetched, config.keywords)
    database.store_opportunities(scored)
    write_live_updates(
        scored,
        database,
        source_names,
        relevant_score_threshold=config.relevant_score_threshold,
    )
    return 0


def write_live_updates(
    scored: list[FundingOpportunity],
    database: OpportunityDatabase,
    source_names: list[str],
    relevant_score_threshold: int = 4,
    output_path: Path = OUTPUT_PATH,
    rss_output_path: Path = RSS_OUTPUT_PATH,
    today: date | None = None,
) -> None:
    """Write the static live funding snapshots for the front page and RSS feed."""

    today = today or date.today()
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
        if opportunity.relevance_score >= relevant_score_threshold
    ]
    featured = _unique(closing_soon + relevant + active)[:MAX_ITEMS]

    payload = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {
            "trackedCalls": len(active),
            "closingSoon": len(closing_soon),
            "sourcesScanned": len(source_names),
            "topicCategories": len(category_names()),
        },
        "items": [
            _serialise_opportunity(opportunity, today, database)
            for opportunity in featured
        ],
        "sourceCounts": Counter(_source_label(opportunity.source) for opportunity in scored),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {output_path}")

    _write_rss_feed(payload, rss_output_path)
    print(f"Wrote {rss_output_path}")


def _write_rss_feed(payload: dict[str, object], output_path: Path) -> None:
    """Write an RSS view of the live updates for no-premium Power Automate flows."""

    generated_at = _parse_datetime(str(payload["generatedAt"]))
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Research Funding Debrief"
    ET.SubElement(channel, "link").text = SITE_URL
    ET.SubElement(channel, "description").text = (
        "Live research funding opportunities for personalised briefings."
    )
    ET.SubElement(channel, "language").text = "en-gb"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(generated_at)

    for item in payload["items"]:
        if isinstance(item, dict):
            _append_rss_item(channel, item, generated_at)

    ET.indent(rss, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(rss).write(output_path, encoding="utf-8", xml_declaration=True)


def _append_rss_item(
    channel: ET.Element,
    item: dict[str, object],
    generated_at: datetime,
) -> None:
    entry = ET.SubElement(channel, "item")
    title = str(item.get("title") or "Untitled funding opportunity")
    source = str(item.get("source") or "Unknown source")
    url = str(item.get("url") or SITE_URL)

    ET.SubElement(entry, "title").text = title
    ET.SubElement(entry, "link").text = url
    ET.SubElement(entry, "guid", {"isPermaLink": "false"}).text = url or f"{source}: {title}"
    ET.SubElement(entry, "pubDate").text = format_datetime(
        _parse_datetime(str(item.get("firstSeenAt") or ""), fallback=generated_at)
    )
    ET.SubElement(entry, "description").text = _rss_description(item)

    categories = _as_list(item.get("statusLabels"))
    categories.extend(_as_list(item.get("topics")))
    categories.extend(_as_list(item.get("opportunityTypes")))
    categories.extend([source, str(item.get("relevanceLevel") or "")])
    for category in [category for category in categories if category]:
        ET.SubElement(entry, "category").text = category


def _rss_description(item: dict[str, object]) -> str:
    lines = [
        f"Source: {item.get('source') or 'Unknown source'}",
        f"Status: {item.get('status') or 'Unlabelled'}",
        f"Deadline: {item.get('deadline') or 'No deadline parsed'}",
        f"Urgency: {item.get('urgency') or 'Deadline not parsed'}",
        f"Topics: {_join_feed_values(item.get('topics'))}",
        f"Opportunity types: {_join_feed_values(item.get('opportunityTypes'))}",
        f"Relevance: {item.get('relevanceLevel') or 'Send me a broad scan'}",
        f"First seen: {item.get('firstSeenAt') or 'Unknown'}",
    ]
    return "\n".join(lines)


def _join_feed_values(value: object) -> str:
    values = _as_list(value)
    return ", ".join(values) if values else "Uncategorised"


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, tuple):
        return [str(item) for item in value if item]
    return []


def _parse_datetime(value: str, fallback: datetime | None = None) -> datetime:
    if value:
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.astimezone() if parsed.tzinfo else parsed.astimezone()
        except ValueError:
            pass
    return fallback or datetime.now().astimezone()


def _serialise_opportunity(
    opportunity: FundingOpportunity,
    today: date,
    database: OpportunityDatabase,
) -> dict[str, object]:
    days_left = _days_left(opportunity, today)
    first_seen_at, last_seen_at = database.seen_timestamps(
        opportunity.source,
        opportunity.external_id,
    )
    opportunity.first_seen_at = first_seen_at
    opportunity.last_seen_at = last_seen_at
    status_labels = _status_labels(opportunity, today, days_left)

    return {
        "status": " · ".join(status_labels),
        "statusLabels": status_labels,
        "title": opportunity.title,
        "source": _source_label(opportunity.source),
        "rawSource": opportunity.source,
        "deadline": _deadline_label(opportunity),
        "urgency": _urgency_label(days_left),
        "url": opportunity.url or "",
        "topics": opportunity.categories,
        "opportunityTypes": _opportunity_types(opportunity),
        "relevanceLevel": _relevance_level(opportunity.relevance_score),
        "relevanceScore": opportunity.relevance_score,
        "firstSeenAt": first_seen_at or "",
        "lastSeenAt": last_seen_at or "",
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


def _deadline_label(opportunity: FundingOpportunity) -> str:
    raw_deadline = opportunity.closing_date or "No deadline parsed"
    if len(raw_deadline) <= 90:
        return raw_deadline

    closing = parse_opportunity_date(raw_deadline)
    if not closing:
        return raw_deadline[:87].rstrip() + "..."

    return f"{closing.day} {closing.strftime('%B %Y')}"


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


def _status_labels(
    opportunity: FundingOpportunity,
    today: date,
    days_left: int | None,
) -> list[str]:
    labels = ["New" if _is_new(opportunity, today) else "Seen"]
    if days_left is not None and 0 <= days_left <= EXPIRING_SOON_DAYS:
        labels.append("Closing soon")
    if _is_ongoing(opportunity):
        labels.append("Ongoing")
    return labels


def _is_new(opportunity: FundingOpportunity, today: date) -> bool:
    if not opportunity.first_seen_at:
        return True
    try:
        first_seen = datetime.fromisoformat(opportunity.first_seen_at).date()
    except ValueError:
        return False
    return 0 <= (today - first_seen).days <= NEW_DAYS


def _is_ongoing(opportunity: FundingOpportunity) -> bool:
    status = (opportunity.status or "").lower()
    return "open" in status or "upcoming" in status


def _is_closed(opportunity: FundingOpportunity) -> bool:
    return "closed" in (opportunity.status or "").lower()


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source)


def _opportunity_types(opportunity: FundingOpportunity) -> list[str]:
    text = _lower_join(
        (
            opportunity.title,
            opportunity.summary,
            opportunity.funding_type,
            opportunity.status,
            *opportunity.categories,
        )
    )
    types = [
        opportunity_type
        for opportunity_type, keywords in OPPORTUNITY_TYPE_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    if not types and "Fellowships" in opportunity.categories:
        types.append("Fellowships")
    return types or ["Research grants"]


def _relevance_level(score: int) -> str:
    if score >= 8:
        return "Send me only highly relevant calls"
    if score >= 4:
        return "Send me a balanced shortlist"
    return "Send me a broad scan"


def _lower_join(values: Iterable[str | None]) -> str:
    return "\n".join(value for value in values if value).lower()


if __name__ == "__main__":
    raise SystemExit(main())
