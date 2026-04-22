# The Agentic Operating System (AI & Assistants)

Back: [`docs/categories/index.md`](index.md)

This setup does not just provide you with AI chat tools; it implements an **Agentic Operating System**. This treats "how my assistants should work" as strict, version-controlled configuration that is installed alongside everything else. The goal is deterministic, verifiable behavior instead of relying on unpredictable LLM heuristics.

## The Governance Layer (SOPs)

Entrypoints installed into your home directory:

| Source                                                                           | Target                | Notes                    |
| -------------------------------------------------------------------------------- | --------------------- | ------------------------ |
| [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md)                       | `~/AGENTS.md`         | Primary SOP              |
| [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md)                       | `~/CLAUDE.md`         | Claude-specific SOP      |
| [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md) | `~/.gemini/GEMINI.md` | Gemini-specific SOP      |
| [`home/dot_cursor/symlink_AGENTS.md`](../../home/dot_cursor/symlink_AGENTS.md)   | `~/.cursor/AGENTS.md` | Symlink to `~/AGENTS.md` |

These files are policy entrypoints; skills are installed separately.

Shared SOP handling rules:

- The entrypoints do not declare their own global instruction hierarchy. They define local SOP selection only: check the closest repo-local `AGENTS.md` first, then the broader home-level entrypoint, and defer to the runtime's higher-priority instruction layers when conflicts exist.
- "Questions" is scoped to information-seeking asks. Requests phrased as questions still count as action requests when the user is asking for investigation, verification, or edits.
- A mandatory compatibility gate runs before edits; see the SOP entrypoints for the exact classification, decision table, and summary-line format.
- If uncertainty remains after local inspection, probes, and any required skills, ask one direct fork-closing question.

Shared git push safety rule:

- If the user asks to push, agents must treat that as `git push --force-with-lease` (not plain `git push`).
- Agents must never auto-run `git pull`, `git pull --rebase`, `git rebase`, or `git merge` as a pre-push reconciliation step.
- If push is rejected due to divergence/non-fast-forward/lease checks, agents must stop and wait for explicit user direction.
- Canonical sources: [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md), [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md), and [`home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md`](../../home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md).

Shared runtime verification rule:

- For "is this correctly set up / working / actually being used" questions, the SOP now owns the canonical end-to-end verification rule, not just config inspection.
- Required chain: source config, rendered/applied config, runtime consumer, and a minimal safe live probe when one is possible.
- The shared rule is tracked in: [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md).

