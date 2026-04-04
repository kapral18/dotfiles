# A Day In The Life

Back: [`docs/index.md`](index.md)

This page is for people coming from a traditional IDE workflow who want to see what "terminal-driven" can look like without becoming a full-time shell person.

## Morning: Restore Context

If you use tmux with session restore, you can pick up where you left off.

- tmux config: [`home/dot_config/exact_tmux/readonly_tmux.conf`](../home/dot_config/exact_tmux/readonly_tmux.conf)

## Start Work: Isolate With Worktrees

Instead of mixing multiple branches in one checkout, this setup uses git worktrees. We provide a custom comma command (`,w`) to make this ergonomic:

```bash
,w add feat/my-change main
```

This creates a separate working directory for the branch and can automatically attach a tmux session to it.

## Review: Check Out PRs Like They Are Local Branches

You can also use the `,w` command to easily check out pull requests:

```bash
,w prs 12345
```

## Agentic Tasks: Offload Work to Assistants

Invoke your CLI assistants (Gemini, Pi, OpenCode) to read context, debug failures, or execute refactors. They will automatically respect the repository's rules thanks to the Agentic OS governance layer and use MCP servers to query codebase context if needed.

## Code: Keep Your Editor

You can run this workflow from VSCode/JetBrains using the integrated terminal. Neovim is available if you want it, but it is optional.

## End Of Day: Clean Up

```bash
,w remove
```

## Maintenance

Update dotfiles:

```bash
chezmoi update
```

Update packages, then reconverge:

```bash
brew update
brew upgrade
chezmoi apply
```
