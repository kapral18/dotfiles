---
sidebar_position: 4
---

# Cross-harness subagents

Subagents run a self-contained task in an isolated child context window and return only a digest. That keeps heavy reads, searches, and review fan-out from bloating the parent conversation.

![Cross-harness subagent topology: shared skills feed runtime profiles, controller delegates to angle lanes/fresh-eyes/adversarial verifier/live UI/auditor, and only controller acts](./assets/subagent-topology.svg)

## Mental model

There are two portable layers:

| Layer                        | Portable? | Role                                                                     |
| ---------------------------- | --------- | ------------------------------------------------------------------------ |
| Skills (`~/.agents/skills/`) | Yes       | Cross-harness source of truth for methodology and routing                |
| Subagents                    | No        | Runtime-specific wrappers that load a skill in an isolated child context |

Every custom subagent profile is a chezmoi template that renders the shared tmux `prefix.txt` preamble before role instructions. Child contexts therefore start with the same verification discipline as parent sessions.

The role body itself is single-sourced. Each per-tool profile is a thin shim: per-tool frontmatter (`model`, `tools`, `sandbox`) + the `prefix.txt` preamble + `Load and follow ~/.agents/skills/k-agent-review/references/<role>.md`.

## Using it

Runtime discovery is harness-specific:

| Harness            | Subagent/profile source                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| Cursor CLI         | project `.cursor/agents/` and user `~/.cursor/agents/`; project agents have higher priority                  |
| GitHub Copilot CLI | `~/.copilot/agents/*.agent.md` and project `.github/agents/*.agent.md`; configured with `subagents.agents.*` |
| Claude Code        | `~/.claude/agents/*.md`; launched via `Task` with `subagent_type`                                            |
| Codex CLI          | `$CODEX_HOME/agents/*.toml`; launched through `multi_agent` `spawn_agent`/`wait`                             |
| Gemini CLI         | project `.gemini/agents/*.md` and user `~/.gemini/agents/*.md`; exposed as tools and forced with `@name`     |
| Pi                 | `~/.pi/agent/agents/*.md`; built-in subagents disabled to avoid name collisions                              |

Verified discovery anchors:

| Harness     | Verified surface                                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------------------------------- |
| Cursor CLI  | bundled `~/.cursor/skills-cursor/create-subagent/SKILL.md`; `cursor-agent 2026.06.15-18-00-12-6f5a2cf`                    |
| Copilot CLI | `copilot --agent <name>`, `/agent`, and `copilot help config`; version `copilot 1.0.63`                                   |
| Claude Code | `claude --agent`, `--agents`, `claude agents`, and `Task.subagent_type`; version `claude 2.1.179`                         |
| Codex CLI   | `$CODEX_HOME/agents/*.toml` plus `multi_agent.spawn_agent` / `wait`; source `openai/codex@45f603302c45`                   |
| Gemini CLI  | `.gemini/agents/*.md`, `@name` forcing, and no subagent-to-subagent calls; source `google-gemini/gemini-cli@f741d0328209` |

Profile `model` frontmatter is rendered from the `agent_review_models` registry. See [Model registry](model-registry.md) for policy and [Agent-review topology](reviews/agent-review-topology.md) for review-flow usage.

Pi encodes reasoning effort in model slug suffixes such as `:xhigh` on its per-task registry value.

Runtime probes confirmed project custom-agent invocation in Cursor and Copilot, Copilot task subagents with explicit model overrides, and Codex `spawn_agent` / `wait`.

Cursor source supports custom subagent types, but the model-facing Task schema can expose only generic types in some runs. Generic or fallback launches pass the registry value as a profile-equivalent model when the role has no usable profile frontmatter, and the adversarial verifier passes the explicitly resolved cross-family id.

## Agent suite

The delegated-subagent contract for every role lives once under `k-agent-review/references/`, except where noted below. That contract loads the owning skill (`k-review`, `k-light-review`, `k-research`, `k-semantic-code-search`) in turn.

`fresh-eyes` is the blind clarity lane: it deliberately loads no skill and launches through a generic task. Only Pi carries a thin `fresh-eyes` profile, because Pi launches subagents solely through named profiles.

The "Loads contract" column is the `k-agent-review/references/<role>.md` file the profile delegates to:

