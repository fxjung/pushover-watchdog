import argparse
import os
import socket
import time
from dataclasses import dataclass

import psutil
import requests


PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
ENV_USER_KEY = "PUSHOVER_USER_KEY"
ENV_APP_TOKEN = "PUSHOVER_APP_TOKEN"

@dataclass
class TargetState:
    name: str
    last_above: bool = False
    last_alert_ts: float = 0.0


def fmt_bytes(n: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    x = float(n)
    for u in units:
        if x < 1024.0 or u == units[-1]:
            return f"{int(x)} B" if u == "B" else f"{x:.2f} {u}"
        x /= 1024.0
    return f"{x:.2f} PiB"


def send_pushover_alert(*, user_key: str, app_token: str, title: str, message: str) -> None:
    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message,
    }
    r = requests.post(PUSHOVER_API_URL, data=payload, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Pushover API error: HTTP {r.status_code} - {r.text}")


def get_ram_usage() -> tuple[float, int, int]:
    vm = psutil.virtual_memory()
    used = int(vm.total - vm.available)
    total = int(vm.total)
    frac = used / total if total else 0.0
    return frac, used, total


def get_disk_usage(path: str) -> tuple[float, int, int]:
    du = psutil.disk_usage(path)
    used = int(du.used)
    total = int(du.total)
    frac = used / total if total else 0.0
    return frac, used, total


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Watchdog: alert on high RAM or disk usage via Pushover.")

    # Pushover creds
    p.add_argument("--pushover-user-key", default=None, help="Pushover user/group key")
    p.add_argument("--pushover-app-token", default=None, help="Pushover application token")

    # Threshold / interval
    p.add_argument(
        "--threshold",
        type=float,
        default=0.80,
        help="Usage threshold as a fraction (0..1). Default: 0.80",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in seconds. Default: 60",
    )
    p.add_argument(
        "--cooldown",
        type=int,
        default=1800,
        help="Seconds between repeated alerts while still above threshold. 0 disables repeats. Default: 1800",
    )

    # What to check
    p.add_argument(
        "--disk-path",
        default="/home",
        help="Path whose filesystem should be monitored. Default: /home",
    )
    p.add_argument(
        "--no-ram",
        action="store_true",
        help="Disable RAM monitoring",
    )
    p.add_argument(
        "--no-disk",
        action="store_true",
        help="Disable disk monitoring",
    )

    # Optional message decoration
    p.add_argument(
        "--host-label",
        default=None,
        help="Override hostname shown in alerts (default: system hostname)",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()

    if not (0.0 < args.threshold <= 1.0):
        raise SystemExit("--threshold must be in (0, 1]. Example: 0.8")

    if args.no_ram and args.no_disk:
        raise SystemExit("Nothing to do: both --no-ram and --no-disk were set.")

    user_key = (args.pushover_user_key or os.environ.get(ENV_USER_KEY, "")).strip()
    app_token = (args.pushover_app_token or os.environ.get(ENV_APP_TOKEN, "")).strip()

    if not user_key or not app_token:
        raise SystemExit(
            "Missing Pushover credentials.\n"
            "Provide both:\n"
            "  --pushover-user-key ... --pushover-app-token ...\n"
        )

    host = args.host_label or socket.gethostname()

    ram_state = TargetState(name="RAM")
    disk_state = TargetState(name=f"Disk({args.disk_path})")

    def maybe_alert(state: TargetState, frac: float, used: int, total: int) -> None:
        now = time.time()
        above = frac >= args.threshold
        crossed_up = (not state.last_above) and above
        cooldown_ok = (now - state.last_alert_ts) >= args.cooldown

        if crossed_up or (above and args.cooldown > 0 and cooldown_ok):
            pct = frac * 100.0
            msg = (
                f"{state.name} usage on {host} is high.\n"
                f"Usage: {pct:.1f}% ({fmt_bytes(used)} / {fmt_bytes(total)})\n"
                f"Threshold: {args.threshold*100:.0f}%"
            )
            title = f"Watchdog alert: {state.name} >= {args.threshold*100:.0f}%"
            send_pushover_alert(
                user_key=user_key,
                app_token=app_token,
                title=title,
                message=msg,
            )
            state.last_alert_ts = now

        state.last_above = above

    while True:
        if not args.no_ram:
            ram_frac, ram_used, ram_total = get_ram_usage()
            maybe_alert(ram_state, ram_frac, ram_used, ram_total)

        if not args.no_disk:
            disk_frac, disk_used, disk_total = get_disk_usage(args.disk_path)
            maybe_alert(disk_state, disk_frac, disk_used, disk_total)

        time.sleep(args.interval)

    # unreachable
    # return 0


if __name__ == "__main__":
    raise SystemExit(main())
