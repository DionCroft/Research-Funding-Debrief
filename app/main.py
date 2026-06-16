"""Command-line entry point for Research Funding Debrief."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import replace
from logging.handlers import RotatingFileHandler

from app.config import Config, load_config
from app.database import OpportunityDatabase
from app.discord_notifier import send_discord_report
from app.emailer import send_email_report
from app.filters import score_opportunities
from app.report import generate_daily_debrief, generate_discord_debrief
from app.sources.registry import SOURCE_FACTORIES, build_sources


logger = logging.getLogger(__name__)


def setup_logging(config: Config) -> None:
    """Configure file and console logging."""

    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        config.log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def setup_console_encoding() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description="Generate a research funding debrief.")
    parser.add_argument(
        "--sources",
        help=(
            "Comma-separated sources to run. "
            f"Available: {', '.join(sorted(SOURCE_FACTORIES))}"
        ),
    )
    parser.add_argument("--min-score", type=int, help="Override the relevant score threshold.")
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Hide previously seen opportunities from the terminal report.",
    )
    parser.add_argument(
        "--send-discord",
        action="store_true",
        help="Force Discord sending for this run if Discord credentials are configured.",
    )
    parser.add_argument(
        "--refresh-live-json",
        action="store_true",
        help="Write web/data/live-updates.json from the same fetched opportunities.",
    )
    parser.add_argument(
        "--no-discord",
        action="store_true",
        help="Disable Discord sending for this run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch, score, and report without writing to SQLite or sending notifications.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    """Run the daily funding debrief workflow."""

    args = build_parser().parse_args(argv)
    setup_console_encoding()
    config = load_config()
    config = _apply_cli_overrides(config, args)
    setup_logging(config)
    logger.info("Research Funding Debrief run started.")

    database = OpportunityDatabase(config.database_path)
    if not args.dry_run:
        try:
            database.initialise()
        except Exception:
            logger.exception("Database initialisation failed.")
            print("Could not initialise the local database. Check the logs for details.")
            return 1

    sources = build_sources(config.enabled_sources, config)
    if not sources:
        print("No valid funding sources are configured.")
        logger.warning("No valid funding sources configured: %s", config.enabled_sources)
        return 1

    opportunities = []
    for source in sources:
        try:
            opportunities.extend(source.fetch())
        except Exception:
            logger.exception("Source failed unexpectedly: %s", source.name)

    logger.info("Fetched %s opportunities.", len(opportunities))

    scored_opportunities = score_opportunities(opportunities, config.keywords)

    if args.dry_run:
        new_opportunities = scored_opportunities
        changed_opportunities = []
        known_opportunities = []
        logger.info("Dry run enabled; skipping database writes.")
    else:
        try:
            new_opportunities, changed_opportunities, known_opportunities = database.store_opportunities(
                scored_opportunities
            )
        except Exception:
            logger.exception("Failed to store opportunities.")
            print("Fetched opportunities, but could not update the local database.")
            return 1

    logger.info("New records: %s.", len(new_opportunities))
    logger.info("Changed records: %s.", len(changed_opportunities))

    if args.refresh_live_json and not args.dry_run:
        try:
            from web.live_updates import write_live_updates

            write_live_updates(
                scored_opportunities,
                database,
                list(SOURCE_FACTORIES),
                relevant_score_threshold=config.relevant_score_threshold,
            )
            logger.info("Live JSON snapshot refreshed.")
        except Exception:
            logger.exception("Failed to refresh live JSON snapshot.")
            print("Fetched opportunities, but could not refresh the live JSON snapshot.")

    report = generate_daily_debrief(
        fetched_opportunities=scored_opportunities,
        new_opportunities=new_opportunities,
        changed_opportunities=changed_opportunities,
        known_opportunities=known_opportunities,
        config=config,
        include_known=not args.new_only,
    )
    print(report)

    subject = "Daily Research Funding Debrief"
    if args.dry_run:
        logger.info("Dry run enabled; skipping email and Discord notifications.")
    else:
        send_email_report(subject, report, config=config)
        discord_report = generate_discord_debrief(
            fetched_opportunities=scored_opportunities,
            new_opportunities=new_opportunities,
            changed_opportunities=changed_opportunities,
            known_opportunities=known_opportunities,
            config=config,
        )
        send_discord_report(discord_report, config=config)

    logger.info("Research Funding Debrief run finished.")
    return 0


def _apply_cli_overrides(config: Config, args: argparse.Namespace) -> Config:
    sources = config.enabled_sources
    if args.sources:
        sources = [source.strip() for source in args.sources.split(",") if source.strip()]

    enable_discord = config.enable_discord
    if args.send_discord:
        enable_discord = True
    if args.no_discord:
        enable_discord = False

    relevant_score_threshold = (
        args.min_score if args.min_score is not None else config.relevant_score_threshold
    )

    return replace(
        config,
        enabled_sources=sources,
        enable_discord=enable_discord,
        relevant_score_threshold=relevant_score_threshold,
    )


if __name__ == "__main__":
    raise SystemExit(run())
