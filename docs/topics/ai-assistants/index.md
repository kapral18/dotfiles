---
sidebar_position: 1
---

# The Agentic Operating System (AI & Assistants)

This setup does not just provide you with AI chat tools; it implements an **Agentic Operating System**. This treats "how my assistants should work" as strict, version-controlled configuration that is installed alongside everything else. The goal is deterministic, verifiable behavior instead of relying on unpredictable LLM heuristics.

This page is the governance hub: the SOP entrypoints, skills, and shared workflows that apply across every tool. Each subsystem (Ralph, MCP, model registry, memory, llama.cpp, per-tool configs) has its own page — see [Subsystems](#subsystems).

![Abstract layered AI operating system: dotfiles base, terminal tools, and coordinated agent workers](./assets/agentic-os-orchestration.jpg)

At a high level, the AI layer is a set of governed routes, not a pile of prompts:

![Agentic operating system governance route: request, SOP, skill, gates, optional subagent, evidence, and gated action](./assets/agentic-governance-flow.svg)

## The Governance Layer (SOPs)

Entrypoints installed into your home directory:

| Source                                                                                              | Target                         | Notes                                  |
| --------------------------------------------------------------------------------------------------- | ------------------------------ | -------------------------------------- |
| [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md)                                       | `~/AGENTS.md`                  | The single SOP source — edit only this |
| [`home/symlink_CLAUDE.md`](../../../home/symlink_CLAUDE.md)                                         | `~/CLAUDE.md`                  | Symlink to `~/AGENTS.md`               |
| [`home/dot_gemini/symlink_GEMINI.md`](../../../home/dot_gemini/symlink_GEMINI.md)                   | `~/.gemini/GEMINI.md`          | Symlink to `~/AGENTS.md`               |
| [`home/dot_cursor/symlink_AGENTS.md`](../../../home/dot_cursor/symlink_AGENTS.md)                   | `~/.cursor/AGENTS.md`          | Symlink to `~/AGENTS.md`               |
| [`home/dot_config/opencode/symlink_AGENTS.md`](../../../home/dot_config/opencode/symlink_AGENTS.md) | `~/.config/opencode/AGENTS.md` | Symlink to `~/AGENTS.md`               |

These files are policy entrypoints; skills are installed separately. There is one real SOP file (`~/AGENTS.md`); Claude, Gemini, Cursor, and OpenCode all read symlinks that resolve to it, so the SOP is identical across every harness by construction.

Shared SOP handling rules:

- The entrypoints do not declare their own global instruction hierarchy. They define local SOP selection only: check the closest repo-local `AGENTS.md` first, then the broader home-level entrypoint, and defer to the runtime's higher-priority instruction layers when conflicts exist.
- "Questions" is scoped to information-seeking asks. Requests phrased as questions still count as action requests when the user is asking for investigation, verification, or edits.
- A mandatory compatibility gate runs before edits; see the SOP entrypoints for the exact classification, decision table, and summary-line format.
- If uncertainty remains after local inspection, probes, and any required skills, ask one direct fork-closing question.

Shared git push safety rule:

- If the user asks to push, agents must treat that as `git push --force-with-lease` (not plain `git push`).
- Agents must never auto-run `git pull`, `git pull --rebase`, `git rebase`, or `git merge` as a pre-push reconciliation step.
- If push is rejected due to divergence/non-fast-forward/lease checks, agents must stop and wait for explicit user direction.
- Canonical source: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md) (the single SOP; `~/CLAUDE.md` and `~/.gemini/GEMINI.md` are symlinks to it), and [`home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md`](../../../home/exact_dot_agents/exact_skills/exact_git/readonly_SKILL.md).

Shared runtime verification rule:

- For "is this correctly set up / working / actually being used" questions, the SOP now owns the canonical end-to-end verification rule, not just config inspection.
- Required chain: source config, rendered/applied config, runtime consumer, and a minimal safe live probe when one is possible.
- The shared rule is tracked in the single SOP: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md) (`~/CLAUDE.md` and `~/.gemini/GEMINI.md` are symlinks to it).

