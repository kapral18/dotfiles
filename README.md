# kapral18/dotfiles

Personal macOS dotfiles managed with Chezmoi: Fish, tmux, Neovim, CLI assistants, and package installation.

Read the [documentation](https://kapral18.github.io/dotfiles/) for setup, command references, and configuration recipes (source: [`docs/`](docs/intro/index.md)).

## Included

| Feature         | Description                                           |
| --------------- | ----------------------------------------------------- |
| Agent memory    | `,ai-kb` knowledge base and `,handoff` session notes  |
| Local inference | llama.cpp router and model sync (`,llama-cpp`)        |
| Git identity    | 1Password SSH agent and SSH commit signing            |
| Git worktrees   | Worktree management with PR integration               |
| Neovim          | LSP, commit-message assistance, and refactoring tools |
| Fish            | Comma-prefixed commands in `~/bin`                    |
| Packages        | Homebrew lists by category and mise-managed runtimes  |

## Setup

### Prerequisites

Use macOS with **1Password** installed and signed in for SSH keys and secrets.
Applying this setup installs packages, changes shell and macOS settings, and can remove Homebrew packages absent from its Brewfile. Review [Getting Started](docs/intro/getting-started.md) and [New machine bootstrap](docs/intro/new-machine-bootstrap.md) before applying it to an existing machine.

### Bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
```

If Chezmoi is already installed, preview with `chezmoi init kapral18 && chezmoi diff` before running `chezmoi apply`.

## Source and deployment

Chezmoi renders templates from [`home/`](home/) into `$HOME`. Hooks in [`home/.chezmoiscripts/`](home/.chezmoiscripts/) install and reconcile packages when lists change.

For the full layout (naming conventions, hook lifecycle, AI config merging, externals), see [Architecture](docs/intro/architecture.md).

## Configuration reference

| Area                                    | Doc                                                         | Source-of-truth (edit here)                                                                              |
| --------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Packages (Homebrew, mise, cargo, go, …) | [Packages](docs/topics/core/packages/index.md)              | [`home/.chezmoitemplates/brews/`](home/.chezmoitemplates/brews/), [`home/readonly_dot_default-*`](home/) |
| Custom `~/bin` commands                 | [Custom commands](docs/topics/workflow/custom-commands/)    | [`home/exact_bin/`](home/exact_bin/), [`home/exact_lib/`](home/exact_lib/)                               |
| Git identity & worktrees                | [Worktrees](docs/topics/workflow/git-identity/worktrees.md) | [`home/exact_bin/executable_,w`](home/exact_bin/executable_,w)                                           |
| GitHub picker & tmux                    | [Tmux](docs/topics/workflow/tmux/index.md)                  | [`home/dot_config/exact_tmux/`](home/dot_config/exact_tmux/)                                             |
| Fish shell                              | [Shell: Fish](docs/topics/workflow/shell-fish.md)           | [`home/dot_config/fish/`](home/dot_config/fish/)                                                         |
| Neovim                                  | [Neovim](docs/topics/editor/neovim/index.md)                | [`home/dot_config/exact_nvim/`](home/dot_config/exact_nvim/)                                             |
| macOS automation                        | [macOS](docs/topics/macos/index.md)                         | [`home/dot_hammerspoon/`](home/dot_hammerspoon/), [`home/.osx.core`](home/.osx.core)                     |
| Reference map (where to change X)       | [Reference map](docs/reference/reference-map.md)            | —                                                                                                        |

## Daily use

1. Tmux sessions auto-restore (`tmux-resurrect` / `continuum`).
2. `,w add …` or the GitHub picker (`prefix + G`) for branch/PR worktrees.
3. Neovim for editing; `,update` to update tools or `chezmoi apply` to apply the declared configuration and package lists.

See [A day in the life](docs/intro/day-in-the-life.md) for a fuller walkthrough.

## Further Reading

- Docs hub: [`docs/intro/index.md`](docs/intro/index.md)
- Contributing (repo development): [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Agent instructions: [`AGENTS.md`](AGENTS.md)
- Chezmoi data prompts: [`home/.chezmoi.toml.tmpl`](home/.chezmoi.toml.tmpl)
- License: [MIT](LICENSE)
