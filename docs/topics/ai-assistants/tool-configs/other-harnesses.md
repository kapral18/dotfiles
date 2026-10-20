---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

Codex, OpenCode, Oh My Pi, Crush, tuicr, and lgtm keep harness-native configuration. Shared agent instructions come from `~/AGENTS.md`; Claude's workflow mods are not ported here.

## Codex and OpenCode

| Tool     | Config source                                                                                                      | Merge                                                                                              |
| -------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/private_config.toml`](../../../../home/dot_codex/private_config.toml)                             | `run_onchange_after_07-merge-codex-config.sh.tmpl` injects MCP servers into `~/.codex/config.toml` |
| OpenCode | [`home/dot_config/opencode/readonly_opencode.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.jsonc) | `run_onchange_after_07-merge-opencode-config.sh.tmpl`                                              |

OpenCode loads [`plugins/readonly_intent-guard.ts.tmpl`](../../../../home/dot_config/opencode/plugins/readonly_intent-guard.ts.tmpl), the intent card adapter ([Staying on the goal](../staying-on-goal.md)).

Interactive shells route `codex` through `~/bin/,codex`, which injects the local llama.cpp model catalog when needed and then runs the real binary.

### Codex settings

`model = "gpt-6-astra"`, `model_reasoning_effort = "xhigh"`, `tui.auto_recap = false`, `features.memories = false` (`,ai-kb` is the only durable store).
Codex discovers shared skills under `~/.agents/skills`. `k-review`'s Verify mode uses fresh native agents with the shared reviewer prompt; other modes stay inline. See [Subagents](../subagents.md).

Policy: `approval_policy = "on-request"`, `sandbox_mode = "danger-full-access"`.

Hooks: `[[hooks.*]]` entries run `,task hook codex` on `UserPromptSubmit`, `SessionStart` (`compact`), `PreToolUse` (`apply_patch|Write|Edit|Bash`), `PostToolUse`, and `Stop` ([Staying on the goal](../staying-on-goal.md)). Codex runs a config hook only after it is trusted once in `/hooks`; the merge keeps the trust hashes.

### Codex reconciliation

The merge rebuilds `config.toml` from source plus the MCP registry and keeps these runtime-owned entries from the live file:

| Runtime-owned entry                               | Rule                        |
| ------------------------------------------------- | --------------------------- |
| `mcp_servers.<server>.tools.<tool>.approval_mode` | valid values only           |
| `projects.*.trust_level`                          | `trusted` or `untrusted`    |
| `hooks.state.*.trusted_hash`                      | reattached                  |
| `tui.model_availability_nux.*`                    | counters in `0..4294967295` |

Everything else in the live file is replaced. Narrow exact-command approvals can live in `~/.codex/rules/*.rules`.

### Provider wrappers

| Wrapper                                                        | Backend                                                            |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `,claude-openrouter`, `,codex-openrouter`                      | OpenRouter; default `xiaomi/mimo-v2.6-pro` at `high`               |
| `,claude-llama-cpp`, `,codex-llama-cpp`, `,opencode-llama-cpp` | local llama.cpp router; see [launchers](../llama-cpp/launchers.md) |

The OpenRouter wrappers read `OPENROUTER_API_KEY`, falling back to `pass show openrouter/api/token`.
`--model <id>` and `--effort <level>` (aliases `--reasoning-effort`, `--thinking`; `--no-thinking` = `minimal`) compose `<model>@preset/effort-<level>`.
Before launch each wrapper ensures the `effort-<level>` preset exists in the active OpenRouter account (created with only `reasoning.effort`; an existing preset is used unchanged).
`--context short|long` selects the working window.

- `,claude-openrouter` sets `ANTHROPIC_BASE_URL=https://openrouter.ai/api` (no `/v1`; the SDK appends `/v1/messages`) and maps every Claude alias to the selected wire id.
- `,codex-openrouter` adds a per-run Responses provider (`wire_api="responses"`, `env_key="OPENROUTER_API_KEY"`) and leaves `model_reasoning_effort` unset so the preset is the only effort source.

Fish completions for `--model`/`--effort` share `~/.config/fish/functions/__openrouter_catalog.fish` (cache `~/.cache/,openrouter/models.tsv`, from `GET /api/v1/models?supported_parameters=reasoning`).

## Oh My Pi

