"""Output formatting helpers — numbers, bars, headers."""


def fmt(n: int) -> str:
    """Format an integer with comma separators."""
    return f"{n:,}"


def pct(n: int, total: int) -> str:
    """Format n/total as a percentage string."""
    return f"{n / total * 100:.1f}%" if total else "0%"


def bar(n: float, max_val: float, width: int = 20) -> str:
    """Render an ASCII progress bar."""
    if max_val == 0:
        return "░" * width
    filled = round(min(n / max_val, 1.0) * width)
    return "█" * filled + "░" * (width - filled)


def print_header(text: str, char: str = "═"):
    """Print a section header with a decorative border."""
    w = 70
    print(f"\n {char * w}")
    print(f"  {text}")
    print(f" {char * w}")


def fmt_tokens(n: int) -> str:
    """Format token counts as human-readable (e.g., 1.2M, 45K)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def fmt_duration(secs: float) -> str:
    """Format seconds as a compact duration string (e.g., 45m, 2.1h)."""
    if secs < 3600:
        return f"{secs / 60:.0f}m"
    return f"{secs / 3600:.1f}h"


def friendly_model(model: str) -> str:
    """Shorten a Claude model ID for display."""
    return (
        model.replace("claude-", "")
        .replace("-20251001", "")
        .replace("-20251101", "")
        .replace("-20250929", "")
    )
