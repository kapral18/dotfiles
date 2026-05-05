// Package activity provides a cross-run event aggregator for the TUI's
// activity stream drawer.
//
// The orchestrator writes two artifact families per run:
//   - decisions.log: free-text orchestrator events (one line per decision)
//   - verdicts.jsonl: per-iteration reviewer/re_reviewer verdicts (one
//     JSON object per line)
//
// Both are append-only, mtime-monotonic. We scan every run directory under
// state.RunsRoot(), parse trailing entries, and return a unified, recency-
// sorted Event slice. Designed for cheap re-reads on every tick: capped
// per-file via tail-bytes, so giant logs never bottleneck the render path.
package activity

import (
	"bufio"
	"encoding/json"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"ralph-tui/internal/state"
)

// Event is a single cross-run activity item.
type Event struct {
	// RunID is the parent (kind="go") run that emitted the event.
	RunID string
	// At is the wall-clock time the event was recorded. May be zero if
	// the source line had no parseable timestamp; in that case the file
	// mtime is used as a fallback so the event still sorts approximately.
	At time.Time
	// Kind narrows what the message body means.
	Kind EventKind
	// Message is a human-readable summary suitable for one-line display.
	Message string
}

// EventKind tags the source of an Event.
type EventKind string

const (
	KindDecision EventKind = "decision"
	KindVerdict  EventKind = "verdict"
)

// LoadRecent walks every run dir under state.RunsRoot() and returns up
// to `limit` events sorted by At descending (most recent first). Errors
// reading individual run dirs are swallowed: the activity stream is a
// best-effort surface and must never block the render path.
func LoadRecent(limit int) []Event {
	if limit <= 0 {
		return nil
	}
	root := state.RunsRoot()
	entries, err := os.ReadDir(root)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil
		}
		return nil
	}
	events := make([]Event, 0, limit*2)
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		// Only parent (kind=go) runs surface in the activity stream;
		// child role manifests double-emit verdicts which would clutter.
		manifest := filepath.Join(root, e.Name(), "manifest.json")
		if !isParentRun(manifest) {
			continue
		}
		events = append(events, scanDecisions(filepath.Join(root, e.Name()), e.Name())...)
		events = append(events, scanVerdicts(filepath.Join(root, e.Name()), e.Name())...)
	}
	sort.SliceStable(events, func(i, j int) bool {
		return events[i].At.After(events[j].At)
	})
	if len(events) > limit {
		events = events[:limit]
	}
	return events
}

// isParentRun returns true when manifest.json declares kind="go". Child
// role manifests (kind="role") share the same root directory but should
// not contribute to the activity stream.
func isParentRun(path string) bool {
	f, err := os.Open(path)
	if err != nil {
		return false
	}
	defer f.Close()
	var probe struct {
		Kind string `json:"kind"`
	}
	if err := json.NewDecoder(f).Decode(&probe); err != nil {
		return false
	}
	return probe.Kind == "go"
}

// scanDecisions reads the trailing N lines of decisions.log and converts
// each into an Event. decisions.log is plain text; the orchestrator does
// not prepend timestamps, so we use the file's mtime as a stable but
// approximate clock — good enough for "most recent first" sort.
func scanDecisions(dir, runID string) []Event {
	path := filepath.Join(dir, "decisions.log")
	st, err := os.Stat(path)
	if err != nil {
		return nil
	}
	mtime := st.ModTime()
	lines := tailLines(path, 8, 8*1024)
	out := make([]Event, 0, len(lines))
	for _, ln := range lines {
		ln = strings.TrimSpace(ln)
		if ln == "" {
			continue
		}
		out = append(out, Event{
			RunID:   runID,
			At:      mtime,
			Kind:    KindDecision,
			Message: ln,
		})
	}
	return out
}

// scanVerdicts reads the trailing N lines of verdicts.jsonl. Each line is
// a JSON object with a `role`, an `iter` (or `n`), and a `verdict` field.
// We surface a compact "iter N · role · verdict" form so multiple verdicts
// from the same iteration stack readably in the drawer.
func scanVerdicts(dir, runID string) []Event {
	path := filepath.Join(dir, "verdicts.jsonl")
	st, err := os.Stat(path)
	if err != nil {
		return nil
	}
	mtime := st.ModTime()
	lines := tailLines(path, 8, 16*1024)
	out := make([]Event, 0, len(lines))
	for _, ln := range lines {
		var rec map[string]any
		if err := json.Unmarshal([]byte(ln), &rec); err != nil {
			continue
		}
		role, _ := rec["role"].(string)
		verdict, _ := rec["verdict"].(string)
		if verdict == "" {
			if v, ok := rec["final_verdict"].(string); ok {
				verdict = v
			}
		}
		iter := iterField(rec)
		msg := joinNonEmpty(" · ", iterPrefix(iter), role, verdict)
		if msg == "" {
			continue
		}
		out = append(out, Event{
			RunID:   runID,
			At:      mtime,
			Kind:    KindVerdict,
			Message: msg,
		})
	}
	return out
}

func iterField(rec map[string]any) int {
	if v, ok := rec["iter"]; ok {
		switch n := v.(type) {
		case float64:
			return int(n)
		case int:
			return n
		}
	}
	if v, ok := rec["n"]; ok {
		switch n := v.(type) {
		case float64:
			return int(n)
		case int:
			return n
		}
	}
	return 0
}

func iterPrefix(n int) string {
	if n <= 0 {
		return ""
	}
	return "iter " + intToString(n)
}

func intToString(n int) string {
	if n == 0 {
		return "0"
	}
	digits := []byte{}
	if n < 0 {
		n = -n
	}
	for n > 0 {
		digits = append([]byte{byte('0' + n%10)}, digits...)
		n /= 10
	}
	return string(digits)
}

func joinNonEmpty(sep string, parts ...string) string {
	out := []string{}
	for _, p := range parts {
		if p == "" {
			continue
		}
		out = append(out, p)
	}
	return strings.Join(out, sep)
}

// tailLines returns the last `n` non-empty lines from the file at `path`,
// reading at most `cap` trailing bytes to keep the operation cheap.
func tailLines(path string, n int, cap int64) []string {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil || st.Size() == 0 {
		return nil
	}
	size := st.Size()
	if size > cap {
		_, err := f.Seek(size-cap, 0)
		if err != nil {
			return nil
		}
	}
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 0, 8*1024), 1024*1024)
	all := make([]string, 0, 64)
	for scanner.Scan() {
		all = append(all, scanner.Text())
	}
	if len(all) > n {
		all = all[len(all)-n:]
	}
	return all
}

// FormatLine renders an Event into a single line suitable for a status
// strip: shortened run id, kind glyph, then the message.
func FormatLine(ev Event, runIDWidth int) string {
	short := ev.RunID
	if i := strings.LastIndex(short, "-"); i >= 0 && i+1 < len(short) {
		short = short[i+1:]
	}
	if len(short) > runIDWidth && runIDWidth > 1 {
		short = short[:runIDWidth-1] + "…"
	}
	glyph := "·"
	switch ev.Kind {
	case KindDecision:
		glyph = "d"
	case KindVerdict:
		glyph = "v"
	}
	return short + " " + glyph + " " + ev.Message
}