Shared behavioral disciplines (integrated from [`forrestchang/andrej-karpathy-skills`](https://github.com/forrestchang/andrej-karpathy-skills) without duplicating existing SOP rules):

- `2 Core Principles`: surface material assumptions and competing interpretations rather than picking silently (evidence-first from `2.1` still wins — probe locally before asking); push back when a simpler approach satisfies the stated goal.
- `3.3 Success Criteria & Verification Loops`: reframe imperative tasks as verifiable goals (test-first / reproducer-first when practical); multi-step plans must carry per-step verify checks; does not override `2.0`, `2.1`, `2.2`, or `5 Minimal edit scope`.
- `5 Code Quality`: simplicity discipline (no speculative abstractions/flexibility/impossible-scenario error handling; senior-engineer test); dead-code handling (remove only orphans your own changes created; mention, don't delete pre-existing dead code unless asked).
- Canonical sources: [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md).

## Skills Layout

All routable files live under `~/.agents/skills/`. Each skill folder contains a `SKILL.md` entrypoint (and optional `references/` for sub-modes).

Source of truth (this repo, chezmoi-managed):

- [`home/exact_dot_agents/exact_skills/`](../../home/exact_dot_agents/exact_skills/) -> `~/.agents/skills/`

Entry contract standard:

- Each skill should make four things obvious near the top: `Use when`, `Do not use`, `First actions`, and `Output`.
- The `description` frontmatter field is the primary routing signal — agents use it to decide whether to load the skill. Keep it concise, specific, and include non-obvious trigger words.
- Skills gated to specific repos (e.g. elastic-only) must state the constraint in the `description` so agents skip them early.
- The goal is to remove implied routing and implied next steps so the agent has less room to "remember roughly" and skip the file.

Current skills:

| Skill                   | Use when                                                                               | Gated to       |
| ----------------------- | -------------------------------------------------------------------------------------- | -------------- |
| `review`                | Reviewing changes, continuing a review, addressing threads, rechecking PR changes      |                |
| `github`                | Any GitHub mutation (PRs, issues, comments, reviews, labels, releases, merges)         |                |
| `git`                   | Any local git operation (branching, committing, pushing, rebasing, merging, conflicts) |                |
| `research`              | Investigating a third-party project/library/tool by cloning its GitHub repo            |                |
| `walkthrough`           | Explore codebase flows, map component relationships, render diagrams (manual only)     |                |
| `cli-skills`            | Creating or upgrading CLI tool skills                                                  |                |
| `semantic-code-search`  | Semantic search, base-branch context, or when another skill requires SCSI              |                |
| `google-workspace`      | Gmail / Drive / Calendar / Admin / Docs / Sheets via `gws` CLI                         |                |
| `worktrees`             | Create/switch/open/list/prune/remove worktrees via `,w`                                |                |
| `compose-pr`            | Drafting a PR title and body as text (before creating/editing a PR)                    |                |
| `compose-issue`         | Drafting an issue title and body as text (before creating/editing an issue)            |                |
| `buildkite`             | Checking build status, triggering builds, reading logs, debugging CI failures          | elastic org    |
| `kibana-labels-propose` | Proposing labels/backports/version targeting when composing or creating a Kibana PR    | elastic/kibana |
| `kibana-console-monaco` | Automating/testing the Kibana Dev Tools Console editor via Playwright                  | elastic/kibana |
| `playwriter`            | Controlling Chrome browser via Playwriter (explicit mention only)                      |                |
| `beads`                 | Persisting work in the beads DB (explicit mention of beads/bdlocal/BEADS_DIR only)     |                |
| `knip`                  | Finding unused files, dependencies, and exports in JS/TS projects                      |                |
| `jscpd`                 | Detecting duplicates during refactoring, code cleanup, or DRY improvement              |                |
| `improve-codebase`      | Suggest the single smartest addition to the current codebase                           |                |
| `improve-local`         | Suggest the single smartest addition to the local changes                              |                |
| `improve-branch`        | Suggest the single smartest addition for the current branch/PR/issue                   |                |

Always-on rule source:

- The SOP entrypoints are the only canonical always-on mechanism for assistant behavior.
- Do not encode mandatory every-prompt rules as skills; OpenCode skills are on-demand, not guaranteed every turn.
- Keep mandatory completeness and no-guessing rules in: [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md).

## Reviews: Base-Branch Context And Semantic Search

Review skills require comparing your local diff/PR against how base (usually `main`) works today.

If semantic code search (SCSI) is available and the current repo is indexed, it is required for base-branch context:

- Preflight is blocking: run `list_indices` first (do not guess an index; try both `scsi-main` and `scsi-local` when both exist).
- If the user provided an index name, still run `list_indices` and verify the index exists before using it.
- If the user did not provide an index name, use the single obvious repo-matching index from `list_indices`; ask only when multiple equally plausible matches remain after evidence-based filtering.
- Use SCSI results as base-branch context only; validate the actual change via local git diffs and file reads.

Review outputs also include a single reviewer-metadata line so it's obvious what was used for base context:

```text
Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD
```

Do not paste that line into GitHub comment bodies.

## Reviews: Truth Validation Loop

For non-trivial review decisions (accepting a suggestion, pushing back, or proposing an alternative), use a strict verify-first loop:

- Base truth: establish what base branch does today (SCSI when indexed; otherwise `git show <base>:<path>` + local search).
- Change truth: validate what your branch/PR actually does (local diff + file reads).
- Assumption tests: reproduce in `/tmp` when possible; otherwise run the smallest safe experiment in the worktree.
- Quality gates: if you changed code as part of an iteration cycle, re-run the repo's lint/type_check/tests trio (discover the correct commands from the repo; do not guess).

Skill support:

- Review modes live under `~/.agents/skills/review/references/`:
  - `shared_rules.md` — base-context gate, truth validation, coverage checklist, severity, draft style, posting boundary (loaded once by the router)
  - `pr_common.md` — PR resolution, media evidence, anchoring, deep links (loaded once for PR modes)
  - `local_changes.md` — local diff / branch delta review
  - `pr_review.md` — initial or continued PR review (batch or one-at-a-time)
  - `pr_fix.md` — address reviewer feedback (reply and/or code changes per thread)

## Reviews: Reply Style

When drafting PR thread replies:

- Do not use `RE:`.
- Default: reply directly; do not quote when the whole parent comment is the reference.
- If you need to point at a specific fragment, use a minimal blockquote (`> ...`) and then reply.
- A closing prompt like `Wdyt` is optional, not mandatory. Use it only when it fits the tone of the specific comment.

## Reviews: Router Behavior

- The review router selects exactly one of three modes: local changes, PR review, or PR fix (address feedback). Shared rules and PR-common setup are loaded once by the router, not duplicated per mode.
- When both a dirty working tree and a current-branch PR exist, the router asks which target to review instead of silently forcing local review first.
- GitHub posting stays outside read-only review mode until the user explicitly asks for a side effect.

## Source-First Research

- Explicit external repo-inspection requests now route to the same source-first skill instead of a separate variant.
- The research skill now requires: resolve repo/ref first, then inspect the checked out source locally.
- Source-first research now resolves the target ref before inspecting code.
- Use the default branch only for current/latest behavior questions.
- For version-, branch-, tag-, or commit-specific questions, inspect that exact ref instead of defaulting to latest upstream.

## Core Workflow: Change A Skill

1. Edit files under:

- [`home/exact_dot_agents/exact_skills/`](../../home/exact_dot_agents/exact_skills/)

1. Apply and verify:

```bash
chezmoi diff
chezmoi apply
ls -la ~/.agents/skills
```

## Tool Configs

### Cursor agent CLI

A cross-shell alias `agent` is provided for `cursor-agent`:

- POSIX interactive shells: [`home/readonly_dot_shellrc`](../../home/readonly_dot_shellrc) → `~/.shellrc`
- fish: [`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl) → `~/.config/fish/config.fish`

Verification:

```bash
command -v agent
agent --help
```

Tool configs included here:

| Tool        | Config source                                                                                                                |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/`](../../home/dot_claude/)                                                                                 |
| OpenCode    | [`home/dot_config/opencode/`](../../home/dot_config/opencode/)                                                               |
| Codex       | [`home/dot_codex/`](../../home/dot_codex/)                                                                                   |
| Amp         | [`home/dot_config/exact_amp/private_readonly_settings.json`](../../home/dot_config/exact_amp/private_readonly_settings.json) |
| Gemini CLI  | [`home/dot_gemini/`](../../home/dot_gemini/)                                                                                 |

### Profile-based file merging

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk target and a `run_onchange` script writes the correct profile-specific version from the repo source.

Instead of keeping complex templates or comment-based filtering logic, we use explicit `.work.*` and `.personal.*` files. The shell script checks the `.isWork` template variable and copies the correct source to the final destination, completely decoupling the formats.

| Tool                 | Source files                                                                                                                                   | Target                               | Merge script                                               |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Claude Code settings | [`home/dot_claude/settings.{work,personal}.json`](../../home/dot_claude/settings.{work,personal}.json)                                         | `~/.claude/settings.json`            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Claude Code MCP      | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.claude.json` (mcpServers field)  | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Cursor MCP           | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.cursor/mcp.json`                 | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Gemini settings+MCP  | [`home/dot_gemini/settings.json`](../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml)        | `~/.gemini/settings.json`            | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config      | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc)   | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| OpenCode MCP         | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config         | [`home/dot_codex/private_config.{work,personal}.toml`](../../home/dot_codex/private_config.{work,personal}.toml)                               | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Codex MCP            | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi MCP               | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.pi/agent/mcp.json`               | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Pi settings/models   | [`home/dot_pi/agent/readonly_{settings,models}.{work,personal}.json`](../../home/dot_pi/agent/readonly_{settings,models}.{work,personal}.json) | `~/.pi/agent/{settings,models}.json` | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |
| oMLX settings        | [`home/dot_omlx/settings.json`](../../home/dot_omlx/settings.json)                                                                             | `~/.omlx/settings.json`              | `run_onchange_after_07-merge-omlx-settings.sh.tmpl`        |

All merge scripts live under [`home/.chezmoiscripts/`](../../home/.chezmoiscripts/). Pi targets are installed readonly.

### Claude Code settings

Source: [`home/dot_claude/settings.{work,personal}.json`](../../home/dot_claude/settings.{work,personal}.json) → `~/.claude/settings.json`.

Both profiles enable extended thinking and skip the dangerous-mode permission prompt. The work profile uses native Claude enterprise auth by default (no `apiKeyHelper` or `ANTHROPIC_BASE_URL` override).

MCP servers are stored separately in `~/.claude.json` (top-level `mcpServers` field) because that file contains runtime state managed by Claude Code. The merge script surgically updates only the `mcpServers` key, leaving other fields intact.

Work MCP servers: sequentialthinking, scsi-main, scsi-local. Personal MCP servers: sequentialthinking.

### Gemini CLI settings

Source: [`home/dot_gemini/settings.json`](../../home/dot_gemini/settings.json) → `~/.gemini/settings.json`.

- MCP servers are injected from the shared [`mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) registry at apply time (no longer hardcoded in the settings file).
- Tool approval is controlled by `general.defaultApprovalMode` (we use `auto_edit` to auto-approve edit tools).

### Pi coding agent settings

**Installation:** Pi globals are installed via npm from [`home/readonly_dot_default-npm-pkgs`](../../home/readonly_dot_default-npm-pkgs) → `~/.default-npm-pkgs`:

| Package                         | Purpose               |
| ------------------------------- | --------------------- |
| `@mariozechner/pi-coding-agent` | Core Pi agent         |
| `@mariozechner/pi-tui`          | Pi TUI (work profile) |
| `pi-mcp-adapter`                | MCP adapter extension |

**Config sources:**

| Config            | Source                                                                                                                                                          |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Settings + models | [`home/dot_pi/agent/readonly_{settings,models}.{work,personal}.json`](../../home/dot_pi/agent/readonly_{settings,models}.{work,personal}.json) → `~/.pi/agent/` |
| MCP servers       | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry) → `~/.pi/agent/mcp.json`                                     |

