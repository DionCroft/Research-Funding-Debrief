"""UKRI Funding Finder RSS source."""

from __future__ import annotations

import logging
from email.utils import parsedate_to_datetime

import feedparser
import requests

from app.config import UKRI_RSS_URL
from app.filters import detect_amount, normalise_amount
from app.models import FundingOpportunity
from app.sources.base import FundingSource
from app.sources.html_utils import clean_text, extract_label, get_soup


logger = logging.getLogger(__name__)


class UKRIFundingSource(FundingSource):
    """Fetch opportunities from the UKRI Funding Finder RSS feed."""

    name = "UKRI"

    def __init__(self, feed_url: str = UKRI_RSS_URL, enrich_details: bool = True) -> None:
        self.feed_url = feed_url
        self.enrich_details = enrich_details

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
                if self.enrich_details and opportunity.url:
                    self._enrich_from_detail_page(opportunity)
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
        summary = clean_text(str(raw_summary))
        published_date = _parse_published_date(entry)

        status = extract_label(summary, "Opportunity status")
        funder = extract_label(summary, "Funders") or extract_label(summary, "Funder")
        funding_type = extract_label(summary, "Funding type")
        eligibility = _extract_eligibility(summary)
        opening_date = _clean_date(extract_label(summary, "Opening date"))
        closing_date = _clean_date(extract_label(summary, "Closing date"))
        amount = (
            extract_label(summary, "Total fund")
            or extract_label(summary, "Maximum award")
            or extract_label(summary, "Award range")
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
            funding_type=funding_type,
            eligibility=eligibility,
            opening_date=opening_date,
            closing_date=closing_date,
            published_date=published_date,
            url=link or None,
        )

    def _enrich_from_detail_page(self, opportunity: FundingOpportunity) -> None:
        try:
            soup = get_soup(opportunity.url or "")
        except requests.RequestException:
            logger.warning("Could not enrich UKRI opportunity: %s", opportunity.url)
            return

        main = soup.find("main") or soup
        detail_text = clean_text(main)
        opportunity.summary = _best_summary(opportunity.summary or "", detail_text, opportunity.title)
        opportunity.funder = (
            extract_label(detail_text, "Funders")
            or extract_label(detail_text, "Funder")
            or opportunity.funder
        )
        opportunity.status = extract_label(detail_text, "Opportunity status") or opportunity.status
        opportunity.funding_type = extract_label(detail_text, "Funding type") or opportunity.funding_type
        opportunity.opening_date = (
            _clean_date(extract_label(detail_text, "Opening date")) or opportunity.opening_date
        )
        opportunity.closing_date = (
            _clean_date(extract_label(detail_text, "Closing date")) or opportunity.closing_date
        )
        opportunity.amount = (
            extract_label(detail_text, "Total fund")
            or extract_label(detail_text, "Maximum award")
            or extract_label(detail_text, "Award range")
            or opportunity.amount
        )
        if opportunity.amount:
            opportunity.amount = normalise_amount(opportunity.amount)
        opportunity.eligibility = _extract_eligibility(detail_text) or opportunity.eligibility


def _first_content_value(entry: object) -> str | None:
    content = entry.get("content")
    if isinstance(content, list) and content:
        value = content[0].get("value")
        return str(value) if value else None
    return None


def _parse_published_date(entry: object) -> str | None:
    published = entry.get("published") or entry.get("updated")
    if not published:
        return None
    try:
        return parsedate_to_datetime(str(published)).isoformat()
    except (TypeError, ValueError):
        return str(published)

def _extract_eligibility(text: str) -> str | None:
    section = _extract_section(
        text,
        "Who can apply",
        (
            "Who is eligible",
            "Who is not eligible",
            "International researchers",
            "What we're looking for",
            "How to apply",
            "How we will assess",
            "Contact details",
        ),
    )
    if section:
        return section

    for marker in (
        "You must be based",
        "This opportunity is open",
        "This opportunity is only open",
        "UK registered organisations can apply",
        "UK registered academic institutions can apply",
        "To lead a project",
        "You must:",
    ):
        index = text.lower().find(marker.lower())
        if index >= 0:
            lines = text[index:].splitlines()
            selected: list[str] = []
            for line in lines:
                if selected and line.endswith(":"):
                    break
                selected.append(line)
                if len(" ".join(selected)) > 350:
                    break
            eligibility = " ".join(selected).strip()
            if "provide a descriptive caption" in eligibility.lower():
                continue
            return eligibility
    return None


def _extract_section(text: str, start_label: str, stop_labels: tuple[str, ...]) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    collecting = False
    selected: list[str] = []
    for line in lines:
        if not collecting:
            collecting = line.lower() == start_label.lower()
            continue
        if any(line.lower().startswith(stop.lower()) for stop in stop_labels):
            break
        selected.append(line)
        if len(" ".join(selected)) > 450:
            break

    value = " ".join(selected).strip()
    if not value or "provide a descriptive caption" in value.lower():
        return None
    return value


def _clean_date(value: str | None) -> str | None:
    if not value:
        return None
    markers = (
        " See ",
        " Start application",
        " Last updated:",
        " Apply for ",
        " UK registered",
        " Organisations can apply",
        " An opportunity",
    )
    cleaned = value
    for marker in markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0]
    return cleaned.strip(" .") or None


def _best_summary(feed_summary: str, detail_text: str, title: str) -> str:
    if len(feed_summary) > 250:
        return feed_summary
    lines = detail_text.splitlines()
    useful: list[str] = []
    skip_prefixes = (
        "funding finder",
        "opportunity status",
        "funders",
        "funding type",
        "total fund",
        "publication date",
        "opening date",
        "closing date",
    )
    for line in lines:
        lowered = line.lower()
        if not line or lowered.startswith(skip_prefixes):
            continue
        if line.strip() == title.strip():
            continue
        useful.append(line)
        if len(" ".join(useful)) > 600:
            break
    return "\n".join(useful) if useful else feed_summary
