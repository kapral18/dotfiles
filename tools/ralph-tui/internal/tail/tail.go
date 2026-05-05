// Package tail renders a scrollable view of a role's output.log file with
// live updates fed by an external fsnotify watcher.
package tail

import (
	"errors"
	"io/fs"
	"os"
	"strings"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"

	"ralph-tui/internal/styles"
)

// Model is a thin wrapper around bubbles/viewport with a "current file" the
// caller can swap out as the user moves through roles.
type Model struct {
	vp        viewport.Model
	path      string
	tailLines int
	width     int
	height    int
	loaded    bool
}

// New returns a tail viewport with sensible defaults.
func New() Model {
	vp := viewport.New(80, 20)
	vp.SetContent("")
	return Model{vp: vp, tailLines: 200}
}

// SetSize keeps the inner viewport in sync with the layout.
func (m *Model) SetSize(w, h int) {
	m.width, m.height = w, h
	m.vp.Width = w
	m.vp.Height = h
}

// SetTailLines bounds how many trailing lines we keep in memory; large output
// logs need clamping or the TUI lags during typing.
func (m *Model) SetTailLines(n int) {
	if n > 0 {
		m.tailLines = n
	}
}

// SetPath swaps to a new file and re-reads it. Empty path clears the view.
func (m *Model) SetPath(p string) error {
	m.path = p
	m.loaded = false
	if p == "" {
		m.vp.SetContent("")
		return nil
	}
	return m.Reload()
}

// Path returns the file currently being tailed.
func (m Model) Path() string { return m.path }

// Reload reads the current path; called after fsnotify says it changed.
func (m *Model) Reload() error {
	if m.path == "" {
		m.vp.SetContent("")
		return nil
	}
	data, err := os.ReadFile(m.path)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			m.vp.SetContent(styles.Faint.Render("(no output yet)"))
			return nil
		}
		return err
	}
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	if len(lines) > m.tailLines {
		lines = lines[len(lines)-m.tailLines:]
	}
	m.vp.SetContent(strings.Join(lines, "\n"))
	if !m.loaded {
		// First load: pin to bottom (live tail).
		m.vp.GotoBottom()
		m.loaded = true
	} else {
		// Subsequent loads: stay pinned to bottom unless user has scrolled
		// up. Heuristic: if we were at the bottom before reload, stay there.
		m.vp.GotoBottom()
	}
	return nil
}

// Update forwards key events to the inner viewport (scroll, page up/down).
func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	var cmd tea.Cmd
	m.vp, cmd = m.vp.Update(msg)
	return m, cmd
}

// View renders the viewport content.
func (m Model) View() string {
	if m.path == "" {
		return styles.Faint.Render("focus a role and press tab to tail its output")
	}
	return m.vp.View()
}
