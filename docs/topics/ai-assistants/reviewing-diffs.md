---
sidebar_position: 9
---

# Reviewing Agent Diffs (`tuicr`)

[`tuicr`](https://github.com/agavra/tuicr) is the user-facing half of the agent loop: after the agent edits the working tree, you review the diff in a GitHub-style TUI, drop line/file/review comments, and export them as structured markdown that pastes back to the agent for a one-pass fix. It is the inverse of the [review workflow](reviews.md) (which is the agent reviewing your diff).

Use after an agent has made edits, when you want to give structured feedback back to it.

## Install

[`home/readonly_dot_Brewfile.tmpl`](../../../home/readonly_dot_Brewfile.tmpl) — `AI & LARGE LANGUAGE MODELS` section, via the `agavra/tap` Homebrew tap.

## Config

Theme + comment-type vocabulary: [`home/dot_config/tuicr/readonly_config.toml`](../../../home/dot_config/tuicr/readonly_config.toml) → `~/.config/tuicr/config.toml`.

Comment types are actionable categories (`issue`, `suggestion`, `question`, `nit`, `praise`); severity (CRITICAL/HIGH/MEDIUM/LOW from the review SOP) stays internal and is intentionally not encoded as a comment type.

## Loop

Invoke `tuicr` directly — no wrapper:

```bash
# 1. agent makes edits (claude / codex / opencode / cursor-agent / pi / agent)

# 2. review and export to clipboard, then paste into the next agent prompt:
tuicr
tuicr -r main..HEAD              # scope to a revision range (Git/JJ/Hg syntax)

# or one-shot: export straight to stdout for piping:
tuicr --stdout | claude --print
tuicr --stdout | codex exec
tuicr --stdout | cursor-agent
tuicr --stdout > /tmp/review.md
```

On export, tuicr copies markdown to the system clipboard (handling tmux/SSH OSC 52 propagation automatically). `.tuicrignore` (gitignore-style, repo-local) excludes generated files from the review surface; not managed by chezmoi.

## Related

- [Review workflow](reviews.md) — the inverse loop (the agent reviewing your diff)
- [The Agentic Operating System](index.md) — governance layer
