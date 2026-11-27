import json
from datetime import date, datetime, timezone
from xml.etree import ElementTree as ET

import pytest
import requests

from app import main
from app.config import Config
from app.database import OpportunityDatabase
from app.models import FundingOpportunity
from app.sources.health import SourceCheck, fetch_sources
from app.sources.nihr import NIHRFundingSource
from web import live_updates
from web.live_updates import MAX_FEATURED_ITEMS, write_live_updates


PREVIOUS_CHECK = "2026-06-16T09:00:00+00:00"
CURRENT_CHECK = "2026-06-17T09:00:00+00:00"


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
        {
            "UKRI": SourceCheck("healthy", PREVIOUS_CHECK),
            "Innovate UK": SourceCheck("healthy", PREVIOUS_CHECK),
        },
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
        {"UKRI": SourceCheck("healthy", PREVIOUS_CHECK)},
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


def test_fetch_sources_distinguishes_healthy_empty_and_failed() -> None:
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

    class EmptySource:
        name = "Empty source"

        def fetch(self) -> list[FundingOpportunity]:
            return []

    opportunities, checks = fetch_sources([BrokenSource(), WorkingSource(), EmptySource()])
    assert opportunities == [expected]
    assert {source: check.status for source, check in checks.items()} == {
        "Broken source": "failed",
        "Working source": "healthy",
        "Empty source": "empty",
    }


def test_page_failure_does_not_accept_a_partial_nihr_result(monkeypatch) -> None:
    source = NIHRFundingSource()
    grant = FundingOpportunity(source="NIHR", external_id="first", title="First page")

    def get_first_page(url):
        if url == source.funding_url:
            return object()
        raise requests.Timeout("Second page timed out")

    monkeypatch.setattr("app.sources.nihr.get_soup", get_first_page)
    monkeypatch.setattr("app.sources.nihr.parse_nihr_opportunities", lambda *_: [grant])
    monkeypatch.setattr("app.sources.nihr._next_page_url", lambda *_: "https://example.test/page-2")
    opportunities, checks = fetch_sources([source])
    assert opportunities == []
    assert checks["NIHR"].status == "failed"


