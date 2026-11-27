"""Verify the public snapshot and notify the scheduled job's Discord destination."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import replace
from pathlib import Path

import requests

from app.config import PUBLIC_JSON_PATH, PUBLIC_RSS_PATH, PUBLIC_SITE_URL, load_config
from app.discord_notifier import send_discord_report


def verify_publication(
    paths: tuple[Path, ...] = (PUBLIC_JSON_PATH, PUBLIC_RSS_PATH),
    timeout: float = 600,
    interval: float = 15,
) -> bool:
    """Wait for GitHub Pages to serve the exact contents of both local feed files."""

    expected = {
        path.name: path.read_bytes().replace(b"\r\n", b"\n") for path in paths
    }
    deadline = time.monotonic() + timeout
    while True:
        pending = []
        for name, content in expected.items():
            try:
                response = requests.get(
                    f"{PUBLIC_SITE_URL}data/{name}",
                    params={"verify": time.time_ns()},
                    headers={"Cache-Control": "no-cache"},
                    timeout=10,
                )
                response.raise_for_status()
            except requests.RequestException:
                pending.append(name)
                continue
            if response.content.replace(b"\r\n", b"\n") != content:
                pending.append(name)

        if not pending:
            print("Verified the JSON and RSS snapshots on GitHub Pages.")
            return True

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logging.error("Public snapshot did not match: %s", ", ".join(pending))
            return False
        time.sleep(min(interval, remaining))


def send_publication_alert(stage: str, exit_code: int) -> bool:
    config = replace(load_config(), enable_discord=True)
    return send_discord_report(
        "**Research Funding Debrief publication failed**\n"
        f"Stage: {stage} (exit {exit_code}).\n"
        "Check the scheduled refresh and application logs. "
        "If the push succeeded, check the GitHub Pages deployment run.",
        config=config,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="Wait for Pages to serve both updated feeds.")
    alert = commands.add_parser("alert", help="Send a publishing failure alert to Discord.")
    alert.add_argument("stage")
    alert.add_argument("exit_code", type=int)
    args = parser.parse_args()

    if args.command == "verify":
        return 0 if verify_publication() else 1
    return 0 if send_publication_alert(args.stage, args.exit_code) else 1


if __name__ == "__main__":
    raise SystemExit(main())
