"""Wellcome funding schemes source."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from app.config import WELLCOME_FUNDING_URL
from app.models import FundingOpportunity
from app.sources.base import FundingSource
from app.sources.html_utils import absolute_url, clean_text, get_soup, nearby_block_text


logger = logging.getLogger(__name__)


class WellcomeFundingSource(FundingSource):
    """Fetch Wellcome research funding schemes."""

    name = "Wellcome"

    def __init__(self, funding_url: str = WELLCOME_FUNDING_URL) -> None:
        self.funding_url = funding_url

    def fetch(self) -> list[FundingOpportunity]:
        logger.info("Fetching Wellcome funding schemes: %s", self.funding_url)
        try:
            soup = get_soup(self.funding_url)
        except requests.RequestException:
            logger.exception("Failed to fetch Wellcome funding schemes.")
            return []

        opportunities = parse_wellcome_opportunities(self.funding_url, soup)
        logger.info("Parsed %s opportunities from Wellcome.", len(opportunities))
        return opportunities


def parse_wellcome_opportunities(base_url: str, soup: object) -> list[FundingOpportunity]:
    opportunities: list[FundingOpportunity] = []
    seen_ids: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if not _looks_like_scheme_url(href):
            continue

        title = link.get_text(" ", strip=True)
        if not title or title.lower() in {"find a funding opportunity", "research funding"}:
            continue

        url = absolute_url(base_url, href)
        external_id = _external_id(url)
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        block_text = nearby_block_text(link)
        opportunities.append(_parse_wellcome_card(external_id, title, url, block_text))

    return opportunities


def _parse_wellcome_card(
    external_id: str,
    title: str,
    url: str,
    block_text: str,
) -> FundingOpportunity:
    summary = _summary_without_title(block_text, title)
    return FundingOpportunity(
        source=WellcomeFundingSource.name,
        external_id=external_id,
        title=_clean_title(title),
        funder="Wellcome",
        summary=summary,
        status=_extract_status(block_text),
        funding_type=_extract_funding_type(block_text),
        amount=_extract_amount(block_text),
        opening_date=_extract_date(block_text, ("Opening date", "Opens")),
        closing_date=_extract_date(block_text, ("Closing date", "Deadline", "Closes")),
        url=url,
    )


def _looks_like_scheme_url(href: str) -> bool:
    return (
        "/research-funding/schemes/" in href
        or "/grant-funding/schemes/" in href
    )


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    return re.split(r"\s+(?:Open to applications|Upcoming|Closed to applications)\b", title)[0]


def _summary_without_title(text: str, title: str) -> str:
    lines = [line for line in clean_text(text).splitlines() if line.strip() and line.strip() != title]
    return "\n".join(lines).strip()


def _extract_status(text: str) -> str | None:
    lowered = text.lower()
    if "open to applications" in lowered:
        return "Open"
    if "upcoming" in lowered:
        return "Opening soon"
    if "closed to applications" in lowered:
        return "Closed"
    return None


def _extract_funding_type(text: str) -> str | None:
    for label in ("Discovery Research", "Climate and Health", "Infectious Disease", "Mental Health"):
        if label.lower() in text.lower():
            return label
    return "Scheme"


def _extract_amount(text: str) -> str | None:
    match = re.search(r"(?:up to|award(?:s)? of)\s+([£$€][\d,]+(?:\s*(?:million|m|k))?)", text, re.I)
    return match.group(0).strip() if match else None


def _extract_date(text: str, labels: tuple[str, ...]) -> str | None:
    lines = [line.strip() for line in clean_text(text).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        stripped = line.rstrip(":")
        if any(stripped.lower() == label.lower() for label in labels):
            if index + 1 < len(lines):
                return lines[index + 1]
        for label in labels:
            match = re.match(rf"{re.escape(label)}\s*:\s*(.+)", line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _external_id(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/")