**Profile defaults:**

| Profile  | Default provider | Default model                        |
| -------- | ---------------- | ------------------------------------ |
| Work     | `google`         | `gemini-3.1-pro-preview-customtools` |
| Personal | `google`         | `gemini-3.1-pro-preview-customtools` |

Work profile also exposes additional configured models alongside the Google direct default.

**Shared settings:**

- Automatic context compaction (saves tokens)
- Exponential backoff retries
- `npm:pi-mcp-adapter` extension auto-installed (kept in npm convergence list)
- Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) are picked up from environment variables exported via `pass` in `config.fish.tmpl`

#### LiteLLM integration (work profile)

Fish exports these values from `pass` when the entries exist:

| Variable            | Pass path           | Notes                      |
| ------------------- | ------------------- | -------------------------- |
| `LITELLM_PROXY_KEY` | `litellm/api/token` | API authentication         |
| `LITELLM_API_BASE`  | `litellm/api/base`  | Normalized to end in `/v1` |

**OpenCode specifics:** The work config ([`home/dot_config/opencode/readonly_opencode.work.jsonc`](../../home/dot_config/opencode/readonly_opencode.work.jsonc)) uses Google direct Gemini as the primary default now.

- Main agent default: `google/gemini-3.1-pro-preview-customtools`
- Additional LiteLLM aliases may still be available for explicit selection.

