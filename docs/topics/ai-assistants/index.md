---
sidebar_position: 1
---

# AI Assistants

CLI assistants share operating rules, skills, read-only review profiles, and local memory tools.
Agents work inline by default and query memory on demand.
OMP's native advisor adds main-session notes; child advisors stay off.

## What is installed

| Piece               | Source                                                     | Deployed to                                                       | Page                                          |
| ------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------- |
| Global instructions | `home/readonly_AGENTS.md`                                  | `~/AGENTS.md`, linked into every harness                          | [Instructions](instructions.md)               |
| Skills              | `home/exact_dot_agents/exact_skills/`                      | `~/.agents/skills/`                                               | [Skills](skills.md)                           |
| Subagent profiles   | `k-agent-reviewer` (Claude, Pi, OMP), `k-agent-scout` (Pi) | each harness's agents dir                                         | [Subagents](subagents.md)                     |
| Knowledge base      | `,ai-kb`                                                   | `~/bin/,ai-kb`, data in `~/.local/share/ai-kb`                    | [Memory and handoffs](memory-and-handoffs.md) |
| Session handoffs    | `,handoff`                                                 | `~/bin/,handoff`, notes in `~/.local/share/agent-handoffs`        | [Memory and handoffs](memory-and-handoffs.md) |
| Behavior maps       | `,behavior-map`                                            | `~/bin/,behavior-map`, maps in `~/.local/share/k-ai-behavior-map` | [Memory and handoffs](memory-and-handoffs.md) |
| Intent cards        | `,task` and the intent-guard hooks                         | `~/bin/,task`, cards in `~/.local/share/agent-tasks`              | [Staying on the goal](staying-on-goal.md)     |
| MCP servers         | `home/.chezmoidata/mcp_servers.yaml`                       | rendered per harness                                              | [MCP servers](mcp.md)                         |
| Harness configs     | per-harness files under `home/`                            | `~/.claude`, `~/.pi`, `~/.omp`, `~/.codex`, …                     | [Tool configs](tool-configs/index.md)         |
| Local inference     | llama.cpp router and launchers                             | `~/bin/,llama-cpp`, `,*-llama-cpp`                                | [llama.cpp](llama-cpp/index.md)               |

## Harnesses

| Harness                   | Default model                    | Notes                                                            |
| ------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| Claude Code               | `claude-opus-5-5`, effort high   | `,claude-openrouter` and `,claude-llama-cpp` switch the backend  |
| Pi                        | `anthropic/claude-opus-5-5`      | `pi-subagents` with built-in agents disabled; repo profiles only |
| OMP                       | `anthropic/claude-opus-5-5:auto` | native `scout`; repo `k-agent-reviewer`                          |
| Codex                     | `gpt-6-astra`                    | `,codex`, `,codex-openrouter`, `,codex-llama-cpp`                |
| OpenCode, Crush, freebuff | per-harness config               | basic config and MCP; OpenCode also runs the intent-guard plugin |

## Principles

The [global operating rules](../../../home/readonly_AGENTS.md) define the exact scope, approval, verification, and completion gates. [Review and verification](skills.md#review-and-verification) describes the review loop, including returned findings and review baselines.

- **Inline by default.** Subagents handle broad read-only searches and independent reviews. Reviews required by a risky code or instruction change use two fresh reviewers in parallel.
- **Static verification.** Run affected unit and static checks once on the finished change, under time limits. Use source reads and isolated local runs for evidence. Live checks require the user's request, a hard timeout, and a copy when they would change external state or overwrite user data.
- **Fix before finishing.** Resolve every supported issue in scope, including low-severity findings. Review fixes and continue until a full review round is clean. Report evidence, assumptions, out-of-scope proposals, and blockers; complete available in-scope work and cleanup before reporting.

- **On-demand memory.** `,ai-kb search` when it can help; `,ai-kb remember` only for verified, reusable gotchas, or `--supersedes` to retire a stale capsule.
- **Intent card.** Before its first edit the agent writes the task's goal, reading, `Done when` items, and scope; hooks in every harness check each iteration against it ([Staying on the goal](staying-on-goal.md)).
- **Explicit handoffs.** "handoff X" writes a short note with `,handoff`; "continue X" reads it in any harness.
- **Behavior maps.** Each repo keeps a short map of critical behaviors seen from the user side; agents update only the entries their diff touches.

Related: [Reviewing agent diffs](reviewing-diffs.md).
