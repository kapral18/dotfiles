package app

import (
	"os"
	"regexp"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"ralph-tui/internal/control"
	"ralph-tui/internal/state"
)

func writeFile(path, body string) error {
	return os.WriteFile(path, []byte(body), 0o644)
}

var stripAnsi = regexp.MustCompile(`\x1b\[[0-9;?]*[A-Za-z]`)

// TestViewRendersAllFourCornersOfEveryPane verifies the rounded-border corners
// are emitted for each visible pane (3 panes when not zoomed). Top-border
// invisibility was reported visually; this test pins that the chars are at
// least present in the rendered string.
func TestViewRendersAllFourCornersOfEveryPane(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()

	// Drive a window-size message through Update to set width/height + run layout().
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	mm := updated.(*Model)

	out := mm.View()
	if out == "" {
		t.Fatalf("View produced empty output")
	}

	tl := strings.Count(out, "╭")
	tr := strings.Count(out, "╮")
	bl := strings.Count(out, "╰")
	br := strings.Count(out, "╯")
	if tl != 3 || tr != 3 || bl != 3 || br != 3 {
		t.Errorf("expected 3 of each rounded corner, got TL=%d TR=%d BL=%d BR=%d", tl, tr, bl, br)
	}
	if !strings.Contains(out, "─") {
		t.Errorf("missing horizontal border char")
	}
	if !strings.Contains(out, "│") {
		t.Errorf("missing vertical border char")
	}
}

// TestViewFitsTerminalHeight asserts the rendered View fits within the
// reported terminal height. A previous bug let the status bar wrap to two
// rows, pushing total output to height+1 lines so the topmost row (and the
// pane top borders) scrolled off-screen on alt-screen flush.
func TestViewFitsTerminalHeight(t *testing.T) {
	cases := []struct{ w, h int }{
		{80, 24},
		{100, 30},
		{120, 40},
		{160, 50},
	}
	for _, c := range cases {
		m, err := New(".")
		if err != nil {
			t.Fatalf("app.New: %v", err)
		}
		updated, _ := m.Update(tea.WindowSizeMsg{Width: c.w, Height: c.h})
		mm := updated.(*Model)
		out := mm.View()
		mm.Close()

		stripped := stripAnsi.ReplaceAllString(out, "")
		rows := strings.Split(stripped, "\n")
		if len(rows) != c.h {
			t.Errorf("size %dx%d: expected %d rows, got %d", c.w, c.h, c.h, len(rows))
		}
		for i, r := range rows {
			rw := lipglossWidth(r)
			if rw > c.w {
				t.Errorf("size %dx%d: row %d width %d exceeds terminal width", c.w, c.h, i, rw)
			}
		}
		// First row must contain a top-left corner of the leftmost pane.
		if len(rows) > 0 && !strings.Contains(rows[0], "╭") {
			t.Errorf("size %dx%d: first row missing top-left corner: %q", c.w, c.h, rows[0])
		}
	}
}

// lipglossWidth uses rune count as a stand-in for visual width. Acceptable
// here because all the strings under test are ASCII or single-column runes.
func lipglossWidth(s string) int {
	return len([]rune(s))
}

func TestConfirmModalRendersAndCancels(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	mm := updated.(*Model)

	mm.askConfirm("Kill", "Send Ctrl-C?", control.ActionKill, "go-demo-20260505000000000000", "executor-1")
	out := mm.View()
	if !strings.Contains(out, "Kill 20260505000000000000:executor-1?") {
		t.Fatalf("confirm view missing target: %s", out)
	}
	if !strings.Contains(out, "enter/y: confirm") || !strings.Contains(out, "n/q/esc/ctrl-c: cancel") {
		t.Fatalf("confirm view missing key help: %s", out)
	}

	next, _ := mm.handleModalKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'q'}})
	mm = next.(*Model)
	if mm.modal != modalNone {
		t.Fatalf("q should cancel confirm modal, got modal=%v", mm.modal)
	}
}

func mkAwaitingRun() state.Run {
	return state.Run{
		ID:           "go-demo-1730000000",
		Name:         "demo",
		Goal:         "explain X",
		Status:       "awaiting_human",
		AwaitingRole: "planner-1",
		Questions: []state.Question{
			{ID: "q-1", Role: "planner-1", Text: "Where does X live?", AskedAt: "2026-05-04T00:00:00Z"},
		},
	}
}

