"""Funding source registry."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from app.config import Config
from app.sources.base import FundingSource
from app.sources.find_a_grant import FindAGrantSource
from app.sources.innovate_uk import InnovateUKSource
from app.sources.nihr import NIHRFundingSource
from app.sources.raeng import RAEngProgrammesSource
from app.sources.royal_society import RoyalSocietyGrantsSource
from app.sources.ukri import UKRIFundingSource
from app.sources.wellcome import WellcomeFundingSource


logger = logging.getLogger(__name__)

SOURCE_REGISTRY: dict[str, tuple[type[FundingSource], Callable[[Config], str]]] = {
    "ukri": (UKRIFundingSource, lambda config: config.ukri_rss_url),
    "innovate_uk": (InnovateUKSource, lambda config: config.innovate_uk_search_url),
    "find_a_grant": (FindAGrantSource, lambda config: config.find_a_grant_url),
    "nihr": (NIHRFundingSource, lambda config: config.nihr_funding_url),
    "wellcome": (WellcomeFundingSource, lambda config: config.wellcome_funding_url),
    "royal_society": (RoyalSocietyGrantsSource, lambda config: config.royal_society_grants_url),
    "raeng": (RAEngProgrammesSource, lambda config: config.raeng_programmes_url),
}
SOURCE_NAMES = tuple(source_type.name for source_type, _ in SOURCE_REGISTRY.values())


def build_sources(source_names: Sequence[str], config: Config) -> list[FundingSource]:
    """Build source objects for configured source names."""

    sources: list[FundingSource] = []
    for key in dict.fromkeys(name.strip().lower() for name in source_names):
        definition = SOURCE_REGISTRY.get(key)
        if definition is None:
            logger.warning("Unknown funding source configured: %s", key)
            continue
        source_type, get_url = definition
        sources.append(source_type(get_url(config)))
    return sources
