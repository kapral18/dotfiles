package answer

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"ralph-tui/internal/state"
)

func mkQuestions() []state.Question {
	return []state.Question{
		{ID: "q-1", Role: "planner-1", Text: "Which workspace?", AskedAt: "2026-05-04T00:00:00Z"},
		{ID: "q-2", Role: "executor-1", Text: "Use semantic versioning?", AskedAt: "2026-05-04T00:01:00Z"},
	}
}

func keyRune(r rune) tea.KeyMsg          { return tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}} }
func keyType(k tea.KeyType) tea.KeyMsg   { return tea.KeyMsg{Type: k} }

func typeStr(t *testing.T, m Modal, s string) Modal {
	t.Helper()
	for _, r := range s {
		var sub *Result
		var cancelled bool
		m, _, sub, cancelled = m.Update(keyRune(r))
		if cancelled {
			t.Fatalf("typing %q must not cancel modal", s)
		}
		if sub != nil {
			t.Fatalf("typing %q must not submit modal", s)
		}
	}
	return m
}

func TestModalRendersAllOpenQuestions(t *testing.T) {
	m := New("go-foo-1730000000", mkQuestions())
	m.SetWidth(80)
	v := m.View()
	for _, q := range mkQuestions() {
		if !strings.Contains(v, q.ID) {
			t.Errorf("view missing question id %q:\n%s", q.ID, v)
		}
		if !strings.Contains(v, q.Text) {
			t.Errorf("view missing question text %q", q.Text)
		}
		if !strings.Contains(v, q.Role) {
			t.Errorf("view missing role tag %q", q.Role)
		}
	}
	if !strings.Contains(v, "1730000000") {
		t.Errorf("view should show the short rid in title:\n%s", v)
	}
	if !strings.Contains(v, "Submit answers") {
		t.Errorf("view missing submit button label:\n%s", v)
	}
}

func TestModalEnterAdvancesOffQuestionThenSubmitsOnButton(t *testing.T) {
	m := New("rid-x", mkQuestions())
	m = typeStr(t, m, "first answer")

	m, _, sub, _ := m.Update(keyType(tea.KeyEnter))
	if sub != nil {
		t.Fatalf("first enter must move focus, not submit (got %+v)", sub)
	}
	if m.focus != 1 {
		t.Errorf("focus after enter on q1: got %d want 1", m.focus)
	}
	m = typeStr(t, m, "second answer")
	m, _, sub, _ = m.Update(keyType(tea.KeyEnter))
	if sub != nil {
		t.Fatalf("second enter must move focus to submit, got %+v", sub)
	}
	if m.focus != m.submitIx {
		t.Errorf("focus must be on submit, got %d (submit=%d)", m.focus, m.submitIx)
	}
	_, _, sub, _ = m.Update(keyType(tea.KeyEnter))
	if sub == nil {
		t.Fatal("enter on submit must produce Result")
	}
	if sub.RID != "rid-x" {
		t.Errorf("rid: got %q", sub.RID)
	}
	if got, want := sub.Answers["q-1"], "first answer"; got != want {
		t.Errorf("q-1: got %q want %q", got, want)
	}
	if got, want := sub.Answers["q-2"], "second answer"; got != want {
		t.Errorf("q-2: got %q want %q", got, want)
	}
}

func TestModalSkipsBlankAnswersInResult(t *testing.T) {
	m := New("rid-x", mkQuestions())
	for m.focus != 1 {
		m, _, _, _ = m.Update(keyType(tea.KeyTab))
	}
	m = typeStr(t, m, "only second")
	for m.focus != m.submitIx {
		m, _, _, _ = m.Update(keyType(tea.KeyTab))
	}
	_, _, sub, _ := m.Update(keyType(tea.KeyEnter))
	if sub == nil {
		t.Fatal("submit must succeed when at least one answer is non-empty")
	}
	if _, exists := sub.Answers["q-1"]; exists {
		t.Errorf("blank q-1 must not appear in answers map: %+v", sub.Answers)
	}
	if got, want := sub.Answers["q-2"], "only second"; got != want {
		t.Errorf("q-2: %q != %q", got, want)
	}
}

func TestModalSubmitWithAllBlankSnapsToFirstEmpty(t *testing.T) {
	m := New("rid-x", mkQuestions())
	for m.focus != m.submitIx {
		m, _, _, _ = m.Update(keyType(tea.KeyTab))
	}
	m, _, sub, _ := m.Update(keyType(tea.KeyEnter))
	if sub != nil {
		t.Fatal("submit with no answers must NOT emit Result")
	}
	if m.focus != 0 {
		t.Errorf("focus must snap to first empty question (0), got %d", m.focus)
	}
}

func TestModalEscAndCtrlCAndQCancel(t *testing.T) {
	cases := []struct {
		name string
		key  tea.KeyMsg
	}{
		{"esc", keyType(tea.KeyEsc)},
		{"ctrl+c", tea.KeyMsg{Type: tea.KeyCtrlC}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			m := New("rid-x", mkQuestions())
			_, _, _, cancelled := m.Update(tc.key)
			if !cancelled {
				t.Errorf("%s must cancel modal", tc.name)
			}
		})
	}

	t.Run("q-on-submit", func(t *testing.T) {
		m := New("rid-x", mkQuestions())
		for m.focus != m.submitIx {
			m, _, _, _ = m.Update(keyType(tea.KeyTab))
		}
		_, _, _, cancelled := m.Update(keyRune('q'))
		if !cancelled {
			t.Errorf("q on submit (non-text focus) must cancel modal")
		}
	})

	t.Run("q-on-text-input-types-literally", func(t *testing.T) {
		m := New("rid-x", mkQuestions())
		m = typeStr(t, m, "queue")
		if got := m.inputs[0].Value(); got != "queue" {
			t.Errorf("q must be typed into input as literal, got %q", got)
		}
	})
}

func TestModalJKNavigatesOffSubmitButTypesIntoText(t *testing.T) {
	m := New("rid-x", mkQuestions())
	for m.focus != m.submitIx {
		m, _, _, _ = m.Update(keyType(tea.KeyTab))
	}
	if m.focus != m.submitIx {
		t.Fatalf("setup: focus should be on submit, got %d", m.focus)
	}
	m, _, _, _ = m.Update(keyRune('k'))
	if m.focus != m.submitIx-1 {
		t.Errorf("k on submit must go to last question, got %d", m.focus)
	}

	m2 := New("rid-x", mkQuestions())
	m2 = typeStr(t, m2, "jk")
	if got := m2.inputs[0].Value(); got != "jk" {
		t.Errorf("j/k on text input must type literally, got %q", got)
	}
}

func TestModalEmptyQuestionsRendersPlaceholder(t *testing.T) {
	m := New("rid-x", nil)
	v := m.View()
	if !strings.Contains(v, "no open questions") {
		t.Errorf("empty modal should explain no questions, got:\n%s", v)
	}
	if m.HasOpenQuestions() {
		t.Errorf("HasOpenQuestions must be false for empty modal")
	}
}
