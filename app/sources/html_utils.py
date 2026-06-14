"""Shared helpers for HTML-backed funding sources."""

from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


USER_AGENT = "ResearchFundingDebrief/0.2"
STOP_LABELS = {
    "opportunity status",
    "funders",
    "funder",
    "co-funders",
    "funding type",
    "total fund",
    "maximum award",
    "award range",
    "publication date",
    "opening date",
    "closing date",
    "location",
    "funding organisation",
    "who can apply",
    "how much you can get",
    "total size of grant scheme",
    "eligibility",
    "opened",
    "opens",
    "closes",
    "start application",
    "print and download options",
    "guidance on good research",
    "subscribe to ukri emails",
}


def get_soup(url: str, timeout: int = 30) -> BeautifulSoup:
    """Fetch a URL and return a BeautifulSoup document."""

    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def absolute_url(base_url: str, href: str) -> str:
    """Return an absolute URL for a possibly relative href."""

    return urljoin(base_url, href)


def clean_text(value: str | Tag) -> str:
    """Convert HTML or a tag into normalised plain text."""

    if isinstance(value, Tag):
        text = value.get_text("\n")
    else:
        soup = BeautifulSoup(value, "html.parser")
        text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_label(text: str, label: str) -> str | None:
    """Extract a label/value pair from normalised text."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    label_lower = label.lower().strip(":")
    value_lines: list[str] = []
    collecting = False

    for line in lines:
        line_label = _normalise_label(line)
        if not collecting:
            inline = re.match(rf"{re.escape(label)}\s*:\s*(.+)", line, re.IGNORECASE)
            if inline:
                value = inline.group(1).strip()
                return value or None
            if line_label == label_lower:
                collecting = True
            continue

        if _is_stop_label(line):
            break
        value_lines.append(line)

    value = " ".join(value_lines)
    return re.sub(r"\s+", " ", value).strip(" ,") or None


def first_matching_line(text: str, prefixes: tuple[str, ...]) -> str | None:
    """Return the first line starting with one of the supplied prefixes."""

    for line in text.splitlines():
        stripped = line.strip()
        if any(stripped.lower().startswith(prefix.lower()) for prefix in prefixes):
            return stripped
    return None


def nearby_block_text(link: Tag) -> str:
    """Return useful text around a result link."""

    for parent_name in ("li", "article", "section", "div"):
        parent = link.find_parent(parent_name)
        if parent:
            text = clean_text(parent)
            if len(text) > len(link.get_text(strip=True)):
                return text
    return clean_text(link)


def _normalise_label(line: str) -> str:
    return line.strip().strip(":").lower()


def _is_stop_label(line: str) -> bool:
    label = _normalise_label(line)
    if label in STOP_LABELS:
        return True
    if line.strip().endswith(":") and len(line.strip()) < 70:
        return True
    return False
