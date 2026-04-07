package config

import (
	"os"
	"path/filepath"
)

// Paths
var (
	ClaudeDir   = filepath.Join(homeDir(), ".claude")
	ProjectsDir = filepath.Join(homeDir(), ".claude", "projects")
	SettingsFile = filepath.Join(homeDir(), ".claude", "settings.json")
)

func homeDir() string {
	h, _ := os.UserHomeDir()
	return h
}

// Pricing per 1M tokens
type ModelPricing struct {
	Input       float64
	Output      float64
	CacheRead   float64
	CacheCreate float64
}

var Pricing = map[string]ModelPricing{
	"claude-opus-4-6":            {Input: 15.00, Output: 75.00, CacheRead: 1.875, CacheCreate: 18.75},
	"claude-opus-4-5-20251101":   {Input: 15.00, Output: 75.00, CacheRead: 1.875, CacheCreate: 18.75},
	"claude-sonnet-4-6":          {Input: 3.00, Output: 15.00, CacheRead: 0.30, CacheCreate: 3.75},
	"claude-haiku-4-5-20251001":  {Input: 0.80, Output: 4.00, CacheRead: 0.08, CacheCreate: 1.00},
}

var DefaultPricing = ModelPricing{Input: 15.00, Output: 75.00, CacheRead: 1.875, CacheCreate: 18.75}

func GetPricing(model string) ModelPricing {
	if p, ok := Pricing[model]; ok {
		return p
	}
	return DefaultPricing
}

// Tool classifications
var ReadTools = map[string]bool{
	"Read": true, "Glob": true, "Grep": true,
	"WebFetch": true, "WebSearch": true,
	"TaskList": true, "TaskGet": true,
}

var WriteTools = map[string]bool{
	"Edit": true, "Write": true, "NotebookEdit": true,
	"Bash": true, "TaskCreate": true, "TaskUpdate": true,
}

var AgentTools = map[string]bool{
	"Task": true, "SendMessage": true,
}

var AutoAllowedTools = map[string]bool{
	"Glob": true, "Grep": true, "WebSearch": true, "WebFetch": true,
	"Task": true, "TaskCreate": true, "TaskUpdate": true,
	"TaskList": true, "TaskGet": true, "TaskOutput": true,
	"SendMessage": true, "TeamCreate": true, "TeamDelete": true,
	"AskUserQuestion": true, "EnterPlanMode": true, "ExitPlanMode": true,
	"Skill": true, "NotebookEdit": true, "EnterWorktree": true, "TaskStop": true,
}

var DestructiveCmds = map[string]bool{
	"rm": true, "sudo": true, "kill": true, "pkill": true, "rmdir": true,
}

// Display
var Days = []string{"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
var Heat = []string{" · ", " ░ ", " ▒ ", " ▓ ", " █ "}

// JiraPattern prefix list (checked via strings.HasPrefix in practice)
var JiraPrefixes = []string{
	"DX", "BACK", "FRNT", "ANG", "CACG", "CORE",
	"INF", "DATA", "RES", "CSD", "NJP", "SFR", "DPI",
}
