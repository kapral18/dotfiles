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
		`{"iter":1,"role":"reviewer-1","verdict":"pass"}`+"\n"+
			`{"iter":2,"role":"reviewer-2","final_verdict":"needs_iteration"}`+"\n")
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

	wantSubstrings := []string{"first decision", "second decision",
		"reviewer-1", "reviewer-2", "older decision"}
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
