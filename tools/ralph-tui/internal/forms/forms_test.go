package forms

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"ralph-tui/internal/state"
)

func defaults() state.RolesDefaults {
	// Pick model ids that exist in the curated cursor list so the picker
	// seeds at the matching index instead of falling back to 0.
	return state.RolesDefaults{
		Planner:    state.RoleSpec{Harness: "cursor", Model: "claude-opus-4-7-thinking-max"},
		Executor:   state.RoleSpec{Harness: "cursor", Model: "composer-2"},
		Reviewer:   state.RoleSpec{Harness: "cursor", Model: "claude-opus-4-7-thinking-high"},
		ReReviewer: state.RoleSpec{Harness: "cursor", Model: "gpt-5.5-extra-high"},
	}
}

func keyRune(r rune) tea.KeyMsg     { return tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}} }
func keyType(k tea.KeyType) tea.KeyMsg { return tea.KeyMsg{Type: k} }

func TestNewRunFormSubmitsDefaultsWhenUntouched(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for _, r := range "ship feature" {
		var sub *NewRunResult
		f, _, sub, _ = f.Update(keyRune(r))
		if sub != nil {
			t.Fatal("unexpected early submit")
		}
	}
	_, _, sub, _ := f.Update(keyType(tea.KeyEnter))
	if sub == nil {
		t.Fatal("expected submit after enter on goal")
	}
	if sub.Goal != "ship feature" {
		t.Errorf("goal: %q", sub.Goal)
	}
	if sub.Workspace != "/tmp/ws" {
		t.Errorf("workspace: %q", sub.Workspace)
	}
	if got := sub.Roles["planner"]; got.Harness != "cursor" || got.Model != "claude-opus-4-7-thinking-max" {
		t.Errorf("planner default: %+v", got)
	}
	if got := sub.Roles["re_reviewer"]; got.Harness != "cursor" || got.Model != "gpt-5.5-extra-high" {
		t.Errorf("re_reviewer default: %+v", got)
	}
}

func TestNewRunFormBlocksSubmitOnEmptyGoal(t *testing.T) {
	f := New("/tmp/ws", defaults())
	_, _, sub, _ := f.Update(keyType(tea.KeyEnter))
	if sub != nil {
		t.Fatal("submit must be blocked on empty goal")
	}
	if f.focus != int(fldGoal) {
		t.Errorf("focus must snap back to goal, got %d", f.focus)
	}
}

func TestHarnessPickerCyclesWithVimAndArrowKeys(t *testing.T) {
	// Closed cursor → pi cycle (no `command` — that's CLI/runtime
	// only, not a dashboard knob; see HarnessChoices).
	cases := []struct {
		name   string
		key    tea.KeyMsg
		expect []string // expected harness sequence after each press
	}{
		{"right", keyType(tea.KeyRight), []string{"pi", "cursor", "pi"}},
		{"l", keyRune('l'), []string{"pi", "cursor", "pi"}},
		{"left", keyType(tea.KeyLeft), []string{"pi", "cursor", "pi"}},
		{"h", keyRune('h'), []string{"pi", "cursor", "pi"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := New("/tmp/ws", defaults())
			for f.focus != int(fldPlannerHarness) {
				f, _, _, _ = f.Update(keyType(tea.KeyTab))
			}
			if HarnessChoices[f.harness["planner"]] != "cursor" {
				t.Fatalf("seed harness: %q", HarnessChoices[f.harness["planner"]])
			}
			for i, want := range tc.expect {
				f, _, _, _ = f.Update(tc.key)
				got := HarnessChoices[f.harness["planner"]]
				if got != want {
					t.Errorf("step %d (%s): got %q want %q", i, tc.name, got, want)
				}
			}
		})
	}
}

func TestModelPickerCyclesWithVimAndArrowKeys(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for f.focus != int(fldPlannerModel) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	cursor := state.AvailableModels("cursor")
	if len(cursor) < 4 {
		t.Skipf("need at least 4 cursor models, got %d", len(cursor))
	}
	startIdx := f.modelIdx["planner"]

	f, _, _, _ = f.Update(keyRune('l'))
	if f.modelIdx["planner"] != wrapIndex(startIdx+1, len(cursor)) {
		t.Errorf("l: idx=%d want=%d", f.modelIdx["planner"], wrapIndex(startIdx+1, len(cursor)))
	}
	f, _, _, _ = f.Update(keyType(tea.KeyRight))
	if f.modelIdx["planner"] != wrapIndex(startIdx+2, len(cursor)) {
		t.Errorf("right: idx=%d", f.modelIdx["planner"])
	}
	f, _, _, _ = f.Update(keyRune('h'))
	f, _, _, _ = f.Update(keyType(tea.KeyLeft))
	if f.modelIdx["planner"] != startIdx {
		t.Errorf("h+left: idx=%d want=%d", f.modelIdx["planner"], startIdx)
	}
}

