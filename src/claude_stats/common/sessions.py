"""Session file discovery."""

from datetime import datetime
from pathlib import Path

from claude_stats.common.config import PROJECTS_DIR


def find_sessions(
    target_dates: list[str] | None,
    skip_subagents: bool = False,
) -> list[Path]:
    """Find session JSONL files matching the given dates.

    Args:
        target_dates: List of "YYYY-MM-DD" strings, or None for all dates.
        skip_subagents: If True, exclude sessions under subagents/ dirs.

    Returns:
        Sorted list of matching session file paths.
    """
    sessions = []
    if not PROJECTS_DIR.exists():
        return sessions
    for jsonl in PROJECTS_DIR.rglob("*.jsonl"):
        if skip_subagents and "subagents" in str(jsonl):
            continue
        if target_dates is not None:
            mtime = datetime.fromtimestamp(jsonl.stat().st_mtime)
            if mtime.strftime("%Y-%m-%d") not in target_dates:
                continue
        sessions.append(jsonl)
    return sorted(sessions, key=lambda p: p.stat().st_mtime)
