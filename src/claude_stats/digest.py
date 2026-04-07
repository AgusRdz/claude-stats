"""Work digest — what you worked on: tickets, branches, MRs, commits, files."""

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta

from claude_stats.common import (
    JIRA_PATTERN,
    parse_ts, get_tz_label,
    find_sessions, extract_project, shorten_path, get_ext,
    fmt, print_header,
)


def parse_args(args: list[str]) -> tuple[list[str] | None, str, bool]:
    today = datetime.now()
    use_ai = "--ai" in args
    args = [a for a in args if a != "--ai"]

    if not args:
        d = today.strftime("%Y-%m-%d")
        return [d], f"Daily Digest — {d}", use_ai
    arg = args[0]
    if arg == "--yesterday":
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return [d], f"Daily Digest — {d}", use_ai
    if arg == "--week":
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        return dates, f"Weekly Digest ({dates[-1]} → {dates[0]})", use_ai
    if arg == "--month":
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        return dates, f"Monthly Digest ({dates[-1]} → {dates[0]})", use_ai
    if arg == "--all":
        return None, "Full History Digest", use_ai
    if arg in ("--help", "-h"):
        print("Usage: claude-stats digest [--yesterday|--week|--month|--all|YYYY-MM-DD] [--ai]")
        sys.exit(0)
    try:
        datetime.strptime(arg, "%Y-%m-%d")
        return [arg], f"Daily Digest — {arg}", use_ai
    except ValueError:
        print(f"Invalid: {arg}. Use --yesterday, --week, --month, --all, or YYYY-MM-DD")
        sys.exit(1)


def extract_commit_msg(cmd: str) -> str:
    m = re.search(r"-m\s+[\"'](.+?)[\"']", cmd)
    if m:
        return m.group(1)[:80]
    m = re.search(r"-m\s+\"?\$\(cat\s+<<.*?\n(.+?)(?:\n|EOF)", cmd, re.DOTALL)
    if m:
        return m.group(1).strip()[:80]
    return ""


def extract_mr_title(cmd: str) -> str:
    m = re.search(r'--title\s+["\'](.+?)["\']', cmd)
    if m:
        return m.group(1)[:80]
    return ""


