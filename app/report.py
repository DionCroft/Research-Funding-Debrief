"""Plain-text and Discord report generation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime

from app.config import Config
from app.filters import relevance_bucket
from app.models import FundingOpportunity


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
        "**Daily Research Funding Debrief**",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M %Z')}".rstrip(),
        (
            f"Fetched: {len(fetched_opportunities)} | New: {len(new_opportunities)} | "
            f"Relevant new: {len(relevant_new)} | Changed: {len(changed_opportunities)} | "
            f"Seen before: {len(known_opportunities)}"
        ),
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
                f"{category} {count}" for category, count in category_counts.most_common(3)
            )
        )
    lines.append("")

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


def _sort_by_score(opportunities: Sequence[FundingOpportunity]) -> list[FundingOpportunity]:
    return sorted(opportunities, key=lambda opportunity: opportunity.relevance_score, reverse=True)


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
    categories = ", ".join(
        category for category in opportunity.categories if category != "General / Low Match"
    )
    matched = ", ".join(opportunity.matched_keywords[:5]) if opportunity.matched_keywords else "None"
    lines = [
        f"{index}. **{opportunity.title}**",
        f"   Score: {opportunity.relevance_score} | Source: {opportunity.source}",
    ]
    if categories:
        lines.append(f"   Categories: {categories}")
    if opportunity.amount or opportunity.closing_date:
        lines.append(
            f"   Funding/deadline: {opportunity.amount or 'Not stated'} | "
            f"{opportunity.closing_date or 'No closing date parsed'}"
        )
    if opportunity.change_summary:
        lines.append(f"   Changes: {', '.join(opportunity.change_summary)}")
    lines.extend(
        [
            f"   Keywords: {matched}",
            f"   {opportunity.url or 'URL not available'}",
            "",
        ]
    )
    return lines
