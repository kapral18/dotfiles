// Package app composes the Ralph TUI from the smaller component packages.
//
// The App is a Bubble Tea program: every keystroke flows through Update, every
// frame is produced by View. State is split across:
//
//   - runs:    the list of all Ralph runs on disk
//   - detail:  the selected run's metadata, iterations, roles
//   - tail:    a live tail of the selected role's output.log
//   - modal:   one of {none, newRun, control, help}
//   - toast:   one-line transient status message
//
// Nothing in this file mutates Ralph state directly. Mutations happen via
// `,ralph` subprocesses fired from internal/cmds.
package app

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/activity"
	"ralph-tui/internal/answer"
	kbmod "ralph-tui/internal/kb"
	"ralph-tui/internal/cmds"
	"ralph-tui/internal/control"
	"ralph-tui/internal/detail"
	"ralph-tui/internal/forms"
	"ralph-tui/internal/help"
	"ralph-tui/internal/preview"
	"ralph-tui/internal/runs"
	"ralph-tui/internal/state"
	"ralph-tui/internal/styles"
	"ralph-tui/internal/tail"
)

type focusPane int

const (
	focusRuns focusPane = iota
	focusRoles
	focusTail
)

type modalKind int

const (
	modalNone modalKind = iota
	modalNewRun
	modalControl
	modalHelp
	modalConfirm
	modalAnswer
	modalPreview
	modalKB
)

// layoutKind switches the App between fleet-observability shapes.
//
//   - layoutDetail: 3-pane (runs · detail · tail). Default.
//   - layoutGrid:   2x2 role tails for the selected run, plus a thin
//     header bar showing run identity. Lets the operator see all four
//     roles' live output simultaneously.
//   - layoutZoom:   the focused pane fills the screen. Replaces the old
//     `zoom` bool toggle. Pressing the layout key again returns to detail.
type layoutKind int

const (
	layoutDetail layoutKind = iota
	layoutGrid
	layoutZoom
)

func (l layoutKind) String() string {
	switch l {
	case layoutGrid:
		return "grid"
	case layoutZoom:
		return "zoom"
	default:
		return "detail"
	}
}

type confirmInfo struct {
	title  string
	body   string
	action control.Action
	rid    string
	role   string
}

// activitySize controls the activity drawer's height so an operator
// running a busy fleet can opt in to seeing more recent events without
// permanently wasting screen real estate when the swarm is quiet.
type activitySize int

const (
	activityOff activitySize = iota
	activitySmall
	activityLarge
)

func (a activitySize) String() string {
	switch a {
	case activitySmall:
		return "small"
	case activityLarge:
		return "large"
	default:
		return "off"
	}
}

// Model is the top-level bubbletea model.
type Model struct {
	runs    runs.Model
	detail  detail.Model
	tail    tail.Model
	form    forms.NewRunForm
	control control.Menu
	confirm confirmInfo
	answer  answer.Modal
	preview preview.Modal
	kb      kbmod.Modal
	kbStats cmds.KBStatsMsg

	focus        focusPane
	modal        modalKind
	layout       layoutKind
	activitySize activitySize
	gridCursor   int
	toast        toastInfo

	width  int
	height int

	watcherEvents <-chan state.WatchEvent
	watcherClose  func()
	defaultWS     string
	pendingAttach string
	rolesDefaults state.RolesDefaults
}

// New builds the app with sane defaults.
func New(defaultWorkspace string) (*Model, error) {
	defaults, _ := state.LoadRolesDefaults() // err = no roles.json → fallback constants
	m := &Model{
		runs:          runs.New(),
		detail:        detail.New(),
		tail:          tail.New(),
		focus:         focusRuns,
		modal:         modalNone,
		defaultWS:     defaultWorkspace,
		rolesDefaults: defaults,
	}
	w, err := state.NewWatcher()
	if err == nil {
		m.watcherEvents = w.Events()
		m.watcherClose = func() { _ = w.Close() }
	}
	return m, nil
}

// PendingAttach returns a non-empty tmux target if the user requested
// `tmux switch-client` on exit. main() reads this after Run() returns.
func (m *Model) PendingAttach() string { return m.pendingAttach }

// Close releases the watcher; safe to call multiple times.
func (m *Model) Close() {
	if m.watcherClose != nil {
		m.watcherClose()
		m.watcherClose = nil
	}
}

// --- bubbletea contract ----------------------------------------------------

// Init kicks off initial loads + watcher subscription.
func (m *Model) Init() tea.Cmd {
	return tea.Batch(
		cmds.LoadRunsCmd(),
		cmds.KBStatsCmd(),
		m.watcherCmd(),
		periodicTickCmd(0),
	)
}

