"""Royal Society grants source."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from app.config import ROYAL_SOCIETY_GRANTS_URL
from app.models import FundingOpportunity
from app.sources.base import FundingSource
from app.sources.html_utils import absolute_url, clean_text, get_soup, nearby_block_text


logger = logging.getLogger(__name__)


class RoyalSocietyGrantsSource(FundingSource):
    """Fetch Royal Society grant listings."""

    name = "Royal Society"

    def __init__(self, grants_url: str = ROYAL_SOCIETY_GRANTS_URL) -> None:
        self.grants_url = grants_url

    def fetch(self) -> list[FundingOpportunity]:
        logger.info("Fetching Royal Society grants: %s", self.grants_url)
        try:
            soup = get_soup(self.grants_url)
        except requests.RequestException:
            logger.exception("Failed to fetch Royal Society grants.")
            return []

        opportunities = parse_royal_society_opportunities(self.grants_url, soup)
        logger.info("Parsed %s opportunities from Royal Society.", len(opportunities))
        return opportunities


def parse_royal_society_opportunities(base_url: str, soup: object) -> list[FundingOpportunity]:
    opportunities: list[FundingOpportunity] = []
    seen_ids: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "/grants/" not in href:
            continue

        text = clean_text(link)
        if not text or not _looks_like_grant_card(text):
            continue

        url = absolute_url(base_url, href)
        external_id = _external_id(url)
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        block_text = nearby_block_text(link)
        opportunities.append(_parse_royal_society_card(external_id, text, url, block_text))

    return opportunities


def _parse_royal_society_card(
    external_id: str,
    link_text: str,
    url: str,
    block_text: str,
) -> FundingOpportunity:
    text = clean_text(block_text if len(block_text) > len(link_text) else link_text)
    return FundingOpportunity(
        source=RoyalSocietyGrantsSource.name,
        external_id=external_id,
        title=_extract_title(link_text),
        funder="Royal Society",
        summary=_extract_summary(text),
        status=_extract_status(text),
        funding_type="Grant",
        opening_date=_extract_date(text, "Opening"),
        closing_date=_extract_date(text, "Closing"),
        url=url,
    )


def _looks_like_grant_card(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("opening ", "closing ", " open", " closed"))


def _extract_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(Grant|Fellowship)\s+", "", text, flags=re.IGNORECASE)
    title = re.split(
        r"\s+(?:Closing|Opening)\s+\d{1,2}\s+\w+\s+\d{4}\b|\s+\b(?:Open|Closed)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    for marker in (
        " This scheme ",
        " A scheme ",
        " In partnership ",
        " The ",
        " This fellowship ",
    ):
        if marker in title:
            title = title.split(marker, 1)[0]
    return title.strip(" .") or text


def _extract_summary(text: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\b(?:Opening|Closing)\s+\d{1,2}\s+\w+\s+\d{4}\b", "", cleaned)
    cleaned = re.sub(r"\b(?:Open|Closed)\b$", "", cleaned).strip()
    return cleaned or None


def _extract_status(text: str) -> str | None:
    if re.search(r"\bOpen\b", text, re.IGNORECASE):
        return "Open"
    if re.search(r"\bClosed\b", text, re.IGNORECASE):
        return "Closed"
    return None


def _extract_date(text: str, label: str) -> str | None:
    match = re.search(rf"\b{label}\s+(\d{{1,2}}\s+\w+\s+\d{{4}})", text, re.IGNORECASE)
    return match.group(1) if match else None


def _external_id(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/")
