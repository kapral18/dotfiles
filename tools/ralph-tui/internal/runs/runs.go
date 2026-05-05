// Package runs renders the list of Ralph runs in the TUI's left pane.
package runs

import (
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"ralph-tui/internal/state"
	"ralph-tui/internal/styles"
)

// SortMode defines how the fleet view orders runs in the list pane.
//
// `SortNeed` (default) bubbles runs that need the operator's attention to
// the top: parked-on-questions first, then live but not-yet-validated
// runs, then the rest by recency. `SortRecent` is the legacy ordering
// (newest CreatedAt first).
type SortMode int

const (
	SortNeed SortMode = iota
	SortRecent
)

// String returns a short display label for the sort mode (used in the
// status bar / help overlay).
func (s SortMode) String() string {
	switch s {
	case SortRecent:
		return "recent"
	default:
		return "need"
	}
}

// Model is the runs list. It maintains its own selection cursor and width;
// callers feed it updated runs slices and resize messages.
type Model struct {
	Runs        []state.Run
	cursor      int
	width       int
	height      int
	filter      string
	filterMode  bool
	FilterInput string
	Sort        SortMode
}

// New returns an empty list. Use SetRuns to populate.
func New() Model {
	return Model{}
}

// SetRuns replaces the runs slice and clamps the cursor.
func (m *Model) SetRuns(runs []state.Run) {
	m.Runs = runs
	m.clampCursor()
}

// CycleSort advances the sort mode (Need -> Recent -> Need ...) and
// re-clamps the cursor so the same run stays selected when possible.
func (m *Model) CycleSort() {
	if m.Sort == SortNeed {
		m.Sort = SortRecent
	} else {
		m.Sort = SortNeed
	}
	m.clampCursor()
}

// SetSize updates the available render area.
func (m *Model) SetSize(w, h int) {
	m.width, m.height = w, h
}

// IsTyping reports whether the runs list is currently consuming raw text
// input (filter mode). The parent App checks this before dispatching its
// global keybindings so single-letter shortcuts (`q`, `n`, `a`, ...)
// don't shadow filter input — without this, typing `n` to filter for a
// run named "needs-attention" would silently open the new-run modal.
func (m Model) IsTyping() bool { return m.filterMode }

// Selected returns the currently focused run, or zero-value if list is empty.
func (m Model) Selected() (state.Run, bool) {
	visible := m.visible()
	if len(visible) == 0 || m.cursor < 0 || m.cursor >= len(visible) {
		return state.Run{}, false
	}
	return visible[m.cursor], true
}

// Update handles list-scoped key events. Returns the new model + any commands
// the parent should run (currently none — selection changes are observed by
// the parent via Selected()).
func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		if m.filterMode {
			switch {
			case key.Matches(msg, KeyEsc):
				m.filterMode = false
				m.FilterInput = ""
				m.filter = ""
				m.clampCursor()
			case key.Matches(msg, KeyEnter):
				m.filterMode = false
				m.filter = m.FilterInput
				m.clampCursor()
			case msg.Type == tea.KeyBackspace:
				if len(m.FilterInput) > 0 {
					m.FilterInput = m.FilterInput[:len(m.FilterInput)-1]
				}
				m.filter = m.FilterInput
				m.clampCursor()
			case msg.Type == tea.KeyRunes && len(msg.Runes) == 1:
				m.FilterInput += string(msg.Runes)
				m.filter = m.FilterInput
				m.clampCursor()
			}
			return m, nil
		}
		switch {
		case key.Matches(msg, KeyDown):
			if m.cursor < len(m.visible())-1 {
				m.cursor++
			}
		case key.Matches(msg, KeyUp):
			if m.cursor > 0 {
				m.cursor--
			}
		case key.Matches(msg, KeyHome):
			m.cursor = 0
		case key.Matches(msg, KeyEnd):
			m.cursor = max(0, len(m.visible())-1)
		case key.Matches(msg, KeyFilter):
			m.filterMode = true
			m.FilterInput = m.filter
		}
	}
	return m, nil
}