// Update routes events to the active modal or focused pane.
func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		m.relayout()
		// Keep every modal in sync with the new terminal width — without
		// this, a resize while a modal was open would leave the box at
		// its pre-resize width and clip text. The new-run form and the
		// control menu have fixed-width children, so they don't need a
		// SetWidth call.
		switch m.modal {
		case modalAnswer:
			m.answer.SetWidth(m.width - 8)
		case modalKB:
			m.kb.SetWidth(m.width - 8)
		case modalPreview:
			w, h := m.previewSize()
			m.preview.SetSize(w, h)
		}
		return m, nil
	case cmds.RunsLoadedMsg:
		if msg.Err == nil {
			m.runs.SetRuns(msg.Runs)
			m.refreshDetail()
		} else {
			m.toast = newToast("error loading runs: "+msg.Err.Error(), styles.Bad)
		}
		return m, nil
	case cmds.RunReloadedMsg:
		if msg.Err == nil {
			m.applyRunUpdate(msg.Run)
		}
		return m, nil
	case cmds.CmdResultMsg:
		col := styles.OK
		if msg.Code != 0 {
			col = styles.Bad
		}
		m.toast = newToast(cmds.FormatResult(msg), col)
		return m, cmds.LoadRunsCmd()
	case cmds.AttachMsg:
		m.pendingAttach = msg.SessionTarget
		return m, tea.Quit
	case cmds.KBSearchMsg:
		// The KB modal owns its own state; even when closed, we
		// still let the message land so the modal stays consistent
		// across reopens.
		m.kb.SetHits(msg)
		return m, nil
	case cmds.KBStatsMsg:
		m.kbStats = msg
		return m, nil
	case watcherEventMsg:
		if shouldReload(msg.Path) {
			m.refreshDetailTail()
			return m, tea.Batch(cmds.LoadRunsCmd(), m.watcherCmd())
		}
		return m, m.watcherCmd()
	case tickMsg:
		m.expireToast()
		// Refresh KB stats every ~30 ticks (~30s) so the `KB:N` segment
		// reflects capsules that landed mid-session (reflector outputs,
		// mid-run learnings) instead of being frozen at the value
		// captured during Init().
		batch := []tea.Cmd{periodicTickCmd(msg.count + 1)}
		if (msg.count+1)%30 == 0 {
			batch = append(batch, cmds.KBStatsCmd())
		}
		return m, tea.Batch(batch...)
	case preview.CapturedMsg:
		_, _ = m.preview.Update(msg)
		return m, nil
	case preview.AttachReadOnlyMsg:
		return m, m.attachReadOnlyPopup(msg.Target)
	case previewTickMsg:
		if m.modal != modalPreview || !m.preview.IsOpen() {
			return m, nil
		}
		return m, tea.Batch(preview.CaptureCmd(m.preview.Target()), previewTickCmd())
	case tea.KeyMsg:
		return m.handleKey(msg)
	}
	return m, nil
}

// previewTickMsg drives the auto-refresh loop for an open preview modal.
type previewTickMsg struct{}

func previewTickCmd() tea.Cmd {
	return tea.Tick(time.Second, func(time.Time) tea.Msg { return previewTickMsg{} })
}

// View composes the layout.
func (m *Model) View() string {
	if m.width == 0 || m.height == 0 {
		return "loading…"
	}

	main := m.viewMain()
	bar := m.viewStatusBar()
	parts := []string{main}
	if m.activitySize != activityOff {
		parts = append(parts, m.viewActivityDrawer())
	}
	parts = append(parts, bar)
	view := lipgloss.JoinVertical(lipgloss.Left, parts...)

	switch m.modal {
	case modalNewRun:
		return centerOverlay(m.form.View(), m.width, m.height)
	case modalControl:
		return centerOverlay(m.control.View(), m.width, m.height)
	case modalHelp:
		return centerOverlay(help.Overlay(m.width-4), m.width, m.height)
	case modalConfirm:
		return centerOverlay(m.viewConfirm(), m.width, m.height)
	case modalAnswer:
		return centerOverlay(m.answer.View(), m.width, m.height)
	case modalPreview:
		return centerOverlay(m.preview.View(), m.width, m.height)
	case modalKB:
		return centerOverlay(m.kb.View(), m.width, m.height)
	}
	return view
}

// --- key handling -----------------------------------------------------------

