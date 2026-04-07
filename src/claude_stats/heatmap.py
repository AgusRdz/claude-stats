"""Activity heatmap by hour and day of week."""

import json
import sys
from collections import defaultdict
from datetime import datetime

from claude_stats.common import (
    PRICING, DEFAULT_PRICING, DAYS, HOURS, HEAT,
    parse_dates, parse_ts, get_tz_label,
    find_sessions, extract_project,
    fmt, bar, print_header,
)


def heat_char(value: float, max_val: float) -> str:
    if value == 0:
        return HEAT[0]
    if max_val == 0:
        return HEAT[0]
    ratio = value / max_val
    if ratio < 0.2:
        return HEAT[1]
    if ratio < 0.45:
        return HEAT[2]
    if ratio < 0.75:
        return HEAT[3]
    return HEAT[4]


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates(args)
    session_files = find_sessions(dates)
    tz_label = get_tz_label()

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    grid_messages = defaultdict(lambda: defaultdict(int))
    grid_tools = defaultdict(lambda: defaultdict(int))
    grid_tokens = defaultdict(lambda: defaultdict(int))
    grid_cost = defaultdict(lambda: defaultdict(float))
    daily_messages = defaultdict(int)
    daily_tokens = defaultdict(int)
    daily_cost = defaultdict(float)
    daily_sessions = defaultdict(int)
    hourly_messages = defaultdict(int)
    hourly_tools = defaultdict(int)
    project_by_dow = defaultdict(lambda: defaultdict(int))
    session_data = []
    total_messages = 0
    total_tools = 0
    total_output_tokens = 0

    for sf in session_files:
        project = extract_project(sf)
        first_ts = None
        last_ts = None
        sess_messages = 0
        sess_tokens = 0
        sess_cost = 0.0

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

                if local_dt:
                    if not first_ts:
                        first_ts = local_dt
                    last_ts = local_dt

                msg_type = obj.get("type")

                if msg_type in ("human", "assistant") and local_dt:
                    dow = local_dt.weekday()
                    hour = local_dt.hour
                    date_str = local_dt.strftime("%Y-%m-%d")
                    grid_messages[dow][hour] += 1
                    hourly_messages[hour] += 1
                    daily_messages[date_str] += 1
                    total_messages += 1
                    sess_messages += 1
                    project_by_dow[project][dow] += 1

                if msg_type == "assistant":
                    msg = obj.get("message", {})
                    if not isinstance(msg, dict):
                        continue
                    for block in msg.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "tool_use" and local_dt:
                            dow = local_dt.weekday()
                            hour = local_dt.hour
                            grid_tools[dow][hour] += 1
                            hourly_tools[hour] += 1
                            total_tools += 1

                    usage = msg.get("usage")
                    model = msg.get("model", "unknown")
                    if usage and local_dt:
                        dow = local_dt.weekday()
                        hour = local_dt.hour
                        date_str = local_dt.strftime("%Y-%m-%d")
                        out = usage.get("output_tokens", 0)
                        grid_tokens[dow][hour] += out
                        daily_tokens[date_str] += out
                        total_output_tokens += out
                        sess_tokens += out

                        pricing = PRICING.get(model, DEFAULT_PRICING)
                        cost = sum(
                            (usage.get(k, 0) / 1_000_000) * pricing[t]
                            for k, t in [
                                ("input_tokens", "input"),
                                ("output_tokens", "output"),
                                ("cache_read_input_tokens", "cache_read"),
                                ("cache_creation_input_tokens", "cache_create"),
                            ]
                        )
                        grid_cost[dow][hour] += cost
                        daily_cost[date_str] += cost
                        sess_cost += cost
        except Exception:
            pass

        if first_ts and last_ts and sess_messages > 0:
            duration = (last_ts - first_ts).total_seconds()
            date_str = first_ts.strftime("%Y-%m-%d")
            daily_sessions[date_str] += 1
            session_data.append({
                "project": project, "start": first_ts, "duration": duration,
                "messages": sess_messages, "tokens": sess_tokens, "cost": sess_cost,
            })

    if total_messages == 0:
        print(f"\n  No activity found for {label}")
        sys.exit(0)

    max_messages = max((grid_messages[d][h] for d in range(7) for h in range(24)), default=1)
    max_cost = max((grid_cost[d][h] for d in range(7) for h in range(24)), default=1)

    # ── Output
    print_header(f"📊  CLAUDE CODE ACTIVITY HEATMAP — {label}")
    print(f"\n  Timezone: {tz_label}")
    print(f"  Sessions: {len(session_data)} | Messages: {fmt(total_messages)} | Tools: {fmt(total_tools)}")

    # ── Messages Heatmap
    print_header("💬  MESSAGES BY HOUR & DAY", "─")
    print()
    print("        ", end="")
    for h in HOURS:
        if h % 3 == 0:
            print(f"{h:>2} ", end="")
        else:
            print("   ", end="")
    print()

    for d in range(7):
        print(f"  {DAYS[d]}  ", end="")
        for h in HOURS:
            val = grid_messages[d][h]
            print(heat_char(val, max_messages), end="")
        row_total = sum(grid_messages[d][h] for h in HOURS)
        print(f"  {row_total:>5}")
    print()
    print(f"        {HEAT[0]}none {HEAT[1]}low  {HEAT[2]}med  {HEAT[3]}high {HEAT[4]}peak")

    # ── Cost Heatmap
    print_header("💰  COST ($) BY HOUR & DAY", "─")
    print()
    print("        ", end="")
    for h in HOURS:
        if h % 3 == 0:
            print(f"{h:>2} ", end="")
        else:
            print("   ", end="")
    print()

    for d in range(7):
        print(f"  {DAYS[d]}  ", end="")
        for h in HOURS:
            val = grid_cost[d][h]
            print(heat_char(val, max_cost), end="")
        row_cost = sum(grid_cost[d][h] for h in HOURS)
        print(f" ${row_cost:>6.1f}")
    print()
    print(f"        {HEAT[0]}$0   {HEAT[1]}<20% {HEAT[2]}<45% {HEAT[3]}<75% {HEAT[4]}peak")

    # ── Hourly Summary
    print_header(f"⏰  HOURLY ACTIVITY ({tz_label})", "─")
    print()
    max_hourly = max(hourly_messages.values()) if hourly_messages else 1
    sorted_hours = sorted(HOURS, key=lambda h: hourly_messages.get(h, 0), reverse=True)

    for h in HOURS:
        msgs = hourly_messages.get(h, 0)
        tools = hourly_tools.get(h, 0)
        if msgs == 0 and tools == 0:
            continue
        bar_len = round(msgs / max_hourly * 35)
        bar_str = "█" * bar_len + "░" * (35 - bar_len)
        peak = " ← PEAK" if h == sorted_hours[0] else ""
        print(f"  {h:02d}:00  {bar_str}  {msgs:>5} msgs  {tools:>4} tools{peak}")

    # ── Daily Summary
    print_header("📅  DAILY SUMMARY", "─")
    print()
    dow_messages = defaultdict(int)
    dow_cost = defaultdict(float)
    for d in range(7):
        for h in HOURS:
            dow_messages[d] += grid_messages[d][h]
            dow_cost[d] += grid_cost[d][h]

    max_dow = max(dow_messages.values()) if dow_messages else 1
    print(f"  {'Day':<6} {'Messages':>9} {'Cost':>9} {'':>35}")
    print(f"  {'─' * 6} {'─' * 9} {'─' * 9} {'─' * 35}")
    for d in range(7):
        msgs = dow_messages[d]
        cost = dow_cost[d]
        bar_len = round(msgs / max_dow * 35) if max_dow else 0
        bar_str = "█" * bar_len + "░" * (35 - bar_len)
        print(f"  {DAYS[d]:<6} {msgs:>9} ${cost:>8.1f} {bar_str}")

    # ── Calendar View
    if daily_messages:
        print_header("📆  DAILY ACTIVITY (last 30 days)", "─")
        print()
        sorted_dates = sorted(daily_messages.keys())
        max_daily = max(daily_messages.values()) if daily_messages else 1

        print(f"  {'Date':<12} {'Sess':>5} {'Msgs':>6} {'Tokens':>9} {'Cost':>8}  {'':>25}")
        print(f"  {'─' * 12} {'─' * 5} {'─' * 6} {'─' * 9} {'─' * 8}  {'─' * 25}")

        for date in sorted_dates[-30:]:
            msgs = daily_messages[date]
            tokens = daily_tokens.get(date, 0)
            cost = daily_cost.get(date, 0)
            sessions = daily_sessions.get(date, 0)
            bar_len = round(msgs / max_daily * 25)
            bar_str = "█" * bar_len + "░" * (25 - bar_len)
            dt = datetime.strptime(date, "%Y-%m-%d")
            marker = " 🏖" if dt.weekday() >= 5 else ""
            print(f"  {date:<12} {sessions:>5} {msgs:>6} {fmt(tokens):>9} ${cost:>7.1f}  {bar_str}{marker}")

    # ── Top Sessions
    if session_data:
        print_header("🏆  TOP SESSIONS BY COST", "─")
        print()
        sorted_sessions = sorted(session_data, key=lambda s: s["cost"], reverse=True)[:10]
        for s in sorted_sessions:
            dur_min = s["duration"] / 60
            dur_str = f"{dur_min:.0f}m" if dur_min < 60 else f"{dur_min / 60:.1f}h"
            print(f"  ${s['cost']:>6.1f}  {dur_str:>6}  {s['messages']:>4} msgs  {s['project']}")

    # ── Insights
    print_header("💡  INSIGHTS", "─")
    insights = []
    active_hours = [h for h in sorted_hours if hourly_messages.get(h, 0) > 0]
    if active_hours:
        peak_h = active_hours[0]
        insights.append(f"Peak hour: {peak_h:02d}:00 {tz_label} ({hourly_messages[peak_h]} messages)")

    busiest_dow = max(range(7), key=lambda d: dow_messages[d])
    quietest_dow = min(range(7), key=lambda d: dow_messages[d])
    insights.append(f"Busiest day: {DAYS[busiest_dow]} ({dow_messages[busiest_dow]} msgs, ${dow_cost[busiest_dow]:.0f})")
    if dow_messages[quietest_dow] > 0:
        insights.append(f"Quietest day: {DAYS[quietest_dow]} ({dow_messages[quietest_dow]} msgs)")

    weekend_msgs = dow_messages[5] + dow_messages[6]
    weekday_msgs = sum(dow_messages[d] for d in range(5))
    if weekend_msgs > 0:
        weekend_pct = weekend_msgs / (weekend_msgs + weekday_msgs) * 100
        insights.append(f"Weekend activity: {weekend_pct:.1f}% of messages — {'take a break!' if weekend_pct > 20 else 'good balance'}")
    else:
        insights.append("No weekend activity — healthy work-life balance!")

    if daily_cost:
        exp_date = max(daily_cost, key=daily_cost.get)
        insights.append(f"Most expensive day: {exp_date} (${daily_cost[exp_date]:.1f})")

    if session_data:
        avg_dur = sum(s["duration"] for s in session_data) / len(session_data)
        avg_str = f"{avg_dur / 60:.0f}m" if avg_dur < 3600 else f"{avg_dur / 3600:.1f}h"
        insights.append(f"Avg session duration: {avg_str}")

    for i, insight in enumerate(insights, 1):
        print(f"  {i}. {insight}")
    print()
