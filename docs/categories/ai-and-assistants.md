# The Agentic Operating System (AI & Assistants)

Back: [`docs/categories/index.md`](index.md)

This setup does not just provide you with AI chat tools; it implements an
**Agentic Operating System**. This treats "how my assistants should work" as
strict, version-controlled configuration that is installed alongside everything
else. The goal is deterministic, verifiable behavior instead of relying on
unpredictable LLM heuristics.

## The Governance Layer (SOPs)

Entrypoints installed into your home directory:

| Source                                                                           | Target                | Notes                    |
| -------------------------------------------------------------------------------- | --------------------- | ------------------------ |
| [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md)                       | `~/AGENTS.md`         | Primary SOP              |
| [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md)                       | `~/CLAUDE.md`         | Claude-specific SOP      |
| [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md) | `~/.gemini/GEMINI.md` | Gemini-specific SOP      |
| [`home/dot_cursor/symlink_AGENTS.md`](../../home/dot_cursor/symlink_AGENTS.md)   | `~/.cursor/AGENTS.md` | Symlink to `~/AGENTS.md` |

These files are policy entrypoints; playbooks and skills are installed
separately.

Shared SOP handling rules:

- The entrypoints do not declare their own global instruction hierarchy. They
  define local SOP selection only: check the closest repo-local `AGENTS.md`
  first, then the broader home-level entrypoint, and defer to the runtime's
  higher-priority instruction layers when conflicts exist.
- "Questions" is scoped to information-seeking asks. Requests phrased as
  questions still count as action requests when the user is asking for
  investigation, verification, or edits.
- A mandatory compatibility gate runs before edits; see the SOP entrypoints for
  the exact classification, decision table, and summary-line format.
- If uncertainty remains after local inspection, probes, and any required
  playbooks or skills, ask one direct fork-closing question.

Shared git push safety rule:

- If the user asks to push, agents must treat that as
  `git push --force-with-lease` (not plain `git push`).
- Agents must never auto-run `git pull`, `git pull --rebase`, `git rebase`, or
  `git merge` as a pre-push reconciliation step.
- If push is rejected due to divergence/non-fast-forward/lease checks, agents
  must stop and wait for explicit user direction.
- Canonical sources: [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md),
  [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md),
  [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md),
  and
  [`home/exact_dot_agents/exact_playbooks/exact_git/readonly_PLAYBOOK.md`](../../home/exact_dot_agents/exact_playbooks/exact_git/readonly_PLAYBOOK.md).

Shared runtime verification rule:

- For "is this correctly set up / working / actually being used" questions, the
  SOP now owns the canonical end-to-end verification rule, not just config
  inspection.
- Required chain: source config, rendered/applied config, runtime consumer, and
  a minimal safe live probe when one is possible.
- The shared rule is tracked in:
  [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md),
  [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md), and
  [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md).

Shared SOP routing rules:

- Routed playbooks and skills are binding procedures, not optional reference
  material.
- A request must have exactly one primary route. Secondary files load only when
  the primary requires them or the user explicitly asks for the cross-boundary
  action.
- Review stays primary for PR review/recheck/reply flows even when the final
  step is posting to GitHub.
- Draft-only GitHub composition is its own route. The `gh` playbook loads the
  compose skill before creating/editing PR or issue text.
- Semantic-code-search routing also covers explicit index-selection language
  such as "use `<index>` index" or "which index should we use?".
- Google Workspace requests route to
  `~/.agents/skills/google_workspace/SKILL.md`.
- Source file:
  [`home/exact_dot_agents/exact_skills/exact_google_workspace/readonly_SKILL.md`](../../home/exact_dot_agents/exact_skills/exact_google_workspace/readonly_SKILL.md)
- The skill standardizes on `gws`, using `gws schema ...` before direct
  `gws <service> ...` calls.
- Source-first research now also covers explicit external repo-inspection
  requests when the user provides GitHub/GitLab repo URLs or asks to inspect
  repo pages/files/directories directly.
- The required order is GitHub/ref resolution first, then local source
  inspection at that exact ref. Raw content URLs or repo APIs are not the first
  inspection surface.
- It is still not the default for the current repo.
- This routing is referenced from the tracked SOP entrypoints:
  [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md),
  [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md), and
  [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md).

## Playbooks & Skills Layout

Two kinds of routable files live under `~/.agents/`:

- **Playbooks** (`~/.agents/playbooks/`): Multi-step workflow orchestration.
  Each folder has a `PLAYBOOK.md` entrypoint (plus optional sub-mode files).