func (m *Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	if m.modal != modalNone {
		return m.handleModalKey(msg)
	}
	// When the runs pane is currently in filter mode, route every key
	// straight to it so single-letter global shortcuts (`q`, `n`, `a`,
	// ...) don't shadow filter typing. Mirrors the modal-exclusive
	// dispatch above. Without this, the `/` filter is broken for any
	// letter that's also a global shortcut.
	if m.focus == focusRuns && m.runs.IsTyping() {
		var cmd tea.Cmd
		m.runs, cmd = m.runs.Update(msg)
		return m, cmd
	}
	switch {
	case key.Matches(msg, KeyQuit):
		m.Close()
		return m, tea.Quit
	case key.Matches(msg, KeyHelp):
		m.modal = modalHelp
		return m, nil
	case key.Matches(msg, KeyRefresh):
		return m, cmds.LoadRunsCmd()
	case key.Matches(msg, KeyTab):
		m.cycleFocus(1)
		return m, nil
	case key.Matches(msg, KeyShiftTab):
		m.cycleFocus(-1)
		return m, nil
	case key.Matches(msg, KeyZoom):
		// In grid layout, `enter` drills the cursored cell into the
		// default layout with focus on its role's tail — the only way
		// to "open" a grid cell. Outside grid, `enter` toggles zoom.
		if m.layout == layoutGrid {
			if r, ok := m.runs.Selected(); ok {
				if cells := pickGridRoles(r); m.gridCursor < len(cells) {
					m.detail.SelectRole(cells[m.gridCursor].Name)
				}
			}
			m.layout = layoutDetail
			m.focus = focusTail
			m.relayout()
			m.refreshTail()
			return m, nil
		}
		if m.layout == layoutZoom {
			m.layout = layoutDetail
		} else {
			m.layout = layoutZoom
		}
		m.relayout()
		return m, nil
	case key.Matches(msg, KeyLayoutDetail):
		m.layout = layoutDetail
		m.relayout()
		m.toast = newToast("layout: detail", styles.Info)
		return m, nil
	case key.Matches(msg, KeyLayoutGrid):
		m.layout = layoutGrid
		m.relayout()
		m.toast = newToast("layout: role grid", styles.Info)
		return m, nil
	case key.Matches(msg, KeyLayoutZoom):
		m.layout = layoutZoom
		m.relayout()
		m.toast = newToast("layout: zoom", styles.Info)
		return m, nil
	case key.Matches(msg, KeyNew):
		m.form = forms.New(m.defaultWS, m.rolesDefaults)
		m.modal = modalNewRun
		return m, nil
	case key.Matches(msg, KeyAttach):
		return m, m.attachCurrent()
	case key.Matches(msg, KeyAnswer):
		return m, m.openAnswerModal()
	case key.Matches(msg, KeySort):
		m.runs.CycleSort()
		m.refreshDetail()
		m.toast = newToast("sort: "+m.runs.Sort.String(), styles.Info)
		return m, nil
	case key.Matches(msg, KeyActivity):
		// Cycle off -> small (5 rows) -> large (12 rows) -> off so a
		// busy fleet can opt into a wider drawer without losing the
		// "off" state. Layout is re-flowed so the main pane shrinks
		// in lockstep and the View stays exactly terminal-height.
		m.activitySize = (m.activitySize + 1) % 3
		m.relayout()
		m.toast = newToast("activity: "+m.activitySize.String(), styles.Info)
		return m, nil
	case key.Matches(msg, KeyPreview):
		return m, m.openPreviewModal()
	case key.Matches(msg, KeyKB):
		return m, m.openKBModal()
	case key.Matches(msg, KeyVerify):
		if r, ok := m.runs.Selected(); ok {
			m.toast = newToast("verifying "+r.ShortID()+"…", styles.Info)
			return m, cmds.VerifyCmd(r.ID)
		}
		return m, nil
	case key.Matches(msg, KeyResumeRunner):
		if r, ok := m.runs.Selected(); ok {
			m.toast = newToast("resume runner "+r.ShortID()+"…", styles.Info)
			return m, cmds.ResumeCmd(r.ID)
		}
		return m, nil
	case key.Matches(msg, KeyReplan):
		if r, ok := m.runs.Selected(); ok {
			m.toast = newToast("replan "+r.ShortID()+"…", styles.Info)
			return m, cmds.ReplanCmd(r.ID)
		}
		return m, nil
	case key.Matches(msg, KeyKill):
		if r, ok := m.runs.Selected(); ok {
			role := ""
			if m.focus == focusRoles {
				role = m.detail.SelectedRole()
			}
			m.askConfirm("Kill", "Send Ctrl-C and mark killed?", control.ActionKill, r.ID, role)
			return m, nil
		}
		return m, nil
	case key.Matches(msg, KeyRm):
		if r, ok := m.runs.Selected(); ok {
			m.askConfirm("Remove", "Archive run dir and drop learnings?", control.ActionRemove, r.ID, "")
			return m, nil
		}
		return m, nil
	case key.Matches(msg, KeyControl):
		if r, ok := m.runs.Selected(); ok {
			role := ""
			if m.focus == focusRoles {
				role = m.detail.SelectedRole()
			}
			label := r.ShortID()
			if role != "" {
				label += ":" + role
			}
			m.control = control.New(label, true, role != "")
			m.modal = modalControl
			return m, nil
		}
		return m, nil
	}

	// Grid layout cell navigation: h/j/k/l (and arrows) move between
	// the four role tiles. We intercept here, before the focused-pane
	// switch, because the standard up/down scroll is meaningless in
	// the grid layout.
	if m.layout == layoutGrid {
		switch {
		case key.Matches(msg, KeyGridLeft):
			if m.gridCursor%2 == 1 {
				m.gridCursor--
			}
			return m, nil
		case key.Matches(msg, KeyGridRight):
			if m.gridCursor%2 == 0 && m.gridCursor+1 < gridCellCount {
				m.gridCursor++
			}
			return m, nil
		case key.Matches(msg, KeyGridUp):
			if m.gridCursor >= 2 {
				m.gridCursor -= 2
			}
			return m, nil
		case key.Matches(msg, KeyGridDown):
			if m.gridCursor < 2 {
				m.gridCursor += 2
			}
			return m, nil
		}
	}

	switch m.focus {
	case focusRuns:
		oldID := indexOfSelected(m)
		var cmd tea.Cmd
		m.runs, cmd = m.runs.Update(msg)
		if oldID != indexOfSelected(m) {
			m.refreshDetail()
		}
		return m, cmd
	case focusRoles:
		switch {
		case key.Matches(msg, KeyUp):
			m.detail.MoveCursor(-1)
			m.refreshTail()
		case key.Matches(msg, KeyDown):
			m.detail.MoveCursor(1)
			m.refreshTail()
		}
		return m, nil
	case focusTail:
		var cmd tea.Cmd
		m.tail, cmd = m.tail.Update(msg)
		return m, cmd
	}
	return m, nil
}

