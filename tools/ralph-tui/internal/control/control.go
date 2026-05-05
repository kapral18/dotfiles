// Package control provides a modal listing the actions a user can take on
// a selected run / role: takeover, dirty, resume, auto, kill, rm, etc.
package control

import (
	"strings"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/styles"
)

// Action identifies a single menu item; matches `,ralph` subcommand vocabulary.
type Action string

const (
	ActionVerify   Action = "verify"
	ActionTakeover Action = "takeover"
	ActionDirty    Action = "dirty"
	ActionResume   Action = "resume"
	ActionAuto     Action = "auto"
	ActionKill     Action = "kill"
	ActionRemove   Action = "rm"
	ActionReplan   Action = "replan"
	ActionResumeRunner Action = "resume_runner"
)

// Item bundles a label and the action it triggers.
type Item struct {
	Label  string
	Action Action
	Help   string
}

// Menu is a vertical list with a cursor.
type Menu struct {
	items  []Item
	cursor int
	title  string
}

// New returns a menu with the run-scoped action set: each item maps to a
// `,ralph` subcommand the parent will dispatch.
func New(title string, runScoped, hasRole bool) Menu {
	items := []Item{
		{"Verify", ActionVerify, "re-run validation chain"},
		{"Resume runner", ActionResumeRunner, "re-launch runner if it died"},
		{"Replan", ActionReplan, "queue a replan; runner consumes next loop"},
		{"Kill", ActionKill, "Ctrl-C role panes and mark run killed"},
		{"Remove", ActionRemove, "archive run dir; drop ai-kb capsules"},
	}
	if hasRole {
		items = append(items,
			Item{"Takeover", ActionTakeover, "manual control of this role"},
			Item{"Dirty", ActionDirty, "mark role dirty (re-validate later)"},
			Item{"Resume role", ActionResume, "hand control back to the orchestrator"},
			Item{"Auto", ActionAuto, "force role back to automated"},
		)
	}
	return Menu{items: items, title: title}
}

// Update handles cursor + selection key events.
//
// Returns:
//   - new menu
//   - selected: non-nil when the user pressed enter on an item
//   - cancel: true if the user pressed esc
func (m Menu) Update(msg tea.Msg) (Menu, *Item, bool) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch {
		case key.Matches(msg, KeyCancel):
			return m, nil, true
		case key.Matches(msg, KeyDown):
			if m.cursor < len(m.items)-1 {
				m.cursor++
			}
		case key.Matches(msg, KeyUp):
			if m.cursor > 0 {
				m.cursor--
			}
		case key.Matches(msg, KeySubmit):
			if m.cursor >= 0 && m.cursor < len(m.items) {
				it := m.items[m.cursor]
				return m, &it, false
			}
		}
	}
	return m, nil, false
}

// View renders the menu.
func (m Menu) View() string {
	var b strings.Builder
	b.WriteString(styles.Title.Render(m.title))
	b.WriteByte('\n')
	for i, it := range m.items {
		cursor := "  "
		style := lipgloss.NewStyle()
		if i == m.cursor {
			cursor = "> "
			style = style.Foreground(styles.Accent).Bold(true)
		}
		row := cursor + it.Label
		if it.Help != "" {
			row += "  " + styles.Faint.Render("— "+it.Help)
		}
		b.WriteString(style.Render(row))
		b.WriteByte('\n')
	}
	return b.String()
}

var (
	KeyUp     = key.NewBinding(key.WithKeys("up", "k"))
	KeyDown   = key.NewBinding(key.WithKeys("down", "j"))
	KeySubmit = key.NewBinding(key.WithKeys("enter"))
	KeyCancel = key.NewBinding(key.WithKeys("esc", "ctrl+c", "q"))
)