- **Skills** (`~/.agents/skills/`): Self-contained tool or integration
  capabilities. Each folder has a `SKILL.md` entrypoint.

Source of truth (this repo, chezmoi-managed):

- [`home/exact_dot_agents/exact_playbooks/`](../../home/exact_dot_agents/exact_playbooks/)
  -> `~/.agents/playbooks/`
- [`home/exact_dot_agents/exact_skills/`](../../home/exact_dot_agents/exact_skills/)
  -> `~/.agents/skills/`

Entry contract standard:

- Each playbook or skill should make four things obvious near the top:
  `Use when`, `Do not use`, `First actions`, and `Output`.
- The goal is to remove implied routing and implied next steps so the agent has
  less room to "remember roughly" and skip the file.
- The shared SOP trigger list should also carry the high-signal routing nuance
  that changes behavior, for example: propose-only vs apply, current repo vs
  external repo, read-only review vs GitHub posting, `gws`-supported tasks, and
  `,w` over raw `git worktree`.

Current playbooks:

| Playbook       | Use when                                                                    |
| -------------- | --------------------------------------------------------------------------- |
| `review`       | Review local changes or PR (start, iterative, reply, change-cycle modes)    |
| `github`       | GitHub side effects (create/edit PRs/issues, post comments, apply metadata) |
| `git`          | Local git operations (status, diff, log, staging, commit, rebase/merge)     |
| `research`     | Investigate external/public codebases (source-first clone + grep)           |
| `architecture` | Walk through a system, explain flows, or build a diagram/mental model       |

Current skills:

| Skill                   | Use when                                                                 |
| ----------------------- | ------------------------------------------------------------------------ |
| `semantic-code-search`  | Semantic investigation via SCSI tools (symbol analysis, index selection) |
| `google-workspace`      | Gmail / Drive / Calendar / Admin / Docs / Sheets via `gws`               |
| `worktrees`             | Create/switch/open/list/prune/remove worktrees via `,w`                  |
| `compose-pr`            | Draft PR description text only (no `gh` side effects)                    |
| `compose-issue`         | Draft issue text only (no `gh` side effects)                             |
| `kibana-labels-propose` | Propose labels/backports/version targeting for elastic/kibana            |
| `kibana`                | CODEOWNERS / ownership / reviewer guidance for elastic/kibana            |
| `kibana-console-monaco` | Automate/test Kibana Dev Tools Console editor via Playwright             |
| `playwriter`            | Control the user's Chrome browser via Playwriter extension               |
| `beads`                 | Inspect/create/claim/update/close/export beads in the beads DB           |
| `improve-codebase`      | Suggest the single smartest addition to the current codebase             |
| `improve-local`         | Suggest the single smartest addition to the local changes                |
| `improve-branch`        | Suggest the single smartest addition for the current branch/PR/issue     |

Always-on rule source:

- The SOP entrypoints are the only canonical always-on mechanism for assistant
  behavior.
- Do not encode mandatory every-prompt rules as skills; OpenCode skills are
  on-demand, not guaranteed every turn.
- Keep mandatory completeness and no-guessing rules in:
  [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md),
  [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md), and
  [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md).

## Reviews: Base-Branch Context And Semantic Search

Review playbooks require comparing your local diff/PR against how base (usually
`main`) works today.

If semantic code search (SCSI) is available and the current repo is indexed, it
is required for base-branch context:

- Preflight is blocking: run `list_indices` first (do not guess an index; try
  both `scsi-main` and `scsi-local` when both exist).
- If the user provided an index name, still run `list_indices` and verify the
  index exists before using it.
- If the user did not provide an index name, use the single obvious
  repo-matching index from `list_indices`; ask only when multiple equally
  plausible matches remain after evidence-based filtering.
- Use SCSI results as base-branch context only; validate the actual change via
  local git diffs and file reads.

Review outputs also include a single reviewer-metadata line so it's obvious what
was used for base context:

```text
Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD
```

Do not paste that line into GitHub comment bodies.

## Reviews: Truth Validation Loop

For non-trivial review decisions (accepting a suggestion, pushing back, or
proposing an alternative), use a strict verify-first loop:

- Base truth: establish what base branch does today (SCSI when indexed;
  otherwise `git show <base>:<path>` + local search).
- Change truth: validate what your branch/PR actually does (local diff + file
  reads).
- Assumption tests: reproduce in `/tmp` when possible; otherwise run the
  smallest safe experiment in the worktree.
- Quality gates: if you changed code as part of an iteration cycle, re-run the
  repo's lint/type_check/tests trio (discover the correct commands from the
  repo; do not guess).

Playbook support:

- Draft-only review modes live under `~/.agents/playbooks/review/`.
- If you want to apply requested changes one thread/comment at a time (with
  verification after each cycle), use:
  - `~/.agents/playbooks/review/pr_change_cycle.md` (loaded by the review
    `PLAYBOOK.md` router)

## Reviews: Reply Style

When drafting PR thread replies:

- Do not use `RE:`.
- Default: reply directly; do not quote when the whole parent comment is the
  reference.
- If you need to point at a specific fragment, use a minimal blockquote
  (`> ...`) and then reply.
- A closing prompt like `Wdyt` is optional, not mandatory. Use it only when it
  fits the tone of the specific comment.

## Reviews: Router Behavior

- The review router selects exactly one primary review mode, then loads
  secondary playbooks or skills only when required by that mode.
- When both a dirty working tree and a current-branch PR exist, the router now
  asks which target to review instead of silently forcing local review first.
- GitHub posting stays outside read-only review mode until the user explicitly
  asks for a side effect.

## Source-First Research

- Explicit external repo-inspection requests now route to the same source-first
  playbook instead of a separate variant.
- The research playbook now requires: resolve repo/ref first, then inspect the
  checked out source locally.
- Source-first research now resolves the target ref before inspecting code.
- Use the default branch only for current/latest behavior questions.
- For version-, branch-, tag-, or commit-specific questions, inspect that exact
  ref instead of defaulting to latest upstream.

## Core Workflow: Change A Playbook Or Skill

1. Edit files under:

- [`home/exact_dot_agents/exact_playbooks/`](../../home/exact_dot_agents/exact_playbooks/)
  (playbooks)
- [`home/exact_dot_agents/exact_skills/`](../../home/exact_dot_agents/exact_skills/)
  (skills)

2. Apply and verify:

```bash
chezmoi diff
chezmoi apply
ls -la ~/.agents/playbooks ~/.agents/skills
```

## Tool Configs

### Cursor agent CLI

A cross-shell alias `agent` is provided for `cursor-agent`:

- POSIX interactive shells:
  [`home/readonly_dot_shellrc`](../../home/readonly_dot_shellrc) → `~/.shellrc`
- fish:
  [`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl)
  → `~/.config/fish/config.fish`

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

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk
target and a `run_onchange` script writes the correct profile-specific version
from the repo source.

Instead of keeping complex templates or comment-based filtering logic, we use
explicit `.work.*` and `.personal.*` files. The shell script checks the
`.isWork` template variable and copies the correct source to the final
destination, completely decoupling the formats.

| Tool                 | Source files                                                                                                                                   | Target                               | Merge script                                               |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Claude Code settings | [`home/dot_claude/settings.{work,personal}.json`](../../home/dot_claude/settings.{work,personal}.json)                                         | `~/.claude/settings.json`            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Claude Code MCP      | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.claude.json` (mcpServers field)  | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Cursor MCP           | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.cursor/mcp.json`                 | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Gemini settings+MCP  | [`home/dot_gemini/settings.json`](../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml)        | `~/.gemini/settings.json`            | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config      | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc)   | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config         | [`home/dot_codex/private_config.{work,personal}.toml`](../../home/dot_codex/private_config.{work,personal}.toml)                               | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi MCP               | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                             | `~/.pi/agent/mcp.json`               | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Pi settings/models   | [`home/dot_pi/agent/readonly_{settings,models}.{work,personal}.json`](../../home/dot_pi/agent/readonly_{settings,models}.{work,personal}.json) | `~/.pi/agent/{settings,models}.json` | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |

All merge scripts live under
[`home/.chezmoiscripts/`](../../home/.chezmoiscripts/). Pi targets are installed
readonly.

### Claude Code installation and context window patch

Claude Code is installed via npm (`@anthropic-ai/claude-code` in
[`home/readonly_dot_default-npm-pkgs`](../../home/readonly_dot_default-npm-pkgs))
instead of the Homebrew cask. The npm package contains raw `cli.js` which can be
patched, unlike the compiled Homebrew binary. The brew cask is commented out in
the Brewfile.

A post-install patch
([`home/exact_bin/executable_,patch-claude-code`](../../home/exact_bin/executable_,patch-claude-code))
modifies `cli.js` so the context window default (hardcoded to 200k) reads from
the `CLAUDE_CODE_CONTEXT_WINDOW` env var. This allows third-party models routed
through LLM gateways (e.g. Gemini with 1M context) to use their native window
size instead of being capped at 200k.

The patch is re-applied automatically by a post-install hook in
[`home/exact_bin/executable_,install-npm-pkgs`](../../home/exact_bin/executable_,install-npm-pkgs)
— it runs `,patch-claude-code` after every npm sync, but only when
`@anthropic-ai/claude-code` is in the desired packages list.

Usage:
`CLAUDE_CODE_CONTEXT_WINDOW=1000000 claude --model gemini-3.1-pro-preview-customtools`

The model catalog is defined in a single source of truth:
[`home/.chezmoidata/litellm_models.yaml`](../../home/.chezmoidata/litellm_models.yaml).
Consumer configs (OpenCode, Pi) are generated from this catalog via chezmoi
templates. To add or modify a model, edit the YAML file only.

### Claude Code settings

Source:
[`home/dot_claude/settings.{work,personal}.json`](../../home/dot_claude/settings.{work,personal}.json)
→ `~/.claude/settings.json`.

Both profiles enable extended thinking and skip the dangerous-mode permission
prompt. The work profile uses native Claude enterprise auth by default (no
`apiKeyHelper` or `ANTHROPIC_BASE_URL` override).

MCP servers are stored separately in `~/.claude.json` (top-level `mcpServers`
field) because that file contains runtime state managed by Claude Code. The
merge script surgically updates only the `mcpServers` key, leaving other fields
intact.

Work MCP servers: sequentialthinking, scsi-main, scsi-local. Personal MCP
servers: sequentialthinking.

### Gemini CLI settings

Source: [`home/dot_gemini/settings.json`](../../home/dot_gemini/settings.json) →
`~/.gemini/settings.json`.

- MCP servers are injected from the shared
  [`mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml) registry at
  apply time (no longer hardcoded in the settings file).
