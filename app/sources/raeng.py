"""Royal Academy of Engineering programmes source."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import Tag

from app.config import RAENG_PROGRAMMES_URL
from app.models import FundingOpportunity
from app.sources.base import FundingSource
from app.sources.html_utils import absolute_url, clean_text, extract_label, get_soup, nearby_block_text


logger = logging.getLogger(__name__)


class RAEngProgrammesSource(FundingSource):
    """Fetch Royal Academy of Engineering research support programmes."""

    name = "Royal Academy of Engineering"

    def __init__(self, programmes_url: str = RAENG_PROGRAMMES_URL) -> None:
        self.programmes_url = programmes_url

    def fetch(self) -> list[FundingOpportunity]:
        logger.info("Fetching Royal Academy of Engineering programmes: %s", self.programmes_url)
        try:
            soup = get_soup(self.programmes_url)
        except requests.RequestException:
            logger.exception("Failed to fetch Royal Academy of Engineering programmes.")
            return []

        opportunities = parse_raeng_opportunities(self.programmes_url, soup)
        logger.info("Parsed %s opportunities from Royal Academy of Engineering.", len(opportunities))
        return opportunities


def parse_raeng_opportunities(base_url: str, soup: object) -> list[FundingOpportunity]:
    opportunities: list[FundingOpportunity] = []
    seen_ids: set[str] = set()

    for heading in soup.find_all(["h2", "h3"]):
        title = heading.get_text(" ", strip=True)
        if not title or _is_non_programme_heading(title):
            continue

        link = _find_programme_link(heading)
        if not link:
            continue

        url = absolute_url(base_url, str(link["href"]))
        if not _looks_like_programme_url(url):
            continue
        external_id = _external_id(url)
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)

        block_text = nearby_block_text(link)
        opportunities.append(_parse_raeng_card(external_id, title, url, block_text))

    return opportunities


def _parse_raeng_card(
    external_id: str,
    title: str,
    url: str,
    block_text: str,
) -> FundingOpportunity:
    summary = _summary_without_title(block_text, title)
    return FundingOpportunity(
        source=RAEngProgrammesSource.name,
        external_id=external_id,
        title=title,
        funder="Royal Academy of Engineering",
        summary=summary,
        status=_extract_status(block_text),
        funding_type="Programme",
        opening_date=_clean_date(
            extract_label(block_text, "Opening date") or _extract_date(block_text, "Opens")
        ),
        closing_date=_clean_date(
            extract_label(block_text, "Closing date")
            or extract_label(block_text, "Deadline")
            or _extract_date(block_text, "Closes")
        ),
        url=url,
    )


def _find_programme_link(heading: Tag) -> Tag | None:
    for sibling in heading.next_siblings:
        if isinstance(sibling, Tag):
            link = sibling.find("a", href=True)
            if link:
                return link
            if sibling.name in {"h2", "h3"}:
                return None
    parent = heading.find_parent(["article", "section", "div", "li"])
    if parent:
        return parent.find("a", href=True)
    return None


def _summary_without_title(text: str, title: str) -> str:
    lines = [line for line in clean_text(text).splitlines() if line.strip() and line.strip() != title]
    return "\n".join(lines).strip()


def _extract_status(text: str) -> str | None:
    lowered = text.lower()
    if "now open" in lowered or "apply now" in lowered:
        return "Open"
    if "closed" in lowered:
        return "Closed"
    return None


def _extract_date(text: str, label: str) -> str | None:
    match = re.search(
        rf"\b{label}\s+(\d{{1,2}}\s+\w+\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{4}})",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def _clean_date(value: str | None) -> str | None:
    if not value:
        return None
    for marker in (" Find out more", " Apply Now", " Apply now", " Read more"):
        if marker in value:
            value = value.split(marker, 1)[0]
    return value.strip(" .") or None


def _is_non_programme_heading(title: str) -> bool:
    return title.lower() in {
        "support for research",
        "grant management system",
        "our research programmes and fellowships",
        "review of opportunities to enhance the academy’s research programmes",
        "funding opportunities",
        "research programmes evaluation",
        "academy cafe: connecting awardees, fostering engagement",
        "covid-19 advice to awardees",
        "daphne jackson trust",
        "stem for britain",
        "sign up to our funding opportunities newsletter",
        "resources and policies",
        "our policies",
    }


def _looks_like_programme_url(url: str) -> bool:
    return "/programmes-and-prizes/programmes/uk-grants-and-prizes/support-for-research/" in url


def _external_id(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/")
