package state

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func writeJSON(t *testing.T, path string, v any) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(path, b, 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
}

func withRunsRoot(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	t.Setenv("RALPH_STATE_HOME", dir)
	return filepath.Join(dir, "runs")
}

func TestLoadRunsSortedNewestFirst(t *testing.T) {
	root := withRunsRoot(t)

	writeJSON(t, filepath.Join(root, "go-old", "manifest.json"), map[string]any{
		"id":         "go-old",
		"kind":       "go",
		"goal":       "old run",
		"created_at": "2026-04-01T00:00:00Z",
		"phase":      "completed",
		"status":     "completed",
	})
	writeJSON(t, filepath.Join(root, "go-new", "manifest.json"), map[string]any{
		"id":         "go-new",
		"kind":       "go",
		"goal":       "new run",
		"created_at": "2026-05-01T00:00:00Z",
		"phase":      "executing",
		"status":     "running",
	})

	runs, err := LoadRuns()
	if err != nil {
		t.Fatalf("LoadRuns: %v", err)
	}
	if len(runs) != 2 {
		t.Fatalf("want 2 runs, got %d", len(runs))
	}
	if runs[0].ID != "go-new" {
		t.Errorf("want newest first, got %q", runs[0].ID)
	}
	if runs[1].ID != "go-old" {
		t.Errorf("want oldest second, got %q", runs[1].ID)
	}
}

func TestLoadRunsSkipsRoleManifests(t *testing.T) {
	root := withRunsRoot(t)

	writeJSON(t, filepath.Join(root, "go-parent", "manifest.json"), map[string]any{
		"id":         "go-parent",
		"kind":       "go",
		"created_at": "2026-05-01T00:00:00Z",
	})
	writeJSON(t, filepath.Join(root, "executor-1", "manifest.json"), map[string]any{
		"id":         "executor-1",
		"kind":       "role",
		"created_at": "2026-05-01T00:00:00Z",
	})

	runs, err := LoadRuns()
	if err != nil {
		t.Fatalf("LoadRuns: %v", err)
	}
	if len(runs) != 1 || runs[0].ID != "go-parent" {
		t.Fatalf("want only parent run, got %+v", runs)
	}
}

func TestLoadRunsTolerantToCorruptManifest(t *testing.T) {
	root := withRunsRoot(t)

	if err := os.MkdirAll(filepath.Join(root, "broken"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(root, "broken", "manifest.json"), []byte("{not json"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	writeJSON(t, filepath.Join(root, "good", "manifest.json"), map[string]any{
		"id":         "good",
		"kind":       "go",
		"created_at": "2026-05-01T00:00:00Z",
	})

	runs, err := LoadRuns()
	if err != nil {
		t.Fatalf("LoadRuns: %v", err)
	}
	if len(runs) != 1 || runs[0].ID != "good" {
		t.Fatalf("want only the good run, got %+v", runs)
	}
}

func TestSessionNameFromManifest(t *testing.T) {
	r := Run{
		ID:   "go-foo-1234567890",
		Tmux: &RunTmux{Session: "ralph-explicit"},
	}
	if got := r.SessionName(); got != "ralph-explicit" {
		t.Errorf("explicit session: got %q", got)
	}

	r2 := Run{ID: "go-foo-1234567890"}
	if got := r2.SessionName(); got != "ralph-1234567890" {
		t.Errorf("derived session: got %q", got)
	}
}

func TestShortIDExtractsTrailingTimestamp(t *testing.T) {
	cases := []struct {
		id, want string
	}{
		{"go-add-feature-1730000000", "1730000000"},
		{"go-1730000000", "1730000000"},
		{"weird", "weird"},
	}
	for _, c := range cases {
		got := Run{ID: c.id}.ShortID()
		if got != c.want {
			t.Errorf("ShortID(%q)=%q want %q", c.id, got, c.want)
		}
	}
}

func TestSortedRoleNamesByIterationThenRank(t *testing.T) {
	roles := map[string]Role{
		"reviewer-2":    {ID: "reviewer-2"},
		"executor-1":    {ID: "executor-1"},
		"planner-1":     {ID: "planner-1"},
		"re_reviewer-1": {ID: "re_reviewer-1"},
		"reviewer-1":    {ID: "reviewer-1"},
		"executor-2":    {ID: "executor-2"},
	}
	got := SortedRoleNames(roles)
	want := []string{
		"planner-1", "executor-1", "reviewer-1", "re_reviewer-1",
		"executor-2", "reviewer-2",
	}
	if len(got) != len(want) {
		t.Fatalf("len: got %d want %d (%+v)", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("pos %d: got %q want %q (full=%v)", i, got[i], want[i], got)
		}
	}
}

func TestLoadManifestDecodesRunnerAndIterations(t *testing.T) {
	root := withRunsRoot(t)

	writeJSON(t, filepath.Join(root, "go-x", "manifest.json"), map[string]any{
		"id":         "go-x",
		"kind":       "go",
		"phase":      "reviewing",
		"created_at": "2026-05-01T00:00:00Z",
		"runner": map[string]any{
			"pid":          1234,
			"host":         "macbook",
			"started_at":   "2026-05-01T00:01:00Z",
			"heartbeat_at": "2026-05-01T00:02:00Z",
			"alive":        true,
		},
		"iterations": []any{
			map[string]any{
				"n":              1,
				"phase":          "review",
				"executor_id":    "executor-1",
				"reviewer_id":    "reviewer-1",
				"verdict":        nil,
				"task":           "first task",
				"primary_verdict": "approve",
			},
		},
		"roles": map[string]any{
			"executor-1": map[string]any{
				"id":     "executor-1",
				"status": "completed",
				"output": "/tmp/out.txt",
			},
		},
	})

	r, err := LoadRun("go-x")
	if err != nil {
		t.Fatalf("LoadRun: %v", err)
	}
	if r.Runner == nil || r.Runner.PID != 1234 || !r.Runner.Alive {
		t.Errorf("runner not decoded: %+v", r.Runner)
	}
	if len(r.Iterations) != 1 || r.Iterations[0].Phase != "review" {
		t.Errorf("iterations not decoded: %+v", r.Iterations)
	}
	if r.Iterations[0].PrimaryVerdict != "approve" {
		t.Errorf("primary_verdict not decoded: got %q", r.Iterations[0].PrimaryVerdict)
	}
	role, ok := r.Roles["executor-1"]
	if !ok {
		t.Fatalf("executor-1 not in roles: %+v", r.Roles)
	}
	if role.Status != "completed" || role.OutputPath != "/tmp/out.txt" {
		t.Errorf("role decode: %+v", role)
	}
}

func TestRunsRootFallsBackThroughEnv(t *testing.T) {
	t.Setenv("RALPH_STATE_HOME", "")
	t.Setenv("XDG_STATE_HOME", "/tmp/some-xdg")

	if got, want := RunsRoot(), "/tmp/some-xdg/ralph/runs"; got != want {
		t.Errorf("XDG fallback: got %q want %q", got, want)
	}

	t.Setenv("RALPH_STATE_HOME", "/tmp/explicit")
	if got, want := RunsRoot(), "/tmp/explicit/runs"; got != want {
		t.Errorf("RALPH override: got %q want %q", got, want)
	}
}
