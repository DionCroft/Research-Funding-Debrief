"""Local signup server for the Research Funding Debrief front page."""

from __future__ import annotations

import argparse
import json
import os
import sys
import sqlite3
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


WEB_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_ROOT.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "signup_subscribers.db"
HOST = "127.0.0.1"
PORT = 8080


class SignupHandler(SimpleHTTPRequestHandler):
    """Serve the front page and persist signup submissions."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/signup":
            self.send_error(404, "Not found")
            return

        try:
            payload = self._read_json()
            subscriber = _validate_signup(payload)
            _save_signup(subscriber)
        except ValueError as error:
            self._send_json({"message": str(error)}, status=400)
            return
        except Exception:
            self._send_json({"message": "Could not save this signup."}, status=500)
            return

        frequency = subscriber["frequency"]
        self._send_json({"message": f"You're on the {frequency} briefing list."})

    def _read_json(self) -> dict[str, object]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise ValueError("Invalid signup details.") from error
        if not isinstance(payload, dict):
            raise ValueError("Invalid signup details.")
        return payload

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _validate_signup(payload: dict[str, object]) -> dict[str, object]:
    first_name = _clean_text(payload.get("firstName"))
    last_name = _clean_text(payload.get("lastName"))
    email = _clean_text(payload.get("email")).lower()
    frequency = _clean_text(payload.get("frequency")).lower() or "daily"
    topics = payload.get("topics")

    if not first_name or not last_name:
        raise ValueError("Please provide your first and last name.")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("Please provide a valid email address.")
    if frequency not in {"daily", "weekly"}:
        raise ValueError("Choose daily or weekly email frequency.")
    if not isinstance(topics, list) or not topics:
        raise ValueError("Choose at least one topic of interest.")

    cleaned_topics = [_clean_text(topic) for topic in topics if _clean_text(topic)]
    if not cleaned_topics:
        raise ValueError("Choose at least one topic of interest.")

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "frequency": frequency,
        "topics": cleaned_topics,
    }


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _save_signup(subscriber: dict[str, object]) -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                frequency TEXT NOT NULL,
                topics TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO subscribers (
                first_name, last_name, email, frequency, topics, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                frequency = excluded.frequency,
                topics = excluded.topics,
                updated_at = excluded.updated_at
            """,
            (
                subscriber["first_name"],
                subscriber["last_name"],
                subscriber["email"],
                subscriber["frequency"],
                json.dumps(subscriber["topics"]),
                now,
                now,
            ),
        )
        connection.commit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the Research Funding Debrief signup page.")
    host = os.getenv("SIGNUP_SERVER_HOST", HOST)
    port = int(os.getenv("SIGNUP_SERVER_PORT", str(PORT)))
    parser.add_argument("--host", default=host, help=f"Host to bind. Default: {host}")
    parser.add_argument("--port", type=int, default=port, help=f"Port to bind. Default: {port}")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        server = ThreadingHTTPServer((args.host, args.port), SignupHandler)
    except OSError as error:
        if error.errno == 98:
            print(
                (
                    f"Port {args.port} is already in use. "
                    f"Try: python web/server.py --port {args.port + 1}"
                ),
                file=sys.stderr,
            )
            return 1
        raise

    print(f"Research Funding Debrief signup page: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
