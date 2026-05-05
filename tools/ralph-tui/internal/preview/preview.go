// Package preview implements a tmux capture-pane modal so users can peek
// at any role's live pane without exiting the TUI.
//
// The modal owns a target (tmux pane like "ralph-12345:executor-1.0") and
// re-runs `tmux capture-pane -p -e -t TARGET` on a periodic tick. The
// captured output is rendered inside a bordered box that respects modal
// width/height; ANSI escapes are preserved so colors and progress bars
// look the same as in the live pane.
package preview

import (
	"bytes"
	"errors"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/styles"
)

// Modal is a tmux capture-pane preview overlay.
type Modal struct {
	target  string // tmux pane target, e.g. "ralph-abc:executor-1"
	label   string // friendly label shown in title (e.g. "go-abc-… / executor-1")
	content string
	width   int
	height  int
	err     error
	open    bool
}

// CapturedMsg is emitted by CaptureCmd; the model handles it via Update.
type CapturedMsg struct {
	Target  string
	Output  string
	Err     error
	When    time.Time
}

// AttachReadOnlyMsg signals the app to launch a tmux popup attached
// read-only to the modal's target. The app dispatches it via tea.ExecProcess
// so the TUI does not exit; the popup overlays for the duration of the
// attach and the TUI redraws when the popup closes.
type AttachReadOnlyMsg struct {
	Target string
}

// keybindings exported for help overlay parity.
var (
	KeyClose       = key.NewBinding(key.WithKeys("esc", "q"))
	KeyForceClose  = key.NewBinding(key.WithKeys("ctrl+c"))
	KeyRefresh     = key.NewBinding(key.WithKeys("r"))
	KeyAttachRO    = key.NewBinding(key.WithKeys("A"))
)

// New constructs a closed modal. Open() configures the target and label.
func New() Modal {
	return Modal{}
}

// Open configures the modal for a given tmux pane target and stores a
// short label for the title bar. Returns the initial CaptureCmd so the
// caller can dispatch it from Update.
func (m *Modal) Open(target, label string) tea.Cmd {
	m.target = target
	m.label = label
	m.content = ""
	m.err = nil
	m.open = true
	return CaptureCmd(target)
}

// Close marks the modal closed and clears its target.
func (m *Modal) Close() {
	m.open = false
	m.target = ""
	m.label = ""
	m.content = ""
	m.err = nil
}

// IsOpen returns true while the modal is visible.
func (m *Modal) IsOpen() bool { return m.open }

// Target returns the configured tmux pane target (empty when closed).
func (m *Modal) Target() string { return m.target }

// SetSize stores the available modal area; subtract from terminal width/height.
func (m *Modal) SetSize(w, h int) {
	m.width = w
	m.height = h
}

// Update handles capture results and key input. The returned commands are:
//   - CaptureCmd refresh on `r`
//   - AttachReadOnlyMsg on `A`
// The boolean `cancel` is true when the user pressed esc/q/ctrl-c so the
// caller can close the modal.
func (m *Modal) Update(msg tea.Msg) (tea.Cmd, bool) {
	switch v := msg.(type) {
	case CapturedMsg:
		if v.Target != m.target {
			return nil, false
		}
		m.err = v.Err
		if v.Err == nil {
			m.content = v.Output
		}
		return nil, false
	case tea.KeyMsg:
		switch {
		case key.Matches(v, KeyClose), key.Matches(v, KeyForceClose):
			return nil, true
		case key.Matches(v, KeyRefresh):
			return CaptureCmd(m.target), false
		case key.Matches(v, KeyAttachRO):
			return func() tea.Msg { return AttachReadOnlyMsg{Target: m.target} }, false
		}
	}
	return nil, false
}

