---
sidebar_position: 1
---

# The Agentic Operating System (AI & Assistants)

This setup does not just provide you with AI chat tools; it implements an **Agentic Operating System**. This treats "how my assistants should work" as strict, version-controlled configuration that is installed alongside everything else. The goal is deterministic, verifiable behavior instead of relying on unpredictable LLM heuristics.

This page is the governance hub: the SOP entrypoints, skills, and shared workflows that apply across every tool. Each subsystem (Ralph, MCP, model registry, memory, llama.cpp, per-tool configs) has its own page — see [Subsystems](#subsystems).

## The Governance Layer (SOPs)

Entrypoints installed into your home directory:

| Source                                                                              | Target                | Notes                    |
| ----------------------------------------------------------------------------------- | --------------------- | ------------------------ |
| [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md)                       | `~/AGENTS.md`         | Primary SOP              |
| [`home/readonly_CLAUDE.md`](../../../home/readonly_CLAUDE.md)                       | `~/CLAUDE.md`         | Claude-specific SOP      |
| [`home/dot_gemini/readonly_GEMINI.md`](../../../home/dot_gemini/readonly_GEMINI.md) | `~/.gemini/GEMINI.md` | Gemini-specific SOP      |
| [`home/dot_cursor/symlink_AGENTS.md`](../../../home/dot_cursor/symlink_AGENTS.md)   | `~/.cursor/AGENTS.md` | Symlink to `~/AGENTS.md` |

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
- Canonical sources: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../home/readonly_CLAUDE.md), [`home/dot_gemini/readonly_GEMINI.md`](../../../home/dot_gemini/readonly_GEMINI.md), and [`home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md`](../../../home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md).

Shared runtime verification rule:

- For "is this correctly set up / working / actually being used" questions, the SOP now owns the canonical end-to-end verification rule, not just config inspection.
- Required chain: source config, rendered/applied config, runtime consumer, and a minimal safe live probe when one is possible.
- The shared rule is tracked in: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../../home/dot_gemini/readonly_GEMINI.md).

