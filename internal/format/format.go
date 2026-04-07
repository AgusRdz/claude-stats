package format

import (
	"fmt"
	"math"
	"strings"
)

// Fmt formats an integer with comma separators.
func Fmt(n int) string {
	s := fmt.Sprintf("%d", n)
	if n < 0 {
		s = s[1:]
		return "-" + insertCommas(s)
	}
	return insertCommas(s)
}

func insertCommas(s string) string {
	n := len(s)
	if n <= 3 {
		return s
	}
	var b strings.Builder
	for i, c := range s {
		if i > 0 && (n-i)%3 == 0 {
			b.WriteByte(',')
		}
		b.WriteRune(c)
	}
	return b.String()
}

// Pct formats n/total as a percentage string.
func Pct(n, total int) string {
	if total == 0 {
		return "0%"
	}
	return fmt.Sprintf("%.1f%%", float64(n)/float64(total)*100)
}

// Bar renders an ASCII progress bar.
func Bar(n, maxVal float64, width int) string {
	if maxVal == 0 {
		return strings.Repeat("░", width)
	}
	ratio := n / maxVal
	if ratio > 1 {
		ratio = 1
	}
	filled := int(math.Round(ratio * float64(width)))
	return strings.Repeat("█", filled) + strings.Repeat("░", width-filled)
}

// Header prints a section header with a decorative border.
func Header(text, char string) {
	w := 70
	border := strings.Repeat(char, w)
	fmt.Printf("\n %s\n  %s\n %s\n", border, text, border)
}

// FmtTokens formats token counts as human-readable (e.g., 1.2M, 45K).
func FmtTokens(n int) string {
	if n >= 1_000_000 {
		return fmt.Sprintf("%.1fM", float64(n)/1_000_000)
	}
	if n >= 1_000 {
		return fmt.Sprintf("%.0fK", float64(n)/1_000)
	}
	return fmt.Sprintf("%d", n)
}

// FmtDuration formats seconds as a compact duration string.
func FmtDuration(secs float64) string {
	if secs < 3600 {
		return fmt.Sprintf("%.0fm", secs/60)
	}
	return fmt.Sprintf("%.1fh", secs/3600)
}

// FriendlyModel shortens a Claude model ID for display.
func FriendlyModel(model string) string {
	r := model
	r = strings.ReplaceAll(r, "claude-", "")
	r = strings.ReplaceAll(r, "-20251001", "")
	r = strings.ReplaceAll(r, "-20251101", "")
	r = strings.ReplaceAll(r, "-20250929", "")
	return r
}
