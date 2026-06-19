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

Cursor CLI is the primary interactive assistant harness. Its user-level hooks (session context, worklog) make up the hook-memory layer — documented in [Agent memory](knowledge-base.md).

### Tmux agent prompt wrap

When running an AI coding agent (`claude`, `cursor-agent`, `pi`, or `copilot`) inside tmux, `Alt-Enter` is intercepted to prepend a calibrated verification scaffold and leave the prompt editable.

- **Binding:** `Alt-Enter` (inserts the wrapped prompt)
- **Toggle:** `prefix` + `W` (toggles wrapping on/off for the session)
- **Prefix text:** [`home/dot_config/exact_tmux/agent_prompts/prefix.txt`](../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt)

Plain `Enter` is never touched. Press it when the wrapped prompt is ready to send. `Alt-Enter` is passed through untouched in non-agent panes or when the toggle is OFF.

The same `prefix.txt` is **also injected automatically**: `session_context.py` injects it at `SessionStart` for hook-based harnesses such as `cursor-agent`, `claude`, and `copilot`; `ai-kb-recall.ts` injects it at the first `before_agent_start` for `pi`; and every registered custom subagent profile renders it as the first body/developer-instructions block in the isolated child context (see [Agent memory](knowledge-base.md)). The `Alt-Enter` wrap remains the way to prepend it to a specific prompt as a direct user message (stronger framing than session-level context).

## Profile-based file merging

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk target and a `run_onchange` script writes the correct profile-specific version from the repo source.

Instead of keeping complex templates or comment-based filtering logic, we use explicit `.work.*` and `.personal.*` files. The shell script checks the `.isWork` template variable and copies the correct source to the final destination, completely decoupling the formats. All merge scripts live under [`home/.chezmoiscripts/`](../../../home/.chezmoiscripts/) and source the shared [`scripts/chezmoi_lib.sh`](../../../scripts/chezmoi_lib.sh) helper library.

