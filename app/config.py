"""Application configuration for Research Funding Debrief."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "research_funding_debrief.db"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "research_funding_debrief.log"
UKRI_RSS_URL = "https://www.ukri.org/opportunity/feed/"
INNOVATE_UK_SEARCH_URL = "https://apply-for-innovation-funding.service.gov.uk/competition/search"
FIND_A_GRANT_URL = "https://www.find-government-grants.service.gov.uk/grants"
NIHR_FUNDING_URL = "https://www.nihr.ac.uk/funding-opportunities"
WELLCOME_FUNDING_URL = "https://wellcome.org/research-funding/schemes"
ROYAL_SOCIETY_GRANTS_URL = "https://royalsociety.org/grants/search/grant-listings/"
RAENG_PROGRAMMES_URL = (
    "https://raeng.org.uk/programmes-and-prizes/programmes/uk-grants-and-prizes/"
    "support-for-research/"
)
DEFAULT_ENABLED_SOURCES = [
    "ukri",
    "innovate_uk",
    "find_a_grant",
    "nihr",
    "wellcome",
    "royal_society",
    "raeng",
]

DEFAULT_KEYWORDS: list[str] = [
    "embedded systems",
    "electronics",
    "IoT",
    "Internet of Things",
    "robotics",
    "sensors",
    "instrumentation",
    "AI",
    "artificial intelligence",
    "machine learning",
    "cybersecurity",
    "cyber security",
    "wireless",
    "telecoms",
    "accessibility",
    "SEND",
    "assistive technology",
    "clinical trials",
    "public health",
    "social care",
    "mental health",
    "education",
    "policy",
    "energy",
    "sustainability",
    "climate",
    "environment",
    "manufacturing",
    "space",
    "aerospace",
    "defence",
    "creative",
    "media",
    "digital health",
    "knowledge transfer",
    "KTP",
    "university business collaboration",
    "fellowship",
    "early career",
    "infrastructure",
    "horizon europe",
    "commercialisation",
    "translation",
]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_keywords(defaults: Sequence[str]) -> list[str]:
    raw = os.getenv("RELEVANCE_KEYWORDS", "").strip()
    if not raw:
        return list(defaults)
    return [keyword.strip() for keyword in raw.split(",") if keyword.strip()]


def _env_list(name: str, defaults: Sequence[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(defaults)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from defaults and environment variables."""

    project_root: Path = PROJECT_ROOT
    database_path: Path = DEFAULT_DATABASE_PATH
    log_path: Path = DEFAULT_LOG_PATH
    ukri_rss_url: str = UKRI_RSS_URL
    innovate_uk_search_url: str = INNOVATE_UK_SEARCH_URL
    find_a_grant_url: str = FIND_A_GRANT_URL
    nihr_funding_url: str = NIHR_FUNDING_URL
    wellcome_funding_url: str = WELLCOME_FUNDING_URL
    royal_society_grants_url: str = ROYAL_SOCIETY_GRANTS_URL
    raeng_programmes_url: str = RAENG_PROGRAMMES_URL
    enabled_sources: list[str] = field(default_factory=lambda: list(DEFAULT_ENABLED_SOURCES))
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    relevant_score_threshold: int = 4
    high_relevance_threshold: int = 8
    medium_relevance_threshold: int = 4
    max_known_report_items: int = 10
    discord_max_items: int = 8
    discord_include_known: bool = False
    enable_email: bool = False
    enable_discord: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_to: str | None = None
    discord_webhook_url: str | None = None
    discord_bot_token: str | None = None
    discord_channel_id: str | None = None


def load_config() -> Config:
    """Load configuration from .env and environment variables."""

    load_dotenv(PROJECT_ROOT / ".env")

    database_path = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))
    log_path = Path(os.getenv("LOG_PATH", str(DEFAULT_LOG_PATH)))

    return Config(
        database_path=database_path,
        log_path=log_path,
        ukri_rss_url=os.getenv("UKRI_RSS_URL", UKRI_RSS_URL),
        innovate_uk_search_url=os.getenv("INNOVATE_UK_SEARCH_URL", INNOVATE_UK_SEARCH_URL),
        find_a_grant_url=os.getenv("FIND_A_GRANT_URL", FIND_A_GRANT_URL),
        nihr_funding_url=os.getenv("NIHR_FUNDING_URL", NIHR_FUNDING_URL),
        wellcome_funding_url=os.getenv("WELLCOME_FUNDING_URL", WELLCOME_FUNDING_URL),
        royal_society_grants_url=os.getenv(
            "ROYAL_SOCIETY_GRANTS_URL",
            ROYAL_SOCIETY_GRANTS_URL,
        ),
        raeng_programmes_url=os.getenv("RAENG_PROGRAMMES_URL", RAENG_PROGRAMMES_URL),
        enabled_sources=_env_list("ENABLED_SOURCES", DEFAULT_ENABLED_SOURCES),
        keywords=_env_keywords(DEFAULT_KEYWORDS),
        relevant_score_threshold=_env_int("RELEVANT_SCORE_THRESHOLD", 4),
        high_relevance_threshold=_env_int("HIGH_RELEVANCE_THRESHOLD", 8),
        medium_relevance_threshold=_env_int("MEDIUM_RELEVANCE_THRESHOLD", 4),
        max_known_report_items=_env_int("MAX_KNOWN_REPORT_ITEMS", 10),
        discord_max_items=_env_int("DISCORD_MAX_ITEMS", 8),
        discord_include_known=_env_bool("DISCORD_INCLUDE_KNOWN", False),
        enable_email=_env_bool("ENABLE_EMAIL", False),
        enable_discord=_env_bool("ENABLE_DISCORD", False),
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=_env_int("SMTP_PORT", 587),
        smtp_username=os.getenv("SMTP_USERNAME") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        email_from=os.getenv("EMAIL_FROM") or None,
        email_to=os.getenv("EMAIL_TO") or None,
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL") or None,
        discord_bot_token=os.getenv("DISCORD_BOT_TOKEN") or None,
        discord_channel_id=os.getenv("DISCORD_CHANNEL_ID") or None,
    )
