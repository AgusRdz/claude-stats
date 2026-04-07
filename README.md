# claude-stats

Analytics suite for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — track your token usage, tool patterns, session health, productivity, and more.

All data is read locally from `~/.claude/projects/` session files. Nothing is sent anywhere.

## Install

```bash
pip install git+https://github.com/Andrevops/claude-stats.git
```

Or clone and install:

```bash
git clone https://github.com/Andrevops/claude-stats.git
cd claude-stats
pip install .
```

## Usage

### Interactive menu

```bash
claude-stats
```

### Direct commands

```bash
claude-stats tokens              # today's token usage & cost
claude-stats tokens --week       # last 7 days
claude-stats tools --month       # tool analytics for last 30 days
claude-stats report --all        # all-time executive summary
claude-stats digest --ai         # today's work digest + AI summary
```

### Available commands

| Command | Description |
|---------|-------------|
| `tokens` | Token consumption, cost breakdown by project and model |
| `tools` | Tool call frequency, error rates, Bash subcommands, chains |
| `prompts` | Permission prompt analysis, allowlist suggestions |
| `heatmap` | Activity by hour/day, calendar view, top sessions |
| `lines` | Lines written, edited, removed by extension and project |
| `sessions` | Context growth, duration, bloat detection, restart advice |
| `efficiency` | Lines/turn, wasted turns, productivity ratios |
| `report` | Executive summary combining all analytics |
| `digest` | What you worked on: tickets, branches, MRs, commits |

### Time filters

All commands accept these options:

```
(default)        Today
--yesterday      Yesterday
--week           Last 7 days
--month          Last 30 days
--all            All time
YYYY-MM-DD       Specific date
```

## Install with pipx (recommended)

[pipx](https://pipx.pypa.io/) installs in an isolated environment so it won't interfere with your system Python:

```bash
pipx install git+https://github.com/Andrevops/claude-stats.git
```

## Requirements

- Python 3.10+
- Claude Code (the data source — `~/.claude/projects/`)
- `~/.local/bin` on your `$PATH` (default on most Linux/WSL distros)
- No third-party Python dependencies

## License

MIT
