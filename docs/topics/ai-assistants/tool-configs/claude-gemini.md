---
sidebar_position: 3
title: Claude and Antigravity
---

# Claude and Antigravity

| Tool        | Source                                                                          | Target                                                                        | MCP servers                             |
| ----------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------- |
| Claude Code | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/) | `~/.claude/settings.json` (whole file)                                        | `~/.claude.json` top-level `mcpServers` |
| Antigravity | [`home/dot_gemini/`](../../../../home/dot_gemini/)                              | `~/.gemini/config/` + policy-merged `~/.gemini/antigravity-cli/settings.json` | `~/.gemini/config/mcp_config.json`      |

## Claude Code settings

| Area             | Value                                                                               |
| ---------------- | ----------------------------------------------------------------------------------- |
| Model            | `claude-sonnet-5-5`, `effortLevel: high` (also pinned in `modelSettings`)           |
| Thinking         | `alwaysThinkingEnabled: false`                                                      |
| Permissions      | `defaultMode: bypassPermissions`; dangerous-mode prompt skipped                     |
| Subagent nesting | `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`                                        |
| Auto-compact     | `autoCompactWindow: 400000`: compaction near 366k instead of near 1M                |
| Auto-memory      | `autoMemoryEnabled: false`; `,ai-kb` is the only durable memory                     |
| Away recap       | `awaySummaryEnabled: false`                                                         |
| Hooks            | none in settings; the mods below load through `env.CLAUDE_CODE_PLUGIN_DIRS` (below) |
| Work auth        | native Claude enterprise auth; no `apiKeyHelper` or `ANTHROPIC_BASE_URL` override   |

Instructions come from `~/.claude/CLAUDE.md` (symlink to `~/AGENTS.md`); skills from `~/.claude/skills` → `~/.agents/skills`.
The only custom agent is `exact_agents/k-agent-reviewer.md.tmpl` (see [Subagents](../subagents.md)); search uses the built-in `Explore`.
The personal profile also keeps fullscreen mode and push notifications.
`settings.llama-cpp*.json.tmpl` hold the settings `,claude-llama-cpp` passes for local models: model-scoped `high` effort, thinking off.

### Mods

Claude Code mods are TypeScript function-hook plugins (early-access API).
Sources live in [`home/dot_claude/exact_mods/`](../../../../home/dot_claude/exact_mods/) and deploy to `~/.claude/mods/`.
Both settings profiles load them all with `env.CLAUDE_CODE_PLUGIN_DIRS`. Pi, OMP, and the other harnesses do not run them.

| Mod                  | Event                                                    | Behavior                                                                                                                                                                                                                                                                                                                                                                                                                            |
| -------------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `behavior-map-guard` | `tool.call` on Edit, Write, NotebookEdit; `session.end`  | Runs `,behavior-map affected <path>`. Refuses the first edit per session in an unmapped directory; adds a context note for touched entries.                                                                                                                                                                                                                                                                                         |
| `checked-gate`       | `tool.call` (every tool); `turn.start`; `classic.Stop`   | Sends the turn back once when: files changed (edits, or Bash changed the git working tree) and the final message has no `Checked:` list; or a turn that used a tool ends with a question whose last prose paragraph (before any list or code block) does not start with `Decision needed:` and that is not an item under `Open:` or `Known gaps:` (those are open items; a decision for the user belongs under `Decision needed:`). |
| `sop-guard`          | `tool.call` on Bash, WebFetch, Edit, Write, NotebookEdit | Refuses the hard-rule breaks listed below.                                                                                                                                                                                                                                                                                                                                                                                          |

`sop-guard` rules:

| Rule                                                                                                                                                                                                                               | Source           | Refusal                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------- |
| Edit of a chezmoi-managed target (symlinks resolved)                                                                                                                                                                               | `~/AGENTS.md` §6 | always; names the source path                                                               |
| A command that prints a secret: `pass show`, `security … -w`, `op read`, `gh auth token`, `cat .env` (quoted text, heredoc bodies, and `#` comments are not commands; a `#` inside `${…}` or after `(` in `[[ … ]]` is no comment) | `~/AGENTS.md` §5 | always, unless `$(...)`, a redirect, or a pipe into a non-printing command takes the output |
| Bare `tmux kill-server`                                                                                                                                                                                                            | `k-tmux`         | always, unless `-S` or `-L`                                                                 |
| A default-server tmux change (`send-keys`, `source-file`, `attach`, …)                                                                                                                                                             | `k-tmux`         | once per subcommand per session                                                             |
| WebFetch or `curl`/`wget` of `buildkite.com`                                                                                                                                                                                       | `k-buildkite`    | always                                                                                      |
| Edit of a path whose CODEOWNERS owners do not include the team                                                                                                                                                                     | `~/AGENTS.md` §5 | once per owner set per session                                                              |
| Edit in a repo with CODEOWNERS while the `team` option is empty                                                                                                                                                                    | `~/AGENTS.md` §5 | once per repo per session; asks for the team                                                |

