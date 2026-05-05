// Package help renders an opaque help overlay listing every keybinding
// across the focused panes plus global actions.
package help

import (
	"strings"

	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/styles"
)

// Section is one column of help entries.
type Section struct {
	Title string
	Rows  [][2]string // (key, description)
}

// Overlay returns a centered help block.
func Overlay(width int) string {
	sections := []Section{
		{Title: "Navigation", Rows: [][2]string{
			{"↑/k ↓/j", "move within pane"},
			{"tab", "next pane"},
			{"shift+tab", "previous pane"},
			{"enter", "zoom focused pane (esc to zoom out)"},
			{"/", "filter runs (typing shadows global keys)"},
			{"g / G", "first / last (runs pane only)"},
			{"h/j/k/l", "navigate cells in grid layout"},
		}},
		{Title: "Actions", Rows: [][2]string{
			{"n", "new run (goal + workflow modal)"},
			{"a", "attach to selected run/role (exits to tmux)"},
			{"p", "preview pane (read-only modal; A to popup-attach)"},
			{"A", "answer open questions (awaiting_human)"},
			{"v", "verify selected run"},
			{"c", "control menu (kill / takeover / replan / resume)"},
			{"R", "resume runner if it died"},
			{"P", "queue a replan"},
			{"x", "kill selected (run or role)"},
			{"X", "remove selected run"},
		}},
		{Title: "Other", Rows: [][2]string{
			{"r", "manual refresh"},
			{"s", "cycle sort: need / recent"},
			{"S", "cycle activity drawer: off / small / large"},
			{"K", "browse the AI knowledge base"},
			{"1/2/3", "layout: detail / grid / zoom"},
			{"?", "toggle this help"},
			{"q / Ctrl-c", "quit"},
		}},
	}

	cols := make([]string, 0, len(sections))
	for _, s := range sections {
		var b strings.Builder
		b.WriteString(styles.Title.Render(s.Title))
		b.WriteByte('\n')
		for _, kv := range s.Rows {
			keyCol := lipgloss.NewStyle().Foreground(styles.Accent).Bold(true).Width(12).Render(kv[0])
			descCol := styles.Subdued.Render(kv[1])
			b.WriteString(keyCol + "  " + descCol + "\n")
		}
		cols = append(cols, lipgloss.NewStyle().Padding(0, 2).Render(b.String()))
	}
	body := lipgloss.JoinHorizontal(lipgloss.Top, cols...)
	if width > 4 {
		body = lipgloss.NewStyle().MaxWidth(width - 4).Render(body)
	}
	frame := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder(), true).
		BorderForeground(styles.Accent).
		Padding(1, 2).
		Render(body)
	return frame
}
