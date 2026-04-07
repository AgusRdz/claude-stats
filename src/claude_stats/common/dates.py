"""Date parsing and timestamp utilities."""

import sys
import time
from datetime import datetime, timedelta, timezone


def get_local_utc_offset() -> float:
    """Get local UTC offset in hours, accounting for DST."""
    now = datetime.now(timezone.utc).astimezone()
    return now.utcoffset().total_seconds() / 3600


def get_tz_label() -> str:
    """Get the local timezone abbreviation (e.g., CST, EST)."""
    return time.tzname[time.daylight] if time.daylight else time.tzname[0]


def parse_dates(args: list[str]) -> tuple[list[str] | None, str]:
    """Parse CLI date arguments into (target_dates, label).

    Returns (None, label) for --all (meaning all dates).
    Returns (list[str], label) for specific date ranges.
    """
    today = datetime.now()
    if not args:
        d = today.strftime("%Y-%m-%d")
        return [d], f"Today ({d})"
    arg = args[0]
    if arg == "--yesterday":
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return [d], f"Yesterday ({d})"
    if arg == "--week":
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        return dates, f"Last 7 days ({dates[-1]} → {dates[0]})"
    if arg == "--month":
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        return dates, f"Last 30 days ({dates[-1]} → {dates[0]})"
    if arg == "--all":
        return None, "All time"
    if arg in ("--help", "-h"):
        print("Usage: claude-stats <command> [--yesterday|--week|--month|--all|YYYY-MM-DD]")
        sys.exit(0)
    try:
        datetime.strptime(arg, "%Y-%m-%d")
        return [arg], arg
    except ValueError:
        print(f"Invalid date: {arg}. Use --yesterday, --week, --month, --all, or YYYY-MM-DD")
        sys.exit(1)


def parse_ts(ts_str: str) -> datetime | None:
    """Parse an ISO timestamp (UTC) and convert to local time."""
    try:
        ts_str = ts_str.replace("Z", "+00:00")
        if "." in ts_str:
            parts = ts_str.split(".")
            frac = parts[1].split("+")[0].split("-")[0][:6]
            tz = ""
            if "+" in parts[1]:
                tz = "+" + parts[1].split("+")[1]
            elif parts[1].count("-") > 0:
                tz = "-" + parts[1].split("-")[1]
            ts_str = f"{parts[0]}.{frac}{tz}"
        dt = datetime.fromisoformat(ts_str)
        offset = get_local_utc_offset()
        return dt + timedelta(hours=offset)
    except Exception:
        return None
