---
sidebar_position: 3
title: Claude Code
---

# Claude Code

| Tool        | Source                                                                       | Target                                 | MCP servers                             |
| ----------- | ---------------------------------------------------------------------------- | -------------------------------------- | --------------------------------------- |
| Claude Code | [`home/dot_claude/settings.json`](../../../../home/dot_claude/settings.json) | `~/.claude/settings.json` (whole file) | `~/.claude.json` top-level `mcpServers` |

## Claude Code settings

| Area             | Value                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------ |
| Model            | `claude-opus-5-5`, `effortLevel: high` (also pinned in `modelSettings`)                    |
| Advisor          | `advisorModel: claude-opus-5-5` (server-side advisor tool)                                 |
| Thinking         | `alwaysThinkingEnabled: false`                                                             |
| Permissions      | `defaultMode: bypassPermissions`; dangerous-mode prompt skipped                            |
| Subagent nesting | `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`                                               |
| Auto-compact     | `autoCompactWindow: 400000`: compaction near 366k instead of near 1M                       |
| Auto-memory      | `autoMemoryEnabled: false`; `,ai-kb` is the only durable memory                            |
| Away recap       | `awaySummaryEnabled: false`                                                                |
| Subagent cache   | `subagentPromptCacheTtl: "1h"`: prompt cache for subagents and helpers, not the 5m default |
| Hooks            | none in settings; the mods below load through `env.CLAUDE_CODE_PLUGIN_DIRS` (below)        |
| Auth             | native Claude account auth; no `apiKeyHelper` or `ANTHROPIC_BASE_URL` override             |

Instructions come from `~/.claude/CLAUDE.md` (symlink to `~/AGENTS.md`); skills from `~/.claude/skills` → `~/.agents/skills`.
The only custom agent is `exact_agents/k-agent-reviewer.md.tmpl` (see [Subagents](../subagents.md)); search uses the built-in `Explore`.
Fullscreen mode and push notifications are on.
`settings.llama-cpp*.json.tmpl` hold the settings `,claude-llama-cpp` passes for local models: model-scoped `high` effort, thinking off.

### Mods

Claude Code mods are TypeScript function-hook plugins (early-access API).
Sources live in [`home/dot_claude/exact_mods/`](../../../../home/dot_claude/exact_mods/) and deploy to `~/.claude/mods/`.
`settings.json` loads them all with `env.CLAUDE_CODE_PLUGIN_DIRS`. Pi, OMP, and the other harnesses do not run them.

