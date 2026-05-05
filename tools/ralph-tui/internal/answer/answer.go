// Package answer provides the modal that lets the human respond to open
// clarifying questions emitted by an awaiting_human Ralph run.
//
// Each open Question maps to a single textinput line; the modal fans those
// out into a stable focus cycle (questions in order, then submit) and
// returns a Result on enter when at least one non-empty answer is present.
//
// The modal is purely presentational: it does NOT shell out to `,ralph
// answer` itself. The parent App takes the Result, builds a {qid: text}
// map, and dispatches cmds.AnswerCmd, mirroring how forms.NewRunForm hands
// its Result back to the App.
package answer

import (
	"strings"

	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/state"
	"ralph-tui/internal/styles"
)

// Result is what Modal emits when the user submits.
type Result struct {
	// RID is the run id this answer set targets.
	RID string
	// Answers maps question id -> trimmed text. Only non-empty entries are
	// included so the parent never POSTs an empty answer to `,ralph answer`.
	Answers map[string]string
}

// fieldKind enumerates focus stops in the modal: each open question, then
// the submit button.
type fieldKind int

// Modal is the answer textinput surface.
type Modal struct {
	rid       string
	questions []state.Question
	inputs    []textinput.Model
	focus     int
	width     int
	submitIx  int
}

// New builds a modal seeded with one textinput per open question. The
// caller is responsible for passing only state.Run.OpenQuestions(); the
// modal renders an "all answered" placeholder if questions is empty (the
// parent App should not open the modal in that case, but the path is safe
// either way).
func New(rid string, questions []state.Question) Modal {
	inputs := make([]textinput.Model, len(questions))
	for i, q := range questions {
		ti := textinput.New()
		ti.Placeholder = "answer"
		ti.CharLimit = 4096
		ti.Width = 60
		_ = q
		inputs[i] = ti
	}
	if len(inputs) > 0 {
		inputs[0].Focus()
	}
	return Modal{
		rid:       rid,
		questions: questions,
		inputs:    inputs,
		focus:     0,
		submitIx:  len(questions),
	}
}

// SetWidth lets the parent reflow the textinputs against the modal width.
func (m *Modal) SetWidth(w int) {
	m.width = w
	box := w - 8
	if box < 30 {
		box = 30
	}
	for i := range m.inputs {
		m.inputs[i].Width = box
	}
}

// Update handles key events. Returns:
//   - the updated modal
//   - tea.Cmd for textinput blink
//   - submit: non-nil Result when the user pressed enter on submit (and at
//     least one answer is non-empty)
//   - cancelled: true on esc / ctrl+c (always) or 'q' (only off text input)
func (m Modal) Update(msg tea.Msg) (Modal, tea.Cmd, *Result, bool) {
	switch tm := msg.(type) {
	case tea.KeyMsg:
		switch {
		case key.Matches(tm, KeyCancel):
			return m, nil, nil, true
		case key.Matches(tm, KeyQuit):
			if !m.isTextFocus() {
				return m, nil, nil, true
			}
		case key.Matches(tm, KeyTab), key.Matches(tm, KeyNextField):
			if !m.isTextFocus() || key.Matches(tm, KeyTab) {
				m.advance(1)
				return m, nil, nil, false
			}
		case key.Matches(tm, KeyShiftTab), key.Matches(tm, KeyPrevField):
			if !m.isTextFocus() || key.Matches(tm, KeyShiftTab) {
				m.advance(-1)
				return m, nil, nil, false
			}
		case key.Matches(tm, KeySubmit):
			if m.focus == m.submitIx {
				if res := m.tryResult(); res != nil {
					return m, nil, res, false
				}
				m.snapToFirstEmpty()
				return m, nil, nil, false
			}
			m.advance(1)
			return m, nil, nil, false
		}
	}
	if m.focus >= 0 && m.focus < len(m.inputs) {
		var cmd tea.Cmd
		m.inputs[m.focus], cmd = m.inputs[m.focus].Update(msg)
		return m, cmd, nil, false
	}
	return m, nil, nil, false
}

