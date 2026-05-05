package cmds

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"ralph-tui/internal/state"
)

func writeMockBinary(t *testing.T, body string) string {
	t.Helper()
	dir := t.TempDir()
	bin := filepath.Join(dir, "ralph-mock")
	if err := os.WriteFile(bin, []byte("#!/bin/sh\n"+body), 0o755); err != nil {
		t.Fatalf("write mock binary: %v", err)
	}
	return bin
}

func runCmd(t *testing.T, c tea.Cmd) tea.Msg {
	t.Helper()
	if c == nil {
		t.Fatal("nil tea.Cmd")
	}
	return c()
}

func TestRalphCmdSuccessReturnsZeroCode(t *testing.T) {
	bin := writeMockBinary(t, "echo hello\nexit 0\n")
	t.Setenv("RALPH_BIN", bin)

	msg := runCmd(t, VerifyCmd("test-rid"))

	res, ok := msg.(CmdResultMsg)
	if !ok {
		t.Fatalf("want CmdResultMsg, got %T (%+v)", msg, msg)
	}
	if res.Code != 0 {
		t.Errorf("code: got %d, stderr=%q", res.Code, res.Stderr)
	}
	if res.Action != "verify" {
		t.Errorf("action: %q", res.Action)
	}
	if res.Target != "test-rid" {
		t.Errorf("target: %q", res.Target)
	}
	if !strings.Contains(res.Stdout, "hello") {
		t.Errorf("stdout: %q", res.Stdout)
	}
}

func TestRalphCmdNonzeroBubblesUpExitCode(t *testing.T) {
	bin := writeMockBinary(t, "echo failed >&2\nexit 7\n")
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, KillCmd("rid", "")).(CmdResultMsg)
	if res.Code != 7 {
		t.Errorf("want code=7 got %d", res.Code)
	}
	if !strings.Contains(res.Stderr, "failed") {
		t.Errorf("stderr: %q", res.Stderr)
	}
}

func TestKillCmdAppendsRoleArg(t *testing.T) {
	bin := writeMockBinary(t, `printf '%s\n' "$@"; exit 0`)
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, KillCmd("rid", "executor-1")).(CmdResultMsg)
	want := "kill\nrid\n--role\nexecutor-1\n"
	if res.Stdout != want {
		t.Errorf("args mismatch:\nwant=%q\ngot =%q", want, res.Stdout)
	}
	if res.Target != "rid:executor-1" {
		t.Errorf("target=%q", res.Target)
	}
}

func TestNewRunCmdHandlesPlanOnlyAndWorkspace(t *testing.T) {
	bin := writeMockBinary(t, `printf '%s\n' "$@"; exit 0`)
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, NewRunCmd("ship feature", "/tmp/ws", true, "", nil)).(CmdResultMsg)
	want := "go\n--goal\nship feature\n--workspace\n/tmp/ws\n--plan-only\n"
	if res.Stdout != want {
		t.Errorf("args:\nwant=%q\ngot =%q", want, res.Stdout)
	}
}

func TestNewRunCmdEmitsWorkflowFlag(t *testing.T) {
	bin := writeMockBinary(t, `printf '%s\n' "$@"; exit 0`)
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, NewRunCmd("g", "", false, "research", nil)).(CmdResultMsg)
	want := "go\n--goal\ng\n--workflow\nresearch\n"
	if res.Stdout != want {
		t.Errorf("args:\nwant=%q\ngot =%q", want, res.Stdout)
	}
}

func TestNewRunCmdOmitsEmptyWorkflow(t *testing.T) {
	bin := writeMockBinary(t, `printf '%s\n' "$@"; exit 0`)
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, NewRunCmd("g", "", false, "", nil)).(CmdResultMsg)
	if strings.Contains(res.Stdout, "--workflow") {
		t.Errorf("empty workflow must not emit flag: %q", res.Stdout)
	}
}

func TestNewRunCmdEmitsRoleOverrideFlagsInOrder(t *testing.T) {
	bin := writeMockBinary(t, `printf '%s\n' "$@"; exit 0`)
	t.Setenv("RALPH_BIN", bin)

	overrides := map[string]state.RoleSpec{
		"planner":     {Harness: "cursor", Model: "claude-opus-4-7-thinking-max"},
		"executor":    {Harness: "pi", Model: "composer-2"},
		"reviewer":    {Harness: "cursor", Model: "claude-opus-4-7-thinking-max"},
		"re_reviewer": {Harness: "cursor", Model: "gpt-5.5-extra-high"},
	}
	res := runCmd(t, NewRunCmd("g", "", false, "", overrides)).(CmdResultMsg)
	want := strings.Join([]string{
		"go", "--goal", "g",
		"--planner-harness", "cursor", "--planner-model", "claude-opus-4-7-thinking-max",
		"--executor-harness", "pi", "--executor-model", "composer-2",
		"--reviewer-harness", "cursor", "--reviewer-model", "claude-opus-4-7-thinking-max",
		"--re-reviewer-harness", "cursor", "--re-reviewer-model", "gpt-5.5-extra-high",
	}, "\n") + "\n"
	if res.Stdout != want {
		t.Errorf("args:\nwant=%q\ngot =%q", want, res.Stdout)
	}
}

