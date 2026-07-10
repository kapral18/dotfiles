package activity

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func writeJSON(t *testing.T, path string, v any) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(path, b, 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
}

func writeFile(t *testing.T, path, body string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
}

func touch(t *testing.T, path string, mtime time.Time) {
	t.Helper()
	if err := os.Chtimes(path, mtime, mtime); err != nil {
		t.Fatalf("chtimes: %v", err)
	}
}

func setStateRoot(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	t.Setenv("RALPH_STATE_HOME", dir)
	return filepath.Join(dir, "runs")
}

func TestLoadRecentReturnsNilWhenNoRunsDir(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", t.TempDir())
	if got := LoadRecent(10); len(got) != 0 {
		t.Errorf("expected empty events, got %d", len(got))
	}
}

func TestLoadRecentMergesDecisionsAndVerdictsAcrossRuns(t *testing.T) {
	root := setStateRoot(t)
	now := time.Now()

	writeJSON(t, filepath.Join(root, "go-foo", "manifest.json"), map[string]any{
		"id": "go-foo", "kind": "go",
	})
	writeFile(t, filepath.Join(root, "go-foo", "decisions.log"),
		"first decision\nsecond decision\n")
	writeFile(t, filepath.Join(root, "go-foo", "verdicts.jsonl"),
		`{"iter": 1, "role": "reviewer-1", "verdict": {"verdict": "pass", "criteria_met": ["artifact exists", "content matches"], "criteria_unmet": [], "next_task": "", "blocking_reason": "", "notes": "passes on iter 1"}, "at": "2026-07-10T01:39:50Z"}`+"\n"+
			`{"iter": 2, "role": "reviewer-2", "verdict": {"agree_with_primary": false, "final_verdict": "needs_iteration", "next_task": "retry creating the artifact", "blocking_reason": "", "notes": "re_reviewer says recoverable on iter 2"}, "at": "2026-07-10T01:39:51Z"}`+"\n")
	touch(t, filepath.Join(root, "go-foo", "decisions.log"), now.Add(-30*time.Second))
	touch(t, filepath.Join(root, "go-foo", "verdicts.jsonl"), now.Add(-10*time.Second))

	writeJSON(t, filepath.Join(root, "go-bar", "manifest.json"), map[string]any{
		"id": "go-bar", "kind": "go",
	})
	writeFile(t, filepath.Join(root, "go-bar", "decisions.log"), "older decision\n")
	touch(t, filepath.Join(root, "go-bar", "decisions.log"), now.Add(-2*time.Minute))

	got := LoadRecent(10)
	if len(got) == 0 {
		t.Fatalf("expected events, got 0")
	}
	if got[0].At.Before(got[len(got)-1].At) {
		t.Errorf("events must be sorted newest-first")
	}

	wantSubstrings := []string{
		"first decision", "second decision",
		"reviewer-1", "reviewer-2", "pass", "needs_iteration", "older decision",
	}
	merged := strings.Builder{}
	for _, ev := range got {
		merged.WriteString(ev.Message)
		merged.WriteString("|")
		merged.WriteString(ev.RunID)
		merged.WriteString("\n")
	}
	for _, s := range wantSubstrings {
		if !strings.Contains(merged.String(), s) {
			t.Errorf("expected event substring %q in:\n%s", s, merged.String())
		}
	}
}

func TestLoadRecentSkipsRoleManifests(t *testing.T) {
	root := setStateRoot(t)
	writeJSON(t, filepath.Join(root, "go-parent", "manifest.json"), map[string]any{
		"id": "go-parent", "kind": "go",
	})
	writeFile(t, filepath.Join(root, "go-parent", "decisions.log"), "parent decision\n")

	writeJSON(t, filepath.Join(root, "executor-1", "manifest.json"), map[string]any{
		"id": "executor-1", "kind": "role",
	})
	writeFile(t, filepath.Join(root, "executor-1", "decisions.log"), "child decision\n")

	got := LoadRecent(10)
	for _, ev := range got {
		if ev.RunID != "go-parent" {
			t.Errorf("activity stream must skip role manifests, got runID %q", ev.RunID)
		}
	}
}

func TestLoadRecentRespectsLimit(t *testing.T) {
	root := setStateRoot(t)
	writeJSON(t, filepath.Join(root, "go-x", "manifest.json"), map[string]any{
		"id": "go-x", "kind": "go",
	})
	body := strings.Repeat("a decision line\n", 50)
	writeFile(t, filepath.Join(root, "go-x", "decisions.log"), body)

	got := LoadRecent(3)
	if len(got) > 3 {
		t.Errorf("limit=3 must cap output, got %d", len(got))
	}
}

func TestLoadRecentParsesProducerVerdictObjects(t *testing.T) {
	root := setStateRoot(t)
	now := time.Now()

	writeFile(t, filepath.Join(root, "go-foo", "manifest.json"), `{"id": "go-foo", "kind": "go"}`)
	writeFile(t, filepath.Join(root, "go-foo", "verdicts.jsonl"),
		`{"iter": 1, "role": "reviewer-1", "verdict": {"verdict": "pass", "criteria_met": ["artifact exists", "content matches"], "criteria_unmet": [], "next_task": "", "blocking_reason": "", "notes": "passes on iter 1"}, "at": "2026-07-10T01:39:50Z"}`+"\n"+
			`{"iter": 2, "role": "reviewer-2", "verdict": {"verdict": "fail", "criteria_met": [], "criteria_unmet": ["forced fail"], "next_task": "", "blocking_reason": "RALPH_TEST_REVIEWER_VERDICT=fail", "notes": "forced fail on iter 2"}, "at": "2026-07-10T01:39:51Z"}`+"\n"+
			`{"iter": 3, "role": "re_reviewer-1", "verdict": {"agree_with_primary": false, "final_verdict": "needs_iteration", "next_task": "retry creating the artifact", "blocking_reason": "", "notes": "re_reviewer says recoverable on iter 3"}, "at": "2026-07-10T01:39:52Z"}`+"\n")
	touch(t, filepath.Join(root, "go-foo", "verdicts.jsonl"), now)

	got := LoadRecent(10)
	if len(got) != 3 {
		t.Fatalf("expected 3 verdict events, got %d", len(got))
	}

	want := []string{
		"iter 1 · reviewer-1 · pass — passes on iter 1",
		"iter 2 · reviewer-2 · fail — RALPH_TEST_REVIEWER_VERDICT=fail",
		"iter 3 · re_reviewer-1 · needs_iteration — re_reviewer says recoverable on iter 3",
	}
	for i, s := range want {
		if got[i].Kind != KindVerdict {
			t.Fatalf("event %d kind = %q, want verdict", i, got[i].Kind)
		}
		if got[i].Message != s {
			t.Errorf("event %d message = %q, want %q", i, got[i].Message, s)
		}
	}
}

func TestFormatLineShortensRunID(t *testing.T) {
	ev := Event{
		RunID:   "go-foo-1730000000",
		Kind:    KindDecision,
		Message: "hello",
	}
	got := FormatLine(ev, 12)
	if !strings.Contains(got, "1730000000") {
		t.Errorf("FormatLine must include short id, got %q", got)
	}
	if !strings.Contains(got, "d") {
		t.Errorf("FormatLine should include kind glyph, got %q", got)
	}
	if !strings.Contains(got, "hello") {
		t.Errorf("FormatLine should include the message, got %q", got)
	}
}
