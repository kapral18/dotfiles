---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

Codex, OpenCode, Oh My Pi, Crush, tuicr, and lgtm keep harness-native configuration. Shared agent instructions come from `~/AGENTS.md`; Claude's workflow mods are not ported here.

## Codex and OpenCode

| Tool     | Config source                                                                                               | Merge                                                                                              |
| -------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/private_config.{work,personal}.toml`](../../../../home/dot_codex/)                         | `run_onchange_after_07-merge-codex-config.sh.tmpl` injects MCP servers into `~/.codex/config.toml` |
| OpenCode | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../../home/dot_config/opencode/) | `run_onchange_after_07-merge-opencode-config.sh.tmpl`                                              |

Interactive shells route `codex` through `~/bin/,codex`, which injects the local llama.cpp model catalog when needed and then runs the real binary.

### Codex settings

Both profiles: `model = "gpt-6.1-sol"`, `model_reasoning_effort = "high"`, `tui.auto_recap = false`, `features.memories = false` (`,ai-kb` is the only durable store).
Codex discovers shared skills under `~/.agents/skills`. `k-review`'s Verify mode uses fresh native agents with the shared reviewer prompt; other modes stay inline. See [Subagents](../subagents.md).

| Profile  | Policy                                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| work     | `approval_policy = "on-request"`, `approvals_reviewer = "auto_review"`, `sandbox_mode = "workspace-write"` |
| personal | `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`                                         |

The work profile's `sandbox_workspace_write.writable_roots` add `~/.local/share/{chezmoi,ai-kb,agent-handoffs,k-ai-behavior-map}`, `~/.local/state/chezmoi`, `~/.local/state/llama-cpp/lifecycle`, `~/.cache/{ai-embed-runtime,agent-artifacts}`, `~/bin`, `~/lib`, `~/.agents`, `~/.codex`, and `~/.claude`.
These grant directory writes only; other paths still need approval.

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

| Surface      | Source                                                                                                                   | Target                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------ | --------------------------- |
| Config       | [`home/dot_omp/private_agent/readonly_config.yml.tmpl`](../../../../home/dot_omp/private_agent/readonly_config.yml.tmpl) | `~/.omp/agent/config.yml`   |
| Models       | `readonly_models.yml`                                                                                                    | `~/.omp/agent/models.yml`   |
| MCP servers  | `mcp_servers.yaml` via `generate_mcp_configs.py omp`                                                                     | `~/.omp/agent/mcp.json`     |
| Instructions | `symlink_AGENTS.md`, `readonly_APPEND_SYSTEM.md` (subagent overlay), `readonly_RULES.md`                                 | `~/.omp/agent/`             |
| Skills       | `symlink_skills` → `~/.agents/skills`                                                                                    | `~/.omp/agent/skills`       |
| Advisors     | `readonly_WATCHDOG.yml`                                                                                                  | `~/.omp/agent/WATCHDOG.yml` |
| Reviewer     | `exact_agents/k-agent-reviewer.md.tmpl`                                                                                  | `~/.omp/agent/agents/`      |
| Extension    | `extensions/context-mode.ts.tmpl` ([working-context selection](pi.md#working-context-selection))                         | `~/.omp/agent/extensions/`  |
| Install      | `@oh-my-pi/pi-coding-agent` in [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs)  | pnpm global, unpinned       |

The context-mode extension reapplies the session's chosen window after initial model discovery.
This keeps GPT's 272,000-token default from reverting to the catalog window without delaying the first interactive frame.
An overlapping mode command finishes first. Session or branch changes are refused while discovery or a context update is pending; retry when it finishes.

Key settings (both profiles):

| Setting                                                | Value                                                                                                                                                                                                                      |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `modelRoles.default`                                   | `anthropic/claude-opus-5-5:high` (Claude subscription); `slow`/`plan` `:max`; `task` `:medium`; `smol`/`vision` `claude-sonnet-5-5:high`; `tiny`/`commit` `claude-haiku-5-5:medium`; `web` stays `openai-codex/gpt-6-luna` |
| `advisor.enabled`                                      | `true`; advisors use `openai-codex/gpt-6-astra:high`, a different model family from the root                                                                                                                               |
| `task.agentAdvisor.task`                               | `"off"`; child advisors stay disabled                                                                                                                                                                                      |
| `memory.backend`, `autolearn.enabled`, `recap.enabled` | `off`, `false`, `false`                                                                                                                                                                                                    |
| `task.maxRecursionDepth`                               | `1` (children cannot spawn)                                                                                                                                                                                                |
| `task.disabledAgents`                                  | `reviewer`, `security-reviewer` (the repo `k-agent-reviewer` replaces them)                                                                                                                                                |
| `extendedContext`, `defaultThinkingLevel`              | `true`, `high`                                                                                                                                                                                                             |
| `dev.autoqaConsent`                                    | `granted`                                                                                                                                                                                                                  |

`WATCHDOG.yml` replaces OMP's default advisor with two advisors.
`General` is the default advisor, kept by name; it reviews every turn.
OMP shows a `General` concern about a finished answer only as a card, so the agent never acts on it; only a blocker or an `agent-end` concern starts another turn.
`Gate` is the final-answer reviewer and extends Claude's `checked-gate` mod: `reviewMode: agent-end` and `syncBacklog: strict` make the root wait for its review.
It sends a `concern` for a missing `Checked:` list or claim evidence, a claim from truncated output, a question not under `Decision needed:`, a done claim without passing check output, or a test that cannot fail, on top of OMP's base advisor review.
OMP steers at most one continuation turn per final review.

`providers.webSearchOrder` differs per profile: work tries OpenRouter, Codex, Gemini, Google, then DuckDuckGo; personal tries Codex then the keyless scrapers. Every unused provider is listed in `webSearchExclude`, including `perplexity`.

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
