package format

import (
	"fmt"
	"math"
	"strings"
)

// ANSI reset and styles.
const (
	Reset = "\033[0m"
	Bold  = "\033[1m"
	Dim   = "\033[2m"
)

// Semantic colors (256-color palette).
const (
	Red    = "\033[38;5;197m"
	Green  = "\033[38;5;35m"
	Yellow = "\033[38;5;220m"
	Orange = "\033[38;5;208m"
	Blue   = "\033[38;5;33m"
	Cyan   = "\033[38;5;37m"
)

// barGradient defines the color progression for chart bars (teal → blue).
var barGradient = []int{36, 37, 38, 39, 33, 27}

// gradientColor returns the ANSI color for position t (0.0 to 1.0).
func gradientColor(t float64) string {
	n := len(barGradient)
	idx := int(t * float64(n-1))
	if idx < 0 {
		idx = 0
	}
	if idx >= n {
		idx = n - 1
	}
	return fmt.Sprintf("\033[38;5;%dm", barGradient[idx])
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// ScoreColor returns green/yellow/red based on a 0-100 score.
func ScoreColor(score float64) string {
	switch {
	case score >= 70:
		return Green
	case score >= 40:
		return Yellow
	default:
		return Red
	}
}

// ArrowColor colors trend arrows (▲ green, ▼ red).
func ArrowColor(s string) string {
	switch s {
	case "▲":
		return Green + s + Reset
	case "▼":
		return Red + s + Reset
	default:
		return Dim + s + Reset
	}
}

// BarWith renders a progress bar with a specific color for the filled section.
func BarWith(n, maxVal float64, width int, color string) string {
	if maxVal == 0 {
		return Dim + strings.Repeat("░", width) + Reset
	}
	ratio := n / maxVal
	if ratio > 1 {
		ratio = 1
	}
	filled := int(math.Round(ratio * float64(width)))
	empty := width - filled

	var b strings.Builder
	if filled > 0 {
		b.WriteString(color)
		b.WriteString(strings.Repeat("█", filled))
		b.WriteString(Reset)
	}
	if empty > 0 {
		b.WriteString(Dim)
		b.WriteString(strings.Repeat("░", empty))
		b.WriteString(Reset)
	}
	return b.String()
}
