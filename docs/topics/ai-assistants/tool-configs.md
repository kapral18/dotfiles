---
sidebar_position: 7
---

# Tool Configs

Per-assistant configuration: the Cursor CLI harness, the profile-based merging mechanism, and each tool's settings source. MCP servers and model lists are single-sourced separately (see [MCP servers](mcp.md) and [Model registry & routing](model-registry.md)).

## Cursor agent CLI

A cross-shell alias `agent` is provided for `cursor-agent`:

- POSIX interactive shells: [`home/readonly_dot_shellrc`](../../../home/readonly_dot_shellrc) → `~/.shellrc`
- fish: [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl) → `~/.config/fish/config.fish`

```bash
command -v agent
agent --help
```

Cursor CLI is the primary interactive assistant harness. Its user-level hooks (session context, worklog, evidence ledger) make up the hook-memory layer — documented in [Agent memory](knowledge-base.md).

### Tmux agent prompt wrap

When running an AI coding agent (`claude`, `cursor-agent`, or `pi`) inside tmux, `Alt-Enter` is intercepted to prepend a calibrated verification scaffold to your prompt before submitting.

- **Binding:** `Alt-Enter` (submits the wrapped prompt)
- **Toggle:** `prefix` + `W` (toggles wrapping on/off for the session)
- **Prefix text:** [`home/dot_config/exact_tmux/agent_prompts/prefix.txt`](../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt)

Plain `Enter` is never touched. `Alt-Enter` is passed through untouched in non-agent panes or when the toggle is OFF.

## Profile-based file merging

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk target and a `run_onchange` script writes the correct profile-specific version from the repo source.

Instead of keeping complex templates or comment-based filtering logic, we use explicit `.work.*` and `.personal.*` files. The shell script checks the `.isWork` template variable and copies the correct source to the final destination, completely decoupling the formats. All merge scripts live under [`home/.chezmoiscripts/`](../../../home/.chezmoiscripts/) and source the shared [`scripts/chezmoi_lib.sh`](../../../scripts/chezmoi_lib.sh) helper library.

| Tool                 | Source files                                                                                                                                                          | Target                               | Merge script                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Claude Code settings | [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/)                                                                                          | `~/.claude/settings.json`            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Gemini settings+MCP  | [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml)                         | `~/.gemini/settings.json`            | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config+MCP  | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../home/dot_config/opencode/)                                                              | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config+MCP     | [`home/dot_codex/private_config.{work,personal}.toml`](../../../home/dot_codex/)                                                                                      | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi settings/models   | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../home/dot_pi/agent/) + [`readonly_models.json`](../../../home/dot_pi/agent/readonly_models.json) | `~/.pi/agent/{settings,models}.json` | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |

Pi targets are installed readonly. MCP-server injection for each tool is covered in [MCP servers](mcp.md).

## Claude Code settings

Source: [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/) → `~/.claude/settings.json`.

Both profiles enable extended thinking and skip the dangerous-mode permission prompt. The work profile uses native Claude enterprise auth by default (no `apiKeyHelper` or `ANTHROPIC_BASE_URL` override). MCP servers are stored separately in `~/.claude.json` (top-level `mcpServers` field) because that file contains runtime state managed by Claude Code; the merge script surgically updates only the `mcpServers` key, leaving other fields intact.

**LetsFG** is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions. Agents load [`~/.agents/skills/letsfg/SKILL.md`](../../../home/exact_dot_agents/exact_skills/exact_letsfg/readonly_SKILL.md) on demand and use the local `letsfg` uv tool from [`home/readonly_dot_default-uv-tools.tmpl`](../../../home/readonly_dot_default-uv-tools.tmpl) for free local searches that return direct airline/OTA `booking_url` values. Normal agent searches pass `LETSFG_BROWSERS=0` on each `letsfg` invocation so LetsFG skips browser connectors without changing the user shell environment; browser connectors are explicit opt-in. Playwriter headless browser automation remains a fallback for rendered UI checks or booking-adjacent flows that need explicit user confirmation.

## Gemini CLI settings

Source: [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json) → `~/.gemini/settings.json`.

