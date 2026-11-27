from unittest.mock import Mock

import requests

from app.config import Config
from scripts import publication


def test_verify_waits_for_both_files(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "live-updates.json"
    rss_path = tmp_path / "live-updates.xml"
    json_path.write_bytes(b"new JSON")
    rss_path.write_bytes(b"new RSS")

    get = Mock(
        side_effect=[
            Mock(content=b"new JSON"),
            requests.HTTPError("RSS unavailable"),
            Mock(content=b"new JSON"),
            Mock(content=b"new RSS"),
        ]
    )
    monkeypatch.setattr(publication.requests, "get", get)
    monkeypatch.setattr(publication.time, "sleep", Mock())
    assert publication.verify_publication((json_path, rss_path), timeout=10)
    assert get.call_count == 4


def test_verify_rejects_an_old_public_snapshot(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "live-updates.json"
    json_path.write_bytes(b"new JSON")
    monkeypatch.setattr(publication.requests, "get", Mock(return_value=Mock(content=b"old JSON")))
    assert not publication.verify_publication((json_path,), timeout=0)


def test_publication_alert_uses_the_configured_discord_channel(monkeypatch) -> None:
    config = Config(discord_bot_token="test-token", discord_channel_id="test-channel")
    notify = Mock(return_value=True)
    monkeypatch.setattr(publication, "load_config", lambda: config)
    monkeypatch.setattr(publication, "send_discord_report", notify)

    assert publication.send_publication_alert("verifying GitHub Pages", 1)
    message = notify.call_args.args[0]
    supplied_config = notify.call_args.kwargs["config"]
    assert "publication failed" in message
    assert "verifying GitHub Pages (exit 1)" in message
    assert supplied_config.enable_discord
    assert supplied_config.discord_channel_id == "test-channel"
