# AI And Assistants

Back: [`docs/categories/index.md`](index.md)

This setup treats "how my assistants should work" as configuration that can be
installed alongside everything else.

## Assistant SOPs

Entrypoints installed into your home directory:

- `home/readonly_AGENTS.md` -> `~/AGENTS.md`
- `home/readonly_CLAUDE.md` -> `~/CLAUDE.md`
- `home/dot_gemini/readonly_GEMINI.md` -> `~/.gemini/GEMINI.md`
- `home/dot_cursor/symlink_AGENTS.md` -> `~/.cursor/AGENTS.md` (symlink to `~/AGENTS.md`)

These files are policy entrypoints; playbooks are installed separately.

Shared SOP routing rule:

- Google Workspace requests route to
  `~/.agents/playbooks/google_workspace/workflow.md`.
- Source file:
  `home/exact_dot_agents/exact_playbooks/exact_google_workspace/workflow.md`
- The playbook standardizes on `gws`, using `gws schema ...` before direct
  `gws <service> ...` calls.
- This routing is referenced from the tracked SOP entrypoints:
  `home/readonly_AGENTS.md`, `home/readonly_CLAUDE.md`, and
  `home/dot_gemini/readonly_GEMINI.md`.

## Playbooks Layout

Playbooks are stored under `~/.agents/playbooks/` and referenced by the SOP
entrypoints (for example: "Use playbook X").

Source of truth (this repo, chezmoi-managed):

- `home/exact_dot_agents/exact_playbooks/` -> `~/.agents/playbooks/`

## Reviews: Base-Branch Context And Semantic Search

Review playbooks require comparing your local diff/PR against how base (usually
`main`) works today.

If semantic code search (SCSI) is available and the current repo is indexed, it
is required for base-branch context:

- Preflight is blocking: run `list_indices` first (do not guess an index; try
  both `scsi-main` and `scsi-local` when both exist).
- If the user provided an index name, still run `list_indices` and verify the
  index exists before using it.
- Use SCSI results as base-branch context only; validate the actual change via
  local git diffs and file reads.

Review outputs also include a single reviewer-metadata line so it's obvious
what was used for base context:

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

Playbook support:

- Draft-only review modes live under `~/.agents/playbooks/review/`.
- If you want to apply requested changes one thread/comment at a time (with verification after each cycle), use:
  - `~/.agents/playbooks/review/pr_change_cycle.md`

## Reviews: Reply Style

When drafting PR thread replies:

- Do not use `RE:`.
- Default: reply directly; do not quote when the whole parent comment is the reference.
- If you need to point at a specific fragment, use a minimal blockquote (`> ...`) and then reply.

## Core Workflow: Change A Playbook

1. Edit playbooks under:

- `home/exact_dot_agents/exact_playbooks/`

2. Apply and verify:

```bash
chezmoi diff
chezmoi apply
ls -la ~/.agents/playbooks
```

## Tool Configs

### Cursor agent CLI

A cross-shell alias `agent` is provided for `cursor-agent`:

- POSIX interactive shells: `home/readonly_dot_shellrc` → `~/.shellrc`
- fish: `home/dot_config/fish/config.fish.tmpl` → `~/.config/fish/config.fish`

Verification:

```bash
command -v agent
agent --help
```

Examples of tool configs included here:

- OpenCode: `home/dot_config/opencode/`
- Codex: `home/dot_codex/`
- Amp: `home/dot_config/exact_amp/private_settings.json` (private settings)
- Gemini CLI: `home/dot_gemini/`
- Copilot CLI: `home/dot_config/dot_copilot/`

### Profile-based file merging

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk
target and a `run_onchange` script writes the correct profile-specific version from the repo
source.

Instead of keeping complex templates or comment-based filtering logic, we use explicit
`.work.*` and `.personal.*` files. The shell script checks the `.isWork` template variable
and copies the correct source to the final destination, completely decoupling the formats.

