# The Agentic Operating System (AI & Assistants)

This setup does not just provide you with AI chat tools; it implements an **Agentic Operating System**. This treats "how my assistants should work" as strict, version-controlled configuration that is installed alongside everything else. The goal is deterministic, verifiable behavior instead of relying on unpredictable LLM heuristics.

## The Governance Layer (SOPs)

Entrypoints installed into your home directory:

| Source                                                                                 | Target                | Notes                    |
| -------------------------------------------------------------------------------------- | --------------------- | ------------------------ |
| [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md)                       | `~/AGENTS.md`         | Primary SOP              |
| [`home/readonly_CLAUDE.md`](../../../../home/readonly_CLAUDE.md)                       | `~/CLAUDE.md`         | Claude-specific SOP      |
| [`home/dot_gemini/readonly_GEMINI.md`](../../../../home/dot_gemini/readonly_GEMINI.md) | `~/.gemini/GEMINI.md` | Gemini-specific SOP      |
| [`home/dot_cursor/symlink_AGENTS.md`](../../../../home/dot_cursor/symlink_AGENTS.md)   | `~/.cursor/AGENTS.md` | Symlink to `~/AGENTS.md` |

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
- Canonical sources: [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../../home/readonly_CLAUDE.md), [`home/dot_gemini/readonly_GEMINI.md`](../../../../home/dot_gemini/readonly_GEMINI.md), and [`home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md).

Shared runtime verification rule:

- For "is this correctly set up / working / actually being used" questions, the SOP now owns the canonical end-to-end verification rule, not just config inspection.
- Required chain: source config, rendered/applied config, runtime consumer, and a minimal safe live probe when one is possible.
- The shared rule is tracked in: [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../../../home/dot_gemini/readonly_GEMINI.md).

Shared behavioral disciplines (integrated from [`forrestchang/andrej-karpathy-skills`](https://github.com/forrestchang/andrej-karpathy-skills) without duplicating existing SOP rules):

- `2 Core Principles`: surface material assumptions and competing interpretations rather than picking silently (evidence-first from `2.1` still wins — probe locally before asking); push back when a simpler approach satisfies the stated goal.
- `3.3 Success Criteria & Verification Loops`: reframe imperative tasks as verifiable goals (test-first / reproducer-first when practical); multi-step plans must carry per-step verify checks; does not override `2.0`, `2.1`, `2.2`, or `5 Minimal edit scope`.
- `5 Code Quality`: simplicity discipline (no speculative abstractions/flexibility/impossible-scenario error handling; senior-engineer test); artifact necessity (prove behavior is missing without a new artifact before adding it unless explicitly requested); dead-code handling (remove only orphans your own changes created; mention, don't delete pre-existing dead code unless asked).
- Canonical sources: [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../../../home/dot_gemini/readonly_GEMINI.md).

## Skills Layout

All routable files live under `~/.agents/skills/`. Each skill folder contains a `SKILL.md` entrypoint (and optional `references/` for sub-modes).

Source of truth (this repo, chezmoi-managed):

- [`home/exact_dot_agents/exact_skills/`](../../../../home/exact_dot_agents/exact_skills/) -> `~/.agents/skills/`

Entry contract standard:

- Each skill should make four things obvious near the top: `Use when`, `Do not use`, `First actions`, and `Output`.
- The `description` frontmatter field is the primary routing signal — agents use it to decide whether to load the skill. Keep it concise, specific, and include non-obvious trigger words.
- For manual-only skills with `disable-model-invocation: true`, the description is catalog metadata rather than an automatic routing trigger.
- Skills gated to specific repos (e.g. elastic-only) must state the constraint in the `description` so agents skip them early.
- The goal is to remove implied routing and implied next steps so the agent has less room to "remember roughly" and skip the file.

Current skills:

| Skill                   | Use when                                                                                                           | Gated to       |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------- |
| `review`                | Reviewing changes, continuing a review, addressing threads, rechecking PR changes                                  |                |
| `github`                | Any GitHub mutation (PRs, issues, comments, reviews, labels, releases, merges)                                     |                |
| `git`                   | Any local git operation (branching, committing, pushing, rebasing, merging, conflicts)                             |                |
| `research`              | Investigating a third-party project/library/tool by cloning its GitHub repo                                        |                |
| `walkthrough`           | Explore codebase flows, map component relationships, render diagrams (manual only)                                 |                |
| `cli-skills`            | Creating or upgrading CLI tool skills                                                                              |                |
| `letsfg`                | Searching flight tickets/fares through the local LetsFG CLI with direct booking URLs                               |                |
| `semantic-code-search`  | Semantic search, base-branch context, or when another skill requires SCSI                                          |                |
| `google-workspace`      | Gmail / Drive / Calendar / Admin / Docs / Sheets via `gws` CLI                                                     |                |
| `worktrees`             | Create/switch/open/list/prune/remove worktrees via `,w`                                                            |                |
| `compose-pr`            | Drafting a PR title and body as text (before creating/editing a PR)                                                |                |
| `compose-issue`         | Drafting an issue title and body as text (before creating/editing an issue)                                        |                |
| `buildkite`             | Checking build status, triggering builds, reading logs, debugging CI failures                                      | elastic org    |
| `kibana-labels-propose` | Proposing labels/backports/version targeting when composing or creating a Kibana PR                                | elastic/kibana |
| `kibana-console-monaco` | Automating/testing the Kibana Dev Tools Console editor via Playwright                                              | elastic/kibana |
| `playwriter`            | Controlling Chrome browser via Playwriter (explicit mention only)                                                  |                |
| `beads`                 | Persisting work in the beads DB (explicit mention of beads/bdlocal/BEADS_DIR only)                                 |                |
| `knip`                  | Finding unused files, dependencies, and exports in JS/TS projects                                                  |                |
| `jscpd`                 | Detecting duplicates during refactoring, code cleanup, or DRY improvement                                          |                |
| `improve-codebase`      | Suggest the single smartest addition to the current codebase                                                       |                |
| `improve-local`         | Suggest the single smartest addition to the local changes                                                          |                |
| `improve-branch`        | Suggest the single smartest addition for the current branch/PR/issue                                               |                |
| `ralph`                 | Drive the Ralph orchestrator (planner/executor/reviewer/re-reviewer with self-healing) via `,ralph go` and tmux UX |                |

Always-on rule source:

- The SOP entrypoints are the only canonical always-on mechanism for assistant behavior.
- Do not encode mandatory every-prompt rules as skills; OpenCode skills are on-demand, not guaranteed every turn.
- Keep mandatory completeness and no-guessing rules in: [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../../../home/dot_gemini/readonly_GEMINI.md).

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
- Default to inline anchored comments for code-review feedback (not PR-level summary bodies) unless explicitly requested.
- Any code/file/symbol reference in a comment body must be a clickable source link to the exact location on the PR head SHA.

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

- [`home/exact_dot_agents/exact_skills/`](../../../../home/exact_dot_agents/exact_skills/)

1. Apply and verify:

```bash
chezmoi diff
chezmoi apply
ls -la ~/.agents/skills
```

## Tool Configs

### Cursor agent CLI

A cross-shell alias `agent` is provided for `cursor-agent`:

- POSIX interactive shells: [`home/readonly_dot_shellrc`](../../../../home/readonly_dot_shellrc) → `~/.shellrc`
- fish: [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl) → `~/.config/fish/config.fish`

Verification:

```bash
command -v agent
agent --help
```

#### Cursor CLI hooks

Cursor CLI is the primary interactive assistant harness. User-level hooks are installed from [`home/dot_cursor/hooks.json`](../../../../home/dot_cursor/hooks.json) to `~/.cursor/hooks.json` and call shared scripts deployed from [`home/exact_dot_agents/exact_hooks/`](../../../../home/exact_dot_agents/exact_hooks/) to `~/.agents/hooks/`.

The hook layer is Cursor-native first:

| Event                                                                                                         | Script                | Purpose                                                                                                  |
| ------------------------------------------------------------------------------------------------------------- | --------------------- | -------------------------------------------------------------------------------------------------------- |
| `sessionStart`                                                                                                | `session_context.py`  | Inject the active `/tmp/specs` topic spec plus recent worklog tail when present                          |
| `afterShellExecution`, `postToolUse`, `postToolUseFailure`, `afterFileEdit`                                   | `worklog_recorder.py` | Append compact per-topic JSONL worklog entries                                                           |
| `afterAgentThought`, `afterAgentResponse`, `afterShellExecution`, `postToolUse`, `postToolUseFailure`, `stop` | `evidence_anchor.py`  | Maintain a turn-level claim/evidence ledger, log hook decisions, and retry when claims remain unresolved |

`evidence_anchor.py` is calibrated to the SOP's `External Truth` rule. A factual, setup, state, or behavior claim is considered resolved only when the visible claim unit includes a hard source anchor (for example a file path, command/probe output, test result, or freshly fetched docs URL) or explicitly demotes the claim to `Unknown` with a reason. Words like "verified" are not enough by themselves. Claims made in model thoughts are tracked, and later tool/probe events are logged as evidence, but they do not globally clear every unresolved claim. A final visible response must carry anchors for its claim units, otherwise the `stop` hook issues a bounded follow-up.

Runtime state is intentionally outside chezmoi and outside worktrees:

```text
/tmp/specs/<workspace-path-without-leading-slash>/_active_topic.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.txt
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.worklog.jsonl
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.evidence_state.json
/tmp/specs/<workspace-path-without-leading-slash>/<topic>.evidence_decisions.jsonl
```

This memory layer is bounded without injecting partial memory. Oversized topic specs are omitted with a pointer to the full file instead of being sliced into the prompt, and only whole recent worklog entries are included. Worklog and evidence-decision JSONL files are trimmed on write. Shared default-branch workspaces (`main`, `master`, `dev`, `develop`, `trunk`) use session-scoped topics when no explicit non-`current` topic is active, so unrelated sessions do not inherit the generic `current` memory. Feature/topic worktrees keep `current` continuity by default. Review topics also run in clean-room mode by default: startup context keeps neutral metadata but omits prior verified-facts, findings, verdicts, inline comments, and worklog tails so re-reviews are less biased by prior conclusions. To force a fully clean session, start the agent with `AGENT_HOOK_CONTEXT=0` or place a `_no_session_context` / `<topic>.no_context` sentinel under the workspace's `/tmp/specs/...` directory and remove it when context injection should resume.

The user-facing dead switch is `,agent-memory`: `,agent-memory status` shows the selected workspace topic, and `,agent-memory wipe-current` deletes that topic's spec, worklog, evidence state, decision log, and no-context sentinel without touching other topics. On default branches without an explicit active topic, `wipe-current` targets the latest `session-*` topic. Fish completions are installed from `home/dot_config/fish/completions/readonly_,agent-memory.fish` for the subcommands, shared options, wipe flags, and existing topic names.

Claude Code mirrors only the proven shared subset through [`home/dot_claude/settings.personal.json`](../../../../home/dot_claude/settings.personal.json) and [`home/dot_claude/settings.work.json`](../../../../home/dot_claude/settings.work.json): session context and tool worklog recording. The local llama.cpp settings file is intentionally excluded. Pi has no verified hook lifecycle, so it remains static-prompt only.

Verification:

```bash
python3 scripts/tests/test_agent_hooks.py
chezmoi diff --no-pager
chezmoi apply --force --no-tty
tmp=/tmp/cursor-hook-user-check
mkdir -p "$tmp"
rm -rf /tmp/specs/private/tmp/cursor-hook-user-check
(cd "$tmp" && cursor-agent -p --output-format json --force \
  "Use your shell tool to run exactly: printf deployed_cursor_hook_ok. Then reply done.")
python3 - <<'PY'
from pathlib import Path
print(Path('/tmp/specs/private/tmp/cursor-hook-user-check/current.worklog.jsonl').read_text())
PY
```

#### Tmux agent prompt wrap

When running an AI coding agent (`claude`, `cursor-agent`, or `pi`) inside tmux, `Alt-Enter` is intercepted to prepend a calibrated verification scaffold to your prompt before submitting.

- **Binding:** `Alt-Enter` (submits the wrapped prompt)
- **Toggle:** `prefix` + `W` (toggles wrapping on/off for the session)
- **Prefix text:** [`home/dot_config/exact_tmux/agent_prompts/prefix.txt`](../../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt)

Plain `Enter` is never touched. `Alt-Enter` is passed through untouched in non-agent panes or when the toggle is OFF.

### AI knowledge base (`,ai-kb`)

`,ai-kb` is the durable memory layer Ralph reads from and writes to. Capsules are markdown sidecars under `~/.local/share/ai-kb/capsules/<id>.md` (canonical content) plus an indexed SQLite mirror at `~/.local/share/ai-kb/kb.sqlite3` for retrieval. Schema is breaking by policy: when [`scripts/ai_kb.py::CAPSULE_COLUMNS`](../../../../scripts/ai_kb.py) drifts from the on-disk shape, `init()` drops `capsules`/`capsule_fts`/`kb_meta` and recreates them — markdown sidecars survive so a curator (`,ai-kb ingest`) can re-hydrate.

Capsule shape:

| Field                                   | Purpose                                                                                                |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `kind`                                  | `gotcha` / `principle` / `fact` / `decision` / `pattern` / `anti_pattern` / `doc` / `experiment`       |
| `scope`                                 | `global` / `project` / `repo` / `workflow` / `session` (controls reuse across runs and projects)       |
| `tags` / `domain_tags`                  | Free-form (TUI badges) and structured taxonomy (e.g. `auth`, `tmux`, `rust`)                           |
| `confidence` / `verified_by`            | Float 0-1 + role/run that verified it; reflectors and reviewers raise these                            |
| `supersedes` / `superseded_by`          | Bidirectional links built by `,ai-kb curate dedupe`; superseded capsules drop out of search            |
| `refs`                                  | Run / iteration / role / file refs so a hit can jump back to its origin                                |
| `embedding` / `embedding_model` / `dim` | Packed `float32` vector + provenance; populated via [`scripts/embed.py`](../../../../scripts/embed.py) |
| `decay_score`                           | Incremented by `,ai-kb curate decay` for capsules nobody retrieves; surfaces stale memory              |

Retrieval is hybrid by default: lexical (FTS5/BM25) + dense (cosine over the embedding column, accelerated by `sqlite-vec`'s `vec0` virtual table) fused with Reciprocal Rank Fusion, then diversified with Maximal Marginal Relevance and filtered by `kind` / `scope` / `workspace_path` / `domain_tags`. Workspace matches give a soft RRF boost so project-scoped capsules outrank global ones for the active workspace. Superseded capsules are excluded by default. See [`KnowledgeBase.search`](../../../../scripts/ai_kb.py).

Embeddings are computed by [`scripts/embed_runner.py`](../../../../scripts/embed_runner.py) — a PEP 723 inline-deps script (`uv run --script`) that loads `fastembed` (`BAAI/bge-small-en-v1.5`, 384-d) on demand. The orchestrator stays stdlib-only; `Embedder` (in [`scripts/embed.py`](../../../../scripts/embed.py)) shells out via JSON over stdin/stdout. `RALPH_KB_DISABLE_EMBED=1` skips embedding (used by the test suite + offline boxes; lexical retrieval still works).

Vector search and curate-pairs use the same subprocess-isolation pattern: [`scripts/vec_runner.py`](../../../../scripts/vec_runner.py) is a PEP 723 inline-deps script that loads `sqlite-vec` and serves KNN / pairs queries against the KB SQLite file. The runner manages its own `vec_index` virtual table — lazily created from `capsules.embedding` BLOBs on first call and delta-synced on every subsequent call — so the orchestrator process never needs to load extensions (Apple's stock `python3` ships without `enable_load_extension`). Hard-fail by design: vec_runner errors raise `RuntimeError` rather than silently degrading to BM25-only. `RALPH_KB_DISABLE_VEC=1` is the test/offline escape hatch (mirrors `RALPH_KB_DISABLE_EMBED`). Curation's pairwise dedupe / contradiction-scan loop also goes through vec_runner — KNN-shortlist + per-pair cosine — replacing what was an O(N²) Python loop, so the curator scales with the KB.

Memory flow during a Ralph run:

1. Each role's prompt builder calls `KnowledgeBase.search(...)` filtered to that role's preferred kinds. Planner gets the broadest slice (no kind filter — anything prior may influence planning, with workspace bias surfacing project-local capsules first). Executor: `fact / recipe / gotcha / anti_pattern / pattern`. Reviewer: `gotcha / anti_pattern`. Re_reviewer: `gotcha / anti_pattern / principle`. Hits are injected into a `## RECENT LEARNINGS` block in the role prompt and a compressed copy is persisted to `manifest.json::roles[*].retrieval_log` for TUI replay.
2. Roles can also call the KB on demand from inside their pane (`,ai-kb search "<q>" --kind gotcha,anti_pattern --json`) — see the `Tool: on-demand KB search` section in each prompt.
3. Roles emit `LEARNING:` lines (free-form `gotcha`/`principle`/`fact`/`decision`); `,ralph` parses these in [`RalphRunner.capture_learnings`](../../../../scripts/ralph.py) and stores them with `kind` inferred from role and `scope=project` when a workspace is set.
4. After a passing run the dedicated `reflector` role distills the run into a small JSON list of structured capsules (see [`reflector.md`](../../../../home/dot_config/ralph/prompts/reflector.md)) which are validated and persisted, giving the next run high-signal retrieval material.

CLI surface:

```bash
,ai-kb remember --title "Project rule" --body "Keep generated state out of git." \
                --kind principle --scope project --tags lint
,ai-kb search "tmux capture-pane reuse"           # hybrid (lexical + vector)
,ai-kb search --kind gotcha --scope project --json
,ai-kb get <capsule-id>                            # full body + metadata
,ai-kb ingest ./AGENTS.md ./docs                   # chunk markdown into kind=doc capsules; idempotent on sha256
,ai-kb reembed                                     # rebuild missing/stale embeddings
,ai-kb curate dedupe                               # mark near-duplicates as superseded
,ai-kb curate decay                                # bump decay_score on dormant capsules
,ai-kb curate contradiction                       # flag suspicious gotcha vs fact pairs
,ai-kb doctor                                      # capsule count, FTS sanity, embedding coverage
```

The Ralph TUI exposes the KB with a `K` keybinding: a modal launches `,ai-kb search ... --json` over stdin/stdout; navigation is `↑/↓`, `enter` to dispatch a search, `esc`/`q` to close. The status bar shows total capsule count (`KB:N`).

### Ralph orchestrator (`,ralph go`)

One entry point, `,ralph go`, drives an opinionated `planner -> executor -> reviewer -> re_reviewer` loop with persistent state, self-healing (replans on `RALPH_REPLAN`), and full tmux observability. Both reviewer and re_reviewer run on every iteration, in sequence, so two different model families always cover each other's gaps. After a passing run, an optional `reflector` role distills durable lessons into the AI KB (see above) so subsequent runs benefit from the learnings.

| Command  | Source                                                                                                                                                                                                                                                          | Purpose                                                                                                                           |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `,ai-kb` | [`home/exact_bin/executable_,ai-kb`](../../../../home/exact_bin/executable_,ai-kb) + [`scripts/ai_kb.py`](../../../../scripts/ai_kb.py) + [`scripts/embed.py`](../../../../scripts/embed.py) + [`scripts/embed_runner.py`](../../../../scripts/embed_runner.py) | Structured-capsule memory (kind/scope/embedding) backed by SQLite FTS5 + dense vectors; hybrid retrieval, curation, doc ingestion |
| `,ralph` | [`home/exact_bin/executable_,ralph`](../../../../home/exact_bin/executable_,ralph) + [`scripts/ralph.py`](../../../../scripts/ralph.py)                                                                                                                         | Orchestrator loop, role spawning, persistent state, learning capture                                                              |

Roles + diversity gate (`~/.config/ralph/roles.json`):

| Role          | Default harness | Default model                  | Mode flag     |
| ------------- | --------------- | ------------------------------ | ------------- |
| `planner`     | `cursor`        | `claude-opus-4-7-thinking-max` | `--mode plan` |
| `executor`    | `cursor`        | `composer-2`                   | `--force`     |
| `reviewer`    | `cursor`        | `claude-opus-4-7-thinking-max` | `--mode ask`  |
| `re_reviewer` | `cursor`        | `gpt-5.5-extra-high`           | `--mode ask`  |
| `reflector`   | `cursor`        | `claude-opus-4-7-thinking-max` | `--mode ask`  |

Defaults are cursor-first because cursor's frontier models give the strongest output and judgement on this user's setup; pi stays fully supported and is required for non-cursor providers (anthropic/openai/google direct, openrouter, llama-cpp). The orchestrator enforces `family_of(re_reviewer.model) != family_of(reviewer.model)` (substring match on `claude|gpt|gemini|llama|mistral|deepseek`) so the mandatory second opinion never comes from the same family. `--mode plan` (planner) and `--mode ask` (reviewer/re_reviewer) are read-only — they prevent role hijacking (small models with full tools tend to skip JSON and just execute the goal) while still allowing read access for verification probes. `--force` on the executor auto-approves shell commands so the orchestrator can drive non-interactively. On pi the equivalent role-scoping is `--no-tools` for planner/reviewer/re_reviewer. Per-role prompts live at [`home/dot_config/ralph/prompts/`](../../../../home/dot_config/ralph/prompts/).

#### Elastic-gated `/review` skill invocation

For elastic-belonging codebases — operator's day job — the reviewer and re-reviewer roles invoke the operator's [`review` skill](../../../../home/exact_dot_agents/exact_skills/exact_review) directly. The skill's verification disciplines become the primary instruction; Ralph's existing JSON output contract is preserved as the wire format. Non-elastic workspaces are unchanged.

- **Detection**: [`is_elastic_workspace(path)`](../../../../scripts/ralph.py) parses `git remote -v` and matches `(github\.com[:/])elastic/` against any remote URL (HTTPS or SSH; `origin` or `upstream`). Best-effort — non-git directories, missing paths, or `git` failures all yield `False`.
- **Wiring**: [`elastic_review_preamble(role)`](../../../../scripts/ralph.py) reads `~/.agents/skills/review/references/{shared_rules,local_changes}.md` and renders a `## REVIEW SKILL HEURISTICS (elastic)` block containing (a) "you are running the `/review` skill in local_changes mode", (b) the skill's `shared_rules.md` content verbatim, (c) the skill's `local_changes.md` content verbatim, and (d) a format-normalization note translating the skill's "fix in working tree" guidance into Ralph's `criteria_unmet` + `next_task` JSON fields. The block is prepended to the dynamic context BEFORE `## SPEC`, so the model reads the skill instruction first then applies it to the inputs.
- **Override**: `RALPH_REVIEW_SKILL_DIR=<path>` swaps in a different skill source directory (useful for testing alternate review heuristics without touching `~/.agents/`).
- **Graceful degradation**: when the skill files are missing the preamble silently degrades to empty (no crash) and the default review path runs unchanged. Operators without the skill installed see no behavior change.
- **Output contract**: unchanged. Reviewer still emits `{verdict, criteria_met, criteria_unmet, next_task, blocking_reason, notes}`; re-reviewer still emits `{agree_with_primary, final_verdict, ...}`. The orchestrator's verdict parser is not aware that the elastic preamble was injected.

Local models (llama-cpp / qwen3.6) are opt-in only; defaults never depend on `,llama-cpp serve` being up. Swap them in by editing `roles.json` (e.g. point `executor.harness=pi`, `executor.model=llama-cpp/qwen3.6-35b-a3b-q4-k-m`).

Runtime data stays outside chezmoi (per-session isolation, never under the project worktree):

| Data                | Default path                 | Override             |
| ------------------- | ---------------------------- | -------------------- |
| Knowledge capsules  | `~/.local/share/ai-kb/`      | `AI_KB_HOME`         |
| Ralph run manifests | `~/.local/state/ralph/runs/` | `RALPH_STATE_HOME`   |
| Ralph roles config  | `~/.config/ralph/roles.json` | `RALPH_ROLES_CONFIG` |

Core workflow:

```bash
,ai-kb remember --title "Project rule" --body "Keep generated state out of git."
,ralph dry-run --goal "Memory rehearsal"                          # render the prompt only
,ralph go --goal "Build a tiny CLI tool" --workspace "$(mktemp -d)"
,ralph go --goal "Refactor module" --plan-only                    # stop after planner
,ralph go --goal "Refactor module" --workflow research             # workflow hint
,ralph go --goal "Refactor module" \
  --reviewer-model claude-sonnet-4-7 --re-reviewer-model gpt-5.5  # per-role overrides
,ralph answer <run-id> --json - <<< '{"q-1":"yes, the cache is ok"}' # post answers when parked at awaiting_human
,ralph runner <run-id>                                            # internal: drive the state machine
,ralph resume <run-id>                                            # re-launch runner if it died (no-op if alive/terminal)
,ralph replan <run-id>                                            # queue replan; runner consumes it next loop
,ralph supervisor --json                                          # resume dead non-terminal runners when safe
```

Tmux-native mode (default when `$TMUX` is set the runner detaches and your shell returns immediately; `--foreground` blocks inline; `--subprocess` skips tmux entirely):

```bash
,ralph go --goal "Build a tiny artifact"               # detached runner; observe via dashboard
,ralph go --foreground --goal "Block until done"       # inline state-machine drive
,ralph runs --json --session "$(tmux display-message -p '#S')"
,ralph preview <run-id>      # rich summary; --mode tail for live tail
,ralph dashboard             # alias for prefix+A: execs ~/.local/bin/ralph-tui
,ralph attach <run-id> --role executor-1
,ralph verify <run-id>
,ralph kill  <run-id> [--role executor-1]              # SIGINT pane(s), mark killed
,ralph kill  --all                                     # bulk-kill every non-terminal run
,ralph rm    <run-id>                                  # archive + drop ai-kb capsules
,ralph statusline                                      # one-line tmux status segment + (^A) hint
```

Resumability: every iteration is a state machine driven by the manifest on disk. If the runner process dies (Ctrl-C, SSH drop, host reboot), `,ralph resume <run-id>` re-launches it and the loop picks up at the earliest pending phase: per-iteration phases are `pending -> exec -> review -> rereview -> decided`. Role spawns are idempotent at the parent-manifest level: a role with `status=completed` in the manifest cache is reused without re-spawning; if a tmux role pane is still alive after a runner crash, the runner reuses that pane and waits for its exit marker instead of spawning a duplicate. Runner liveness is detected via an exclusive `flock` on `<run_dir>/runner.pid`. `,ralph supervisor` can resume dead non-terminal runners and skips runs parked for manual control.

Multi-Ralph dashboard ([`tools/ralph-tui/`](../../../../tools/ralph-tui/), `prefix + A` opens the popup):

The dashboard is a Bubble Tea TUI installed at `~/.local/bin/ralph-tui` by [`home/.chezmoiscripts/run_onchange_after_06-build-ralph-tui.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_06-build-ralph-tui.sh.tmpl). It reads run state directly from the manifest tree under `$RALPH_STATE_HOME` via fsnotify, so updates are live without polling. All mutating actions still shell out to `,ralph` so the orchestrator stays the only writer.

Layout:

- Left pane: scrollable list of every run (newest first). `*` = runner alive, `R` = replan queued. Status colors track validation/phase.
- Right top: selected run's header (id, goal, phase, status, runner) and a roles table with per-iteration history.
- Right bottom: live tail of the selected role's `output.log`.
- Modals: new-run form (`n`), control menu (`c`), help overlay (`?`).

Keybindings:

- Fleet view rows: heartbeat dot (bright violet `●` alive+fresh, amber `●` alive+stale, red `●` dead, `R` replan queued, blank never started), name, status badge, phase, `n/N` iterations vs `max_iterations`, and a verdict-colored sparkline (green=pass, red=fail, amber=replan, blue=in-flight, dim=pending). A `Q:N` badge surfaces open clarifying questions.
- `j/k` (or arrows) move within the focused pane; `tab` cycles `runs -> roles -> tail`; `enter` (or `3`) zooms the focused pane to fullscreen; `1`/`2`/`3` switch between detail / 2x2 role grid / zoom layouts.
- `s` cycles the runs list sort (`need` parks-on-questions+live-work first, `recent` newest first); `S` toggles the cross-run activity drawer (recent decisions + verdicts across all parent `kind=go` runs).
- `enter` (on a run) attaches via `tmux switch-client -t ralph-<short-rid>`; `enter` (on a role) attaches to that role's window. `p` opens a tmux capture-pane preview of the focused role's pane (read-only, refreshes every second + on `r`); inside the modal, capital `A` launches `tmux display-popup -E -- tmux attach-session -r -t TARGET` for a read-only popup attach without leaving the TUI.
- `n` opens the new-run form. Fields: goal, workspace, plan-only, **workflow** picker (`auto` / `feature` / `bugfix` / `review` / `research`), plus per-role harness AND model pickers for planner / executor / reviewer / re_reviewer. Pickers cycle with `h`/`l` or `←`/`→`; `j`/`k` (or `↓`/`↑`, or `tab`/`shift+tab`) move down/up between fields (gated so the goal/workspace text inputs still accept literal characters); `enter` advances harness → matching model → next role. Harness cycles `cursor → pi → command`; model lists curated per harness in [`tools/ralph-tui/internal/state/models.go`](../../../../tools/ralph-tui/internal/state/models.go); `auto` workflow lets the planner pick, otherwise `--workflow <name>` is forwarded to `,ralph go`.
- `A` (capital) opens the answer modal when the selected run is parked at `awaiting_human`. One text input per open question; `tab`/`j`/`k`/`shift+tab` move focus, `enter` advances or submits, `esc`/`ctrl+c` cancels (`q` cancels only when focus is not on a text input). Submission pipes JSON answers through `,ralph answer <rid> --json -` so the orchestrator can resume. The status bar shows `Q:Σ` aggregated across the fleet.
- `K` (capital) opens the AI KB browser modal. Type a query and `enter` to dispatch a hybrid search (lexical + dense, RRF + MMR, superseded capsules excluded); `↑/↓` move between hits to expand metadata (kind/scope/confidence/refs) on the right; `esc`/`q` closes. The status bar shows `KB:N` (total non-superseded capsules).
- `v` verify; `r` manual refresh; `R` resume runner; `P` replan; `x` kill; `X` rm. `x` and `X` open a confirmation modal before dispatching.
- `/` filter the runs list; `c` opens the control menu (verify, takeover, dirty, kill, rm, replan, resume); `?` toggles help; `q` quit.

Multi-Ralph isolation contract:

- Each `,ralph go` run owns a dedicated tmux session named `ralph-<short-rid>`. Multiple runs coexist without polluting the user's main session.
- The dashboard never holds tmux state; quitting (`q`) does not affect any running runners or sessions.
- `kill <rid>` and `rm <rid>` only touch their own dedicated session; concurrent runs are unaffected (covered by [`scripts/tests/test_scripts.py::TestRalphMultiRunIsolation`](../../../../scripts/tests/test_scripts.py)).

Other tmux integrations:

- `prefix + A` opens the dashboard popup (only top-level prefix key Ralph claims). The popup runs `~/.local/bin/ralph-tui` directly; if the user picks a run + `enter`, the TUI exits cleanly and `tmux switch-client` jumps to that run's session.
- `prefix + R` is **untouched** (still reloads tmux config); start runs from the dashboard (`n`) or the palette.
- The command palette (`prefix + r`) lists Ralph entries (dashboard, `ralph:start-go` prompt, `ralph:plan-only` prompt, verify latest, attach prompt, doctor) that fire `tmux command-prompt` instead of dumping text.
- The session picker (`prefix + T`) tags Ralph-owned tmux sessions with a colored badge (`ralph✓` `ralph?` `ralph✗` `ralph●` `ralph⨯`) and shows the matching `,ralph runs --session …` block in the preview.
- The GitHub picker (`prefix + G`) `alt-A` on a PR/issue stages a Ralph handoff: closes the picker, resolves the matching worktree (or `$PWD`), and opens a `,ralph go` goal prompt seeded with the PR/issue title.
- A status-bar segment (appended after TPM/Catppuccin) shows `R:<running>` and `V:<needs_verification>` counts via `,ralph statusline`.

Dashboard / control-plane invariants:

- Source of truth: `~/.local/state/ralph/runs/<run-id>/manifest.json`. Mutate via the CLI only.
- Each `go` run records `phase` (`planning|executing|reviewing|rereviewing|replanning|done|failed|blocked`), `iterations[]` (each with its own `phase` (`pending|exec|review|rereview|decided`), `verdict`, `executor_id`, `reviewer_id`, `re_reviewer_id`, `task`, `next_task`, `spec_seq`), `roles{}` (pane handles for planner-N / executor-N / reviewer-N / re_reviewer-N), `spec`, `spec_seq`, `learned_ids`, and `runner` (pid + host + heartbeat + alive bit).
- `spec.target_artifact` is promoted to top-level `manifest.artifact`; on a passing verdict Ralph freezes `artifact_sha256`, and `verify` requires the artifact hash to match.
- `executor_count` must be `1` until real multi-executor orchestration exists. Planner output with a higher value fails fast instead of being silently ignored.
- Iteration records are appended at iteration START (phase=pending) and updated as phases progress; the runner is fully resumable from the manifest alone — see `Resumability` above.
- Human control: every role records pane handle, status, last output path, and `control_state` (`automated|manual_control|dirty_control|resume_requested`).
- Low-token observability: dashboards read manifests, logs, and tmux pane tails directly. No LLM is invoked for summarization unless the user explicitly requests a review/triage agent.
- Validation gates: a `go` run is `passed` only when the orchestrator loop exits with `status=completed`, the final verdict is `pass`, every role child is `automated`, every role child passed validation, and the artifact hash gate passes when `target_artifact` is declared.
- Manual takeover: `,ralph control <run-id> --role <role> --action takeover|dirty|resume|auto`. `resume` auto-runs `verify`.
- Isolation: workspace and ralph state stay separated by run ID; worktrees remain source-code context, not scratch storage.

Verification:

```bash
uvx pytest scripts/tests/                          # python suite (ralph + isolation + resumability + artifact/control gates + workflows + answer + KB schema/hybrid retrieval/reflector/doc-ingest/curation)
( cd tools/ralph-tui && go test ./... )            # TUI suite (state, cmds, forms, runs, detail, answer, preview, activity, kb, app/view)
AI_KB_HOME="$(mktemp -d)" RALPH_STATE_HOME="$(mktemp -d)" \
  ,ralph go --goal "create $(mktemp -d)/hello.txt with content 'hi'" \
            --workspace "$(mktemp -d)" --subprocess
```

`--runtime local` is deterministic and still exists for `,ralph dry-run` smoke tests; `,ralph go` itself reads runtimes from `roles.json` (Pi rich primary, Cursor Agent secondary).

Tool configs included here:

| Tool        | Config source                                                                                                                      |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/`](../../../../home/dot_claude/)                                                                                 |
| OpenCode    | [`home/dot_config/opencode/`](../../../../home/dot_config/opencode/)                                                               |
| Codex       | [`home/dot_codex/`](../../../../home/dot_codex/)                                                                                   |
| Amp         | [`home/dot_config/exact_amp/private_readonly_settings.json`](../../../../home/dot_config/exact_amp/private_readonly_settings.json) |
| Gemini CLI  | [`home/dot_gemini/`](../../../../home/dot_gemini/)                                                                                 |

### Profile-based file merging

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk target and a `run_onchange` script writes the correct profile-specific version from the repo source.

Instead of keeping complex templates or comment-based filtering logic, we use explicit `.work.*` and `.personal.*` files. The shell script checks the `.isWork` template variable and copies the correct source to the final destination, completely decoupling the formats.

| Tool                 | Source files                                                                                                                                                                | Target                               | Merge script                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Claude Code settings | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/settings.{work,personal}.json)                                                                | `~/.claude/settings.json`            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Claude Code MCP      | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                                                    | `~/.claude.json` (mcpServers field)  | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Cursor MCP           | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                                                    | `~/.cursor/mcp.json`                 | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Gemini settings+MCP  | [`home/dot_gemini/settings.json`](../../../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                         | `~/.gemini/settings.json`            | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config      | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc)                          | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| OpenCode MCP         | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                                                    | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config         | [`home/dot_codex/private_config.{work,personal}.toml`](../../../../home/dot_codex/private_config.{work,personal}.toml)                                                      | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Codex MCP            | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                                                    | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi MCP               | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) (shared registry)                                                                    | `~/.pi/agent/mcp.json`               | `run_onchange_after_07-generate-mcp-configs.sh.tmpl`       |
| Pi settings/models   | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) | `~/.pi/agent/{settings,models}.json` | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |

