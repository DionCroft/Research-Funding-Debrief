"""Discord notification scaffold."""

from __future__ import annotations

import logging

import requests

from app.config import Config, load_config


logger = logging.getLogger(__name__)


def send_discord_report(body: str, config: Config | None = None) -> bool:
    """Post the report to Discord when Discord is explicitly enabled."""

    config = config or load_config()
    if not config.enable_discord:
        logger.info("Discord disabled; skipping Discord report.")
        return False

    if not config.discord_webhook_url:
        logger.warning("Discord enabled but DISCORD_WEBHOOK_URL is missing.")
        return False

    try:
        response = requests.post(
            config.discord_webhook_url,
            json={"content": body[:1900]},
            timeout=20,
        )
        response.raise_for_status()
        logger.info("Discord report sent.")
        return True
    except requests.RequestException:
        logger.exception("Discord report failed.")
        return False