- MCP servers are injected from the shared [`mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) registry at apply time (no longer hardcoded in the settings file).
- Tool approval is controlled by `general.defaultApprovalMode` (we use `auto_edit` to auto-approve edit tools).

## Pi coding agent settings

**Installation:** Pi globals are installed via yarn from [`home/readonly_dot_default-yarn-pkgs`](../../../home/readonly_dot_default-yarn-pkgs) → `~/.default-yarn-pkgs`:

| Package                           | Purpose                                                    |
| --------------------------------- | ---------------------------------------------------------- |
| `@earendil-works/pi-coding-agent` | Core Pi agent                                              |
| `@earendil-works/pi-tui`          | Pi TUI (work profile)                                      |
| `pi-mcp-adapter`                  | MCP adapter extension                                      |
| `pi-subagents`                    | Subagent delegation extension (parallel, isolated context) |

**Config sources:**

| Config            | Source                                                                                                                                                                                        |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Settings + models | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../home/dot_pi/agent/) + shared [`readonly_models.json`](../../../home/dot_pi/agent/readonly_models.json) → `~/.pi/agent/` |
| MCP servers       | [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) (shared registry) → `~/.pi/agent/mcp.json`                                                                |

**Profile defaults:** both work and personal default to provider `openrouter`, model `anthropic/claude-opus-4.8`. The work profile also exposes additional configured models alongside the OpenRouter default.

**Shared settings:**

- Automatic context compaction (hybrid sliding window): triggers when context exceeds `contextWindow − reserveTokens` (16384), keeps the most recent `keepRecentTokens` (80000) verbatim, and LLM-summarizes older turns — merging iteratively with the prior summary so it never decays into a summary-of-a-summary. `keepRecentTokens` is raised from Pi's `20000` default to preserve far more high-fidelity recent context before any lossy summarization. The setting is global (not per-model); 80000 is sized for the smallest window in play (the local Qwen3.6 model at 262144 tokens, ~30% recent-verbatim) and stays comfortably safe on the larger OpenRouter default `anthropic/claude-opus-4.8` (1000000-token window).
- Exponential backoff retries
- Pi loads `pi-mcp-adapter` and `pi-subagents` from yarn global `node_modules` paths in Pi settings `packages` (avoids Pi-managed npm update prompts; `pi install` is not used). Each package's `package.json` `pi` field declares its extension/skills/prompts, which Pi auto-loads. `@earendil-works/pi-tui` stays yarn-managed but is not loaded as a Pi extension package.
- `pi-subagents` adds a `subagent` tool so Pi can delegate work (review, scout, parallel audits) to child agents with isolated context windows, keeping the parent session's token use bounded on long tasks. Fully local — no network/telemetry beyond the model calls the child agents make.
- Shell PATH order keeps `~/.yarn/bin` ahead of runtime-manager shims so `pi` resolves to the yarn-managed binary
- Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) are picked up from environment variables exported via `pass` in `config.fish.tmpl`

The work-profile LiteLLM provider and the local llama.cpp provider for Pi are covered in [Model registry & routing](model-registry.md) and [llama.cpp local inference](llama-cpp.md).

## Cross-harness subagents

Subagents run a self-contained task (review, external-repo research, semantic code search) in an **isolated child context window** and return only a digest, so the heavy reads/searches never bloat the parent conversation. Each harness has its own subagent runtime and definition format, so there is no single shared subagent file — but skills stay the one source of truth and each subagent is a thin wrapper that loads a skill.

**Two portable layers (do not conflate them):**

- **Skills** (`~/.agents/skills/`) are the cross-harness source of truth, loaded by every assistant (Cursor, Claude, Pi, Gemini, OpenCode).
- **Subagents** are per-runtime, and only two harnesses support user-global subagents:
  - **Claude Code** reads `~/.claude/agents/*.md`.
  - **Pi** has its own format and reads `~/.pi/agent/agents/*.md` (and, unavoidably, recursively from `~/.agents/` — see leakage below).
  - **Cursor CLI is excluded.** Runtime-verified (`cursor-agent v2026.06.03`): Cursor only loads **project-scoped** `.cursor/agents/` and ignores every user-global path, including `~/.claude/agents/` and `~/.cursor/agents/`. There is no `$HOME`-level subagent surface to wire declaratively, so dotfiles do not manage Cursor subagents.

**The suite** wraps read-heavy skills (distinct agent names so they never collide with the skill names). `review` is the reference implementation of the two-phase pattern; the others are judge-only specializations:

| Agent                    | Wraps skill            | Isolated work                                                                    |
| ------------------------ | ---------------------- | -------------------------------------------------------------------------------- |
| `review-controller` (Pi) | `review`               | Orchestrates a multi-model review then acts (fix tree / draft / drain / verdict) |
| `reviewer`               | `review`               | Read-only review worker (one angle/model); returns findings, never posts         |
| `researcher`             | `research`             | Clone + inspect an external GitHub repo under `/tmp/agent-src`                   |
| `code-searcher`          | `semantic-code-search` | SCSI semantic investigation / base-branch context                                |

**Two-phase review hierarchy** (the topology falls out of the `review` skill's role×mode matrix):

- **Find/judge** is parallel and multi-model: read-only `reviewer` workers inspect the diff/PR from files, each on a distinct angle. The fan-out is the place where a second model earns its keep (adversarial disagreement).
- **Act** is serial, side-effectful, and scenario-aware: fix the working tree (own changes / self-review), draft inline comments (reviewing others), drain threads with the SOP posting gate (PR fix), or emit a verdict (verify-a-fix).
- **Pi** runs the full hierarchy: `review-controller` (default model) detects role+mode, fans out to two `reviewer` tasks with per-task model overrides — both via OpenRouter (Pi's `defaultProvider`): `openrouter/anthropic/claude-opus-4.8:off` (no extended thinking) and `openrouter/openai/gpt-5.5:xhigh` (max reasoning budget) — reconciles via the skill's dedup + truth filter, then performs the act phase itself. The `:<thinking>` model suffix sets reasoning effort; `pi-subagents` does not consume a `thinking` frontmatter field, so effort lives in the model slug, not the agent.
- **Claude** cannot run the hierarchy: its subagents cannot spawn subagents. A single read-only `reviewer` returns findings and the **main session** synthesizes and acts. Multi-model fan-out is therefore a Pi-only capability.

**Sources** (chezmoi-managed, deployed declaratively):

| Target                    | Source                                                                        | Consumed by |
| ------------------------- | ----------------------------------------------------------------------------- | ----------- |
| `~/.claude/agents/*.md`   | [`home/dot_claude/exact_agents/`](../../../home/dot_claude/exact_agents/)     | Claude      |
| `~/.pi/agent/agents/*.md` | [`home/dot_pi/agent/exact_agents/`](../../../home/dot_pi/agent/exact_agents/) | Pi          |

**Design notes:**

- Each agent file's body explicitly instructs loading the wrapped `~/.agents/skills/<name>/SKILL.md`. Claude files set Claude fields (`model`, `readonly: true`, `tools`, `skills:` preload); Pi files use Pi frontmatter (`inheritSkills`, `systemPromptMode`, comma-separated `tools`, `maxSubagentDepth` on the controller). No `thinking` field — Pi reasoning effort is set per task via the model slug suffix.
- Workers are strictly read-only: they report fixes for the parent (the Pi `review-controller`, or the Claude main session) to apply rather than editing or posting themselves. Only the Pi `review-controller` performs the act phase, and it still honors the Human-Visible Publication Gate (bot threads auto-resolve inside the flow; human threads stop for approval).
- **Built-in subagents:** Pi ships 8 stock role agents (`reviewer`, `scout`, `oracle`, …) that overlap and name-collide with ours, so they are disabled via `subagents.disableBuiltins: true` in Pi settings. Claude (`Explore`/`Plan`/general-purpose) built-ins are generic context-savers that coexist with our distinctly-named agents and are intentionally left enabled.
- **Pi skill leakage (accepted):** Pi's subagent extension recursively scans `~/.agents/` and registers every `SKILL.md` (which all carry `name`+`description`) as a subagent. There is no Pi setting or frontmatter flag to suppress this (verified in the extension source), and the skills must keep that frontmatter for cross-harness discovery. The effect is cosmetic — the Pi subagent list also shows skill names — and harmless because our agents have distinct names and sharper delegation descriptions; we deliberately do not patch the extension to keep upgrades clean.

## Codex, OpenCode, Amp

| Tool     | Config source                                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/`](../../../home/dot_codex/)                                                                                   |
| OpenCode | [`home/dot_config/opencode/`](../../../home/dot_config/opencode/)                                                               |
| Amp      | [`home/dot_config/exact_amp/private_readonly_settings.json`](../../../home/dot_config/exact_amp/private_readonly_settings.json) |

Codex and OpenCode use the profile-merging mechanism above (with MCP injection); Amp settings are tracked directly. Codex and OpenCode each have a llama.cpp launcher wrapper (`,codex-llama-cpp`, `,opencode-llama-cpp`) — see [llama.cpp local inference](llama-cpp.md#codex-launcher-codex-llama-cpp).

## Token optimization (RTK)

[RTK](https://github.com/rtk-ai/rtk) (`brew "rtk"`, added in [`brews/shared/38-ai-large-language-models.brewfile`](../../../home/.chezmoitemplates/brews/shared/38-ai-large-language-models.brewfile)) is a CLI proxy that compacts noisy command output (test runners, linters, `git log`/`git status`, build tools, …) to cut 60-90% of the tokens those outputs would otherwise consume. Each agent's pre-execution shell hook calls the native `rtk hook <agent>` binary, which rewrites a command like `git status` to `rtk git status` before it runs; `rtk` then filters the output. No `jq` or shell wrapper is needed — the binary reads the hook JSON and emits the rewrite itself.

**Per-agent wiring (all chezmoi-managed source):**

| Agent    | Source                                                                                        | Mechanism                                                           |
| -------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Cursor   | [`home/dot_cursor/hooks.json`](../../../home/dot_cursor/hooks.json)                           | `preToolUse` entry `rtk hook cursor` (`matcher: "Shell"`)           |
| Claude   | [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/)                  | `PreToolUse` block `rtk hook claude` (`matcher: "Bash"`)            |
| Gemini   | [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json)                     | `BeforeTool` `run_shell_command`, `rtk hook gemini` after the gates |
| OpenCode | [`home/dot_config/opencode/plugins/rtk.ts`](../../../home/dot_config/opencode/plugins/rtk.ts) | `tool.execute.before` plugin calling `rtk rewrite`                  |
| Pi       | [`home/dot_pi/agent/extensions/rtk.ts`](../../../home/dot_pi/agent/extensions/rtk.ts)         | `tool_call` extension calling `rtk rewrite`                         |

The Cursor and Gemini RTK hooks run **after** the existing git/PR gates ([`gemini-git-gate.sh`](../../../home/exact_dot_agents/exact_hooks/executable_gemini-git-gate.sh), [`gemini-pr-anchor-gate.sh`](../../../home/exact_dot_agents/exact_hooks/executable_gemini-pr-anchor-gate.sh)). RTK does not rewrite mutating git commands away from their gated form: `git commit`/`git push` map to `rtk git commit`/`rtk git push`, and both the Cursor matcher (`git\s+(commit|push)`) and the gate scripts (`git[[:space:]]+.*commit`) match that substring, so the gates still fire.

### RTK is a recoverable index, not a lossless substitute

Config: [`home/Library/Application Support/rtk/config.toml`](<../../../home/Library/Application Support/rtk/config.toml>) → `~/Library/Application Support/rtk/config.toml` (RTK reads `dirs::config_dir()/rtk/config.toml`; on macOS that is `~/Library/Application Support`, not XDG).

A full audit of RTK's filter surface classified every filter as one of:

| Class             | Meaning                                                            | Default handling   |
| ----------------- | ------------------------------------------------------------------ | ------------------ |
| SAFE              | Strips only boilerplate; no semantic loss                          | rewrite            |
| LOSSY-RECOVERABLE | Drops content but signals it (`+N more`, `[full output: <path>]`)  | rewrite + `tee`    |
| LOSSY-SILENT      | Drops semantically-relevant content with no count or recovery path | `exclude_commands` |

The config encodes that audit:

- `[hooks] exclude_commands = ["gh pr view", "gh pr checks", "git diff", "git show"]`:
  - `gh pr view` / `gh pr checks` — the two audited **LOSSY-SILENT** commands (they field-subset the PR/check JSON with no overflow count).
  - `git diff` / `git show` — **policy** exclusions: these are recoverable (the diff filter prints `… (N lines truncated)` + `[full diff: rtk git diff --no-compact]`), but a truncated diff is never useful for review or judgment, so we never compact them. The word-boundary match (`^git\ diff($|\s)`) excludes `git diff --staged`/`git diff HEAD~1` but **not** `git diff-tree`/`git difftool`, which stay rewritten.
  - `gh ... --json/--jq/--template` and `gh api` already pass through raw, and `git status/log` compact recoverably (overflow counts + `tee`), so they stay rewritten. `terraform plan`/`tofu plan` are TOML-only filters that are not auto-rewritten, so excluding them would be a no-op; `prisma` is reached as `npx prisma`/`pnpm prisma`, which a bare exclude cannot match — both are left to the recovery contract instead.
- `[tee] enabled = true, mode = "always"` — saves the full raw output for **every** long command (not just failures), so anything RTK compacts is one `cat` away.
- `[telemetry] enabled = false` — no phone-home.

**Recovery contract.** The SOP entrypoints (`~/AGENTS.md`, `~/CLAUDE.md` §2.4, `~/.gemini/GEMINI.md` §2.4) instruct every agent to treat a compacted view as an index: when output shows `[full output: <path>]`, `[see remaining: tail -n +N <path>]`, or `… +N more`, fetch the full output before relying on it. Recovery is mandatory for diff/PR review, debugging a failure, or enumerating issues; `RTK_DISABLED=1 <cmd>` (or `RTK_NO_TOML=1`, a tool's `--no-compact`/`--json`) bypasses the rewrite.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime. See [Security and secrets](../security/security-and-secrets.md).

## Related

- [MCP servers](mcp.md) — single-sourced server registry
- [Model registry & routing](model-registry.md) — single-sourced model definitions
- [llama.cpp local inference](llama-cpp.md) — local backend + Claude/Codex/OpenCode/Pi launchers
- [The Agentic Operating System](index.md) — governance layer