All merge scripts live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/). Pi targets are installed readonly.

### Claude Code settings

Source: [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/settings.{work,personal}.json) → `~/.claude/settings.json`.

Both profiles enable extended thinking and skip the dangerous-mode permission prompt. The work profile uses native Claude enterprise auth by default (no `apiKeyHelper` or `ANTHROPIC_BASE_URL` override).

MCP servers are stored separately in `~/.claude.json` (top-level `mcpServers` field) because that file contains runtime state managed by Claude Code. The merge script surgically updates only the `mcpServers` key, leaving other fields intact.

Work MCP servers: sequentialthinking, scsi-main, scsi-local, slack. Personal MCP servers: sequentialthinking.

LetsFG is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions. Agents load [`~/.agents/skills/letsfg/SKILL.md`](../../../../home/exact_dot_agents/exact_skills/exact_letsfg/readonly_SKILL.md) on demand and use the local `letsfg` uv tool from [`home/readonly_dot_default-uv-tools.tmpl`](../../../../home/readonly_dot_default-uv-tools.tmpl) for free local searches that return direct airline/OTA `booking_url` values. Normal agent searches pass `LETSFG_BROWSERS=0` on each `letsfg` invocation so LetsFG skips browser connectors without changing the user shell environment; browser connectors are explicit opt-in coverage because some upstream connectors intentionally avoid headless mode for anti-bot reasons. Playwriter headless browser automation remains a fallback for rendered UI checks or booking-adjacent flows that need explicit user confirmation.

