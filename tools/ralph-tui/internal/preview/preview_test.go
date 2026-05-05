package preview

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestModalOpenAndCloseTransitions(t *testing.T) {
	m := New()
	if m.IsOpen() {
		t.Fatalf("modal must default to closed")
	}
	cmd := m.Open("ralph-abc:executor-1", "go-abc / executor-1")
	if cmd == nil {
		t.Errorf("Open must return an initial CaptureCmd")
	}
	if !m.IsOpen() {
		t.Errorf("modal must be open after Open()")
	}
	if got, want := m.Target(), "ralph-abc:executor-1"; got != want {
		t.Errorf("Target = %q, want %q", got, want)
	}
	m.Close()
	if m.IsOpen() {
		t.Errorf("modal must be closed after Close()")
	}
	if m.Target() != "" {
		t.Errorf("Close must clear target, got %q", m.Target())
	}
}

func TestUpdateAcceptsCapturedOutputForMatchingTarget(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "")
	_, cancel := m.Update(CapturedMsg{
		Target: "ralph-x:planner-1",
		Output: "hello pane",
	})
	if cancel {
		t.Fatalf("captured output must not cancel modal")
	}
	if !strings.Contains(m.View(), "hello pane") {
		t.Errorf("View must include captured content:\n%s", m.View())
	}
}

func TestUpdateIgnoresStaleCaptureForOtherTarget(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "")
	m.Update(CapturedMsg{Target: "ralph-x:planner-1", Output: "current"})
	m.Update(CapturedMsg{Target: "ralph-other:executor-1", Output: "stale"})
	v := m.View()
	if !strings.Contains(v, "current") {
		t.Errorf("current output missing:\n%s", v)
	}
	if strings.Contains(v, "stale") {
		t.Errorf("stale capture for different target leaked into view")
	}
}

func TestEscClosesModal(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "")
	_, cancel := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	if !cancel {
		t.Fatalf("Esc must request modal close")
	}
}

func TestQClosesModal(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "")
	_, cancel := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'q'}})
	if !cancel {
		t.Fatalf("q must request modal close")
	}
}

func TestRefreshKeyEmitsCaptureCmd(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "")
	cmd, cancel := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'r'}})
	if cancel {
		t.Fatalf("refresh must not cancel")
	}
	if cmd == nil {
		t.Fatalf("refresh must emit CaptureCmd")
	}
}

func TestAttachKeyEmitsAttachReadOnlyMsg(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "go-x / planner-1")
	cmd, cancel := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'A'}})
	if cancel {
		t.Fatalf("A must not cancel modal")
	}
	if cmd == nil {
		t.Fatalf("A must emit AttachReadOnlyMsg cmd")
	}
	msg := cmd()
	at, ok := msg.(AttachReadOnlyMsg)
	if !ok {
		t.Fatalf("cmd must return AttachReadOnlyMsg, got %T", msg)
	}
	if at.Target != "ralph-x:planner-1" {
		t.Errorf("attach target = %q, want ralph-x:planner-1", at.Target)
	}
}

func TestViewIsEmptyWhenClosed(t *testing.T) {
	m := New()
	if v := m.View(); v != "" {
		t.Errorf("closed modal must produce empty view, got %q", v)
	}
}

func TestViewClampsLongCaptures(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "")
	m.SetSize(60, 14)
	long := strings.Repeat("LINE\n", 100)
	m.Update(CapturedMsg{Target: "ralph-x:planner-1", Output: long})
	out := m.View()
	if strings.Count(out, "\n") > 14 {
		t.Errorf("modal must clip to allotted height, got %d rows:\n%s",
			strings.Count(out, "\n"), out)
	}
}

func TestCaptureCmdEmptyTargetReturnsError(t *testing.T) {
	cmd := CaptureCmd("")
	msg := cmd()
	cap, ok := msg.(CapturedMsg)
	if !ok {
		t.Fatalf("CaptureCmd must emit CapturedMsg, got %T", msg)
	}
	if cap.Err == nil {
		t.Errorf("empty target must produce an error")
	}
}

// TestViewRendersFriendlyMessageWhenPaneClosed pins the regression
// where the modal showed a raw `capture-pane error: can't find window:
// planner-1` after a role finished and its pane was reaped. The new
// renderer detects the four common tmux "missing target" phrases and
// shows a friendlier message instead, with the raw tmux error preserved
// underneath as a faint subtitle for power users.
func TestViewRendersFriendlyMessageWhenPaneClosed(t *testing.T) {
	cases := []string{
		"can't find pane: %1234",
		"can't find window: planner-1",
		"can't find session: ralph-abc123",
		"no server running on /tmp/tmux-501/default",
	}
	for _, raw := range cases {
		m := New()
		m.Open("ralph-x:planner-1", "go-x / planner-1")
		m.SetSize(80, 20)
		m.Update(CapturedMsg{Target: "ralph-x:planner-1", Err: errAsString{raw}})
		v := m.View()
		if !strings.Contains(v, "Role pane has already been closed.") {
			t.Errorf("err=%q: friendly message missing:\n%s", raw, v)
		}
		if !strings.Contains(v, raw) {
			t.Errorf("err=%q: raw tmux error missing from subtitle:\n%s", raw, v)
		}
		if strings.Contains(v, "capture-pane error:") {
			t.Errorf("err=%q: friendly path must NOT prefix with 'capture-pane error:':\n%s", raw, v)
		}
	}
}

// TestViewRendersRawErrorForUnknownFailure keeps the existing path
// honest for failures we can't classify (e.g. permission denied,
// version mismatch); they should still surface as a hard error so we
// don't silently hide real bugs behind the friendly label.
func TestViewRendersRawErrorForUnknownFailure(t *testing.T) {
	m := New()
	m.Open("ralph-x:planner-1", "")
	m.SetSize(80, 20)
	m.Update(CapturedMsg{Target: "ralph-x:planner-1", Err: errAsString{"permission denied"}})
	v := m.View()
	if !strings.Contains(v, "capture-pane error: permission denied") {
		t.Errorf("unrecognized errors must surface raw:\n%s", v)
	}
	if strings.Contains(v, "Role pane has already been closed.") {
		t.Errorf("unrecognized errors must NOT use the friendly closed-pane message:\n%s", v)
	}
}

// errAsString is a tiny error wrapper for tests so we can construct
// tmux-style failure strings without depending on errors.New from the
// standard test scaffolding.
type errAsString struct{ s string }

func (e errAsString) Error() string { return e.s }
