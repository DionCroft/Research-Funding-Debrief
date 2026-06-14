"""Keyword matching and relevance scoring."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.categories import assign_categories
from app.config import DEFAULT_KEYWORDS
from app.models import FundingOpportunity
from app.summaries import build_bid_summary


ACADEMIC_TERMS = (
    "university",
    "academic",
    "research organisation",
    "research organization",
    "collaboration",
    "collaborative",
)

AMOUNT_PATTERN = re.compile(
    r"(?:\u00a3|GBP|\$|USD|EUR|\u20ac)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|million|billion))?",
    re.IGNORECASE,
)


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    escaped = re.escape(keyword)
    if len(keyword) <= 4 or keyword.isupper():
        return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _contains_keyword(text: str, keyword: str) -> bool:
    return bool(_keyword_pattern(keyword).search(text))


def detect_amount(text: str) -> str | None:
    """Return the first funding amount-like value found in text."""

    match = AMOUNT_PATTERN.search(text)
    return normalise_amount(match.group(0)) if match else None


def normalise_amount(value: str) -> str:
    """Normalise common currency symbols for terminal-safe output."""

    cleaned = (
        value.replace("\u00a3", "GBP ")
        .replace("\u0141", "GBP ")
        .replace("\u20ac", "EUR ")
        .replace("$", "USD ")
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(".,;:")


def score_opportunity(
    opportunity: FundingOpportunity,
    keywords: Sequence[str] | None = None,
) -> FundingOpportunity:
    """Populate matched keywords and relevance score for an opportunity."""

    keywords = keywords or DEFAULT_KEYWORDS
    title = opportunity.title or ""
    summary = opportunity.summary or ""
    combined_text = f"{title}\n{summary}"
    score = 0
    matched: list[str] = []

    for keyword in keywords:
        keyword_score = 0
        if _contains_keyword(title, keyword):
            keyword_score += 3
        if _contains_keyword(summary, keyword):
            keyword_score += 1

        if keyword_score:
            score += keyword_score
            matched.append(keyword)

    status_text = (opportunity.status or "").lower()
    combined_lower = combined_text.lower()
    if "open" in status_text or "upcoming" in status_text:
        score += 2
    elif "opportunity status" in combined_lower and (
        "open" in combined_lower or "upcoming" in combined_lower
    ):
        score += 2

    if any(term in combined_lower for term in ACADEMIC_TERMS):
        score += 2

    detected_amount = opportunity.amount or detect_amount(combined_text)
    if detected_amount:
        score += 1
        if not opportunity.amount:
            opportunity.amount = detected_amount

    opportunity.matched_keywords = matched
    opportunity.relevance_score = score
    assign_categories(opportunity)
    build_bid_summary(opportunity)
    return opportunity


def score_opportunities(
    opportunities: Sequence[FundingOpportunity],
    keywords: Sequence[str] | None = None,
) -> list[FundingOpportunity]:
    """Score a list of opportunities."""

    return [score_opportunity(opportunity, keywords) for opportunity in opportunities]


def relevance_bucket(score: int, medium_threshold: int = 4, high_threshold: int = 8) -> str:
    """Classify a numeric score as high, medium, or low."""

    if score >= high_threshold:
        return "high"
    if score >= medium_threshold:
        return "medium"
    return "low"