### Gemini CLI settings

Source: [`home/dot_gemini/settings.json`](../../../../home/dot_gemini/settings.json) → `~/.gemini/settings.json`.

- MCP servers are injected from the shared [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) registry at apply time (no longer hardcoded in the settings file).
- Tool approval is controlled by `general.defaultApprovalMode` (we use `auto_edit` to auto-approve edit tools).

### Pi coding agent settings

**Installation:** Pi globals are installed via yarn from [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs) → `~/.default-yarn-pkgs`:

| Package                         | Purpose               |
| ------------------------------- | --------------------- |
| `@mariozechner/pi-coding-agent` | Core Pi agent         |
| `@mariozechner/pi-tui`          | Pi TUI (work profile) |
| `pi-mcp-adapter`                | MCP adapter extension |

**Config sources:**

| Config            | Source                                                                                                                                                                                              |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Settings + models | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + shared [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) → `~/.pi/agent/` |
| MCP servers       | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) (shared registry) → `~/.pi/agent/mcp.json`                                                                   |

**Profile defaults:**

| Profile  | Default provider | Default model                        |
| -------- | ---------------- | ------------------------------------ |
| Work     | `google`         | `gemini-3.1-pro-preview-customtools` |
| Personal | `google`         | `gemini-3.1-pro-preview-customtools` |

