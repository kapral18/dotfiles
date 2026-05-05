package app

import "github.com/charmbracelet/bubbles/key"

// Global keybindings (active when no modal is up).
var (
	KeyQuit         = key.NewBinding(key.WithKeys("q", "ctrl+c"))
	KeyHelp         = key.NewBinding(key.WithKeys("?"))
	KeyRefresh      = key.NewBinding(key.WithKeys("r"))
	KeyTab          = key.NewBinding(key.WithKeys("tab"))
	KeyShiftTab     = key.NewBinding(key.WithKeys("shift+tab"))
	KeyZoom         = key.NewBinding(key.WithKeys("enter"))
	KeyNew          = key.NewBinding(key.WithKeys("n"))
	KeyAttach       = key.NewBinding(key.WithKeys("a"))
	KeyAnswer       = key.NewBinding(key.WithKeys("A"))
	KeyVerify       = key.NewBinding(key.WithKeys("v"))
	KeyControl      = key.NewBinding(key.WithKeys("c"))
	KeyKill         = key.NewBinding(key.WithKeys("x"))
	KeyRm           = key.NewBinding(key.WithKeys("X"))
	KeyResumeRunner = key.NewBinding(key.WithKeys("R"))
	KeyReplan       = key.NewBinding(key.WithKeys("P"))
	KeySort         = key.NewBinding(key.WithKeys("s"))
	KeyActivity     = key.NewBinding(key.WithKeys("S"))
	KeyPreview      = key.NewBinding(key.WithKeys("p"))
	KeyKB           = key.NewBinding(key.WithKeys("K"))

	// Layout switchers. Pressing the same key while already in that layout
	// drops back to the default detail view, so it doubles as a toggle.
	KeyLayoutDetail = key.NewBinding(key.WithKeys("1"))
	KeyLayoutGrid   = key.NewBinding(key.WithKeys("2"))
	KeyLayoutZoom   = key.NewBinding(key.WithKeys("3"))

	KeyUp   = key.NewBinding(key.WithKeys("up", "k"))
	KeyDown = key.NewBinding(key.WithKeys("down", "j"))

	// Grid-layout cell navigation. Distinct bindings (rather than reusing
	// KeyUp/KeyDown) so we can intercept them in the parent only when the
	// grid layout is active, leaving the runs/roles list scrollers alone
	// in the default detail layout.
	KeyGridUp    = key.NewBinding(key.WithKeys("up", "k"))
	KeyGridDown  = key.NewBinding(key.WithKeys("down", "j"))
	KeyGridLeft  = key.NewBinding(key.WithKeys("left", "h"))
	KeyGridRight = key.NewBinding(key.WithKeys("right", "l"))
)