func TestNewRunCmdSkipsEmptyRoleFields(t *testing.T) {
	bin := writeMockBinary(t, `printf '%s\n' "$@"; exit 0`)
	t.Setenv("RALPH_BIN", bin)

	overrides := map[string]state.RoleSpec{
		"planner":  {Model: "only-model"},
		"reviewer": {Harness: "pi"},
	}
	res := runCmd(t, NewRunCmd("g", "", false, "", overrides)).(CmdResultMsg)
	want := strings.Join([]string{
		"go", "--goal", "g",
		"--planner-model", "only-model",
		"--reviewer-harness", "pi",
	}, "\n") + "\n"
	if res.Stdout != want {
		t.Errorf("args:\nwant=%q\ngot =%q", want, res.Stdout)
	}
}


func TestAnswerCmdRejectsEmptyAnswers(t *testing.T) {
	bin := writeMockBinary(t, `exit 0`)
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, AnswerCmd("rid-x", nil)).(CmdResultMsg)
	if res.Code == 0 {
		t.Errorf("empty answers must produce non-zero code, got %d", res.Code)
	}
	if !strings.Contains(res.Stderr, "no answers") {
		t.Errorf("expected explanatory stderr, got %q", res.Stderr)
	}
}

func TestAnswerCmdPipesSortedJSONOnStdin(t *testing.T) {
	// The mock prints argv (one per line) followed by the entire stdin so
	// the test can assert both pieces in one round-trip.
	bin := writeMockBinary(t, `printf '%s\n' "$@"; printf '\nSTDIN:'; cat`)
	t.Setenv("RALPH_BIN", bin)

	answers := map[string]string{
		"q-2": "second",
		"q-1": "first",
	}
	res := runCmd(t, AnswerCmd("rid-x", answers)).(CmdResultMsg)
	if res.Code != 0 {
		t.Fatalf("code=%d stderr=%q", res.Code, res.Stderr)
	}
	wantArgs := "answer\nrid-x\n--json\n-\n"
	if !strings.HasPrefix(res.Stdout, wantArgs) {
		t.Errorf("argv prefix mismatch:\nwant prefix=%q\ngot=%q", wantArgs, res.Stdout)
	}
	if !strings.Contains(res.Stdout, `STDIN:{"q-1":"first","q-2":"second"}`) {
		t.Errorf("stdin payload missing or wrong order: %q", res.Stdout)
	}
	if res.Action != "answer" || res.Target != "rid-x" {
		t.Errorf("action/target: %+v", res)
	}
}

func TestAnswerCmdPropagatesNonzeroExit(t *testing.T) {
	bin := writeMockBinary(t, `cat >/dev/null; printf 'unknown qid\n' >&2; exit 4`)
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, AnswerCmd("rid-x", map[string]string{"q-1": "ans"})).(CmdResultMsg)
	if res.Code != 4 {
		t.Errorf("code: got %d want 4", res.Code)
	}
	if !strings.Contains(res.Stderr, "unknown qid") {
		t.Errorf("stderr: %q", res.Stderr)
	}
}

func TestEncodeAnswersIsDeterministic(t *testing.T) {
	answers := map[string]string{"b": "2", "a": "1", "c": "3"}
	got, err := encodeAnswers(answers)
	if err != nil {
		t.Fatalf("encodeAnswers: %v", err)
	}
	want := `{"a":"1","b":"2","c":"3"}`
	if got != want {
		t.Errorf("encode:\nwant=%q\ngot =%q", want, got)
	}
}

func TestControlCmdComposesTarget(t *testing.T) {
	bin := writeMockBinary(t, `exit 0`)
	t.Setenv("RALPH_BIN", bin)

	res := runCmd(t, ControlCmd("rid", "reviewer-1", "takeover")).(CmdResultMsg)
	if res.Target != "rid:reviewer-1" {
		t.Errorf("target=%q", res.Target)
	}
}

func TestAttachCmdActionEmitsAttachMsg(t *testing.T) {
	msg := runCmd(t, AttachCmdAction("ralph-foo"))
	att, ok := msg.(AttachMsg)
	if !ok {
		t.Fatalf("want AttachMsg, got %T", msg)
	}
	if att.SessionTarget != "ralph-foo" {
		t.Errorf("target: %q", att.SessionTarget)
	}
}

func TestFormatResultSuccessAndFailure(t *testing.T) {
	ok := FormatResult(CmdResultMsg{Action: "verify", Target: "rid", Code: 0, Elapsed: 12 * time.Millisecond})
	if !strings.Contains(ok, "verify rid ok") {
		t.Errorf("ok formatting: %q", ok)
	}
	bad := FormatResult(CmdResultMsg{Action: "kill", Target: "rid", Code: 1, Stderr: "boom\nstack..."})
	if !strings.Contains(bad, "FAILED") || !strings.Contains(bad, "boom") {
		t.Errorf("err formatting: %q", bad)
	}
	codeOnly := FormatResult(CmdResultMsg{Action: "rm", Target: "rid", Code: 2})
	if !strings.Contains(codeOnly, "exit=2") {
		t.Errorf("bare exit formatting: %q", codeOnly)
	}
}

func TestRalphBinaryUsesEnvOverride(t *testing.T) {
	t.Setenv("RALPH_BIN", "/tmp/some-mock")
	if got := ralphBinary(); got != "/tmp/some-mock" {
		t.Errorf("RALPH_BIN override: %q", got)
	}
}