Work profile also exposes additional configured models alongside the Google direct default.

**Shared settings:**

- Automatic context compaction (saves tokens)
- Exponential backoff retries
- `yarn:pi-mcp-adapter` extension auto-installed (kept in yarn convergence list)
- Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) are picked up from environment variables exported via `pass` in `config.fish.tmpl`

#### LiteLLM integration (work profile)

Fish exports these values from `pass` when the entries exist:

| Variable            | Pass path           | Notes                      |
| ------------------- | ------------------- | -------------------------- |
| `LITELLM_PROXY_KEY` | `litellm/api/token` | API authentication         |
| `LITELLM_API_BASE`  | `litellm/api/base`  | Normalized to end in `/v1` |

**OpenCode specifics:** The work config ([`home/dot_config/opencode/readonly_opencode.work.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.work.jsonc)) uses Google direct Gemini as the primary default now.

- Main agent default: `google/gemini-3.1-pro-preview-customtools`
- Additional LiteLLM aliases may still be available for explicit selection.

**Pi specifics:** The work config is rendered by `run_onchange_after_07-merge-pi-config.sh.tmpl` into `~/.pi/agent/`.

#### llama.cpp local provider (Pi)

Pi settings and models are intentionally installed readonly, so the llama.cpp provider is declared once in shared chezmoi source and rendered into `~/.pi/agent/models.json` for both profiles:

- Shared source: [`home/dot_pi/agent/readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json)
- Work source: [`scripts/generate_pi_models.py`](../../../../scripts/generate_pi_models.py) starts from that shared source, then adds work-only LiteLLM and Azure providers

Use it after starting the llama.cpp router:

```bash
,llama-cpp serve
pi --model llama-cpp/qwen3.6-35b-a3b-q4-k-m
```

The provider points Pi at `http://127.0.0.1:8080/v1` with `api: "openai-completions"` and Qwen chat-template thinking compatibility. If you start `llama-server` with `--api-key`, export `LLAMA_CPP_API_KEY` before launching Pi.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

Verification:

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime.

## Ollama

This setup includes a hook that pulls a small list of models:

- [`home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh`](../../../../home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh)

Environment tuning for Ollama lives in:

- [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl)

Workflow:

```bash
chezmoi apply
ollama list
```

## llama.cpp (local GGUF inference server)

[llama.cpp](https://github.com/ggml-org/llama.cpp) provides `llama-server`, a local C/C++ inference server with OpenAI-compatible chat/completions/responses endpoints and Anthropic-compatible `/v1/messages` endpoints. It is the primary local-agentic-coding backend.

### Install

`llama.cpp` and the official Hugging Face CLI (`hf`) are installed via Homebrew:

- [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl) — AI & LARGE LANGUAGE MODELS section

```ruby
brew "llama.cpp"
brew "hf"
```

### Model manifest

The curated GGUF model list is declared as a chezmoi-templated manifest:

- [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../home/readonly_dot_default-llama-cpp-models.tmpl)

The manifest keeps the measured best local Qwen3.6 GGUF checkpoint: `bartowski/Qwen_Qwen3.6-35B-A3B-GGUF` with `Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf` (~21.4 GB).

Format (pipe-delimited):

```text
<hf-repo-id>|<hf-file>
```

- `hf-repo-id` — Hugging Face repo id containing GGUF weights.
- `hf-file` — GGUF filename to place under `~/.llama.cpp/models/`.

### Sync hook (opt-in)

Downloads are gated by `downloadLlamaCppModels` in `~/.config/chezmoi/chezmoi.toml`. Default is `false`, so `chezmoi apply` never auto-downloads multi-GB weights unless explicitly enabled. To change the setting, clear that key and re-run `chezmoi init`.

The sync hook is a thin shell orchestrator that delegates parse + skip + download logic to a Python helper:

- [`home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl)
- [`scripts/sync_llama_cpp_models.py`](../../../../scripts/sync_llama_cpp_models.py)

The helper treats a GGUF file as "complete" if it exists and has non-zero size, so re-runs are idempotent.

Override the model root with `LLAMA_CPP_MODELS_ROOT` (defaults to `~/.llama.cpp/models`).

Workflow:

```bash
chezmoi init  # (once) prompts for downloadLlamaCppModels
chezmoi apply # syncs models when gate is true
,llama-cpp serve
```

Add a model: [`docs/recipes/add-a-llama-cpp-model.md`](../../core/packages/llama-cpp-model.md).

### Router preset

llama.cpp model routing and per-model defaults live in an INI preset:

- Source: [`home/dot_config/llama.cpp/models.ini.tmpl`](../../../../home/dot_config/llama.cpp/models.ini.tmpl)
- Target: `~/.config/llama.cpp/models.ini`

The shipped preset defines the model id `qwen3.6-35b-a3b-q4-k-m`, points it at `~/.llama.cpp/models/Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`, and sets shared defaults for `ctx-size=262144`, Metal offload, flash attention, Jinja chat templates, q8 KV cache, and `reasoning=auto`. Local A/B testing showed no-reasoning mode improves latency and structured-output cleanliness, but it makes Qwen3.6 noticeably less capable for agent work; keep reasoning enabled by default and disable it only for narrow structured-output probes.

The default `ctx-size` is `262144`, matching the Qwen3.6 GGUF's native `qwen35moe.context_length`. Claude Code's local settings use `autoCompactWindow=200000` to compact before the server context fills.

Start and verify:

```bash
,llama-cpp serve
curl -s http://localhost:8080/models | python3 -m json.tool
```

### Model-level control plane (`,llama-cpp`)

This repo ships a thin wrapper around `llama-server` router mode and its model API:

- [`home/exact_bin/executable_,llama-cpp`](../../../../home/exact_bin/executable_,llama-cpp) → `~/bin/,llama-cpp`
- [`home/dot_config/fish/completions/readonly_,llama-cpp.fish`](../../../../home/dot_config/fish/completions/readonly_,llama-cpp.fish) — context-aware subcommand + model-id completions

Subcommands:

```bash
,llama-cpp serve                      # start llama-server router mode
,llama-cpp status                     # loaded/unloaded state
,llama-cpp load <model-id> [<id> ...] # POST /models/load
,llama-cpp unload <model-id> [<id> ...]
,llama-cpp unload --all
```

Respects `LLAMA_CPP_HOST` / `LLAMA_CPP_PORT` / `LLAMA_CPP_API_KEY` / `LLAMA_CPP_MODELS_PRESET` (defaults: `127.0.0.1:8080`, no auth header unless `LLAMA_CPP_API_KEY` is set, preset at `~/.config/llama.cpp/models.ini`).

### Codex launcher metadata

Codex only has first-class model metadata for slugs present in its model catalog; unknown local slugs use fallback metadata and emit a warning.

This repo ships a transparent `codex` wrapper plus a small local catalog for the llama.cpp model:

- [`home/exact_bin/executable_codex`](../../../../home/exact_bin/executable_codex) -> `~/bin/codex`
- [`home/dot_codex/readonly_llama-cpp-model-catalog.json`](../../../../home/dot_codex/readonly_llama-cpp-model-catalog.json) -> `~/.codex/llama-cpp-model-catalog.json`

The wrapper injects `-c model_catalog_json="$HOME/.codex/llama-cpp-model-catalog.json"` only when the selected model is `qwen3.6-35b-a3b-q4-k-m`; normal Codex invocations fall through to `/opt/homebrew/bin/codex` unchanged.

### Claude Code launcher (`,claude-llama-cpp`)

Claude Code compacts conversation history at `autoCompactWindow` tokens (schema min 100000, max 1000000). Cloud `opus[1m]` sessions benefit from leaving this at the default (~1M). Local llama.cpp sessions need it below the server context so Claude Code compacts before llama.cpp rejects the prompt. Those two needs conflict on a single global value.

Solution: a dedicated llama.cpp-scoped settings file loaded via `claude --settings <file>` (layers additively on top of `~/.claude/settings.json` — see `claude --help`), wired through a thin wrapper.

- [`home/dot_claude/settings.llama-cpp.json`](../../../../home/dot_claude/settings.llama-cpp.json) → `~/.claude/settings.llama-cpp.json` (contains only `autoCompactWindow: 200000`)
- [`home/exact_bin/executable_,claude-llama-cpp`](../../../../home/exact_bin/executable_,claude-llama-cpp) → `~/bin/,claude-llama-cpp`

The wrapper exports `ANTHROPIC_BASE_URL=http://${LLAMA_CPP_HOST:-127.0.0.1}:${LLAMA_CPP_PORT:-8080}`, sets `ANTHROPIC_API_KEY=$LLAMA_CPP_API_KEY` (defaults to `sk-no-key-required` because llama.cpp accepts unauthenticated local requests unless started with `--api-key`), and invokes `claude --settings ~/.claude/settings.llama-cpp.json --model "$CLAUDE_LLAMA_CPP_MODEL" "$@"`.

Environment overrides:

| Variable                    | Default                                 | Purpose                                                             |
| --------------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| `LLAMA_CPP_HOST`            | `127.0.0.1`                             | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_PORT`            | `8080`                                  | Same as `,llama-cpp`                                                |
| `LLAMA_CPP_API_KEY`         | `sk-no-key-required`                    | Sent as `ANTHROPIC_API_KEY` (Claude Code uses this for bearer auth) |
| `CLAUDE_LLAMA_CPP_MODEL`    | `qwen3.6-35b-a3b-q4-k-m`                | Set empty to skip `--model` injection                               |
| `CLAUDE_LLAMA_CPP_SETTINGS` | `$HOME/.claude/settings.llama-cpp.json` | Point at an alternate llama.cpp settings file                       |

`autoCompactWindow=200000` leaves ~62k headroom under the 262144-token server context for the next turn's prompt, tool outputs, and model reply.

Usage:

```bash
,claude-llama-cpp                                  # interactive session, default model
,claude-llama-cpp -p "summarize README.md"         # one-shot prompt
CLAUDE_LLAMA_CPP_MODEL=other-local-model ,claude-llama-cpp
```

Cloud Claude sessions are unaffected — plain `claude ...` still reads only `~/.claude/settings.json`, where `autoCompactWindow` stays unset so the default for `opus[1m]` applies.

## Reviewing Agent Diffs (`tuicr`)

[`tuicr`](https://github.com/agavra/tuicr) is the user-facing half of the agent loop: after the agent edits the working tree, you review the diff in a GitHub-style TUI, drop line/file/review comments, and export them as structured markdown that pastes back to the agent for a one-pass fix. It's the inverse of the `review` skill (which is the agent reviewing your diff).

Install: [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl) — `AI & LARGE LANGUAGE MODELS` section, via the `agavra/tap` Homebrew tap.

Config (theme + comment-type vocabulary): [`home/dot_config/tuicr/readonly_config.toml`](../../../../home/dot_config/tuicr/readonly_config.toml) → `~/.config/tuicr/config.toml`. Comment types are actionable categories (`issue`, `suggestion`, `question`, `nit`, `praise`); severity (CRITICAL/HIGH/MEDIUM/LOW from the review SOP) stays internal and is intentionally not encoded as a comment type.

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

- Wrapper function: `bdlocal` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl)

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

- Beads task tracking: [`docs/recipes/beads-task-tracking.md`](beads.md)
- Switching work/personal identity: [`docs/recipes/switching-work-personal-identity.md`](../../workflow/git-identity/switch-identity.md)
- Security and secrets: [`docs/categories/security-and-secrets.md`](../security-and-secrets.md)