This repo also has a project plugin, [`.claude/skills/dotfiles-guard/`](../../../../.claude/skills/dotfiles-guard/), which loads only in sessions started in this repo.
It refuses `make check-full`, `make test`, `bin/check --full` (repo `AGENTS.md`), `scripts/test_runner.py`, and `scripts/check.py --full` (user request).
A command inside a quoted string, such as `bash -c "make test"`, is not seen.
It keeps a copy of `sop-guard`'s `shell.ts`, because a plugin cannot import outside its folder; `test_claude_mods.py` fails when the copies differ.

The team is the `team` option (default `@elastic/kibana-management`), set under `pluginConfigs` in settings.
A "once" refusal passes on retry: the model retries only when the condition in the refusal message holds.

All of them fail open: a failed hook or a missing command lets the call through.
`behavior-map-guard` never refuses a docs-only, test-only, `/tmp`, or non-git edit.
Bash-only edits rely on the SOP's mapping rule, not this guard.
`checked-gate` snapshots only the git repo of the session's working directory, so Bash changes in another repo are not seen.
A turn whose only change is `git commit`, `stash`, or `reset` also changes the snapshot, so a commit-only reply is sent back once.
Each check (missing `Checked:`, ending question) sends a turn back at most once per Stop chain (a continuation has `stop_hook_active` set), so a turn is sent back at most twice.
The question check stays quiet when the user's prompt asks to be asked ("ask me", "asking us"), unless a negation ("not", "never", …) comes up to three words before it ("don't even need to ask me"), or "stop", "quit", or "avoid" up to two words before it, not across "and", "then", or "to". "Don't hesitate to ask me" and a negation in a condition ("if not sure, ask me") stay invitations.
Markdown blockquotes and fenced code are excluded from the question check, so quoted draft questions do not trigger it.
A continuation after a send-back keeps the turn's state, so each check stays once per turn.
`sop-guard` reads `$(...)` inside double quotes as data: `echo "$(pass show x)"` and a quoted `"$(curl https://buildkite.com/...)"` pass.
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

### Antigravity settings

Antigravity (`agy`) reads its global MCP servers from `~/.gemini/config/mcp_config.json`, generated directly from the shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) registry by `07-generate-mcp-configs`. Hosted OAuth servers without an Antigravity row in `oauth_by_tool` are omitted.

Instructions and skills live in Antigravity's global customization root: `~/.gemini/config/AGENTS.md` points to `~/AGENTS.md`, while `~/.gemini/config/skills` symlinks to `~/.agents/skills`. There are no Antigravity hooks.

Paid Gemini API quota for Antigravity CLI is declared in [`home/dot_gemini/private_antigravity-cli/readonly_settings.policy.json`](../../../../home/dot_gemini/private_antigravity-cli/readonly_settings.policy.json) and merged into `~/.gemini/antigravity-cli/settings.json` by `07-merge-antigravity-cli-settings` (declared-over-live). Policy owns `modelProvider: "gemini"`, `model: "Gemini 3.8 Flash (High)"`, and `enableTelemetry: false`, and strips any top-level `gcp` pin. That Flash pin is the interactive-TUI default. Runtime fields such as `trustedWorkspaces`, `permissions`, and `statusLine` survive. Fish still loads `GEMINI_API_KEY` from `pass google/gemini/api/token`; the key alone does not switch providers.

Do not export `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_CLOUD_PROJECT`, or `GOOGLE_CLOUD_LOCATION` into interactive shells. Those force `authMethod=gcp` onto `aiplatform.googleapis.com` and burn shared Vertex quota instead. Corporate Google OAuth without the Gemini API key provider lands on Antigravity Starter product quota.