| Surface      | Source                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Target                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------- |
| Config       | [`home/dot_omp/private_agent/readonly_config.yml.tmpl`](../../../../home/dot_omp/private_agent/readonly_config.yml.tmpl)                                                                                                                                                                                                                                                                                                                                                                                                       | `~/.omp/agent/config.yml`   |
| Models       | `readonly_models.yml`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `~/.omp/agent/models.yml`   |
| MCP servers  | `mcp_servers.yaml` via `generate_mcp_configs.py omp`                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | `~/.omp/agent/mcp.json`     |
| Instructions | `symlink_AGENTS.md`, `readonly_APPEND_SYSTEM.md` (workflow overlay: inline work, scout, reviewer use, and static verification per `AGENTS.md` §3 step 4, which replaces the base prompt's verification defaults), `readonly_RULES.md` (sticky §5 git and publication rules plus §2 evidence and static verification with the live-check definition, for subagents that do not load `AGENTS.md`); `readonly_config.yml.tmpl` sets `personality: none` and `tui.reactions: false`, so OMP's prompt adds no tone rules of its own | `~/.omp/agent/`             |
| Skills       | `symlink_skills` → `~/.agents/skills`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `~/.omp/agent/skills`       |
| Advisors     | `readonly_WATCHDOG.yml`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | `~/.omp/agent/WATCHDOG.yml` |
| Reviewer     | `exact_agents/k-agent-reviewer.md.tmpl`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | `~/.omp/agent/agents/`      |
| Extensions   | `extensions/intent-guard.ts.tmpl` ([intent card](../staying-on-goal.md)); `extensions/advisor-followup.ts` (acts on late `Gate` notes, below)                                                                                                                                                                                                                                                                                                                                                                                  | `~/.omp/agent/extensions/`  |
| Install      | `@oh-my-pi/pi-coding-agent` in [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs)                                                                                                                                                                                                                                                                                                                                                                                                        | pnpm global, unpinned       |

OMP uses native `/extended-context on|off|status` and per-model compaction limits (`/models` → Roles → `k`).
The managed default is off, so OMP uses each model's native default window: `openai-codex/gpt-6.1-sol` is 500,000 tokens; Astra and Luna are 272,000. Codex's own catalog advertises those same defaults. There is no provider-wide 272K default or custom GPT context override.
Native extended context opens 922,000 input tokens for Sol and Astra where supported. These are local context budgets, not billing or server-capacity guarantees.
The former `/context-mode` extension is retired: OMP's native policy could override its requested window while its status still reported success.
Restart the OMP process after applying the removal; reloading the session or extension dashboard does not unload the already-imported extension. Old transcript mode entries no longer control OMP after restart.
Pi retains its own [working-context selection](pi.md#working-context-selection).

Key settings:

| Setting                                                | Value                                                                                                                                                                                                                              |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `modelRoles`                                           | `default`/`slow`/`plan`: `anthropic/claude-opus-5-5:medium`; `task`/`smol`/`vision`: `anthropic/claude-sonnet-5-5:medium`; `tiny`/`commit`/`web`: `anthropic/claude-haiku-5-5:medium`; `advisor`: `openai-codex/gpt-6-astra:xhigh` |
| `modelProviderOrder`                                   | `anthropic`, `openai-codex`, `openrouter`, `openai`                                                                                                                                                                                |
| `advisor.enabled`                                      | `true`; the Astra advisor uses a different model family from the Opus root; `advisor.syncBacklog: "1"` (a string; a bare number reads as `off`)                                                                                    |
| `task.agentAdvisor.task`                               | `"off"`; child advisors stay disabled                                                                                                                                                                                              |
| `memory.backend`, `autolearn.enabled`, `recap.enabled` | `off`, `false`, `false`                                                                                                                                                                                                            |
| `task.maxRecursionDepth`                               | `1` (children cannot spawn)                                                                                                                                                                                                        |
| `task.disabledAgents`                                  | `reviewer`, `security-reviewer` (the repo `k-agent-reviewer` replaces them)                                                                                                                                                        |
| `extendedContext`, `defaultThinkingLevel`              | `false`, `medium`                                                                                                                                                                                                                  |
| `compaction.methodOrder`                               | `snapcompact`, `remote`, `soft`: local image-frame archive first (models with image input only), then provider-native compaction, then a summary                                                                                   |
| `dev.autoqaConsent`                                    | `granted`                                                                                                                                                                                                                          |

`WATCHDOG.yml` replaces OMP's default advisor, which reviewed every turn, with one advisor, `Gate`.
The default advisor made the root wait for it every turn and could steer mid-run every turn.
OMP keeps one interrupt cooldown (`advisor.immuneTurns`) for all advisors, so a cooldown to quiet it would also mute `Gate`'s final concern.
OMP steers the agent after the final answer only for a blocker or an `agent-end` concern; otherwise the user sees the notes as a card.
`Gate` is the final-answer reviewer: `reviewMode: agent-end` with Gate's own `syncBacklog: 1` (the global setting is the string `"1"`) makes the root wait for its review for at most 30 seconds (`strict` would wait with no cap). A note that lands later, while the session is idle, becomes a follow-up turn through `advisor-followup.ts`; if the user already started a new prompt, OMP may steer that note into the new run.
Like `stop-review`, it holds no rules of its own: it judges against `~/AGENTS.md` (an advisor context file), sends a `concern` for every break the agent can fix now (the 3 most severe if more), skips preferences, judges the answer against the intent card first when the intent-guard extension added one to the prompt, and checks §2, §1, §3 steps 3 and 8, and §5 first.
It sends every concern in its first review of a run, so the run goes back once with all of them; a later review of the same run sends only a break the agent's last change introduced or a concern held back for the 3-note cap.
OMP steers at most one continuation turn per final review.
It steers only a `concern` or `blocker`, and only while no user interrupt is in effect. A prompt or a queued message clears its interrupt flag, but the empty Enter that interrupts a run to send a queued message sets it again, as does cancelling an `ask`; the resumed run keeps it.
In those runs, and for any `nit`, the final note became a passive card and the agent stopped until the user replied.
`advisor-followup.ts` closes that gap in the main session: when an advisor note lands after a finished answer (`stopReason: stop`) and the agent has not answered it by the terminal `agent_end`, or lands while the session is idle, it steers a hidden `advisor-followup` message that starts a turn to weigh the notes and rewrite the final answer. When OMP continues the settle itself (`willContinue`, for example a `session_stop` or todo continuation, a retry, or background work), that turn's reply does not count as an answer; the terminal settle resolves the note: a follow-up after a finished answer, else the note is dropped. A message that starts a user turn by OMP's own rule (a prompt, a `/skill:` prompt, a collab peer's prompt) drops a pending note; other user-attributed messages, such as a `/tan` breadcrumb riding along with a continuation, do not.
`advisor-followup.ts` also relabels OMP's spinner "Advisor reviewing the final answer" when a final answer ends, since OMP otherwise keeps showing the last tool's label during the review wait, and restores the default label once, at the next `agent_end` or `turn_start`.
`Gate` reviews the follow-up turn like any other run, so the exchange goes on until `Gate` has no new note; OMP's emission guard drops a note it already sent.
It leaves a run alone whose last answer was interrupted or ended in a tool call. Extensions get no interrupt signal, so an Esc pressed after a finished answer and before the follow-up starts does not stop it; an Esc that cancels a continuation OMP had scheduled leaves the note to the user. It also starts turns in plan mode, where OMP keeps advisor notes as cards; extensions cannot see plan-mode state.

Web search uses `modelRoles.web` (Haiku) as its primary. OMP 18.11.1 migrates the legacy `providers.webSearchOrder` into `retry.fallbackChains.web`, replacing its leading Codex selector with the explicit Haiku role. The effective fallbacks are `web/startpage`, `web/duckduckgo`, `web/ecosia`, `web/google`, `web/mojeek`, `web/public`, then `web/hosted`. Perplexity remains excluded.

## Crush

Crush auto-discovers project-local context files (such as `AGENTS.md`) from the working directory only. The home SOP is injected into every session through a global `crushrc`.

| Surface       | Path                                                                                           | Target                    |
| ------------- | ---------------------------------------------------------------------------------------------- | ------------------------- |
| Global config | [`home/dot_config/crush/readonly_crushrc`](../../../../home/dot_config/crush/readonly_crushrc) | `~/.config/crush/crushrc` |
| Home SOP      | [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md) → `~/AGENTS.md`               | global context path       |

The `crushrc` sets `option global-context-path "$HOME/AGENTS.md"`, so Crush loads the home instructions in every session regardless of cwd. It also runs `model large openrouter/z-ai/glm-5.3-flash --reasoning-effort high`, using Crush's native full model context. Project repos keep their own local `AGENTS.md`, which is discovered automatically; project-local instructions may add constraints but must not weaken the global SOP. Crush's runtime data JSON has higher precedence than `crushrc`, so deployment reconciles the saved selection separately.

## tuicr (review TUI)

[tuicr](https://github.com/agavra/tuicr) is a terminal UI for code review, not an LLM harness. Its config is single-sourced and read-only.

| Surface | Path                                                                                                   | Target                        |
| ------- | ------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Config  | [`home/dot_config/tuicr/readonly_config.toml`](../../../../home/dot_config/tuicr/readonly_config.toml) | `~/.config/tuicr/config.toml` |

The config defines the review **comment types** (`issue`, `suggestion`, `question`, `nit`, `praise`) that tuicr exports as `[LABEL]` prefixes in the markdown an agent consumes.

These are actionable categories, not severity. Severity (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`) stays in the `k-review` finding format and is intentionally not encoded here, so tuicr labels and the review skill's severity model do not collide.

## lgtm (live diff reviewer)

[lgtm](https://github.com/kunkka19xx/lgtm) is a terminal diff reviewer that runs in a tmux pane beside the agent and sends `path:line` references into its input box. Its config is single-sourced and read-only.

| Surface | Path                                                                                                 | Target                       |
| ------- | ---------------------------------------------------------------------------------------------------- | ---------------------------- |
| Config  | [`home/dot_config/lgtm/readonly_config.toml`](../../../../home/dot_config/lgtm/readonly_config.toml) | `~/.config/lgtm/config.toml` |

The config sets the `catppuccin` theme, nerd-font icons, inline comment rendering, lockfile ignores, and the compose-box question presets; every other setting stays compiled-in default.

Per-repo `.lgtm/` state (comments, reviews, read marks) and `refs/lgtm/**` snapshots are runtime-owned and intentionally unmanaged by chezmoi.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

```bash
echo "${GEMINI_API_KEY:+set}"
echo "${OPENROUTER_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime. See [Security and secrets](../../security/security-and-secrets.md).