func TestHarnessChangeReclampsModelIndex(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for f.focus != int(fldPlannerHarness) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	// Push the model index near the end of cursor's list (where pi's list
	// is shorter), so without re-clamping we'd overflow.
	cursor := state.AvailableModels("cursor")
	f.modelIdx["planner"] = len(cursor) - 1

	// Cycle harness to pi.
	f, _, _, _ = f.Update(keyType(tea.KeyRight))
	if HarnessChoices[f.harness["planner"]] != "pi" {
		t.Fatalf("expected harness=pi after one cycle, got %q", HarnessChoices[f.harness["planner"]])
	}
	pi := state.AvailableModels("pi")
	if f.modelIdx["planner"] >= len(pi) {
		t.Errorf("model index %d not clamped to pi list len %d", f.modelIdx["planner"], len(pi))
	}
}

// TestHarnessChoicesExcludeCommand pins that the dashboard picker
// only cycles cursor → pi. The `command` harness lives at the CLI /
// runtime layer (used by tests in scripts/tests/test_scripts.py and by
// power users wiring custom agents in roles.json) but is intentionally
// hidden from the interactive form because nobody types shell
// incantations into a textinput per run. See the HarnessChoices
// comment in forms.go for the full rationale.
func TestHarnessChoicesExcludeCommand(t *testing.T) {
	for _, h := range HarnessChoices {
		if h == "command" {
			t.Errorf("HarnessChoices must NOT expose `command` in the dashboard picker; got %v", HarnessChoices)
		}
	}
	if got, want := len(HarnessChoices), 2; got != want {
		t.Errorf("HarnessChoices must have %d entries (cursor + pi), got %d: %v", want, got, HarnessChoices)
	}
}

func TestNewRunFormViewMentionsAllFourRoles(t *testing.T) {
	f := New("", defaults())
	v := f.View()
	for _, role := range RoleOrder {
		if !strings.Contains(v, role) {
			t.Errorf("view missing role %q:\n%s", role, v)
		}
	}
	if !strings.Contains(v, "claude-opus-4-7-thinking-max") || !strings.Contains(v, "gpt-5.5-extra-high") {
		t.Errorf("view missing default model values")
	}
	if !strings.Contains(v, "Roles") {
		t.Errorf("view missing roles section header")
	}
	if !strings.Contains(v, "h/l cycles") {
		t.Errorf("view should advertise h/l cycling")
	}
	if !strings.Contains(v, "j/k") {
		t.Errorf("view should advertise j/k navigation")
	}
}

func TestNewRunFormFocusCycleVisitsEveryField(t *testing.T) {
	f := New("/tmp/ws", defaults())
	seen := map[int]bool{f.focus: true}
	for i := 0; i < int(fldCount); i++ {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
		seen[f.focus] = true
	}
	if len(seen) != int(fldCount) {
		t.Errorf("expected %d focus stops, hit %d (visited=%v)", int(fldCount), len(seen), seen)
	}
}

func TestWorkflowPickerDefaultsToAutoAndEmitsEmptyFlag(t *testing.T) {
	f := New("/tmp/ws", defaults())
	if WorkflowChoices[f.workflowIx] != "auto" {
		t.Fatalf("default workflow must be 'auto', got %q", WorkflowChoices[f.workflowIx])
	}
	for _, r := range "ship" {
		f, _, _, _ = f.Update(keyRune(r))
	}
	_, _, sub, _ := f.Update(keyType(tea.KeyEnter))
	if sub == nil {
		t.Fatal("submit expected after enter on goal")
	}
	if sub.Workflow != "" {
		t.Errorf("auto must produce empty Workflow flag, got %q", sub.Workflow)
	}
}

func TestWorkflowPickerCyclesWithVimAndArrowKeys(t *testing.T) {
	cases := []struct {
		name   string
		key    tea.KeyMsg
		expect []string
	}{
		{"l", keyRune('l'), []string{"feature", "bugfix", "review", "research", "auto"}},
		{"right", keyType(tea.KeyRight), []string{"feature", "bugfix", "review", "research", "auto"}},
		{"h", keyRune('h'), []string{"research", "review", "bugfix", "feature", "auto"}},
		{"left", keyType(tea.KeyLeft), []string{"research", "review", "bugfix", "feature", "auto"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := New("/tmp/ws", defaults())
			for f.focus != int(fldWorkflow) {
				f, _, _, _ = f.Update(keyType(tea.KeyTab))
			}
			for i, want := range tc.expect {
				f, _, _, _ = f.Update(tc.key)
				got := WorkflowChoices[f.workflowIx]
				if got != want {
					t.Errorf("step %d (%s): got %q want %q", i, tc.name, got, want)
				}
			}
		})
	}
}

