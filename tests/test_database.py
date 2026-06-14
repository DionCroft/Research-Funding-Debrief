import sqlite3

from app.database import OpportunityDatabase
from app.models import FundingOpportunity


def test_opportunity_model_creation() -> None:
    opportunity = FundingOpportunity(
        source="UKRI",
        external_id="https://example.test/opportunity",
        title="Example opportunity",
    )

    assert opportunity.source == "UKRI"
    assert opportunity.display_funder() == "Unknown"
    assert opportunity.matched_keywords == []
    assert opportunity.categories == []
    assert opportunity.bid_summary == []
    assert opportunity.relevance_score == 0


def test_database_insert_and_duplicate_detection(tmp_path) -> None:
    database = OpportunityDatabase(tmp_path / "test.db")
    database.initialise()
    opportunity = FundingOpportunity(
        source="UKRI",
        external_id="item-1",
        title="Robotics funding",
        summary="A test opportunity.",
        matched_keywords=["robotics"],
        relevance_score=3,
        url="https://example.test/item-1",
    )

    first_insert = database.store_opportunity(opportunity)
    second_insert = database.store_opportunity(opportunity)

    assert first_insert.status == "new"
    assert second_insert.status == "known"
    assert opportunity.first_seen_at is not None
    assert opportunity.last_seen_at is not None


def test_database_detects_changed_opportunity(tmp_path) -> None:
    database = OpportunityDatabase(tmp_path / "test.db")
    database.initialise()
    opportunity = FundingOpportunity(
        source="UKRI",
        external_id="item-2",
        title="AI funding",
        summary="Initial summary.",
        status="Upcoming",
    )

    database.store_opportunity(opportunity)
    opportunity.status = "Open"
    result = database.store_opportunity(opportunity)

    assert result.status == "changed"
    assert "Status changed" in result.changes


def test_database_migrates_existing_schema(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT NOT NULL,
                funder TEXT,
                summary TEXT,
                amount TEXT,
                status TEXT,
                opening_date TEXT,
                closing_date TEXT,
                published_date TEXT,
                url TEXT,
                matched_keywords TEXT NOT NULL DEFAULT '[]',
                relevance_score INTEGER NOT NULL DEFAULT 0,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(source, external_id)
            )
            """
        )

    database = OpportunityDatabase(db_path)
    database.initialise()
    result = database.store_opportunity(
        FundingOpportunity(
            source="Innovate UK",
            external_id="legacy-test",
            title="Robotics adoption",
            categories=["Robotics / Automation"],
            bid_summary=["Why it may fit: robotics."],
        )
    )

    assert result.status == "new"
