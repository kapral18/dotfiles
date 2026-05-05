// Package forms holds modal forms for `,ralph go` invocations.
package forms

import (
	"strings"

	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/state"
	"ralph-tui/internal/styles"
)

// HarnessChoices is the closed set the New-Run form cycles through.
// `cursor` and `pi` are the two interactive AI-agent harnesses; the
// `command` harness exists in scripts/ralph.py's Runner.execute_role
// (and is reachable from the CLI via `--<role>-harness command
// --<role>-args "..."`) but is intentionally NOT exposed in the
// dashboard picker — its only real users are the test harness
// (scripts/tests/test_scripts.py mocks roles via mock_role.sh) and
// power users wiring custom agents persistently in
// `~/.config/ralph/roles.json`. Surfacing it in an interactive form
// would add a knob that requires typing exact shell incantations
// (including stdin-redirect semantics) for a workflow nobody runs ad
// hoc; persistent custom agents belong in roles.json, one-off probes
// belong on the CLI.
var HarnessChoices = []string{"cursor", "pi"}

// WorkflowChoices is the closed set the workflow picker cycles through.
// Order matches the picker's left-to-right cycle. Index 0 ("auto") sends
// no `--workflow` flag, leaving the choice to the planner; the rest pin
// scripts/ralph.py's WORKFLOWS keys.
var WorkflowChoices = []string{"auto", "feature", "bugfix", "review", "research"}

// WorkflowDescriptions mirrors WorkflowChoices order. Each line is
// "shape · when-to-pick" so a first-time user sees both the role lattice
// and the operational fit without having to read the SKILL.md.
var WorkflowDescriptions = map[string]string{
	"auto":     "let the planner choose (default) · use when scope is unclear",
	"feature":  "planner→executor→reviewer→re_reviewer · build new behavior",
	"bugfix":   "feature ladder + failing-test seed · fix a defect with a regression",
	"review":   "reviewer-only pass over an existing artifact · read PR / diff / file",
	"research": "planner→executor(read-only)→reviewer · investigate, write notes",
}

// RoleOrder fixes the per-role row order in the form view AND the focus
// cycle. Keep in sync with scripts/ralph.py role keys.
var RoleOrder = []string{"planner", "executor", "reviewer", "re_reviewer"}

// NewRunResult is what the form emits when the user confirms.
type NewRunResult struct {
	Goal      string
	Workspace string
	PlanOnly  bool
	// Workflow is the operator's workflow hint. Empty string when the user
	// picked "auto" (let the planner decide). Otherwise one of WORKFLOWS
	// keys ("feature" | "bugfix" | "review" | "research").
	Workflow string
	// Roles holds the per-role harness+model. Always populated for all four
	// roles; the form pre-fills with defaults so the user can always submit
	// without touching them.
	Roles map[string]state.RoleSpec
}

// fieldKind enumerates the focus targets in the form, in tab order.
// One harness picker + one model picker per role; both `cursor` and
// `pi` always have a curated model list, so every slot is always
// reachable in nav (no visibility logic needed).
type fieldKind int

const (
	fldGoal fieldKind = iota
	fldWorkspace
	fldPlanOnly
	fldWorkflow
	fldPlannerHarness
	fldPlannerModel
	fldExecutorHarness
	fldExecutorModel
	fldReviewerHarness
	fldReviewerModel
	fldReReviewerHarness
	fldReReviewerModel
	fldSubmit
	fldCount
)

// NewRunForm is a goal/workspace/plan-only/workflow + per-role
// harness/model modal. Per-role `extra_args` (e.g. `--mode plan` for
// cursor) live in `~/.config/ralph/roles.json`; the form does not
// expose them because they are persistent configuration, not per-run
// inputs. Run-specific overrides go through `,ralph go --<role>-args`
// at the CLI.
type NewRunForm struct {
	goal       textinput.Model
	workspace  textinput.Model
	planOnly   bool
	workflowIx int

	harness  map[string]int
	modelIdx map[string]int

	focus int
	width int
}

