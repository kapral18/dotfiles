// Package cmds wraps `,ralph` subprocess invocations as bubbletea Commands.
//
// All mutating actions in the TUI go through `,ralph` so the orchestrator's
// own validation, manifest writes, and side effects stay authoritative. The
// TUI never edits manifest files directly.
package cmds

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"sort"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"ralph-tui/internal/state"
)

// --- messages ---------------------------------------------------------------

// RunsLoadedMsg carries a fresh slice of runs after a LoadRunsCmd completes.
type RunsLoadedMsg struct {
	Runs []state.Run
	Err  error
}

// RunReloadedMsg carries an updated single run (after fsnotify said it changed).
type RunReloadedMsg struct {
	ID  string
	Run state.Run
	Err error
}

// CmdResultMsg is the generic outcome of any `,ralph` mutating call.
type CmdResultMsg struct {
	Action  string // "verify" | "control" | "kill" | "rm" | "resume" | "replan" | "go"
	Target  string // run id (or rid:role)
	Stdout  string
	Stderr  string
	Code    int
	Elapsed time.Duration
}

// AttachMsg signals the app to exit the TUI and switch the user into a tmux
// session/pane via `tmux switch-client`. The Tea program returns from Run()
// and `main` runs the switch as a follow-on.
type AttachMsg struct {
	SessionTarget string // tmux target like "ralph-<short-rid>" or "ralph-<rid>:executor-1"
}

// QuitMsg requests a clean exit.
type QuitMsg struct{}

// --- commands ---------------------------------------------------------------

// LoadRunsCmd reads every parent manifest from disk.
//
// Returns a tea.Cmd suitable for Init() and for periodic refresh. The TUI
// fires this on startup and after every WatcherTickMsg that touched a
// manifest path.
func LoadRunsCmd() tea.Cmd {
	return func() tea.Msg {
		runs, err := state.LoadRuns()
		return RunsLoadedMsg{Runs: runs, Err: err}
	}
}

// LoadRunCmd re-reads a single run by id.
func LoadRunCmd(id string) tea.Cmd {
	return func() tea.Msg {
		r, err := state.LoadRun(id)
		return RunReloadedMsg{ID: id, Run: r, Err: err}
	}
}

// VerifyCmd shells out to `,ralph verify <rid>` and reports the result.
func VerifyCmd(rid string) tea.Cmd {
	return ralphCmd("verify", rid, []string{"verify", rid})
}

// ControlCmd issues `,ralph control <rid> --role <role> --action <act>`.
func ControlCmd(rid, role, action string) tea.Cmd {
	target := rid + ":" + role
	return ralphCmd("control", target, []string{"control", rid, "--role", role, "--action", action})
}

// KillCmd issues `,ralph kill <rid>` (or with --role for a single role).
func KillCmd(rid, role string) tea.Cmd {
	args := []string{"kill", rid}
	target := rid
	if role != "" {
		args = append(args, "--role", role)
		target = rid + ":" + role
	}
	return ralphCmd("kill", target, args)
}

// RemoveCmd issues `,ralph rm <rid>` (drops the run dir + ai-kb capsules).
func RemoveCmd(rid string) tea.Cmd {
	return ralphCmd("rm", rid, []string{"rm", rid})
}

// ResumeCmd issues `,ralph resume <rid>` (no-op if alive or terminal).
func ResumeCmd(rid string) tea.Cmd {
	return ralphCmd("resume", rid, []string{"resume", rid})
}

// ReplanCmd issues `,ralph replan <rid>` (auto-resumes if not alive).
func ReplanCmd(rid string) tea.Cmd {
	return ralphCmd("replan", rid, []string{"replan", rid})
}

// NewRunCmd kicks off a fresh `,ralph go --goal "..."` (detached by default
// when caller's $TMUX is set, which is the popup's environment).
//
// roleOverrides is keyed by role ("planner" | "executor" | "reviewer" |
// "re_reviewer") and maps to a {Harness, Model} pair. Empty fields are
// skipped (server falls back to roles.json). nil/empty map = no overrides.
//
// workflow is the operator's chosen workflow id ("feature" | "bugfix" |
// "review" | "research"). Empty string = no hint (the planner picks). The
// flag is forwarded as `--workflow=<id>` and surfaces to the planner via
// the `## OPERATOR HINT` block in scripts/ralph.py:_planner_context.
func NewRunCmd(goal, workspace string, planOnly bool, workflow string, roleOverrides map[string]state.RoleSpec) tea.Cmd {
	args := []string{"go", "--goal", goal}
	if workspace != "" {
		args = append(args, "--workspace", workspace)
	}
	if planOnly {
		args = append(args, "--plan-only")
	}
	if workflow != "" {
		args = append(args, "--workflow", workflow)
	}
	for _, role := range []string{"planner", "executor", "reviewer", "re_reviewer"} {
		spec, ok := roleOverrides[role]
		if !ok {
			continue
		}
		flagRole := strings.ReplaceAll(role, "_", "-")
		if spec.Harness != "" {
			args = append(args, "--"+flagRole+"-harness", spec.Harness)
		}
		if spec.Model != "" {
			args = append(args, "--"+flagRole+"-model", spec.Model)
		}
	}
	return ralphCmd("go", goal, args)
}

