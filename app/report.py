"""Plain-text and Discord report generation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
import re

from app.config import Config
from app.filters import relevance_bucket
from app.models import FundingOpportunity


EXPIRING_SOON_DAYS = 30


@dataclass(frozen=True)
class Timeline:
    """Time-based slices for the daily debrief."""

    today: date
    new: list[FundingOpportunity]
    expiring_soon: list[FundingOpportunity]
    ongoing: list[FundingOpportunity]
    unknown_deadline: list[FundingOpportunity]


def generate_daily_debrief(
    fetched_opportunities: Sequence[FundingOpportunity],
    new_opportunities: Sequence[FundingOpportunity],
    changed_opportunities: Sequence[FundingOpportunity],
    known_opportunities: Sequence[FundingOpportunity],
    config: Config,
    include_known: bool = True,
    generated_at: datetime | None = None,
) -> str:
    """Generate a terminal-friendly daily funding debrief."""

    generated_at = generated_at or datetime.now().astimezone()
    relevant_new = [
        opportunity
        for opportunity in new_opportunities
        if opportunity.relevance_score >= config.relevant_score_threshold
    ]
    relevant_changed = [
        opportunity
        for opportunity in changed_opportunities
        if opportunity.relevance_score >= config.relevant_score_threshold
    ]

    high_new = _bucketed_new(new_opportunities, "high", config)
    medium_new = _bucketed_new(new_opportunities, "medium", config)
    low_new = _bucketed_new(new_opportunities, "low", config)
    changed = _sort_by_score(list(changed_opportunities))
    source_counts = Counter(opportunity.source for opportunity in fetched_opportunities)
    category_counts = _category_counts(fetched_opportunities)

    lines = [
        "Daily Research Funding Debrief",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M %Z')}".rstrip(),
        "",
        "Summary:",
        f"Fetched: {len(fetched_opportunities)}",
        f"New: {len(new_opportunities)}",
        f"Relevant new: {len(relevant_new)}",
        f"Changed: {len(changed_opportunities)}",
        f"Relevant changed: {len(relevant_changed)}",
        f"Previously seen: {len(known_opportunities)}",
    ]
    if source_counts:
        lines.append(
            "Sources: "
            + ", ".join(f"{source} {count}" for source, count in sorted(source_counts.items()))
        )
    if category_counts:
        lines.append(
            "Top categories: "
            + ", ".join(
                f"{category} {count}" for category, count in category_counts.most_common(5)
            )
        )
    lines.append("")

    if not fetched_opportunities:
        lines.append("No opportunities were fetched. The feed may be unavailable or empty.")
        return "\n".join(lines)

    timeline = build_timeline(
        fetched_opportunities=fetched_opportunities,
        new_opportunities=new_opportunities,
        config=config,
        today=generated_at.date(),
    )
    lines.extend(_timeline_section(timeline, config))

    if not relevant_new and not relevant_changed:
        lines.extend(["No relevant new or changed opportunities found today.", ""])

    lines.extend(_section("High relevance new opportunities", high_new))
    lines.extend(_section("Medium relevance new opportunities", medium_new))
    lines.extend(_section("Low relevance or unclassified new opportunities", low_new))
    lines.extend(_section("Changed opportunities", changed))

    if include_known:
        known = _sort_by_score(list(known_opportunities))
        lines.extend(
            _section(
                "Previously seen opportunities fetched today (not re-alerted)",
                known[: config.max_known_report_items],
            )
        )
        if len(known) > config.max_known_report_items:
            lines.extend([f"...and {len(known) - config.max_known_report_items} more.", ""])

    return "\n".join(lines).rstrip()


def generate_discord_debrief(
    fetched_opportunities: Sequence[FundingOpportunity],
    new_opportunities: Sequence[FundingOpportunity],
    changed_opportunities: Sequence[FundingOpportunity],
    known_opportunities: Sequence[FundingOpportunity],
    config: Config,
    generated_at: datetime | None = None,
) -> str:
    """Generate a compact Discord-friendly funding debrief."""

    generated_at = generated_at or datetime.now().astimezone()
    relevant_new = _sort_by_score(
        [
            opportunity
            for opportunity in new_opportunities
            if opportunity.relevance_score >= config.relevant_score_threshold
        ]
    )
    relevant_changed = _sort_by_score(
        [
            opportunity
            for opportunity in changed_opportunities
            if opportunity.relevance_score >= config.relevant_score_threshold
        ]
    )
    source_counts = Counter(opportunity.source for opportunity in fetched_opportunities)
    category_counts = _category_counts(fetched_opportunities)

    lines = [
        "**Research Funding Debrief**",
        f"`{generated_at.strftime('%Y-%m-%d %H:%M %Z').rstrip()}`",
        (
            f"Fetched **{len(fetched_opportunities)}** calls | "
            f"New **{len(new_opportunities)}** | "
            f"Relevant new **{len(relevant_new)}** | "
            f"Changed **{len(changed_opportunities)}** | "
            f"Seen before **{len(known_opportunities)}**"
        ),
    ]
    if source_counts:
        lines.append(
            "**Sources:** "
            + ", ".join(f"{source} {count}" for source, count in sorted(source_counts.items()))
        )
    if category_counts:
        lines.append(
            "**Top categories:** "
            + ", ".join(
                f"{category} {count}" for category, count in category_counts.most_common(3)
            )
        )
    lines.append("")

    timeline = build_timeline(
        fetched_opportunities=fetched_opportunities,
        new_opportunities=new_opportunities,
        config=config,
        today=generated_at.date(),
    )
    lines.extend(_discord_timeline_section(timeline, config))

    if not relevant_new and not relevant_changed:
        lines.append("No relevant new or changed opportunities found today.")
        if config.discord_include_known:
            known = _sort_by_score(list(known_opportunities))[: config.discord_max_items]
            lines.extend(["", "**Top previously seen matches**"])
            for index, opportunity in enumerate(known, start=1):
                lines.extend(_format_discord_opportunity(index, opportunity))
        return "\n".join(lines).rstrip()

    if relevant_new:
        lines.append("**Relevant new opportunities**")
        for index, opportunity in enumerate(relevant_new[: config.discord_max_items], start=1):
            lines.extend(_format_discord_opportunity(index, opportunity))

    if relevant_changed:
        lines.append("**Changed relevant opportunities**")
        for index, opportunity in enumerate(relevant_changed[: config.discord_max_items], start=1):
            lines.extend(_format_discord_opportunity(index, opportunity))

    return "\n".join(lines).rstrip()


def build_timeline(
    fetched_opportunities: Sequence[FundingOpportunity],
    new_opportunities: Sequence[FundingOpportunity],
    config: Config,
    today: date | None = None,
) -> Timeline:
    """Classify relevant opportunities into time-based reporting buckets."""

    today = today or date.today()
    relevant_fetched = [
        opportunity
        for opportunity in fetched_opportunities
        if opportunity.relevance_score >= config.relevant_score_threshold
        and not _is_closed(opportunity)
    ]
    relevant_new = [
        opportunity
        for opportunity in new_opportunities
        if opportunity.relevance_score >= config.relevant_score_threshold
        and not _is_closed(opportunity)
    ]

    new_keys = _opportunity_keys(relevant_new)
    expiring_soon = [
        opportunity
        for opportunity in relevant_fetched
        if _is_expiring_soon(opportunity, today)
    ]
    expiring_keys = _opportunity_keys(expiring_soon)
    ongoing = [
        opportunity
        for opportunity in relevant_fetched
        if _opportunity_key(opportunity) not in new_keys
        and _opportunity_key(opportunity) not in expiring_keys
        and _is_ongoing(opportunity, today)
    ]
    unknown_deadline = [
        opportunity
        for opportunity in ongoing
        if opportunity.closing_date and parse_opportunity_date(opportunity.closing_date) is None
    ]

    return Timeline(
        today=today,
        new=_sort_for_timeline(relevant_new, today),
        expiring_soon=_sort_for_timeline(expiring_soon, today),
        ongoing=_sort_for_timeline(ongoing, today),
        unknown_deadline=_sort_for_timeline(unknown_deadline, today),
    )


def _bucketed_new(
    opportunities: Sequence[FundingOpportunity],
    bucket: str,
    config: Config,
) -> list[FundingOpportunity]:
    return _sort_by_score(
        [
            opportunity
            for opportunity in opportunities
            if relevance_bucket(
                opportunity.relevance_score,
                config.medium_relevance_threshold,
                config.high_relevance_threshold,
            )
            == bucket
        ]
    )


def _timeline_section(timeline: Timeline, config: Config) -> list[str]:
    lines = [
        "Funding timeline:",
        (
            f"New: {len(timeline.new)} | "
            f"Expiring within {EXPIRING_SOON_DAYS} days: {len(timeline.expiring_soon)} | "
            f"Other ongoing: {len(timeline.ongoing)}"
        ),
        "",
    ]
    lines.extend(_timeline_bucket("New funding calls", timeline.new, timeline.today))
    lines.extend(
        _timeline_bucket(
            f"Expiring within {EXPIRING_SOON_DAYS} days",
            timeline.expiring_soon,
            timeline.today,
        )
    )
    lines.extend(
        _timeline_bucket(
            "Other ongoing calls",
            timeline.ongoing[: config.max_known_report_items],
            timeline.today,
        )
    )
    if len(timeline.ongoing) > config.max_known_report_items:
        lines.extend(
            [
                f"...and {len(timeline.ongoing) - config.max_known_report_items} more ongoing calls.",
                "",
            ]
        )
    if timeline.unknown_deadline:
        lines.extend(
            [
                (
                    "Note: "
                    f"{len(timeline.unknown_deadline)} ongoing call(s) have an unparsed deadline."
                ),
                "",
            ]
        )
    return lines


def _timeline_bucket(
    title: str,
    opportunities: Sequence[FundingOpportunity],
    today: date,
) -> list[str]:
    lines = [f"{title}:"]
    if not opportunities:
        lines.extend(["None.", ""])
        return lines

    for index, opportunity in enumerate(opportunities, start=1):
        lines.extend(_format_timeline_opportunity(index, opportunity, today))
    lines.append("")
    return lines


def _format_timeline_opportunity(
    index: int,
    opportunity: FundingOpportunity,
    today: date,
) -> list[str]:
    timing = _timeline_timing(opportunity, today)
    parts = [
        f"Source: {opportunity.source}",
        f"Funder: {opportunity.display_funder()}",
        f"Score: {opportunity.relevance_score}",
    ]
    if opportunity.amount:
        parts.append(f"Amount: {opportunity.amount}")
    lines = [
        f"{index}. {opportunity.title}",
        f"   {' | '.join(parts)}",
        f"   {timing}",
    ]
    if opportunity.url:
        lines.append(f"   URL: {opportunity.url}")
    return lines


def _discord_timeline_section(timeline: Timeline, config: Config) -> list[str]:
    lines = [
        "## Funding Timeline",
        (
            f"New **{len(timeline.new)}** | "
            f"Closing soon **{len(timeline.expiring_soon)}** | "
            f"Other ongoing **{len(timeline.ongoing)}**"
        ),
        "",
    ]
    lines.extend(
        _discord_timeline_bucket("New", timeline.new[: config.discord_max_items], timeline.today)
    )
    lines.extend(
        _discord_timeline_bucket(
            f"Expiring within {EXPIRING_SOON_DAYS} days",
            timeline.expiring_soon[: config.discord_max_items],
            timeline.today,
        )
    )
    lines.extend(
        _discord_timeline_bucket(
            "Other ongoing",
            timeline.ongoing[: config.discord_max_items],
            timeline.today,
        )
    )
    return lines


def _discord_timeline_bucket(
    title: str,
    opportunities: Sequence[FundingOpportunity],
    today: date,
) -> list[str]:
    lines = [f"### {title}"]
    if not opportunities:
        lines.extend(["_None._", ""])
        return lines

    for index, opportunity in enumerate(opportunities, start=1):
        lines.extend(_format_discord_timeline_opportunity(index, opportunity, today))
    lines.append("")
    return lines


def _format_discord_timeline_opportunity(
    index: int,
    opportunity: FundingOpportunity,
    today: date,
) -> list[str]:
    details = [
        _discord_source_funder(opportunity),
        _timeline_timing(opportunity, today),
        f"score {opportunity.relevance_score}",
    ]
    categories = _discord_categories(opportunity)
    if categories:
        details.append(categories)

    lines = [
        f"**{index}. {opportunity.title}**",
        f"> {' | '.join(detail for detail in details if detail)}",
    ]
    if opportunity.url:
        lines.append(f"> Link: <{opportunity.url}>")
    else:
        lines.append("> Link: not available")
    lines.append("")
    return lines


def _sort_by_score(opportunities: Sequence[FundingOpportunity]) -> list[FundingOpportunity]:
    return sorted(opportunities, key=lambda opportunity: opportunity.relevance_score, reverse=True)


def _sort_for_timeline(
    opportunities: Sequence[FundingOpportunity],
    today: date,
) -> list[FundingOpportunity]:
    return sorted(
        opportunities,
        key=lambda opportunity: (
            _sort_date(opportunity),
            -opportunity.relevance_score,
            opportunity.title.lower(),
        ),
    )


def _sort_date(opportunity: FundingOpportunity) -> date:
    closing = parse_opportunity_date(opportunity.closing_date)
    opening = parse_opportunity_date(opportunity.opening_date)
    return closing or opening or date.max


def _timeline_timing(opportunity: FundingOpportunity, today: date) -> str:
    parts: list[str] = []
    if opportunity.opening_date:
        parts.append(f"opens {opportunity.opening_date}")
    if opportunity.closing_date:
        closing_date = parse_opportunity_date(opportunity.closing_date)
        if closing_date:
            days_left = (closing_date - today).days
            days_label = "today" if days_left == 0 else f"{days_left} days left"
            parts.append(f"closes {opportunity.closing_date} ({days_label})")
        else:
            parts.append(f"closes {opportunity.closing_date}")
    return " | ".join(parts) if parts else "No parsed opening or closing date"


def _is_ongoing(opportunity: FundingOpportunity, today: date) -> bool:
    closing = parse_opportunity_date(opportunity.closing_date)
    if closing:
        return closing >= today
    if opportunity.closing_date:
        return True
    status = (opportunity.status or "").lower()
    return "open" in status or "upcoming" in status


def _is_closed(opportunity: FundingOpportunity) -> bool:
    status = (opportunity.status or "").lower()
    return "closed" in status


def _days_until_closing(opportunity: FundingOpportunity, today: date) -> int | None:
    closing = parse_opportunity_date(opportunity.closing_date)
    if not closing:
        return None
    return (closing - today).days


def _is_expiring_soon(opportunity: FundingOpportunity, today: date) -> bool:
    days_until_closing = _days_until_closing(opportunity, today)
    return (
        days_until_closing is not None
        and 0 <= days_until_closing <= EXPIRING_SOON_DAYS
    )


def _opportunity_keys(opportunities: Sequence[FundingOpportunity]) -> set[tuple[str, str]]:
    return {_opportunity_key(opportunity) for opportunity in opportunities}


def _opportunity_key(opportunity: FundingOpportunity) -> tuple[str, str]:
    return (opportunity.source, opportunity.external_id)


def parse_opportunity_date(value: str | None) -> date | None:
    """Best-effort date parser for source-supplied funding dates."""

    if not value:
        return None

    cleaned = _clean_date_value(value)
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%d %B %Y",
        "%d %b %Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", cleaned)
    if iso_match:
        try:
            return datetime.strptime(iso_match.group(0), "%Y-%m-%d").date()
        except ValueError:
            return None

    return None


def _clean_date_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" .")
    cleaned = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+at\s+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\d{1,2}:\d{2}.*$", "", cleaned)
    cleaned = re.sub(r"\s+\d{1,2}(am|pm).*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _category_counts(opportunities: Sequence[FundingOpportunity]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for opportunity in opportunities:
        counts.update(opportunity.categories or ["Uncategorised"])
    return counts


def _section(title: str, opportunities: Sequence[FundingOpportunity]) -> list[str]:
    lines = [f"{title}:"]
    if not opportunities:
        lines.extend(["None.", ""])
        return lines

    for index, opportunity in enumerate(opportunities, start=1):
        lines.extend(_format_opportunity(index, opportunity))
    lines.append("")
    return lines


def _format_opportunity(index: int, opportunity: FundingOpportunity) -> list[str]:
    matched = ", ".join(opportunity.matched_keywords) if opportunity.matched_keywords else "None"
    categories = ", ".join(opportunity.categories) if opportunity.categories else "Uncategorised"
    lines = [
        f"{index}. {opportunity.title}",
        f"   Source: {opportunity.source}",
        f"   Funder: {opportunity.display_funder()}",
        f"   Categories: {categories}",
    ]

    if opportunity.status:
        lines.append(f"   Status: {opportunity.status}")
    if opportunity.funding_type:
        lines.append(f"   Type: {opportunity.funding_type}")
    if opportunity.amount:
        lines.append(f"   Amount: {opportunity.amount}")
    if opportunity.closing_date:
        lines.append(f"   Closing date: {opportunity.closing_date}")
    if opportunity.change_summary:
        lines.append(f"   Changes: {', '.join(opportunity.change_summary)}")

    lines.extend(
        [
            f"   Score: {opportunity.relevance_score}",
            f"   Matched keywords: {matched}",
            f"   URL: {opportunity.url or 'Unknown'}",
        ]
    )
    if opportunity.bid_summary:
        lines.append("   Bid-fit summary:")
        lines.extend(f"   - {line}" for line in opportunity.bid_summary)
    return lines


def _format_discord_opportunity(index: int, opportunity: FundingOpportunity) -> list[str]:
    matched = ", ".join(opportunity.matched_keywords[:5]) if opportunity.matched_keywords else "None"
    lines = [
        f"**{index}. {opportunity.title}**",
        f"> {_discord_source_funder(opportunity)} | Score: {opportunity.relevance_score}",
    ]
    categories = _discord_categories(opportunity)
    if categories:
        lines.append(f"> Topics: {categories}")
    if opportunity.amount or opportunity.closing_date:
        lines.append(
            f"> Funding/deadline: {opportunity.amount or 'Not stated'} | "
            f"{opportunity.closing_date or 'No closing date parsed'}"
        )
    if opportunity.change_summary:
        lines.append(f"> Changes: {', '.join(opportunity.change_summary)}")
    if opportunity.url:
        link = f"<{opportunity.url}>"
    else:
        link = "not available"
    lines.extend(
        [
            f"> Keywords: {matched}",
            f"> Link: {link}",
            "",
        ]
    )
    return lines


def _discord_categories(opportunity: FundingOpportunity) -> str:
    return ", ".join(
        category for category in opportunity.categories if category != "General / Low Match"
    )


def _discord_source_funder(opportunity: FundingOpportunity) -> str:
    funder = opportunity.display_funder()
    if not funder or funder == "Unknown":
        return opportunity.source
    if funder.casefold() == opportunity.source.casefold():
        return opportunity.source
    return f"{opportunity.source} | {funder}"
