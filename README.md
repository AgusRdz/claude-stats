# claude-stats

Analytics suite for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — track your token usage, tool patterns, session health, productivity, and more.

All data is read locally from `~/.claude/projects/` session files. Nothing is sent anywhere.

## Install

### One-liner (Linux / macOS / WSL)

```bash
curl -fsSL https://raw.githubusercontent.com/Andrevops/claude-stats/main/install.sh | sh
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/Andrevops/claude-stats/main/install.ps1 | iex
```

### Go install

```bash
go install github.com/Andrevops/claude-stats/cmd/claude-stats@latest
```

### Build from source

```bash
git clone https://github.com/Andrevops/claude-stats.git
cd claude-stats
make install
```

### Docker (no install required)

```bash
git clone https://github.com/Andrevops/claude-stats.git
cd claude-stats
make docker-run              # interactive menu
make docker-run-cmd CMD="tokens --week"
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

## Requirements

- Claude Code (the data source — `~/.claude/projects/`)
- `~/.local/bin` on your `$PATH` (default on most Linux/WSL/macOS)

No runtime dependencies — single static binary.

## License

MIT
