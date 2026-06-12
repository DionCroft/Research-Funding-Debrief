"""Plain-text daily report generation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.config import Config
from app.filters import relevance_bucket
from app.models import FundingOpportunity


def generate_daily_debrief(
    fetched_opportunities: Sequence[FundingOpportunity],
    new_opportunities: Sequence[FundingOpportunity],
    known_opportunities: Sequence[FundingOpportunity],
    config: Config,
    generated_at: datetime | None = None,
) -> str:
    """Generate a terminal-friendly daily funding debrief."""

    generated_at = generated_at or datetime.now().astimezone()
    relevant_new = [
        opportunity
        for opportunity in new_opportunities
        if opportunity.relevance_score >= config.relevant_score_threshold
    ]

    high = _sort_by_score(
        [
            opportunity
            for opportunity in new_opportunities
            if relevance_bucket(
                opportunity.relevance_score,
                config.medium_relevance_threshold,
                config.high_relevance_threshold,
            )
            == "high"
        ]
    )
    medium = _sort_by_score(
        [
            opportunity
            for opportunity in new_opportunities
            if relevance_bucket(
                opportunity.relevance_score,
                config.medium_relevance_threshold,
                config.high_relevance_threshold,
            )
            == "medium"
        ]
    )
    low = _sort_by_score(
        [
            opportunity
            for opportunity in new_opportunities
            if relevance_bucket(
                opportunity.relevance_score,
                config.medium_relevance_threshold,
                config.high_relevance_threshold,
            )
            == "low"
        ]
    )

    lines = [
        "Daily Research Funding Debrief",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M %Z')}".rstrip(),
        "",
        "Summary:",
        f"Fetched: {len(fetched_opportunities)}",
        f"New: {len(new_opportunities)}",
        f"Relevant new: {len(relevant_new)}",
        f"Previously seen: {len(known_opportunities)}",
        "",
    ]

    if not fetched_opportunities:
        lines.append("No opportunities were fetched. The feed may be unavailable or empty.")
        return "\n".join(lines)

    if not relevant_new:
        lines.extend(["No relevant new opportunities found today.", ""])

    lines.extend(_section("High relevance new opportunities", high))
    lines.extend(_section("Medium relevance new opportunities", medium))
    lines.extend(_section("Low relevance or unclassified new opportunities", low))
    lines.extend(
        _section(
            "Previously seen opportunities fetched today (not re-alerted)",
            _sort_by_score(list(known_opportunities)),
        )
    )

    return "\n".join(lines).rstrip()


def _sort_by_score(opportunities: Sequence[FundingOpportunity]) -> list[FundingOpportunity]:
    return sorted(opportunities, key=lambda opportunity: opportunity.relevance_score, reverse=True)


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
    lines = [
        f"{index}. {opportunity.title}",
        f"   Source: {opportunity.source}",
        f"   Funder: {opportunity.display_funder()}",
    ]

    if opportunity.status:
        lines.append(f"   Status: {opportunity.status}")
    if opportunity.amount:
        lines.append(f"   Amount: {opportunity.amount}")
    if opportunity.closing_date:
        lines.append(f"   Closing date: {opportunity.closing_date}")

    lines.extend(
        [
            f"   Score: {opportunity.relevance_score}",
            f"   Matched keywords: {matched}",
            f"   URL: {opportunity.url or 'Unknown'}",
        ]
    )
    return lines