| Mod                  | Event                                                         | Behavior                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| -------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `behavior-map-guard` | `tool.call` on Edit, Write, NotebookEdit, Bash; `session.end` | Runs `,behavior-map affected <path>`. Refuses the first edit per session in an unmapped directory; adds a context note for touched entries. After a Bash command that may write, adds the same notes as context for the files it changed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `checked-gate`       | `tool.call` (every tool); `turn.start`; `classic.Stop`        | Sends the turn back once when: files changed (edits, or Bash changed the git working tree) and the final message has no `Checked:` list (a `Checked` line counts, bold or not, with or without a colon or a parenthetical; a sentence that starts with "Checked" does not); or a turn that used a tool lists work under a heading the report has no list for (`Known gaps:`, `Next steps:`, `Unverified:`, …); or a turn that used a tool ends with a question whose last prose paragraph (before any list or code block) does not start with `Decision needed:` and that is not an item under `Open:` or `Proposed:`. Each message names what it found and the `~/AGENTS.md` rule to apply; the rule text lives only in `~/AGENTS.md`. |
| `sop-guard`          | `tool.call` on Bash, Edit, Write, NotebookEdit                | Refuses the hard-rule breaks listed below.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `stop-review`        | `classic.Stop`                                                | When a turn that used tools ends, sends `advisorModel` (`claude-opus-5-5`) the transcript (earlier turns as context, then the turn's request, messages, and tool calls with cut inputs and results, and its final answer) and `~/AGENTS.md`. Sends the turn back once with up to 3 concerns; `PASS` adds nothing. Its prompt holds no rules of its own: it explains the record, asks for every break of `~/AGENTS.md` the agent can fix now (the 3 most severe if more; no preferences), and names the sections to check first (§2, §1, §3 steps 3 and 8, §5). With `~/AGENTS.md` unreadable it skips the review and logs why.                                                                                                          |

`sop-guard` rules:

| Rule                                                                                                                                                                                                                               | Source           | Refusal                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------- |
| Edit of a chezmoi-managed target (symlinks resolved)                                                                                                                                                                               | `~/AGENTS.md` §6 | always; names the source path                                                               |
| A command that prints a secret: `pass show`, `security … -w`, `op read`, `gh auth token`, `cat .env` (quoted text, heredoc bodies, and `#` comments are not commands; a `#` inside `${…}` or after `(` in `[[ … ]]` is no comment) | `~/AGENTS.md` §5 | always, unless `$(...)`, a redirect, or a pipe into a non-printing command takes the output |
| Bare `tmux kill-server`                                                                                                                                                                                                            | `k-tmux`         | always, unless `-S` or `-L`                                                                 |
| A default-server tmux change (`send-keys`, `source-file`, `attach`, …)                                                                                                                                                             | `k-tmux`         | once per subcommand per session                                                             |

This repo also has a project plugin, [`.claude/skills/dotfiles-guard/`](../../../../.claude/skills/dotfiles-guard/), which loads only in sessions started in this repo.
It refuses `make check-full`, `make test`, `bin/check --full` (repo `AGENTS.md`), `scripts/test_runner.py`, and `scripts/check.py --full` (user request).
A command inside a quoted string, such as `bash -c "make test"`, is not seen.
It keeps a copy of `sop-guard`'s `shell.ts`, because a plugin cannot import outside its folder; `test_claude_mods.py` fails when the copies differ.

A "once" refusal passes on retry: the model retries only when the condition in the refusal message holds.

All of them fail open: a failed hook or a missing command lets the call through.
`behavior-map-guard` never refuses a docs-only, test-only, `/tmp`, or non-git edit.
A Bash command cannot be refused before it runs, because its paths are unknown.
For a main-agent command that may write (a redirect, `sed -i`/`--in-place`, `perl -i`, a scripting runtime, a file command, or `git apply`/`checkout`/`restore`/`stash`/`mv`), the guard creates a marker file for that call just before it runs, so parallel calls do not share one; the marker is removed after the scan.
After it runs, the guard reads `git status -z` of the session's repo (a rename by its new path) and keeps the files whose change time is newer than the marker, so `mv` and `cp -p` count.
It asks for area init when one of them is a code file in an unmapped directory, once per directory, and notes touched entries. The note does not use up the Edit refusal for that directory.
It sees only the session's repo, skips subagent commands and deletions, leaves out commands that move HEAD (merge, pull, rebase, switch, cherry-pick, am, reset: code the agent did not write; a branch-switching `git checkout` leaves the files it switched clean, and carried changes keep their change time), and misses a write by a command that matches none of those patterns.
`checked-gate` snapshots only the git repo of the session's working directory, so Bash changes in another repo are not seen.
A turn whose only change is `git commit`, `stash`, or `reset` also changes the snapshot, so a commit-only reply is sent back once.
Each check (missing `Checked:`, parked work, ending question) sends a turn back at most once per Stop chain (a continuation has `stop_hook_active` set), so a Stop chain is sent back at most three times. A pause starts a new chain.
Each send-back from `checked-gate` or `stop-review` ends by telling the model that its reply replaces its last answer and to follow the `~/AGENTS.md` §8 send-back rule.
The question check stays quiet when the user's prompt asks to be asked ("ask me", "asking us"), unless a negation ("not", "never", …) comes up to three words before it ("don't even need to ask me"), or "stop", "quit", or "avoid" up to two words before it, not across "and", "then", or "to". "Don't hesitate to ask me" and a negation in a condition ("if not sure, ask me") stay invitations.
Markdown blockquotes and fenced code are excluded from the question and parked-work checks, so quoted drafts do not trigger them.
The parked-work check matches only a heading line (plain, `#`, or bold; not a bullet) named `Known gaps`, `Not done`, `Not yet done`, `Still/Left to do`, `Remaining work/steps/items`, `Next step(s)` or `Follow-up(s)` (either may start with `Suggested`, `Recommended`, or `Possible`), `TODO(s)`, `Unverified`, `Not verified`, or `Deferred`; the one-word labels `Next:`, `Remaining:`, and `Pending:` count only alone on their line. A heading whose whole list is "none", "n/a", or "nothing" (no other item or line after it) passes. It stays quiet when the user's prompt asks for such a list: "list", "show (me)", "give me", or "tell me" at the start of a sentence or after "please", "and", "then", "also", "just", "can you", or "could you", up to 30 characters before "next steps", "gaps", "remaining", "left", "todo", or "follow-ups"; "what's/what is/what are" before "next", "left", "remaining", or "missing"; "what remains"; "handoff"/"hand off"; or a prompt that names the heading itself, in quotes (`a "Known gaps:" list`) or before "list", "section", "heading", or "block" (`a Next steps section`).
`checked-gate` reads the `Decision needed:` label by form only; whether the item has a pick and is the user's to decide is judged by `stop-review` (and OMP's `Gate`), so it is checked only where an advisor model is set.
A continuation after a send-back keeps the turn's state, so each check stays once per turn.
A Stop with a subagent or workflow still in `background_tasks` pauses the turn: `checked-gate` and `stop-review` send nothing back.
The `turn.start` that the task notice raises (in `claude -p` its text starts with `<task-notification>`; an empty text also counts) then continues the same turn, so the answer that ends it is checked against the user's request; a typed prompt starts a new turn.
A background shell task alone does not pause it, because a server never ends.
`stop-review` is the Claude counterpart of OMP's `Gate` advisor: Claude's own advisor runs only when the model calls it.
It reviews once per turn and skips a draft another gate sends back. It is listed first in `CLAUDE_CODE_PLUGIN_DIRS`, so its Stop hook runs outermost and sees those blocks.
The turn opens at the `turn.start` prompt; for a turn a task notice started (no typed prompt), at the notice before its first `tool.call` id; else at that call, so a skill body or an idle task notice is not read as the request.
The record holds about 360,000 characters plus the request and the final answer: the turn under review takes up to 180,000 first, and earlier messages and calls fill the rest, each message cut to 4,000. Past that, the oldest earlier parts drop in 90,000-character steps, so the record's start stays the same between steps and a review reads it from the cache. Each step can cost up to 90,000 characters of the oldest context, and a turn of 90,000 characters or more moves the step, so that review misses the cache.
Each earlier user message opens a prompt-cache block; the mark on the last one lets a review within five minutes, the cache's lifetime, read that prefix from the cache.
The reviewer sees only that record, not the files, so the block asks the model to reject a wrong concern with a reason.
After a hot reload it waits for a new turn; a send-back's continuation does not count.
It adds one model call per tool-using turn, stays off while `advisorModel` is unset, and logs a failed review.
`sop-guard` reads `$(...)` inside double quotes as data: `echo "$(pass show x)"` passes.
Its chezmoi rule sees only managed files: a new file written into an `exact_` target directory passes, and the next `chezmoi apply` deletes it.
Test a mod with `claude plugin test ~/.claude/mods/<mod>`; `claude plugin validate` checks what it hooks.
The engine writes `.claude-plugin/types/` and `tsconfig.json` into each mod folder, so the mod folders are not `exact_`.

### LetsFG

**LetsFG** is intentionally not exposed through the shared MCP registry.

| Decision               | Reason                                                                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| not in MCP registry    | flight tools are irrelevant to most sessions                                                                                                |
| skill-loaded on demand | agents load [`k-letsfg/SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-letsfg/readonly_SKILL.md) only for travel searches |
| local CLI              | `letsfg` uv tool comes from [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl)                |
| normal agent mode      | passes `LETSFG_BROWSERS=0` per invocation                                                                                                   |
| browser connectors     | explicit opt-in                                                                                                                             |

Playwriter remains a fallback for rendered UI checks or booking-adjacent flows that need explicit user confirmation.
