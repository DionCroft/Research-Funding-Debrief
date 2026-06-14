"""Deterministic bid-fit summaries for funding opportunities."""

from __future__ import annotations

import re

from app.models import FundingOpportunity


def build_bid_summary(opportunity: FundingOpportunity) -> FundingOpportunity:
    """Populate a short bid-fit summary for a funding opportunity."""

    categories = [
        category
        for category in opportunity.categories
        if category != "General / Low Match"
    ]
    keywords = ", ".join(opportunity.matched_keywords[:5])

    if categories and keywords:
        why = f"Matches {', '.join(categories[:3])}; keyword hits include {keywords}."
    elif categories:
        why = f"Falls under {', '.join(categories[:3])}."
    elif keywords:
        why = f"Keyword hits include {keywords}."
    else:
        why = "No strong configured match; review manually if the title looks useful."

    eligibility = opportunity.eligibility or _extract_eligibility(opportunity.summary or "")
    deadline = opportunity.closing_date or "Not stated"
    bid_type_parts = [
        value
        for value in (opportunity.funding_type, opportunity.status, opportunity.source)
        if value
    ]
    bid_type = " / ".join(bid_type_parts) if bid_type_parts else "Not stated"

    if opportunity.relevance_score >= 8:
        next_action = "Shortlist for bid/no-bid review and check full eligibility."
    elif opportunity.relevance_score >= 4:
        next_action = "Skim the full call and decide whether to monitor or shortlist."
    else:
        next_action = "Store for awareness; only pursue if a stakeholder asks."

    opportunity.bid_summary = [
        f"Why it may fit: {why}",
        f"Eligibility: {eligibility or 'Not stated in the parsed feed.'}",
        f"Funding available: {opportunity.amount or 'Not stated'}",
        f"Deadline: {deadline}",
        f"Likely bid type: {bid_type}",
        f"Suggested next action: {next_action}",
    ]
    return opportunity


def _extract_eligibility(summary: str) -> str | None:
    patterns = (
        r"(You must .+?)(?:\n[A-Z][A-Za-z /-]{2,40}:|\n\n|$)",
        r"(This competition is open to .+?)(?:\n[A-Z][A-Za-z /-]{2,40}:|\n\n|$)",
        r"(To lead .+?)(?:\n[A-Z][A-Za-z /-]{2,40}:|\n\n|$)",
        r"(UK registered .+? can apply.+?)(?:\n[A-Z][A-Za-z /-]{2,40}:|\n\n|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, summary, re.IGNORECASE | re.DOTALL)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return None
