"""CLI entry point for claude-stats — interactive menu and subcommand routing."""

import sys

from claude_stats import (
    tokens, tools, prompts, heatmap, lines,
    sessions_health, efficiency, report, digest,
)

BLUE = "\033[1;34m"
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

COMMANDS = [
    ("tokens", "Token Usage", tokens, "Tokens, cost breakdown, per-project and per-model spending"),
    ("tools", "Tool Analytics", tools, "Tool call frequency, error rates, Bash subcommands, chains"),
    ("prompts", "Permission Prompts", prompts, "Commands requiring approval, allowlist suggestions"),
    ("heatmap", "Activity Heatmap", heatmap, "Activity by hour/day, calendar view, top sessions"),
    ("lines", "Lines of Code", lines, "Lines written, edited, removed by extension, project, file"),
    ("sessions", "Session Health", sessions_health, "Context growth, duration, bloat detection, restart advice"),
    ("efficiency", "Efficiency", efficiency, "Lines/turn, wasted turns, productivity ratios per project"),
    ("report", "Weekly Report", report, "Executive summary combining all analytics into one view"),
    ("digest", "Work Digest", digest, "What you worked on: tickets, branches, MRs, commits, files"),
]


def show_menu():
    print(f"\n{BOLD}")
    print("  ╔═══════════════════════════════════════════════════╗")
    print("  ║        🔢  Claude Code Analytics Suite           ║")
    print("  ╚═══════════════════════════════════════════════════╝")
    print(f"{RESET}")

    for i, (cmd, name, _, desc) in enumerate(COMMANDS, 1):
        print(f"  {BLUE}{i}){RESET} {BOLD}{name}{RESET}  {DIM}({cmd}){RESET}")
        print(f"     {CYAN}{desc}{RESET}")
        print()

    print(f"  {DIM}─────────────────────────────────────────────────{RESET}")
    print(f"  {BLUE}q){RESET} Quit")
    print()


def pick_timeframe() -> list[str]:
    print()
    print(f"  {BOLD}Timeframe:{RESET}")
    print(f"  {GREEN}1){RESET} Today       {GREEN}4){RESET} Last 30 days")
    print(f"  {GREEN}2){RESET} Yesterday   {GREEN}5){RESET} All time")
    print(f"  {GREEN}3){RESET} Last 7 days {GREEN}6){RESET} Custom date")
    print()

    try:
        tf = input("  Pick [1-6]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return []

    if tf in ("1", ""):
        return []
    elif tf == "2":
        return ["--yesterday"]
    elif tf == "3":
        return ["--week"]
    elif tf == "4":
        return ["--month"]
    elif tf == "5":
        return ["--all"]
    elif tf == "6":
        try:
            custom = input("  Enter date (YYYY-MM-DD): ").strip()
        except (EOFError, KeyboardInterrupt):
            return []
        return [custom]
    return []


def interactive_menu():
    while True:
        show_menu()
        try:
            choice = input(f"  Pick a tool [1-{len(COMMANDS)}, q]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice.lower() == "q":
            print()
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(COMMANDS):
                cmd, name, module, desc = COMMANDS[idx]
                extra_args = pick_timeframe()

                # Offer --ai for digest
                if cmd == "digest":
                    print()
                    print(f"  {BOLD}AI Analysis:{RESET}")
                    print(f"  {GREEN}1){RESET} Data only   {GREEN}2){RESET} Data + AI summary")
                    print()
                    try:
                        ai_choice = input("  Pick [1-2]: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        ai_choice = "1"
                    if ai_choice == "2":
                        extra_args.append("--ai")

                print()
                module.run(extra_args)
                print()
                try:
                    input("  Press Enter to continue...")
                except (EOFError, KeyboardInterrupt):
                    pass
            else:
                print("  Invalid choice")
        except ValueError:
            pass


def main():
    if len(sys.argv) < 2:
        interactive_menu()
        return

    subcmd = sys.argv[1]
    remaining = sys.argv[2:]

    if subcmd in ("--help", "-h"):
        print("Usage: claude-stats [command] [options]")
        print()
        print("Commands:")
        for cmd, name, _, desc in COMMANDS:
            print(f"  {cmd:<14} {desc}")
        print()
        print("Options:")
        print("  --yesterday    Yesterday's data")
        print("  --week         Last 7 days")
        print("  --month        Last 30 days")
        print("  --all          All time")
        print("  YYYY-MM-DD     Specific date")
        print()
        print("Run without arguments for interactive menu.")
        return

    if subcmd == "--version":
        from claude_stats import __version__
        print(f"claude-stats {__version__}")
        return

    cmd_map = {cmd: module for cmd, _, module, _ in COMMANDS}
    if subcmd in cmd_map:
        cmd_map[subcmd].run(remaining)
    else:
        print(f"Unknown command: {subcmd}")
        print(f"Available: {', '.join(cmd for cmd, _, _, _ in COMMANDS)}")
        sys.exit(1)