func TestAnswerKeyOpensModalForAwaitingRun(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{mkAwaitingRun()})
	mm.refreshDetail()

	cmd := mm.openAnswerModal()
	if cmd != nil {
		t.Errorf("openAnswerModal must not emit a tea.Cmd when opening")
	}
	if mm.modal != modalAnswer {
		t.Fatalf("expected modalAnswer, got %v", mm.modal)
	}
	out := mm.View()
	if !strings.Contains(out, "Answer human questions") {
		t.Errorf("answer modal view missing title:\n%s", out)
	}
	if !strings.Contains(out, "Where does X live?") {
		t.Errorf("answer modal view missing question text:\n%s", out)
	}
}

func TestAnswerKeyShowsToastWhenNoOpenQuestions(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{
		{ID: "go-quiet-1", Name: "quiet", Status: "running"},
	})
	mm.refreshDetail()

	cmd := mm.openAnswerModal()
	if cmd != nil {
		t.Errorf("openAnswerModal returned cmd unexpectedly: %v", cmd)
	}
	if mm.modal != modalNone {
		t.Errorf("modal must remain closed when no open questions, got %v", mm.modal)
	}
	if !strings.Contains(mm.toast.text, "no open questions") {
		t.Errorf("toast missing explanation: %q", mm.toast.text)
	}
}

func TestStatusBarShowsTotalOpenQuestions(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 160, Height: 30})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{mkAwaitingRun(), mkAwaitingRun()})
	mm.refreshDetail()

	bar := mm.viewStatusBar()
	if !strings.Contains(bar, "Q:2") {
		t.Errorf("status bar must summarize total open questions:\n%s", bar)
	}
	if !strings.Contains(bar, "A: answer") {
		t.Errorf("status bar must advertise A keybind:\n%s", bar)
	}
}

// TestViewFitsTerminalHeightWithOpenQuestions covers the regression where
// the new "Q:N" status-bar segment plus the "A: answer" right-side hint
// could push the bar past the terminal width and cause the top border to
// scroll off.
func TestViewFitsTerminalHeightWithOpenQuestions(t *testing.T) {
	cases := []struct{ w, h int }{
		{80, 24},
		{100, 30},
		{120, 40},
	}
	for _, c := range cases {
		m, err := New(".")
		if err != nil {
			t.Fatalf("app.New: %v", err)
		}
		updated, _ := m.Update(tea.WindowSizeMsg{Width: c.w, Height: c.h})
		mm := updated.(*Model)
		mm.runs.SetRuns([]state.Run{mkAwaitingRun(), mkAwaitingRun()})
		mm.refreshDetail()
		out := mm.View()
		mm.Close()

		stripped := stripAnsi.ReplaceAllString(out, "")
		rows := strings.Split(stripped, "\n")
		if len(rows) != c.h {
			t.Errorf("size %dx%d w/ Q-segment: expected %d rows, got %d",
				c.w, c.h, c.h, len(rows))
		}
		for i, r := range rows {
			rw := lipglossWidth(r)
			if rw > c.w {
				t.Errorf("size %dx%d w/ Q-segment: row %d width %d > %d",
					c.w, c.h, i, rw, c.w)
			}
		}
		if len(rows) > 0 && !strings.Contains(rows[0], "╭") {
			t.Errorf("size %dx%d: first row missing top-left corner: %q",
				c.w, c.h, rows[0])
		}
	}
}

func TestLayoutSwitchKeysCycleBetweenViews(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	mm := updated.(*Model)
	if mm.layout != layoutDetail {
		t.Fatalf("default layout must be detail, got %v", mm.layout)
	}

	mm2, _ := mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'2'}})
	mm = mm2.(*Model)
	if mm.layout != layoutGrid {
		t.Errorf("'2' must select grid layout, got %v", mm.layout)
	}

	mm2, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'3'}})
	mm = mm2.(*Model)
	if mm.layout != layoutZoom {
		t.Errorf("'3' must select zoom layout, got %v", mm.layout)
	}

	mm2, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'1'}})
	mm = mm2.(*Model)
	if mm.layout != layoutDetail {
		t.Errorf("'1' must return to detail layout, got %v", mm.layout)
	}
}

