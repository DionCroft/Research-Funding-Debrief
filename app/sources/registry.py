"""Funding source registry."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from app.config import Config
from app.sources.base import FundingSource
from app.sources.find_a_grant import FindAGrantSource
from app.sources.innovate_uk import InnovateUKSource
from app.sources.ukri import UKRIFundingSource


logger = logging.getLogger(__name__)

SourceFactory = Callable[[Config], FundingSource]


SOURCE_FACTORIES: dict[str, SourceFactory] = {
    "ukri": lambda config: UKRIFundingSource(config.ukri_rss_url),
    "innovate_uk": lambda config: InnovateUKSource(config.innovate_uk_search_url),
    "find_a_grant": lambda config: FindAGrantSource(config.find_a_grant_url),
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
