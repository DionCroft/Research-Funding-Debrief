from app.filters import score_opportunity
from app.models import FundingOpportunity


def test_keyword_scoring_counts_title_summary_status_academic_and_amount() -> None:
    opportunity = FundingOpportunity(
        source="Test",
        external_id="abc",
        title="Sensors and IoT innovation grant",
        summary=(
            "This open call supports university collaboration in digital health. "
            "Funding of GBP 100,000 is available."
        ),
        status="Open",
        url="https://example.test/funding",
    )

    scored = score_opportunity(
        opportunity,
        keywords=["sensors", "IoT", "digital health", "robotics"],
    )

    assert scored.relevance_score == 12
    assert scored.matched_keywords == ["sensors", "IoT", "digital health"]
    assert scored.amount == "GBP 100,000"
    assert "Sensors / Instrumentation" in scored.categories
    assert "Electronics / IoT" in scored.categories
    assert "Digital Health" in scored.categories
    assert "AI / Data" not in scored.categories
    assert scored.bid_summary


def test_short_keyword_ai_does_not_match_inside_words() -> None:
    opportunity = FundingOpportunity(
        source="Test",
        external_id="chain",
        title="Supply chain funding",
        summary="Support for fair access to research.",
    )

    scored = score_opportunity(opportunity, keywords=["AI"])

    assert scored.relevance_score == 0
    assert scored.matched_keywords == []
    assert scored.categories == ["General / Low Match"]
