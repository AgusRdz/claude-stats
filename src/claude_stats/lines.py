"""Lines of code analytics — written, edited, and removed."""

import json
import sys
from collections import defaultdict

from claude_stats.common import (
    parse_dates, find_sessions, extract_project, shorten_path, get_ext,
    fmt, bar, print_header,
)


def count_lines(s: str) -> int:
    return len(s.splitlines()) if s else 0


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates(args)
    session_files = find_sessions(dates)

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    total_writes = 0
    total_edits = 0
    total_written = 0
    total_added = 0
    total_removed = 0
    total_files_created = 0
    total_files_edited = 0

    ext_stats = defaultdict(lambda: {"written": 0, "added": 0, "removed": 0, "files": set()})
    proj_stats = defaultdict(lambda: {"written": 0, "added": 0, "removed": 0, "writes": 0, "edits": 0, "files": set()})
    file_stats = defaultdict(lambda: {"written": 0, "added": 0, "removed": 0, "ops": 0})
    all_files = set()

    for sf in session_files:
        project = extract_project(sf)
        try:
            for line in open(sf):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue

                for block in msg.get("content", []):
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue

                    name = block.get("name")
                    inp = block.get("input", {})

                    if name == "Write":
                        fp = inp.get("file_path", "")
                        content = inp.get("content", "")
                        lines = count_lines(content)
                        total_writes += 1
                        total_written += lines
                        total_files_created += 1

                        ext = get_ext(fp)
                        ext_stats[ext]["written"] += lines
                        ext_stats[ext]["files"].add(fp)
                        proj_stats[project]["written"] += lines
                        proj_stats[project]["writes"] += 1
                        proj_stats[project]["files"].add(fp)

                        short = shorten_path(fp)
                        file_stats[short]["written"] += lines
                        file_stats[short]["ops"] += 1
                        all_files.add(fp)

                    elif name == "Edit":
                        fp = inp.get("file_path", "")
                        old = inp.get("old_string", "")
                        new = inp.get("new_string", "")
                        old_lines = count_lines(old)
                        new_lines = count_lines(new)
                        total_edits += 1
                        total_added += new_lines
                        total_removed += old_lines
                        total_files_edited += 1

                        ext = get_ext(fp)
                        ext_stats[ext]["added"] += new_lines
                        ext_stats[ext]["removed"] += old_lines
                        ext_stats[ext]["files"].add(fp)
                        proj_stats[project]["added"] += new_lines
                        proj_stats[project]["removed"] += old_lines
                        proj_stats[project]["edits"] += 1
                        proj_stats[project]["files"].add(fp)

                        short = shorten_path(fp)
                        file_stats[short]["added"] += new_lines
                        file_stats[short]["removed"] += old_lines
                        file_stats[short]["ops"] += 1
                        all_files.add(fp)
        except Exception:
            pass

    total_ops = total_writes + total_edits
    if total_ops == 0:
        print(f"\n  No Write/Edit operations found for {label}")
        sys.exit(0)

    net = total_written + total_added - total_removed

    # ── Summary
    print_header(f"📝  CLAUDE CODE LINES OF CODE — {label}")
    print(f"""
  Operations:    {total_writes} writes + {total_edits} edits = {total_ops} total
  Files touched: {len(all_files)}

  ┌──────────────────────────────────────┐
  │  Lines written (new files):  {fmt(total_written):>8} │
  │  Lines added (edits):        {fmt(total_added):>8} │
  │  Lines removed (edits):      {fmt(total_removed):>8} │
  │  ──────────────────────────────────  │
  │  NET LINES:                  {fmt(net):>8} │
  │  TOTAL THROUGHPUT:           {fmt(total_written + total_added + total_removed):>8} │
  └──────────────────────────────────────┘""")

    # ── By Extension
    print_header("📄  BY FILE EXTENSION", "─")
    sorted_ext = sorted(ext_stats.items(), key=lambda x: x[1]["written"] + x[1]["added"], reverse=True)[:15]
    max_ext = max((e["written"] + e["added"]) for _, e in sorted_ext) if sorted_ext else 1

    print(f"\n  {'Ext':<10} {'Written':>8} {'Added':>8} {'Removed':>8} {'Net':>8} {'Files':>5}  {'':>12}")
    print(f"  {'─' * 10} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 5}  {'─' * 12}")

    for ext, s in sorted_ext:
        ext_net = s["written"] + s["added"] - s["removed"]
        total_ext = s["written"] + s["added"]
        sign = "+" if ext_net >= 0 else ""
        print(f"  {ext:<10} {s['written']:>8} {s['added']:>8} {s['removed']:>8} {sign}{ext_net:>7} {len(s['files']):>5}  {bar(total_ext, max_ext, 12)}")

    # ── By Project
    print_header("📁  BY PROJECT", "─")
    sorted_proj = sorted(proj_stats.items(), key=lambda x: x[1]["written"] + x[1]["added"], reverse=True)
    max_proj = max((p["written"] + p["added"]) for _, p in sorted_proj) if sorted_proj else 1

    print(f"\n  {'Project':<40} {'Written':>8} {'Added':>8} {'Removed':>8} {'Net':>7}  {'':>10}")
    print(f"  {'─' * 40} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 7}  {'─' * 10}")

    for proj, s in sorted_proj:
        proj_net = s["written"] + s["added"] - s["removed"]
        total_proj = s["written"] + s["added"]
        name = proj[:38] if len(proj) > 38 else proj
        sign = "+" if proj_net >= 0 else ""
        print(f"  {name:<40} {s['written']:>8} {s['added']:>8} {s['removed']:>8} {sign}{proj_net:>6}  {bar(total_proj, max_proj, 10)}")

    # ── Top Files (most touched)
    print_header("🔥  TOP FILES (most operations)", "─")
    sorted_files = sorted(file_stats.items(), key=lambda x: x[1]["ops"], reverse=True)[:20]

    print(f"\n  {'Ops':>4} {'Written':>8} {'+Lines':>7} {'-Lines':>7}  File")
    print(f"  {'─' * 4} {'─' * 8} {'─' * 7} {'─' * 7}  {'─' * 45}")

    for fp, s in sorted_files:
        display = fp if len(fp) <= 50 else "..." + fp[-(47):]
        print(f"  {s['ops']:>4} {s['written']:>8} {s['added']:>7} {s['removed']:>7}  {display}")

    # ── Top Files (most lines)
    print_header("📏  TOP FILES (most lines written/added)", "─")
    sorted_by_lines = sorted(file_stats.items(), key=lambda x: x[1]["written"] + x[1]["added"], reverse=True)[:15]
    max_lines = (sorted_by_lines[0][1]["written"] + sorted_by_lines[0][1]["added"]) if sorted_by_lines else 1

    print(f"\n  {'Lines':>7} {'':>10}  File")
    print(f"  {'─' * 7} {'─' * 10}  {'─' * 45}")

    for fp, s in sorted_by_lines:
        total_lines = s["written"] + s["added"]
        display = fp if len(fp) <= 50 else "..." + fp[-(47):]
        print(f"  {total_lines:>7} {bar(total_lines, max_lines, 10)}  {display}")

    # ── Insights
    print_header("💡  INSIGHTS", "─")
    insights = []

    if total_written > total_added:
        pct_new = total_written / (total_written + total_added) * 100
        insights.append(f"Mostly new files: {pct_new:.0f}% of lines are from Write (new files/rewrites).")
    else:
        pct_edit = total_added / (total_written + total_added) * 100
        insights.append(f"Mostly edits: {pct_edit:.0f}% of lines are from Edit operations.")

    if total_removed > 0:
        ratio = (total_written + total_added) / total_removed
        insights.append(f"Add/remove ratio: {ratio:.1f}:1 — {'growing codebase' if ratio > 2 else 'healthy refactoring' if ratio > 1 else 'net reduction'}.")

    if sorted_files:
        top_file = sorted_files[0]
        insights.append(f"Most touched file: {top_file[0][-40:]} ({top_file[1]['ops']} operations)")

    if sorted_ext:
        top_ext = sorted_ext[0]
        ext_total = top_ext[1]["written"] + top_ext[1]["added"]
        all_total = total_written + total_added
        insights.append(f"Top language: {top_ext[0]} ({ext_total / all_total * 100:.0f}% of lines)")

    for i, insight in enumerate(insights, 1):
        print(f"  {i}. {insight}")
    print()
