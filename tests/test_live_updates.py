import json
from datetime import date, datetime, timezone
from xml.etree import ElementTree as ET

from app.database import OpportunityDatabase
from app.models import FundingOpportunity
from web.live_updates import MAX_FEATURED_ITEMS, _fetch_opportunities, write_live_updates


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
        published_date="1 June 2026",
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
    assert len(payload["allItems"]) == 2
    status_by_title = {
        item["title"]: item["statusLabels"]
        for item in payload["items"]
    }
    assert status_by_title["New AI funding"][0] == "New"
    assert status_by_title["Seen robotics funding"][0] == "Seen"
    new_item = next(
        item for item in payload["items"] if item["title"] == "New AI funding"
    )
    assert new_item["publishedLabel"] == "1 June 2026"
    assert new_item["firstSeenAt"].startswith("2026-06-10")

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
    new_rss_item = next(
        item
        for item in rss.findall("./channel/item")
        if item.findtext("title") == "New AI funding"
    )
    assert new_rss_item.findtext("pubDate").startswith("Mon, 01 Jun 2026")
    assert new_rss_item.findtext("publishedDate") == "1 June 2026"
    assert new_rss_item.findtext("firstSeenAt").startswith("2026-06-10")
    assert "Published: 1 June 2026" in new_rss_item.findtext("description")


def test_rss_uses_all_active_calls_not_only_featured_items(tmp_path) -> None:
    database = OpportunityDatabase(tmp_path / "funding.db")
    database.initialise()
    opportunities = [
        FundingOpportunity(
            source="UKRI",
            external_id=f"item-{index}",
            title=f"Active funding {index:03}",
            summary="Research grant for active opportunities.",
            status="Open",
            closing_date="31 December 2026",
            url=f"https://example.test/{index}",
            categories=["AI / Data"],
            relevance_score=5,
            first_seen_at=datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat(
                timespec="seconds"
            ),
        )
        for index in range(MAX_FEATURED_ITEMS + 1)
    ]
    database.store_opportunities(opportunities)

    json_path = tmp_path / "live-updates.json"
    rss_path = tmp_path / "live-updates.xml"
    write_live_updates(
        opportunities,
        database,
        ["ukri"],
        output_path=json_path,
        rss_output_path=rss_path,
        today=date(2026, 6, 16),
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload["items"]) == MAX_FEATURED_ITEMS
    assert len(payload["allItems"]) == MAX_FEATURED_ITEMS + 1
    assert payload["summary"]["featuredCalls"] == MAX_FEATURED_ITEMS
    assert payload["summary"]["rssCalls"] == MAX_FEATURED_ITEMS + 1

    rss = ET.parse(rss_path)
    assert len(rss.findall("./channel/item")) == MAX_FEATURED_ITEMS + 1


def test_fetch_opportunities_skips_failed_sources() -> None:
    expected = FundingOpportunity(
        source="Working source",
        external_id="working-item",
        title="Working funding",
        summary="A source that still parses.",
        status="Open",
    )

    class BrokenSource:
        name = "Broken source"

        def fetch(self) -> list[FundingOpportunity]:
            raise RuntimeError("parser exploded")

    class WorkingSource:
        name = "Working source"

        def fetch(self) -> list[FundingOpportunity]:
            return [expected]

    assert _fetch_opportunities([BrokenSource(), WorkingSource()]) == [expected]