**Pi specifics:** The work config is rendered by `run_onchange_after_07-merge-pi-config.sh.tmpl` into `~/.pi/agent/`.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

Verification:

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime.

## Ollama

This setup includes a hook that pulls a small list of models:

- [`home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh`](../../home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh)

Environment tuning for Ollama lives in:

- [`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl)

Workflow:

```bash
chezmoi apply
ollama list
```

## oMLX (Apple Silicon MLX inference server)

[oMLX](https://github.com/jundot/omlx) is an LLM inference server optimized for Apple Silicon, with continuous batching, a tiered (RAM + SSD) KV cache, and native TurboQuant / oQ quantization. It is the primary local-agentic-coding backend on Apple Silicon hosts.

### Install

`omlx` and the official Hugging Face CLI (`hf`) are installed via Homebrew:

- [`home/readonly_dot_Brewfile.tmpl`](../../home/readonly_dot_Brewfile.tmpl) — AI & LARGE LANGUAGE MODELS section

```ruby
tap "jundot/omlx", "https://github.com/jundot/omlx"
brew "jundot/omlx/omlx"
brew "hf"
```

### Model manifest

The curated model list is declared as a chezmoi-templated manifest:

- [`home/readonly_dot_default-omlx-models.tmpl`](../../home/readonly_dot_default-omlx-models.tmpl)

The manifest is 4-bit by default on every Apple Silicon host. Personal hosts (`isWork=false`) additionally pull the Qwen 6-bit quality tier; work hosts skip it because its ~27 GB weights exceed the 25 GB default weights budget before any KV cache is allocated. 4-bit favors long-context KV cache headroom (and faster per-token inference) over quantization fidelity, which is the more useful tradeoff for agentic coding.

Format (pipe-delimited):

```text
<hf-repo-id>|<local-dir-name>
```

- `hf-repo-id` — Hugging Face repo id (e.g. `mlx-community/Qwen3.6-35B-A3B-4bit`).
- `local-dir-name` — subdirectory under `~/.omlx/models/` where the weights land.

### Sync hook (opt-in)

Downloads are gated by `downloadOmlxModels` in `~/.config/chezmoi/chezmoi.toml`. Default is `false`, so `chezmoi apply` never auto-downloads multi-GB weights unless explicitly enabled. To change the setting, re-run `chezmoi init`.

The sync hook is a thin shell orchestrator that delegates parse + skip + download logic to a Python helper:

- [`home/.chezmoiscripts/run_onchange_after_07-sync-omlx-models.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-sync-omlx-models.sh.tmpl)
- [`scripts/sync_omlx_models.py`](../../scripts/sync_omlx_models.py)