func (m *Model) handleModalKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch m.modal {
	case modalHelp:
		m.modal = modalNone
		return m, nil
	case modalNewRun:
		var cmd tea.Cmd
		var result *forms.NewRunResult
		var cancelled bool
		m.form, cmd, result, cancelled = m.form.Update(msg)
		if cancelled {
			m.modal = modalNone
			return m, nil
		}
		if result != nil {
			m.modal = modalNone
			m.toast = newToast("starting run: "+truncate(result.Goal, 60), styles.Info)
			ws := result.Workspace
			if ws == "" {
				ws = m.defaultWS
			}
			return m, cmds.NewRunCmd(result.Goal, ws, result.PlanOnly, result.Workflow, result.Roles)
		}
		return m, cmd
	case modalControl:
		var sel *control.Item
		var cancelled bool
		m.control, sel, cancelled = m.control.Update(msg)
		if cancelled {
			m.modal = modalNone
			return m, nil
		}
		if sel != nil {
			m.modal = modalNone
			r, ok := m.runs.Selected()
			if !ok {
				return m, nil
			}
			role := ""
			if m.focus == focusRoles {
				role = m.detail.SelectedRole()
			}
			if sel.Action == control.ActionKill {
				m.askConfirm("Kill", "Send Ctrl-C and mark killed?", sel.Action, r.ID, role)
				return m, nil
			}
			if sel.Action == control.ActionRemove {
				m.askConfirm("Remove", "Archive run dir and drop learnings?", sel.Action, r.ID, "")
				return m, nil
			}
			cmd := m.dispatchControlAction(r.ID, role, sel.Action)
			return m, cmd
		}
		return m, nil
	case modalConfirm:
		switch msg.String() {
		case "y", "Y", "enter":
			c := m.confirm
			m.modal = modalNone
			m.toast = newToast(strings.ToLower(c.title)+" "+shortLabel(c.rid, c.role)+"…", styles.Warn)
			return m, m.dispatchControlAction(c.rid, c.role, c.action)
		case "n", "N", "esc", "ctrl+c", "q":
			m.modal = modalNone
			return m, nil
		}
		return m, nil
	case modalAnswer:
		var cmd tea.Cmd
		var result *answer.Result
		var cancelled bool
		m.answer, cmd, result, cancelled = m.answer.Update(msg)
		if cancelled {
			m.modal = modalNone
			return m, nil
		}
		if result != nil {
			m.modal = modalNone
			m.toast = newToast(fmt.Sprintf("answering %s (%d)", shortLabel(result.RID, ""), len(result.Answers)), styles.Info)
			return m, cmds.AnswerCmd(result.RID, result.Answers)
		}
		return m, cmd
	case modalPreview:
		cmd, cancelled := m.preview.Update(msg)
		if cancelled {
			m.preview.Close()
			m.modal = modalNone
			return m, nil
		}
		return m, cmd
	case modalKB:
		cmd, query, cancelled := m.kb.Update(msg)
		if cancelled {
			m.modal = modalNone
			return m, nil
		}
		if query != "" {
			m.kb.MarkLoading(query)
			return m, cmds.KBSearchCmd(query, 10)
		}
		return m, cmd
	}
	return m, nil
}

// openPreviewModal opens the tmux capture-pane preview for the currently
// focused role. When focus is not on the roles pane (or the selected run
// has no tmux pane info), surfaces a toast and returns nil.
func (m *Model) openPreviewModal() tea.Cmd {
	r, ok := m.runs.Selected()
	if !ok {
		m.toast = newToast("no run selected", styles.Warn)
		return nil
	}
	target, label := m.previewTarget(r)
	if target == "" {
		m.toast = newToast("no tmux pane for selection", styles.Warn)
		return nil
	}
	cmd := m.preview.Open(target, label)
	w, h := m.previewSize()
	m.preview.SetSize(w, h)
	m.modal = modalPreview
	return tea.Batch(cmd, previewTickCmd())
}

// previewTarget returns the tmux target (and friendly label) for the
// currently focused selection: focused role first, otherwise the run's
// first running role, otherwise empty.
func (m *Model) previewTarget(r state.Run) (string, string) {
	role := ""
	if m.focus == focusRoles {
		role = m.detail.SelectedRole()
	}
	if role != "" {
		if rd, ok := r.Roles[role]; ok && rd.Tmux != nil {
			return roleTmuxTarget(r, rd), r.ShortID() + " / " + role
		}
	}
	for name, rd := range r.Roles {
		if rd.Tmux == nil || rd.Tmux.Target == "" && rd.Tmux.Window == "" {
			continue
		}
		return roleTmuxTarget(r, rd), r.ShortID() + " / " + name
	}
	return "", ""
}

// roleTmuxTarget returns the tmux pane target. Prefers the explicit
// `target` field (e.g. "ralph-foo:executor-1.0"), then synthesizes one
// from session+window so the modal still works on older runs.
func roleTmuxTarget(r state.Run, rd state.Role) string {
	if rd.Tmux == nil {
		return ""
	}
	if rd.Tmux.Target != "" {
		return rd.Tmux.Target
	}
	if rd.Tmux.Window != "" {
		session := rd.Tmux.Session
		if session == "" {
			session = r.SessionName()
		}
		return session + ":" + rd.Tmux.Window
	}
	return ""
}

// previewSize derives the modal area from the current terminal so the
// captured pane has room to breathe but never overlaps the window edge.
func (m *Model) previewSize() (int, int) {
	w := m.width - 8
	if w < 40 {
		w = 40
	}
	h := m.height - 6
	if h < 12 {
		h = 12
	}
	return w, h
}

