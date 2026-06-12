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
    "accessibility",
    "SEND",
    "assistive technology",
    "energy",
    "sustainability",
    "wireless",
    "cybersecurity",
    "digital health",
    "knowledge transfer",
    "KTP",
    "university business collaboration",
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


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from defaults and environment variables."""

    project_root: Path = PROJECT_ROOT
    database_path: Path = DEFAULT_DATABASE_PATH
    log_path: Path = DEFAULT_LOG_PATH
    ukri_rss_url: str = UKRI_RSS_URL
    keywords: list[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    relevant_score_threshold: int = 4
    high_relevance_threshold: int = 8
    medium_relevance_threshold: int = 4
    enable_email: bool = False
    enable_discord: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_to: str | None = None
    discord_webhook_url: str | None = None


def load_config() -> Config:
    """Load configuration from .env and environment variables."""

    load_dotenv(PROJECT_ROOT / ".env")

    database_path = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))
    log_path = Path(os.getenv("LOG_PATH", str(DEFAULT_LOG_PATH)))

    return Config(
        database_path=database_path,
        log_path=log_path,
        ukri_rss_url=os.getenv("UKRI_RSS_URL", UKRI_RSS_URL),
        keywords=_env_keywords(DEFAULT_KEYWORDS),
        relevant_score_threshold=_env_int("RELEVANT_SCORE_THRESHOLD", 4),
        high_relevance_threshold=_env_int("HIGH_RELEVANCE_THRESHOLD", 8),
        medium_relevance_threshold=_env_int("MEDIUM_RELEVANCE_THRESHOLD", 4),
        enable_email=_env_bool("ENABLE_EMAIL", False),
        enable_discord=_env_bool("ENABLE_DISCORD", False),
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=_env_int("SMTP_PORT", 587),
        smtp_username=os.getenv("SMTP_USERNAME") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        email_from=os.getenv("EMAIL_FROM") or None,
        email_to=os.getenv("EMAIL_TO") or None,
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL") or None,
    )
