// Package styles holds shared lipgloss styles so every component renders with
// the same visual language.
package styles

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Colors used across the TUI. They map to ANSI 256 indices so the output stays
// readable on terminals that have not been configured with truecolor.
var (
	Foreground   = lipgloss.AdaptiveColor{Light: "#1d1d1d", Dark: "#dbdbdb"}
	Subtle       = lipgloss.Color("244")
	Border       = lipgloss.Color("245") // bright enough to see on dark terminals
	Accent       = lipgloss.Color("141") // violet
	AccentBright = lipgloss.Color("213")
	OK           = lipgloss.Color("42")  // green
	Warn         = lipgloss.Color("214") // amber
	Bad          = lipgloss.Color("196") // red
	Info         = lipgloss.Color("111") // blue
)

// Common reusable styles.
var (
	Title = lipgloss.NewStyle().
		Bold(true).
		Foreground(AccentBright).
		Padding(0, 1)

	Section = lipgloss.NewStyle().
		Foreground(Accent).
		Bold(true).
		MarginTop(1)

	Subdued = lipgloss.NewStyle().
		Foreground(Subtle)

	Faint = lipgloss.NewStyle().
		Foreground(Subtle).
		Italic(true)

	BorderActive = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder(), true).
		BorderForeground(Accent).
		Padding(0, 1)

	BorderInactive = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder(), true).
		BorderForeground(Border).
		Padding(0, 1)

	StatusBar = lipgloss.NewStyle().
		Foreground(Foreground).
		Background(lipgloss.Color("236")).
		Padding(0, 1)

	Toast = lipgloss.NewStyle().
		Foreground(Foreground).
		Background(lipgloss.Color("237")).
		Padding(0, 2).
		Margin(0, 1).
		Border(lipgloss.NormalBorder(), true).
		BorderForeground(Accent)
)

// Pane wraps content in either an active or inactive bordered box.
//
// Used by the App to highlight the currently focused pane. Content longer
// than the available pane height is clipped (top-aligned) rather than
// allowed to overflow — overflow would push the bottom panes and the
// status bar below the terminal's last row, scrolling the topmost row's
// pane border off-screen.
func Pane(content string, focused bool, width, height int) string {
	style := BorderInactive
	if focused {
		style = BorderActive
	}
	innerW, innerH := width-2, height-2
	if innerW > 0 {
		style = style.Width(innerW)
	}
	if innerH > 0 {
		style = style.Height(innerH).MaxHeight(height)
		content = clampLines(content, innerH)
	}
	return style.Render(content)
}

// clampLines drops lines past the nth so the rendered pane content never
// exceeds its allocated height. We pre-clamp before lipgloss renders so
// the bordered Pane fits exactly its height arg.
func clampLines(s string, n int) string {
	if n <= 0 {
		return ""
	}
	lines := strings.Split(s, "\n")
	if len(lines) <= n {
		return s
	}
	return strings.Join(lines[:n], "\n")
}

// StatusColor maps Ralph status / validation strings to the visual palette.
func StatusColor(status string) lipgloss.Color {
	switch strings.ToLower(status) {
	case "passed", "completed", "automated", "pass":
		return OK
	case "needs_verification", "needs_human", "manual_control", "dirty_control", "resume_requested", "running":
		return Warn
	case "failed", "killed", "fail", "block":
		return Bad
	case "planned", "rereviewing", "reviewing", "executing", "planning", "replanning":
		return Info
	default:
		return Subtle
	}
}

// StatusBadge returns a colored single-line label for a status.
func StatusBadge(status string) string {
	c := StatusColor(status)
	return lipgloss.NewStyle().
		Foreground(c).
		Bold(true).
		Render(status)
}

// PhaseGlyph returns a 1-char visual marker for a phase.
func PhaseGlyph(phase string) string {
	switch phase {
	case "done", "completed":
		return "v"
	case "failed", "killed":
		return "x"
	case "blocked", "needs_human":
		return "!"
	case "running", "executing", "reviewing", "rereviewing", "planning", "replanning":
		return "o"
	case "planned":
		return "."
	default:
		return "?"
	}
}