def collect_data(session_files):
    proj_data = defaultdict(lambda: {
        "messages": 0, "first_ts": None, "last_ts": None,
        "jira_ids": set(), "branches": set(),
        "files_written": [], "files_edited": [],
        "commits": [], "mr_creates": [], "mr_updates": [],
        "lines_written": 0, "lines_added": 0, "lines_removed": 0,
        "aws_commands": [], "acli_commands": [], "deploys": [],
    })

    all_jira = set()
    all_branches = set()
    all_commits = []
    all_mrs = []
    total_messages = 0

    for sf in session_files:
        project = extract_project(sf)
        p = proj_data[project]

        try:
            for line in open(sf):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_str = obj.get("timestamp", "")
                local_dt = parse_ts(ts_str) if ts_str else None
                msg_type = obj.get("type")

                if msg_type in ("human", "assistant", "user"):
                    p["messages"] += 1
                    total_messages += 1
                    if local_dt:
                        if not p["first_ts"]:
                            p["first_ts"] = local_dt
                        p["last_ts"] = local_dt

                if msg_type != "assistant":
                    continue
                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue

                for block in msg.get("content", []):
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    inp = block.get("input", {})

                    if name == "Write":
                        fp = inp.get("file_path", "")
                        content = inp.get("content", "")
                        lines = len(content.splitlines()) if content else 0
                        short = shorten_path(fp)
                        p["files_written"].append((short, lines))
                        p["lines_written"] += lines
                        for m in JIRA_PATTERN.finditer(fp):
                            jid = f"{m.group(1)}-{m.group(2)}"
                            p["jira_ids"].add(jid)
                            all_jira.add(jid)

                    elif name == "Edit":
                        fp = inp.get("file_path", "")
                        old = inp.get("old_string", "")
                        new = inp.get("new_string", "")
                        short = shorten_path(fp)
                        p["files_edited"].append((short, len(new.splitlines()) - len(old.splitlines())))
                        p["lines_added"] += len(new.splitlines()) if new else 0
                        p["lines_removed"] += len(old.splitlines()) if old else 0

                    elif name == "Bash":
                        cmd = inp.get("command", "")
                        for m in JIRA_PATTERN.finditer(cmd):
                            jid = f"{m.group(1)}-{m.group(2)}"
                            p["jira_ids"].add(jid)
                            all_jira.add(jid)

                        for bp in [r'checkout\s+(?:-[bB]\s+)?([a-zA-Z0-9/_.-]+(?:DX|feat|fix|chore)[a-zA-Z0-9/_.-]*)',
                                   r'push\s+(?:-u\s+)?origin\s+([a-zA-Z0-9/_.-]+(?:DX|feat|fix|chore)[a-zA-Z0-9/_.-]*)',
                                   r'--source-branch[= ]([a-zA-Z0-9/_.-]+)']:
                            for m in re.finditer(bp, cmd):
                                p["branches"].add(m.group(1))
                                all_branches.add(m.group(1))

                        if "git commit" in cmd:
                            cm = extract_commit_msg(cmd)
                            if cm:
                                p["commits"].append(cm)
                                all_commits.append((project, cm))
                        if "mr create" in cmd:
                            t = extract_mr_title(cmd)
                            if t:
                                p["mr_creates"].append(t)
                                all_mrs.append(("created", project, t))
                        if "mr update" in cmd:
                            p["mr_updates"].append(cmd[:60])
                        if re.search(r'make\s+deploy|deploy\.sh|cloudformation\s+(?:create|update|deploy)', cmd):
                            p["deploys"].append(" ; ".join(l.strip() for l in cmd.split("\n") if l.strip())[:60])
                        if re.search(r'aws\s+\S+\s+(create|update|delete|put|start|run|deploy)', cmd):
                            p["aws_commands"].append(cmd.strip().split("\n")[0][:60])
                        if "workitem transition" in cmd or "workitem create" in cmd or "workitem assign" in cmd:
                            p["acli_commands"].append(cmd.strip()[:60])
        except Exception:
            pass

    return {
        "proj_data": proj_data, "all_jira": all_jira,
        "all_branches": all_branches, "all_commits": all_commits,
        "all_mrs": all_mrs, "total_messages": total_messages,
    }