func TestWorkflowPickerEmitsExplicitChoice(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for _, r := range "research-task" {
		f, _, _, _ = f.Update(keyRune(r))
	}
	for f.focus != int(fldWorkflow) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	for WorkflowChoices[f.workflowIx] != "research" {
		f, _, _, _ = f.Update(keyRune('l'))
	}
	for f.focus != int(fldSubmit) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	_, _, sub, _ := f.Update(keyType(tea.KeyEnter))
	if sub == nil {
		t.Fatal("submit expected on submit button")
	}
	if sub.Workflow != "research" {
		t.Errorf("workflow flag: got %q want \"research\"", sub.Workflow)
	}
}

func TestEnterOnWorkflowAdvancesToPlannerHarness(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for f.focus != int(fldWorkflow) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	f, _, sub, _ := f.Update(keyType(tea.KeyEnter))
	if sub != nil {
		t.Fatalf("enter on workflow must not submit (got %+v)", sub)
	}
	if f.focus != int(fldPlannerHarness) {
		t.Errorf("expected focus=%d (planner harness), got %d", int(fldPlannerHarness), f.focus)
	}
}

func TestNewRunFormViewMentionsWorkflow(t *testing.T) {
	f := New("", defaults())
	v := f.View()
	if !strings.Contains(v, "Workflow") {
		t.Errorf("view missing Workflow header:\n%s", v)
	}
	if !strings.Contains(v, "auto") {
		t.Errorf("view missing default 'auto' workflow choice")
	}
	if !strings.Contains(v, WorkflowDescriptions["auto"]) {
		t.Errorf("view missing description for the focused workflow choice")
	}
}

func TestNewRunFormCtrlCCancelsLikeEsc(t *testing.T) {
	f := New("/tmp/ws", defaults())
	_, _, _, cancelled := f.Update(tea.KeyMsg{Type: tea.KeyCtrlC})
	if !cancelled {
		t.Errorf("ctrl+c must cancel the form (parity with esc)")
	}
}

func TestQCancelsOnNonTextFields(t *testing.T) {
	// Walk past goal/workspace; q on plan-only / harness / model / submit
	// must close the modal. The literal q on goal/workspace must NOT close
	// it (covered separately).
	for _, target := range []fieldKind{fldPlanOnly, fldPlannerHarness, fldExecutorModel, fldSubmit} {
		f := New("/tmp/ws", defaults())
		for f.focus != int(target) {
			f, _, _, _ = f.Update(keyType(tea.KeyTab))
		}
		_, _, _, cancelled := f.Update(keyRune('q'))
		if !cancelled {
			t.Errorf("q on field %d must cancel the form", int(target))
		}
	}
}

func TestQTypesIntoGoalAndWorkspace(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for _, r := range "queue" {
		var cancelled bool
		f, _, _, cancelled = f.Update(keyRune(r))
		if cancelled {
			t.Fatalf("typing %q into goal must not cancel the form", r)
		}
	}
	if got := f.goal.Value(); got != "queue" {
		t.Errorf("goal must accept q character: got %q", got)
	}
	f, _, _, _ = f.Update(keyType(tea.KeyTab)) // goal -> workspace
	for _, r := range "/q" {
		var cancelled bool
		f, _, _, cancelled = f.Update(keyRune(r))
		if cancelled {
			t.Fatalf("typing %q into workspace must not cancel", r)
		}
	}
	if got := f.workspace.Value(); !strings.HasSuffix(got, "/q") {
		t.Errorf("workspace must accept q: got %q", got)
	}
}

func TestEnterOnHarnessAdvancesToModelField(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for f.focus != int(fldExecutorHarness) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	f, _, sub, _ := f.Update(keyType(tea.KeyEnter))
	if sub != nil {
		t.Fatalf("enter on harness must not submit (got %+v)", sub)
	}
	if f.focus != int(fldExecutorModel) {
		t.Errorf("expected focus=%d (executor model), got %d", int(fldExecutorModel), f.focus)
	}
}

func TestEnterOnModelAdvancesToNextField(t *testing.T) {
	f := New("/tmp/ws", defaults())
	for f.focus != int(fldExecutorModel) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	f, _, _, _ = f.Update(keyType(tea.KeyEnter))
	if f.focus != int(fldReviewerHarness) {
		t.Errorf("expected focus=%d (reviewer harness) after enter on executor model, got %d",
			int(fldReviewerHarness), f.focus)
	}
}

