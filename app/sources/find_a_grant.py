"""GOV.UK Find a Grant source."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from app.config import FIND_A_GRANT_URL
from app.filters import normalise_amount
from app.models import FundingOpportunity
from app.sources.base import FundingSource
from app.sources.html_utils import absolute_url, extract_label, get_soup, nearby_block_text


logger = logging.getLogger(__name__)


class FindAGrantSource(FundingSource):
    """Fetch public grants from the UK Government Find a Grant page."""

    name = "Find a Grant"

    def __init__(self, grants_url: str = FIND_A_GRANT_URL) -> None:
        self.grants_url = grants_url

    def fetch(self) -> list[FundingOpportunity]:
        logger.info("Fetching Find a Grant results: %s", self.grants_url)
        try:
            soup = get_soup(self.grants_url)
        except requests.RequestException:
            logger.exception("Failed to fetch Find a Grant results.")
            return []

        opportunities: list[FundingOpportunity] = []
        seen_ids: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if "/grants/" not in href:
                continue
            title = link.get_text(" ", strip=True)
            if not title or title.lower() in {"find a grant"}:
                continue

            url = absolute_url(self.grants_url, href)
            external_id = _external_id(url)
            if external_id in seen_ids:
                continue
            seen_ids.add(external_id)

            block_text = nearby_block_text(link)
            opportunities.append(_parse_grant(self.name, external_id, title, url, block_text))

        logger.info("Parsed %s opportunities from Find a Grant.", len(opportunities))
        return opportunities


def _parse_grant(
    source: str,
    external_id: str,
    title: str,
    url: str,
    block_text: str,
) -> FundingOpportunity:
    summary = _summary_without_title(block_text, title)
    amount = extract_label(summary, "How much you can get")
    if amount:
        amount = normalise_amount(amount)

    return FundingOpportunity(
        source=source,
        external_id=external_id,
        title=title,
        funder=extract_label(summary, "Funding organisation"),
        summary=summary,
        amount=amount,
        status="Open",
        funding_type="Grant",
        eligibility=extract_label(summary, "Who can apply"),
        location=extract_label(summary, "Location"),
        opening_date=extract_label(summary, "Opening date"),
        closing_date=extract_label(summary, "Closing date"),
        url=url,
    )


def _external_id(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}".rstrip("/")


def _summary_without_title(block_text: str, title: str) -> str:
    lines = [line for line in block_text.splitlines() if line.strip() and line.strip() != title]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
