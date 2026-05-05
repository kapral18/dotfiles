package kb

import (
	"errors"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"ralph-tui/internal/cmds"
)

func TestModalSubmitsNonEmptyQueryOnEnter(t *testing.T) {
	m := New()
	m.SetWidth(80)
	// Type "manifest" character-by-character then press Enter.
	for _, r := range "manifest" {
		_, query, cancelled := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		if cancelled || query != "" {
			t.Fatalf("typing should not submit/cancel: cancelled=%v query=%q", cancelled, query)
		}
	}
	_, query, cancelled := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	if cancelled {
		t.Fatalf("enter must not cancel")
	}
	if query != "manifest" {
		t.Fatalf("expected query 'manifest', got %q", query)
	}
}

func TestModalEmptyQueryDoesNotSubmit(t *testing.T) {
	m := New()
	m.SetWidth(80)
	_, query, cancelled := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	if cancelled {
		t.Fatalf("empty enter must not cancel modal")
	}
	if query != "" {
		t.Fatalf("empty input must not submit; got %q", query)
	}
}

func TestModalEscClosesModal(t *testing.T) {
	m := New()
	_, _, cancelled := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	if !cancelled {
		t.Fatal("esc must cancel the modal")
	}
}

func TestModalQClosesOnlyWhenInputEmpty(t *testing.T) {
	m := New()
	// Empty input → q closes.
	_, _, cancelled := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'q'}})
	if !cancelled {
		t.Fatal("q on empty input should close modal")
	}

	// Once we have content, q must NOT close — it's a literal char in
	// the query (the user might want to search for "qsbr" or similar).
	m2 := New()
	for _, r := range "abc" {
		_, _, _ = m2.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
	}
	_, _, cancelled = m2.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'q'}})
	if cancelled {
		t.Fatal("q with non-empty input must NOT close — it's part of the query")
	}
}

func TestModalRendersHitsAfterSetHits(t *testing.T) {
	m := New()
	m.SetWidth(120)
	m.MarkLoading("manifest")
	view := m.View()
	if !strings.Contains(view, "searching for \"manifest\"") {
		t.Fatalf("loading view should mention current query; got:\n%s", view)
	}

	m.SetHits(cmds.KBSearchMsg{
		Query: "manifest",
		Hits: []cmds.KBHit{
			{
				ID:    "id-1",
				Title: "Manifest layout",
				Body:  "Ralph manifests live under runs/<rid>/manifest.json.",
				Kind:  "fact",
				Scope: "project",
			},
		},
	})
	view = m.View()
	if !strings.Contains(view, "Manifest layout") {
		t.Fatalf("hit list should include the title; got:\n%s", view)
	}
	if !strings.Contains(view, "Ralph manifests live under") {
		t.Fatalf("detail pane should include the body; got:\n%s", view)
	}
}

func TestModalRendersErrorWhenSearchFails(t *testing.T) {
	m := New()
	m.SetWidth(80)
	m.MarkLoading("badq")
	m.SetHits(cmds.KBSearchMsg{Query: "badq", Err: errors.New("ai-kb missing")})
	view := m.View()
	if !strings.Contains(view, "ai-kb missing") {
		t.Fatalf("error view must show the underlying error; got:\n%s", view)
	}
}

func TestModalEmptyHitsRendersNoHitMessage(t *testing.T) {
	m := New()
	m.SetWidth(80)
	m.MarkLoading("nothing-here")
	m.SetHits(cmds.KBSearchMsg{Query: "nothing-here", Hits: nil})
	view := m.View()
	if !strings.Contains(view, "no hits") {
		t.Fatalf("empty hit set must surface 'no hits'; got:\n%s", view)
	}
}

func TestModalCursorMovesWithUpDown(t *testing.T) {
	m := New()
	m.SetWidth(120)
	m.SetHits(cmds.KBSearchMsg{
		Query: "x",
		Hits: []cmds.KBHit{
			{ID: "1", Title: "first", Body: "b1", Kind: "fact", Scope: "project"},
			{ID: "2", Title: "second", Body: "b2", Kind: "fact", Scope: "project"},
			{ID: "3", Title: "third", Body: "b3", Kind: "fact", Scope: "project"},
		},
	})
	if m.cursor != 0 {
		t.Fatalf("cursor must start at 0, got %d", m.cursor)
	}
	_, _, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	if m.cursor != 1 {
		t.Fatalf("down should move cursor to 1, got %d", m.cursor)
	}
	_, _, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	_, _, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	if m.cursor != 2 {
		t.Fatalf("cursor must clamp at last hit, got %d", m.cursor)
	}
	_, _, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	if m.cursor != 1 {
		t.Fatalf("up should decrement cursor, got %d", m.cursor)
	}
}
