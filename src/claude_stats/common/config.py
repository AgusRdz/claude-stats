"""Constants and configuration for claude-stats."""

import re
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"

# ── Pricing (per 1M tokens) ─────────────────────────────────────────────────
PRICING = {
    "claude-opus-4-6": {"input": 15.00, "output": 75.00, "cache_read": 1.875, "cache_create": 18.75},
    "claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00, "cache_read": 1.875, "cache_create": 18.75},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_create": 3.75},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_create": 1.00},
}
DEFAULT_PRICING = {"input": 15.00, "output": 75.00, "cache_read": 1.875, "cache_create": 18.75}

# ── Tool classifications ─────────────────────────────────────────────────────
READ_TOOLS = {"Read", "Glob", "Grep", "WebFetch", "WebSearch", "TaskList", "TaskGet"}
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "Bash", "TaskCreate", "TaskUpdate"}
AGENT_TOOLS = {"Task", "SendMessage"}

AUTO_ALLOWED_TOOLS = {
    "Glob", "Grep", "WebSearch", "WebFetch", "Task", "TaskCreate",
    "TaskUpdate", "TaskList", "TaskGet", "TaskOutput", "SendMessage",
    "TeamCreate", "TeamDelete", "AskUserQuestion", "EnterPlanMode",
    "ExitPlanMode", "Skill", "NotebookEdit", "EnterWorktree", "TaskStop",
}

DESTRUCTIVE_CMDS = {"rm", "sudo", "kill", "pkill", "rmdir"}

# ── Time / display ───────────────────────────────────────────────────────────
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOURS = list(range(24))
HEAT = [" · ", " ░ ", " ▒ ", " ▓ ", " █ "]

# ── Patterns ─────────────────────────────────────────────────────────────────
JIRA_PATTERN = re.compile(
    r"\b(DX|BACK|FRNT|ANG|CACG|CORE|INF|DATA|RES|CSD|NJP|SFR|DPI)-(\d+)\b"
)
