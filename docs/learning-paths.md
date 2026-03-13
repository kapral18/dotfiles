# Learning Paths

Back: [`docs/index.md`](index.md)

This setup is an all-or-nothing installation. When you run `chezmoi apply`, it
installs the entire ecosystem. However, you do **not** need to learn or use all
of it on day one.

If you are coming from VSCode/JetBrains, jumping straight into "tmux + fish +
nvim" can be overwhelming. Here is a recommended path for incrementally learning
the workflow while still getting your job done.

## Phase 1: Git + Identity (Low Friction)

Keep using your current IDE and terminal. Just let the new git defaults work for
you.

What you get immediately:

- Git identity switching (work vs personal)
- 1Password-backed SSH agent setup
- Opinionated git defaults (rerere, autosquash, delta, etc.)

Where to read:

- [`docs/categories/git-and-identity.md`](categories/git-and-identity.md)

## Phase 2: Fish Shell (Medium Friction)

Start using Fish as your default shell inside your IDE's integrated terminal.

What to focus on:

- Fish shell + fzf ergonomics (Ctrl+R for history, etc.)
- Getting used to the prompt and aliases

Where to read:

- [`docs/categories/shell-fish.md`](categories/shell-fish.md)

## Phase 3: Tmux + Custom CLI Tools (High Friction)

Move out of the IDE's integrated terminal and into a dedicated terminal app
(like Ghostty, Alacritty, or iTerm) running `tmux`.

What to focus on:

- tmux sessions + keybindings
- Isolate work with git worktrees (`,w` commands)
- custom CLI tools under `~/bin`

Where to read:

- [`docs/categories/terminals/index.md`](categories/terminals/index.md)
- [`docs/categories/tmux/index.md`](categories/tmux/index.md)
- [`docs/categories/custom-commands.md`](categories/custom-commands.md)

## Phase 4: Neovim Editor Workflow (Optional)

Once you are comfortable living in `tmux`, you can try swapping your IDE for
Neovim. This is entirely optional.

What to focus on:

- Neovim configuration managed like code
- Curated plugins + custom local plugins

Where to read:

- [`docs/categories/editor-neovim.md`](categories/editor-neovim.md)

## Phase 5: The Agentic Operating System (AI)

Once the terminal feels like home, you can begin leveraging the AI integrations
that turn this environment into an Agentic OS.

What to focus on:

- Learning to invoke Terminal Assistants (Pi, Gemini CLI, OpenCode).
- Understanding how SOPs dictate agent behavior.
- Utilizing MCP tools (like Semantic Code Search) to give agents context.

Where to read:

- [`docs/categories/ai-and-assistants.md`](categories/ai-and-assistants.md)
