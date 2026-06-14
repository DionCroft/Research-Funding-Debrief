"""Funding opportunity categorisation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.models import FundingOpportunity


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI / Data": (
        "ai",
        "artificial intelligence",
        "machine learning",
        "data",
        "algorithm",
        "compute",
        "software",
    ),
    "Electronics / Sensors / Embedded": (
        "embedded systems",
        "electronics",
        "electronic",
        "sensors",
        "sensor",
        "instrumentation",
        "photonics",
        "semiconductor",
    ),
    "Robotics / Automation": (
        "robotics",
        "robot",
        "automation",
        "autonomous",
    ),
    "Digital Health / Assistive Tech / SEND": (
        "digital health",
        "health",
        "medical",
        "clinical",
        "social care",
        "assistive technology",
        "accessibility",
        "send",
        "independent living",
    ),
    "Energy / Sustainability": (
        "energy",
        "sustainability",
        "sustainable",
        "low carbon",
        "clean energy",
        "climate",
        "net zero",
        "decarbon",
    ),
    "Cybersecurity": (
        "cybersecurity",
        "cyber security",
        "security",
        "secure",
        "resilience",
    ),
    "KTP / University-Business Collaboration": (
        "knowledge transfer",
        "ktp",
        "collaboration",
        "collaborative",
        "business collaboration",
        "academic institution",
        "research organisation",
        "research organization",
        "university",
    ),
    "Fellowships / Academic Career": (
        "fellowship",
        "career development",
        "doctoral",
        "postdoctoral",
        "professorship",
        "studentship",
        "researcher development",
    ),
    "Capital / Infrastructure": (
        "infrastructure",
        "equipment",
        "capital",
        "facility",
        "facilities",
        "compute",
    ),
}


def assign_categories(opportunity: FundingOpportunity) -> FundingOpportunity:
    """Populate opportunity categories using deterministic keyword matching."""

    text = _opportunity_text(opportunity)
    categories = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(_contains_term(text, keyword) for keyword in keywords)
    ]
    opportunity.categories = categories or ["General / Low Match"]
    return opportunity


def category_names() -> Sequence[str]:
    """Return configured category names."""

    return tuple(CATEGORY_KEYWORDS)


def _opportunity_text(opportunity: FundingOpportunity) -> str:
    return "\n".join(
        value
        for value in (
            opportunity.title,
            opportunity.summary,
            opportunity.funder,
            opportunity.funding_type,
            opportunity.eligibility,
        )
        if value
    ).lower()


def _contains_term(text: str, term: str) -> bool:
    term_lower = term.lower()
    escaped = re.escape(term_lower)
    if len(term) <= 4 or term.isupper():
        return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))
    return term_lower in text