// View renders the modal.
func (m Modal) View() string {
	if len(m.questions) == 0 {
		return styles.Title.Render("Answer questions") + "\n\n" +
			styles.Faint.Render("no open questions for this run") + "\n\n" +
			styles.Faint.Render("esc/ctrl-c/q closes")
	}
	rows := []string{
		styles.Title.Render("Answer human questions · " + shortRid(m.rid)),
		"",
		styles.Faint.Render("answer at least one to unpark this run · tab/j/k cycles · enter advances/submits"),
		"",
	}
	for i, q := range m.questions {
		focused := m.focus == i
		rolePrefix := lipgloss.NewStyle().Foreground(styles.Accent).Bold(true).Render("[" + q.Role + "]")
		header := rolePrefix + " " + lipgloss.NewStyle().Foreground(styles.Subtle).Render("("+q.ID+")")
		body := styles.Subdued.Render(q.Text)
		if focused {
			body = lipgloss.NewStyle().Foreground(styles.Foreground).Render(q.Text)
		}
		rows = append(rows,
			header,
			"  "+body,
			"  "+m.inputs[i].View(),
			"",
		)
	}
	rows = append(rows, submitButton(m.focus == m.submitIx))
	rows = append(rows, "")
	rows = append(rows, styles.Faint.Render("esc/ctrl-c/q cancels"))
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

// HasOpenQuestions reports whether the modal has anything to ask.
func (m Modal) HasOpenQuestions() bool { return len(m.questions) > 0 }

func (m *Modal) advance(delta int) {
	total := m.submitIx + 1
	m.focus = ((m.focus+delta)%total + total) % total
	for i := range m.inputs {
		m.inputs[i].Blur()
	}
	if m.focus < len(m.inputs) {
		m.inputs[m.focus].Focus()
	}
}

func (m Modal) isTextFocus() bool {
	return m.focus >= 0 && m.focus < len(m.inputs)
}

func (m Modal) tryResult() *Result {
	answers := make(map[string]string, len(m.inputs))
	for i, ti := range m.inputs {
		v := strings.TrimSpace(ti.Value())
		if v == "" {
			continue
		}
		answers[m.questions[i].ID] = v
	}
	if len(answers) == 0 {
		return nil
	}
	return &Result{RID: m.rid, Answers: answers}
}

func (m *Modal) snapToFirstEmpty() {
	for i, ti := range m.inputs {
		if strings.TrimSpace(ti.Value()) == "" {
			m.focus = i
			for j := range m.inputs {
				m.inputs[j].Blur()
			}
			m.inputs[i].Focus()
			return
		}
	}
}

func submitButton(focused bool) string {
	style := styles.Subdued
	label := "[ Submit answers ]"
	if focused {
		style = lipgloss.NewStyle().Foreground(styles.AccentBright).Bold(true)
	}
	return style.Render(label)
}

func shortRid(rid string) string {
	if i := strings.LastIndex(rid, "-"); i >= 0 && i+1 < len(rid) {
		return rid[i+1:]
	}
	return rid
}

// Keybindings exported so the parent help overlay can render them.
//
// Tab/shift+tab and j/k both move between fields. j/k is gated on
// non-text-input focus so the literal characters reach the textinput.
// h/l have no special meaning here (textinput accepts them as literals).
// q cancels off-text-input only (it must reach the textinput as a literal).
var (
	KeySubmit    = key.NewBinding(key.WithKeys("enter"))
	KeyCancel    = key.NewBinding(key.WithKeys("esc", "ctrl+c"))
	KeyQuit      = key.NewBinding(key.WithKeys("q"))
	KeyTab       = key.NewBinding(key.WithKeys("tab"))
	KeyShiftTab  = key.NewBinding(key.WithKeys("shift+tab"))
	KeyNextField = key.NewBinding(key.WithKeys("down", "j"))
	KeyPrevField = key.NewBinding(key.WithKeys("up", "k"))
)
