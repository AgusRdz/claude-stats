package projects

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/Andrevops/claude-stats/internal/config"
)

// ExtractProject returns a human-readable project name from a session file path.
// Claude Code encodes absolute paths in folder names by replacing separators with '-'.
func ExtractProject(path string) string {
	// Get the path relative to the projects dir
	rel, err := filepath.Rel(config.ProjectsDir, path)
	if err != nil {
		return "unknown"
	}
	// Use forward slashes for consistency
	rel = filepath.ToSlash(rel)
	parts := strings.SplitN(rel, "/", 2)
	folder := parts[0]

	home, _ := os.UserHomeDir()
	homeEncoded := encodeHome(home)

	if strings.HasPrefix(folder, homeEncoded+"-") {
		result := folder[len(homeEncoded)+1:]
		if result == "" {
			return "unknown"
		}
		return result
	}
	if strings.HasPrefix(folder, homeEncoded) {
		result := strings.TrimLeft(folder[len(homeEncoded):], "-")
		if result == "" {
			return "unknown"
		}
		return result
	}
	if folder == "" {
		return "unknown"
	}
	return folder
}

// encodeHome converts a home directory path to its Claude Code encoded form.
func encodeHome(home string) string {
	// Replace both \ and / with -
	r := strings.ReplaceAll(home, `\`, "-")
	r = strings.ReplaceAll(r, "/", "-")
	return r
}

// ShortenPath replaces the home directory prefix with ~.
func ShortenPath(fp string) string {
	home, _ := os.UserHomeDir()
	if strings.HasPrefix(fp, home) {
		return "~" + fp[len(home):]
	}
	return fp
}

// GetExt returns the file extension including the dot (e.g., ".py", ".ts").
func GetExt(fp string) string {
	// Use forward-slash split for consistency
	clean := filepath.ToSlash(fp)
	base := clean
	if idx := strings.LastIndex(clean, "/"); idx >= 0 {
		base = clean[idx+1:]
	}
	if idx := strings.LastIndex(base, "."); idx > 0 {
		return "." + base[idx+1:]
	}
	return "(none)"
}