// View renders the list, including a filter footer if active.
func (m Model) View() string {
	visible := m.visible()
	if len(visible) == 0 {
		empty := "no runs yet — press 'n' to start one"
		if m.filter != "" {
			empty = fmt.Sprintf("no runs match %q (esc to clear)", m.filter)
		}
		return styles.Faint.Render(empty)
	}

	var b strings.Builder
	header := lipgloss.NewStyle().Foreground(styles.Subtle).
		Render(fmt.Sprintf("sort: %s  (s to cycle)", m.Sort))
	b.WriteString(header)
	b.WriteByte('\n')
	for i, r := range visible {
		b.WriteString(m.renderRow(i, r))
		b.WriteByte('\n')
	}
	if m.filterMode {
		b.WriteString(styles.Subdued.Render(fmt.Sprintf("/%s_", m.FilterInput)))
	} else if m.filter != "" {
		b.WriteString(styles.Subdued.Render(fmt.Sprintf("filter: %s  (/ to edit, esc to clear)", m.filter)))
	}
	return b.String()
}

func (m Model) renderRow(i int, r state.Run) string {
	cursor := "  "
	style := lipgloss.NewStyle()
	if i == m.cursor {
		cursor = "> "
		style = style.Bold(true)
	}
	statusCol := lipgloss.NewStyle().Foreground(styles.StatusColor(displayStatus(r))).Render(displayStatus(r))
	phase := r.Phase
	if phase == "" {
		phase = "-"
	}
	iters := fmt.Sprintf("%d", len(r.Iterations))
	runner := runnerGlyph(r)
	name := r.Name
	if name == "" {
		name = r.ShortID()
	}
	if maxName := 22; len(name) > maxName {
		name = name[:maxName-1] + "…"
	}
	goal := r.Goal
	if goal == "" {
		goal = "-"
	}
	if maxGoal := m.goalWidth(); maxGoal > 0 && len(goal) > maxGoal {
		goal = goal[:maxGoal-1] + "…"
	}
	qBadge := questionBadge(r)
	spark := iterSparkline(r, 8)
	iterCount := iterTotalLabel(r)
	row := fmt.Sprintf(
		"%s%s %-22s  %-12s  %-11s  %s %s  %s%s %s",
		cursor,
		runner,
		name,
		statusCol,
		phase,
		iterCount,
		spark,
		styles.Subdued.Render("· "+iters+" iter"),
		qBadge,
		styles.Subdued.Render(goal),
	)
	return style.Render(row)
}

// iterTotalLabel renders "n/N" for iterations vs max, or "n" when the
// planner has not emitted a max yet. Used so the operator can read at a
// glance how far through the budget the run is.
func iterTotalLabel(r state.Run) string {
	cur := len(r.Iterations)
	max := maxIterations(r)
	if max <= 0 {
		return fmt.Sprintf("%d/?", cur)
	}
	return fmt.Sprintf("%d/%d", cur, max)
}

// iterSparkline renders one block per iteration colored by its verdict
// (pass=green, fail=red, replan=amber, in-flight or unknown=subtle).
// Width is bounded by `slots`; iterations beyond `slots` collapse into
// the last block so the bar never grows past the column width. Empty
// runs (no iterations recorded yet) render as `slots` dim placeholders
// so the row width stays stable.
func iterSparkline(r state.Run, slots int) string {
	if slots <= 0 {
		return ""
	}
	verdicts := iterationVerdicts(r)
	if len(verdicts) == 0 {
		return lipgloss.NewStyle().Foreground(styles.Subtle).Render(strings.Repeat("░", slots))
	}
	if len(verdicts) > slots {
		verdicts = verdicts[len(verdicts)-slots:]
	}
	var b strings.Builder
	for _, v := range verdicts {
		col, glyph := verdictGlyph(v)
		b.WriteString(lipgloss.NewStyle().Foreground(col).Render(glyph))
	}
	for i := len(verdicts); i < slots; i++ {
		b.WriteString(lipgloss.NewStyle().Foreground(styles.Subtle).Render("░"))
	}
	return b.String()
}

