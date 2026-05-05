// Package kb implements the in-TUI Knowledge Base browser modal.
//
// The modal lets the operator search the AI KB at any time without
// leaving the dashboard. It shells out to `,ai-kb search ... --json`
// (the same surface roles use mid-run), parses the response, and
// renders a hit list with a detail pane showing the body of the
// selected capsule. Layout:
//
//	┌─ KB browser ────────────────────────────────────┐
//	│ search: <textinput>                              │
//	│                                                  │
//	│  ▶ 0 [gotcha/project] JWT signature trap         │
//	│    1 [fact/universal] Manifest schema layout     │
//	│    2 [pattern/domain]  Hybrid retrieval shape    │
//	│  ────────────────────────────────────────        │
//	│ Selected hit body:                               │
//	│ <body of focused hit, wrapped, styled>           │
//	└──────────────────────────────────────────────────┘
//
// The modal is presentational: it doesn't talk to the KB itself.
// Search dispatch is initiated by the caller via cmds.KBSearchCmd
// when the user presses Enter on the textinput; the caller hands the
// resulting cmds.KBSearchMsg back to Modal.SetHits before re-rendering.
package kb

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/cmds"
	"ralph-tui/internal/styles"
)

// Modal is the KB browser surface.
type Modal struct {
	input   textinput.Model
	hits    []cmds.KBHit
	cursor  int
	err     error
	width   int
	loading bool
	last    string // last submitted query, for re-display when search returns
}

// New builds an empty modal with the textinput focused.
func New() Modal {
	ti := textinput.New()
	ti.Placeholder = "search the AI KB (Enter=search · ↑↓ select · esc/q close)"
	ti.CharLimit = 256
	ti.Width = 50
	ti.Focus()
	return Modal{input: ti}
}

// SetWidth lets the parent App keep the modal in sync with the terminal width
// so the box doesn't run off the edge on small screens. The caller passes
// `terminal_width - chrome` so the modal can compute its own internal
// row width.
func (m *Modal) SetWidth(w int) {
	if w < 30 {
		w = 30
	}
	m.width = w
	innerWidth := w - 4 // box padding
	m.input.Width = innerWidth - 8
}

// SetHits feeds the result of a cmds.KBSearchCmd back into the modal.
//
// The caller invokes this after KBSearchMsg arrives. We reset the
// cursor to 0 every time so the user is always reading the top-rank
// hit after a new search.
func (m *Modal) SetHits(msg cmds.KBSearchMsg) {
	m.hits = msg.Hits
	m.err = msg.Err
	m.cursor = 0
	m.loading = false
}

// MarkLoading tells the modal that a query was just dispatched and
// it should show a spinner / placeholder until SetHits arrives. The
// app calls this immediately after returning the KBSearchCmd from
// Update.
func (m *Modal) MarkLoading(query string) {
	m.loading = true
	m.last = query
	m.err = nil
}

// Init satisfies the bubbletea.Model contract; the textinput's own
// internal blink cmd is the only thing we need to start.
func (m Modal) Init() tea.Cmd { return textinput.Blink }

// Update handles key events for the modal. The caller routes to this
// method only when the modal is active.
//
// Returns:
//   - cmd:    bubbletea command (textinput animation, search dispatch)
//   - submit: a non-empty query string when the user pressed Enter on
//     a non-empty input. The caller turns that into KBSearchCmd.
//   - close:  true when the user pressed esc/q AND focus is on the
//     textinput; the caller closes the modal.
func (m *Modal) Update(msg tea.Msg) (tea.Cmd, string, bool) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch {
		case key.Matches(msg, keyClose):
			// `q` is also a literal character roles might want to type
			// in a query. Only treat `q`/`esc` as close when the input
			// has nothing in it and isn't currently being edited.
			if msg.String() == "q" && m.input.Value() != "" {
				break
			}
			return nil, "", true
		case key.Matches(msg, keySubmit):
			q := strings.TrimSpace(m.input.Value())
			if q == "" {
				return nil, "", false
			}
			return nil, q, false
		case key.Matches(msg, keyDown):
			if len(m.hits) > 0 && m.cursor < len(m.hits)-1 {
				m.cursor++
			}
			return nil, "", false
		case key.Matches(msg, keyUp):
			if m.cursor > 0 {
				m.cursor--
			}
			return nil, "", false
		}
	}
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	return cmd, "", false
}

