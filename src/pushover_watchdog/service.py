import os
import subprocess
from importlib import resources
from pathlib import Path


SERVICE_NAME = "watchdog.service"
APP_DIR = Path.home() / ".config" / "pushover-watchdog"
ENV_FILE = APP_DIR / "env"
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEMD_UNIT_PATH = SYSTEMD_USER_DIR / SERVICE_NAME


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def install_service() -> int:
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    APP_DIR.mkdir(parents=True, exist_ok=True)

    # Copy unit from package data
    unit_text = resources.files("pushover_watchdog.data").joinpath("watchdog.service").read_text(encoding="utf-8")
    SYSTEMD_UNIT_PATH.write_text(unit_text, encoding="utf-8")

    # Create env file if missing (user edits secrets)
    if not ENV_FILE.exists():
        ENV_FILE.write_text(
            "PUSHOVER_USER_KEY=\n"
            "PUSHOVER_APP_TOKEN=\n",
            encoding="utf-8",
        )
        os.chmod(ENV_FILE, 0o600)

    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "enable", "--now", SERVICE_NAME])

    print(f"Installed and started {SERVICE_NAME}")
    print(f"Edit secrets in: {ENV_FILE}")
    print("Logs: journalctl --user -u watchdog.service -f")
    print("If you want it running while logged out: loginctl enable-linger $USER")
    return 0
