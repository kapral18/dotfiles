---
sidebar_position: 4
---

# Cross-harness subagents

Subagents run a self-contained task in an isolated child context window and return only a digest. That keeps heavy reads, searches, and review fan-out from bloating the parent conversation.

![Cross-harness subagent topology: shared skills feed runtime profiles, controller delegates to reviewers/live UI/auditor, and only controller acts](./assets/subagent-topology.svg)

## Two portable layers

| Layer                        | Portable? | Role                                                                     |
| ---------------------------- | --------- | ------------------------------------------------------------------------ |
| Skills (`~/.agents/skills/`) | Yes       | Cross-harness source of truth for methodology and routing                |
| Subagents                    | No        | Runtime-specific wrappers that load a skill in an isolated child context |

Every custom subagent profile is a chezmoi template that renders the shared tmux `prefix.txt` preamble before role instructions, so child contexts start with the same verification discipline as parent sessions.

## Runtime discovery

| Harness            | Subagent/profile source                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| Cursor CLI         | project `.cursor/agents/` and user `~/.cursor/agents/`; project agents have higher priority                  |
| GitHub Copilot CLI | `~/.copilot/agents/*.agent.md` and project `.github/agents/*.agent.md`; configured with `subagents.agents.*` |
| Claude Code        | `~/.claude/agents/*.md`; launched via `Task` with `subagent_type`                                            |
| Codex CLI          | `$CODEX_HOME/agents/*.toml`; launched through `multi_agent` `spawn_agent`/`wait`                             |
| Gemini CLI         | project `.gemini/agents/*.md` and user `~/.gemini/agents/*.md`; exposed as tools and forced with `@name`     |
| Amp                | Generic `Task` tool plus shared skills; no verified custom profile directory                                 |
| Pi                 | `~/.pi/agent/agents/*.md`; built-in subagents disabled to avoid name collisions                              |

Verified discovery anchors:

| Harness     | Verified surface                                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------------------------------- |
| Cursor CLI  | bundled `~/.cursor/skills-cursor/create-subagent/SKILL.md`; `cursor-agent 2026.06.15-18-00-12-6f5a2cf`                    |
| Copilot CLI | `copilot --agent <name>`, `/agent`, and `copilot help config`; version `copilot 1.0.63`                                   |
| Claude Code | `claude --agent`, `--agents`, `claude agents`, and `Task.subagent_type`; version `claude 2.1.179`                         |
| Codex CLI   | `$CODEX_HOME/agents/*.toml` plus `multi_agent.spawn_agent` / `wait`; source `openai/codex@45f603302c45`                   |
| Gemini CLI  | `.gemini/agents/*.md`, `@name` forcing, and no subagent-to-subagent calls; source `google-gemini/gemini-cli@f741d0328209` |
| Amp         | `amp skill list` and generic `Task`; no custom profile directory found                                                    |

Model identifiers are not portable. Cursor review lanes use `gpt-5.5-extra-high` and `claude-opus-4-8-xhigh`; Copilot uses `gpt-5.5` and `claude-opus-4.8` with `effortLevel: xhigh`; Pi encodes reasoning effort in model slug suffixes such as `:xhigh`.

Runtime probes confirmed project custom-agent invocation in Cursor and Copilot, Cursor controller-to-worker delegation, Copilot task subagents with explicit model overrides, both Opus IDs, and Codex `spawn_agent` / `wait`.

## Agent suite

| Agent                                       | Wraps skill            | Work it owns                                                       |
| ------------------------------------------- | ---------------------- | ------------------------------------------------------------------ |
| `agent-review`                              | `agent-review`         | Controller: route, PR-necessity gate, fan-out, live UI, audit, act |
| `review-controller` (Pi)                    | `review`               | Pi controller for PR gates, reviews, audits, fixes/drafts/verdict  |
| `review-gpt-5-5-extra-high`                 | `review`               | Read-only GPT reviewer lane                                        |
| `review-opus-4-8-xhigh-non-thinking`        | `review`               | Read-only Opus reviewer lane                                       |
| `reviewer`                                  | `review`               | Pi/Claude read-only review worker                                  |
| `review-worker`                             | `review`               | Codex read-only review worker role                                 |
| `review-gemini-pro` / `review-gemini-flash` | `review`               | Gemini reviewer lanes                                              |
| `findings-auditor`                          | `review`               | Non-trivial findings or named fix-diff audit                       |
| `live-ui-review`                            | `review`               | Verification-only live UI reviewer with screenshot handoff         |
| `researcher`                                | `research`             | Clone and inspect external GitHub source                           |
| `code-searcher`                             | `semantic-code-search` | SCSI semantic investigation / base-branch context                  |

## Review hierarchy

The review topology follows the `review` skill's role × mode matrix:

1. **PR necessity gate** runs first and blocks implementation review for other-authored or unknown-author PRs until the PR is worth reviewing.
2. **Find/judge fan-out** runs read-only reviewer lanes in parallel after any required greenlight.
3. **Live UI** runs only when UI/runtime verification is relevant and a target packet exists.
4. **Findings audit** is inline for trivial sets and delegated for non-trivial findings, disagreements, material `verification_needed`, blockers, or overengineering risk.
5. **Act** is serial and controller-owned: fix, draft, drain threads, or emit verdict.

Workers never edit files, post comments, resolve threads, or decide final action. They return candidate findings plus evidence and `verification_needed` items for the controller.

## Source paths

| Target                         | Source                                                                        | Consumed by |
| ------------------------------ | ----------------------------------------------------------------------------- | ----------- |
| `~/.cursor/agents/*.md`        | [`home/dot_cursor/exact_agents/`](../../../home/dot_cursor/exact_agents/)     | Cursor      |
| `~/.copilot/agents/*.agent.md` | [`home/dot_copilot/exact_agents/`](../../../home/dot_copilot/exact_agents/)   | Copilot     |
| `~/.claude/agents/*.md`        | [`home/dot_claude/exact_agents/`](../../../home/dot_claude/exact_agents/)     | Claude      |
| `~/.codex/agents/*.toml`       | [`home/dot_codex/exact_agents/`](../../../home/dot_codex/exact_agents/)       | Codex       |
| `~/.gemini/agents/*.md`        | [`home/dot_gemini/exact_agents/`](../../../home/dot_gemini/exact_agents/)     | Gemini      |
| `~/.pi/agent/agents/*.md`      | [`home/dot_pi/agent/exact_agents/`](../../../home/dot_pi/agent/exact_agents/) | Pi          |

## Design notes

- Profile bodies start with `prefix.txt`, then instruct the child to load the wrapped skill or runtime contract.
- Cursor/Copilot `agent-review` profiles load only the `/agent-review` skill; reviewer/auditor/live profiles load the runtime contracts, and reviewer workers load shared `review` methodology inside child contexts.
- Profiles stay generic. Domain-specific targets or rules are selected by the controller from a verified domain overlay and passed to workers as concrete packets.
- Copilot internal worker profiles are hidden from `/agent` but remain model-invocable so the controller can launch named task agents.
- Pi disables its built-in subagents because stock names overlap with custom roles. Pi also recursively exposes skills as subagents; that leakage is cosmetic and accepted because our agent names are distinct.

## Related

- [Review workflow](reviews/index.md)
- [Tool configs](tool-configs/index.md)
- [Ralph orchestrator](ralph/index.md)