- Cursor MCP: `home/dot_cursor/mcp.{work,personal}.json` → `~/.cursor/mcp.json` (script: `home/.chezmoiscripts/run_onchange_after_07-merge-cursor-mcp.sh.tmpl`)
- Gemini settings: `home/dot_gemini/settings.json` → `~/.gemini/settings.json` (script: `home/.chezmoiscripts/run_onchange_after_07-merge-gemini-settings.sh.tmpl`)
- OpenCode config: `home/dot_config/opencode/opencode.{work,personal}.jsonc` → `~/.config/opencode/opencode.jsonc` (script: `home/.chezmoiscripts/run_onchange_after_07-merge-opencode-config.sh.tmpl`)
- Codex config: `home/dot_codex/private_config.{work,personal}.toml` → `~/.codex/config.toml` (script: `home/.chezmoiscripts/run_onchange_after_07-merge-codex-config.sh.tmpl`)
- Pi MCP config: `home/dot_pi/agent/mcp.{work,personal}.json` → `~/.pi/agent/mcp.json` (script: `home/.chezmoiscripts/run_onchange_after_07-merge-pi-mcp.sh.tmpl`; installed readonly)
- Pi configs: `home/dot_pi/agent/{settings,models}.{work,personal}.json` → `~/.pi/agent/{settings,models}.json` (script: `home/.chezmoiscripts/run_onchange_after_07-merge-pi-config.sh.tmpl`; installed readonly)

### Gemini CLI settings

Source: `home/dot_gemini/settings.json` → `~/.gemini/settings.json`.

- MCP servers are configured under `mcpServers`.
- Tool approval is controlled by `general.defaultApprovalMode` (we use `auto_edit` to auto-approve edit tools).

### Pi coding agent settings

Source: `home/dot_pi/agent/{settings,models}.{work,personal}.json` → `~/.pi/agent/`.
Also manages MCP servers via `home/dot_pi/agent/mcp.{work,personal}.json`.

LiteLLM notes:
- Work profile only: fish exports these values from `pass` when the entries exist:
  - `LITELLM_PROXY_KEY` from `litellm/api/token`
  - `LITELLM_API_BASE` from `litellm/api/base` (normalized to end in `/v1`)
- OpenCode work config uses those shell exports directly via `home/dot_config/opencode/opencode.work.jsonc`.
- Pi work config is rendered from `home/dot_pi/agent/models.work.json` by `home/.chezmoiscripts/run_onchange_after_07-merge-pi-config.sh.tmpl`, which injects the normalized upstream LiteLLM base URL at apply time.

- For the work profile, defaults to `google` using the `gemini-3.1-pro-preview-customtools` model, while also exposing LiteLLM gateway models and OpenAI Codex models via `home/dot_pi/agent/models.work.json`. Pi TUI is enabled via the `npm:@mariozechner/pi-tui` package.
- For the personal profile, defaults to `openai-codex` using `gpt-5.4`.
- Enables automatic context compaction to save tokens.
- Enables exponential backoff retries.
- Installs and enables the `npm:pi-mcp-adapter` extension automatically.
- Secrets (like `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) are already picked up automatically by Pi from the environment variables exported via `pass` in `config.fish.tmpl`.

### Copilot CLI settings

Source: `home/dot_config/dot_copilot/` → `~/.config/.copilot/`.

- `config.json`, `mcp-config.json`, and `lsp-config.json` are managed directly by chezmoi.

## Secrets

Some API keys are loaded into the shell from `pass` in
`home/dot_config/fish/config.fish.tmpl`. That means your password-store is part
of the runtime wiring for AI tools.

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

- `home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh`

Environment tuning for Ollama lives in:

- `home/dot_config/fish/config.fish.tmpl`

Workflow:

```bash
chezmoi apply
ollama list
```

## Beads (Task Tracking)

Beads is integrated as a CLI (`bd`) with a repo-aware wrapper command:

- Wrapper function: `bdlocal` in `home/dot_config/fish/config.fish.tmpl`

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
ls -la ~/.agents/playbooks
```

If assistant behavior is not picking up expected instructions:

- verify the correct entrypoint file exists in `$HOME` (`~/AGENTS.md`,
  `~/CLAUDE.md`, `~/.gemini/GEMINI.md`).
- verify the playbook files exist under `~/.agents/playbooks/`.
- verify secrets expected at runtime are present in `pass`.

## Related

- Beads task tracking: [`docs/recipes/beads-task-tracking.md`](../recipes/beads-task-tracking.md)
- Switching work/personal identity: [`docs/recipes/switching-work-personal-identity.md`](../recipes/switching-work-personal-identity.md)
- Security and secrets: [`docs/categories/security-and-secrets.md`](security-and-secrets.md)
