// Package detail renders the right pane: the selected run's header,
// iteration history, and roles table.
package detail

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"ralph-tui/internal/state"
	"ralph-tui/internal/styles"
)

// Model holds the currently displayed run and the role cursor for
// drill-into-tail navigation.
type Model struct {
	Run       state.Run
	HasRun    bool
	roleNames []string
	cursor    int
	width     int
	height    int
}

// New returns an empty model.
func New() Model { return Model{} }

// SetRun replaces the active run and refreshes the role index.
func (m *Model) SetRun(r state.Run) {
	m.Run = r
	m.HasRun = true
	m.roleNames = state.SortedRoleNames(r.Roles)
	if m.cursor >= len(m.roleNames) {
		m.cursor = max(0, len(m.roleNames)-1)
	}
}

// Clear drops the active run.
func (m *Model) Clear() {
	m.Run = state.Run{}
	m.HasRun = false
	m.roleNames = nil
	m.cursor = 0
}

// SetSize updates the render area.
func (m *Model) SetSize(w, h int) {
	m.width, m.height = w, h
}

// SelectedRole returns the role currently cursor-targeted, or "" if none.
func (m Model) SelectedRole() string {
	if m.cursor < 0 || m.cursor >= len(m.roleNames) {
		return ""
	}
	return m.roleNames[m.cursor]
}

// SelectRole points the cursor at the named role. No-op when the role is
// not in the current run. Used when the operator drills into a grid-layout
// cell so the detail-layout tail snaps to that role's output.log.
func (m *Model) SelectRole(name string) {
	for i, n := range m.roleNames {
		if n == name {
			m.cursor = i
			return
		}
	}
}

// MoveCursor mutates the role cursor by delta, clamped.
func (m *Model) MoveCursor(delta int) {
	if len(m.roleNames) == 0 {
		m.cursor = 0
		return
	}
	m.cursor += delta
	if m.cursor < 0 {
		m.cursor = 0
	}
	if m.cursor >= len(m.roleNames) {
		m.cursor = len(m.roleNames) - 1
	}
}

// View renders the header, optional intent surfaces (awaiting-human banner,
// workflow + summary), iterations, and roles table.
func (m Model) View() string {
	if !m.HasRun {
		return styles.Faint.Render("no run selected")
	}
	r := m.Run
	var b strings.Builder

	header := []string{
		styles.Title.Render(r.ID),
		fmt.Sprintf("Goal: %s", or(r.Goal, "-")),
	}
	if r.Workspace != "" {
		header = append(header, fmt.Sprintf("Workspace: %s", r.Workspace))
	}
	if r.Workflow != "" {
		header = append(header, lipgloss.NewStyle().Foreground(styles.Info).Render("Workflow: "+r.Workflow))
	}
	if r.BlockReason != "" {
		header = append(header, lipgloss.NewStyle().Foreground(styles.Warn).Render("Block: "+r.BlockReason))
	}
	header = append(header,
		fmt.Sprintf(
			"Status: %s  Phase: %s  Validation: %s  Iters: %d  SpecSeq: %d",
			styles.StatusBadge(r.Status),
			r.Phase,
			styles.StatusBadge(r.Validation),
			len(r.Iterations),
			r.SpecSeq,
		))
	if r.Runner != nil {
		alive := "dead"
		if r.Runner.Alive {
			alive = "alive"
		}
		header = append(header, fmt.Sprintf(
			"Runner: pid=%d host=%s heartbeat=%s status=%s",
			r.Runner.PID, or(r.Runner.Host, "-"), or(r.Runner.HeartbeatAt, "-"), alive,
		))
	}
	if r.ReplanQueued {
		header = append(header, lipgloss.NewStyle().Foreground(styles.Warn).Render("replan queued"))
	}
	b.WriteString(strings.Join(header, "\n"))

	if r.AwaitingHuman() {
		b.WriteString("\n\n")
		b.WriteString(awaitingHumanBanner(r))
	}

	if open := r.OpenQuestions(); len(open) > 0 {
		b.WriteString("\n")
		b.WriteString(styles.Section.Render(fmt.Sprintf("Open questions (%d)", len(open))))
		b.WriteString("\n")
		for _, q := range open {
			b.WriteString(formatQuestion(q))
			b.WriteByte('\n')
		}
	}

	if r.SummaryAvailable() {
		b.WriteString("\n")
		b.WriteString(styles.Section.Render("Summary"))
		b.WriteString("\n")
		b.WriteString("  ")
		b.WriteString(lipgloss.NewStyle().Foreground(styles.OK).Render(r.SummaryPath))
		b.WriteByte('\n')
	}

	if len(r.Iterations) > 0 {
		b.WriteString("\n")
		b.WriteString(styles.Section.Render("Iterations"))
		b.WriteString("\n")
		for _, it := range r.Iterations {
			marker := styles.PhaseGlyph(it.Phase)
			verdict := or(it.Verdict, "-")
			line := fmt.Sprintf(
				"  %s iter %d  phase=%-10s  verdict=%s  task=%s",
				marker, it.N, it.Phase, styles.StatusBadge(verdict), truncate(it.Task, 40),
			)
			b.WriteString(line)
			b.WriteByte('\n')
		}
	}

	if len(m.roleNames) > 0 {
		b.WriteString("\n")
		b.WriteString(styles.Section.Render("Roles"))
		b.WriteString("\n")
		for i, name := range m.roleNames {
			role := r.Roles[name]
			cursor := "  "
			rowStyle := lipgloss.NewStyle()
			if i == m.cursor {
				cursor = "> "
				rowStyle = rowStyle.Bold(true)
			}
			validation := or(role.ValidationStatus, role.Status)
			control := or(role.ControlState, "automated")
			pane := "-"
			if role.Tmux != nil && role.Tmux.Pane != "" {
				pane = role.Tmux.Pane
			}
			row := fmt.Sprintf(
				"%s%-15s  %s  ctrl=%-15s  pane=%-12s",
				cursor, name, styles.StatusBadge(validation), control, pane,
			)
			b.WriteString(rowStyle.Render(row))
			b.WriteByte('\n')
		}
	}
	return b.String()
}

func awaitingHumanBanner(r state.Run) string {
	open := r.OpenQuestions()
	by := r.AwaitingRole
	if by == "" {
		by = "orchestrator"
	}
	body := fmt.Sprintf(
		"AWAITING HUMAN · %d open question(s) · asked by %s · press 'A' to answer",
		len(open), by,
	)
	return lipgloss.NewStyle().
		Foreground(styles.Foreground).
		Background(styles.Warn).
		Bold(true).
		Padding(0, 1).
		Render(body)
}

func formatQuestion(q state.Question) string {
	role := lipgloss.NewStyle().Foreground(styles.Accent).Bold(true).Render("[" + q.Role + "]")
	id := lipgloss.NewStyle().Foreground(styles.Subtle).Render("(" + q.ID + ")")
	text := lipgloss.NewStyle().Foreground(styles.Foreground).Render(truncate(q.Text, 80))
	return "  " + role + " " + id + " " + text
}

func or(a, b string) string {
	if a == "" {
		return b
	}
	return a
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	if n <= 1 {
		return "…"
	}
	return s[:n-1] + "…"
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