Shared behavioral disciplines (integrated from [`forrestchang/andrej-karpathy-skills`](https://github.com/forrestchang/andrej-karpathy-skills) without duplicating existing SOP rules):

- `2 Core Principles`: surface material assumptions and competing interpretations rather than picking silently (evidence-first from `2.1` still wins — probe locally before asking); push back when a simpler approach satisfies the stated goal.
- `3.3 Success Criteria & Verification Loops`: reframe imperative tasks as verifiable goals (test-first / reproducer-first when practical); multi-step plans must carry per-step verify checks; does not override `2.0`, `2.1`, `2.2`, or `5 Minimal edit scope`.
- `3.4 State-Machine Verification`: for stateful, parser-like, or branch-heavy behavior, build a disposable `/tmp/state-machine-verification/<pwd>/<topic>/<slug>/` harness before calling the change final; `<pwd>` scopes to the worktree, `<topic>` separates unrelated work in long-lived/default checkouts, and `<slug>` names the behavior under test. Each harness includes a manifest so agents reuse existing state-machine work only when target, branch/base/head refs, requested behavior, and compatibility intent still match.
- `5 Code Quality`: simplicity discipline (no speculative abstractions/flexibility/impossible-scenario error handling; senior-engineer test); artifact necessity (prove behavior is missing without a new artifact before adding it unless explicitly requested); dead-code handling (remove only orphans your own changes created; mention, don't delete pre-existing dead code unless asked).
- Canonical source: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md) (the single SOP; `~/CLAUDE.md` and `~/.gemini/GEMINI.md` are symlinks to it), and the dotfiles repo-local [`AGENTS.md`](../../../AGENTS.md).

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

Current skills (36; sorted by name; routing from each skill’s `disable-model-invocation` frontmatter):

| Skill                         | Use when                                                                                                                                                         | Routing | Gated to       |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | -------------- |
| `agent-review`                | Multi-agent review orchestration: route, PR-necessity gate, reviewer fan-out, live UI, findings audit, reconciliation, act                                       | auto    |                |
| `ai-kb`                       | Recall or persist durable cross-session knowledge (gotchas, decisions, patterns, facts) via `,ai-kb`; not ephemeral `/tmp/specs` context or code search          | auto    |                |
| `buildkite`                   | Buildkite CI status, builds, logs, pipelines, or a `buildkite.com` URL (use `bk` CLI; do not fetch URLs in-browser)                                              | auto    | elastic org    |
| `cli-skills`                  | Creating or upgrading a CLI tool skill                                                                                                                           | auto    |                |
| `compose-issue`               | Drafting an issue title and body as text before create/edit (no `gh` side effects)                                                                               | auto    |                |
| `compose-pr`                  | Drafting a PR title and body as text before create/edit (no `gh` side effects)                                                                                   | auto    |                |
| `communication`               | Canonical tone/style for any human-directed content (PR/issue threads + bodies, Slack, email, chat, release/commit messages); referenced by other skills         | auto    |                |
| `elastic-domain`              | Elastic/Kibana domain overlay layered onto generic skills: PR body/footer/labels, ownership, bots, Buildkite, Kibana live UI target packet                       | auto    | elastic org    |
| `git`                         | Local git operations (branch, commit, push, rebase, merge, conflicts); not GitHub mutations or worktrees                                                         | auto    |                |
| `github`                      | Any GitHub mutation via `gh` (PRs, issues, comments, reviews, labels, releases, merges); not draft-only or review analysis                                       | auto    |                |
| `google-workspace`            | Gmail / Drive / Calendar / Admin / Docs / Sheets via `gws` CLI                                                                                                   | auto    |                |
| `improve-branch`              | One evidence-backed improvement proposal for the current branch, PR, or issue goal                                                                               | manual  |                |
| `improve-codebase`            | One evidence-backed improvement proposal for the whole codebase                                                                                                  | manual  |                |
| `improve-local`               | One evidence-backed improvement proposal for local changes                                                                                                       | manual  |                |
| `improve-targeted`            | One evidence-backed improvement proposal for a targeted dir, module, or component                                                                                | manual  |                |
| `interview-me`                | Reverse-interview until intent is fully clear (not what the user thinks they should want)                                                                        | manual  |                |
| `jscpd`                       | Duplicate-code detection during refactor, cleanup, or DRY work                                                                                                   | auto    |                |
| `kbn-backport`                | Run an e2e Kibana backport for a PR (asks for the PR number if missing): compute targets, drive the interactive tool in a tmux pane, resolve conflicts, open PRs | manual  | elastic/kibana |
| `kibana-console-monaco`       | Automate or test the Kibana Dev Tools Console Monaco editor in a real browser                                                                                    | auto    | elastic/kibana |
| `kibana-labels-propose`       | Propose labels, backports, and version targeting for a Kibana PR/issue (propose only; no posting)                                                                | auto    | elastic/kibana |
| `kibana-management-ownership` | Determine ownership and reviewer targeting for Kibana changes via CODEOWNERS; propose-only                                                                       | auto    | elastic/kibana |
| `knip`                        | Unused files, dependencies, or exports in JS/TS projects                                                                                                         | auto    |                |
| `letsfg`                      | Flight search via local LetsFG CLI (fares, routes, dates; direct booking URLs)                                                                                   | auto    |                |
| `light-review`                | Fast in-place audit of low-risk self-authored changes; shares judging core without mandatory PR/SCSI/GitHub machinery                                            | auto    |                |
| `nano-banana`                 | Generate an image from a text prompt via `,nano-banana` (Gemini image model)                                                                                     | auto    |                |
| `playwriter`                  | Browser control via Playwriter when "playwriter" is explicitly mentioned                                                                                         | auto    |                |
| `present-pr`                  | Build and open a self-contained HTML scrollytelling walkthrough of a PR or local diff (not code review)                                                          | manual  |                |
| `ralph`                       | Drive `,ralph go` / tmux Ralph (spawn, verify, attach, replan, orchestrator roles)                                                                               | auto    |                |
| `research`                    | Investigate a third-party repo by cloning and reading source (GitHub URL or "how does X work")                                                                   | auto    |                |
| `review`                      | Review local changes or a PR; continue review, address threads, recheck PR changes                                                                               | auto    |                |
| `sem`                         | Entity-level git diff, blame, impact, or token-budgeted context via `sem` CLI                                                                                    | auto    |                |
| `semantic-code-search`        | SCSI semantic search, base-branch context, index selection, or another skill requires semantic base context                                                      | auto    |                |
| `standup`                     | `/standup` or prepare/post a #kibana-management standup from Slack + GitHub since last post (post only after approval)                                           | manual  | elastic/kibana |
| `walkthrough`                 | Interactive codebase exploration: trace flows, map components, render architecture diagrams                                                                      | manual  |                |
| `weave`                       | Entity-level merge preview or conflict resolution via `weave` CLI                                                                                                | auto    |                |
| `worktrees`                   | `,w` / `,gh-worktree` worktree create, switch, list, prune, or checkout PR/issue locally                                                                         | auto    |                |

Worktree note for agents: when creating a worktree from a GitHub issue, prefer `,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>` so repo resolution/bootstrap happens before the lower-level `,w issue` metadata and branch creation flow.

PR/issue composition hygiene:

- `compose-pr`, `compose-issue`, and `github` sanitize public GitHub text before drafting or posting.
- When output depends on existing PR/issue/comment context, `compose-pr`, `compose-issue`, and `github` reuse the review skill's GitHub Context Intake + Reference Resolution gate.
- When context is contested or historically unclear, those skills also reuse the bounded Ambient Topic Exploration pass across related GitHub issues/PRs, GitHub Discussions, and available Slack MCP public/team-channel evidence.
- PR/issue bodies must avoid session-specific local references such as private hostnames, non-standard local domains, absolute workspace paths, `/tmp/...` files, browser automation session names, and local usernames.
- Repro-driven PRs must include portable local reproduction steps in the test plan, not only the agent's local validation notes. Prefer generic setup such as `local app`, `http://localhost:<port>`, or explicit role/user creation steps that another reviewer can run.
- Domain-specific PR/issue rules live in overlay skills instead of generic compose/GitHub skills. `elastic-domain` is the Elastic/Kibana overlay: it routes PR footers, release-note/label proposal, Kibana ownership, known bot allowlists, Buildkite handling, and the Kibana live-UI target packet.

Manual `present-pr` hygiene:

- Before filling the HTML template, write a compact authoring preflight: thesis, audience, full file/hunk role ledger, Act II causal chain, source anchors, medium choices, image list, and verification checklist.
- Include an introduced-concepts inventory and review-readiness map in that preflight: mental model, layered explanation, topology groups, load-bearing line index, invariants/non-changes, risk-attention map, GitHub handoff order, source anchors, sidebar labels, and chosen teaching media.
- Reuse prior `/tmp/specs` or `/tmp/present-pr` evidence when the PR/head SHA still matches; refresh only PR metadata/comments that can change.
- Default to one generated image for the Act I contrast. Use deterministic HTML/diff beats for exact labels, symbol lists, and code-line insights; cut label-heavy generated images after one bad regeneration.
- The template scaffold is resized to the preflight, not treated as a quota; every introduced concept appears in the concept primer and left sidebar, the readiness map plus Act I-IV remain reachable from the fixed sidebar or fallback rail, every sidebar note follows a concept or readiness/story link, and every changed file/group appears exactly once in Act IV with `primary`, `supporting`, `guardrail`, or `cleanup` role semantics.
- The page must end with an ordered GitHub handoff: primary hunks first, guardrails/tests second, supporting/mechanical files last.
- Concept cards stay in a vertical anchor stack; every concept sidebar block must visibly navigate to its own card and activate its matching note.
- Run cheap static checks before Playwriter: no real `{{TOKEN}}` placeholders, all referenced `nb-*` images exist with no unreferenced `nb-*` leftovers, code snippets are escaped, concept/sidebar references are consistent, and no beat repeats the same idea across prose, image, and card.
- Keep browser verification compact: Playwriter should emit JSON assertions for page/console errors, image loads, concept sidebar/right notes geometry, act-rail geometry on narrower desktop widths, concept-note interactions, and reveal counts; use snapshots only on failure or tight filters.

Always-on rule source:

- The SOP entrypoints are the only canonical always-on mechanism for assistant behavior.
- Do not encode mandatory every-prompt rules as skills; OpenCode skills are on-demand, not guaranteed every turn.
- Keep mandatory completeness and no-guessing rules in the single SOP: [`home/readonly_AGENTS.md`](../../../home/readonly_AGENTS.md) (`~/CLAUDE.md` and `~/.gemini/GEMINI.md` are symlinks to it).

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
- [Tool configs](tool-configs.md) — Cursor CLI, profile-based merging, per-assistant settings (Claude/Gemini/Pi/Codex/OpenCode/Copilot/Amp), and the RTK token-optimization layer.
- [llama.cpp local inference](llama-cpp.md) — local GGUF server, model router, and the Claude/Codex/OpenCode/Pi launchers.
- [Reviewing agent diffs](reviewing-diffs.md) — the `tuicr` loop for feeding structured feedback back to an agent.

## Safety Boundaries

- Keep assistant instructions declarative and repo-local.
- Keep secrets in `pass` (or local private config), not in tracked markdown.
- Validate generated automation commands before running state-changing actions.
- Treat RTK-compacted command output as a recoverable index, not the full output: when a result shows `[full output: …]` or `… +N more`, fetch the full output before relying on it (`~/CLAUDE.md` §2.4; [RTK wiring](tool-configs.md#token-optimization-rtk)).

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
