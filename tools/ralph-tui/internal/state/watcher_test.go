package state

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestWatcherAbsentRootStartsOnNearestExistingParent(t *testing.T) {
	root := withRunsRoot(t)

	w, err := NewWatcher()
	if err != nil {
		t.Fatalf("NewWatcher: %v", err)
	}
	t.Cleanup(func() { _ = w.Close() })

	parent := filepath.Dir(root)
	waitForWatch(t, w, parent)
	if hasWatchEntry(w, root) {
		t.Fatalf("unexpected root watch before creation: %q in %v", root, w.w.WatchList())
	}
	waitNoEvent(t, w.Events(), 150*time.Millisecond)
}

func TestWatcherPicksUpLateCreatedRootAndRun(t *testing.T) {
	root := withRunsRoot(t)

	w, err := NewWatcher()
	if err != nil {
		t.Fatalf("NewWatcher: %v", err)
	}
	t.Cleanup(func() { _ = w.Close() })

	if err := os.MkdirAll(root, 0o755); err != nil {
		t.Fatalf("mkdir root: %v", err)
	}
	waitForWatch(t, w, root)

	runDir := filepath.Join(root, "go-late")
	if err := os.MkdirAll(runDir, 0o755); err != nil {
		t.Fatalf("mkdir run: %v", err)
	}
	waitForEventPath(t, w.Events(), runDir)
	waitForWatch(t, w, runDir)

	manifest := filepath.Join(runDir, "manifest.json")
	writeJSON(t, manifest, map[string]any{
		"id":         "go-late",
		"kind":       "go",
		"created_at": "2026-07-10T00:00:00Z",
	})
	waitForEventPath(t, w.Events(), manifest)
}

func TestWatcherExistingRootWatchesExistingRuns(t *testing.T) {
	root := withRunsRoot(t)
	manifest := filepath.Join(root, "go-existing", "manifest.json")
	writeJSON(t, manifest, map[string]any{
		"id":         "go-existing",
		"kind":       "go",
		"created_at": "2026-07-10T00:00:00Z",
	})

	w, err := NewWatcher()
	if err != nil {
		t.Fatalf("NewWatcher: %v", err)
	}
	t.Cleanup(func() { _ = w.Close() })

	waitForWatch(t, w, root)
	waitForWatch(t, w, filepath.Dir(manifest))

	writeJSON(t, manifest, map[string]any{
		"id":         "go-existing",
		"kind":       "go",
		"phase":      "reviewing",
		"created_at": "2026-07-10T00:00:00Z",
	})
	waitForEventPath(t, w.Events(), manifest)
}

func TestWatcherCloseClosesEvents(t *testing.T) {
	root := withRunsRoot(t)
	if err := os.MkdirAll(root, 0o755); err != nil {
		t.Fatalf("mkdir root: %v", err)
	}

	w, err := NewWatcher()
	if err != nil {
		t.Fatalf("NewWatcher: %v", err)
	}

	if err := w.Close(); err != nil {
		t.Fatalf("Close: %v", err)
	}

	timer := time.NewTimer(2 * time.Second)
	defer timer.Stop()
	for {
		select {
		case _, ok := <-w.Events():
			if !ok {
				return
			}
		case <-timer.C:
			t.Fatal("events channel did not close")
		}
	}
}

func TestWatcherAvoidsDuplicateRunWatchesOnLateCreation(t *testing.T) {
	root := withRunsRoot(t)

	w, err := NewWatcher()
	if err != nil {
		t.Fatalf("NewWatcher: %v", err)
	}
	t.Cleanup(func() { _ = w.Close() })

	runDir := filepath.Join(root, "go-dup")
	if err := os.MkdirAll(runDir, 0o755); err != nil {
		t.Fatalf("mkdir run tree: %v", err)
	}
	waitForWatch(t, w, runDir)

	if got := countWatchEntries(w, runDir); got != 1 {
		t.Fatalf("run dir watched %d times, want 1 (watchlist=%v)", got, w.w.WatchList())
	}
}

func waitForWatch(t *testing.T, w *Watcher, path string) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	path = filepath.Clean(path)
	for time.Now().Before(deadline) {
		if hasWatchEntry(w, path) {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("watch for %q not installed; watchlist=%v", path, w.w.WatchList())
}

func hasWatchEntry(w *Watcher, path string) bool {
	return countWatchEntries(w, path) > 0
}

func countWatchEntries(w *Watcher, path string) int {
	path = filepath.Clean(path)
	count := 0
	for _, watched := range w.w.WatchList() {
		if filepath.Clean(watched) == path {
			count++
		}
	}
	return count
}

func waitForEventPath(t *testing.T, events <-chan WatchEvent, path string) {
	t.Helper()
	timer := time.NewTimer(2 * time.Second)
	defer timer.Stop()
	path = filepath.Clean(path)
	for {
		select {
		case ev, ok := <-events:
			if !ok {
				t.Fatal("events channel closed before expected event")
			}
			if filepath.Clean(ev.Path) == path {
				return
			}
		case <-timer.C:
			t.Fatalf("timed out waiting for event on %q", path)
		}
	}
}

func waitNoEvent(t *testing.T, events <-chan WatchEvent, d time.Duration) {
	t.Helper()
	select {
	case ev, ok := <-events:
		if !ok {
			t.Fatal("events channel closed unexpectedly")
		}
		t.Fatalf("unexpected event: %+v", ev)
	case <-time.After(d):
	}
}