| Agent                                     | Loads contract                         | Work it owns                                                                            |
| ----------------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------- |
| `k-agent-review`                          | `k-agent-review/SKILL`                 | Controller: route, PR-necessity gate, fan-out, live UI, audit, act                      |
| `review-controller` (Pi)                  | `k-review/SKILL`                       | Pi controller for PR gates, reviews, audits, fixes/drafts/verdict                       |
| `review-worker`                           | `reviewer-worker`                      | Registry-model angle lane (Cursor/Copilot/Codex/Gemini)                                 |
| `reviewer`                                | `reviewer-worker`                      | Pi/Claude read-only angle lane (registry: default/inherit)                              |
| `fresh-eyes` (Pi only; generic elsewhere) | `fresh-eyes`                           | Blind zero-context clarity lane                                                         |
| `adversarial-verifier`                    | `adversarial-verifier`                 | Cross-family refutation over merged candidates                                          |
| `pr-necessity-auditor`                    | `pr-necessity-auditor`                 | Blocking PR necessity / intent gate                                                     |
| `findings-auditor`                        | `findings-auditor`                     | Non-trivial findings or named fix-diff audit                                            |
| `live-ui-review`                          | `live-ui-review`                       | Verification-only live UI reviewer; screenshot handoff required for feedback candidates |
| `post-review`                             | `post-review`                          | Four-dimension hygiene audit of a review's fix diff                                     |
| `criteria-verifier`                       | `k-build/references/criteria-verifier` | `/build` refutation lane over the criteria ledger + scope audit                         |
| `change-auditor`                          | `change-auditor`                       | Proportional-depth audit of a self-authored changeset                                   |
| `researcher`                              | `researcher`                           | Clone and inspect external GitHub source                                                |
| `code-searcher`                           | `code-searcher`                        | SCSI semantic investigation / base-branch context                                       |

## Reference and wiring

Source paths:

| Target                         | Source                                                                                      | Consumed by |
| ------------------------------ | ------------------------------------------------------------------------------------------- | ----------- |
| `~/.cursor/agents/*.md`        | [`home/dot_cursor/exact_agents/`](../../../home/dot_cursor/exact_agents/)                   | Cursor      |
| `~/.copilot/agents/*.agent.md` | [`home/private_dot_copilot/exact_agents/`](../../../home/private_dot_copilot/exact_agents/) | Copilot     |
| `~/.claude/agents/*.md`        | [`home/dot_claude/exact_agents/`](../../../home/dot_claude/exact_agents/)                   | Claude      |
| `~/.codex/agents/*.toml`       | [`home/dot_codex/exact_agents/`](../../../home/dot_codex/exact_agents/)                     | Codex       |
| `~/.gemini/agents/*.md`        | [`home/dot_gemini/exact_agents/`](../../../home/dot_gemini/exact_agents/)                   | Gemini      |
| `~/.pi/agent/agents/*.md`      | [`home/dot_pi/agent/exact_agents/`](../../../home/dot_pi/agent/exact_agents/)               | Pi          |

Not every harness ships every profile:

- Cursor, Copilot, and Claude carry a `k-agent-review` controller.
- Pi carries `review-controller`.
- Codex and Gemini ship only worker/verifier/auditor lanes, so the controller role stays in the interactive session.

The `/build` flow's `criteria-verifier` profile follows the same shim pattern with its contract under `k-build/references/criteria-verifier.md`, using the same `agent_review_models` verifier model.

Claude carries no profile for `criteria-verifier`. This follows the same convention as `adversarial-verifier`: the lane runs degraded on the session model there.

## Review hierarchy

The phase order these profiles serve — necessity gate → angle fan-out → adversarial verification → live UI → findings audit → controller act — is owned by [Agent-review topology](reviews/agent-review-topology.md). This page only maps profiles to harnesses.

Workers never edit files, post comments, resolve threads, or decide final action. They return candidate findings plus evidence and `verification_needed` items for the controller ledger.

## Design notes

- Profile bodies start with `prefix.txt`, then instruct the child to load the wrapped skill or runtime contract.
- Cursor/Copilot `k-agent-review` profiles load only the `/agent-review` skill.
- Reviewer/auditor/live profiles load the runtime contracts, and reviewer workers load shared `k-review` methodology inside child contexts.
- Cursor profiles are real runtime shims, not dead files: Cursor loads `.cursor/agents`, and its internal Task protocol has a custom subagent-name field.
- Whether the controller can address those profiles depends on the active model-facing Task schema.
- Profiles stay generic. Domain-specific targets or rules are selected by the controller from a verified domain overlay and passed to workers as concrete packets.
- Hard runtime read-only flags are not the review safety boundary. Review/audit profile shims keep shell-capable permissions so workers can run safe verification commands; the shared role contracts enforce behavior-level read-only/no-mutation.
- Copilot internal worker profiles are hidden from `/agent` but remain model-invocable so the controller can launch named task agents.
- Pi disables its built-in subagents because stock names overlap with custom roles.
- Pi also recursively exposes skills as subagents; that leakage is cosmetic and accepted because our agent names are distinct.
- Only genuinely harness-specific notes, such as "Claude subagents cannot spawn subagents", stay inline.
- Cursor and Copilot are the canonical shim shape; the other harnesses follow it.

## Related

- [Review workflow](reviews/index.md)
- [Tool configs](tool-configs/index.md)
- [Palantír orchestrator](palantir.md)
