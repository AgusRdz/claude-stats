"""Weekly executive report — combines all analytics into one view."""

import fnmatch
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta

from claude_stats.common import (
    PRICING, DEFAULT_PRICING, AUTO_ALLOWED_TOOLS, DAYS,
    parse_ts, get_tz_label,
    find_sessions, extract_project,
    fmt, fmt_tokens, bar, print_header,
)
from claude_stats.common.config import SETTINGS_FILE


def parse_dates_report(args: list[str]) -> tuple[list[str] | None, str]:
    """Report-specific date parsing — defaults to --week and supports date ranges."""
    today = datetime.now()
    if not args:
        d = today.strftime("%Y-%m-%d")
        return [d], f"Today's Report ({d})"
    arg = args[0]
    if arg == "--week":
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        return dates, f"Weekly Report ({dates[-1]} → {dates[0]})"
    if arg == "--yesterday":
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return [d], f"Yesterday Report ({d})"
    if arg == "--month":
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        return dates, f"Monthly Report ({dates[-1]} → {dates[0]})"
    if arg == "--all":
        return None, "All-Time Report"
    if arg in ("--help", "-h"):
        print("Usage: claude-stats report [--yesterday|--week|--month|--all|YYYY-MM-DD]")
        sys.exit(0)
    try:
        target = datetime.strptime(arg, "%Y-%m-%d")
        days = (today - target).days + 1
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        return dates, f"Report ({arg} → {today.strftime('%Y-%m-%d')})"
    except ValueError:
        print(f"Invalid: {arg}. Use --yesterday, --week, --month, --all, or YYYY-MM-DD")
        sys.exit(1)


def load_bash_patterns() -> list[str]:
    if not SETTINGS_FILE.exists():
        return []
    settings = json.load(open(SETTINGS_FILE))
    allow = settings.get("permissions", {}).get("allow", [])
    return [p[5:-1] for p in allow if p.startswith("Bash(") and p.endswith(")")]


