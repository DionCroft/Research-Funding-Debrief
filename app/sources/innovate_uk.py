"""Innovate UK competition search source."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from app.config import INNOVATE_UK_SEARCH_URL
from app.filters import detect_amount, normalise_amount
from app.models import FundingOpportunity
from app.sources.base import FundingSource
from app.sources.html_utils import absolute_url, clean_text, get_soup, nearby_block_text


logger = logging.getLogger(__name__)


class InnovateUKSource(FundingSource):
    """Fetch current Innovate UK competitions from the public search page."""

    name = "Innovate UK"

    def __init__(self, search_url: str = INNOVATE_UK_SEARCH_URL) -> None:
        self.search_url = search_url

    def fetch(self) -> list[FundingOpportunity]:
        logger.info("Fetching Innovate UK competitions: %s", self.search_url)
        try:
            soup = get_soup(self.search_url)
        except requests.RequestException:
            logger.exception("Failed to fetch Innovate UK competitions.")
            return []

        opportunities: list[FundingOpportunity] = []
        seen_ids: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if "/competition/" not in href or href.rstrip("/") == "/competition/search":
                continue
            title = link.get_text(" ", strip=True)
            if not title or title.lower() in {
                "innovation funding service",
                "sign in",
                "latest funding opportunities",
            }:
                continue

            url = absolute_url(self.search_url, href)
            external_id = _external_id(url)
            if external_id in seen_ids:
                continue
            seen_ids.add(external_id)

            block_text = nearby_block_text(link)
            opportunities.append(_parse_competition(self.name, external_id, title, url, block_text))

        logger.info("Parsed %s opportunities from Innovate UK.", len(opportunities))
        return opportunities


def _parse_competition(
    source: str,
    external_id: str,
    title: str,
    url: str,
    block_text: str,
) -> FundingOpportunity:
    summary = _summary_without_title(block_text, title)
    amount = detect_amount(summary)
    if amount:
        amount = normalise_amount(amount)

    return FundingOpportunity(
        source=source,
        external_id=external_id,
        title=title,
        funder=_extract_funder(summary) or "Innovate UK",
        summary=summary,
        amount=amount,
        status=_extract_status(summary),
        funding_type="Competition",
        eligibility=_extract_eligibility(summary),
        opening_date=_extract_labeled_date(summary, ("Opened", "Opens")),
        closing_date=_extract_labeled_date(summary, ("Closes",)),
        url=url,
    )


def _external_id(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/")


def _summary_without_title(block_text: str, title: str) -> str:
    lines = [line for line in block_text.splitlines() if line.strip() and line.strip() != title]
    return "\n".join(lines)


def _extract_status(text: str) -> str | None:
    for status in ("Open now", "Opening soon", "Closed"):
        if status.lower() in text.lower():
            return status
    return None


def _extract_labeled_date(text: str, labels: tuple[str, ...]) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        stripped = line.rstrip(":")
        if any(stripped.lower() == label.lower() for label in labels):
            if index + 1 < len(lines):
                return lines[index + 1]
        for label in labels:
            match = re.match(rf"{re.escape(label)}:\s*(.+)", line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _extract_eligibility(text: str) -> str | None:
    match = re.search(
        r"Eligibility\s*(?P<value>.+?)(?:Open now|Opening soon|Closed|Opened:|Opens:|Closes:|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return re.sub(r"\s+", " ", clean_text(match.group("value"))).strip()

    match = re.search(
        r"(This competition is open to .+?)(?:\.|Open now|Opening soon|Closed|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return None


def _extract_funder(text: str) -> str | None:
    match = re.search(r"Funding is from ([^.]+)\.", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None