def print_digest(data, label, dates):
    proj_data = data["proj_data"]
    all_jira = data["all_jira"]
    all_branches = data["all_branches"]
    all_commits = data["all_commits"]
    all_mrs = data["all_mrs"]
    total_messages = data["total_messages"]
    tz_label = get_tz_label()

    total_written = sum(p["lines_written"] for p in proj_data.values())
    total_added = sum(p["lines_added"] for p in proj_data.values())
    total_removed = sum(p["lines_removed"] for p in proj_data.values())
    net = total_written + total_added - total_removed
    all_files = set()
    for p in proj_data.values():
        for f, _ in p["files_written"]:
            all_files.add(f)
        for f, _ in p["files_edited"]:
            all_files.add(f)

    print()
    print(f"  ╔══════════════════════════════════════════════════════════════════╗")
    print(f"  ║  📓  CLAUDE CODE — {label:<47} ║")
    print(f"  ╚══════════════════════════════════════════════════════════════════╝")
    print(f"""
  Projects: {len(proj_data):<10} Jira tickets: {len(all_jira):<10} Messages: {total_messages}
  Files:    {len(all_files):<10} Branches:     {len(all_branches):<10} Net lines: {fmt(net)}""")

    if all_jira:
        print_header("🎫  JIRA TICKETS", "─")
        print()
        for jid in sorted(all_jira):
            projects_for_ticket = [name for name, p in proj_data.items() if jid in p["jira_ids"]]
            print(f"  {jid:<12} {', '.join(p[:30] for p in projects_for_ticket)}")

    print_header("📁  ACTIVITY BY PROJECT", "─")
    for project, p in sorted(proj_data.items(), key=lambda x: x[1]["messages"], reverse=True):
        p_net = p["lines_written"] + p["lines_added"] - p["lines_removed"]
        time_range = ""
        if p["first_ts"] and p["last_ts"]:
            s = p["first_ts"].strftime("%H:%M") if dates and len(dates) == 1 else p["first_ts"].strftime("%m/%d %H:%M")
            e = p["last_ts"].strftime("%H:%M") if dates and len(dates) == 1 else p["last_ts"].strftime("%m/%d %H:%M")
            if p["first_ts"].date() != p["last_ts"].date() and dates and len(dates) == 1:
                s = p["first_ts"].strftime("%m/%d %H:%M")
                e = p["last_ts"].strftime("%m/%d %H:%M")
            time_range = f" ({s} → {e})"

        print(f"\n  📂 {project}{time_range}")
        print(f"     {p['messages']} messages | {p_net:+d} lines | {len(set(f for f, _ in p['files_written'] + p['files_edited']))} files")

        if p["jira_ids"]:
            print(f"     🎫 Tickets: {', '.join(sorted(p['jira_ids']))}")
        for b in sorted(p["branches"]):
            print(f"     🌿 {b}")
        for c in list(dict.fromkeys(p["commits"]))[:5]:
            print(f"     💾 {c}")
        for mr in p["mr_creates"]:
            print(f"     🔀 MR: {mr}")
        for d in list(dict.fromkeys(p["deploys"]))[:3]:
            print(f"     🚀 {d}")
        for a in list(dict.fromkeys(p["aws_commands"]))[:3]:
            print(f"     ☁️  {a}")

        file_ops = defaultdict(lambda: {"written": 0, "edits": 0})
        for f, lines in p["files_written"]:
            file_ops[f]["written"] += lines
        for f, delta in p["files_edited"]:
            file_ops[f]["edits"] += 1
        top_files = sorted(file_ops.items(), key=lambda x: x[1]["written"] + x[1]["edits"], reverse=True)[:5]
        if top_files:
            print(f"     📄 Key files:")
            for f, ops in top_files:
                parts = []
                if ops["written"]:
                    parts.append(f"wrote {ops['written']}L")
                if ops["edits"]:
                    parts.append(f"{ops['edits']} edits")
                display = f if len(f) <= 45 else "..." + f[-42:]
                print(f"        {display}  ({', '.join(parts)})")

    if all_mrs:
        print_header("🔀  MERGE REQUESTS", "─")
        print()
        for action, project, title in all_mrs:
            print(f"  {action.upper():<10} [{project[:25]}]")
            print(f"             {title}")

    if all_commits:
        print_header("💾  COMMITS", "─")
        print()
        seen = set()
        for project, msg in all_commits:
            if msg in seen:
                continue
            seen.add(msg)
            print(f"  [{project[:20]}] {msg}")

    print_header("📄  FILES CHANGED", "─")
    ext_counts = defaultdict(lambda: {"created": 0, "edited": 0})
    for p in proj_data.values():
        for f, _ in p["files_written"]:
            ext_counts[get_ext(f) or "(none)"]["created"] += 1
        for f, _ in p["files_edited"]:
            ext_counts[get_ext(f) or "(none)"]["edited"] += 1
    sorted_ext = sorted(ext_counts.items(), key=lambda x: x[1]["created"] + x[1]["edited"], reverse=True)[:10]
    print(f"\n  {'Extension':<12} {'Created':>8} {'Edited':>8}")
    print(f"  {'─' * 12} {'─' * 8} {'─' * 8}")
    for ext, counts in sorted_ext:
        print(f"  {ext:<12} {counts['created']:>8} {counts['edited']:>8}")

    if dates and len(dates) == 1:
        print_header(f"⏰  TIMELINE ({tz_label})", "─")
        print()
        events = []
        for project, p in proj_data.items():
            if p["first_ts"]:
                events.append((p["first_ts"], f"Started working on {project}"))
            for mr in p["mr_creates"]:
                events.append((p["last_ts"] or p["first_ts"], f"Created MR: {mr[:50]}"))
            for c in list(dict.fromkeys(p["commits"]))[:3]:
                events.append((p["last_ts"] or p["first_ts"], f"Committed: {c[:50]}"))
            for d in list(dict.fromkeys(p["deploys"]))[:2]:
                events.append((p["last_ts"] or p["first_ts"], f"Deployed: {d[:50]}"))
        events.sort(key=lambda x: x[0])
        for ts, desc in events:
            print(f"  {ts.strftime('%H:%M')}  {desc}")

    print()


