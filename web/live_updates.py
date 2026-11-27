"""Generate the static live funding snapshot used by the GitHub Pages front page."""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, time
from email.utils import format_datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.categories import category_names
from app.config import PUBLIC_JSON_PATH, PUBLIC_RSS_PATH, PUBLIC_SITE_URL, load_config
from app.database import OpportunityDatabase
from app.filters import score_opportunities
from app.models import FundingOpportunity
from app.report import EXPIRING_SOON_DAYS, parse_opportunity_date
from app.sources.health import SourceCheck, fetch_sources
from app.sources.registry import SOURCE_NAMES, build_sources


MAX_FEATURED_ITEMS = 60
NEW_DAYS = 7
logger = logging.getLogger(__name__)
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
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    config = load_config()
    database = OpportunityDatabase(config.database_path)
    database.initialise()
    sources = build_sources(config.enabled_sources, config)
    if not sources:
        logger.error("No valid funding sources are configured.")
        return 1
    fetched, source_checks = fetch_sources(sources)
    scored = score_opportunities(fetched, config.keywords)
    database.store_opportunities(scored)
    write_live_updates(scored, database, source_checks)
    return 0


def write_live_updates(
    scored: list[FundingOpportunity],
    database: OpportunityDatabase,
    source_checks: dict[str, SourceCheck],
    output_path: Path = PUBLIC_JSON_PATH,
    rss_output_path: Path = PUBLIC_RSS_PATH,
    today: date | None = None,
) -> None:
    """Publish fresh results plus the last verified results from failing sources."""

    today = today or date.today()
    unverified_sources = {name for name, check in source_checks.items() if check.status != "healthy"}
    previous = _read_previous_snapshot(output_path) if unverified_sources else {}
    verified_sources = len(source_checks) - len(unverified_sources)
    if not verified_sources and not previous:
        raise RuntimeError("No source could be verified and no previous snapshot is available.")

    active = _unique([opportunity for opportunity in scored if not _is_closed(opportunity)])
    all_items = [_serialise_opportunity(opportunity, today, database) for opportunity in active]
    previous_items = previous.get("allItems", previous.get("items", []))
    for item in previous_items:
        if item.get("rawSource") in unverified_sources:
            retained = _retain_item(item, today)
            if retained is not None:
                all_items.append(retained)

    all_items.sort(key=_snapshot_sort_key)
    featured = all_items[:MAX_FEATURED_ITEMS]
    source_counts = Counter(str(item["source"]) for item in all_items)

    payload = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {
            "trackedCalls": len(all_items),
            "featuredCalls": len(featured),
            "rssCalls": len(all_items),
            "closingSoon": sum("Closing soon" in _as_list(item["statusLabels"]) for item in all_items),
            "sourcesScanned": len(source_checks),
            "sourcesVerified": verified_sources,
            "topicCategories": len(category_names()),
        },
        "items": featured,
        "allItems": all_items,
        "sourceCounts": source_counts,
        "sourceHealth": _source_health(source_checks, previous, source_counts),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rss_output_path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_path.parent) as json_dir:
        with TemporaryDirectory(dir=rss_output_path.parent) as rss_dir:
            staged_json = Path(json_dir) / output_path.name
            staged_rss = Path(rss_dir) / rss_output_path.name
            staged_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            _write_rss_feed(payload, staged_rss)
            staged_rss.replace(rss_output_path)
            staged_json.replace(output_path)

    print(f"Wrote {output_path}")
    print(f"Wrote {rss_output_path}")


def _read_previous_snapshot(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict) or not isinstance(
        payload.get("allItems", payload.get("items")), list
    ):
        raise ValueError(f"Previous funding snapshot has an invalid structure: {path}")
    return payload


def _source_health(
    checks: dict[str, SourceCheck], previous: dict, counts: Counter[str]
) -> list[dict[str, object]]:
    previous_successes = {
        row["rawSource"]: row["lastSuccessAt"] for row in previous.get("sourceHealth", [])
    }
    # The older snapshot format only recorded the build time and counts by source.
    if "sourceHealth" not in previous:
        previous_successes = {
            name: previous.get("generatedAt")
            for name in checks
            if _source_label(name) in previous.get("sourceCounts", {})
        }

    health = []
    for name in dict.fromkeys((*SOURCE_NAMES, *checks)):
        check = checks.get(name)
        label = _source_label(name)
        last_success_at = previous_successes.get(name) if check else None
        if check and check.status == "healthy":
            last_success_at = check.checked_at
        health.append(
            {
                "source": label,
                "rawSource": name,
                "status": check.status if check else "disabled",
                "lastCheckedAt": check.checked_at if check else None,
                "lastSuccessAt": last_success_at,
                "callCount": counts[label],
            }
        )
    return health


def _retain_item(item: dict, today: date) -> dict | None:
    closing = _item_closing_date(item)
    days_left = (closing - today).days if closing else None
    if days_left is not None and days_left < 0:
        return None
    labels = _status_labels(
        item.get("firstSeenAt"),
        today,
        days_left,
        "Ongoing" in item.get("statusLabels", []),
    )
    return {
        **item,
        "status": " · ".join(labels),
        "statusLabels": labels,
        "urgency": _urgency_label(days_left),
        "closingDate": closing.isoformat() if closing else None,
        "sourceStale": True,
    }