// New returns a fresh form with sensible defaults pre-filled from
// `defaults` (typically state.LoadRolesDefaults() output).
func New(defaultWorkspace string, defaults state.RolesDefaults) NewRunForm {
	g := textinput.New()
	g.Placeholder = "What should the planner work on?"
	g.Focus()
	g.CharLimit = 240
	g.Width = 60

	w := textinput.New()
	w.Placeholder = "/path/to/workspace (defaults to $PWD)"
	w.SetValue(defaultWorkspace)
	w.CharLimit = 240
	w.Width = 60

	specs := map[string]state.RoleSpec{
		"planner":     defaults.Planner,
		"executor":    defaults.Executor,
		"reviewer":    defaults.Reviewer,
		"re_reviewer": defaults.ReReviewer,
	}
	harness := make(map[string]int, len(RoleOrder))
	modelIdx := make(map[string]int, len(RoleOrder))
	for _, role := range RoleOrder {
		harness[role] = harnessIndex(specs[role].Harness)
		modelIdx[role] = state.IndexOfModel(state.AvailableModels(specs[role].Harness), specs[role].Model)
	}

	return NewRunForm{
		goal:       g,
		workspace:  w,
		harness:    harness,
		modelIdx:   modelIdx,
		workflowIx: 0,
	}
}

// Update handles form-local input. Returns:
//   - the updated form
//   - tea.Cmd for textinput blink/cursor animations
//   - submit: NewRunResult when the user pressed enter on Submit (or any text field)
//   - cancel: true if the user pressed Esc or Ctrl-C
func (f NewRunForm) Update(msg tea.Msg) (NewRunForm, tea.Cmd, *NewRunResult, bool) {
	switch m := msg.(type) {
	case tea.KeyMsg:
		switch {
		case key.Matches(m, KeyCancel):
			return f, nil, nil, true
		case key.Matches(m, KeyQuit):
			// 'q' cancels the form on non-text fields. Gated so the
			// literal 'q' keystroke still types into goal/workspace.
			if !isTextFocus(f.focus) {
				return f, nil, nil, true
			}
		case key.Matches(m, KeyTab):
			f.focus = (f.focus + 1) % int(fldCount)
			f.applyFocus()
			return f, nil, nil, false
		case key.Matches(m, KeyShiftTab):
			f.focus = (f.focus + int(fldCount) - 1) % int(fldCount)
			f.applyFocus()
			return f, nil, nil, false
		case key.Matches(m, KeyNextField):
			if !isTextFocus(f.focus) {
				f.focus = (f.focus + 1) % int(fldCount)
				f.applyFocus()
				return f, nil, nil, false
			}
		case key.Matches(m, KeyPrevField):
			if !isTextFocus(f.focus) {
				f.focus = (f.focus + int(fldCount) - 1) % int(fldCount)
				f.applyFocus()
				return f, nil, nil, false
			}
		case key.Matches(m, KeyToggle):
			if f.focus == int(fldPlanOnly) {
				f.planOnly = !f.planOnly
				return f, nil, nil, false
			}
		case key.Matches(m, KeyCycleLeft), key.Matches(m, KeyCycleRight):
			delta := 1
			if key.Matches(m, KeyCycleLeft) {
				delta = -1
			}
			if f.focus == int(fldWorkflow) {
				f.workflowIx = wrapIndex(f.workflowIx+delta, len(WorkflowChoices))
				return f, nil, nil, false
			}
			if role, ok := harnessRoleAt(f.focus); ok {
				f.harness[role] = wrapIndex(f.harness[role]+delta, len(HarnessChoices))
				f.modelIdx[role] = clampIndex(f.modelIdx[role], len(state.AvailableModels(HarnessChoices[f.harness[role]])))
				return f, nil, nil, false
			}
			if role, ok := modelRoleAt(f.focus); ok {
				list := state.AvailableModels(HarnessChoices[f.harness[role]])
				if len(list) == 0 {
					return f, nil, nil, false
				}
				f.modelIdx[role] = wrapIndex(f.modelIdx[role]+delta, len(list))
				return f, nil, nil, false
			}
		case key.Matches(m, KeySubmit):
			if f.focus == int(fldWorkflow) {
				f.focus = (f.focus + 1) % int(fldCount)
				f.applyFocus()
				return f, nil, nil, false
			}
			if role, ok := harnessRoleAt(f.focus); ok {
				f.focus = int(modelFieldOf(role))
				f.applyFocus()
				return f, nil, nil, false
			}
			if _, ok := modelRoleAt(f.focus); ok {
				f.focus = (f.focus + 1) % int(fldCount)
				f.applyFocus()
				return f, nil, nil, false
			}
			if strings.TrimSpace(f.goal.Value()) == "" {
				f.focus = int(fldGoal)
				f.applyFocus()
				return f, nil, nil, false
			}
			return f, nil, f.toResult(), false
		}
	}
	var cmd tea.Cmd
	switch fieldKind(f.focus) {
	case fldGoal:
		f.goal, cmd = f.goal.Update(msg)
	case fldWorkspace:
		f.workspace, cmd = f.workspace.Update(msg)
	}
	return f, cmd, nil, false
}