// AnswerCmd records human answers for an awaiting_human run. It pipes a
// JSON object {questionID: answerText, ...} to `,ralph answer <rid>
// --json -`, which the orchestrator consumes via stdin.
//
// Empty answers maps cause an immediate error result (the CLI rejects them
// anyway). Each key must be a question id present in manifest.questions[];
// the CLI emits a non-zero exit otherwise and the toast surfaces stderr.
func AnswerCmd(rid string, answers map[string]string) tea.Cmd {
	return func() tea.Msg {
		start := time.Now()
		if len(answers) == 0 {
			return CmdResultMsg{
				Action: "answer", Target: rid,
				Stderr:  "no answers provided",
				Code:    -1,
				Elapsed: time.Since(start),
			}
		}
		payload, err := encodeAnswers(answers)
		if err != nil {
			return CmdResultMsg{
				Action: "answer", Target: rid,
				Stderr: err.Error(), Code: -1,
				Elapsed: time.Since(start),
			}
		}
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		bin := ralphBinary()
		args := []string{"answer", rid, "--json", "-"}
		cmd := exec.CommandContext(ctx, bin, args...)
		cmd.Env = os.Environ()
		cmd.Stdin = strings.NewReader(payload)
		var stdout, stderr strings.Builder
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr
		runErr := cmd.Run()
		code := 0
		if runErr != nil {
			if exitErr, ok := runErr.(*exec.ExitError); ok {
				code = exitErr.ExitCode()
			} else {
				code = -1
			}
		}
		return CmdResultMsg{
			Action:  "answer",
			Target:  rid,
			Stdout:  stdout.String(),
			Stderr:  stderr.String(),
			Code:    code,
			Elapsed: time.Since(start),
		}
	}
}

// encodeAnswers marshals answers with sorted keys so the rendered JSON is
// deterministic (helps testing and produces stable diffs in `,ralph` logs).
func encodeAnswers(answers map[string]string) (string, error) {
	keys := make([]string, 0, len(answers))
	for k := range answers {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	ordered := make([][2]string, 0, len(keys))
	for _, k := range keys {
		ordered = append(ordered, [2]string{k, answers[k]})
	}
	var b strings.Builder
	b.WriteByte('{')
	for i, kv := range ordered {
		if i > 0 {
			b.WriteByte(',')
		}
		kb, err := json.Marshal(kv[0])
		if err != nil {
			return "", err
		}
		vb, err := json.Marshal(kv[1])
		if err != nil {
			return "", err
		}
		b.Write(kb)
		b.WriteByte(':')
		b.Write(vb)
	}
	b.WriteByte('}')
	return b.String(), nil
}

// AttachCmdAction emits an AttachMsg so main() can shell out to tmux
// switch-client after the TUI exits cleanly.
func AttachCmdAction(target string) tea.Cmd {
	return func() tea.Msg { return AttachMsg{SessionTarget: target} }
}

// KBHit mirrors one row from `,ai-kb search ... --json`. Decoupled from
// state.* so the cmds package owns the wire shape; the kb modal reads
// these directly.
type KBHit struct {
	ID            string  `json:"id"`
	Title         string  `json:"title"`
	Body          string  `json:"body"`
	Snippet       string  `json:"snippet"`
	Source        string  `json:"source"`
	Kind          string  `json:"kind"`
	Scope         string  `json:"scope"`
	WorkspacePath *string `json:"workspace_path"`
	DomainTags    string  `json:"domain_tags"`
	Confidence    float64 `json:"confidence"`
	BM25Rank      *int    `json:"bm25_rank"`
	VectorRank    *int    `json:"vector_rank"`
	BM25Score     *float64 `json:"bm25_score"`
	CosineScore   *float64 `json:"cosine_score"`
	RRFScore      float64 `json:"rrf_score"`
	MMRSelected   bool    `json:"mmr_selected"`
}

// KBSearchMsg carries a knowledge-base search response from the TUI's
// `K` modal back to the app. Exactly one of Hits / Err is non-zero.
type KBSearchMsg struct {
	Query   string
	Hits    []KBHit
	Err     error
	Elapsed time.Duration
}

// KBSearchCmd shells out to `,ai-kb search "<query>" --json --limit N`.
//
// Identical to how a role would invoke the KB at runtime — the TUI
// uses the same binary surface roles do, so the modal is also a
// dogfood probe of the memory-as-tool boundary. Soft-fails: any
// non-zero exit or unparseable JSON returns an error in KBSearchMsg
// rather than panicking the program.
func KBSearchCmd(query string, limit int) tea.Cmd {
	return func() tea.Msg {
		if strings.TrimSpace(query) == "" {
			return KBSearchMsg{Query: query, Hits: nil}
		}
		if limit <= 0 {
			limit = 10
		}
		bin := aiKBBinary()
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		start := time.Now()
		args := []string{"search", query, "--limit", fmt.Sprintf("%d", limit), "--json"}
		cmd := exec.CommandContext(ctx, bin, args...)
		cmd.Env = os.Environ()
		var stdout, stderr strings.Builder
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr
		err := cmd.Run()
		elapsed := time.Since(start)
		if err != nil {
			msg := strings.TrimSpace(stderr.String())
			if msg == "" {
				msg = err.Error()
			}
			return KBSearchMsg{Query: query, Err: fmt.Errorf("%s", msg), Elapsed: elapsed}
		}
		var hits []KBHit
		if jerr := json.Unmarshal([]byte(stdout.String()), &hits); jerr != nil {
			return KBSearchMsg{Query: query, Err: jerr, Elapsed: elapsed}
		}
		return KBSearchMsg{Query: query, Hits: hits, Elapsed: elapsed}
	}
}

// KBStatsMsg carries quick KB summary numbers for the status bar.
type KBStatsMsg struct {
	Capsules int
	Docs     int
	Err      error
}

// KBStatsCmd reads `,ai-kb doctor` and parses the `capsules=N` line.
//
// The TUI calls this on startup and on a slow tick; the result feeds
// the `KB:N` status segment so the operator sees how much knowledge
// the swarm has accumulated without opening the modal.
func KBStatsCmd() tea.Cmd {
	return func() tea.Msg {
		bin := aiKBBinary()
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, bin, "doctor")
		cmd.Env = os.Environ()
		var stdout strings.Builder
		cmd.Stdout = &stdout
		if err := cmd.Run(); err != nil {
			return KBStatsMsg{Err: err}
		}
		stats := KBStatsMsg{}
		for _, line := range strings.Split(stdout.String(), "\n") {
			if v, ok := strings.CutPrefix(line, "capsules="); ok {
				if n, err := parseUint(v); err == nil {
					stats.Capsules = n
				}
			}
		}
		return stats
	}
}