def test_failed_source_retains_legacy_items_until_recovery(tmp_path) -> None:
    database = OpportunityDatabase(tmp_path / "funding.db")
    database.initialise()
    json_path = tmp_path / "live-updates.json"
    rss_path = tmp_path / "live-updates.xml"
    legacy_item = {
        "rawSource": "UKRI",
        "source": "UKRI",
        "title": "Retained call",
        "url": "https://example.test/retained",
        "deadline": "20 June 2026",
        "urgency": "4 days left",
        "firstSeenAt": "2026-06-03T09:00:00+00:00",
        "lastSeenAt": PREVIOUS_CHECK,
        "statusLabels": ["Seen", "Closing soon", "Ongoing"],
        "relevanceScore": 5,
    }
    json_path.write_text(
        json.dumps(
            {
                "generatedAt": PREVIOUS_CHECK,
                "sourceCounts": {"UKRI": 2},
                "allItems": [
                    legacy_item,
                    {**legacy_item, "title": "Expired call", "deadline": "16 June 2026"},
                ],
            }
        ),
        encoding="utf-8",
    )
    fresh = FundingOpportunity(
        source="Find a Grant", external_id="new", title="Fresh call", status="Open"
    )
    database.store_opportunities([fresh])
    write_live_updates(
        [fresh],
        database,
        {
            "UKRI": SourceCheck("failed", CURRENT_CHECK),
            "Find a Grant": SourceCheck("healthy", CURRENT_CHECK),
            "NIHR": SourceCheck("empty", CURRENT_CHECK),
        },
        json_path,
        rss_path,
        today=date(2026, 6, 17),
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["sourcesScanned"] == 3
    assert payload["summary"]["sourcesVerified"] == 1
    assert payload["summary"]["closingSoon"] == 1
    assert [item["title"] for item in payload["allItems"]] == ["Retained call", "Fresh call"]
    retained = payload["allItems"][0]
    assert retained["lastSeenAt"] == PREVIOUS_CHECK
    assert retained["urgency"] == "3 days left"
    assert retained["sourceStale"] is True
    health = {row["source"]: row for row in payload["sourceHealth"]}
    assert health["UKRI"] == {
        "source": "UKRI",
        "rawSource": "UKRI",
        "status": "failed",
        "lastCheckedAt": CURRENT_CHECK,
        "lastSuccessAt": PREVIOUS_CHECK,
        "callCount": 1,
    }
    assert health["GOV.UK Find a Grant"]["lastSuccessAt"] == CURRENT_CHECK
    assert health["NIHR"]["status"] == "empty"
    assert health["Wellcome"]["status"] == "disabled"
    assert "last verified snapshot" in ET.parse(rss_path).findtext("./channel/item/description")

    next_check = "2026-06-18T09:00:00+00:00"
    write_live_updates(
        [],
        database,
        {"UKRI": SourceCheck("empty", next_check), "Find a Grant": SourceCheck("failed", next_check)},
        json_path,
        rss_path,
        today=date(2026, 6, 18),
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["sourcesVerified"] == 0
    assert all(item["sourceStale"] for item in payload["items"])
    assert payload["sourceHealth"][0]["lastSuccessAt"] == PREVIOUS_CHECK

    replacement = FundingOpportunity(
        source="UKRI", external_id="new-id", title="Recovered call", status="Open"
    )
    database.store_opportunities([replacement])
    write_live_updates(
        [replacement],
        database,
        {"UKRI": SourceCheck("healthy", next_check)},
        json_path,
        rss_path,
        today=date(2026, 6, 18),
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert [item["title"] for item in payload["allItems"]] == ["Recovered call"]
    assert payload["sourceHealth"][0]["lastSuccessAt"] == next_check


def test_unverified_first_snapshot_fails_without_writing(tmp_path) -> None:
    json_path = tmp_path / "live-updates.json"
    rss_path = tmp_path / "live-updates.xml"
    with pytest.raises(RuntimeError, match="no previous snapshot"):
        write_live_updates(
            [],
            OpportunityDatabase(tmp_path / "funding.db"),
            {"UKRI": SourceCheck("failed", CURRENT_CHECK)},
            json_path,
            rss_path,
        )
    assert not json_path.exists()
    assert not rss_path.exists()


def test_rss_generation_failure_keeps_previous_files(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "live-updates.json"
    rss_path = tmp_path / "live-updates.xml"
    json_path.write_text("previous JSON", encoding="utf-8")
    rss_path.write_text("previous RSS", encoding="utf-8")

    def fail_rss(*_):
        raise OSError("Could not write RSS")

    monkeypatch.setattr(live_updates, "_write_rss_feed", fail_rss)
    with pytest.raises(OSError, match="Could not write RSS"):
        write_live_updates(
            [],
            OpportunityDatabase(tmp_path / "funding.db"),
            {"UKRI": SourceCheck("healthy", CURRENT_CHECK)},
            json_path,
            rss_path,
        )
    assert json_path.read_text(encoding="utf-8") == "previous JSON"
    assert rss_path.read_text(encoding="utf-8") == "previous RSS"


def test_cli_exits_nonzero_when_snapshot_cannot_be_written(tmp_path, monkeypatch) -> None:
    config = Config(database_path=tmp_path / "funding.db")

    def fail_snapshot(*_):
        raise OSError("Could not write snapshot")

    monkeypatch.setattr(main, "load_config", lambda: config)
    monkeypatch.setattr(main, "setup_logging", lambda _: None)
    monkeypatch.setattr(main, "setup_console_encoding", lambda: None)
    monkeypatch.setattr(main, "build_sources", lambda *_: [object()])
    monkeypatch.setattr(main, "fetch_sources", lambda _: ([], {}))
    monkeypatch.setattr(live_updates, "write_live_updates", fail_snapshot)
    assert main.run(["--refresh-live-json"]) == 1
