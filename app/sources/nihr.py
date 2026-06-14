"""NIHR funding opportunities source."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import Tag

from app.config import NIHR_FUNDING_URL
from app.models import FundingOpportunity
from app.sources.base import FundingSource
from app.sources.html_utils import absolute_url, extract_label, get_soup, nearby_block_text


logger = logging.getLogger(__name__)


class NIHRFundingSource(FundingSource):
    """Fetch current NIHR funding opportunities."""

    name = "NIHR"

    def __init__(self, funding_url: str = NIHR_FUNDING_URL, max_pages: int = 5) -> None:
        self.funding_url = funding_url
        self.max_pages = max_pages

    def fetch(self) -> list[FundingOpportunity]:
        logger.info("Fetching NIHR funding opportunities: %s", self.funding_url)

        opportunities: list[FundingOpportunity] = []
        seen_ids: set[str] = set()
        next_url: str | None = self.funding_url
        pages_fetched = 0

        while next_url and pages_fetched < self.max_pages:
            try:
                soup = get_soup(next_url)
            except requests.RequestException:
                logger.exception("Failed to fetch NIHR funding opportunities.")
                break

            pages_fetched += 1
            for opportunity in parse_nihr_opportunities(next_url, soup):
                if opportunity.external_id in seen_ids:
                    continue
                seen_ids.add(opportunity.external_id)
                opportunities.append(opportunity)

            next_url = _next_page_url(next_url, soup)

        logger.info("Parsed %s opportunities from NIHR.", len(opportunities))
        return opportunities


def parse_nihr_opportunities(base_url: str, soup: object) -> list[FundingOpportunity]:
    opportunities: list[FundingOpportunity] = []
    seen_ids: set[str] = set()

    for heading in soup.find_all(["h2", "h3"]):
        title = heading.get_text(" ", strip=True)
        if not title or _is_navigation_link(title):
            continue

        block = _funding_card(heading)
        if not block:
            continue
        block_text = "\n".join(
            line.strip() for line in block.get_text("\n").splitlines() if line.strip()
        )
        if "Closing date" not in block_text and "Opening date" not in block_text:
            continue

        url = _find_card_url(base_url, heading) or _synthetic_url(base_url, title)
        external_id = _external_id(url)
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        opportunities.append(_parse_nihr_card(external_id, title, url, block_text))

    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        if not title or _is_navigation_link(title):
            continue

        block = _funding_card(link)
        if not block:
            continue
        block_text = "\n".join(
            line.strip() for line in block.get_text("\n").splitlines() if line.strip()
        )
        if "Closing date" not in block_text and "Opening date" not in block_text:
            continue

        url = absolute_url(base_url, str(link["href"]))
        external_id = _external_id(url)
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        opportunities.append(_parse_nihr_card(external_id, title, url, block_text))

    return opportunities


def _parse_nihr_card(
    external_id: str,
    title: str,
    url: str,
    block_text: str,
) -> FundingOpportunity:
    return FundingOpportunity(
        source=NIHRFundingSource.name,
        external_id=external_id,
        title=title,
        funder="NIHR",
        summary=_summary_without_metadata(block_text, title),
        status=extract_label(block_text, "Status"),
        funding_type=_first_meaningful_line(block_text, title),
        opening_date=extract_label(block_text, "Opening date"),
        closing_date=extract_label(block_text, "Closing date"),
        url=url,
    )


def _summary_without_metadata(text: str, title: str) -> str:
    lines = []
    skip_next = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == title:
            continue
        if skip_next:
            skip_next = False
            continue
        if stripped.rstrip(":").lower() in {"opening date", "closing date", "status"}:
            skip_next = True
            continue
        lines.append(stripped)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _first_meaningful_line(text: str, title: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and stripped != title and stripped.rstrip(":").lower() != "opening date":
            return stripped
    return None


def _next_page_url(base_url: str, soup: object) -> str | None:
    for link in soup.find_all("a", href=True):
        label = link.get_text(" ", strip=True).lower()
        if "next" in label and "page" in label:
            return absolute_url(base_url, str(link["href"]))
    return None


def _funding_card(tag: Tag) -> Tag | None:
    return tag.find_parent(class_="card--funding")


def _find_card_url(base_url: str, heading: Tag) -> str | None:
    parent = _funding_card(heading)
    if not parent:
        return None
    for link in parent.find_all("a", href=True):
        href = str(link["href"])
        if href and not href.startswith("#"):
            return absolute_url(base_url, href)
    return None


def _synthetic_url(base_url: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{base_url.rstrip('/')}#{slug}"


def _external_id(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/")


def _is_navigation_link(title: str) -> bool:
    return title.lower() in {"next page", "previous page", "current page"} or title.isdigit()