func parseUint(s string) (int, error) {
	s = strings.TrimSpace(s)
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0, fmt.Errorf("not a uint: %q", s)
		}
		n = n*10 + int(c-'0')
	}
	return n, nil
}

func aiKBBinary() string {
	if v := os.Getenv("AI_KB_BIN"); v != "" {
		return v
	}
	if path, err := exec.LookPath(",ai-kb"); err == nil {
		return path
	}
	if home, err := os.UserHomeDir(); err == nil {
		guess := home + "/bin/,ai-kb"
		if _, err := os.Stat(guess); err == nil {
			return guess
		}
	}
	return ",ai-kb"
}

// --- internals --------------------------------------------------------------

func ralphCmd(action, target string, args []string) tea.Cmd {
	return func() tea.Msg {
		bin := ralphBinary()
		ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
		defer cancel()
		start := time.Now()
		cmd := exec.CommandContext(ctx, bin, args...)
		cmd.Env = os.Environ()
		var stdout, stderr strings.Builder
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr
		err := cmd.Run()
		code := 0
		if err != nil {
			if exitErr, ok := err.(*exec.ExitError); ok {
				code = exitErr.ExitCode()
			} else {
				code = -1
			}
		}
		return CmdResultMsg{
			Action:  action,
			Target:  target,
			Stdout:  stdout.String(),
			Stderr:  stderr.String(),
			Code:    code,
			Elapsed: time.Since(start),
		}
	}
}

func ralphBinary() string {
	if v := os.Getenv("RALPH_BIN"); v != "" {
		return v
	}
	if path, err := exec.LookPath(",ralph"); err == nil {
		return path
	}
	// Last resort: assume the chezmoi-deployed path.
	if home, err := os.UserHomeDir(); err == nil {
		guess := home + "/bin/,ralph"
		if _, err := os.Stat(guess); err == nil {
			return guess
		}
	}
	return ",ralph"
}

// FormatResult renders a CmdResultMsg into a single-line summary suitable
// for a tmux display-message style toast.
func FormatResult(m CmdResultMsg) string {
	if m.Code == 0 {
		return fmt.Sprintf("%s %s ok (%s)", m.Action, m.Target, m.Elapsed.Round(time.Millisecond))
	}
	first := strings.TrimSpace(m.Stderr)
	if first == "" {
		first = strings.TrimSpace(m.Stdout)
	}
	if i := strings.IndexByte(first, '\n'); i >= 0 {
		first = first[:i]
	}
	if first == "" {
		first = fmt.Sprintf("exit=%d", m.Code)
	}
	return fmt.Sprintf("%s %s FAILED: %s", m.Action, m.Target, first)
}