The helper treats a model directory as "complete" if it contains `config.json` and at least one `*.safetensors` shard, so re-runs are idempotent.

Override the model root with `OMLX_MODELS_ROOT` (defaults to `~/.omlx/models`).

Workflow:

```bash
chezmoi init  # (once) prompts for downloadOmlxModels
chezmoi apply # syncs models when gate is true
omlx serve
```

Add a model: [`docs/recipes/add-an-omlx-model.md`](../recipes/add-an-omlx-model.md).

### Server settings

oMLX's server-side prompt/output caps are declared as a partial override and deep-merged into `~/.omlx/settings.json` on every apply:

- Source: [`home/dot_omlx/settings.json`](../../home/dot_omlx/settings.json) (only the keys we own)
- Helper: [`scripts/merge_omlx_settings.py`](../../scripts/merge_omlx_settings.py) (stdlib-only deep merge)
- Hook: [`home/.chezmoiscripts/run_onchange_after_07-merge-omlx-settings.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-omlx-settings.sh.tmpl)

The merge preserves everything oMLX writes itself (`auth.secret_key`, `server.server_aliases`, `model.model_dirs`, etc.) and only updates the keys present in the source. The real target is listed in [`home/.chezmoiignore`](../../home/.chezmoiignore) so chezmoi never deploys the partial source as the full settings file.

The shipped default raises `sampling.max_context_window` and `sampling.max_tokens` to 262144 — the full native trained context of the Qwen3.6 (6-bit) and Gemma-4 checkpoints in the manifest (`rope_scaling.type: "default"`, not YaRN-extrapolated, so retrieval quality holds across the whole range). With aggressive GQA (`num_key_value_heads: 2`, `head_dim: 256`) the FP16 KV cache sits around 80 KB/token, so a fully-populated 262144-token cache is ~20 GB — fits alongside the 6-bit Qwen weights under the personal profile's `max_model_memory` budget. Work-profile hosts (36 GB, 4-bit models only) will spill long-context KV to oMLX's paged SSD cache; lower this value or enable per-model TurboQuant KV if prefill latency becomes a concern there.

If `~/.omlx/settings.json` does not exist yet (fresh install, oMLX never started), the merge is a no-op with a hint. Start the service once (`brew services start jundot/omlx/omlx`) so oMLX writes its defaults + generates `auth.secret_key`, then re-run `chezmoi apply` to layer the overrides. After changing the source, `brew services restart jundot/omlx/omlx` to pick up the new values (oMLX loads settings at startup).

Verify live:

```bash
curl -s http://localhost:8000/v1/models/status | python3 -m json.tool | rg max_context_window
```

### Fish completions

- [`home/dot_config/fish/completions/readonly_omlx.fish`](../../home/dot_config/fish/completions/readonly_omlx.fish)

Tab-completes `omlx <subcommand>`, `omlx launch <tool>`, and model ids for `--model` / `--pin`. Model names are the union (deduped by id) of the running server (`GET /v1/models`) and a filesystem scan of `${OMLX_MODELS_ROOT:-$HOME/.omlx/models}` (same root used by the sync hook). Unioning matters because oMLX only scans the models directory at server startup — a model downloaded after `omlx serve` launched won't appear in `/v1/models` until the server is restarted, but completion still surfaces it from disk. `OMLX_HOST` / `OMLX_PORT` override the defaults (`127.0.0.1:8000`) for the live query.

### Model-level control plane (`,omlx`)

oMLX's CLI only exposes `serve`, `launch`, `diagnose` — no model-level control. This repo ships a thin umbrella wrapping the public HTTP API:

- [`home/exact_bin/executable_,omlx`](../../home/exact_bin/executable_,omlx) → `~/bin/,omlx`
- [`home/dot_config/fish/completions/readonly_,omlx.fish`](../../home/dot_config/fish/completions/readonly_,omlx.fish) — context-aware subcommand + model-id completions

Daemon lifecycle is NOT in scope (that's `brew services start|stop|restart jundot/omlx/omlx`). Subcommands:

```bash
,omlx status                          # loaded/unloaded state, memory, budget
,omlx load <model-id> [<id> ...]      # lazy-load via /v1/chat/completions
,omlx unload <model-id> [<id> ...]    # POST /v1/models/<id>/unload
,omlx unload --all                    # unload everything currently loaded
```

`unload` hits `POST /v1/models/<id>/unload`, which runs `mx.synchronize()` + `mx.clear_cache()` server-side so Metal buffers actually release (not just the accounting). `load` has no public endpoint (the admin one requires a session cookie), so we trigger a lazy-load with a `max_tokens=1` chat completion against the target id.

`status` and `load` union the server registry with a scan of `${OMLX_MODELS_ROOT:-~/.omlx/models}` (any subdir with a `config.json` counts, same definition as the sync script). oMLX only registers on-disk models at startup via `engine_pool.discover_models()`, so a model downloaded after `omlx serve` launched stays invisible to the server until it restarts. Both surfaces handle that explicitly:

- `,omlx status` prints three states — `✓ loaded`, `· on disk`, `? on disk, not discovered` — and appends a footer telling you to `brew services restart jundot/omlx/omlx` if any `?` rows exist.
- `,omlx load <id>` pre-checks against the registry; if the id is only on disk, it refuses the warmup and prints the same restart hint instead of firing a warmup that would 404.

Completion follows the same model. `,omlx load <TAB>` offers the union (server-unloaded + disk-only, with distinct descriptions); `,omlx unload <TAB>` stays server-loaded-only because "loaded" is a server-only state.

Respects `OMLX_HOST` / `OMLX_PORT` / `OMLX_API_KEY` / `OMLX_MODELS_ROOT` (defaults: `127.0.0.1:8000`, no auth header unless `OMLX_API_KEY` is set, disk scan under `~/.omlx/models`).

### Claude Code launcher (`,claude-omlx`)

Claude Code compacts conversation history at `autoCompactWindow` tokens (schema min 100000, max 1000000). Cloud `opus[1m]` sessions benefit from leaving this at the default (~1M). Local oMLX sessions need it below the server's `sampling.max_context_window` (262144) so Claude Code compacts before oMLX would reject the prompt. Those two needs conflict on a single global value.

Solution: a dedicated omlx-scoped settings file loaded via `claude --settings <file>` (layers additively on top of `~/.claude/settings.json` — see `claude --help`), wired through a thin wrapper.

- [`home/dot_claude/settings.omlx.json`](../../home/dot_claude/settings.omlx.json) → `~/.claude/settings.omlx.json` (contains only `autoCompactWindow: 200000`)
- [`home/exact_bin/executable_,claude-omlx`](../../home/exact_bin/executable_,claude-omlx) → `~/bin/,claude-omlx`

The wrapper exports `ANTHROPIC_BASE_URL=http://${OMLX_HOST:-127.0.0.1}:${OMLX_PORT:-8000}`, forces `ANTHROPIC_API_KEY=$OMLX_API_KEY` (empty by default — oMLX accepts unauthenticated local requests unless `auth.api_key_set` is true), and invokes `claude --settings ~/.claude/settings.omlx.json --model "$CLAUDE_OMLX_MODEL" "$@"`.

Environment overrides:

| Variable               | Default                            | Purpose                                                             |
| ---------------------- | ---------------------------------- | ------------------------------------------------------------------- |
| `OMLX_HOST`            | `127.0.0.1`                        | Same as `,omlx` / `omlx` CLI                                        |
| `OMLX_PORT`            | `8000`                             | Same as `,omlx` / `omlx` CLI                                        |
| `OMLX_API_KEY`         | empty                              | Sent as `ANTHROPIC_API_KEY` (Claude Code uses this for bearer auth) |
| `CLAUDE_OMLX_MODEL`    | `qwen3.6-abliterated-heretic-6bit` | Set empty to skip `--model` injection                               |
| `CLAUDE_OMLX_SETTINGS` | `$HOME/.claude/settings.omlx.json` | Point at an alternate omlx settings file                            |

`autoCompactWindow=200000` leaves ~62k headroom under the 262144-token server cap for the next turn's prompt, tool outputs, and model reply. Note that auto-compact summarizes multi-turn **history** between turns — it does not shrink a single oversized tool output in the current turn. That scenario (e.g. a directory listing that emits 30k+ tokens) is handled purely by the raised server cap in `home/dot_omlx/settings.json`.

Usage:

```bash
,claude-omlx                                  # interactive session, default model
,claude-omlx -p "summarize README.md"         # one-shot prompt
CLAUDE_OMLX_MODEL=other-local-model ,claude-omlx
```

Cloud Claude sessions are unaffected — plain `claude ...` still reads only `~/.claude/settings.json`, where `autoCompactWindow` stays unset so the default for `opus[1m]` applies.

## Reviewing Agent Diffs (`tuicr`)

[`tuicr`](https://github.com/agavra/tuicr) is the user-facing half of the agent loop: after the agent edits the working tree, you review the diff in a GitHub-style TUI, drop line/file/review comments, and export them as structured markdown that pastes back to the agent for a one-pass fix. It's the inverse of the `review` skill (which is the agent reviewing your diff).

Install: [`home/readonly_dot_Brewfile.tmpl`](../../home/readonly_dot_Brewfile.tmpl) — `AI & LARGE LANGUAGE MODELS` section, via the `agavra/tap` Homebrew tap.

Config (theme + comment-type vocabulary): [`home/dot_config/tuicr/readonly_config.toml`](../../home/dot_config/tuicr/readonly_config.toml) → `~/.config/tuicr/config.toml`. Comment types are actionable categories (`issue`, `suggestion`, `question`, `nit`, `praise`); severity (CRITICAL/HIGH/MEDIUM/LOW from the review SOP) stays internal and is intentionally not encoded as a comment type.

Loop (invoke `tuicr` directly — no wrapper):

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

## Beads (Task Tracking)

Beads is integrated as a CLI (`bd`) with a repo-aware wrapper command:

- Wrapper function: `bdlocal` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl)

The wrapper chooses a per-repo `$BEADS_DIR` under `~/beads-data/` and pins the Beads discovery anchor to `$BEADS_DIR/.beads/beads.db`, then runs `bd` in `--sandbox` mode (per-project Dolt SQL server backend).

Verification:

```bash
echo "$BEADS_DIR"
bdlocal status
```

## Safety Boundaries

- Keep assistant instructions declarative and repo-local.
- Keep secrets in `pass` (or local private config), not in tracked markdown.
- Validate generated automation commands before running state-changing actions.

## Verification And Troubleshooting

High-signal checks:

```bash
chezmoi diff
chezmoi apply
ls -la ~/.agents/skills
```

If assistant behavior is not picking up expected instructions:

- verify the correct entrypoint file exists in `$HOME` (`~/AGENTS.md`, `~/CLAUDE.md`, `~/.gemini/GEMINI.md`).
- verify skill files exist under `~/.agents/skills/`.
- verify secrets expected at runtime are present in `pass`.

## Related

- Beads task tracking: [`docs/recipes/beads-task-tracking.md`](../recipes/beads-task-tracking.md)
- Switching work/personal identity: [`docs/recipes/switching-work-personal-identity.md`](../recipes/switching-work-personal-identity.md)
- Security and secrets: [`docs/categories/security-and-secrets.md`](security-and-secrets.md)
