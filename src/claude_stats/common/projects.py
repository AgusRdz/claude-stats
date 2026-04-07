"""Project name extraction and path utilities."""

import os
from pathlib import Path

from claude_stats.common.config import PROJECTS_DIR


def extract_project(path: Path) -> str:
    """Extract a human-readable project name from a session file path.

    Claude Code encodes absolute paths in folder names by replacing '/' with '-'.
    E.g., /home/user/my-project → -home-user-my-project
    This strips the home directory prefix to get just the project portion.
    """
    rel = str(path.relative_to(PROJECTS_DIR))
    folder = rel.split("/")[0]
    # Build the encoded home prefix: /home/user → -home-user
    home_encoded = str(Path.home()).replace(os.sep, "-")
    if folder.startswith(home_encoded + "-"):
        return folder[len(home_encoded) + 1:] or "unknown"
    if folder.startswith(home_encoded):
        return folder[len(home_encoded):].lstrip("-") or "unknown"
    return folder or "unknown"


def shorten_path(fp: str) -> str:
    """Shorten an absolute file path for display by replacing $HOME with ~."""
    home = str(Path.home())
    if fp.startswith(home):
        return "~" + fp[len(home):]
    return fp


def get_ext(fp: str) -> str:
    """Extract file extension from a path (e.g., '.py', '.ts')."""
    basename = fp.split("/")[-1]
    if "." in basename:
        return "." + fp.rsplit(".", 1)[-1]
    return "(none)"