- Tool approval is controlled by `general.defaultApprovalMode` (we use
  `auto_edit` to auto-approve edit tools).

### Pi coding agent settings

**Installation:** Pi globals are installed via npm from
[`home/readonly_dot_default-npm-pkgs`](../../home/readonly_dot_default-npm-pkgs)
→ `~/.default-npm-pkgs`:

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

Work profile also exposes additional configured models alongside the Google
direct default.

**Shared settings:**

- Automatic context compaction (saves tokens)
- Exponential backoff retries
- `npm:pi-mcp-adapter` extension auto-installed (kept in npm convergence list)
- Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`,
  `OPENROUTER_API_KEY`) are picked up from environment variables exported via
  `pass` in `config.fish.tmpl`

#### LiteLLM integration (work profile)

Fish exports these values from `pass` when the entries exist:

| Variable            | Pass path           | Notes                      |
| ------------------- | ------------------- | -------------------------- |
| `LITELLM_PROXY_KEY` | `litellm/api/token` | API authentication         |
| `LITELLM_API_BASE`  | `litellm/api/base`  | Normalized to end in `/v1` |

**OpenCode specifics:** The work config
([`home/dot_config/opencode/readonly_opencode.work.jsonc`](../../home/dot_config/opencode/readonly_opencode.work.jsonc))
uses Google direct Gemini as the primary default now.

- Main agent default: `google/gemini-3.1-pro-preview-customtools`
- Additional LiteLLM aliases may still be available for explicit selection.

**Pi specifics:** The work config is rendered by
`run_onchange_after_07-merge-pi-config.sh.tmpl` into `~/.pi/agent/`.

## Secrets

Some API keys are loaded into the shell from `pass` in
[`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl).
That means your password-store is part of the runtime wiring for AI tools.

Verification:

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and
load at runtime.

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

## Beads (Task Tracking)

Beads is integrated as a CLI (`bd`) with a repo-aware wrapper command:

- Wrapper function: `bdlocal` in
  [`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl)

The wrapper chooses a per-repo `$BEADS_DIR` under `~/beads-data/` and pins the
database to `$BEADS_DIR/.beads/beads.db`.

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
ls -la ~/.agents/playbooks ~/.agents/skills
```

If assistant behavior is not picking up expected instructions:

- verify the correct entrypoint file exists in `$HOME` (`~/AGENTS.md`,
  `~/CLAUDE.md`, `~/.gemini/GEMINI.md`).
- verify playbook/skill files exist under `~/.agents/playbooks/` and
  `~/.agents/skills/`.
- verify secrets expected at runtime are present in `pass`.

## Related

- Beads task tracking:
  [`docs/recipes/beads-task-tracking.md`](../recipes/beads-task-tracking.md)
- Switching work/personal identity:
  [`docs/recipes/switching-work-personal-identity.md`](../recipes/switching-work-personal-identity.md)
- Security and secrets:
  [`docs/categories/security-and-secrets.md`](security-and-secrets.md)