// attachReadOnlyPopup launches `tmux display-popup -E` running an
// `attach-session -r` against the modal's target. The popup hovers
// without exiting the TUI; when it closes, the TUI redraws.
func (m *Model) attachReadOnlyPopup(target string) tea.Cmd {
	if target == "" {
		m.toast = newToast("no tmux target to attach", styles.Warn)
		return nil
	}
	bin, err := exec.LookPath("tmux")
	if err != nil {
		m.toast = newToast("tmux not found on PATH", styles.Bad)
		return nil
	}
	body := fmt.Sprintf("tmux attach-session -r -t %s", shellQuote(target))
	cmd := exec.Command(bin, "display-popup", "-E", "-w", "90%", "-h", "85%", body)
	return tea.ExecProcess(cmd, func(err error) tea.Msg {
		if err != nil {
			return cmds.CmdResultMsg{
				Action: "attach-popup",
				Target: target,
				Stderr: err.Error(),
				Code:   -1,
			}
		}
		return cmds.CmdResultMsg{
			Action: "attach-popup",
			Target: target,
			Code:   0,
		}
	})
}

// shellQuote single-quotes a string so it survives the body of a tmux
// display-popup `-E` command. Tmux wraps the body in `sh -c` so any
// single-quote inside the target needs escaping.
func shellQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", `'\''`) + "'"
}

// openAnswerModal opens the answer textinput modal for the currently
// selected run when it has open clarifying questions. Otherwise it surfaces
// a friendly toast explaining there is nothing to answer.
func (m *Model) openAnswerModal() tea.Cmd {
	r, ok := m.runs.Selected()
	if !ok {
		m.toast = newToast("no run selected", styles.Warn)
		return nil
	}
	open := r.OpenQuestions()
	if len(open) == 0 {
		m.toast = newToast("no open questions on "+r.ShortID(), styles.Info)
		return nil
	}
	m.answer = answer.New(r.ID, open)
	if m.width > 0 {
		m.answer.SetWidth(m.width - 8)
	}
	m.modal = modalAnswer
	return nil
}

// openKBModal opens the AI knowledgebase browser. Always available —
// the KB is global, not per-run — so this never short-circuits on a
// missing selection. The modal initializes empty; the user types a
// query and presses Enter to dispatch a `,ai-kb search` shell-out.
func (m *Model) openKBModal() tea.Cmd {
	m.kb = kbmod.New()
	if m.width > 0 {
		m.kb.SetWidth(m.width - 8)
	}
	m.modal = modalKB
	return nil
}

// --- helpers ----------------------------------------------------------------

func (m *Model) cycleFocus(delta int) {
	switch m.focus {
	case focusRuns:
		if delta > 0 {
			m.focus = focusRoles
		} else {
			m.focus = focusTail
		}
	case focusRoles:
		if delta > 0 {
			m.focus = focusTail
		} else {
			m.focus = focusRuns
		}
	case focusTail:
		if delta > 0 {
			m.focus = focusRuns
		} else {
			m.focus = focusRoles
		}
	}
}

func (m *Model) attachCurrent() tea.Cmd {
	r, ok := m.runs.Selected()
	if !ok {
		return nil
	}
	target := r.SessionName()
	role := ""
	if m.focus == focusRoles {
		role = m.detail.SelectedRole()
	}
	if role != "" {
		if rd, ok := r.Roles[role]; ok && rd.Tmux != nil && rd.Tmux.Window != "" {
			target = target + ":" + rd.Tmux.Window
		}
	}
	return cmds.AttachCmdAction(target)
}

func (m *Model) dispatchControlAction(rid, role string, action control.Action) tea.Cmd {
	switch action {
	case control.ActionVerify:
		return cmds.VerifyCmd(rid)
	case control.ActionResumeRunner:
		return cmds.ResumeCmd(rid)
	case control.ActionReplan:
		return cmds.ReplanCmd(rid)
	case control.ActionKill:
		return cmds.KillCmd(rid, role)
	case control.ActionRemove:
		return cmds.RemoveCmd(rid)
	case control.ActionTakeover:
		return cmds.ControlCmd(rid, role, "takeover")
	case control.ActionDirty:
		return cmds.ControlCmd(rid, role, "dirty")
	case control.ActionResume:
		return cmds.ControlCmd(rid, role, "resume")
	case control.ActionAuto:
		return cmds.ControlCmd(rid, role, "auto")
	}
	return nil
}

func (m *Model) askConfirm(title, body string, action control.Action, rid, role string) {
	m.confirm = confirmInfo{title: title, body: body, action: action, rid: rid, role: role}
	m.modal = modalConfirm
}