// View renders the modal box. Returns an empty string when closed so the
// caller can compose without a nil check.
func (m *Modal) View() string {
	if !m.open {
		return ""
	}
	w := m.width
	h := m.height
	if w < 30 {
		w = 30
	}
	if h < 8 {
		h = 8
	}

	heading := lipgloss.NewStyle().
		Foreground(styles.AccentBright).
		Bold(true).
		Render("Pane preview")
	target := lipgloss.NewStyle().Foreground(styles.Subtle).Render(m.target)
	label := ""
	if m.label != "" {
		label = lipgloss.NewStyle().Foreground(styles.Foreground).Render(m.label)
	}
	titleParts := []string{heading}
	if label != "" {
		titleParts = append(titleParts, label)
	}
	titleParts = append(titleParts, target)
	title := strings.Join(titleParts, "  ")

	body := m.content
	if m.err != nil {
		body = renderCaptureError(m.err)
	} else if body == "" {
		body = styles.Faint.Render("(loading capture-pane…)")
	}
	innerW := w - 4
	innerH := h - 6
	if innerH < 3 {
		innerH = 3
	}
	body = clampLines(body, innerH)
	body = lipgloss.NewStyle().Width(innerW).MaxHeight(innerH).Render(body)

	footer := lipgloss.NewStyle().
		Foreground(styles.Subtle).
		Render("r: refresh · A: read-only popup attach · esc/q: close")

	box := lipgloss.JoinVertical(lipgloss.Left, title, "", body, "", footer)
	return lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder(), true).
		BorderForeground(styles.Accent).
		Padding(1, 2).
		Width(w - 4).
		MaxHeight(h).
		Render(box)
}

// CaptureCmd returns a tea.Cmd that runs tmux capture-pane against the
// supplied target and emits a CapturedMsg.
func CaptureCmd(target string) tea.Cmd {
	if target == "" {
		return func() tea.Msg {
			return CapturedMsg{Err: errors.New("no tmux target")}
		}
	}
	return func() tea.Msg {
		bin, err := exec.LookPath("tmux")
		if err != nil {
			return CapturedMsg{Target: target, Err: err, When: time.Now()}
		}
		cmd := exec.Command(bin, "capture-pane", "-p", "-e", "-J", "-t", target)
		var stdout, stderr bytes.Buffer
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr
		if err := cmd.Run(); err != nil {
			msg := strings.TrimSpace(stderr.String())
			if msg == "" {
				msg = err.Error()
			}
			return CapturedMsg{
				Target: target,
				Err:    errors.New(msg),
				When:   time.Now(),
			}
		}
		return CapturedMsg{
			Target: target,
			Output: stdout.String(),
			When:   time.Now(),
		}
	}
}

// renderCaptureError translates a tmux capture-pane failure into a
// user-friendly modal body. Common case: the role's pane was closed
// when the role finished (orchestrator runs roles with
// `keep_window=False` so completed-role panes are reaped). Tmux then
// returns one of "can't find pane:", "can't find window:", "can't find
// session:", or "no server running". Show those as "role pane already
// closed" with a hint at where to find the role's tail. Anything we
// don't recognize falls through to the raw error so we don't paper over
// real bugs.
func renderCaptureError(err error) string {
	if err == nil {
		return ""
	}
	msg := strings.TrimSpace(err.Error())
	low := strings.ToLower(msg)
	closed := strings.Contains(low, "can't find pane") ||
		strings.Contains(low, "can't find window") ||
		strings.Contains(low, "can't find session") ||
		strings.Contains(low, "no server running")
	if closed {
		return lipgloss.NewStyle().Foreground(styles.Subtle).Render(
			"Role pane has already been closed.\n\n"+
				"This is normal when the role finished — Ralph reaps role panes "+
				"on success so they don't accumulate. The role's full output is "+
				"still on disk; close this modal and view it in the role grid "+
				"(layout key `2`) or zoom into the tail pane (`enter`).") +
			"\n\n" +
			styles.Faint.Render("tmux: "+msg)
	}
	return lipgloss.NewStyle().Foreground(styles.Bad).Render(
		fmt.Sprintf("capture-pane error: %s", msg))
}

// clampLines clips text to the first n lines so the rendered modal never
// overflows its allotted height. Mirrors styles.Pane's clamp logic.
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