def is_bash_allowed(cmd: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(cmd, p) for p in patterns)


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates_report(args)
    session_files = find_sessions(dates)
    bash_patterns = load_bash_patterns()
    tz_label = get_tz_label()

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    total_messages = 0
    total_turns = 0
    total_tool_calls = 0
    total_errors = 0
    main_sessions = 0
    subagent_count = 0
    total_output = 0
    models_global = defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0})
    total_written = 0
    total_added = 0
    total_removed = 0
    files_touched = set()
    tool_counts = defaultdict(int)
    tool_errors = defaultdict(int)
    bash_cmds = defaultdict(int)
    proj = defaultdict(lambda: {
        "messages": 0, "tools": 0, "errors": 0, "output": 0,
        "written": 0, "added": 0, "removed": 0, "files": set(),
        "sessions": 0, "models": defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}),
    })
    daily_messages = defaultdict(int)
    daily_output = defaultdict(int)
    hourly = defaultdict(int)
    prompted_commands = defaultdict(int)
    total_prompted = 0
    total_auto = 0
    session_data = []

    for sf in session_files:
        project = extract_project(sf)
        is_sub = "subagents" in str(sf)
        if is_sub:
            subagent_count += 1
        else:
            main_sessions += 1
            proj[project]["sessions"] += 1

        sess_first_ts = None
        sess_last_ts = None
        sess_msgs = 0
        sess_ctx = []

        try:
            pending_tools = {}
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
                    total_messages += 1
                    sess_msgs += 1
                    proj[project]["messages"] += 1
                    if local_dt:
                        daily_messages[local_dt.strftime("%Y-%m-%d")] += 1
                        hourly[local_dt.hour] += 1
                        if not sess_first_ts:
                            sess_first_ts = local_dt
                        sess_last_ts = local_dt

                if msg_type in ("human", "user"):
                    total_turns += 1
                    msg = obj.get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_result":
                                    if block.get("is_error"):
                                        tid = block.get("tool_use_id")
                                        tname = pending_tools.get(tid, "unknown")
                                        total_errors += 1
                                        tool_errors[tname] += 1
                                        proj[project]["errors"] += 1

                elif msg_type == "assistant":
                    msg = obj.get("message", {})
                    if not isinstance(msg, dict):
                        continue
                    usage = msg.get("usage")
                    model = msg.get("model", "unknown")
                    if usage:
                        for src, dst in [("input_tokens", "input"), ("output_tokens", "output"),
                                         ("cache_read_input_tokens", "cache_read"),
                                         ("cache_creation_input_tokens", "cache_create")]:
                            v = usage.get(src, 0)
                            models_global[model][dst] += v
                            proj[project]["models"][model][dst] += v
                        out = usage.get("output_tokens", 0)
                        total_output += out
                        proj[project]["output"] += out
                        cr = usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
                        sess_ctx.append(cr)
                        if local_dt:
                            daily_output[local_dt.strftime("%Y-%m-%d")] += out

                    for block in msg.get("content", []):
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        name = block.get("name", "")
                        inp = block.get("input", {})
                        tid = block.get("id", "")
                        total_tool_calls += 1
                        tool_counts[name] += 1
                        proj[project]["tools"] += 1
                        pending_tools[tid] = name

                        if name == "Bash":
                            cmd = inp.get("command", "").strip()
                            base = cmd.split()[0] if cmd.split() else "(empty)"
                            if "/" in base:
                                base = base.rsplit("/", 1)[-1]
                            bash_cmds[base] += 1
                            if not is_bash_allowed(cmd, bash_patterns):
                                prompted_commands[f"Bash({base})"] += 1
                                total_prompted += 1
                            else:
                                total_auto += 1
                        elif name in ("Edit", "Write"):
                            total_prompted += 1
                        elif name in AUTO_ALLOWED_TOOLS or name == "Read":
                            total_auto += 1
                        else:
                            total_prompted += 1

                        if name == "Write":
                            content = inp.get("content", "")
                            lines = len(content.splitlines()) if content else 0
                            total_written += lines
                            proj[project]["written"] += lines
                            fp = inp.get("file_path", "")
                            if fp:
                                files_touched.add(fp)
                                proj[project]["files"].add(fp)
                        elif name == "Edit":
                            old = inp.get("old_string", "")
                            new = inp.get("new_string", "")
                            total_added += len(new.splitlines()) if new else 0
                            total_removed += len(old.splitlines()) if old else 0
                            proj[project]["added"] += len(new.splitlines()) if new else 0
                            proj[project]["removed"] += len(old.splitlines()) if old else 0
                            fp = inp.get("file_path", "")
                            if fp:
                                files_touched.add(fp)
                                proj[project]["files"].add(fp)
        except Exception:
            pass

        if sess_first_ts and sess_last_ts and sess_msgs >= 4 and not is_sub:
            duration = (sess_last_ts - sess_first_ts).total_seconds()
            ctx_growth = 0
            if len(sess_ctx) >= 4:
                q = len(sess_ctx) // 4
                first_q = sum(sess_ctx[:q]) / q if q else 0
                last_q = sum(sess_ctx[-q:]) / q if q else 0
                ctx_growth = (last_q / first_q - 1) * 100 if first_q > 0 else 0
            session_data.append({
                "project": project, "start": sess_first_ts, "duration": duration,
                "messages": sess_msgs, "ctx_growth": ctx_growth,
            })

    net_lines = total_written + total_added - total_removed
    total_cost = sum(
        sum((t[k] / 1e6) * PRICING.get(m, DEFAULT_PRICING)[k] for k in ("input", "output", "cache_read", "cache_create"))
        for m, t in models_global.items()
    )

    # ── Output
    print()
    print(f"  ╔══════════════════════════════════════════════════════════════════╗")
    print(f"  ║  📊  CLAUDE CODE — {label:<47} ║")
    print(f"  ╚══════════════════════════════════════════════════════════════════╝")

    print_header("📋  OVERVIEW", "─")
    sess_str = f"{main_sessions} (+{subagent_count} sub)" if subagent_count else str(main_sessions)
    err_rate = total_errors / total_tool_calls * 100 if total_tool_calls else 0
    lines_per_turn = net_lines / total_turns if total_turns else 0

    print(f"""
  Sessions:    {sess_str:<18}  Projects:       {len(proj)}
  Messages:    {fmt(total_messages):<18}  Turns:          {fmt(total_turns)}
  Tool calls:  {fmt(total_tool_calls):<18}  Errors:         {fmt(total_errors)} ({err_rate:.1f}%)
  Files:       {len(files_touched):<18}  Est. cost:      ${total_cost:.0f}

  ┌──────────────────────────────────────────────────────────┐
  │  NET LINES PRODUCED:     {fmt(net_lines):>8}  ({lines_per_turn:.1f} lines/turn)    │
  │  LINES WRITTEN (new):    {fmt(total_written):>8}                          │
  │  LINES ADDED (edits):    {fmt(total_added):>8}                          │
  │  LINES REMOVED:          {fmt(total_removed):>8}                          │
  └──────────────────────────────────────────────────────────┘""")

    if daily_messages and len(daily_messages) > 1:
        print_header("📅  DAILY ACTIVITY", "─")
        sorted_dates = sorted(daily_messages.keys())
        max_daily = max(daily_messages.values())
        print(f"\n  {'Date':<12} {'Msgs':>6} {'Output':>8} {'':>25}")
        print(f"  {'─' * 12} {'─' * 6} {'─' * 8} {'─' * 25}")
        for date in sorted_dates:
            msgs = daily_messages[date]
            out = daily_output.get(date, 0)
            dt = datetime.strptime(date, "%Y-%m-%d")
            day = DAYS[dt.weekday()]
            weekend = " 🏖" if dt.weekday() >= 5 else ""
            print(f"  {date} {day} {msgs:>5} {fmt_tokens(out):>8} {bar(msgs, max_daily, 25)}{weekend}")

    print_header("🏆  PROJECT LEADERBOARD", "─")
    sorted_proj = sorted(proj.items(), key=lambda x: x[1]["written"] + x[1]["added"], reverse=True)
    print(f"\n  {'Project':<36} {'Sess':>4} {'Msgs':>5} {'Lines':>7} {'L/Msg':>6} {'Err%':>5} {'Files':>5}")
    print(f"  {'─' * 36} {'─' * 4} {'─' * 5} {'─' * 7} {'─' * 6} {'─' * 5} {'─' * 5}")
    for name, p in sorted_proj:
        p_net = p["written"] + p["added"] - p["removed"]
        lpm = p_net / p["messages"] if p["messages"] else 0
        err = p["errors"] / p["tools"] * 100 if p["tools"] else 0
        pname = name[:34] if len(name) > 34 else name
        warn = " ⚠️" if err > 10 else ""
        print(f"  {pname:<36} {p['sessions']:>4} {p['messages']:>5} {p_net:>7} {lpm:>6.1f} {err:>4.0f}% {len(p['files']):>5}{warn}")

    print_header("🔧  TOP TOOLS", "─")
    sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    max_tool = sorted_tools[0][1] if sorted_tools else 1
    print(f"\n  {'Tool':<18} {'Calls':>6} {'Err':>5} {'%':>5}  {'':>15}")
    print(f"  {'─' * 18} {'─' * 6} {'─' * 5} {'─' * 5}  {'─' * 15}")
    for name, count in sorted_tools:
        errs = tool_errors.get(name, 0)
        pct = count / total_tool_calls * 100
        flag = " ⚠️" if errs > 5 else ""
        print(f"  {name:<18} {count:>6} {errs:>5} {pct:>4.0f}%  {bar(count, max_tool, 15)}{flag}")

    print_header("🐚  TOP BASH COMMANDS", "─")
    sorted_bash = sorted(bash_cmds.items(), key=lambda x: x[1], reverse=True)[:10]
    max_bash = sorted_bash[0][1] if sorted_bash else 1
    print(f"\n  {'Cmd':<14} {'Calls':>6}  {'':>12}")
    print(f"  {'─' * 14} {'─' * 6}  {'─' * 12}")
    for cmd, count in sorted_bash:
        print(f"  {cmd:<14} {count:>6}  {bar(count, max_bash, 12)}")

    if session_data:
        print_header("🏥  SESSION HEALTH", "─")
        high_growth = [s for s in session_data if s["ctx_growth"] > 200]
        avg_dur = sum(s["duration"] for s in session_data) / len(session_data)
        avg_msgs = sum(s["messages"] for s in session_data) / len(session_data)
        dur_str = f"{avg_dur / 60:.0f}m" if avg_dur < 3600 else f"{avg_dur / 3600:.1f}h"
        print(f"""
  Sessions analyzed:   {len(session_data)}
  Avg duration:        {dur_str}
  Avg messages:        {avg_msgs:.0f}
  High context growth: {len(high_growth)} sessions (>200% growth) {'⚠️' if high_growth else '✅'}""")
        if high_growth:
            print(f"\n  Bloated sessions:")
            for s in sorted(high_growth, key=lambda x: x["ctx_growth"], reverse=True)[:3]:
                dur = f"{s['duration'] / 3600:.1f}h" if s["duration"] >= 3600 else f"{s['duration'] / 60:.0f}m"
                print(f"    {s['start'].strftime('%Y-%m-%d')} {dur:>5} +{s['ctx_growth']:.0f}%  {s['project'][:35]}")
    else:
        high_growth = []

    if hourly:
        print_header(f"⏰  PEAK HOURS ({tz_label})", "─")
        sorted_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)
        active_hours = [(h, c) for h, c in sorted_hours if c > 0][:6]
        max_hour = active_hours[0][1] if active_hours else 1
        print()
        for h, count in sorted(active_hours, key=lambda x: x[0]):
            peak = " ← PEAK" if h == sorted_hours[0][0] else ""
            print(f"  {h:02d}:00  {bar(count, max_hour, 20)} {count:>5}{peak}")

    total_perm = total_prompted + total_auto
    if total_perm > 0:
        print_header("🔐  PERMISSION PROMPTS", "─")
        prompt_pct = total_prompted / total_perm * 100
        print(f"""
  Auto-allowed:    {fmt(total_auto):>8} ({100 - prompt_pct:.0f}%)
  Required prompt: {fmt(total_prompted):>8} ({prompt_pct:.0f}%)""")
        if prompted_commands:
            top_prompted = sorted(prompted_commands.items(), key=lambda x: x[1], reverse=True)[:5]
            print(f"\n  Top prompted commands:")
            for cmd, count in top_prompted:
                print(f"    {cmd:<30} ~{count}")

    # ── Scorecard
    print_header("📊  SCORECARD", "─")
    scores = {}
    scores["Productivity"] = min(lines_per_turn / 5 * 100, 100) if total_turns else 0
    scores["Reliability"] = max(0, (1 - err_rate / 15) * 100) if total_tool_calls else 100
    prompt_rate = total_prompted / total_perm * 100 if total_perm else 0
    scores["Prompt Efficiency"] = max(0, (1 - prompt_rate / 30) * 100)
    if session_data:
        high_pct = len(high_growth) / len(session_data) * 100
        scores["Session Health"] = max(0, (1 - high_pct / 20) * 100)
    else:
        scores["Session Health"] = 100
    out_per_turn = total_output / total_turns if total_turns else 0
    scores["Output Density"] = min(out_per_turn / 100 * 100, 100)

    overall = sum(scores.values()) / len(scores) if scores else 0
    print()
    for metric, score in sorted(scores.items(), key=lambda x: x[1]):
        grade = "🟢" if score >= 70 else "🟡" if score >= 40 else "🔴"
        print(f"  {grade} {metric:<22} {score:>5.0f}/100  {bar(score, 100, 20)}")
    print(f"\n  {'Overall Score':<25} {overall:>5.0f}/100  {bar(overall, 100, 20)}")
    grade_emoji = "🏆" if overall >= 80 else "👍" if overall >= 60 else "⚠️" if overall >= 40 else "🔧"
    grade_text = "Excellent" if overall >= 80 else "Good" if overall >= 60 else "Needs Work" if overall >= 40 else "Optimize"
    print(f"  {grade_emoji}  Grade: {grade_text}")

    # ── Action Items
    print_header("🎯  ACTION ITEMS", "─")
    actions = []
    if err_rate > 8:
        actions.append(f"🔴 Error rate is {err_rate:.1f}% — run `claude-stats tools --week` to identify failing tools and fix root causes.")
    if prompt_rate > 20:
        actions.append(f"🟡 {prompt_rate:.0f}% of tool calls need prompts — run `claude-stats prompts --week` and apply suggestions to reduce friction.")
    if high_growth and len(high_growth) > 2:
        actions.append(f"🟡 {len(high_growth)} sessions had context bloat — restart sessions more frequently for these projects.")
    if lines_per_turn < 2 and total_turns > 50:
        actions.append(f"🟡 Low output ({lines_per_turn:.1f} lines/turn) — consider Plan mode for complex tasks to reduce research turns.")

    worst_proj = [(n, p) for n, p in proj.items() if p["tools"] > 10 and p["errors"] / p["tools"] > 0.1]
    if worst_proj:
        names = ", ".join(n[:20] for n, _ in worst_proj[:2])
        actions.append(f"🟡 High error rate in: {names} — check CLAUDE.md and allowlist for those repos.")

    if not actions:
        actions.append("🟢 Everything looks good! No urgent optimizations needed.")

    for i, action in enumerate(actions, 1):
        print(f"  {i}. {action}")
    print()
