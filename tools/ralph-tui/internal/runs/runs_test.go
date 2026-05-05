package runs

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"ralph-tui/internal/state"
)

func mkRuns() []state.Run {
	return []state.Run{
		{ID: "go-foo-1", Name: "foo", Goal: "build the foo", Status: "completed", Validation: "passed",
			Iterations: []state.Iteration{{N: 1, Phase: "decided"}}},
		{ID: "go-bar-2", Name: "bar", Goal: "fix the bar", Status: "running", Validation: "needs_verification",
			Runner: &state.RunnerInfo{Alive: true}},
		{ID: "go-baz-3", Name: "baz", Goal: "review the baz", Status: "needs_human", Validation: "blocked",
			ReplanQueued: true},
	}
}

func TestSetRunsClampsCursor(t *testing.T) {
	// Use SortRecent so the input order is preserved (this test predates
	// the attention-need sort; it only cares about cursor clamping).
	m := New()
	m.Sort = SortRecent
	m.SetRuns(mkRuns())
	for i := 0; i < 5; i++ {
		m, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	}
	if got, _ := m.Selected(); got.ID != "go-baz-3" {
		t.Errorf("cursor should clamp at last visible: got %q", got.ID)
	}

	m.SetRuns(mkRuns()[:1])
	if got, _ := m.Selected(); got.ID != "go-foo-1" {
		t.Errorf("after shrink want first run: got %q", got.ID)
	}
}

func TestFilterReducesVisibleSet(t *testing.T) {
	m := New()
	m.SetRuns(mkRuns())
	m.filter = "bar"
	m.clampCursor()
	if len(m.visible()) != 1 || m.visible()[0].ID != "go-bar-2" {
		t.Errorf("filter=bar visible=%+v", m.visible())
	}
	if got, _ := m.Selected(); got.ID != "go-bar-2" {
		t.Errorf("selected after filter: got %q", got.ID)
	}
}

func TestFilterModeKeysPipeIntoQuery(t *testing.T) {
	m := New()
	m.SetRuns(mkRuns())

	m, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	if !m.filterMode {
		t.Fatal("filter mode should be active after '/'")
	}
	for _, r := range []rune("baz") {
		m, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
	}
	if m.FilterInput != "baz" {
		t.Errorf("filter input: %q", m.FilterInput)
	}
	m, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	if m.filterMode {
		t.Error("enter should exit filter mode")
	}
	if got, _ := m.Selected(); got.ID != "go-baz-3" {
		t.Errorf("selected after typed filter: %q", got.ID)
	}
}

func TestEscClearsFilter(t *testing.T) {
	m := New()
	m.SetRuns(mkRuns())
	m.filter = "bar"
	m, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	m, _ = m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	if m.filter != "" || m.FilterInput != "" {
		t.Errorf("esc should clear filter: %q / %q", m.filter, m.FilterInput)
	}
}

func TestDisplayStatusPicksMostRelevantSignal(t *testing.T) {
	cases := []struct {
		r    state.Run
		want string
	}{
		{state.Run{Status: "completed", Validation: "passed"}, "passed"},
		{state.Run{Status: "completed", Validation: "needs_verification"}, "needs_verification"},
		{state.Run{Status: "running"}, "running"},
		{state.Run{}, "-"},
	}
	for _, c := range cases {
		got := displayStatus(c.r)
		if got != c.want {
			t.Errorf("displayStatus(%+v)=%q want %q", c.r, got, c.want)
		}
	}
}

func TestRunnerGlyphReflectsHeartbeatAndReplan(t *testing.T) {
	cases := []struct {
		name    string
		r       state.Run
		wantHas string
	}{
		{"alive runner -> dot", state.Run{Runner: &state.RunnerInfo{Alive: true}}, "●"},
		{"dead runner -> dot",  state.Run{Runner: &state.RunnerInfo{Alive: false}}, "●"},
		{"replan queued -> R",  state.Run{ReplanQueued: true}, "R"},
		{"never started -> blank", state.Run{}, " "},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := runnerGlyph(c.r)
			if !strings.Contains(got, c.wantHas) {
				t.Errorf("runnerGlyph %+v -> %q, want contains %q", c.r, got, c.wantHas)
			}
		})
	}
}