def _item_closing_date(item: dict) -> date | None:
    return parse_opportunity_date(item.get("closingDate") or item.get("deadline"))


def _snapshot_sort_key(item: dict) -> tuple[int, int, str]:
    closing = _item_closing_date(item)
    ordinal = closing.toordinal() if closing else date.max.toordinal()
    return ordinal, -int(item["relevanceScore"]), str(item["title"]).lower()


def _write_rss_feed(payload: dict[str, object], output_path: Path) -> None:
    """Write an RSS view of the live updates for no-premium Power Automate flows."""

    generated_at = _parse_datetime(str(payload["generatedAt"]))
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Research Funding Debrief"
    ET.SubElement(channel, "link").text = PUBLIC_SITE_URL
    ET.SubElement(channel, "description").text = (
        "Live research funding opportunities for personalised briefings."
    )
    ET.SubElement(channel, "language").text = "en-gb"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(generated_at)

    for item in payload.get("allItems") or payload.get("items") or []:
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
    url = str(item.get("url") or PUBLIC_SITE_URL)

    ET.SubElement(entry, "title").text = title
    ET.SubElement(entry, "link").text = url
    ET.SubElement(entry, "guid", {"isPermaLink": "false"}).text = url or f"{source}: {title}"
    published_at = str(item.get("publishedAt") or "")
    first_seen_at = str(item.get("firstSeenAt") or "")
    ET.SubElement(entry, "pubDate").text = format_datetime(
        _parse_datetime(published_at, fallback=_parse_datetime(first_seen_at, generated_at))
    )
    ET.SubElement(entry, "description").text = _rss_description(item)
    ET.SubElement(entry, "publishedDate").text = str(
        item.get("publishedLabel") or "Not provided by source"
    )
    ET.SubElement(entry, "firstSeenAt").text = first_seen_at or "Unknown"

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
        f"Published: {item.get('publishedLabel') or 'Not provided by source'}",
        f"Topics: {_join_feed_values(item.get('topics'))}",
        f"Opportunity types: {_join_feed_values(item.get('opportunityTypes'))}",
        f"Relevance: {item.get('relevanceLevel') or 'Send me a broad scan'}",
        f"First seen: {item.get('firstSeenAt') or 'Unknown'}",
    ]
    if item.get("sourceStale"):
        lines.append("Source freshness: Retained from the last verified snapshot")
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
            parsed_date = parse_opportunity_date(value)
            if parsed_date:
                return datetime.combine(parsed_date, time.min).astimezone()
    return fallback or datetime.now().astimezone()


def _serialise_opportunity(
    opportunity: FundingOpportunity,
    today: date,
    database: OpportunityDatabase,
) -> dict[str, object]:
    closing = parse_opportunity_date(opportunity.closing_date)
    days_left = (closing - today).days if closing else None
    first_seen_at, last_seen_at = database.seen_timestamps(
        opportunity.source,
        opportunity.external_id,
    )
    opportunity.first_seen_at = first_seen_at
    opportunity.last_seen_at = last_seen_at
    status_labels = _status_labels(first_seen_at, today, days_left, _is_ongoing(opportunity))

    return {
        "status": " · ".join(status_labels),
        "statusLabels": status_labels,
        "title": opportunity.title,
        "source": _source_label(opportunity.source),
        "rawSource": opportunity.source,
        "deadline": _deadline_label(opportunity),
        "closingDate": closing.isoformat() if closing else None,
        "urgency": _urgency_label(days_left),
        "publishedAt": opportunity.published_date or "",
        "publishedLabel": _published_label(opportunity),
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


def _deadline_label(opportunity: FundingOpportunity) -> str:
    raw_deadline = opportunity.closing_date or "No deadline parsed"
    if len(raw_deadline) <= 90:
        return raw_deadline

    closing = parse_opportunity_date(raw_deadline)
    if not closing:
        return raw_deadline[:87].rstrip() + "..."

    return f"{closing.day} {closing.strftime('%B %Y')}"


def _published_label(opportunity: FundingOpportunity) -> str:
    raw_published = opportunity.published_date or ""
    if not raw_published:
        return "Not provided by source"

    published = parse_opportunity_date(raw_published)
    if published:
        return f"{published.day} {published.strftime('%B %Y')}"
    return raw_published


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
    first_seen_at: str | None,
    today: date,
    days_left: int | None,
    ongoing: bool,
) -> list[str]:
    labels = ["New" if _is_new(first_seen_at, today) else "Seen"]
    if days_left is not None and 0 <= days_left <= EXPIRING_SOON_DAYS:
        labels.append("Closing soon")
    if ongoing:
        labels.append("Ongoing")
    return labels


def _is_new(first_seen_at: str | None, today: date) -> bool:
    if not first_seen_at:
        return True
    try:
        first_seen = datetime.fromisoformat(first_seen_at).date()
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
