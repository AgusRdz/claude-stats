"""Session health analyzer — context growth, duration, and restart advice."""

import json
import sys

from claude_stats.common import (
    parse_dates, parse_ts,
    find_sessions, extract_project,
    fmt, fmt_duration, fmt_tokens, bar, print_header,
)


def parse_session(path):
    messages = 0
    human_messages = 0
    tool_calls = 0
    errors = 0
    first_ts = None
    last_ts = None
    context_sizes = []
    output_tokens_list = []
    total_output = 0
    total_cache_read = 0
    total_cache_create = 0
    lines_written = 0
    lines_added = 0
    lines_removed = 0
    files_touched = set()

    try:
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts_str = obj.get("timestamp", "")
            ts = parse_ts(ts_str) if ts_str else None
            if ts:
                if not first_ts:
                    first_ts = ts
                last_ts = ts

            msg_type = obj.get("type")
            if msg_type in ("human", "assistant"):
                messages += 1
            if msg_type == "human":
                human_messages += 1

            if msg_type == "assistant":
                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if usage:
                    cr = usage.get("cache_read_input_tokens", 0)
                    cc = usage.get("cache_creation_input_tokens", 0)
                    out = usage.get("output_tokens", 0)
                    context_sizes.append(cr + cc)
                    output_tokens_list.append(out)
                    total_output += out
                    total_cache_read += cr
                    total_cache_create += cc

                for block in msg.get("content", []):
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        tool_calls += 1
                        name = block.get("name", "")
                        inp = block.get("input", {})
                        if name == "Write":
                            content = inp.get("content", "")
                            lines_written += len(content.splitlines()) if content else 0
                            fp = inp.get("file_path", "")
                            if fp:
                                files_touched.add(fp)
                        elif name == "Edit":
                            old = inp.get("old_string", "")
                            new = inp.get("new_string", "")
                            lines_added += len(new.splitlines()) if new else 0
                            lines_removed += len(old.splitlines()) if old else 0
                            fp = inp.get("file_path", "")
                            if fp:
                                files_touched.add(fp)

            elif msg_type == "user":
                msg = obj.get("message", {})
                if isinstance(msg, dict):
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_result":
                                if block.get("is_error"):
                                    errors += 1
    except Exception:
        return None

    if not first_ts or not last_ts or messages < 2:
        return None

    duration = (last_ts - first_ts).total_seconds()
    ctx_growth = 0
    if len(context_sizes) >= 4:
        quarter = len(context_sizes) // 4
        first_q = sum(context_sizes[:quarter]) / quarter if quarter else 0
        last_q = sum(context_sizes[-quarter:]) / quarter if quarter else 0
        ctx_growth = (last_q / first_q - 1) * 100 if first_q > 0 else 0

    avg_context = sum(context_sizes) / len(context_sizes) if context_sizes else 0
    peak_context = max(context_sizes) if context_sizes else 0

    return {
        "project": extract_project(path),
        "start": first_ts, "duration": duration,
        "messages": messages, "human_messages": human_messages,
        "tool_calls": tool_calls, "errors": errors,
        "total_output": total_output,
        "total_cache_read": total_cache_read, "total_cache_create": total_cache_create,
        "avg_context": avg_context, "peak_context": peak_context,
        "context_growth": ctx_growth, "context_sizes": context_sizes,
        "lines_written": lines_written, "lines_added": lines_added,
        "lines_removed": lines_removed, "files_touched": len(files_touched),
        "net_lines": lines_written + lines_added - lines_removed,
    }


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates(args)
    session_files = find_sessions(dates, skip_subagents=True)

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    sessions = []
    for sf in session_files:
        s = parse_session(sf)
        if s and s["messages"] >= 4:
            sessions.append(s)

    if not sessions:
        print(f"\n  No meaningful sessions found for {label}")
        sys.exit(0)

    total_msgs = sum(s["messages"] for s in sessions)
    total_turns = sum(s["human_messages"] for s in sessions)
    total_tools = sum(s["tool_calls"] for s in sessions)
    total_errors = sum(s["errors"] for s in sessions)
    total_duration = sum(s["duration"] for s in sessions)
    total_output = sum(s["total_output"] for s in sessions)
    avg_duration = total_duration / len(sessions)
    avg_ctx = sum(s["avg_context"] for s in sessions) / len(sessions)

    print_header(f"🏥  SESSION HEALTH ANALYSIS — {label}")
    print(f"""
  Sessions: {len(sessions):<12} Total turns:   {fmt(total_turns)}
  Duration: {fmt_duration(total_duration):<12} Avg/session:   {fmt_duration(avg_duration)}

  Total messages:    {fmt(total_msgs):<12} Total tools:   {fmt(total_tools)}
  Total errors:      {fmt(total_errors):<12} Error rate:    {total_errors / total_tools * 100:.1f}%
  Avg context/turn:  {fmt_tokens(int(avg_ctx))}""")

    # ── Session Table
    print_header("📋  ALL SESSIONS", "─")
    sorted_sessions = sorted(sessions, key=lambda s: s["start"], reverse=True)

    print(f"\n  {'Date':<12} {'Dur':>5} {'Msgs':>5} {'Tools':>5} {'Err':>4} {'Ctx':>6} {'Growth':>7} {'Lines':>6} {'Files':>5}  Project")
    print(f"  {'─' * 12} {'─' * 5} {'─' * 5} {'─' * 5} {'─' * 4} {'─' * 6} {'─' * 7} {'─' * 6} {'─' * 5}  {'─' * 30}")

    for s in sorted_sessions:
        date = s["start"].strftime("%Y-%m-%d")
        dur = fmt_duration(s["duration"])
        ctx = fmt_tokens(int(s["avg_context"]))
        growth = f"+{s['context_growth']:.0f}%" if s["context_growth"] > 0 else f"{s['context_growth']:.0f}%"
        err_str = str(s["errors"]) if s["errors"] else "—"
        proj = s["project"][:28] if len(s["project"]) > 28 else s["project"]
        warn = " ⚠️" if s["context_growth"] > 200 else ""
        print(f"  {date:<12} {dur:>5} {s['messages']:>5} {s['tool_calls']:>5} {err_str:>4} {ctx:>6} {growth:>7} {s['net_lines']:>6} {s['files_touched']:>5}  {proj}{warn}")

    # ── Context Growth Analysis
    print_header("📈  CONTEXT GROWTH PATTERNS", "─")
    low_growth = [s for s in sessions if s["context_growth"] < 50]
    med_growth = [s for s in sessions if 50 <= s["context_growth"] < 200]
    high_growth = [s for s in sessions if s["context_growth"] >= 200]

    print(f"""
  Low growth  (<50%):   {len(low_growth):>3} sessions  — context stays manageable
  Med growth  (50-200%): {len(med_growth):>3} sessions  — normal for long sessions
  High growth (>200%):  {len(high_growth):>3} sessions  — consider restarting ⚠️""")

    if high_growth:
        print(f"\n  High-growth sessions:")
        for s in sorted(high_growth, key=lambda x: x["context_growth"], reverse=True)[:5]:
            print(f"    {s['start'].strftime('%Y-%m-%d')} {fmt_duration(s['duration']):>5} {s['context_growth']:>+.0f}% ctx  {s['messages']} msgs  {s['project'][:35]}")

    # ── Duration vs Productivity
    print_header("⏱️  DURATION vs PRODUCTIVITY", "─")
    buckets = [
        ("< 30m", lambda s: s["duration"] < 1800),
        ("30m-1h", lambda s: 1800 <= s["duration"] < 3600),
        ("1-2h", lambda s: 3600 <= s["duration"] < 7200),
        ("2-4h", lambda s: 7200 <= s["duration"] < 14400),
        ("4h+", lambda s: s["duration"] >= 14400),
    ]

    print(f"\n  {'Duration':<10} {'Count':>5} {'Avg msgs':>9} {'Avg lines':>10} {'Avg tools':>10} {'Lines/msg':>10} {'Err%':>6}")
    print(f"  {'─' * 10} {'─' * 5} {'─' * 9} {'─' * 10} {'─' * 10} {'─' * 10} {'─' * 6}")

    for label_b, pred in buckets:
        bucket = [s for s in sessions if pred(s)]
        if not bucket:
            continue
        avg_m = sum(s["messages"] for s in bucket) / len(bucket)
        avg_l = sum(s["net_lines"] for s in bucket) / len(bucket)
        avg_t = sum(s["tool_calls"] for s in bucket) / len(bucket)
        total_m = sum(s["messages"] for s in bucket)
        lines_per_msg = sum(s["net_lines"] for s in bucket) / total_m if total_m else 0
        total_tc = sum(s["tool_calls"] for s in bucket)
        total_e = sum(s["errors"] for s in bucket)
        err_pct = f"{total_e / total_tc * 100:.1f}%" if total_tc else "—"
        print(f"  {label_b:<10} {len(bucket):>5} {avg_m:>9.0f} {avg_l:>10.0f} {avg_t:>10.0f} {lines_per_msg:>10.1f} {err_pct:>6}")

    # ── Wasted Turns
    print_header("🗑️  WASTED TURNS (errors + retries)", "─")
    print(f"""
  Total tool calls:    {fmt(total_tools)}
  Total errors:        {fmt(total_errors)}
  Error rate:          {total_errors / total_tools * 100:.1f}%

  Each error wastes ~1 turn (the failed attempt) plus context tokens
  for the retry. Over {len(sessions)} sessions, that's ~{total_errors} wasted turns.""")

    high_err = sorted([s for s in sessions if s["tool_calls"] > 10],
                      key=lambda s: s["errors"] / s["tool_calls"] if s["tool_calls"] else 0,
                      reverse=True)[:5]
    if high_err:
        print(f"\n  Worst error-rate sessions:")
        for s in high_err:
            rate = s["errors"] / s["tool_calls"] * 100 if s["tool_calls"] else 0
            print(f"    {s['start'].strftime('%Y-%m-%d')} {rate:>5.1f}% ({s['errors']}/{s['tool_calls']})  {s['project'][:35]}")

    # ── Recommendations
    print_header("💡  RECOMMENDATIONS", "─")
    recs = []

    if len(sessions) >= 5:
        short = [s for s in sessions if s["duration"] < 3600 and s["messages"] > 5]
        long_s = [s for s in sessions if s["duration"] >= 7200 and s["messages"] > 5]
        if short and long_s:
            short_lpm = sum(s["net_lines"] for s in short) / sum(s["messages"] for s in short) if sum(s["messages"] for s in short) else 0
            long_lpm = sum(s["net_lines"] for s in long_s) / sum(s["messages"] for s in long_s) if sum(s["messages"] for s in long_s) else 0
            if short_lpm > long_lpm * 1.3:
                recs.append(f"Short sessions (<1h) produce {short_lpm:.1f} lines/msg vs {long_lpm:.1f} for long sessions (>2h). Consider shorter, focused sessions.")
            elif long_lpm > short_lpm * 1.3:
                recs.append(f"Long sessions (>2h) produce {long_lpm:.1f} lines/msg vs {short_lpm:.1f} for short. Your long sessions are productive — keep going.")

    if high_growth:
        avg_growth_dur = sum(s["duration"] for s in high_growth) / len(high_growth)
        recs.append(f"{len(high_growth)} sessions had >200% context growth. Consider restarting after ~{fmt_duration(avg_growth_dur / 2)} for these projects.")

    if total_errors > total_tools * 0.1:
        recs.append(f"Error rate is {total_errors / total_tools * 100:.1f}% — above 10%. Review common failures in claude-tools to reduce wasted turns.")
    elif total_errors > 0:
        recs.append(f"Error rate {total_errors / total_tools * 100:.1f}% is reasonable. Most errors are unavoidable (Edit mismatches, network issues).")

    peak_sessions = [s for s in sessions if s["peak_context"] > 500_000]
    if peak_sessions:
        recs.append(f"{len(peak_sessions)} sessions hit >500K context tokens. Responses slow down significantly at high context — restart to reset.")

    if not recs:
        recs.append("Sessions look healthy. No major optimization opportunities detected.")

    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec}")
    print()