func (m *Model) viewConfirm() string {
	target := shortLabel(m.confirm.rid, m.confirm.role)
	rows := []string{
		styles.Title.Render(m.confirm.title + " " + target + "?"),
		"",
		m.confirm.body,
		"",
		lipgloss.NewStyle().Foreground(styles.Warn).Bold(true).Render("enter/y: confirm"),
		styles.Faint.Render("n/q/esc/ctrl-c: cancel"),
	}
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

func shortLabel(rid, role string) string {
	label := rid
	if i := strings.LastIndex(rid, "-"); i >= 0 && i+1 < len(rid) {
		label = rid[i+1:]
	}
	if role != "" {
		label += ":" + role
	}
	return label
}

func (m *Model) refreshDetail() {
	if r, ok := m.runs.Selected(); ok {
		m.detail.SetRun(r)
	} else {
		m.detail.Clear()
	}
	// Reset the grid cell cursor whenever the selected run changes so a
	// stale index from a prior run can't point past the new run's role
	// count.
	m.gridCursor = 0
	m.refreshTail()
}

func (m *Model) refreshTail() {
	role := m.detail.SelectedRole()
	if role == "" {
		_ = m.tail.SetPath("")
		return
	}
	r := m.detail.Run
	rd, ok := r.Roles[role]
	if !ok || rd.OutputPath == "" {
		_ = m.tail.SetPath("")
		return
	}
	if m.tail.Path() != rd.OutputPath {
		_ = m.tail.SetPath(rd.OutputPath)
	} else {
		_ = m.tail.Reload()
	}
}

func (m *Model) refreshDetailTail() {
	if m.tail.Path() != "" {
		_ = m.tail.Reload()
	}
}

func (m *Model) applyRunUpdate(r state.Run) {
	for i, existing := range m.runs.Runs {
		if existing.ID == r.ID {
			m.runs.Runs[i] = r
			break
		}
	}
	if cur, ok := m.runs.Selected(); ok && cur.ID == r.ID {
		m.detail.SetRun(r)
		m.refreshTail()
	}
}

func indexOfSelected(m *Model) string {
	if r, ok := m.runs.Selected(); ok {
		return r.ID
	}
	return ""
}

func (m *Model) expireToast() {
	if m.toast.until.IsZero() {
		return
	}
	if time.Now().After(m.toast.until) {
		m.toast = toastInfo{}
	}
}

// --- watcher subscription ---------------------------------------------------

type watcherEventMsg struct{ Path string }

func (m *Model) watcherCmd() tea.Cmd {
	if m.watcherEvents == nil {
		return nil
	}
	return func() tea.Msg {
		ev, ok := <-m.watcherEvents
		if !ok {
			return nil
		}
		return watcherEventMsg{Path: ev.Path}
	}
}

func shouldReload(path string) bool {
	base := filepath.Base(path)
	switch base {
	case "manifest.json", "decisions.log", "progress.jsonl", "verdicts.jsonl", "output.log", "spec.md":
		return true
	}
	if strings.HasPrefix(base, "go-") {
		return true
	}
	return false
}

// --- periodic tick (for toast expiry + KB-stats refresh) ------------------

// tickMsg is the per-second heartbeat. The counter monotonically advances
// so handlers can opt into slower cadences (e.g. KB stats every 30s)
// without standing up a second timer.
type tickMsg struct{ count int }

func periodicTickCmd(count int) tea.Cmd {
	return tea.Tick(time.Second, func(time.Time) tea.Msg { return tickMsg{count: count} })
}

// --- toast ------------------------------------------------------------------

type toastInfo struct {
	text  string
	color lipgloss.Color
	until time.Time
}

func newToast(text string, color lipgloss.Color) toastInfo {
	return toastInfo{text: text, color: color, until: time.Now().Add(4 * time.Second)}
}

// --- layout / view ---------------------------------------------------------

// relayout refreshes the per-pane sizes after window resize or layout
// switch. Cheap to call; touches no state machinery beyond pane sizes.
func (m *Model) relayout() {
	if m.width == 0 || m.height == 0 {
		return
	}
	left, rightTop, rightBot := m.paneRects()
	m.runs.SetSize(left.w, left.h)
	m.detail.SetSize(rightTop.w, rightTop.h)
	m.tail.SetSize(rightBot.w, rightBot.h)
}

type rect struct{ w, h int }

// activityHeight returns the row count reserved for the activity drawer
// at its current size, including the surrounding rule line. Zero when
// the drawer is hidden.
//
//   - small: heading + 5 inner rows + spacer = 6 rows
//   - large: heading + 12 inner rows + spacer = 13 rows
func (m *Model) activityHeight() int {
	switch m.activitySize {
	case activitySmall:
		return 6
	case activityLarge:
		return 13
	}
	return 0
}

func (m *Model) paneRects() (left, rightTop, rightBot rect) {
	statusH := 1
	actH := m.activityHeight()
	main := m.height - statusH - actH
	if main < 4 {
		main = 4
	}
	if m.layout == layoutZoom {
		switch m.focus {
		case focusRuns:
			return rect{w: m.width, h: main}, rect{}, rect{}
		case focusRoles:
			return rect{}, rect{w: m.width, h: main}, rect{}
		case focusTail:
			return rect{}, rect{}, rect{w: m.width, h: main}
		}
	}
	leftW := m.width / 2
	if leftW < 32 {
		leftW = 32
	}
	if leftW > m.width-32 && m.width >= 64 {
		leftW = m.width - 32
	}
	rightW := m.width - leftW
	rightTopH := main * 3 / 5
	if rightTopH < 6 {
		rightTopH = 6
	}
	rightBotH := main - rightTopH
	if rightBotH < 4 {
		rightBotH = 4
	}
	return rect{w: leftW, h: main}, rect{w: rightW, h: rightTopH}, rect{w: rightW, h: rightBotH}
}

func (m *Model) viewMain() string {
	switch m.layout {
	case layoutGrid:
		return m.viewRoleGrid()
	case layoutZoom:
		return m.viewZoomedPane()
	}
	left, rightTop, rightBot := m.paneRects()
	leftView := styles.Pane(m.runs.View(), m.focus == focusRuns, left.w, left.h)
	rightTopView := styles.Pane(m.detail.View(), m.focus == focusRoles, rightTop.w, rightTop.h)
	rightBotView := styles.Pane(m.tail.View(), m.focus == focusTail, rightBot.w, rightBot.h)
	right := lipgloss.JoinVertical(lipgloss.Left, rightTopView, rightBotView)
	return lipgloss.JoinHorizontal(lipgloss.Top, leftView, right)
}

// viewZoomedPane renders the focused pane full-width/full-height. Mirrors
// the legacy `enter` zoom toggle behaviour but driven by `m.layout`.
func (m *Model) viewZoomedPane() string {
	left, rightTop, rightBot := m.paneRects()
	switch m.focus {
	case focusRuns:
		return styles.Pane(m.runs.View(), true, left.w, left.h)
	case focusRoles:
		return styles.Pane(m.detail.View(), true, rightTop.w, rightTop.h)
	case focusTail:
		return styles.Pane(m.tail.View(), true, rightBot.w, rightBot.h)
	}
	return ""
}

// gridCellCount is the maximum number of role tiles rendered in the
// 2x2 grid layout (planner / executor / reviewer / re_reviewer of the
// latest iteration).
const gridCellCount = 4

// viewRoleGrid renders a 2x2 grid of role-tail panes for the currently
// selected run, plus a thin header showing run identity. Each cell shows
// the last N lines of that role's output.log so the operator can scan
// what every role is doing simultaneously without leaving the TUI.
//
// Cell selection: the latest iteration's planner/executor/reviewer/re_reviewer
// (per the role naming convention `<role>-<iter>`). Missing roles render
// as a faint placeholder so the grid keeps its 2x2 shape. The cell at
// `m.gridCursor` is the focused tile; h/j/k/l move the cursor and `enter`
// drills the cursored cell into the default detail layout (focusTail).
func (m *Model) viewRoleGrid() string {
	statusH := 1
	main := m.height - statusH - m.activityHeight()
	if main < 4 {
		main = 4
	}
	r, ok := m.runs.Selected()
	if !ok {
		return styles.Pane(styles.Faint.Render("no run selected"), true, m.width, main)
	}
	header := lipgloss.NewStyle().
		Foreground(styles.Foreground).
		Bold(true).
		Render(fmt.Sprintf(" %s · %s · iter %d ", r.ID, displayRunStatus(r), len(r.Iterations)))
	headerH := 1
	gridH := main - headerH
	if gridH < 4 {
		gridH = 4
	}
	cellH := gridH / 2
	cellW := m.width / 2
	if cellW < 24 {
		cellW = 24
	}
	cells := pickGridRoles(r)
	cursor := m.gridCursor
	if cursor >= len(cells) && len(cells) > 0 {
		cursor = len(cells) - 1
	}
	tiles := make([]string, 0, gridCellCount)
	for i, cell := range cells {
		tiles = append(tiles, styles.Pane(renderGridCell(cell), i == cursor, cellW, cellH))
	}
	for len(tiles) < gridCellCount {
		tiles = append(tiles, styles.Pane(styles.Faint.Render("no role"), false, cellW, cellH))
	}
	row1 := lipgloss.JoinHorizontal(lipgloss.Top, tiles[0], tiles[1])
	row2 := lipgloss.JoinHorizontal(lipgloss.Top, tiles[2], tiles[3])
	return lipgloss.JoinVertical(lipgloss.Left, header, row1, row2)
}

// gridCell holds the per-tile data the role-grid layout displays.
type gridCell struct {
	Name string
	Role state.Role
}

// pickGridRoles returns up to 4 grid cells for the run, in canonical
// planner/executor/reviewer/re_reviewer order, prioritising the latest
// iteration when multiple iterations of the same role exist.
func pickGridRoles(r state.Run) []gridCell {
	want := []string{"planner", "executor", "reviewer", "re_reviewer"}
	picked := make([]gridCell, 0, 4)
	for _, root := range want {
		var bestName string
		var bestRole state.Role
		bestIter := -1
		for name, role := range r.Roles {
			if !strings.HasPrefix(name, root+"-") {
				continue
			}
			suffix := name[len(root)+1:]
			n := 0
			if _, err := fmt.Sscanf(suffix, "%d", &n); err != nil {
				continue
			}
			if n > bestIter {
				bestIter = n
				bestName = name
				bestRole = role
			}
		}
		if bestIter >= 0 {
			picked = append(picked, gridCell{Name: bestName, Role: bestRole})
		}
	}
	return picked
}

// renderGridCell composes the cell body: name + status + last N lines of
// output.log (read fresh each render so the live tail is always current).
//
// Reads are best-effort and capped to a small number of trailing lines so
// a giant log doesn't slow the render path.
func renderGridCell(c gridCell) string {
	name := lipgloss.NewStyle().Foreground(styles.Accent).Bold(true).Render(c.Name)
	status := styles.StatusBadge(orStr(c.Role.ValidationStatus, c.Role.Status))
	control := orStr(c.Role.ControlState, "automated")
	header := name + "  " + status + "  ctrl=" + control
	body := readTail(c.Role.OutputPath, 12)
	if body == "" {
		body = styles.Faint.Render("(no output yet)")
	}
	return header + "\n" + body
}

func displayRunStatus(r state.Run) string {
	if r.Validation == "passed" && r.Status == "completed" {
		return "passed"
	}
	if r.Status != "" {
		return r.Status
	}
	return "-"
}

func orStr(a, b string) string {
	if a == "" {
		return b
	}
	return a
}

// readTail returns the last `n` lines of the file at `path`, best-effort.
// Empty string on missing path or read error.
func readTail(path string, n int) string {
	if path == "" {
		return ""
	}
	const capBytes = 16 * 1024
	data, err := readLastBytes(path, capBytes)
	if err != nil || len(data) == 0 {
		return ""
	}
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, "\n")
}

