"""Permission prompt analysis — which commands require approval and allowlist suggestions."""

import fnmatch
import json
import sys
from collections import defaultdict

from claude_stats.common import (
    AUTO_ALLOWED_TOOLS, DESTRUCTIVE_CMDS,
    parse_dates, find_sessions, extract_project, shorten_path,
    fmt, pct, bar, print_header,
)
from claude_stats.common.config import SETTINGS_FILE


def load_allow_patterns() -> dict:
    if not SETTINGS_FILE.exists():
        return {"bash": [], "edit": [], "write": [], "read": [], "raw": []}
    settings = json.load(open(SETTINGS_FILE))
    allow = settings.get("permissions", {}).get("allow", [])
    patterns = {"bash": [], "edit": [], "write": [], "read": [], "raw": allow}
    for p in allow:
        if p.startswith("Bash(") and p.endswith(")"):
            patterns["bash"].append(p[5:-1])
        elif p.startswith("Edit(") and p.endswith(")"):
            patterns["edit"].append(p[5:-1])
        elif p.startswith("Write(") and p.endswith(")"):
            patterns["write"].append(p[5:-1])
        elif p.startswith("Read(") and p.endswith(")"):
            patterns["read"].append(p[5:-1])
        elif p == "Read":
            patterns["read"].append("**")
    return patterns


def is_allowed(name: str, inp: dict, patterns: dict) -> bool:
    if name in AUTO_ALLOWED_TOOLS:
        return True
    if name == "Read":
        return any(fnmatch.fnmatch(inp.get("file_path", ""), p) for p in patterns["read"]) if patterns["read"] else False
    if name == "Bash":
        return any(fnmatch.fnmatch(inp.get("command", ""), p) for p in patterns["bash"])
    if name in ("Edit", "Write"):
        key = name.lower()
        return any(fnmatch.fnmatch(inp.get("file_path", ""), p) for p in patterns[key])
    return False


def get_bash_base(cmd: str) -> str:
    parts = cmd.strip().split()
    if not parts:
        return "(empty)"
    base = parts[0]
    if "/" in base:
        base = base.rsplit("/", 1)[-1]
    return base


def bash_preview(cmd: str, max_len: int = 55) -> str:
    cmd = " ; ".join(line.strip() for line in cmd.split("\n") if line.strip())
    return cmd[:max_len - 3] + "..." if len(cmd) > max_len else cmd


def suggest_pattern(name: str, inp: dict) -> str:
    if name == "Bash":
        base = get_bash_base(inp.get("command", ""))
        if base in DESTRUCTIVE_CMDS:
            return ""
        if base == "chmod":
            return "Bash(chmod +x *)"
        if base == "#":
            return "Bash(#*)"
        if base == "mkdir":
            return "Bash(mkdir *)"
        if base == "jq":
            return "Bash(jq*)"
        return f"Bash({base} *)"
    if name in ("Edit", "Write"):
        fp = inp.get("file_path", "")
        home = str(__import__("pathlib").Path.home())
        if fp.startswith(home):
            # Suggest pattern for the first two path segments under home
            rel = fp[len(home) + 1:]
            parts = rel.split("/")
            if len(parts) >= 2:
                return f'{name}({home}/{"/".join(parts[:2])}/**)'
            return f"{name}({home}/**)"
        if fp.startswith("/tmp/"):
            return f"{name}(/tmp/**)"
        return ""
    return ""