def build_ai_context(data, label):
    proj_data = data["proj_data"]
    all_jira = data["all_jira"]
    all_mrs = data["all_mrs"]
    all_commits = data["all_commits"]
    total_messages = data["total_messages"]

    total_written = sum(p["lines_written"] for p in proj_data.values())
    total_added = sum(p["lines_added"] for p in proj_data.values())
    total_removed = sum(p["lines_removed"] for p in proj_data.values())
    net = total_written + total_added - total_removed

    all_files = set()
    for p in proj_data.values():
        for f, _ in p["files_written"]:
            all_files.add(f)
        for f, _ in p["files_edited"]:
            all_files.add(f)

    lines = []
    lines.append(f"Period: {label}")
    lines.append(f"Projects: {len(proj_data)}, Jira tickets: {len(all_jira)}, Messages: {total_messages}")
    lines.append(f"Files: {len(all_files)}, Net lines: {net} (wrote {total_written}, added {total_added}, removed {total_removed})")
    lines.append("")
    lines.append("JIRA TICKETS:")
    for jid in sorted(all_jira):
        projects_for = [n for n, p in proj_data.items() if jid in p["jira_ids"]]
        lines.append(f"  {jid}: {', '.join(projects_for)}")
    lines.append("")
    lines.append("PROJECTS:")
    for project, p in sorted(proj_data.items(), key=lambda x: x[1]["messages"], reverse=True):
        p_net = p["lines_written"] + p["lines_added"] - p["lines_removed"]
        time_info = ""
        if p["first_ts"] and p["last_ts"]:
            time_info = f" ({p['first_ts'].strftime('%m/%d %H:%M')} → {p['last_ts'].strftime('%m/%d %H:%M')})"
        lines.append(f"\n  {project}{time_info}")
        lines.append(f"    {p['messages']} messages, {p_net:+d} lines")
        if p["jira_ids"]:
            lines.append(f"    Tickets: {', '.join(sorted(p['jira_ids']))}")
        for b in sorted(p["branches"]):
            lines.append(f"    Branch: {b}")
        for c in list(dict.fromkeys(p["commits"]))[:5]:
            lines.append(f"    Commit: {c}")
        for mr in p["mr_creates"]:
            lines.append(f"    MR created: {mr}")
        for d in list(dict.fromkeys(p["deploys"]))[:3]:
            lines.append(f"    Deploy: {d}")
        for a in list(dict.fromkeys(p["acli_commands"]))[:3]:
            lines.append(f"    Jira action: {a}")

        file_ops = defaultdict(lambda: {"written": 0, "edits": 0})
        for f, l in p["files_written"]:
            file_ops[f]["written"] += l
        for f, delta in p["files_edited"]:
            file_ops[f]["edits"] += 1
        top = sorted(file_ops.items(), key=lambda x: x[1]["written"] + x[1]["edits"], reverse=True)[:5]
        if top:
            lines.append("    Key files:")
            for f, ops in top:
                parts = []
                if ops["written"]:
                    parts.append(f"wrote {ops['written']}L")
                if ops["edits"]:
                    parts.append(f"{ops['edits']} edits")
                lines.append(f"      {f} ({', '.join(parts)})")

    if all_mrs:
        lines.append("\nMERGE REQUESTS:")
        for action, project, title in all_mrs:
            lines.append(f"  [{project[:30]}] {action}: {title}")

    return "\n".join(lines)


