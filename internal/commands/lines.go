package commands

import (
	"fmt"
	"sort"

	"github.com/Andrevops/claude-stats/internal/dates"
	"github.com/Andrevops/claude-stats/internal/format"
	"github.com/Andrevops/claude-stats/internal/projects"
	"github.com/Andrevops/claude-stats/internal/session"
)

type lineStat struct {
	written, added, removed int
	files                   map[string]bool
}

type fileLineStat struct {
	written, added, removed, ops int
}

func Lines(args []string) {
	targetDates, label := dates.ParseArgs(args)
	if label == "" {
		return
	}
	files := session.Find(targetDates, false)
	if len(files) == 0 {
		fmt.Printf("\n  No sessions found for %s\n", label)
		return
	}

	totalWrites, totalEdits := 0, 0
	totalWritten, totalAdded, totalRemoved := 0, 0, 0

	extStats := map[string]*lineStat{}
	projStats := map[string]*struct {
		lineStat
		writes, edits int
	}{}
	fileStats := map[string]*fileLineStat{}
	allFiles := map[string]bool{}

	for _, f := range files {
		projName := projects.ExtractProject(f)
		session.ScanLines(f, func(line session.LogLine) {
			if line.Type != "assistant" {
				return
			}
			msg, ok := session.ParseAssistantMsg(line.Message)
			if !ok {
				return
			}
			for _, b := range msg.Content {
				if b.Type != "tool_use" {
					continue
				}
				switch b.Name {
				case "Write":
					wi := session.ParseWriteInput(b.Input)
					lines := session.CountLines(wi.Content)
					ext := projects.GetExt(wi.FilePath)
					short := projects.ShortenPath(wi.FilePath)

					totalWrites++
					totalWritten += lines
					allFiles[wi.FilePath] = true

					ensureLineStat(extStats, ext).written += lines
					ensureLineStat(extStats, ext).files[wi.FilePath] = true

					ensureProjStat(projStats, projName).written += lines
					ensureProjStat(projStats, projName).writes++
					ensureProjStat(projStats, projName).files[wi.FilePath] = true

					ensureFileStat(fileStats, short).written += lines
					ensureFileStat(fileStats, short).ops++

				case "Edit":
					ei := session.ParseEditInput(b.Input)
					oldLines := session.CountLines(ei.OldString)
					newLines := session.CountLines(ei.NewString)
					ext := projects.GetExt(ei.FilePath)
					short := projects.ShortenPath(ei.FilePath)

					totalEdits++
					totalAdded += newLines
					totalRemoved += oldLines
					allFiles[ei.FilePath] = true

					ensureLineStat(extStats, ext).added += newLines
					ensureLineStat(extStats, ext).removed += oldLines
					ensureLineStat(extStats, ext).files[ei.FilePath] = true

					ensureProjStat(projStats, projName).added += newLines
					ensureProjStat(projStats, projName).removed += oldLines
					ensureProjStat(projStats, projName).edits++
					ensureProjStat(projStats, projName).files[ei.FilePath] = true

					ensureFileStat(fileStats, short).added += newLines
					ensureFileStat(fileStats, short).removed += oldLines
					ensureFileStat(fileStats, short).ops++
				}
			}
		})
	}

	totalOps := totalWrites + totalEdits
	if totalOps == 0 {
		fmt.Printf("\n  No Write/Edit operations found for %s\n", label)
		return
	}

	net := totalWritten + totalAdded - totalRemoved
	throughput := totalWritten + totalAdded + totalRemoved

	format.Header(fmt.Sprintf("📝  CLAUDE CODE LINES OF CODE — %s", label), "═")
	fmt.Printf(`
  Operations:    %d writes + %d edits = %d total
  Files touched: %d

  ┌──────────────────────────────────────┐
  │  Lines written (new files):  %8s │
  │  Lines added (edits):        %8s │
  │  Lines removed (edits):      %8s │
  │  ──────────────────────────────────  │
  │  NET LINES:                  %8s │
  │  TOTAL THROUGHPUT:           %8s │
  └──────────────────────────────────────┘`+"\n",
		totalWrites, totalEdits, totalOps,
		len(allFiles),
		format.Fmt(totalWritten),
		format.Fmt(totalAdded),
		format.Fmt(totalRemoved),
		format.Fmt(net),
		format.Fmt(throughput),
	)

	// ── By Extension
	format.Header("📄  BY FILE EXTENSION", "─")
	type extEntry struct {
		ext string
		s   *lineStat
	}
	var extList []extEntry
	for ext, s := range extStats {
		extList = append(extList, extEntry{ext, s})
	}
	sort.Slice(extList, func(i, j int) bool {
		ti := extList[i].s.written + extList[i].s.added
		tj := extList[j].s.written + extList[j].s.added
		return ti > tj
	})
	if len(extList) > 15 {
		extList = extList[:15]
	}
	maxExt := 0
	if len(extList) > 0 {
		maxExt = extList[0].s.written + extList[0].s.added
	}

	fmt.Printf("\n  %-10s %8s %8s %8s %8s %5s  %s\n",
		"Ext", "Written", "Added", "Removed", "Net", "Files", "")
	fmt.Printf("  %s %s %s %s %s %s  %s\n",
		repeat("─", 10), repeat("─", 8), repeat("─", 8), repeat("─", 8), repeat("─", 8), repeat("─", 5), repeat("─", 12))

	for _, e := range extList {
		extNet := e.s.written + e.s.added - e.s.removed
		total := e.s.written + e.s.added
		sign := "+"
		if extNet < 0 {
			sign = ""
		}
		fmt.Printf("  %-10s %8d %8d %8d %s%7d %5d  %s\n",
			e.ext, e.s.written, e.s.added, e.s.removed,
			sign, extNet, len(e.s.files),
			format.Bar(float64(total), float64(maxExt), 12))
	}

	// ── By Project
	format.Header("📁  BY PROJECT", "─")
	type projEntry struct {
		name  string
		s     *lineStat
		w, ed int
	}
	var projList []projEntry
	for name, p := range projStats {
		projList = append(projList, projEntry{name, &p.lineStat, p.writes, p.edits})
	}
	sort.Slice(projList, func(i, j int) bool {
		ti := projList[i].s.written + projList[i].s.added
		tj := projList[j].s.written + projList[j].s.added
		return ti > tj
	})
	maxProj := 0
	if len(projList) > 0 {
		maxProj = projList[0].s.written + projList[0].s.added
	}

	fmt.Printf("\n  %-40s %8s %8s %8s %7s  %s\n",
		"Project", "Written", "Added", "Removed", "Net", "")
	fmt.Printf("  %s %s %s %s %s  %s\n",
		repeat("─", 40), repeat("─", 8), repeat("─", 8), repeat("─", 8), repeat("─", 7), repeat("─", 10))

	for _, e := range projList {
		projNet := e.s.written + e.s.added - e.s.removed
		total := e.s.written + e.s.added
		sign := "+"
		if projNet < 0 {
			sign = ""
		}
		name := truncate(e.name, 38)
		fmt.Printf("  %-40s %8d %8d %8d %s%6d  %s\n",
			name, e.s.written, e.s.added, e.s.removed,
			sign, projNet,
			format.Bar(float64(total), float64(maxProj), 10))
	}

	// ── Top Files (most operations)
	format.Header("🔥  TOP FILES (most operations)", "─")
	type fileEntry struct {
		path string
		s    *fileLineStat
	}
	var fileList []fileEntry
	for path, s := range fileStats {
		fileList = append(fileList, fileEntry{path, s})
	}
	sort.Slice(fileList, func(i, j int) bool { return fileList[i].s.ops > fileList[j].s.ops })
	if len(fileList) > 20 {
		fileList = fileList[:20]
	}

	fmt.Printf("\n  %4s %8s %7s %7s  File\n", "Ops", "Written", "+Lines", "-Lines")
	fmt.Printf("  %s %s %s %s  %s\n",
		repeat("─", 4), repeat("─", 8), repeat("─", 7), repeat("─", 7), repeat("─", 45))
	for _, e := range fileList {
		display := e.path
		if len(display) > 50 {
			display = "..." + display[len(display)-47:]
		}
		fmt.Printf("  %4d %8d %7d %7d  %s\n",
			e.s.ops, e.s.written, e.s.added, e.s.removed, display)
	}

	// ── Top Files (most lines)
	format.Header("📏  TOP FILES (most lines written/added)", "─")
	sort.Slice(fileList, func(i, j int) bool {
		ti := fileList[i].s.written + fileList[i].s.added
		tj := fileList[j].s.written + fileList[j].s.added
		return ti > tj
	})
	topFiles := fileList
	if len(topFiles) > 15 {
		topFiles = topFiles[:15]
	}
	maxLines := 0
	if len(topFiles) > 0 {
		maxLines = topFiles[0].s.written + topFiles[0].s.added
	}

	fmt.Printf("\n  %7s %10s  File\n", "Lines", "")
	fmt.Printf("  %s %s  %s\n", repeat("─", 7), repeat("─", 10), repeat("─", 45))
	for _, e := range topFiles {
		total := e.s.written + e.s.added
		display := e.path
		if len(display) > 50 {
			display = "..." + display[len(display)-47:]
		}
		fmt.Printf("  %7d %s  %s\n",
			total, format.Bar(float64(total), float64(maxLines), 10), display)
	}

	// ── Insights
	format.Header("💡  INSIGHTS", "─")
	var insights []string
	if totalWritten > totalAdded {
		pct := float64(totalWritten) / float64(totalWritten+totalAdded) * 100
		insights = append(insights, fmt.Sprintf("Mostly new files: %.0f%% of lines are from Write (new files/rewrites).", pct))
	} else if totalAdded > 0 {
		pct := float64(totalAdded) / float64(totalWritten+totalAdded) * 100
		insights = append(insights, fmt.Sprintf("Mostly edits: %.0f%% of lines are from Edit operations.", pct))
	}
	if totalRemoved > 0 {
		ratio := float64(totalWritten+totalAdded) / float64(totalRemoved)
		desc := "growing codebase"
		if ratio <= 2 {
			desc = "healthy refactoring"
		}
		if ratio <= 1 {
			desc = "net reduction"
		}
		insights = append(insights, fmt.Sprintf("Add/remove ratio: %.1f:1 — %s.", ratio, desc))
	}
	if len(fileList) > 0 {
		tf := fileList[0]
		insights = append(insights, fmt.Sprintf("Most touched file: %s (%d operations)", truncate(tf.path, 40), tf.s.ops))
	}
	if len(extList) > 0 {
		te := extList[0]
		te_total := te.s.written + te.s.added
		all_total := totalWritten + totalAdded
		if all_total > 0 {
			insights = append(insights, fmt.Sprintf("Top language: %s (%.0f%% of lines)", te.ext, float64(te_total)/float64(all_total)*100))
		}
	}

	for i, ins := range insights {
		fmt.Printf("  %d. %s\n", i+1, ins)
	}
	fmt.Println()
}

func ensureLineStat(m map[string]*lineStat, key string) *lineStat {
	if _, ok := m[key]; !ok {
		m[key] = &lineStat{files: map[string]bool{}}
	}
	return m[key]
}

func ensureProjStat(m map[string]*struct {
	lineStat
	writes, edits int
}, key string) *struct {
	lineStat
	writes, edits int
} {
	if _, ok := m[key]; !ok {
		m[key] = &struct {
			lineStat
			writes, edits int
		}{lineStat: lineStat{files: map[string]bool{}}}
	}
	return m[key]
}

func ensureFileStat(m map[string]*fileLineStat, key string) *fileLineStat {
	if _, ok := m[key]; !ok {
		m[key] = &fileLineStat{}
	}
	return m[key]
}