| Tool                       | Source files                                                                                                                                                                                           | Target                                                               | Merge script                                               |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | ---------------------------------------------------------- |
| Claude Code settings       | [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/)                                                                                                                           | `~/.claude/settings.json`                                            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Gemini settings+MCP        | [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml)                                                          | `~/.gemini/settings.json`                                            | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config+MCP        | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../home/dot_config/opencode/)                                                                                               | `~/.config/opencode/opencode.jsonc`                                  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config+MCP           | [`home/dot_codex/private_config.{work,personal}.toml`](../../../home/dot_codex/)                                                                                                                       | `~/.codex/config.toml`                                               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi settings/models         | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../home/dot_pi/agent/) + [`readonly_models.json`](../../../home/dot_pi/agent/readonly_models.json)                                  | `~/.pi/agent/{settings,models}.json`                                 | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |
| Copilot settings+MCP+hooks | [`home/dot_copilot/settings.json`](../../../home/dot_copilot/settings.json) + [`hooks.json`](../../../home/dot_copilot/hooks.json) + [`mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) | `~/.copilot/{settings.json,mcp-config.json,hooks/agent-memory.json}` | `run_onchange_after_07-merge-copilot-config.sh.tmpl`       |

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
| System prompt     | [`home/dot_pi/agent/readonly_APPEND_SYSTEM.md`](../../../home/dot_pi/agent/readonly_APPEND_SYSTEM.md) → `~/.pi/agent/APPEND_SYSTEM.md` (appended to Pi's default prompt)                      |

**Profile defaults:** both work and personal default to provider `openrouter`, model `anthropic/claude-opus-4.8`. The work profile also exposes additional configured models alongside the OpenRouter default.

**Shared settings:**

- Automatic context compaction (hybrid sliding window): triggers when context exceeds `contextWindow − reserveTokens` (16384), keeps the most recent `keepRecentTokens` (80000) verbatim, and LLM-summarizes older turns — merging iteratively with the prior summary so it never decays into a summary-of-a-summary. `keepRecentTokens` is raised from Pi's `20000` default to preserve far more high-fidelity recent context before any lossy summarization. The setting is global (not per-model); 80000 is sized for the smallest window in play (the local Qwen3.6 model at 262144 tokens, ~30% recent-verbatim) and stays comfortably safe on the larger OpenRouter default `anthropic/claude-opus-4.8` (1000000-token window).
- Exponential backoff retries
- Pi loads `pi-mcp-adapter` and `pi-subagents` from yarn global `node_modules` paths in Pi settings `packages` (avoids Pi-managed npm update prompts; `pi install` is not used). Each package's `package.json` `pi` field declares its extension/skills/prompts, which Pi auto-loads. `@earendil-works/pi-tui` stays yarn-managed but is not loaded as a Pi extension package.
- `pi-subagents` adds a `subagent` tool so Pi can delegate work (review, scout, parallel audits) to child agents with isolated context windows, keeping the parent session's token use bounded on long tasks. Fully local — no network/telemetry beyond the model calls the child agents make.
- Shell PATH order keeps `~/.yarn/bin` ahead of runtime-manager shims so `pi` resolves to the yarn-managed binary
- Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) are picked up from environment variables exported via `pass` in `config.fish.tmpl`

**Harness operating layer (`APPEND_SYSTEM.md`):** Pi's built-in default system prompt is intentionally minimal (~18 lines: persona, tools list, "be concise", "show file paths"), whereas Cursor injects a thick operating layer (tool-usage policy, task/todo discipline, code-citation format, proactiveness, edit-scope rules). With the same model and the same `AGENTS.md`, Pi therefore steered noticeably weaker because `AGENTS.md` carried the entire load alone. `~/.pi/agent/APPEND_SYSTEM.md` closes that gap: Pi auto-discovers it (`DefaultResourceLoader`) and appends it after the default prompt and before the `<project_context>` block that wraps any `AGENTS.md`/`CLAUDE.md`, so the final order is **Pi default → operating layer → project context**. It is profile-agnostic (no work/personal split) and installed readonly. Pi's sibling alternative — `SYSTEM.md` — would _replace_ the default entirely (losing Pi's accurate tools list and self-doc pointers), so the additive `APPEND_SYSTEM.md` is used instead.

**Scope (harness-vs-harness, not vs `AGENTS.md`):** the content is the set-difference _Cursor's built-in system prompt − Pi's built-in system prompt_ — only mechanics Pi's own prompt lacks. Pi's default carries just persona, tools list, "be concise", "show file paths", and self-doc pointers; the ported additive mechanics are tone/style (no emojis, no colon before a tool call, backtick paths/symbols), tool-calling (dedicated file tools over shell, **parallelize independent calls**, don't name tools to the user), code-change rules (read-before-edit, fix introduced linter errors, no narrating comments), autonomy, task management (todos for complex tasks, finish before yielding), structured enumerated questions, and `file_path:line_number` citations. It is independent of `AGENTS.md`: where a project context file overlaps, that file wins; nothing here restates it. Cursor-only items are deliberately excluded — `@`-mentions / system-tag handling, the terminal-files convention, and Plan/Agent mode-selection are Cursor platform features with no Pi equivalent, and Cursor's ` ```start:end:path``` ` citation block is a Cursor UI element Pi cannot render (so only the `file_path:line` form is ported). The inline-line-number rule is also dropped: Pi's read tool returns raw file text with no `LINE|` prefixes (verified in `core/tools/read.ts`), so there is nothing to disambiguate.

The work-profile LiteLLM provider and the local llama.cpp provider for Pi are covered in [Model registry & routing](model-registry.md) and [llama.cpp local inference](llama-cpp.md).

## Cross-harness subagents

Subagents run a self-contained task (review, external-repo research, semantic code search) in an **isolated child context window** and return only a digest, so the heavy reads/searches never bloat the parent conversation. Each harness has its own subagent runtime and definition format, so there is no single shared subagent file — but skills stay the one source of truth and each subagent is a thin wrapper that loads a skill. Every custom subagent profile is a chezmoi template that renders the shared `prefix.txt` preamble before its role instructions, so child contexts start with the same verification discipline as parent sessions.

**Two portable layers (do not conflate them):**

- **Skills** (`~/.agents/skills/`) are the cross-harness source of truth, loaded by every assistant (Cursor, Claude, Pi, Gemini, OpenCode, Copilot).
- **Subagents** are per-runtime:
  - **Cursor CLI** reads project `.cursor/agents/` and user `~/.cursor/agents/`. Runtime-verified from the bundled `~/.cursor/skills-cursor/create-subagent/SKILL.md` in `cursor-agent 2026.06.15-18-00-12-6f5a2cf`: project agents have higher priority than user agents.
  - **GitHub Copilot CLI** reads user `~/.copilot/agents/*.agent.md` and project `.github/agents/*.agent.md`; `copilot --agent <name>` and `/agent` are exposed by `copilot 1.0.63`, and `copilot help config` exposes `subagents.agents.<agent-name>` model/effort/context settings.
  - **Claude Code** reads `~/.claude/agents/*.md`; `claude 2.1.179` exposes `--agent`, `--agents`, `claude agents`, and a `Task` tool schema with `subagent_type` plus model overrides limited to `sonnet`, `opus`, `haiku`, and `fable`.
  - **Codex CLI** discovers `$CODEX_HOME/agents/*.toml` role files and exposes stable `multi_agent` with `spawn_agent`/`wait`; verified against `openai/codex@45f603302c45`.
  - **Gemini CLI** reads project `.gemini/agents/*.md` and user `~/.gemini/agents/*.md`; source docs in `google-gemini/gemini-cli@f741d0328209` say subagents are exposed as tools, can be forced with `@name`, and cannot call other subagents.
  - **Amp** exposes generic subagents through the `Task` tool and sees shared skills through `amp skill list`; it has no verified custom profile directory in the local CLI/package interface.
  - **Pi** has its own format and reads `~/.pi/agent/agents/*.md` (and, unavoidably, recursively from `~/.agents/` — see leakage below).

Verified model identifiers are not portable between harnesses. Cursor's requested review lanes are `gpt-5.5-extra-high` and `claude-opus-4-8-xhigh` from `cursor-agent models`; Copilot's equivalent lanes are `gpt-5.5` and `claude-opus-4.8` from `copilot help config`, with `effortLevel: xhigh` in `subagents.agents.*`. Cursor's CLI default can differ from the review policy (`composer-2.5-fast` was the live default on 2026-06-18), so Cursor review agents pin `model:` in their frontmatter and generic Subagent/Task launches must pass an explicit `model`. Minimal live probes on 2026-06-17 confirmed project custom-agent invocation in both CLIs, Cursor controller -> worker delegation, Copilot task subagents with explicit model overrides, both Opus model IDs, and Codex `spawn_agent`/`wait`.

**The suite** wraps read-heavy skills (distinct agent names so they never collide with the skill names). `review` is the reference implementation of the two-phase pattern; the others are judge-only specializations:

| Agent                                | Wraps skill            | Isolated work                                                                      |
| ------------------------------------ | ---------------------- | ---------------------------------------------------------------------------------- |
| `agent-review`                       | `agent-review`         | `/agent-review` controller: routes, fans out, aggregates, judges, then acts        |
| `review-controller` (Pi)             | `review`               | Orchestrates a multi-model review then acts (fix tree / draft / drain / verdict)   |
| `review-gpt-5-5-extra-high`          | `review`               | Read-only GPT reviewer lane for Cursor/Copilot fan-out                             |
| `review-opus-4-8-xhigh-non-thinking` | `review`               | Read-only Opus reviewer lane for Cursor/Copilot fan-out                            |
| `reviewer`                           | `review`               | Pi/Claude read-only review worker (one angle/model); returns findings, never posts |
| `review-worker`                      | `review`               | Codex read-only review worker role; run twice with distinct angles                 |
| `review-gemini-pro`                  | `review`               | Gemini Pro read-only review worker lane                                            |
| `review-gemini-flash`                | `review`               | Gemini Flash read-only review worker lane                                          |
| `findings-auditor`                   | `review`               | Read-only four-dimension audit of candidate findings or a named fix diff           |
| `live-ui-review`                     | `review`               | Read-only live UI verifier for UI/runtime-relevant candidate findings              |
| `researcher`                         | `research`             | Clone + inspect an external GitHub repo under `/tmp/agent-src`                     |
| `code-searcher`                      | `semantic-code-search` | SCSI semantic investigation / base-branch context                                  |

**Two-phase review hierarchy** (the topology falls out of the `review` skill's role×mode matrix):

- **Find/judge** is parallel and multi-model: read-only reviewer workers inspect the diff/PR from files, each on a distinct angle. The fan-out is the place where a second model earns its keep (adversarial disagreement).
- **Act** is serial, side-effectful, and scenario-aware: fix the working tree (own changes / self-review), draft inline comments (reviewing others), drain threads with the SOP posting gate (PR fix), or emit a verdict (verify-a-fix).
- **Cursor/Copilot** keep the shared `review` skill as methodology and use the separate `/agent-review` skill as a thin controller. The controller builds a scope packet, fans out through configured reviewer lanes, runs conditional live UI verification and findings audit, aggregates investigation outputs, then judges and acts. The reviewer workers load the full review methodology in their isolated contexts; the controller does not load or duplicate that review pass before fan-out. Cursor pins the default lane in agent frontmatter to `gpt-5.5-extra-high` and the Opus lane to `claude-opus-4-8-xhigh`; generic Subagent/Task calls must pass those same model IDs explicitly. Copilot uses task subagents with explicit `model` arguments (`gpt-5.5`, `claude-opus-4.8`) because nested probes showed that is the verified child-subagent mechanism.
- **Claude** now has a current-session `agent-review` controller profile. It uses `Task` for isolated reviewer, auditor, and live UI verification work; exact GPT-vs-Opus parity is not available in Claude's verified model override enum.
- **Codex** uses configured `$CODEX_HOME/agents/*.toml` roles through `spawn_agent`/`wait`; this preserves isolation and controller-only side effects, but not Opus model diversity.
- **Gemini** uses native `.gemini/agents/*.md` subagents for `review-gemini-pro`, `review-gemini-flash`, `findings-auditor`, and `live-ui-review`. Because Gemini subagents cannot call other subagents, `/agent-review` must run in the main Gemini session as the controller.
- **Amp** has no custom profile directory in the verified local interface. It bridges through generic `Task` prompts and the shared runtime contracts.
- **Pi** runs the full hierarchy: `review-controller` (default model) detects role+mode, fans out to two `reviewer` tasks with per-task model overrides — both via OpenRouter (Pi's `defaultProvider`): `openrouter/anthropic/claude-opus-4.8:off` (no extended thinking) and `openrouter/openai/gpt-5.5:xhigh` (max reasoning budget) — reconciles via the skill's dedup + truth filter, then performs the act phase itself. The `:<thinking>` model suffix sets reasoning effort; `pi-subagents` does not consume a `thinking` frontmatter field, so effort lives in the model slug, not the agent.

**Sources** (chezmoi-managed, deployed declaratively):

| Target                         | Source                                                                        | Consumed by |
| ------------------------------ | ----------------------------------------------------------------------------- | ----------- |
| `~/.cursor/agents/*.md`        | [`home/dot_cursor/exact_agents/`](../../../home/dot_cursor/exact_agents/)     | Cursor      |
| `~/.copilot/agents/*.agent.md` | [`home/dot_copilot/exact_agents/`](../../../home/dot_copilot/exact_agents/)   | Copilot     |
| `~/.claude/agents/*.md`        | [`home/dot_claude/exact_agents/`](../../../home/dot_claude/exact_agents/)     | Claude      |
| `~/.codex/agents/*.toml`       | [`home/dot_codex/exact_agents/`](../../../home/dot_codex/exact_agents/)       | Codex       |
| `~/.gemini/agents/*.md`        | [`home/dot_gemini/exact_agents/`](../../../home/dot_gemini/exact_agents/)     | Gemini      |
| `~/.pi/agent/agents/*.md`      | [`home/dot_pi/agent/exact_agents/`](../../../home/dot_pi/agent/exact_agents/) | Pi          |

**Design notes:**

- Each agent file's rendered body starts with `prefix.txt`, then explicitly instructs loading the wrapped `~/.agents/skills/<name>/SKILL.md` or a shared runtime contract. Cursor files use the minimal documented `name` + `description` frontmatter and keep model pins in the controller's invocation. Copilot files use `.agent.md` profiles with `target`, `model`, `tools`, and invocation controls; xhigh effort is configured in `settings.json` because `copilot help config` exposes per-subagent `effortLevel`. The Cursor/Copilot `agent-review` profiles only load the `/agent-review` skill; worker/auditor/live profiles load `~/.agents/skills/agent-review/references/runtime-contracts.md`, which keeps the per-runtime profiles thin while reviewer workers load the shared `review` methodology in child contexts. Claude files set Claude fields (`model`, `readonly: true`, `tools`, `skills:` preload); Codex files are TOML role configs with `developer_instructions`; Gemini files are YAML-frontmatter Markdown subagents; Pi files use Pi frontmatter (`inheritSkills`, `systemPromptMode`, comma-separated `tools`, `maxSubagentDepth` on the controller). No `thinking` field — Pi reasoning effort is set per task via the model slug suffix.
- Workers and auditors are strictly investigation-only: they report evidence for the parent controller (`/agent-review`, Pi `review-controller`, or Claude main session) to judge rather than editing, posting, resolving, or deciding themselves. Controllers perform the act phase and still honor the Human-Visible Publication Gate (bot threads auto-resolve inside an invoked flow; human threads stop for approval). `live-ui-review` is part of the default flow and returns applicability, comparison evidence, or a target/branch blocker.
- **Built-in subagents:** Pi ships 8 stock role agents (`reviewer`, `scout`, `oracle`, …) that overlap and name-collide with ours, so they are disabled via `subagents.disableBuiltins: true` in Pi settings. Claude (`Explore`/`Plan`/general-purpose) built-ins are generic context-savers that coexist with our distinctly-named agents and are intentionally left enabled.
- **Pi skill leakage (accepted):** Pi's subagent extension recursively scans `~/.agents/` and registers every `SKILL.md` (which all carry `name`+`description`) as a subagent. There is no Pi setting or frontmatter flag to suppress this (verified in the extension source), and the skills must keep that frontmatter for cross-harness discovery. The effect is cosmetic — the Pi subagent list also shows skill names — and harmless because our agents have distinct names and sharper delegation descriptions; we deliberately do not patch the extension to keep upgrades clean.

## Codex, OpenCode, Amp

| Tool     | Config source                                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/`](../../../home/dot_codex/)                                                                                   |
| OpenCode | [`home/dot_config/opencode/`](../../../home/dot_config/opencode/)                                                               |
| Amp      | [`home/dot_config/exact_amp/private_readonly_settings.json`](../../../home/dot_config/exact_amp/private_readonly_settings.json) |

Codex and OpenCode use the profile-merging mechanism above (with MCP injection); Amp settings are tracked directly. Codex and OpenCode each have a llama.cpp launcher wrapper (`,codex-llama-cpp`, `,opencode-llama-cpp`) — see [llama.cpp local inference](llama-cpp.md#codex-launcher-codex-llama-cpp).

Amp remains lightly integrated: no SOP symlink, no MCP injection, no RTK hook, and `amp.dangerouslyAllowAll: true`. The `/agent-review` bridge uses only Amp's built-in `Task` tool and shared skills, so it adds no Amp-specific profile files or settings. If Amp comes back into regular rotation, wire it into `mcp_servers.yaml` injection and the SOP fan-out before adding deeper configuration.

## GitHub Copilot CLI

Source: [`home/dot_copilot/`](../../../home/dot_copilot/) → `~/.copilot/`. Installed as a Homebrew cask (`copilot-cli`, binary `copilot`, in [`brews/shared/39-applications-casks.brewfile`](../../../home/.chezmoitemplates/brews/shared/39-applications-casks.brewfile)); the cask auto-generates fish/zsh/bash completions, so no completion file is tracked. Copilot CLI uses the shared SOP, skills, session context, and worklog hooks, while Copilot-specific hook adapters live with the rest of the Copilot source under `home/dot_copilot/`.

| Surface            | Source                                                                                                         | Target                               |
| ------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| SOP / instructions | [`symlink_copilot-instructions.md`](../../../home/dot_copilot/symlink_copilot-instructions.md) → `~/AGENTS.md` | `~/.copilot/copilot-instructions.md` |
| Skills             | [`symlink_skills`](../../../home/dot_copilot/symlink_skills) → `~/.agents/skills`                              | `~/.copilot/skills`                  |
| Custom agents      | [`exact_agents/`](../../../home/dot_copilot/exact_agents/)                                                     | `~/.copilot/agents/`                 |
| MCP servers        | `mcp_servers.yaml` via `generate_mcp_configs.py copilot`                                                       | `~/.copilot/mcp-config.json`         |
| Hooks              | [`hooks.json`](../../../home/dot_copilot/hooks.json)                                                           | `~/.copilot/hooks/agent-memory.json` |
| Settings           | [`settings.json`](../../../home/dot_copilot/settings.json)                                                     | `~/.copilot/settings.json`           |

Key wiring decisions:

- **Instructions/skills are symlinks** (not copies): Copilot reads `$HOME/.copilot/copilot-instructions.md` as its global SOP and `~/.copilot/skills/<name>/SKILL.md` for skills. Copilot no longer reads `~/.claude/` agents/skills, so the explicit `~/.copilot/skills` symlink is required. The managed custom agents are thin `.agent.md` profiles that point back to the shared review skill; they exist only to give Copilot a runtime-native subagent surface and per-agent model settings.
- **MCP: stdio only; no OAuth HTTP server.** The `copilot` transform in `generate_mcp_configs.py` emits stdio servers as `type: "local"` and (when wired) OAuth HTTP servers as `type: "http"` with `oauthClientId` + `auth.redirectPort` + `oauthScopes` for Copilot's browser `authorization_code` flow. In practice no HTTP server is wired for Copilot: it hardcodes its OAuth redirect to `http://127.0.0.1:{port}/` (only the port is configurable), which neither the SCSI Okta app nor the public Slack client registers, so the flow is rejected (HTTP 400 / `redirect_uri did not match`). `scsi-main` and `slack` therefore omit a `copilot` `oauth_by_tool` block, and `scsi-local` carries `exclude_tools: [copilot]` (no point keeping the local SCSI backend once the hosted one is gone). With the always-on `sequentialthinking` server also removed from the registry, Copilot's generated `mcp-config.json` has an empty `mcpServers` and it relies solely on its built-in servers. The built-in `github-mcp-server` is provided by Copilot and is not emitted. See [MCP servers](mcp.md).
- **Settings are merged, not overwritten.** Copilot owns `~/.copilot/settings.json` and rewrites it at runtime (chosen `model`, `allowedUrls`, `config.json` migration), so the merge script deep-merges the declared baseline (`effortLevel: xhigh`, `keepAlive: busy`, `autoUpdate: false` to defer to the brew cask's auto-update, `banner: never`, `includeCoAuthoredBy: true`) **on top of** the live file with our keys winning, preserving the user's runtime choices. The target is in `.chezmoiignore`.
- **Hooks use PascalCase event names** (`SessionStart`, `PreToolUse`, `PostToolUse`) so Copilot delivers the VS Code-compatible snake_case payloads (`hook_event_name`, `session_id`, `tool_input`) that the shared session/worklog scripts already read — the same contract Codex uses. Copilot has no shell-gate hooks; PR review anchor verification is instruction-owned by the review/GitHub skills.

## Token optimization (RTK)

[RTK](https://github.com/rtk-ai/rtk) (`brew "rtk"`, added in [`brews/shared/38-ai-large-language-models.brewfile`](../../../home/.chezmoitemplates/brews/shared/38-ai-large-language-models.brewfile)) is a CLI proxy that compacts noisy command output (test runners, linters, `git log`/`git status`, build tools, …) to cut 60-90% of the tokens those outputs would otherwise consume. Each agent's pre-execution shell hook calls the native `rtk hook <agent>` binary, which rewrites a command like `git status` to `rtk git status` before it runs; `rtk` then filters the output. No `jq` or shell wrapper is needed — the binary reads the hook JSON and emits the rewrite itself.

**Per-agent wiring (all chezmoi-managed source):**

| Agent    | Source                                                                                        | Mechanism                                                                     |
| -------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Cursor   | [`home/dot_cursor/hooks.json`](../../../home/dot_cursor/hooks.json)                           | `preToolUse` entry `rtk hook cursor` (`matcher: "Shell"`)                     |
| Claude   | [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/)                  | `PreToolUse` block `rtk hook claude` (`matcher: "Bash"`)                      |
| Gemini   | [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json)                     | `BeforeTool` `run_shell_command`, `gemini-git-gate.sh` then `rtk hook gemini` |
| OpenCode | [`home/dot_config/opencode/plugins/rtk.ts`](../../../home/dot_config/opencode/plugins/rtk.ts) | `tool.execute.before` plugin calling `rtk rewrite`                            |
| Pi       | [`home/dot_pi/agent/extensions/rtk.ts`](../../../home/dot_pi/agent/extensions/rtk.ts)         | `tool_call` extension calling `rtk rewrite`                                   |
| Copilot  | _not wired_                                                                                   | fail-closed `PreToolUse` hooks must not depend on RTK for Copilot             |

Cursor and Gemini keep the git commit/push gate in front of RTK because those shells may otherwise rush mutating git operations. PR review anchor verification is handled by the review/GitHub skill instructions instead of a shell hook. Copilot is intentionally not wired to RTK: its `PreToolUse` hooks are fail-closed, and a failing output-compaction hook can block every bash call. Git commit/push protection for Copilot is instruction-based, not hook-based. RTK does not rewrite mutating git commands away from their gated form for the agents that still use it: `git commit`/`git push` map to `rtk git commit`/`rtk git push`, and both the Cursor matcher (`git\s+(commit|push)`) and the Gemini git gate (`git[[:space:]]+.*commit`) match that substring, so those gates still fire.

### RTK is a recoverable index, not a lossless substitute

Config: [`home/Library/Application Support/rtk/config.toml`](<../../../home/Library/Application Support/rtk/config.toml>) → `~/Library/Application Support/rtk/config.toml` (RTK reads `dirs::config_dir()/rtk/config.toml`; on macOS that is `~/Library/Application Support`, not XDG).

A full audit of RTK's filter surface classified every filter as one of:

| Class             | Meaning                                                            | Default handling   |
| ----------------- | ------------------------------------------------------------------ | ------------------ |
| SAFE              | Strips only boilerplate; no semantic loss                          | rewrite            |
| LOSSY-RECOVERABLE | Drops content but signals it (`+N more`, `[full output: <path>]`)  | rewrite + `tee`    |
| LOSSY-SILENT      | Drops semantically-relevant content with no count or recovery path | `exclude_commands` |

The config encodes that audit:

- `[hooks] exclude_commands = ["gh pr view", "gh pr checks", "git diff", "git show", "git log", "find", "grep", "rg"]`:
  - `gh pr view` / `gh pr checks` — the two audited **LOSSY-SILENT** commands (they field-subset the PR/check JSON with no overflow count).
  - `git diff` / `git show` — **policy** exclusions: these are recoverable (the diff filter prints `… (N lines truncated)` + `[full diff: rtk git diff --no-compact]`), but a truncated diff is never useful for review or judgment, so we never compact them. The word-boundary match (`^git\ diff($|\s)`) excludes `git diff --staged`/`git diff HEAD~1` but **not** `git diff-tree`/`git difftool`, which stay rewritten.
  - `git log` — audited **LOSSY-SILENT** (rtk 0.42.1, verified native-vs-rtk at scale): a bare `git log`/`git log --oneline` is silently capped at **50 commits with no overflow marker** (101 commits → shows 50 and stops, no `+N more`); an explicit `git log -N` overrides the cap. Silently truncating history can hide older relevant commits from review, same principle as the diff/show exclusion. (By contrast, `ls`/`read`/`tree`/`git status` were re-tested at 1000 files / 5000 lines / 40 modified and drop **nothing** — format-only compaction — so they stay rewritten.)
  - `find` / `grep` / `rg` — audited **LOSSY-SILENT/BROKEN** (rtk 0.42.1, verified by `rtk hook check` dry-run + live probe): RTK's `find` subcommand models only `-name`/`-type` and silently drops `-mindepth`/`-maxdepth`/`-print`/`-quit`/`-prune`/`-path` (different result set, no overflow marker); `grep`/`rg` both rewrite to `rtk grep`, whose `-l` means `--max-len` (collides with grep/rg's `-l` = `--files-with-matches`) and whose `--files-with-matches .` falls back to non-recursive system `grep` and errors `Is a directory`. All three overlap with the agent's native Grep/Glob tools (which bypass RTK), so excluding them costs zero measured savings (`rtk gain` attributes 0 tokens to any of them).
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