def run_ai_summary(context, label):
    print_header("🤖  AI ANALYSIS", "─")
    print()
    print("  Generating AI summary...")
    print()

    period = "today" if "Daily" in label and "Yesterday" not in label else "this period"
    if "Yesterday" in label:
        period = "yesterday"
    elif "Weekly" in label:
        period = "this week"
    elif "Monthly" in label:
        period = "this month"

    prompt = f"""You are reviewing a developer's work log. Write a tight summary.

Rules:
- Use actual ticket IDs, project names, branch names from the data. No placeholders.
- Second person ("you"). Direct. No filler.
- No markdown headers. Use plain text with bullet dashes.

Format (exactly this, nothing more):

SUMMARY: 1-2 sentences on main focus {period}.

DONE:
- (bullet per concrete deliverable: MR created, repo initialized, policy added, etc.)

STANDUP: 2-3 sentence ready-to-paste standup for Slack.

Keep under 150 words total.

DATA:
{context}"""

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "opus"],
            input=prompt,
            capture_output=True, text=True, timeout=120, env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            print("\033[A\033[2K", end="")
            text = result.stdout.strip()

            sections = {}
            current_key = None
            current_lines = []
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped.upper().startswith("SUMMARY:"):
                    if current_key:
                        sections[current_key] = current_lines
                    current_key = "summary"
                    current_lines = [stripped[len("SUMMARY:"):].strip()]
                elif stripped.upper().startswith("DONE:"):
                    if current_key:
                        sections[current_key] = current_lines
                    current_key = "done"
                    rest = stripped[len("DONE:"):].strip()
                    current_lines = [rest] if rest else []
                elif stripped.upper().startswith("STANDUP:"):
                    if current_key:
                        sections[current_key] = current_lines
                    current_key = "standup"
                    current_lines = [stripped[len("STANDUP:"):].strip()]
                else:
                    current_lines.append(stripped)
            if current_key:
                sections[current_key] = current_lines

            if "summary" in sections:
                summary = " ".join(l for l in sections["summary"] if l)
                print(f"  📋 {summary}")
                print()
            if "done" in sections:
                print(f"  ✅ Accomplishments:")
                for line in sections["done"]:
                    if line.startswith("-"):
                        print(f"     {line}")
                    elif line:
                        print(f"     - {line}")
                print()
            if "standup" in sections:
                standup = " ".join(l for l in sections["standup"] if l)
                print(f"  💬 Standup:")
                print(f"  ┌{'─' * 66}┐")
                words = standup.split()
                line = ""
                for word in words:
                    if len(line) + len(word) + 1 > 64:
                        print(f"  │ {line:<64} │")
                        line = word
                    else:
                        line = f"{line} {word}".strip()
                if line:
                    print(f"  │ {line:<64} │")
                print(f"  └{'─' * 66}┘")
        else:
            print(f"  Could not generate AI summary.")
            if result.stderr:
                print(f"  Error: {result.stderr.strip()[:200]}")
    except subprocess.TimeoutExpired:
        print("  AI summary timed out. Try again later.")
    except FileNotFoundError:
        print("  'claude' CLI not found. Install Claude Code to use --ai.")
    except Exception as e:
        print(f"  Error: {e}")

    print()


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label, use_ai = parse_args(args)
    session_files = find_sessions(dates, skip_subagents=True)

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    data = collect_data(session_files)
    if data["total_messages"] == 0:
        print(f"\n  No activity found for {label}")
        sys.exit(0)

    print_digest(data, label, dates)
    if use_ai:
        context = build_ai_context(data, label)
        run_ai_summary(context, label)
