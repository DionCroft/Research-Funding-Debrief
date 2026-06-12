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

    assert first_insert is True
    assert second_insert is False
    assert opportunity.first_seen_at is not None
    assert opportunity.last_seen_at is not None