func TestRoleGridShowsAllPickedRoles(t *testing.T) {
	tmp := t.TempDir()
	logPath := tmp + "/exec.log"
	if err := writeFile(logPath, "exec line 1\nexec line 2\n"); err != nil {
		t.Fatalf("write log: %v", err)
	}

	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 160, Height: 40})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{
		{
			ID:   "go-grid-1",
			Name: "grid",
			Roles: map[string]state.Role{
				"planner-1":  {ID: "planner-1", Name: "planner-1", Status: "completed"},
				"executor-1": {ID: "executor-1", Name: "executor-1", Status: "running", OutputPath: logPath},
				"reviewer-1": {ID: "reviewer-1", Name: "reviewer-1", Status: "completed"},
			},
		},
	})
	mm.refreshDetail()
	mm.layout = layoutGrid

	out := mm.View()
	for _, name := range []string{"planner-1", "executor-1", "reviewer-1"} {
		if !strings.Contains(out, name) {
			t.Errorf("role grid view must contain %q:\n%s", name, out)
		}
	}
	if !strings.Contains(out, "exec line 2") {
		t.Errorf("role grid must include the executor's tail line: %s", out)
	}
	if !strings.Contains(out, "no role") {
		t.Errorf("missing re_reviewer should render placeholder cell: %s", out)
	}
}

// TestActivityKeyCyclesDrawerSize pins the contract that capital S
// cycles off -> small -> large -> off, producing a status toast each
// time so the operator sees the size change. Mirrors E8 in the UI/UX
// audit: a busy fleet needs a wider drawer without permanently wasting
// rows when the swarm is quiet.
func TestActivityKeyCyclesDrawerSize(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", t.TempDir())
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 40})
	mm := updated.(*Model)
	if mm.activitySize != activityOff {
		t.Fatalf("activity drawer must default to off")
	}

	next, _ := mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'S'}})
	mm = next.(*Model)
	if mm.activitySize != activitySmall {
		t.Errorf("S must move drawer to small; got %s", mm.activitySize)
	}
	if !strings.Contains(mm.toast.text, "small") {
		t.Errorf("toast missing 'small' hint: %q", mm.toast.text)
	}

	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'S'}})
	mm = next.(*Model)
	if mm.activitySize != activityLarge {
		t.Errorf("second S must move drawer to large; got %s", mm.activitySize)
	}
	if !strings.Contains(mm.toast.text, "large") {
		t.Errorf("toast missing 'large' hint: %q", mm.toast.text)
	}

	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'S'}})
	mm = next.(*Model)
	if mm.activitySize != activityOff {
		t.Errorf("third S must move drawer back to off; got %s", mm.activitySize)
	}
}

// TestActivityLargeReservesMoreRows verifies the layout reserves more
// vertical space when the drawer is in its large size, so the bigger
// drawer actually shows more events instead of just relabeling itself.
func TestActivityLargeReservesMoreRows(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", t.TempDir())
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 140, Height: 50})
	mm := updated.(*Model)

	mm.activitySize = activitySmall
	small := mm.activityHeight()
	mm.activitySize = activityLarge
	large := mm.activityHeight()
	mm.activitySize = activityOff
	off := mm.activityHeight()

	if !(off == 0 && small > off && large > small) {
		t.Errorf("expected off=0 < small < large, got off=%d small=%d large=%d", off, small, large)
	}
}

// TestActivityDrawerRendersHeadingWhenOpen asserts the drawer surface
// emits an "activity" heading and a placeholder line when no events
// exist. We point RALPH_STATE_HOME at an empty temp dir so LoadRecent
// returns nil and the drawer must still occupy fixed rows so the layout
// stays stable.
func TestActivityDrawerRendersHeadingWhenOpen(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", t.TempDir())
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 140, Height: 40})
	mm := updated.(*Model)
	mm.activitySize = activitySmall

	out := mm.View()
	if !strings.Contains(out, "activity") {
		t.Errorf("activity drawer heading missing:\n%s", out)
	}
	if !strings.Contains(out, "no recent decisions") {
		t.Errorf("empty drawer must show placeholder:\n%s", out)
	}
}

