---
sidebar_position: 13
---

# Reviewing Agent Diffs (`tuicr`, `lgtm`)

Two tools cover this loop: [`tuicr`](https://github.com/agavra/tuicr) for a GitHub-style pass with exported structured markdown after the agent finishes, and [`lgtm`](https://github.com/kunkka19xx/lgtm) for a live pane beside the agent that re-renders as it writes and sends `#id path:line` references into the agent's input box.

## Independent agent reviews

`k-review` runs two fresh reviewers against the same request, [acceptance snapshot](staying-on-goal.md#review-acceptance), and code scope. One focuses on completion claims; the other focuses on regressions and scope. Either can report any supported defect in the authorized scope or impact, including defects discovered in later rounds and regressions introduced by fixes.

Each reviewer assesses the source before reading the earlier findings and dispositions from a separate history file, then reconciles them before returning. The history preserves finding IDs, original triggers, and evidence for fixes or rejections. A prior verdict does not prove a fix; new evidence can reopen it.

Results include evidence and pass, fail, or unverified for each applicable criterion and claimed fix. Fix evidence addresses the original failure. A missing row or material verification gap does not establish completion. Findings identify the requirement, preserved invariant, or authorized impact they violate; unrelated new behavior remains a proposal.

Rounds remain unbounded. A clean fix-diff or narrowed review cannot end the loop: it returns to a review of the whole scope. The same discovery and scope rules apply in every round. These instructions and deterministic snapshot checks establish the review contract; they do not guarantee model adherence or prove behavior that requires a live check.

## tuicr

[`tuicr`](https://github.com/agavra/tuicr) is the user-facing half of the agent loop.

Flow:

1. The agent edits the working tree.
2. You review the diff in a GitHub-style TUI.
3. You drop line, file, or review comments.
4. `tuicr` exports structured markdown.
5. You paste that markdown back to the agent for a one-pass fix.

This is the inverse of the [`k-review` skill](skills.md), where the agent reviews your diff.

Use after an agent has made edits, when you want to give structured feedback back to it.

### Install

[`home/readonly_dot_Brewfile.tmpl`](../../../home/readonly_dot_Brewfile.tmpl) — `AI & LARGE LANGUAGE MODELS` section, homebrew-core formula `tuicr`.

### Config

Theme + comment-type vocabulary: [`home/dot_config/tuicr/readonly_config.toml`](../../../home/dot_config/tuicr/readonly_config.toml) → `~/.config/tuicr/config.toml`.

Comment types are actionable categories (`issue`, `suggestion`, `question`, `nit`, `praise`); severity (critical/high/medium/low in `k-review` findings) stays internal and is intentionally not encoded as a comment type.

### Loop

Invoke `tuicr` directly — no wrapper:

```bash
# 1. agent makes edits (claude / ,codex / opencode / pi)

# 2. review and export to clipboard, then paste into the next agent prompt:
tuicr
tuicr -r main..HEAD              # scope to a revision range (Git/JJ/Hg syntax)

# or one-shot: export straight to stdout for piping:
tuicr --stdout | claude --print
tuicr --stdout | ,codex exec
tuicr --stdout > /tmp/review.md
```

On export, tuicr copies markdown to the system clipboard (handling tmux/SSH OSC 52 propagation automatically). `.tuicrignore` (gitignore-style, repo-local) excludes generated files from the review surface; not managed by chezmoi.

## lgtm

[`lgtm`](https://github.com/kunkka19xx/lgtm) reviews the diff while the agent is still writing it, in a tmux pane next to the agent.

### Install

[`home/readonly_dot_Brewfile.tmpl`](../../../home/readonly_dot_Brewfile.tmpl) — same `AI & LARGE LANGUAGE MODELS` section as `tuicr`, via the `kunkka19xx/tap` Homebrew tap.

### Config

[`home/dot_config/lgtm/readonly_config.toml`](../../../home/dot_config/lgtm/readonly_config.toml) → `~/.config/lgtm/config.toml`.

It sets the `catppuccin` theme (matching tuicr), nerd-font icons, inline comment rendering, lockfile ignores for tracked generated files, and the compose-box question presets. Everything else stays compiled-in default.

A repo-local `.lgtm/config.toml` overrides the home config key by key, so a single repo can change the theme or ignore list without touching the managed file.

### Loop

```bash
# split a tmux pane beside the agent and run it there
lgtm                              # HEAD vs working tree, live
lgtm --base main                  # whole branch incl. uncommitted, live
lgtm --base main --target HEAD    # committed work only, static
```

Keys:

- `<CR>` — compose a reference for this line
- `V` / `v` — select lines / words
- `<Space>c` — comment
- `<C-s>` — submit all comments as `.lgtm/review-N.md` and mark read
- `]m` — walk changes since the mark
- `]w` — walk weakened tests
- `]t` — walk snapshot turns
- `R` — restore a file from a turn
- `<Space>t` — pick the target pane

State: `.lgtm/` holds comments, reviews, and read state and gitignores itself; snapshots live under `refs/lgtm/**`, invisible to `git branch`/`git status` but visible to `git log --all`. Neither is managed by chezmoi.

Pane targeting: with exactly two panes `lgtm` infers the agent's pane and types into it with tmux `send-keys`. Otherwise it opens a pane picker, or take `--pane %N`.

## Related

- [`k-review` skill](skills.md) — the inverse loop (the agent reviewing your diff)
- [AI assistants](index.md) — shared instructions and configuration