func TestQuestionBadgeOmittedWithoutOpenQuestions(t *testing.T) {
	r := state.Run{
		Questions: []state.Question{
			{ID: "q-1", Answer: "yes", AnsweredAt: "t1"},
		},
	}
	if got := questionBadge(r); got != "" {
		t.Errorf("answered question must not produce badge, got %q", got)
	}
}

func TestQuestionBadgeShowsOpenCountWhenAwaitingHuman(t *testing.T) {
	r := state.Run{
		Status: "awaiting_human",
		Questions: []state.Question{
			{ID: "q-1"},
			{ID: "q-2"},
		},
	}
	got := questionBadge(r)
	if !strings.Contains(got, "Q:2") {
		t.Errorf("badge missing Q:2: %q", got)
	}
}

func TestRenderRowIncludesQBadgeWhenAwaiting(t *testing.T) {
	m := New()
	r := state.Run{
		ID:     "go-aw-1",
		Name:   "aw",
		Goal:   "blocked on questions",
		Status: "awaiting_human",
		Questions: []state.Question{
			{ID: "q-1"},
		},
	}
	m.SetRuns([]state.Run{r})
	m.SetSize(120, 30)
	v := m.View()
	if !strings.Contains(v, "Q:1") {
		t.Errorf("rendered list must include Q:1 badge:\n%s", v)
	}
}

// TestRenderRowDoesNotWrapWithLongGoal pins the regression where the
// fixed-column subtraction in goalWidth() was stale (set for the legacy
// layout) and let long goals overflow the runs pane, wrapping the row
// onto two visible lines. The runs pane in a half-width 220-column TUI
// is roughly 110 chars; with a long goal we must still render exactly
// one row line per run.
func TestRenderRowDoesNotWrapWithLongGoal(t *testing.T) {
	m := New()
	m.Sort = SortRecent
	long := "Create WORKSPACE/fleet_check.py: a Python 3 stdlib-only script that takes one positional arg, scans manifests, and prints a JSON line — long enough to overflow the runs column on any width below 200."
	r := state.Run{
		ID:         "go-long-1",
		Name:       "Create-WORKSPACE-fleet_check.py",
		Goal:       long,
		Status:     "running",
		Phase:      "planning",
		Validation: "needs_iteration", // worst-case status width
		Iterations: []state.Iteration{
			{N: 1, PrimaryVerdict: "pass"},
			{N: 2, PrimaryVerdict: "pass"},
		},
		Questions: []state.Question{{ID: "q-1"}, {ID: "q-2"}},
	}
	m.SetRuns([]state.Run{r})
	for _, w := range []int{96, 110, 140, 220} {
		m.SetSize(w, 30)
		body := m.View()
		// Strip the "sort: …" header line — we only want to count row lines.
		lines := strings.Split(body, "\n")
		rowLines := 0
		for _, ln := range lines {
			if strings.Contains(ln, "Create-WORKSPACE-flee") || strings.Contains(ln, long[:20]) {
				rowLines++
			}
		}
		if rowLines != 1 {
			t.Errorf("width=%d: expected 1 row line, got %d:\n%s", w, rowLines, body)
		}
	}
}

func TestSortNeedBubblesAwaitingHumanToTop(t *testing.T) {
	m := New() // default sort = SortNeed
	m.SetRuns([]state.Run{
		{ID: "go-old-completed", Status: "completed", Validation: "passed", CreatedAt: "2026-04-01T00:00:00Z"},
		{ID: "go-running", Status: "running", CreatedAt: "2026-04-15T00:00:00Z"},
		{ID: "go-blocked", Status: "awaiting_human", Questions: []state.Question{{ID: "q-1"}}, CreatedAt: "2026-03-01T00:00:00Z"},
		{ID: "go-needs-verify", Status: "running", Validation: "needs_verification", CreatedAt: "2026-04-10T00:00:00Z"},
	})
	visible := m.visible()
	if len(visible) < 4 {
		t.Fatalf("expected 4 runs, got %d", len(visible))
	}
	if visible[0].ID != "go-blocked" {
		t.Errorf("awaiting_human must be first: got %q", visible[0].ID)
	}
	if visible[1].ID != "go-needs-verify" {
		t.Errorf("needs_verification should rank above plain running: got %q", visible[1].ID)
	}
	if visible[3].ID != "go-old-completed" {
		t.Errorf("completed runs sink to the bottom: got %q", visible[3].ID)
	}
}

