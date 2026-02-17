# Adoption Paths

Back: [`docs/index.md`](index.md)

Not everyone wants to jump from VSCode/JetBrains into "tmux + fish + nvim" in one
week. This setup is designed so you can adopt slices incrementally.

## Path 1: Identity + Git Hygiene (Low Disruption)

What you get:

- Git identity switching (work vs personal)
- 1Password-backed SSH agent setup
- Opinionated git defaults (rerere, autosquash, delta, etc.)

Where to read:

- [`docs/categories/git-and-identity.md`](categories/git-and-identity.md)

## Path 2: Declarative Packages (Medium Disruption)

What you get:

- Brewfile-based tool installation
- ASDF tool version pinning
- Global language tools (cargo/go/gems/npm/uv)

Where to read:

- [`docs/categories/packages.md`](categories/packages.md)

## Path 3: Terminal Workflow (High Disruption)

What you get:

- Fish shell + fzf ergonomics
- tmux sessions + keybindings
- custom CLI tools under `~/bin`

Where to read:

- [`docs/categories/shell-fish.md`](categories/shell-fish.md)
- [`docs/categories/terminals-and-tmux.md`](categories/terminals-and-tmux.md)
- [`docs/categories/custom-commands.md`](categories/custom-commands.md)

## Path 4: Neovim Editor Workflow (Optional)

What you get:

- Neovim configuration managed like code
- curated plugins + custom local plugins

Where to read:

- [`docs/categories/editor-neovim.md`](categories/editor-neovim.md)
