"""Install the signup web server as a user-level systemd service."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "deploy" / "systemd" / "research-funding-signup.service.in"
SERVICE_NAME = "research-funding-signup.service"
USER_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install the signup server systemd user service.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind. Default: 8080")
    parser.add_argument(
        "--no-enable-linger",
        action="store_true",
        help="Skip loginctl enable-linger for this user.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    python_bin = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not python_bin.exists():
        raise SystemExit(f"Could not find virtualenv Python at {python_bin}")

    service = TEMPLATE_PATH.read_text(encoding="utf-8")
    service = service.replace("{{PROJECT_DIR}}", str(PROJECT_ROOT))
    service = service.replace("{{PYTHON_BIN}}", str(python_bin))
    service = service.replace("{{HOST}}", args.host)
    service = service.replace("{{PORT}}", str(args.port))

    USER_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    service_path = USER_SYSTEMD_DIR / SERVICE_NAME
    service_path.write_text(service, encoding="utf-8")

    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", SERVICE_NAME])
    if not args.no_enable_linger:
        subprocess.run(["loginctl", "enable-linger"], check=False)

    print(f"Installed {service_path}")
    print(f"Signup server should be available at http://{args.host}:{args.port}")
    print(f"Check status with: systemctl --user status {SERVICE_NAME}")
    return 0


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