def run(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    dates, label = parse_dates(args)
    patterns = load_allow_patterns()
    session_files = find_sessions(dates)

    if not session_files:
        print(f"\n  No sessions found for {label}")
        sys.exit(0)

    total_auto = 0
    total_prompted = 0
    prompted_by_tool = defaultdict(int)
    auto_by_tool = defaultdict(int)
    bash_prompted = defaultdict(int)
    bash_auto = defaultdict(int)
    bash_samples = defaultdict(list)
    edit_prompted = defaultdict(int)
    write_prompted = defaultdict(int)
    project_prompted = defaultdict(int)
    project_auto = defaultdict(int)
    suggestions = defaultdict(int)

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
                    name = block.get("name", "")
                    inp = block.get("input", {})

                    if is_allowed(name, inp, patterns):
                        total_auto += 1
                        auto_by_tool[name] += 1
                        project_auto[project] += 1
                        if name == "Bash":
                            bash_auto[get_bash_base(inp.get("command", ""))] += 1
                    else:
                        total_prompted += 1
                        prompted_by_tool[name] += 1
                        project_prompted[project] += 1

                        if name == "Bash":
                            base = get_bash_base(inp.get("command", ""))
                            bash_prompted[base] += 1
                            if len(bash_samples[base]) < 1:
                                bash_samples[base].append(bash_preview(inp.get("command", "")))
                        elif name == "Edit":
                            fp = shorten_path(inp.get("file_path", ""))
                            parts = fp.split("/")
                            edit_prompted["/".join(parts[:2]) + "/**" if len(parts) >= 2 else fp] += 1
                        elif name == "Write":
                            fp = shorten_path(inp.get("file_path", ""))
                            parts = fp.split("/")
                            write_prompted["/".join(parts[:2]) + "/**" if len(parts) >= 2 else fp] += 1

                        sug = suggest_pattern(name, inp)
                        if sug:
                            suggestions[sug] += 1
        except Exception:
            pass

    total = total_auto + total_prompted
    if total == 0:
        print(f"\n  No tool calls found for {label}")
        sys.exit(0)

    # ── Summary
    print_header(f"🔐  PERMISSION PROMPT ANALYSIS — {label}")
    auto_pct = total_auto / total * 100 if total else 0
    prompt_pct = total_prompted / total * 100 if total else 0

    print(f"""
  Total tool calls:  {fmt(total)}
  Auto-allowed:      {fmt(total_auto):>8} ({auto_pct:.0f}%)  {bar(total_auto, total, 30)}
  Required prompt:   {fmt(total_prompted):>8} ({prompt_pct:.0f}%)  {bar(total_prompted, total, 30)}""")

    if total_prompted == 0:
        print("\n  🎉 Zero prompts! Your allowlist is perfectly tuned.")
        print()
        return

    # ── By Tool
    print_header("🔧  PROMPTS BY TOOL", "─")
    max_tool = max(prompted_by_tool.values()) if prompted_by_tool else 1

    print(f"\n  {'Tool':<22} {'Prompted':>8} {'Auto':>8} {'Rate':>7}  {'':>15}")
    print(f"  {'─' * 22} {'─' * 8} {'─' * 8} {'─' * 7}  {'─' * 15}")
    for tool in sorted(prompted_by_tool, key=lambda t: prompted_by_tool[t], reverse=True):
        p = prompted_by_tool[tool]
        a = auto_by_tool.get(tool, 0)
        print(f"  {tool:<22} {p:>8} {a:>8} {pct(p, p + a):>7}  {bar(p, max_tool, 15)}")

    # ── Bash Ranking
    if bash_prompted:
        print_header("🐚  BASH COMMANDS REQUIRING PROMPTS", "─")
        sorted_bash = sorted(bash_prompted.items(), key=lambda x: x[1], reverse=True)[:15]
        max_bash = sorted_bash[0][1] if sorted_bash else 1

        print(f"\n  {'Cmd':<12} {'#':>5} {'Auto':>5} {'Rate':>6}  {'':>12}  Sample")
        print(f"  {'─' * 12} {'─' * 5} {'─' * 5} {'─' * 6}  {'─' * 12}  {'─' * 30}")
        for cmd, count in sorted_bash:
            a = bash_auto.get(cmd, 0)
            rate = pct(count, count + a)
            sample = bash_samples.get(cmd, [""])[0]
            sample_str = sample[:38] + "..." if len(sample) > 38 else sample
            print(f"  {cmd:<12} {count:>5} {a:>5} {rate:>6}  {bar(count, max_bash, 12)}  {sample_str}")

    # ── Edit/Write Paths
    if edit_prompted or write_prompted:
        print_header("✏️  EDIT/WRITE PATHS REQUIRING PROMPTS", "─")

        combined = defaultdict(lambda: {"edit": 0, "write": 0})
        for path, count in edit_prompted.items():
            combined[path]["edit"] = count
        for path, count in write_prompted.items():
            combined[path]["write"] = count

        sorted_paths = sorted(combined.items(), key=lambda x: x[1]["edit"] + x[1]["write"], reverse=True)[:10]
        max_path = (sorted_paths[0][1]["edit"] + sorted_paths[0][1]["write"]) if sorted_paths else 1

        print(f"\n  {'Path':<35} {'Edit':>5} {'Write':>6} {'Total':>6}  {'':>12}")
        print(f"  {'─' * 35} {'─' * 5} {'─' * 6} {'─' * 6}  {'─' * 12}")
        for path, counts in sorted_paths:
            t = counts["edit"] + counts["write"]
            print(f"  {path:<35} {counts['edit']:>5} {counts['write']:>6} {t:>6}  {bar(t, max_path, 12)}")

    # ── By Project
    if len(project_prompted) > 1:
        print_header("📁  PROMPTS BY PROJECT", "─")
        sorted_proj = sorted(project_prompted.items(), key=lambda x: x[1], reverse=True)
        max_proj = sorted_proj[0][1] if sorted_proj else 1

        print(f"\n  {'Project':<42} {'Prompts':>7} {'Rate':>7}  {'':>12}")
        print(f"  {'─' * 42} {'─' * 7} {'─' * 7}  {'─' * 12}")
        for proj, p in sorted_proj:
            a = project_auto.get(proj, 0)
            name = proj[:40] if len(proj) > 40 else proj
            print(f"  {name:<42} {p:>7} {pct(p, p + a):>7}  {bar(p, max_proj, 12)}")

    # ── Suggestions
    print_header("💡  SUGGESTED ALLOW PATTERNS", "─")

    bash_sugs = {k: v for k, v in suggestions.items() if k.startswith("Bash(") and v >= 3}
    edit_sugs = {k: v for k, v in suggestions.items() if k.startswith("Edit(") and v >= 3}
    write_sugs = {k: v for k, v in suggestions.items() if k.startswith("Write(") and v >= 3}

    if bash_sugs:
        print("\n  Bash commands:")
        print(f"  {'Pattern':<40} {'Saves':>6}")
        print(f"  {'─' * 40} {'─' * 6}")
        for pattern, count in sorted(bash_sugs.items(), key=lambda x: x[1], reverse=True):
            if not any(pattern == f"Bash({p})" for p in patterns["bash"]):
                quoted = f'"{pattern}"'
                print(f"  {quoted:<40} ~{count}")

    if edit_sugs or write_sugs:
        print("\n  Edit/Write paths:")
        print(f"  {'Pattern':<58} {'Saves':>6}")
        print(f"  {'─' * 58} {'─' * 6}")
        all_path_sugs = defaultdict(int)
        for k, v in {**edit_sugs, **write_sugs}.items():
            all_path_sugs[k] += v
        for pattern, count in sorted(all_path_sugs.items(), key=lambda x: x[1], reverse=True):
            quoted = f'"{pattern}"'
            print(f"  {quoted:<58} ~{count}")

    total_edit_write = sum(edit_prompted.values()) + sum(write_prompted.values())
    home = str(__import__("pathlib").Path.home())
    if total_edit_write > 20:
        print(f'\n  💣 Nuclear option (saves ~{total_edit_write} prompts):')
        print(f'     "Edit({home}/**)"')
        print(f'     "Write({home}/**)"')

    # ── Impact
    print_header("📊  IMPACT SUMMARY", "─")
    bash_saveable = sum(v for k, v in bash_sugs.items()
                        if not any(f"Bash({p})" == k for p in patterns["bash"]))
    total_saveable = bash_saveable + total_edit_write

    pct_bar = bar(total_saveable, total_prompted, 30)
    print(f"""
  Bash patterns:    ~{bash_saveable} prompts saved
  Edit/Write nuke:  ~{total_edit_write} prompts saved
  ─────────────────────────────────
  Potential:        ~{total_saveable} / {total_prompted}  ({pct(total_saveable, total_prompted)})
  {pct_bar}
""")