func TestSortRecentRestoresChronologicalOrder(t *testing.T) {
	m := New()
	m.Sort = SortRecent
	m.SetRuns([]state.Run{
		{ID: "go-old", CreatedAt: "2026-04-01T00:00:00Z"},
		{ID: "go-new", CreatedAt: "2026-05-01T00:00:00Z"},
		{ID: "go-mid", CreatedAt: "2026-04-15T00:00:00Z"},
	})
	visible := m.visible()
	if visible[0].ID != "go-old" {
		t.Errorf("SortRecent must preserve input order, got %q first", visible[0].ID)
	}
}

func TestCycleSortToggles(t *testing.T) {
	m := New()
	if m.Sort != SortNeed {
		t.Fatalf("default sort must be SortNeed, got %v", m.Sort)
	}
	m.CycleSort()
	if m.Sort != SortRecent {
		t.Errorf("first cycle must give SortRecent, got %v", m.Sort)
	}
	m.CycleSort()
	if m.Sort != SortNeed {
		t.Errorf("second cycle must wrap back to SortNeed, got %v", m.Sort)
	}
}

// TestIterSparklineColorsByVerdict pins that each iteration's verdict
// produces the right glyph: pass=█ green, fail=█ red, replan=▆ amber.
// The sparkline is left-to-right, so position N reflects iteration N+1.
func TestIterSparklineColorsByVerdict(t *testing.T) {
	r := state.Run{
		Iterations: []state.Iteration{
			{N: 1, PrimaryVerdict: "PASS"},
			{N: 2, PrimaryVerdict: "REPLAN"},
			{N: 3, PrimaryVerdict: "FAIL"},
		},
	}
	bar := iterSparkline(r, 8)
	stripped := stripAnsi(bar)
	if got, want := strings.Count(stripped, "█"), 2; got != want {
		t.Errorf("expected 2 full blocks (pass+fail), got %d in %q", got, stripped)
	}
	if !strings.Contains(stripped, "▆") {
		t.Errorf("replan glyph (▆) missing from sparkline: %q", stripped)
	}
	if got, want := strings.Count(stripped, "░"), 5; got != want {
		t.Errorf("remaining slots should be dim: got %d, want %d in %q", got, want, stripped)
	}
}

// TestIterSparklineEmptyForFreshRun pins that a run with no iterations
// renders dim placeholders for the full slot count, so the column width
// stays stable across the list.
func TestIterSparklineEmptyForFreshRun(t *testing.T) {
	r := state.Run{Status: "running"}
	stripped := stripAnsi(iterSparkline(r, 8))
	if got, want := strings.Count(stripped, "░"), 8; got != want {
		t.Errorf("fresh run must render %d dim slots, got %d in %q", want, got, stripped)
	}
	if strings.Contains(stripped, "█") {
		t.Errorf("no iterations should mean no full blocks: %q", stripped)
	}
}

// TestIterSparklineCollapsesPastSlots pins that history beyond `slots`
// is truncated from the left so the bar reflects the most recent N
// iterations (matches the operator's expectation that the rightmost
// glyph is the latest verdict).
func TestIterSparklineCollapsesPastSlots(t *testing.T) {
	r := state.Run{
		Iterations: []state.Iteration{
			{N: 1, PrimaryVerdict: "PASS"},
			{N: 2, PrimaryVerdict: "PASS"},
			{N: 3, PrimaryVerdict: "PASS"},
			{N: 4, PrimaryVerdict: "FAIL"},
			{N: 5, PrimaryVerdict: "PASS"},
			{N: 6, PrimaryVerdict: "REPLAN"},
		},
	}
	stripped := stripAnsi(iterSparkline(r, 4))
	if l := len([]rune(stripped)); l != 4 {
		t.Errorf("sparkline must clip to slots=4 runes, got %d (%q)", l, stripped)
	}
	if !strings.HasSuffix(stripped, "▆") {
		t.Errorf("rightmost block must reflect most recent verdict (replan): %q", stripped)
	}
}

// stripAnsi is a tiny helper to remove ANSI sequences for sparkline assertions.
func stripAnsi(s string) string {
	var b strings.Builder
	in := false
	for _, r := range s {
		if r == 0x1b {
			in = true
			continue
		}
		if in {
			if (r >= 'A' && r <= 'Z') || (r >= 'a' && r <= 'z') {
				in = false
			}
			continue
		}
		b.WriteRune(r)
	}
	return b.String()
}
