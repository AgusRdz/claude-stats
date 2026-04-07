package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"

	"github.com/Andrevops/claude-stats/internal/commands"
)

// version is set at build time via -ldflags.
var version = "dev"

const (
	blue  = "\033[1;34m"
	cyan  = "\033[0;36m"
	green = "\033[0;32m"
	dim   = "\033[2m"
	bold  = "\033[1m"
	reset = "\033[0m"
)

type command struct {
	cmd, name, desc string
	fn              func([]string)
}

var allCommands = []command{
	{"tokens", "Token Usage", "Tokens, cost breakdown, per-project and per-model spending", commands.Tokens},
	{"tools", "Tool Analytics", "Tool call frequency, error rates, Bash subcommands, chains", commands.Tools},
	{"prompts", "Permission Prompts", "Commands requiring approval, allowlist suggestions", commands.Prompts},
	{"heatmap", "Activity Heatmap", "Activity by hour/day, calendar view, top sessions", commands.Heatmap},
	{"lines", "Lines of Code", "Lines written, edited, removed by extension, project, file", commands.Lines},
	{"sessions", "Session Health", "Context growth, duration, bloat detection, restart advice", commands.Sessions},
	{"efficiency", "Efficiency", "Lines/turn, wasted turns, productivity ratios per project", commands.Efficiency},
	{"report", "Weekly Report", "Executive summary combining all analytics into one view", commands.Report},
	{"digest", "Work Digest", "What you worked on: tickets, branches, MRs, commits, files", commands.Digest},
}

func showMenu() {
	fmt.Printf("\n%s", bold)
	fmt.Println("  ╔═══════════════════════════════════════════════════╗")
	fmt.Println("  ║        🔢  Claude Code Analytics Suite           ║")
	fmt.Println("  ╚═══════════════════════════════════════════════════╝")
	fmt.Printf("%s\n", reset)

	for i, c := range allCommands {
		fmt.Printf("  %s%d)%s %s%s%s  %s(%s)%s\n",
			blue, i+1, reset, bold, c.name, reset, dim, c.cmd, reset)
		fmt.Printf("     %s%s%s\n\n", cyan, c.desc, reset)
	}

	fmt.Printf("  %s%s%s\n", dim, strings.Repeat("─", 49), reset)
	fmt.Printf("  %sq)%s Quit\n\n", blue, reset)
}

func pickTimeframe(reader *bufio.Reader) []string {
	fmt.Printf("\n  %sTimeframe:%s\n", bold, reset)
	fmt.Printf("  %s1)%s Today       %s4)%s Last 30 days\n", green, reset, green, reset)
	fmt.Printf("  %s2)%s Yesterday   %s5)%s All time\n", green, reset, green, reset)
	fmt.Printf("  %s3)%s Last 7 days %s6)%s Custom date\n\n", green, reset, green, reset)

	fmt.Print("  Pick [1-6]: ")
	tf, _ := readLine(reader)

	switch strings.TrimSpace(tf) {
	case "", "1":
		return nil
	case "2":
		return []string{"--yesterday"}
	case "3":
		return []string{"--week"}
	case "4":
		return []string{"--month"}
	case "5":
		return []string{"--all"}
	case "6":
		fmt.Print("  Enter date (YYYY-MM-DD): ")
		date, _ := readLine(reader)
		return []string{strings.TrimSpace(date)}
	}
	return nil
}

