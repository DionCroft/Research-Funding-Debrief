from app.config import Config
from app.discord_notifier import send_discord_report


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


def test_discord_skips_when_disabled() -> None:
    config = Config(enable_discord=False)

    assert send_discord_report("hello", config=config) is False


def test_discord_sends_via_bot_when_configured(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.discord_notifier.requests.post", fake_post)
    config = Config(
        enable_discord=True,
        discord_bot_token="dummy-token",
        discord_channel_id="123456789",
    )

    assert send_discord_report("hello", config=config) is True
    assert captured["url"].endswith("/channels/123456789/messages")
    assert captured["headers"]["Authorization"] == "Bot dummy-token"
    assert captured["json"] == {
        "content": "hello",
        "flags": 4,
        "allowed_mentions": {"parse": []},
    }


def test_discord_splits_long_messages(monkeypatch) -> None:
    payloads = []

    def fake_post(url, headers=None, json=None, timeout=None):
        payloads.append(json)
        return FakeResponse()

    monkeypatch.setattr("app.discord_notifier.requests.post", fake_post)
    config = Config(
        enable_discord=True,
        discord_bot_token="dummy-token",
        discord_channel_id="123456789",
    )

    assert send_discord_report("a\n" * 2200, config=config) is True
    assert len(payloads) > 1
    assert all(len(payload["content"]) <= 1900 for payload in payloads)