// iterationVerdicts extracts each iteration's primary verdict in order
// so the sparkline reflects history left-to-right.
func iterationVerdicts(r state.Run) []string {
	out := make([]string, 0, len(r.Iterations))
	for _, it := range r.Iterations {
		v := it.PrimaryVerdict
		if v == "" {
			v = it.Verdict
		}
		if v == "" {
			v = it.Phase
		}
		out = append(out, strings.ToLower(v))
	}
	return out
}

// verdictGlyph maps a verdict (or phase) string to a colored single-cell
// glyph for the sparkline. Unknown values fall through to a faint dot so
// the bar is never empty when an iteration has been recorded.
func verdictGlyph(v string) (lipgloss.Color, string) {
	switch v {
	case "pass", "passed", "complete", "completed":
		return styles.OK, "█"
	case "fail", "failed", "block", "blocked":
		return styles.Bad, "█"
	case "replan", "replan_requested", "needs_verification":
		return styles.Warn, "▆"
	case "running", "executing", "reviewing", "rereviewing", "planning", "replanning":
		return styles.Info, "▄"
	case "killed":
		return styles.Bad, "▆"
	default:
		return styles.Subtle, "░"
	}
}

// maxIterations pulls the planner-emitted max_iterations from the run's
// Spec map; returns 0 when the spec hasn't landed yet.
func maxIterations(r state.Run) int {
	v, ok := r.Spec["max_iterations"]
	if !ok {
		return 0
	}
	switch n := v.(type) {
	case float64:
		return int(n)
	case int:
		return n
	}
	return 0
}

// questionBadge renders an inline `Q:N` segment when the run has open
// clarifying questions, so the operator sees "this run wants me" before
// drilling into the detail pane.
func questionBadge(r state.Run) string {
	open := len(r.OpenQuestions())
	if open == 0 {
		return ""
	}
	col := styles.Warn
	if r.AwaitingHuman() {
		col = styles.Bad
	}
	body := fmt.Sprintf(" Q:%d", open)
	return lipgloss.NewStyle().Foreground(col).Bold(true).Render(body)
}

// runnerGlyph paints a heartbeat-aware status dot for the runner column.
//
//   - bright violet `●`  - alive + heartbeat fresh (<= 30s)
//   - amber       `●`  - alive but heartbeat stale (>30s, suggests stuck/blocked)
//   - red dim     `●`  - explicitly dead
//   - amber       `R`  - replan queued (no live runner)
//   - blank       ` `  - never started
//
// Heartbeat staleness is derived from RunnerInfo.HeartbeatAt; if the
// orchestrator has not been writing heartbeats yet the dot stays bright
// violet so users don't see false alarms.
func runnerGlyph(r state.Run) string {
	if r.Runner == nil {
		if r.ReplanQueued {
			return lipgloss.NewStyle().Foreground(styles.Warn).Render("R")
		}
		return " "
	}
	if !r.Runner.Alive {
		return lipgloss.NewStyle().Foreground(styles.Bad).Render("●")
	}
	col := styles.Accent
	if hb := parseRFC3339(r.Runner.HeartbeatAt); !hb.IsZero() && time.Since(hb) > 30*time.Second {
		col = styles.Warn
	}
	return lipgloss.NewStyle().Foreground(col).Bold(true).Render("●")
}

// parseRFC3339 returns the parsed time or zero on failure. Encapsulated
// so unit tests can pin behavior on malformed timestamps.
func parseRFC3339(s string) time.Time {
	if s == "" {
		return time.Time{}
	}
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		return time.Time{}
	}
	return t
}

func displayStatus(r state.Run) string {
	v := r.Validation
	s := r.Status
	if v == "passed" && s == "completed" {
		return "passed"
	}
	if v != "" && v != "passed" {
		return v
	}
	if s != "" {
		return s
	}
	return "-"
}

