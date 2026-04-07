"""Efficiency and productivity metrics — lines/turn, wasted turns, quota impact."""

import json
import sys
from collections import defaultdict

from claude_stats.common import (
    parse_dates, find_sessions, extract_project,
    fmt, bar, print_header,
)


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates(args)
    session_files = find_sessions(dates)

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    total_human_turns = 0
    total_assistant_turns = 0
    total_tool_calls = 0
    total_errors = 0
    total_output_tokens = 0
    total_written = 0
    total_added = 0
    total_removed = 0
    files_touched = set()

    proj = defaultdict(lambda: {
        "turns": 0, "tools": 0, "errors": 0, "output_tokens": 0,
        "written": 0, "added": 0, "removed": 0, "files": set(),
    })

    tool_type_counts = defaultdict(int)
    productive_turns = 0
    research_turns = 0
    overhead_turns = 0

    for sf in session_files:
        project = extract_project(sf)
        try:
            current_turn_tools = []
            current_turn_has_write = False
            current_turn_has_read = False
            current_turn_has_error = False

            for line in open(sf):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type")

                if msg_type in ("human", "user"):
                    if current_turn_tools:
                        if current_turn_has_error:
                            overhead_turns += 1
                        elif current_turn_has_write:
                            productive_turns += 1
                        elif current_turn_has_read:
                            research_turns += 1
                        else:
                            research_turns += 1
                    current_turn_tools = []
                    current_turn_has_write = False
                    current_turn_has_read = False
                    current_turn_has_error = False

                    total_human_turns += 1
                    proj[project]["turns"] += 1

                    msg = obj.get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_result":
                                    if block.get("is_error"):
                                        total_errors += 1
                                        proj[project]["errors"] += 1
                                        current_turn_has_error = True

                elif msg_type == "assistant":
                    total_assistant_turns += 1
                    msg = obj.get("message", {})
                    if not isinstance(msg, dict):
                        continue

                    usage = msg.get("usage")
                    if usage:
                        out = usage.get("output_tokens", 0)
                        total_output_tokens += out
                        proj[project]["output_tokens"] += out

                    for block in msg.get("content", []):
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue

                        name = block.get("name", "")
                        inp = block.get("input", {})
                        total_tool_calls += 1
                        proj[project]["tools"] += 1
                        tool_type_counts[name] += 1
                        current_turn_tools.append(name)

                        if name == "Write":
                            current_turn_has_write = True
                            content = inp.get("content", "")
                            lines = len(content.splitlines()) if content else 0
                            total_written += lines
                            proj[project]["written"] += lines
                            fp = inp.get("file_path", "")
                            if fp:
                                files_touched.add(fp)
                                proj[project]["files"].add(fp)

                        elif name == "Edit":
                            current_turn_has_write = True
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

                        elif name in ("Read", "Glob", "Grep", "WebSearch", "WebFetch"):
                            current_turn_has_read = True

            # Final turn
            if current_turn_tools:
                if current_turn_has_error:
                    overhead_turns += 1
                elif current_turn_has_write:
                    productive_turns += 1
                elif current_turn_has_read:
                    research_turns += 1

        except Exception:
            pass

    net_lines = total_written + total_added - total_removed
    total_turns = total_human_turns

    if total_turns == 0:
        print(f"\n  No activity found for {label}")
        sys.exit(0)

    lines_per_turn = net_lines / total_turns if total_turns else 0
    tools_per_turn = total_tool_calls / total_turns if total_turns else 0
    files_per_turn = len(files_touched) / total_turns if total_turns else 0
    error_rate = total_errors / total_tool_calls * 100 if total_tool_calls else 0

    # ── Summary
    print_header(f"⚡  EFFICIENCY & PRODUCTIVITY — {label}")
    print(f"""
  Turns (user messages):  {fmt(total_turns)}
  Tool calls:             {fmt(total_tool_calls)} ({tools_per_turn:.1f}/turn)
  Net lines produced:     {fmt(net_lines)}
  Files touched:          {len(files_touched)}

  ┌─────────────────────────────────────────┐
  │  LINES PER TURN:           {lines_per_turn:>10.1f}   │
  │  FILES PER TURN:           {files_per_turn:>10.2f}   │
  │  OUTPUT TOKENS PER TURN:   {total_output_tokens / total_turns:>10.0f}   │
  │  ERROR RATE:               {error_rate:>9.1f}%   │
  └─────────────────────────────────────────┘""")

    # ── Turn Classification
    print_header("🎯  TURN CLASSIFICATION", "─")
    classified = productive_turns + research_turns + overhead_turns
    max_cat = max(productive_turns, research_turns, overhead_turns, 1)

    if classified:
        print(f"""
  Productive (Write/Edit):  {productive_turns:>6}  {bar(productive_turns, max_cat, 25)}  ({productive_turns / classified * 100:.0f}% of classified)
  Research (Read/Search):   {research_turns:>6}  {bar(research_turns, max_cat, 25)}  ({research_turns / classified * 100:.0f}%)
  Overhead (errors):        {overhead_turns:>6}  {bar(overhead_turns, max_cat, 25)}  ({overhead_turns / classified * 100:.0f}%)""")

    # ── Per-Project Efficiency
    print_header("📁  PROJECT EFFICIENCY", "─")
    sorted_proj = sorted(proj.items(), key=lambda x: x[1]["turns"], reverse=True)

    proj_efficiency = []
    for name, p in sorted_proj:
        if p["turns"] < 3:
            continue
        p_net = p["written"] + p["added"] - p["removed"]
        lpt = p_net / p["turns"] if p["turns"] else 0
        err_rate_p = p["errors"] / p["tools"] * 100 if p["tools"] else 0
        proj_efficiency.append((name, p["turns"], p_net, lpt, len(p["files"]), err_rate_p, p["tools"]))

    if proj_efficiency:
        print(f"\n  {'Project':<38} {'Turns':>5} {'Lines':>7} {'L/Turn':>7} {'Files':>5} {'Err%':>6}")
        print(f"  {'─' * 38} {'─' * 5} {'─' * 7} {'─' * 7} {'─' * 5} {'─' * 6}")

        for name, turns, lines, lpt, files, err_rate_p, tools in sorted(proj_efficiency, key=lambda x: x[3], reverse=True):
            pname = name[:36] if len(name) > 36 else name
            warn = " ⚠️" if err_rate_p > 10 else ""
            print(f"  {pname:<38} {turns:>5} {lines:>7} {lpt:>7.1f} {files:>5} {err_rate_p:>5.1f}%{warn}")

    # ── Quota Impact
    print_header("📊  QUOTA IMPACT", "─")
    if total_errors:
        wasted_tool_tokens = total_errors * (total_output_tokens / total_tool_calls) if total_tool_calls else 0
        print(f"""
  Output tokens used:      {fmt(total_output_tokens)}
  Est. wasted on errors:   ~{fmt(int(wasted_tool_tokens))} output tokens ({total_errors} errors)

  If you eliminated all errors, you'd save ~{total_errors / total_tool_calls * 100:.1f}% of your tool calls,
  freeing up quota for ~{int(total_errors * lines_per_turn)} more lines of code.""")
    else:
        print(f"""
  Output tokens used:      {fmt(total_output_tokens)}
  Error rate:              0% — no wasted quota!""")

    # ── Tool Mix
    print_header("🔧  TOOL MIX", "─")
    categories = {
        "Code (Edit/Write)": sum(tool_type_counts.get(t, 0) for t in ("Edit", "Write")),
        "Read (Read/Glob/Grep)": sum(tool_type_counts.get(t, 0) for t in ("Read", "Glob", "Grep")),
        "Shell (Bash)": tool_type_counts.get("Bash", 0),
        "Search (Web)": sum(tool_type_counts.get(t, 0) for t in ("WebSearch", "WebFetch")),
        "Tasks": sum(tool_type_counts.get(t, 0) for t in ("TaskCreate", "TaskUpdate", "TaskList", "TaskGet")),
        "Agents (Task/Message)": sum(tool_type_counts.get(t, 0) for t in ("Task", "SendMessage")),
        "Other": sum(tool_type_counts.get(t, 0) for t in ("AskUserQuestion", "Skill", "EnterPlanMode", "ExitPlanMode",
                                                            "NotebookEdit", "TeamCreate", "TeamDelete", "TaskOutput",
                                                            "EnterWorktree", "TaskStop")),
    }
    max_cat_val = max(categories.values()) if categories else 1

    print()
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        if count == 0:
            continue
        pct = count / total_tool_calls * 100 if total_tool_calls else 0
        print(f"  {cat:<28} {count:>6}  ({pct:>4.0f}%)  {bar(count, max_cat_val, 15)}")

    shell_ratio = categories["Shell (Bash)"] / total_tool_calls * 100 if total_tool_calls else 0

    # ── Recommendations
    print_header("💡  RECOMMENDATIONS", "─")
    recs = []

    if error_rate > 8:
        recs.append(f"Error rate is {error_rate:.1f}%. Top causes are usually Edit mismatches and Bash failures. Run `claude-stats tools` to see which tools fail most.")
    elif error_rate > 4:
        recs.append(f"Error rate {error_rate:.1f}% is moderate. Some errors are unavoidable but there may be room to improve.")

    if lines_per_turn < 1 and total_turns > 20:
        recs.append(f"Producing {lines_per_turn:.1f} lines/turn — heavy on research/exploration. Normal for new projects, but check if sessions are staying productive.")
    elif lines_per_turn > 5:
        recs.append(f"High output at {lines_per_turn:.1f} lines/turn — productive workflow.")

    if shell_ratio > 40:
        recs.append(f"Bash is {shell_ratio:.0f}% of tool calls. Some of these might be replaceable with dedicated tools (Read instead of cat, Grep instead of grep).")

    if research_turns > productive_turns * 3:
        recs.append(f"Research turns outnumber productive turns {research_turns}:{productive_turns}. Consider using Plan mode or Task agents for upfront research to reduce back-and-forth.")

    if overhead_turns > classified * 0.1 and overhead_turns > 5:
        recs.append(f"{overhead_turns} turns ({overhead_turns / classified * 100:.0f}%) were overhead (errors). Allowlisting more commands via `claude-stats prompts` could help.")

    poor_proj = [p for p in proj_efficiency if p[5] > 15 and p[1] > 10]
    if poor_proj:
        names = ", ".join(p[0][:20] for p in poor_proj[:2])
        recs.append(f"High error rate in: {names}. Check project-specific CLAUDE.md or allowlist for those repos.")

    if not recs:
        recs.append("Workflow looks efficient. No major optimization opportunities.")

    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec}")
    print()