// readLastBytes reads at most `max` trailing bytes of the file. Used by
// the role-grid cell tail to keep render paths cheap regardless of log
// size.
func readLastBytes(path string, max int64) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		return nil, err
	}
	size := st.Size()
	if size <= 0 {
		return nil, nil
	}
	if size > max {
		_, err := f.Seek(size-max, 0)
		if err != nil {
			return nil, err
		}
	}
	buf := make([]byte, max)
	n, err := f.Read(buf)
	if err != nil && n == 0 {
		return nil, err
	}
	return buf[:n], nil
}

// viewActivityDrawer renders a 6-row strip above the status bar listing the
// most recent decisions and verdicts across every parent run, sorted most
// recent first. Read on demand: activity.LoadRecent caps each file's tail
// so re-reading on every render stays cheap. Hidden by default; toggled
// via KeyActivity.
func (m *Model) viewActivityDrawer() string {
	innerRows := 5
	if m.activitySize == activityLarge {
		innerRows = 12
	}
	heading := lipgloss.NewStyle().
		Foreground(styles.Accent).
		Bold(true).
		Render("activity")
	hint := lipgloss.NewStyle().Foreground(styles.Subtle).Render("(S cycles size)")
	header := heading + " " + hint
	header = truncate(header, m.width)

	events := activity.LoadRecent(innerRows)
	rows := make([]string, 0, innerRows)
	if len(events) == 0 {
		rows = append(rows, styles.Faint.Render("(no recent decisions or verdicts)"))
	} else {
		for _, ev := range events {
			line := strings.ReplaceAll(activity.FormatLine(ev, 12), "\t", " ")
			line = strings.ReplaceAll(line, "\r", " ")
			if lipgloss.Width(line) > m.width {
				line = lipgloss.NewStyle().MaxWidth(m.width).Render(line)
			}
			rows = append(rows, line)
		}
	}
	for len(rows) < innerRows {
		rows = append(rows, "")
	}
	return lipgloss.JoinVertical(lipgloss.Left, append([]string{header}, rows...)...)
}