func (m *Model) clampCursor() {
	visible := m.visible()
	if len(visible) == 0 {
		m.cursor = 0
		return
	}
	if m.cursor >= len(visible) {
		m.cursor = len(visible) - 1
	}
	if m.cursor < 0 {
		m.cursor = 0
	}
}

// goalWidth returns the budget for the trailing goal column. The
// constant subtracts the visible width of all preceding columns at
// their worst case so the row never wraps even when status words are
// long ("needs_iteration") and the question badge is present:
//
//	cursor(2) + runner(1) + space(1) + name_padded(22) + sep(2)
//	+ status(15 worst) + sep(2) + phase(11) + sep(2) + iter(6)
//	+ space(1) + spark(8) + sep(2) + "· NN iter"(11) + " Q:NN"(5)
//	+ space(1) + safety(2) ≈ 94
func (m Model) goalWidth() int {
	if m.width <= 0 {
		return 40
	}
	w := m.width - 94
	if w < 8 {
		return 8
	}
	return w
}

func (m Model) visible() []state.Run {
	out := make([]state.Run, 0, len(m.Runs))
	if m.filter == "" {
		out = append(out, m.Runs...)
	} else {
		needle := strings.ToLower(m.filter)
		for _, r := range m.Runs {
			hay := strings.ToLower(r.ID + " " + r.Name + " " + r.Goal + " " + r.Status + " " + r.Validation)
			if strings.Contains(hay, needle) {
				out = append(out, r)
			}
		}
	}
	if m.Sort == SortNeed {
		sortByAttentionNeed(out)
	}
	return out
}

// sortByAttentionNeed orders runs so parked-on-questions and live work
// surface above completed/failed runs. Within the same priority bucket,
// runs are stable-sorted newest-first so recent activity stays near the
// top of the list — matching the user's "horde of Ralphs" expectation
// that whatever needs attention shows up at the top.
func sortByAttentionNeed(rs []state.Run) {
	sort.SliceStable(rs, func(i, j int) bool {
		pi, pj := attentionPriority(rs[i]), attentionPriority(rs[j])
		if pi != pj {
			return pi < pj
		}
		ti, tj := rs[i].CreatedTime(), rs[j].CreatedTime()
		if ti.Equal(tj) {
			return rs[i].ID > rs[j].ID
		}
		return ti.After(tj)
	})
}

// attentionPriority assigns a numeric attention rank: lower = surface
// first.
//
//	0: awaiting_human (operator must answer to unblock)
//	1: live runner with open questions but mid-iteration
//	2: needs_verification / dirty_control / manual_control
//	3: running (healthy)
//	4: needs_human (control parked, no open questions)
//	5: completed / passed
//	6: failed / killed
//	9: anything else
func attentionPriority(r state.Run) int {
	if r.Status == "awaiting_human" {
		return 0
	}
	if len(r.OpenQuestions()) > 0 {
		return 1
	}
	switch r.Validation {
	case "needs_verification":
		return 2
	}
	if r.BlockReason != "" {
		return 2
	}
	switch r.Status {
	case "running":
		return 3
	case "needs_human":
		return 4
	case "completed":
		if r.Validation == "passed" {
			return 5
		}
		return 5
	case "failed", "killed":
		return 6
	}
	return 9
}

// Keys exposed to parent App for help overlay rendering and conflict checks.
var (
	KeyUp     = key.NewBinding(key.WithKeys("up", "k"), key.WithHelp("↑/k", "up"))
	KeyDown   = key.NewBinding(key.WithKeys("down", "j"), key.WithHelp("↓/j", "down"))
	KeyHome   = key.NewBinding(key.WithKeys("home", "g"), key.WithHelp("g/Home", "first"))
	KeyEnd    = key.NewBinding(key.WithKeys("end", "G"), key.WithHelp("G/End", "last"))
	KeyFilter = key.NewBinding(key.WithKeys("/"), key.WithHelp("/", "filter"))
	KeyEnter  = key.NewBinding(key.WithKeys("enter"))
	KeyEsc    = key.NewBinding(key.WithKeys("esc"))
)

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