func (f NewRunForm) toResult() *NewRunResult {
	roles := make(map[string]state.RoleSpec, len(RoleOrder))
	for _, role := range RoleOrder {
		harness := HarnessChoices[f.harness[role]]
		list := state.AvailableModels(harness)
		model := ""
		if len(list) > 0 {
			model = list[clampIndex(f.modelIdx[role], len(list))]
		}
		roles[role] = state.RoleSpec{Harness: harness, Model: model}
	}
	return &NewRunResult{
		Goal:      strings.TrimSpace(f.goal.Value()),
		Workspace: strings.TrimSpace(f.workspace.Value()),
		PlanOnly:  f.planOnly,
		Workflow:  f.workflowFlag(),
		Roles:     roles,
	}
}

// workflowFlag returns the value to forward as `--workflow=<id>`, or empty
// string for the "auto" choice (the planner picks).
func (f NewRunForm) workflowFlag() string {
	choice := WorkflowChoices[clampIndex(f.workflowIx, len(WorkflowChoices))]
	if choice == "auto" {
		return ""
	}
	return choice
}

// View renders the modal contents.
func (f NewRunForm) View() string {
	rows := []string{
		styles.Title.Render("New Ralph run"),
		"",
		fieldLabel("Goal", f.focus == int(fldGoal)) + "\n" + f.goal.View(),
		fieldLabel("Workspace", f.focus == int(fldWorkspace)) + "\n" + f.workspace.View(),
		fieldLabel("Plan-only", f.focus == int(fldPlanOnly)) + "  " + checkbox(f.planOnly, f.focus == int(fldPlanOnly)),
		"",
		f.viewWorkflowRow(),
		"",
		styles.Faint.Render("── Roles (h/l cycles · j/k or tab moves down/up · enter advances) ──"),
	}
	for _, role := range RoleOrder {
		rows = append(rows, f.viewRoleRow(role))
	}
	rows = append(rows,
		"",
		buttonRow(f.focus == int(fldSubmit)),
		"",
		styles.Faint.Render("tab/j/k navigate · h/l cycles options · space toggles plan-only · enter advances/submits · esc/ctrl-c/q cancels"),
	)
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

// viewWorkflowRow renders the workflow picker plus a one-line description
// of the currently focused choice.
func (f NewRunForm) viewWorkflowRow() string {
	focused := f.focus == int(fldWorkflow)
	choice := WorkflowChoices[clampIndex(f.workflowIx, len(WorkflowChoices))]
	suffix := "  " + lipgloss.NewStyle().Foreground(styles.Subtle).
		Render(positionLabel(f.workflowIx, len(WorkflowChoices)))
	label := fieldLabel("Workflow", focused)
	pick := picker(choice, suffix, focused, 14)
	desc := WorkflowDescriptions[choice]
	descLine := styles.Faint.Render("    " + desc)
	row := lipgloss.JoinHorizontal(lipgloss.Top, label, "  ", pick)
	return row + "\n" + descLine
}

func (f NewRunForm) viewRoleRow(role string) string {
	hFocus := f.focus == int(harnessFieldOf(role))
	mFocus := f.focus == int(modelFieldOf(role))
	label := lipgloss.NewStyle().Width(13).Render(roleDisplay(role))
	harness := picker(HarnessChoices[f.harness[role]], "", hFocus, 14)
	list := state.AvailableModels(HarnessChoices[f.harness[role]])
	model := f.modelDisplay(role, list, mFocus)
	return lipgloss.JoinHorizontal(lipgloss.Top, label, harness, "  ", model)
}

// modelDisplay renders the model picker for the role. Both cursor and
// pi always have a curated model list (see state/models.go), so the
// empty-list path is treated as a defensive no-op rather than a
// user-visible state.
func (f NewRunForm) modelDisplay(role string, list []string, focused bool) string {
	if len(list) == 0 {
		return styles.Subdued.Render("(no models)")
	}
	idx := clampIndex(f.modelIdx[role], len(list))
	suffix := "  " + lipgloss.NewStyle().Foreground(styles.Subtle).Render(positionLabel(idx, len(list)))
	return picker(list[idx], suffix, focused, 0)
}

func picker(value, suffix string, focused bool, width int) string {
	body := "‹ " + value + " ›"
	style := lipgloss.NewStyle()
	if width > 0 {
		style = style.Width(width)
	}
	if focused {
		style = style.Foreground(styles.Accent).Bold(true)
	} else {
		style = style.Foreground(styles.Subtle)
	}
	return style.Render(body) + suffix
}

func positionLabel(idx, total int) string {
	if total <= 0 {
		return ""
	}
	return fmtIdx(idx+1) + "/" + fmtIdx(total)
}

func fmtIdx(n int) string {
	if n < 10 {
		return string(rune('0'+n))
	}
	const digits = "0123456789"
	out := make([]byte, 0, 4)
	for n > 0 {
		out = append([]byte{digits[n%10]}, out...)
		n /= 10
	}
	return string(out)
}

func fieldLabel(name string, focused bool) string {
	style := styles.Subdued
	if focused {
		style = lipgloss.NewStyle().Foreground(styles.Accent).Bold(true)
	}
	return style.Render(name)
}

func checkbox(checked, focused bool) string {
	mark := "[ ]"
	if checked {
		mark = "[x]"
	}
	style := styles.Subdued
	if focused {
		style = lipgloss.NewStyle().Foreground(styles.Accent).Bold(true)
	}
	return style.Render(mark + " plan-only (stop after planner)")
}

func buttonRow(focused bool) string {
	style := styles.Subdued
	if focused {
		style = lipgloss.NewStyle().Foreground(styles.AccentBright).Bold(true)
	}
	return style.Render("[ Submit ]")
}

func roleDisplay(role string) string {
	if role == "re_reviewer" {
		return "re_reviewer"
	}
	return role
}

func (f *NewRunForm) applyFocus() {
	f.goal.Blur()
	f.workspace.Blur()
	switch fieldKind(f.focus) {
	case fldGoal:
		f.goal.Focus()
	case fldWorkspace:
		f.workspace.Focus()
	}
}

func harnessIndex(name string) int {
	for i, h := range HarnessChoices {
		if h == name {
			return i
		}
	}
	return 0 // default to cursor
}

func harnessFieldOf(role string) fieldKind {
	switch role {
	case "planner":
		return fldPlannerHarness
	case "executor":
		return fldExecutorHarness
	case "reviewer":
		return fldReviewerHarness
	case "re_reviewer":
		return fldReReviewerHarness
	}
	return fldPlannerHarness
}

func modelFieldOf(role string) fieldKind {
	switch role {
	case "planner":
		return fldPlannerModel
	case "executor":
		return fldExecutorModel
	case "reviewer":
		return fldReviewerModel
	case "re_reviewer":
		return fldReReviewerModel
	}
	return fldPlannerModel
}

func harnessRoleAt(focus int) (string, bool) {
	switch fieldKind(focus) {
	case fldPlannerHarness:
		return "planner", true
	case fldExecutorHarness:
		return "executor", true
	case fldReviewerHarness:
		return "reviewer", true
	case fldReReviewerHarness:
		return "re_reviewer", true
	}
	return "", false
}

func modelRoleAt(focus int) (string, bool) {
	switch fieldKind(focus) {
	case fldPlannerModel:
		return "planner", true
	case fldExecutorModel:
		return "executor", true
	case fldReviewerModel:
		return "reviewer", true
	case fldReReviewerModel:
		return "re_reviewer", true
	}
	return "", false
}

func wrapIndex(i, n int) int {
	if n <= 0 {
		return 0
	}
	return ((i % n) + n) % n
}

func clampIndex(i, n int) int {
	if n <= 0 {
		return 0
	}
	if i < 0 {
		return 0
	}
	if i >= n {
		return n - 1
	}
	return i
}

// Keys exported for help overlay rendering.
//
// Vim-style mapping: h/l mirror left/right (cycle within an option), j/k
// mirror tab/shift-tab (move between fields). Arrows do the same. j/k and
// arrow up/down are gated so they reach goal/workspace text inputs as
// regular characters when those fields have focus.
var (
	KeySubmit     = key.NewBinding(key.WithKeys("enter"))
	KeyCancel     = key.NewBinding(key.WithKeys("esc", "ctrl+c"))
	KeyQuit       = key.NewBinding(key.WithKeys("q"))
	KeyTab        = key.NewBinding(key.WithKeys("tab"))
	KeyShiftTab   = key.NewBinding(key.WithKeys("shift+tab"))
	KeyToggle     = key.NewBinding(key.WithKeys(" "))
	KeyCycleLeft  = key.NewBinding(key.WithKeys("left", "h"))
	KeyCycleRight = key.NewBinding(key.WithKeys("right", "l"))
	KeyNextField  = key.NewBinding(key.WithKeys("down", "j"))
	KeyPrevField  = key.NewBinding(key.WithKeys("up", "k"))
)

// isTextFocus reports whether the current focus is on a text-typing
// field (goal or workspace). j/k/h/l and arrow keys must reach these
// fields as regular keystrokes rather than triggering form-level
// navigation.
func isTextFocus(focus int) bool {
	return fieldKind(focus) == fldGoal || fieldKind(focus) == fldWorkspace
}