Shared behavioral disciplines (integrated from [`forrestchang/andrej-karpathy-skills`](https://github.com/forrestchang/andrej-karpathy-skills) without duplicating existing SOP rules):

- `2 Core Principles`: surface material assumptions and competing interpretations rather than picking silently (evidence-first from `2.1` still wins — probe locally before asking); push back when a simpler approach satisfies the stated goal.
- `3.3 Success Criteria & Verification Loops`: reframe imperative tasks as verifiable goals (test-first / reproducer-first when practical); multi-step plans must carry per-step verify checks; does not override `2.0`, `2.1`, `2.2`, or `5 Minimal edit scope`.
- `3.4 State-Machine Verification`: for stateful, parser-like, or branch-heavy behavior, build a disposable `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/` harness before calling the change final; `<pwd>` scopes to the worktree, `<topic>` separates unrelated work in long-lived/default checkouts, and `<slug>` names the behavior under test. Each harness includes a manifest so agents reuse existing state-machine work only when target, branch/base/head refs, requested behavior, and compatibility intent still match.
- `5 Code Quality`: simplicity discipline (no speculative abstractions/flexibility/impossible-scenario error handling; senior-engineer test); artifact necessity (prove behavior is missing without a new artifact before adding it unless explicitly requested); dead-code handling (remove only orphans your own changes created; mention, don't delete pre-existing dead code unless asked).
- Canonical sources: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../home/readonly_CLAUDE.md), [`home/dot_gemini/readonly_GEMINI.md`](../../../home/dot_gemini/readonly_GEMINI.md), and the dotfiles repo-local [`AGENTS.md`](../../../AGENTS.md).

## Skills Layout

All routable files live under `~/.agents/skills/`. Each skill folder contains a `SKILL.md` entrypoint (and optional `references/` for sub-modes).

Source of truth (this repo, chezmoi-managed):

- [`home/exact_dot_agents/exact_skills/`](../../../home/exact_dot_agents/exact_skills/) -> `~/.agents/skills/`

Entry contract standard:

- Each skill should make four things obvious near the top: `Use when`, `Do not use`, `First actions`, and `Output`.
- The `description` frontmatter field is the primary routing signal — agents use it to decide whether to load the skill. Keep it concise, specific, and include non-obvious trigger words.
- For manual-only skills with `disable-model-invocation: true`, the description is catalog metadata rather than an automatic routing trigger.
- Skills gated to specific repos (e.g. elastic-only) must state the constraint in the `description` so agents skip them early.
- The goal is to remove implied routing and implied next steps so the agent has less room to "remember roughly" and skip the file.

Current skills:

| Skill                              | Use when                                                                                                           | Gated to       |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------- |
| `review`                           | Reviewing changes, continuing a review, addressing threads, rechecking PR changes                                  |                |
| `github`                           | Any GitHub mutation (PRs, issues, comments, reviews, labels, releases, merges)                                     |                |
| `git`                              | Any local git operation (branching, committing, pushing, rebasing, merging, conflicts)                             |                |
| `research`                         | Investigating a third-party project/library/tool by cloning its GitHub repo                                        |                |
| `walkthrough`                      | Explore codebase flows, map component relationships, render diagrams (manual only)                                 |                |
| `cli-skills`                       | Creating or upgrading CLI tool skills                                                                              |                |
| `letsfg`                           | Searching flight tickets/fares through the local LetsFG CLI with direct booking URLs                               |                |
| `semantic-code-search`             | Semantic search, base-branch context, or when another skill requires SCSI                                          |                |
| `google-workspace`                 | Gmail / Drive / Calendar / Admin / Docs / Sheets via `gws` CLI                                                     |                |
| `worktrees`                        | Worktree routing and operations (`,gh-worktree` for repo bootstrap/routing, `,w` for in-repo worktree actions)     |                |
| `compose-pr`                       | Drafting a PR title and body as text (before creating/editing a PR)                                                |                |
| `compose-issue`                    | Drafting an issue title and body as text (before creating/editing an issue)                                        |                |
| `buildkite`                        | Checking build status, triggering builds, reading logs, debugging CI failures                                      | elastic org    |
| `kibana-labels-propose`            | Proposing labels/backports/version targeting when composing or creating a Kibana PR                                | elastic/kibana |
| `kibana-console-monaco`            | Automating/testing the Kibana Dev Tools Console editor via Playwright                                              | elastic/kibana |
| `kbn-backport-conflict-resolution` | Manually resolving Kibana backport cherry-pick conflicts, validating, staging, and stopping                        | elastic/kibana |
| `playwriter`                       | Controlling Chrome browser via Playwriter (explicit mention only)                                                  |                |
| `beads`                            | Persisting work in the beads DB (explicit mention of beads/bdlocal/BEADS_DIR only)                                 |                |
| `knip`                             | Finding unused files, dependencies, and exports in JS/TS projects                                                  |                |
| `jscpd`                            | Detecting duplicates during refactoring, code cleanup, or DRY improvement                                          |                |
| `improve-codebase`                 | Suggest the single smartest addition to the current codebase                                                       |                |
| `improve-local`                    | Suggest the single smartest addition to the local changes                                                          |                |
| `improve-branch`                   | Suggest the single smartest addition for the current branch/PR/issue                                               |                |
| `improve-targeted`                 | Suggest the single smartest addition to a targeted part of the codebase (specific dir, module, or component)       |                |
| `ralph`                            | Drive the Ralph orchestrator (planner/executor/reviewer/re-reviewer with self-healing) via `,ralph go` and tmux UX |                |

Worktree note for agents: when creating a worktree from a GitHub issue, prefer `,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>` so repo resolution/bootstrap happens before the lower-level `,w issue` metadata and branch creation flow.

PR/issue composition hygiene:

- `compose-pr`, `compose-issue`, and `github` sanitize public GitHub text before drafting or posting.
- PR/issue bodies must avoid session-specific local references such as private hostnames, non-standard local domains, absolute workspace paths, `/tmp/...` files, browser automation session names, and local usernames.
- Repro-driven PRs must include portable local reproduction steps in the test plan, not only the agent's local validation notes. Prefer generic setup such as `local Kibana`, `http://localhost:5601`, or explicit role/user creation steps that another reviewer can run.

Always-on rule source:

- The SOP entrypoints are the only canonical always-on mechanism for assistant behavior.
- Do not encode mandatory every-prompt rules as skills; OpenCode skills are on-demand, not guaranteed every turn.
- Keep mandatory completeness and no-guessing rules in: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../../home/readonly_CLAUDE.md), and [`home/dot_gemini/readonly_GEMINI.md`](../../../home/dot_gemini/readonly_GEMINI.md).

## Source-First Research

- Explicit external repo-inspection requests now route to the same source-first skill instead of a separate variant.
- The research skill now requires: resolve repo/ref first, then inspect the checked out source locally.
- Source-first research now resolves the target ref before inspecting code.
- Use the default branch only for current/latest behavior questions.
- For version-, branch-, tag-, or commit-specific questions, inspect that exact ref instead of defaulting to latest upstream.

## Core Workflow: Change A Skill

1. Edit files under:

- [`home/exact_dot_agents/exact_skills/`](../../../home/exact_dot_agents/exact_skills/)

1. Apply and verify:

```bash
chezmoi diff
chezmoi apply
ls -la ~/.agents/skills
```

## Subsystems

The agentic layer is split into focused pages:

- [Review workflow](reviews.md) — how the `review` skill reviews your code (base context, truth-validation loop, reply style, router, publication gate).
- [Agent memory](knowledge-base.md) — hook memory (`/tmp/specs`, `,agent-memory`) and the durable AI knowledge base (`,ai-kb`).
- [Ralph orchestrator](ralph.md) — the `,ralph go` planner/executor/reviewer/re-reviewer loop, roles, and tmux control plane.
- [MCP servers](mcp.md) — the canonical `mcp_servers.yaml` registry and per-tool generation.
- [Model registry & routing](model-registry.md) — `ai_models.yaml`, per-tool model generation, and LiteLLM.
- [Tool configs](tool-configs.md) — Cursor CLI, profile-based merging, and per-assistant settings (Claude/Gemini/Pi/Codex/OpenCode/Amp).
- [llama.cpp local inference](llama-cpp.md) — local GGUF server, model router, and the Claude/Codex/OpenCode/Pi launchers.
- [Reviewing agent diffs](reviewing-diffs.md) — the `tuicr` loop for feeding structured feedback back to an agent.
- [Beads task tracking](beads.md) — per-repo task tracking with `bd`/`bdlocal`.

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

- [Switching work/personal identity](../workflow/git-identity/switch-identity.md)
- [Security and secrets](../security/security-and-secrets.md)
- [Reference map](../../reference/reference-map.md) — every AI component and the file that drives it
