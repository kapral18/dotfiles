// Command ralph-tui is the Bubble Tea dashboard for the Ralph orchestrator.
//
// Usage:
//
//	ralph-tui [--workspace PATH]
//
// The TUI reads run state from $RALPH_STATE_HOME (or $XDG_STATE_HOME/ralph)
// and dispatches mutations through `,ralph` subprocesses. It is intended to
// run inside a tmux popup (the chezmoi-managed binding `prefix+A`) but works
// standalone too.
package main

import (
	"flag"
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"ralph-tui/internal/app"
)

func main() {
	workspace := flag.String("workspace", os.Getenv("PWD"), "default workspace for new runs")
	flag.Parse()

	m, err := app.New(*workspace)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ralph-tui: %v\n", err)
		os.Exit(1)
	}
	defer m.Close()

	prog := tea.NewProgram(m, tea.WithAltScreen(), tea.WithMouseCellMotion())
	if _, err := prog.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "ralph-tui: %v\n", err)
		os.Exit(1)
	}

	if target := m.PendingAttach(); target != "" {
		if err := app.AttachExternal(target); err != nil {
			fmt.Fprintf(os.Stderr, "ralph-tui: attach %s: %v\n", target, err)
			os.Exit(2)
		}
	}
}