// View renders the modal box. The parent App wraps the returned string
// in a centerOverlay shell, so this function returns plain content
// (no border / no width hard-cap of its own).
func (m Modal) View() string {
	w := m.width
	if w < 50 {
		w = 50
	}

	header := styles.Title.Render("KB browser")
	hint := styles.Faint.Render("type query · Enter searches · ↑↓ select · esc/q closes")
	queryRow := "search: " + m.input.View()

	var resultsBlock string
	switch {
	case m.err != nil:
		resultsBlock = lipgloss.NewStyle().Foreground(styles.Bad).Render(
			fmt.Sprintf("error: %s", m.err.Error()),
		)
	case m.loading:
		resultsBlock = styles.Faint.Render(fmt.Sprintf("searching for %q…", m.last))
	case len(m.hits) == 0 && m.last != "":
		resultsBlock = styles.Faint.Render(fmt.Sprintf("no hits for %q", m.last))
	case len(m.hits) == 0:
		resultsBlock = styles.Faint.Render(
			"hits are filtered to non-superseded capsules and ranked\n" +
				"by hybrid lexical+semantic retrieval (RRF + MMR).",
		)
	default:
		resultsBlock = m.renderHits(w - 4)
	}

	rows := []string{
		header,
		hint,
		"",
		queryRow,
		"",
		resultsBlock,
	}
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

func (m Modal) renderHits(width int) string {
	if width < 30 {
		width = 30
	}
	listLines := make([]string, 0, len(m.hits)+3)
	for i, h := range m.hits {
		marker := "  "
		row := lipgloss.NewStyle()
		if i == m.cursor {
			marker = "▶ "
			row = row.Foreground(styles.Accent)
		}
		title := h.Title
		// Cap title length so each row stays inside the modal.
		maxTitle := width - 30
		if maxTitle < 16 {
			maxTitle = 16
		}
		if len(title) > maxTitle {
			title = title[:maxTitle-1] + "…"
		}
		listLines = append(listLines, row.Render(fmt.Sprintf(
			"%s%2d  [%s/%s]  %s  %s",
			marker, i, h.Kind, h.Scope,
			styles.Faint.Render(fmt.Sprintf("rrf=%.4f", h.RRFScore)),
			title,
		)))
	}
	listBlock := strings.Join(listLines, "\n")

	// Selected detail pane.
	var detail string
	if m.cursor >= 0 && m.cursor < len(m.hits) {
		h := m.hits[m.cursor]
		var lines []string
		lines = append(lines, styles.Title.Render(h.Title))
		meta := fmt.Sprintf(
			"id=%s · kind=%s · scope=%s · confidence=%.2f",
			h.ID, h.Kind, h.Scope, h.Confidence,
		)
		if h.WorkspacePath != nil && *h.WorkspacePath != "" {
			meta += " · ws=" + *h.WorkspacePath
		}
		if h.DomainTags != "" {
			meta += " · domain=" + h.DomainTags
		}
		lines = append(lines, styles.Faint.Render(meta))
		lines = append(lines, "")
		lines = append(lines, h.Body)
		detail = strings.Join(lines, "\n")
	}

	parts := []string{listBlock, "", styles.Faint.Render(strings.Repeat("─", width)), "", detail}
	return strings.Join(parts, "\n")
}

// Local keys — these don't go in app/keys.go because they're purely
// modal-internal (the close key, in particular, must distinguish
// "close modal" from "type 'q' as part of a query").
var (
	keyClose  = key.NewBinding(key.WithKeys("esc", "q"))
	keySubmit = key.NewBinding(key.WithKeys("enter"))
	keyDown   = key.NewBinding(key.WithKeys("ctrl+n", "down"))
	keyUp     = key.NewBinding(key.WithKeys("ctrl+p", "up"))
)
