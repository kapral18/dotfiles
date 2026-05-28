---
sidebar_position: 4
---

# A Day In The Life

This page is for people coming from a traditional IDE workflow who want to see what "terminal-driven" can look like without becoming a full-time shell person. It walks one day end-to-end and links to the deeper docs for each tool.

## Morning: Restore Context

If you use tmux with session restore, you can pick up where you left off.

- tmux config: [`home/dot_config/exact_tmux/readonly_tmux.conf`](../../home/dot_config/exact_tmux/readonly_tmux.conf)

The session picker (`prefix` + `T`) lists your tmux sessions, git worktrees, and recent directories with dirty/PR/CI badges, so jumping back into yesterday's work is one popup away. See [Session picker](../topics/workflow/tmux/session-picker.md).

## Start Work: Isolate With Worktrees

Instead of mixing multiple branches in one checkout, this setup uses git worktrees. We provide a custom comma command (`,w`) to make this ergonomic:

```bash
,w add feat/my-change main
```

This creates a separate working directory for the branch and can automatically attach a tmux session to it. See [Worktrees](../topics/workflow/git-identity/worktrees.md).

## Triage: Work The GitHub Queue

Open the GitHub picker (`prefix` + `G`) for a PR/issue dashboard with review/CI badges, scopes (`Focus` vs `Explore`), and inline actions. From a row you can:

- `enter` — check out a worktree for the PR/issue and focus its session
- `alt-x` — run GitHub mutations (approve, request-changes, merge, label, comment) without leaving the picker
- `alt-A` — hand the PR/issue off to Ralph (see below)

See [GitHub picker](../topics/workflow/tmux/github-picker.md).

## Agentic Tasks: Offload Work To Assistants

Assistants are governed by a version-controlled SOP + skills layer, so behavior is consistent across tools and respects each repo's rules. See [The Agentic Operating System](../topics/ai-assistants/index.md).

The CLI assistants, in the order this setup leans on them:

1. **Cursor CLI** (`cursor-agent`, aliased `agent`) — the primary interactive harness.
2. **Codex** (`codex`)
3. **Pi** (`pi`)
4. **Claude Code** (`claude`)

```bash
agent      # Cursor CLI (primary)
codex
pi
claude
```

Per-tool configuration (auth, models, MCP, profile merging) lives in [Tool configs](../topics/ai-assistants/tool-configs.md).

When you run `claude`, `cursor-agent`, or `pi` inside tmux, `Alt-Enter` prepends a calibrated verification scaffold to your prompt before submitting (toggle with `prefix` + `W`); plain `Enter` is never touched.

For larger, multi-step work, hand off to **Ralph** — a planner → executor → reviewer → re-reviewer loop with self-healing:

```bash
,ralph go
```

`alt-A` in the GitHub picker seeds a `,ralph go` goal with the selected PR/issue context. See [Ralph orchestrator](../topics/ai-assistants/ralph.md).

Across sessions, agents carry context through two memory layers: short-lived per-workspace hook memory (`/tmp/specs`) and a durable knowledge base (`,ai-kb`). See [Agent memory](../topics/ai-assistants/knowledge-base.md).

## Review: Check Out PRs And Read Agent Diffs

Check out a pull request as a local worktree:

```bash
,w prs 12345
```

To review the changes an agent produced before committing, use the `tuicr` diff loop, which feeds structured feedback back to the agent. See [Reviewing agent diffs](../topics/ai-assistants/reviewing-diffs.md).

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
