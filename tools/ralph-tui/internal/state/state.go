// Package state reads Ralph run state from the on-disk manifest tree.
//
// All fields are decoded best-effort: older manifests (before the resumable
// state-machine refactor) lack a `runner` block and per-iteration `phase`
// tags. Decoders default missing fields rather than erroring, so the TUI
// stays usable while the orchestrator is being developed.
package state

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// RunsRoot returns the directory under which per-run state lives.
//
// Resolution order:
//  1. $RALPH_STATE_HOME/runs (explicit override)
//  2. $XDG_STATE_HOME/ralph/runs
//  3. $HOME/.local/state/ralph/runs
func RunsRoot() string {
	if v := os.Getenv("RALPH_STATE_HOME"); v != "" {
		return filepath.Join(v, "runs")
	}
	if v := os.Getenv("XDG_STATE_HOME"); v != "" {
		return filepath.Join(v, "ralph", "runs")
	}
	if home, err := os.UserHomeDir(); err == nil {
		return filepath.Join(home, ".local", "state", "ralph", "runs")
	}
	return filepath.Join(".", ".ralph", "runs")
}

// Run is the TUI-shaped projection of a parent (kind="go") manifest.
type Run struct {
	ID            string         `json:"id"`
	Kind          string         `json:"kind"`
	Name          string         `json:"name"`
	Goal          string         `json:"goal"`
	Workspace     string         `json:"workspace"`
	Phase         string         `json:"phase"`
	Status        string         `json:"status"`
	Validation    string         `json:"validation_status"`
	BlockReason   string         `json:"block_reason,omitempty"`
	Workflow      string         `json:"workflow,omitempty"`
	Spec          map[string]any `json:"spec,omitempty"`
	SpecSeq       int            `json:"spec_seq,omitempty"`
	CreatedAt     string         `json:"created_at"`
	Tmux          *RunTmux       `json:"tmux,omitempty"`
	Runner        *RunnerInfo    `json:"runner,omitempty"`
	Iterations    []Iteration    `json:"iterations"`
	Roles         map[string]Role
	Questions     []Question  `json:"questions,omitempty"`
	AwaitingRole  string      `json:"awaiting_role,omitempty"`
	SummaryPath   string      `json:"summary_path,omitempty"`
	Artifact      string      `json:"artifact,omitempty"`
	ArtifactSHA   string      `json:"artifact_sha256,omitempty"`
	ArtifactOK    bool        `json:"artifact_ok,omitempty"`
	ReplanQueued  bool        `json:"replan_requested,omitempty"`
	rawRoles      map[string]json.RawMessage
	dir           string
}

// Question mirrors an entry in manifest.questions[].
type Question struct {
	ID         string `json:"id"`
	Role       string `json:"role"`
	Text       string `json:"text"`
	AskedAt    string `json:"asked_at"`
	Answer     string `json:"answer,omitempty"`
	AnsweredAt string `json:"answered_at,omitempty"`
}

// IsAnswered reports whether the human has filled in the answer.
func (q Question) IsAnswered() bool {
	return q.AnsweredAt != "" && q.Answer != ""
}

// OpenQuestions returns the entries that still need a human answer.
func (r Run) OpenQuestions() []Question {
	out := make([]Question, 0, len(r.Questions))
	for _, q := range r.Questions {
		if !q.IsAnswered() {
			out = append(out, q)
		}
	}
	return out
}

// AwaitingHuman is true when the orchestrator parked at status=awaiting_human
// (open clarifying questions block the run from proceeding).
func (r Run) AwaitingHuman() bool {
	return r.Status == "awaiting_human"
}

// SummaryAvailable is true when the orchestrator wrote a per-run summary.md.
func (r Run) SummaryAvailable() bool {
	return r.SummaryPath != ""
}

// Dir returns the run's state directory (where manifest.json lives).
func (r Run) Dir() string { return r.dir }

// ShortID returns the trailing timestamp from the run's id (or the full id
// if there is no recognizable suffix). Used for compact UI labels.
func (r Run) ShortID() string {
	if i := strings.LastIndex(r.ID, "-"); i >= 0 && i+1 < len(r.ID) {
		return r.ID[i+1:]
	}
	return r.ID
}

// SessionName is the dedicated tmux session that hosts this run's role panes.
// Falls back to the manifest's recorded value, then to a deterministic guess
// derived from the run id (matches scripts/ralph.py's run_session_name).
func (r Run) SessionName() string {
	if r.Tmux != nil && r.Tmux.Session != "" {
		return r.Tmux.Session
	}
	return "ralph-" + r.ShortID()
}

// CreatedTime parses CreatedAt; zero on parse failure.
func (r Run) CreatedTime() time.Time {
	if r.CreatedAt == "" {
		return time.Time{}
	}
	t, err := time.Parse(time.RFC3339, r.CreatedAt)
	if err != nil {
		return time.Time{}
	}
	return t
}

// Age returns time since CreatedAt, or 0 if unparseable.
func (r Run) Age() time.Duration {
	t := r.CreatedTime()
	if t.IsZero() {
		return 0
	}
	return time.Since(t)
}

// RunTmux mirrors manifest.tmux.
type RunTmux struct {
	Session string `json:"session"`
}

