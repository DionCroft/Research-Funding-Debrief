"""Funding opportunity categorisation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.models import FundingOpportunity


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI / Data": (
        "ai",
        "artificial intelligence",
        "data",
        "algorithm",
        "compute",
        "software",
    ),
    "Machine Learning": (
        "machine learning",
        "deep learning",
        "neural network",
        "predictive model",
    ),
    "Robotics / Automation": (
        "robotics",
        "robot",
        "automation",
        "autonomous",
    ),
    "Electronics / IoT": (
        "electronics",
        "electronic",
        "iot",
        "internet of things",
        "semiconductor",
        "photonics",
    ),
    "Embedded Systems": (
        "embedded systems",
        "embedded software",
        "firmware",
        "microcontroller",
    ),
    "Sensors / Instrumentation": (
        "sensors",
        "sensor",
        "instrumentation",
        "measurement",
        "monitoring device",
    ),
    "Cybersecurity": (
        "cybersecurity",
        "cyber security",
        "secure",
        "resilience",
        "privacy",
    ),
    "Wireless / Telecoms": (
        "wireless",
        "telecom",
        "telecommunications",
        "connectivity",
        "5g",
        "6g",
        "radio",
    ),
    "Digital Health": (
        "digital health",
        "health",
        "medical",
        "healthcare",
        "patient",
    ),
    "Assistive Technology / SEND": (
        "assistive technology",
        "assistive tech",
        "accessibility",
        "send",
        "independent living",
        "neurodisability",
    ),
    "Clinical Evidence / Trials": (
        "clinical",
        "trial",
        "trials",
        "clinical evidence",
        "evidence generation",
        "randomised",
        "randomized",
    ),
    "Public Health": (
        "public health",
        "population health",
        "prevention",
        "community health",
    ),
    "Social Care": (
        "social care",
        "care home",
        "adult social care",
    ),
    "Mental Health": (
        "mental health",
        "wellbeing",
        "psychological",
        "loneliness",
        "gambling",
    ),
    "Education / Skills": (
        "education",
        "skills",
        "training",
        "school",
        "learning",
        "curriculum",
    ),
    "Policy / Social Sciences": (
        "policy",
        "social science",
        "social sciences",
        "economic",
        "behaviour",
        "behavior",
    ),
    "Energy / Sustainability": (
        "energy",
        "sustainability",
        "sustainable",
        "low carbon",
        "clean energy",
        "net zero",
        "decarbon",
    ),
    "Climate / Environment": (
        "climate",
        "environment",
        "environmental",
        "biodiversity",
        "nature",
        "pollution",
    ),
    "Manufacturing / Industry 4.0": (
        "manufacturing",
        "industry 4.0",
        "industrial",
        "factory",
    ),
    "Space / Aerospace": (
        "space",
        "aerospace",
        "aviation",
        "satellite",
    ),
    "Defence / Security": (
        "defence",
        "defense",
        "security",
        "national security",
    ),
    "Creative / Media Tech": (
        "creative",
        "media",
        "immersive",
        "games",
        "screen",
    ),
    "KTP / Collaboration": (
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
    "Fellowships": (
        "fellowship",
        "fellowships",
        "professorship",
    ),
    "Early Career": (
        "early career",
        "career development",
        "doctoral",
        "postdoctoral",
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
    "International / Horizon Europe": (
        "international",
        "horizon europe",
        "european",
        "global",
        "japan-uk",
        "overseas",
    ),
    "Commercialisation / Translation": (
        "commercialisation",
        "commercialization",
        "translation",
        "translational",
        "innovation catalyst",
        "entrepreneur",
        "market",
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
