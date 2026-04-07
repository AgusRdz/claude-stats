"""Tool usage analytics — frequency, error rates, chains, and workflow balance."""

import json
import sys
from collections import defaultdict

from claude_stats.common import (
    READ_TOOLS, WRITE_TOOLS, AGENT_TOOLS,
    parse_dates, find_sessions, extract_project,
    fmt, pct, bar, print_header,
)


def classify_tool(name: str) -> str:
    if name in READ_TOOLS:
        return "read"
    if name in WRITE_TOOLS:
        return "write"
    if name in AGENT_TOOLS:
        return "agent"
    return "other"


def get_bash_base(inp: dict) -> str:
    cmd = inp.get("command", "").strip()
    if not cmd:
        return "(empty)"
    base = cmd.split()[0] if cmd.split() else "(empty)"
    if "/" in base:
        base = base.rsplit("/", 1)[-1]
    return base


def get_bash_preview(inp: dict, max_len: int = 65) -> str:
    cmd = inp.get("command", "").strip()
    cmd = " ; ".join(line.strip() for line in cmd.split("\n") if line.strip())
    return cmd[:max_len - 3] + "..." if len(cmd) > max_len else cmd


def parse_session(path):
    tool_calls = {}
    tool_results = {}
    call_order = []
    try:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_type = obj.get("type")
            ts = obj.get("timestamp", "")
            if msg_type == "assistant":
                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tid = block.get("id")
                        tool_calls[tid] = {"name": block.get("name", "unknown"), "input": block.get("input", {}), "timestamp": ts}
                        call_order.append(tid)
            elif msg_type == "user":
                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_results[block.get("tool_use_id")] = {"is_error": block.get("is_error", False)}
    except Exception:
        pass
    return {"tool_calls": tool_calls, "tool_results": tool_results, "call_order": call_order}


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates(args)
    session_files = find_sessions(dates)

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    tools = defaultdict(lambda: {"calls": 0, "errors": 0})
    bash_cmds = defaultdict(lambda: {"calls": 0, "errors": 0})
    bash_previews = defaultdict(list)
    project_tools = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "errors": 0}))
    tool_pairs = defaultdict(int)
    total_calls = 0
    total_errors = 0
    session_count = 0
    workflow = {"read": 0, "write": 0, "agent": 0, "other": 0}

    for sf in session_files:
        data = parse_session(sf)
        if not data["call_order"]:
            continue
        session_count += 1
        project = extract_project(sf)

        prev_tool = None
        for tid in data["call_order"]:
            tc = data["tool_calls"].get(tid)
            if not tc:
                continue
            name = tc["name"]
            is_error = data["tool_results"].get(tid, {}).get("is_error", False)

            tools[name]["calls"] += 1
            total_calls += 1
            if is_error:
                tools[name]["errors"] += 1
                total_errors += 1

            project_tools[project][name]["calls"] += 1
            if is_error:
                project_tools[project][name]["errors"] += 1

            workflow[classify_tool(name)] += 1

            if name == "Bash":
                base = get_bash_base(tc["input"])
                bash_cmds[base]["calls"] += 1
                if is_error:
                    bash_cmds[base]["errors"] += 1
                if len(bash_previews[base]) < 2:
                    bash_previews[base].append(get_bash_preview(tc["input"]))

            if prev_tool:
                tool_pairs[(prev_tool, name)] += 1
            prev_tool = name

    if total_calls == 0:
        print(f"\n  No tool calls found for {label}")
        sys.exit(0)

    # ── Summary
    print_header(f"🔧  CLAUDE CODE TOOL ANALYTICS — {label}")
    print(f"""
  Sessions: {session_count:<12} Total calls:  {fmt(total_calls)}
  Errors:   {fmt(total_errors)} ({pct(total_errors, total_calls)}){'':>5} Avg/session:  {total_calls // session_count}""")

    # ── Workflow Balance
    print_header("⚖️  WORKFLOW BALANCE", "─")
    for cat in ("read", "write", "agent", "other"):
        n = workflow[cat]
        if n == 0:
            continue
        icon = {"read": "📖", "write": "✏️ ", "agent": "🤖", "other": "❓"}[cat]
        print(f"  {icon} {cat.upper():<8} {bar(n, total_calls, 25)} {fmt(n):>6}  ({pct(n, total_calls)})")

    # ── Tool Ranking
    print_header("📊  TOOL RANKING", "─")
    sorted_tools = sorted(tools.items(), key=lambda x: x[1]["calls"], reverse=True)
    max_calls = sorted_tools[0][1]["calls"] if sorted_tools else 1

    print(f"\n  {'Tool':<22} {'Calls':>6} {'Err':>5} {'Rate':>6}  {'':>20}")
    print(f"  {'─' * 22} {'─' * 6} {'─' * 5} {'─' * 6}  {'─' * 20}")
    for name, data in sorted_tools:
        if data["calls"] < 2 and total_calls > 100:
            continue
        err_rate = f"{data['errors'] / data['calls'] * 100:.0f}%" if data["errors"] else "—"
        flag = " ⚠️" if data["errors"] > 0 else ""
        print(f"  {name:<22} {data['calls']:>6} {data['errors']:>5} {err_rate:>6}  {bar(data['calls'], max_calls, 20)}{flag}")

    # ── Bash Subcommands
    if bash_cmds:
        print_header("🐚  BASH SUBCOMMANDS (top 15)", "─")
        sorted_bash = sorted(bash_cmds.items(), key=lambda x: x[1]["calls"], reverse=True)[:15]
        max_bash = sorted_bash[0][1]["calls"] if sorted_bash else 1

        print(f"\n  {'Cmd':<14} {'Calls':>6} {'Err':>5}  {'':>15}  Sample")
        print(f"  {'─' * 14} {'─' * 6} {'─' * 5}  {'─' * 15}  {'─' * 30}")
        for cmd, data in sorted_bash:
            flag = f" ⚠️" if data["errors"] else ""
            sample = bash_previews.get(cmd, [""])[0]
            sample_max = 40
            sample_str = sample[:sample_max - 3] + "..." if len(sample) > sample_max else sample
            print(f"  {cmd:<14} {data['calls']:>6} {data['errors']:>5}  {bar(data['calls'], max_bash, 15)}{flag}  {sample_str}")

    # ── Tool Chains
    if tool_pairs:
        print_header("🔗  COMMON TOOL CHAINS (top 10)", "─")
        sorted_pairs = sorted(tool_pairs.items(), key=lambda x: x[1], reverse=True)[:10]
        max_pair = sorted_pairs[0][1] if sorted_pairs else 1

        print()
        for (a, b), count in sorted_pairs:
            print(f"  {a:<14} → {b:<14} {count:>5}x  {bar(count, max_pair, 15)}")

    # ── Per-Project
    if len(project_tools) > 1:
        print_header("📁  BY PROJECT", "─")
        sorted_proj = sorted(project_tools.items(), key=lambda x: sum(t["calls"] for t in x[1].values()), reverse=True)

        print(f"\n  {'Project':<42} {'Calls':>6} {'Err':>4} {'Top tools':>28}")
        print(f"  {'─' * 42} {'─' * 6} {'─' * 4} {'─' * 28}")

        for project, pt in sorted_proj:
            proj_total = sum(t["calls"] for t in pt.values())
            proj_errors = sum(t["errors"] for t in pt.values())
            top3 = sorted(pt.items(), key=lambda x: x[1]["calls"], reverse=True)[:3]
            top3_str = " ".join(f"{n}({d['calls']})" for n, d in top3)
            name = project[:40] if len(project) > 40 else project
            err_str = str(proj_errors) if proj_errors else "—"
            print(f"  {name:<42} {proj_total:>6} {err_str:>4} {top3_str:>28}")

    # ── Insights
    print_header("💡  INSIGHTS", "─")
    insights = []

    reads = workflow["read"]
    writes = workflow["write"]
    if reads and writes:
        ratio = reads / writes
        if ratio > 3:
            insights.append(f"Heavy research mode: {ratio:.1f}:1 read/write ratio.")
        elif ratio < 0.5:
            insights.append(f"Heavy edit mode: {1 / ratio:.1f}:1 write/read ratio.")
        else:
            insights.append(f"Balanced workflow: {ratio:.1f}:1 read/write ratio.")

    if total_errors > 0:
        worst = max(tools.items(), key=lambda x: x[1]["errors"])
        insights.append(f"Error rate {pct(total_errors, total_calls)} — worst: {worst[0]} ({worst[1]['errors']})")

    agent_calls = workflow["agent"]
    if agent_calls > 5:
        insights.append(f"Active agent delegation: {agent_calls} calls.")
    elif total_calls > 50 and agent_calls == 0:
        insights.append("No subagent usage. Consider Task tool for parallel work.")

    edit_errs = tools.get("Edit", {}).get("errors", 0)
    if edit_errs > 2:
        insights.append(f"Edit errored {edit_errs}x — likely non-unique match strings.")

    if not insights:
        insights.append("Clean session. No notable patterns.")

    for i, insight in enumerate(insights, 1):
        print(f"  {i}. {insight}")
    print()
