import json
from datetime import date, datetime, timezone
from xml.etree import ElementTree as ET

from app.database import OpportunityDatabase
from app.models import FundingOpportunity
from web.live_updates import write_live_updates


def test_live_updates_marks_new_for_last_seven_days_and_writes_rss(tmp_path) -> None:
    database = OpportunityDatabase(tmp_path / "funding.db")
    database.initialise()
    new_opportunity = FundingOpportunity(
        source="UKRI",
        external_id="new-item",
        title="New AI funding",
        summary="Research grant for AI and data.",
        status="Open",
        closing_date="30 June 2026",
        url="https://example.test/new",
        categories=["AI / Data"],
        relevance_score=8,
        first_seen_at=datetime(2026, 6, 10, tzinfo=timezone.utc).isoformat(
            timespec="seconds"
        ),
    )
    seen_opportunity = FundingOpportunity(
        source="Innovate UK",
        external_id="seen-item",
        title="Seen robotics funding",
        summary="Innovation grant for robotics.",
        status="Open",
        closing_date="30 June 2026",
        url="https://example.test/seen",
        categories=["Robotics / Automation"],
        relevance_score=8,
        first_seen_at=datetime(2026, 6, 8, tzinfo=timezone.utc).isoformat(
            timespec="seconds"
        ),
    )
    database.store_opportunities([new_opportunity, seen_opportunity])

    json_path = tmp_path / "live-updates.json"
    rss_path = tmp_path / "live-updates.xml"
    write_live_updates(
        [new_opportunity, seen_opportunity],
        database,
        ["ukri", "innovate_uk"],
        output_path=json_path,
        rss_output_path=rss_path,
        today=date(2026, 6, 16),
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    status_by_title = {
        item["title"]: item["statusLabels"]
        for item in payload["items"]
    }
    assert status_by_title["New AI funding"][0] == "New"
    assert status_by_title["Seen robotics funding"][0] == "Seen"

    rss = ET.parse(rss_path)
    item_categories = {
        item.findtext("title"): [
            category.text for category in item.findall("category")
        ]
        for item in rss.findall("./channel/item")
    }
    assert "New" in item_categories["New AI funding"]
    assert "Seen" in item_categories["Seen robotics funding"]
    assert rss.findtext("./channel/title") == "Research Funding Debrief"