func (m *Model) viewStatusBar() string {
	// StatusBar adds Padding(0, 1) (2 chars total horizontal). Pre-shrink the
	// inner text width so the rendered result is exactly m.width and never
	// wraps to a second row, which would scroll the top border off the screen.
	inner := m.width - 2
	if inner < 8 {
		inner = 8
	}
	left := fmt.Sprintf("ralph-tui  runs=%d  layout=%s", len(m.runs.Runs), m.layout)
	if q := m.openQuestionsTotal(); q > 0 {
		qSeg := lipgloss.NewStyle().Foreground(styles.Bad).Bold(true).
			Render(fmt.Sprintf("  Q:%d", q))
		left += qSeg
	}
	if m.kbStats.Capsules > 0 {
		kbSeg := lipgloss.NewStyle().Foreground(styles.Info).
			Render(fmt.Sprintf("  KB:%d", m.kbStats.Capsules))
		left += kbSeg
	}
	right := "?: help · n: new · A: answer · c: ctl · p: preview · K: kb · S: act · 1/2/3: layout · q: quit"
	if m.toast.text != "" {
		toast := lipgloss.NewStyle().
			Foreground(styles.Foreground).
			Background(m.toast.color).
			Render(m.toast.text)
		return styles.StatusBar.Width(m.width).Render(padBetween(left, toast, inner))
	}
	return styles.StatusBar.Width(m.width).Render(padBetween(left, right, inner))
}

// openQuestionsTotal sums open clarifying questions across the entire
// fleet. Used by the status bar to surface "this many runs need you" at a
// glance, without requiring the user to scan the runs list.
func (m *Model) openQuestionsTotal() int {
	total := 0
	for _, r := range m.runs.Runs {
		total += len(r.OpenQuestions())
	}
	return total
}

func padBetween(left, right string, width int) string {
	if width <= 0 {
		return left + " " + right
	}
	lw := lipgloss.Width(left)
	rw := lipgloss.Width(right)
	// If both don't fit, drop the right side first, then truncate the left so
	// the joined string is never wider than `width` (avoids row-wrap and the
	// resulting top-border scroll).
	if lw+1+rw > width {
		if lw+1 >= width {
			return truncate(left, width)
		}
		right = truncate(right, width-lw-1)
		rw = lipgloss.Width(right)
	}
	gap := width - lw - rw
	if gap < 1 {
		gap = 1
	}
	return left + strings.Repeat(" ", gap) + right
}

func centerOverlay(modal string, width, height int) string {
	box := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder(), true).
		BorderForeground(styles.Accent).
		Padding(1, 2).
		Render(modal)
	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, box)
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	if n <= 1 {
		return "…"
	}
	return s[:n-1] + "…"
}

// AttachExternal performs the tmux switch-client based on the model's pending
// attach target. Called from main() after Run() returns.
func AttachExternal(target string) error {
	if target == "" {
		return nil
	}
	bin := "tmux"
	if _, err := exec.LookPath(bin); err != nil {
		return err
	}
	verb := "switch-client"
	if os.Getenv("TMUX") == "" {
		verb = "attach-session"
	}
	cmd := exec.Command(bin, verb, "-t", target)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}
