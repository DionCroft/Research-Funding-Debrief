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

SourceFactory = Callable[[Config], FundingSource]


SOURCE_FACTORIES: dict[str, SourceFactory] = {
    "ukri": lambda config: UKRIFundingSource(config.ukri_rss_url),
    "innovate_uk": lambda config: InnovateUKSource(config.innovate_uk_search_url),
    "find_a_grant": lambda config: FindAGrantSource(config.find_a_grant_url),
    "nihr": lambda config: NIHRFundingSource(config.nihr_funding_url),
    "wellcome": lambda config: WellcomeFundingSource(config.wellcome_funding_url),
    "royal_society": lambda config: RoyalSocietyGrantsSource(config.royal_society_grants_url),
    "raeng": lambda config: RAEngProgrammesSource(config.raeng_programmes_url),
}


def build_sources(source_names: Sequence[str], config: Config) -> list[FundingSource]:
    """Build source objects for configured source names."""

    sources: list[FundingSource] = []
    for source_name in source_names:
        key = source_name.strip().lower()
        factory = SOURCE_FACTORIES.get(key)
        if not factory:
            logger.warning("Unknown funding source configured: %s", source_name)
            continue
        sources.append(factory(config))
    return sources