// TestActivityDrawerKeepsViewWithinTerminalHeight pins that toggling
// the drawer never causes the rendered View to overflow the reported
// terminal height. The drawer reserves rows; main pane area must shrink
// in lockstep.
func TestActivityDrawerKeepsViewWithinTerminalHeight(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", t.TempDir())
	cases := []struct{ w, h int }{
		{100, 30},
		{120, 36},
		{160, 50},
	}
	for _, c := range cases {
		m, err := New(".")
		if err != nil {
			t.Fatalf("app.New: %v", err)
		}
		updated, _ := m.Update(tea.WindowSizeMsg{Width: c.w, Height: c.h})
		mm := updated.(*Model)
		mm.activitySize = activitySmall
		mm.relayout()
		out := mm.View()
		mm.Close()

		stripped := stripAnsi.ReplaceAllString(out, "")
		rows := strings.Split(stripped, "\n")
		if len(rows) != c.h {
			t.Errorf("size %dx%d w/ activity drawer: expected %d rows, got %d",
				c.w, c.h, c.h, len(rows))
		}
		for i, r := range rows {
			rw := lipglossWidth(r)
			if rw > c.w {
				t.Errorf("size %dx%d w/ activity drawer: row %d width %d > %d",
					c.w, c.h, i, rw, c.w)
			}
		}
	}
}

func TestPreviewKeyShowsToastWhenNoTmuxAttached(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{
		{ID: "go-no-tmux-1", Name: "no-tmux", Status: "running"},
	})
	mm.refreshDetail()

	cmd := mm.openPreviewModal()
	if cmd != nil {
		t.Errorf("openPreviewModal must not emit cmd when no tmux target")
	}
	if mm.modal != modalNone {
		t.Errorf("modal must stay closed without tmux target, got %v", mm.modal)
	}
	if !strings.Contains(mm.toast.text, "no tmux pane") {
		t.Errorf("toast missing reason: %q", mm.toast.text)
	}
}

func TestPreviewKeyOpensModalWithRoleTmuxTarget(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 140, Height: 40})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{
		{
			ID:   "go-with-tmux-1",
			Name: "tmux-run",
			Tmux: &state.RunTmux{Session: "ralph-with-tmux"},
			Roles: map[string]state.Role{
				"executor-1": {
					ID:     "executor-1",
					Name:   "executor-1",
					Status: "running",
					Tmux:   &state.RoleTmux{Session: "ralph-with-tmux", Window: "executor-1", Target: "ralph-with-tmux:executor-1.0"},
				},
			},
		},
	})
	mm.refreshDetail()

	cmd := mm.openPreviewModal()
	if mm.modal != modalPreview {
		t.Fatalf("modalPreview must open with tmux target, got %v", mm.modal)
	}
	if !mm.preview.IsOpen() {
		t.Errorf("preview modal IsOpen must be true")
	}
	if got := mm.preview.Target(); got != "ralph-with-tmux:executor-1.0" {
		t.Errorf("preview target = %q, want ralph-with-tmux:executor-1.0", got)
	}
	if cmd == nil {
		t.Errorf("openPreviewModal must return a tea.Cmd batch (capture + tick)")
	}
}

func TestPreviewModalEscClosesAndClearsTarget(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 140, Height: 40})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{
		{
			ID:   "go-esc-1",
			Name: "esc",
			Tmux: &state.RunTmux{Session: "ralph-esc"},
			Roles: map[string]state.Role{
				"planner-1": {
					ID:   "planner-1",
					Name: "planner-1",
					Tmux: &state.RoleTmux{Session: "ralph-esc", Window: "planner-1", Target: "ralph-esc:planner-1.0"},
				},
			},
		},
	})
	mm.refreshDetail()
	mm.openPreviewModal()
	if mm.modal != modalPreview {
		t.Fatalf("setup: preview modal not open")
	}

	next, _ := mm.handleModalKey(tea.KeyMsg{Type: tea.KeyEsc})
	mm = next.(*Model)
	if mm.modal != modalNone {
		t.Errorf("esc must close preview modal, got %v", mm.modal)
	}
	if mm.preview.Target() != "" {
		t.Errorf("preview target must reset on close, got %q", mm.preview.Target())
	}
}

