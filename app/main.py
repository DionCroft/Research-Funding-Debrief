"""Command-line entry point for Research Funding Debrief."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import Config, load_config
from app.database import OpportunityDatabase
from app.discord_notifier import send_discord_report
from app.emailer import send_email_report
from app.filters import score_opportunities
from app.report import generate_daily_debrief
from app.sources.ukri import UKRIFundingSource


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


def run() -> int:
    """Run the daily funding debrief workflow."""

    config = load_config()
    setup_logging(config)
    logger.info("Research Funding Debrief run started.")

    database = OpportunityDatabase(config.database_path)
    try:
        database.initialise()
    except Exception:
        logger.exception("Database initialisation failed.")
        print("Could not initialise the local database. Check the logs for details.")
        return 1

    source = UKRIFundingSource(config.ukri_rss_url)
    opportunities = source.fetch()
    logger.info("Fetched %s opportunities.", len(opportunities))

    scored_opportunities = score_opportunities(opportunities, config.keywords)

    try:
        new_opportunities, known_opportunities = database.store_opportunities(scored_opportunities)
    except Exception:
        logger.exception("Failed to store opportunities.")
        print("Fetched opportunities, but could not update the local database.")
        return 1

    logger.info("New records: %s.", len(new_opportunities))
    report = generate_daily_debrief(
        fetched_opportunities=scored_opportunities,
        new_opportunities=new_opportunities,
        known_opportunities=known_opportunities,
        config=config,
    )
    print(report)

    subject = "Daily Research Funding Debrief"
    send_email_report(subject, report, config=config)
    send_discord_report(report, config=config)

    logger.info("Research Funding Debrief run finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