// RunnerInfo mirrors manifest.runner — populated by the orchestrator at
// runner start, updated on heartbeat, cleared on clean exit.
type RunnerInfo struct {
	PID         int    `json:"pid,omitempty"`
	Host        string `json:"host,omitempty"`
	StartedAt   string `json:"started_at,omitempty"`
	HeartbeatAt string `json:"heartbeat_at,omitempty"`
	Alive       bool   `json:"alive,omitempty"`
}

// Iteration mirrors manifest.iterations[i].
type Iteration struct {
	N             int    `json:"n"`
	Phase         string `json:"phase"`
	Verdict       string `json:"verdict,omitempty"`
	ExecutorID    string `json:"executor_id,omitempty"`
	ReviewerID    string `json:"reviewer_id,omitempty"`
	ReReviewerID  string `json:"re_reviewer_id,omitempty"`
	Task          string `json:"task,omitempty"`
	NextTask      string `json:"next_task,omitempty"`
	StartedAt     string `json:"started_at,omitempty"`
	EndedAt       string `json:"ended_at,omitempty"`
	SpecSeq       int    `json:"spec_seq,omitempty"`
	PrimaryVerdict string `json:"primary_verdict,omitempty"`
}

// Role projects manifest.roles[name] (which is the child role manifest).
type Role struct {
	ID               string  `json:"id"`
	Name             string  `json:"name"`
	Status           string  `json:"status"`
	ValidationStatus string  `json:"validation_status"`
	ControlState     string  `json:"control_state"`
	OutputPath       string  `json:"output"`
	Workspace        string  `json:"workspace"`
	ExitCode         int     `json:"exit_code"`
	Tmux             *RoleTmux `json:"tmux,omitempty"`
	Command          string  `json:"command"`
	Runtime          string  `json:"runtime"`
}

// RoleTmux mirrors child manifest's tmux block.
type RoleTmux struct {
	Session string `json:"session"`
	Window  string `json:"window"`
	Pane    string `json:"pane"`
	Target  string `json:"target"`
	Alive   bool   `json:"alive"`
}

// LoadRuns reads every parent (kind="go") manifest under RunsRoot and returns
// them sorted newest-first.
func LoadRuns() ([]Run, error) {
	root := RunsRoot()
	entries, err := os.ReadDir(root)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil, nil
		}
		return nil, fmt.Errorf("read %s: %w", root, err)
	}
	var runs []Run
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		p := filepath.Join(root, e.Name(), "manifest.json")
		r, err := LoadManifest(p)
		if err != nil {
			continue // skip malformed
		}
		if r.Kind != "go" {
			continue // child role manifests live alongside parents; ignore
		}
		runs = append(runs, r)
	}
	sort.SliceStable(runs, func(i, j int) bool {
		ti := runs[i].CreatedTime()
		tj := runs[j].CreatedTime()
		if ti.Equal(tj) {
			return runs[i].ID > runs[j].ID
		}
		return ti.After(tj)
	})
	return runs, nil
}

// LoadManifest decodes a single parent manifest.json into a Run.
func LoadManifest(path string) (Run, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Run{}, err
	}
	var r Run
	if err := json.Unmarshal(raw, &r); err != nil {
		return Run{}, err
	}
	r.dir = filepath.Dir(path)
	// roles is a free-form map; decode it separately into Role values.
	var probe struct {
		Roles map[string]json.RawMessage `json:"roles"`
	}
	if err := json.Unmarshal(raw, &probe); err == nil && len(probe.Roles) > 0 {
		r.rawRoles = probe.Roles
		r.Roles = make(map[string]Role, len(probe.Roles))
		for k, v := range probe.Roles {
			var role Role
			if err := json.Unmarshal(v, &role); err == nil {
				r.Roles[k] = role
			}
		}
	}
	return r, nil
}

// SortedRoleNames returns role names ordered by iteration then role rank.
//
// Order: planner-1, executor-1, reviewer-1, re_reviewer-1, planner-2, ...
// This matches the orchestrator's lifecycle ordering.
func SortedRoleNames(roles map[string]Role) []string {
	names := make([]string, 0, len(roles))
	for k := range roles {
		names = append(names, k)
	}
	sort.SliceStable(names, func(i, j int) bool {
		ai, ar, aOK := splitRoleName(names[i])
		bi, br, bOK := splitRoleName(names[j])
		if !aOK || !bOK {
			return names[i] < names[j]
		}
		if ai != bi {
			return ai < bi
		}
		return roleRank(ar) < roleRank(br)
	})
	return names
}

func splitRoleName(s string) (iter int, role string, ok bool) {
	idx := strings.LastIndex(s, "-")
	if idx <= 0 || idx >= len(s)-1 {
		return 0, "", false
	}
	role = s[:idx]
	if _, err := fmt.Sscanf(s[idx+1:], "%d", &iter); err != nil {
		return 0, "", false
	}
	return iter, role, true
}

func roleRank(role string) int {
	switch role {
	case "planner":
		return 0
	case "executor":
		return 1
	case "reviewer":
		return 2
	case "re_reviewer":
		return 3
	default:
		return 9
	}
}

// LoadRun reads a specific run by id. Returns os.ErrNotExist if the manifest
// is missing.
func LoadRun(id string) (Run, error) {
	return LoadManifest(filepath.Join(RunsRoot(), id, "manifest.json"))
}