// TestRunsFilterShadowsGlobalShortcuts pins B2: while the runs pane is
// in filter-typing mode, single-letter global shortcuts (`q`, `n`, `a`,
// `c`, `S`, ...) must NOT fire — every keystroke has to flow into the
// filter buffer instead. Without the IsTyping() gate in handleKey,
// typing 'n' to filter for "needs-attention" silently opened the
// new-run modal.
func TestRunsFilterShadowsGlobalShortcuts(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", t.TempDir())
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	mm := updated.(*Model)
	// Seed with a run so the filter pane has something to chew on; the
	// filter is just a string match so the run content doesn't matter.
	mm.runs.SetRuns([]state.Run{mkAwaitingRun()})
	mm.refreshDetail()

	// Enter filter mode via `/`.
	next, _ := mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	mm = next.(*Model)
	if !mm.runs.IsTyping() {
		t.Fatalf("/ must put runs pane in filter mode")
	}

	// Each of these is also a top-level shortcut that would normally open
	// a modal or quit. While typing, every one of them must extend the
	// filter buffer instead.
	for _, r := range []rune{'n', 'a', 'A', 'c', 'q', 'S', 'K', 'p', 'r'} {
		next, _ := mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		mm = next.(*Model)
		if mm.modal != modalNone {
			t.Errorf("rune %q while filter-typing must NOT open a modal; opened %v", r, mm.modal)
		}
	}
	if mm.runs.FilterInput != "naAcqSKpr" {
		t.Errorf("filter buffer must accumulate raw runes; got %q", mm.runs.FilterInput)
	}

	// Esc must drop filter mode and re-arm global shortcuts.
	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyEsc})
	mm = next.(*Model)
	if mm.runs.IsTyping() {
		t.Fatalf("esc must exit filter mode")
	}
	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'n'}})
	mm = next.(*Model)
	if mm.modal != modalNewRun {
		t.Errorf("global `n` must work again after exiting filter; modal=%v", mm.modal)
	}
}

// TestGridCursorNavigationAndDrillIn pins E3: in grid layout, h/j/k/l
// move the cell cursor and `enter` drills the cursored cell into the
// detail layout focused on that role's tail.
func TestGridCursorNavigationAndDrillIn(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", t.TempDir())
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 200, Height: 50})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{mkAwaitingRun()})
	mm.refreshDetail()
	// Switch to grid layout.
	next, _ := mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'2'}})
	mm = next.(*Model)
	if mm.layout != layoutGrid {
		t.Fatalf("`2` must select grid layout; got %v", mm.layout)
	}
	if mm.gridCursor != 0 {
		t.Fatalf("grid cursor must default to 0")
	}

	// Right -> 1 (top-right cell).
	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'l'}})
	mm = next.(*Model)
	if mm.gridCursor != 1 {
		t.Errorf("l must move cursor right; got %d", mm.gridCursor)
	}
	// Down -> 3 (bottom-right cell).
	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'j'}})
	mm = next.(*Model)
	if mm.gridCursor != 3 {
		t.Errorf("j from cell 1 must move to 3; got %d", mm.gridCursor)
	}
	// Left -> 2 (bottom-left cell).
	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'h'}})
	mm = next.(*Model)
	if mm.gridCursor != 2 {
		t.Errorf("h must move cursor left; got %d", mm.gridCursor)
	}
	// Up -> 0 (back to top-left).
	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'k'}})
	mm = next.(*Model)
	if mm.gridCursor != 0 {
		t.Errorf("k must move cursor up; got %d", mm.gridCursor)
	}

	// Enter drills the focused cell into detail layout w/ focusTail.
	mm.gridCursor = 1 // focus executor cell (planner / executor / reviewer / re_reviewer).
	next, _ = mm.handleKey(tea.KeyMsg{Type: tea.KeyEnter})
	mm = next.(*Model)
	if mm.layout != layoutDetail {
		t.Errorf("enter from grid must switch to detail layout; got %v", mm.layout)
	}
	if mm.focus != focusTail {
		t.Errorf("enter from grid must focus the tail pane; got %v", mm.focus)
	}
}

func TestAnswerModalSubmitDispatchesAnswerCmd(t *testing.T) {
	m, err := New(".")
	if err != nil {
		t.Fatalf("app.New: %v", err)
	}
	defer m.Close()
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	mm := updated.(*Model)
	mm.runs.SetRuns([]state.Run{mkAwaitingRun()})
	mm.refreshDetail()
	mm.openAnswerModal()
	if mm.modal != modalAnswer {
		t.Fatalf("modal not opened")
	}

	for _, r := range "answer text" {
		next, _ := mm.handleModalKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		mm = next.(*Model)
	}
	next, _ := mm.handleModalKey(tea.KeyMsg{Type: tea.KeyEnter})
	mm = next.(*Model)

	mNext, cmd := mm.handleModalKey(tea.KeyMsg{Type: tea.KeyEnter})
	mm = mNext.(*Model)
	if cmd == nil {
		t.Fatalf("submit must dispatch a tea.Cmd (AnswerCmd)")
	}
	if mm.modal != modalNone {
		t.Errorf("modal must close after submit, got %v", mm.modal)
	}
	if !strings.Contains(mm.toast.text, "answering") {
		t.Errorf("toast must indicate answering: %q", mm.toast.text)
	}
}
