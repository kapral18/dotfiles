package detail

import (
	"strings"
	"testing"

	"ralph-tui/internal/state"
)

func mkRun() state.Run {
	return state.Run{
		ID:         "go-foo-1730000000",
		Goal:       "ship feature X",
		Workspace:  "/tmp/ws",
		Status:     "running",
		Phase:      "executing",
		Validation: "needs_verification",
		Iterations: []state.Iteration{{N: 1, Phase: "exec", Task: "do thing"}},
		Roles: map[string]state.Role{
			"executor-1": {ID: "executor-1", Name: "executor-1", Status: "completed"},
		},
	}
}

func renderRun(t *testing.T, r state.Run) string {
	t.Helper()
	m := New()
	m.SetRun(r)
	m.SetSize(120, 40)
	return m.View()
}

func TestDetailViewShowsBaseHeaderWithoutIntentSurfaces(t *testing.T) {
	v := renderRun(t, mkRun())
	if !strings.Contains(v, "go-foo-1730000000") {
		t.Errorf("view missing run id")
	}
	if strings.Contains(v, "AWAITING HUMAN") {
		t.Errorf("view should not show banner unless status=awaiting_human")
	}
	if strings.Contains(v, "Open questions") {
		t.Errorf("view should not show open-questions header without questions")
	}
	if strings.Contains(v, "Summary") {
		t.Errorf("view should not show summary header without summary_path")
	}
}

func TestDetailViewShowsWorkflowHeader(t *testing.T) {
	r := mkRun()
	r.Workflow = "research"
	v := renderRun(t, r)
	if !strings.Contains(v, "Workflow: research") {
		t.Errorf("view missing 'Workflow: research':\n%s", v)
	}
}

func TestDetailViewRendersAwaitingHumanBanner(t *testing.T) {
	r := mkRun()
	r.Status = "awaiting_human"
	r.AwaitingRole = "planner-1"
	r.Questions = []state.Question{
		{ID: "q-1", Role: "planner-1", Text: "Which workspace?", AskedAt: "2026-05-04T00:00:00Z"},
	}
	v := renderRun(t, r)
	if !strings.Contains(v, "AWAITING HUMAN") {
		t.Errorf("banner missing in awaiting_human view:\n%s", v)
	}
	if !strings.Contains(v, "asked by planner-1") {
		t.Errorf("banner missing awaiting_role attribution")
	}
	if !strings.Contains(v, "press 'A' to answer") {
		t.Errorf("banner missing answer keybind hint")
	}
	if !strings.Contains(v, "Open questions (1)") {
		t.Errorf("open-questions header missing")
	}
	if !strings.Contains(v, "Which workspace?") {
		t.Errorf("question text missing in open-questions list")
	}
}

func TestDetailViewSkipsAnsweredQuestionsInOpenList(t *testing.T) {
	r := mkRun()
	r.Status = "awaiting_human"
	r.Questions = []state.Question{
		{ID: "q-1", Role: "planner-1", Text: "first", AskedAt: "t1", Answer: "yes", AnsweredAt: "t2"},
		{ID: "q-2", Role: "planner-1", Text: "second open", AskedAt: "t3"},
	}
	v := renderRun(t, r)
	if !strings.Contains(v, "Open questions (1)") {
		t.Errorf("only the unanswered question should appear in open count:\n%s", v)
	}
	if strings.Contains(v, "(q-1)") {
		t.Errorf("answered q-1 must not appear in open list:\n%s", v)
	}
	if !strings.Contains(v, "second open") {
		t.Errorf("unanswered q-2 missing")
	}
}

func TestDetailViewShowsSummaryPath(t *testing.T) {
	r := mkRun()
	r.SummaryPath = "/tmp/runs/go-foo/summary.md"
	v := renderRun(t, r)
	if !strings.Contains(v, "Summary") {
		t.Errorf("summary header missing:\n%s", v)
	}
	if !strings.Contains(v, "/tmp/runs/go-foo/summary.md") {
		t.Errorf("summary path missing")
	}
}
