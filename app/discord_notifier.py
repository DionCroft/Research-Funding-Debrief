"""Discord notification scaffold."""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import Config, load_config


logger = logging.getLogger(__name__)
DISCORD_API_BASE_URL = "https://discord.com/api/v10"
DISCORD_MESSAGE_LIMIT = 1900
DISCORD_SUPPRESS_EMBEDS_FLAG = 4


def send_discord_report(body: str, config: Config | None = None) -> bool:
    """Post the report to Discord when Discord is explicitly enabled."""

    config = config or load_config()
    if not config.enable_discord:
        logger.info("Discord disabled; skipping Discord report.")
        return False

    if config.discord_webhook_url:
        return _send_via_webhook(body, config.discord_webhook_url)

    if config.discord_bot_token and config.discord_channel_id:
        return _send_via_bot(body, config.discord_bot_token, config.discord_channel_id)

    logger.warning(
        "Discord enabled but no delivery method is configured. "
        "Set DISCORD_WEBHOOK_URL or both DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID."
    )
    return False


def _send_via_webhook(body: str, webhook_url: str) -> bool:
    try:
        for chunk in _message_chunks(body):
            response = requests.post(
                webhook_url,
                json=_message_payload(chunk),
                timeout=20,
            )
            response.raise_for_status()
        logger.info("Discord report sent via webhook.")
        return True
    except requests.RequestException:
        logger.exception("Discord webhook report failed.")
        return False


def _send_via_bot(body: str, bot_token: str, channel_id: str) -> bool:
    try:
        for chunk in _message_chunks(body):
            response = requests.post(
                f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages",
                headers={
                    "Authorization": f"Bot {bot_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "ResearchFundingDebrief/0.2",
                },
                json=_message_payload(chunk),
                timeout=20,
            )
            response.raise_for_status()
        logger.info("Discord report sent via bot.")
        return True
    except requests.RequestException:
        logger.exception("Discord bot report failed.")
        return False


def _message_payload(body: str) -> dict[str, Any]:
    return {
        "content": body,
        "flags": DISCORD_SUPPRESS_EMBEDS_FLAG,
        "allowed_mentions": {"parse": []},
    }


def _message_chunks(body: str) -> list[str]:
    """Split a Discord message without breaking lines where possible."""

    if len(body) <= DISCORD_MESSAGE_LIMIT:
        return [body]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for line in body.splitlines():
        line_length = len(line) + 1
        if current and current_length + line_length > DISCORD_MESSAGE_LIMIT:
            chunks.append("\n".join(current).rstrip())
            current = []
            current_length = 0

        if line_length > DISCORD_MESSAGE_LIMIT:
            for start in range(0, len(line), DISCORD_MESSAGE_LIMIT):
                chunks.append(line[start : start + DISCORD_MESSAGE_LIMIT])
            continue

        current.append(line)
        current_length += line_length

    if current:
        chunks.append("\n".join(current).rstrip())

    return chunks
