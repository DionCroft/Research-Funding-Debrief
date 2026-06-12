"""UKRI Funding Finder RSS source."""

from __future__ import annotations

import logging
import re
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

from app.config import UKRI_RSS_URL
from app.filters import detect_amount, normalise_amount
from app.models import FundingOpportunity
from app.sources.base import FundingSource


logger = logging.getLogger(__name__)


class UKRIFundingSource(FundingSource):
    """Fetch opportunities from the UKRI Funding Finder RSS feed."""

    name = "UKRI"

    def __init__(self, feed_url: str = UKRI_RSS_URL) -> None:
        self.feed_url = feed_url

    def fetch(self) -> list[FundingOpportunity]:
        """Fetch and parse UKRI RSS opportunities."""

        logger.info("Fetching UKRI RSS feed: %s", self.feed_url)
        try:
            response = requests.get(
                self.feed_url,
                headers={"User-Agent": "ResearchFundingDebrief/0.1"},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to fetch UKRI RSS feed.")
            return []

        parsed = feedparser.parse(response.content)
        if parsed.bozo:
            logger.warning("UKRI RSS feed parsed with warnings: %s", parsed.bozo_exception)

        opportunities: list[FundingOpportunity] = []
        for entry in parsed.entries:
            opportunity = self._parse_entry(entry)
            if opportunity:
                opportunities.append(opportunity)

        logger.info("Parsed %s opportunities from UKRI RSS feed.", len(opportunities))
        return opportunities

    def _parse_entry(self, entry: object) -> FundingOpportunity | None:
        title = str(entry.get("title", "")).strip()
        link = str(entry.get("link", "")).strip()
        external_id = str(entry.get("id") or entry.get("guid") or link).strip()

        if not title or not external_id:
            logger.warning("Skipping UKRI RSS item missing title or external id.")
            return None

        raw_summary = (
            entry.get("summary")
            or entry.get("description")
            or _first_content_value(entry)
            or ""
        )
        summary = _clean_html(str(raw_summary))
        published_date = _parse_published_date(entry)

        status = _extract_label(summary, "Opportunity status")
        funder = _extract_label(summary, "Funders") or _extract_label(summary, "Funder")
        opening_date = _extract_label(summary, "Opening date")
        closing_date = _extract_label(summary, "Closing date")
        amount = (
            _extract_label(summary, "Total fund")
            or _extract_label(summary, "Maximum award")
            or _extract_label(summary, "Award range")
            or detect_amount(summary)
        )
        if amount:
            amount = normalise_amount(amount)

        return FundingOpportunity(
            source=self.name,
            external_id=external_id,
            title=title,
            funder=funder,
            summary=summary,
            amount=amount,
            status=status,
            opening_date=opening_date,
            closing_date=closing_date,
            published_date=published_date,
            url=link or None,
        )


def _first_content_value(entry: object) -> str | None:
    content = entry.get("content")
    if isinstance(content, list) and content:
        value = content[0].get("value")
        return str(value) if value else None
    return None


def _clean_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _parse_published_date(entry: object) -> str | None:
    published = entry.get("published") or entry.get("updated")
    if not published:
        return None
    try:
        return parsedate_to_datetime(str(published)).isoformat()
    except (TypeError, ValueError):
        return str(published)


def _extract_label(text: str, label: str) -> str | None:
    pattern = re.compile(
        rf"{re.escape(label)}\s*:\s*(?P<value>.+?)(?=\n[A-Z][A-Za-z /-]{{2,40}}\s*:|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None

    value_lines = [
        line.strip()
        for line in match.group("value").splitlines()
        if line.strip() and line.strip() != ","
    ]
    return " ".join(value_lines) if value_lines else None