func interactiveMenu() {
	reader := bufio.NewReader(os.Stdin)
	for {
		showMenu()
		fmt.Printf("  Pick a tool [1-%d, q]: ", len(allCommands))
		choice, err := readLine(reader)
		if err != nil {
			fmt.Println()
			break
		}
		choice = strings.TrimSpace(choice)

		if strings.ToLower(choice) == "q" {
			fmt.Println()
			break
		}

		idx := 0
		fmt.Sscanf(choice, "%d", &idx)
		if idx < 1 || idx > len(allCommands) {
			fmt.Println("  Invalid choice")
			continue
		}

		c := allCommands[idx-1]
		extraArgs := pickTimeframe(reader)
		if extraArgs == nil {
			extraArgs = []string{}
		}

		if c.cmd == "digest" {
			fmt.Printf("\n  %sAI Analysis:%s\n", bold, reset)
			fmt.Printf("  %s1)%s Data only   %s2)%s Data + AI summary\n\n", green, reset, green, reset)
			fmt.Print("  Pick [1-2]: ")
			aiChoice, _ := readLine(reader)
			if strings.TrimSpace(aiChoice) == "2" {
				extraArgs = append(extraArgs, "--ai")
			}
		}

		fmt.Println()
		c.fn(extraArgs)
		fmt.Println()
		fmt.Print("  Press Enter to continue...")
		readLine(reader)
	}
}

func readLine(reader *bufio.Reader) (string, error) {
	line, err := reader.ReadString('\n')
	return strings.TrimRight(line, "\r\n"), err
}

func printHelp() {
	fmt.Println("Usage: claude-stats [command] [options]")
	fmt.Println()
	fmt.Println("Commands:")
	for _, c := range allCommands {
		fmt.Printf("  %-14s %s\n", c.cmd, c.desc)
	}
	fmt.Println()
	fmt.Println("Meta:")
	fmt.Println("  version        Show version")
	fmt.Println("  self-update    Update to latest version")
	fmt.Println("  help           Show this help")
	fmt.Println()
	fmt.Println("Options:")
	fmt.Println("  --yesterday    Yesterday's data")
	fmt.Println("  --week         Last 7 days")
	fmt.Println("  --month        Last 30 days")
	fmt.Println("  --all          All time")
	fmt.Println("  YYYY-MM-DD     Specific date")
	fmt.Println()
	fmt.Println("Run without arguments for interactive menu.")
}

func selfUpdate() {
	fmt.Printf("Updating claude-stats (current: %s)...\n\n", version)

	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		// PowerShell: download and run install.ps1
		script := `irm https://raw.githubusercontent.com/AgusRdz/claude-stats/main/install.ps1 | iex`
		cmd = exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script)
	default:
		// sh: download and run install.sh
		script := `curl -fsSL https://raw.githubusercontent.com/AgusRdz/claude-stats/main/install.sh | sh`
		cmd = exec.Command("sh", "-c", script)
	}

	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "\nupdate failed: %v\n\n", err)
		fmt.Fprintln(os.Stderr, "Manual install:")
		if runtime.GOOS == "windows" {
			fmt.Fprintln(os.Stderr, "  irm https://raw.githubusercontent.com/AgusRdz/claude-stats/main/install.ps1 | iex")
		} else {
			fmt.Fprintln(os.Stderr, "  curl -fsSL https://raw.githubusercontent.com/AgusRdz/claude-stats/main/install.sh | sh")
		}
		os.Exit(1)
	}
}

func main() {
	// Disable ANSI on Windows if not in a capable terminal
	if runtime.GOOS == "windows" {
		// Colors work fine in Windows Terminal / Git Bash; keep them
	}

	if len(os.Args) < 2 {
		interactiveMenu()
		return
	}

	subcmd := os.Args[1]
	remaining := os.Args[2:]

	switch subcmd {
	case "help", "--help", "-h":
		printHelp()
	case "version", "--version", "-v":
		fmt.Printf("claude-stats %s\n", version)
	case "self-update", "update":
		selfUpdate()
	default:
		for _, c := range allCommands {
			if c.cmd == subcmd {
				c.fn(remaining)
				return
			}
		}
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n", subcmd)
		var names []string
		for _, c := range allCommands {
			names = append(names, c.cmd)
		}
		fmt.Fprintf(os.Stderr, "Available: %s\n", strings.Join(names, ", "))
		os.Exit(1)
	}
}
