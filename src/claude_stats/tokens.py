"""Token usage and cost breakdown by project and model."""

import json
import sys

from claude_stats.common import (
    PRICING, DEFAULT_PRICING,
    parse_dates, find_sessions, extract_project,
    fmt, bar, print_header, friendly_model,
)


def calc_cost(tokens: dict, model: str = "") -> float:
    pricing = PRICING.get(model, DEFAULT_PRICING)
    return sum((tokens.get(k, 0) / 1_000_000) * pricing[k] for k in ("input", "output", "cache_read", "cache_create"))


def calc_cost_multi(models: dict) -> float:
    return sum(calc_cost(t, m) for m, t in models.items())


def parse_session(path):
    stats = {
        "file": str(path), "messages": 0, "tool_calls": 0,
        "models": {}, "totals": {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0},
        "is_subagent": "subagents" in str(path),
    }
    try:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") in ("human", "assistant"):
                stats["messages"] += 1
            if obj.get("type") == "assistant":
                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        stats["tool_calls"] += 1
                usage = msg.get("usage")
                model = msg.get("model", "unknown")
                if usage:
                    for src, dst in [("input_tokens", "input"), ("output_tokens", "output"),
                                     ("cache_read_input_tokens", "cache_read"), ("cache_creation_input_tokens", "cache_create")]:
                        v = usage.get(src, 0)
                        stats["totals"][dst] += v
                        stats["models"].setdefault(model, {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0})
                        stats["models"][model][dst] += v
    except Exception:
        pass
    return stats


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates(args)
    session_files = find_sessions(dates)

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    projects = {}
    models_global = {}
    grand = {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}
    grand_messages = 0
    grand_tools = 0
    main_sessions = 0
    subagent_count = 0

    for sf in session_files:
        s = parse_session(sf)
        if s["totals"]["output"] == 0 and s["messages"] == 0:
            continue

        project = extract_project(sf)
        if s["is_subagent"]:
            subagent_count += 1
        else:
            main_sessions += 1

        projects.setdefault(project, {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0,
                                       "messages": 0, "tools": 0, "sessions": 0, "models": {}})
        if not s["is_subagent"]:
            projects[project]["sessions"] += 1

        for k in ("input", "output", "cache_read", "cache_create"):
            grand[k] += s["totals"][k]
            projects[project][k] += s["totals"][k]

        grand_messages += s["messages"]
        grand_tools += s["tool_calls"]
        projects[project]["messages"] += s["messages"]
        projects[project]["tools"] += s["tool_calls"]

        for model, tokens in s["models"].items():
            for d in (models_global, projects[project]["models"]):
                d.setdefault(model, {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0})
            for k in ("input", "output", "cache_read", "cache_create"):
                models_global[model][k] += tokens[k]
                projects[project]["models"][model][k] += tokens[k]

    total_tokens = sum(grand.values())
    total_cost = calc_cost_multi(models_global)

    # ── Summary
    print_header(f"🔢  CLAUDE CODE TOKEN USAGE — {label}")
    sess_str = f"{main_sessions} (+{subagent_count} subagents)" if subagent_count else str(main_sessions)
    print(f"""
  Sessions:  {sess_str:<20} Messages:    {fmt(grand_messages)}
  Projects:  {len(projects):<20} Tool calls:  {fmt(grand_tools)}

  Input tokens:          {fmt(grand['input']):>14}
  Output tokens:         {fmt(grand['output']):>14}
  Cache read tokens:     {fmt(grand['cache_read']):>14}
  Cache creation tokens: {fmt(grand['cache_create']):>14}
  {'─' * 42}
  TOTAL TOKENS:          {fmt(total_tokens):>14}
  ESTIMATED COST:        {'${:.2f}'.format(total_cost):>14}""")

    # ── By Project
    print_header("📁  BY PROJECT", "─")
    sorted_projects = sorted(projects.items(), key=lambda x: x[1]["output"], reverse=True)
    max_cost = max(calc_cost_multi(p["models"]) for _, p in sorted_projects) if sorted_projects else 1

    print(f"\n  {'Project':<42} {'Sess':>4} {'Msgs':>5} {'Output':>9} {'Cost':>8}  {'':>15}")
    print(f"  {'─' * 42} {'─' * 4} {'─' * 5} {'─' * 9} {'─' * 8}  {'─' * 15}")

    for proj, p in sorted_projects:
        proj_cost = calc_cost_multi(p["models"])
        name = proj[:40] if len(proj) > 40 else proj
        print(f"  {name:<42} {p['sessions']:>4} {p['messages']:>5} {fmt(p['output']):>9} ${proj_cost:>7.1f}  {bar(proj_cost, max_cost, 15)}")

    total_line = f"  {'TOTAL':<42} {main_sessions:>4} {grand_messages:>5} {fmt(grand['output']):>9} ${total_cost:>7.1f}"
    print(f"  {'─' * 42} {'─' * 4} {'─' * 5} {'─' * 9} {'─' * 8}")
    print(total_line)

    # ── By Model
    print_header("🤖  BY MODEL", "─")
    active_models = {m: t for m, t in models_global.items() if t["output"] > 0}
    max_model_cost = max(calc_cost(t, m) for m, t in active_models.items()) if active_models else 1

    print(f"\n  {'Model':<25} {'Output':>10} {'%':>5} {'Cost':>9}  {'':>15}")
    print(f"  {'─' * 25} {'─' * 10} {'─' * 5} {'─' * 9}  {'─' * 15}")

    for model in sorted(active_models, key=lambda m: active_models[m]["output"], reverse=True):
        t = active_models[model]
        mcost = calc_cost(t, model)
        pct = (t["output"] / grand["output"] * 100) if grand["output"] else 0
        name = friendly_model(model)
        print(f"  {name:<25} {fmt(t['output']):>10} {pct:>4.0f}% ${mcost:>8.1f}  {bar(mcost, max_model_cost, 15)}")

    # ── Cost Breakdown
    print_header("💰  COST BREAKDOWN", "─")
    cost_parts = []
    for model, tokens in models_global.items():
        pricing = PRICING.get(model, DEFAULT_PRICING)
        for cat in ("cache_read", "cache_create", "output", "input"):
            c = (tokens[cat] / 1_000_000) * pricing[cat]
            if c >= 0.50:
                cost_parts.append((cat, model, c, tokens[cat]))

    cost_parts.sort(key=lambda x: x[2], reverse=True)
    max_part = cost_parts[0][2] if cost_parts else 1
    shown_cost = 0.0

    print(f"\n  {'Category':<35} {'Cost':>9} {'Tokens':>14}  {'':>12}")
    print(f"  {'─' * 35} {'─' * 9} {'─' * 14}  {'─' * 12}")

    for cat, model, cost, tok in cost_parts:
        name = friendly_model(model)
        cat_label = cat.replace("_", " ").title()
        print(f"  {cat_label} ({name}){'':<{35 - len(cat_label) - len(name) - 4}} ${cost:>8.1f} {fmt(tok):>14}  {bar(cost, max_part, 12)}")
        shown_cost += cost

    other_cost = total_cost - shown_cost
    if other_cost >= 0.01:
        print(f"  {'Other (<$0.50 each)':<35} ${other_cost:>8.2f}")

    print(f"  {'─' * 35} {'─' * 9}")
    print(f"  {'TOTAL':<35} ${total_cost:>8.2f}")
    print()
