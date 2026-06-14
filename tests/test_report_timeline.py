from datetime import date, datetime

from app.config import Config
from app.models import FundingOpportunity
from app.report import (
    build_timeline,
    generate_daily_debrief,
    generate_discord_debrief,
    parse_opportunity_date,
)


def opportunity(
    external_id: str,
    title: str,
    closing_date: str | None,
    *,
    opening_date: str | None = None,
    status: str = "Open",
    score: int = 8,
) -> FundingOpportunity:
    return FundingOpportunity(
        source="Test",
        external_id=external_id,
        title=title,
        funder="Example Funder",
        opening_date=opening_date,
        closing_date=closing_date,
        status=status,
        relevance_score=score,
        url=f"https://example.test/{external_id}",
    )


def test_parse_opportunity_date_handles_common_source_formats() -> None:
    assert parse_opportunity_date("2026-07-01") == date(2026, 7, 1)
    assert parse_opportunity_date("Friday, 1 August 2026 at 11:00am") == date(2026, 8, 1)
    assert parse_opportunity_date("01/09/2026") == date(2026, 9, 1)
    assert parse_opportunity_date("not a date") is None


def test_build_timeline_splits_new_expiring_and_ongoing_calls() -> None:
    config = Config(relevant_score_threshold=4)
    new_call = opportunity("new", "New call", "2026-08-01")
    expiring_call = opportunity("soon", "Soon call", "2026-06-30")
    ongoing_call = opportunity("ongoing", "Ongoing call", "2026-09-01")
    low_score_call = opportunity("low", "Low score call", "2026-06-20", score=1)
    closed_call = opportunity("closed", "Closed call", "2026-06-20", status="Closed")

    timeline = build_timeline(
        fetched_opportunities=[
            new_call,
            expiring_call,
            ongoing_call,
            low_score_call,
            closed_call,
        ],
        new_opportunities=[new_call],
        config=config,
        today=date(2026, 6, 14),
    )

    assert timeline.new == [new_call]
    assert timeline.expiring_soon == [expiring_call]
    assert timeline.ongoing == [ongoing_call]


def test_reports_include_channel_appropriate_timeline_sections() -> None:
    config = Config(relevant_score_threshold=4)
    new_call = opportunity("new", "New call", "2026-08-01")
    expiring_call = opportunity("soon", "Soon call", "2026-06-30")
    ongoing_call = opportunity("ongoing", "Ongoing call", "2026-09-01")
    generated_at = datetime(2026, 6, 14, 8, 0)

    plain_text = generate_daily_debrief(
        fetched_opportunities=[new_call, expiring_call, ongoing_call],
        new_opportunities=[new_call],
        changed_opportunities=[],
        known_opportunities=[expiring_call, ongoing_call],
        config=config,
        generated_at=generated_at,
    )
    discord = generate_discord_debrief(
        fetched_opportunities=[new_call, expiring_call, ongoing_call],
        new_opportunities=[new_call],
        changed_opportunities=[],
        known_opportunities=[expiring_call, ongoing_call],
        config=config,
        generated_at=generated_at,
    )

    assert "Funding timeline:" in plain_text
    assert "New funding calls:" in plain_text
    assert "Expiring within 30 days:" in plain_text
    assert "closes 2026-06-30 (16 days left)" in plain_text
    assert "**Funding timeline**" in discord
    assert "**Other ongoing**" in discord
    assert "- **Soon call** - closes 2026-06-30 (16 days left); score 8" in discord