func TestJKNavigateBetweenFieldsLikeTab(t *testing.T) {
	cases := []struct {
		name string
		key  tea.KeyMsg
	}{
		{"j", keyRune('j')},
		{"down", keyType(tea.KeyDown)},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := New("/tmp/ws", defaults())
			for f.focus != int(fldPlanOnly) {
				f, _, _, _ = f.Update(keyType(tea.KeyTab))
			}
			f, _, _, _ = f.Update(tc.key)
			if f.focus != int(fldWorkflow) {
				t.Errorf("%s on plan-only must move to workflow, got %d", tc.name, f.focus)
			}
			f, _, _, _ = f.Update(tc.key)
			if f.focus != int(fldPlannerHarness) {
				t.Errorf("%s on workflow must move to planner harness, got %d", tc.name, f.focus)
			}
		})
	}
}

func TestKArrowUpMovesToPreviousField(t *testing.T) {
	cases := []struct {
		name string
		key  tea.KeyMsg
	}{
		{"k", keyRune('k')},
		{"up", keyType(tea.KeyUp)},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f := New("/tmp/ws", defaults())
			for f.focus != int(fldExecutorHarness) {
				f, _, _, _ = f.Update(keyType(tea.KeyTab))
			}
			f, _, _, _ = f.Update(tc.key)
			// Default cursor harness -> planner-args is hidden, so k
			// must skip it and land on planner-model (the previous
			// VISIBLE field), not on the raw enum-previous slot.
			if f.focus != int(fldPlannerModel) {
				t.Errorf("%s from executor-harness under cursor must skip hidden planner-args and land on planner-model (=%d); got %d",
					tc.name, int(fldPlannerModel), f.focus)
			}
		})
	}
}

func TestJKDoNotEatTextInputCharacters(t *testing.T) {
	// On goal/workspace, j and k must reach the textinput as literal chars.
	f := New("/tmp/ws", defaults())
	for _, r := range "jkjk" {
		f, _, _, _ = f.Update(keyRune(r))
	}
	if got := f.goal.Value(); got != "jkjk" {
		t.Errorf("goal must accept j/k chars: got %q", got)
	}
}

func TestVimKeysStillTypeIntoGoalAndWorkspace(t *testing.T) {
	// h/l are both vim cycle keys AND printable characters. When focus is on
	// the goal or workspace text input, they MUST reach the textinput rather
	// than being eaten by the cycling handler.
	f := New("/tmp/ws", defaults())
	for _, r := range "help" {
		f, _, _, _ = f.Update(keyRune(r))
	}
	if got := f.goal.Value(); got != "help" {
		t.Errorf("goal must accept h/l characters: got %q", got)
	}
	f, _, _, _ = f.Update(keyType(tea.KeyTab))
	if f.focus != int(fldWorkspace) {
		t.Fatalf("expected focus=workspace, got %d", f.focus)
	}
	// Workspace already has "/tmp/ws" — append "/hl" to confirm h+l still type.
	for _, r := range "/hl" {
		f, _, _, _ = f.Update(keyRune(r))
	}
	if got := f.workspace.Value(); !strings.HasSuffix(got, "/hl") {
		t.Errorf("workspace must accept h/l: got %q", got)
	}
}

func TestEnterOnSubmitWithEmptyGoalSnapsBack(t *testing.T) {
	f := New("/tmp/ws", defaults())
	f.goal.SetValue("")
	for f.focus != int(fldSubmit) {
		f, _, _, _ = f.Update(keyType(tea.KeyTab))
	}
	f, _, sub, _ := f.Update(keyType(tea.KeyEnter))
	if sub != nil {
		t.Errorf("must not submit with empty goal")
	}
	if f.focus != int(fldGoal) {
		t.Errorf("focus must snap to goal, got %d", f.focus)
	}
}

// TestFormViewHasNoArgsKnobs pins the dashboard's hidden surface: no
// "args" label or per-role textinput must leak into the form view.
// Per-role `extra_args` are persistent config (roles.json) or
// CLI-only (`,ralph go --<role>-args`); exposing them as form knobs
// would be a feature for a workflow that doesn't exist
// interactively.
func TestFormViewHasNoArgsKnobs(t *testing.T) {
	f := New("/tmp/ws", defaults())
	v := f.View()
	for _, banned := range []string{"args:", "(custom — uses extra_args)", "extra_args"} {
		if strings.Contains(v, banned) {
			t.Errorf("dashboard form must NOT mention %q; view=\n%s", banned, v)
		}
	}
}
