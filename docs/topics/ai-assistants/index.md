---
sidebar_position: 1
---

# AI Assistants

The AI layer is a short global instruction file, a set of skills, a few read-only subagent profiles, and two small CLIs.
Agents work inline by default. Nothing is injected per turn: no hooks, no automatic memory recall, no advisor.

## What is installed

| Piece               | Source                                                     | Deployed to                                                       | Page                                          |
| ------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------- |
| Global instructions | `home/readonly_AGENTS.md`                                  | `~/AGENTS.md`, linked into every harness                          | [Instructions](instructions.md)               |
| Skills              | `home/exact_dot_agents/exact_skills/`                      | `~/.agents/skills/`                                               | [Skills](skills.md)                           |
| Subagent profiles   | `k-agent-reviewer` (Claude, Pi, OMP), `k-agent-scout` (Pi) | each harness's agents dir                                         | [Subagents](subagents.md)                     |
| Knowledge base      | `,ai-kb`                                                   | `~/bin/,ai-kb`, data in `~/.local/share/ai-kb`                    | [Memory and handoffs](memory-and-handoffs.md) |
| Session handoffs    | `,handoff`                                                 | `~/bin/,handoff`, notes in `~/.local/share/agent-handoffs`        | [Memory and handoffs](memory-and-handoffs.md) |
| Behavior maps       | `,behavior-map`                                            | `~/bin/,behavior-map`, maps in `~/.local/share/k-ai-behavior-map` | [Memory and handoffs](memory-and-handoffs.md) |
| MCP servers         | `home/.chezmoidata/mcp_servers.yaml`                       | rendered per harness                                              | [MCP servers](mcp.md)                         |
| Harness configs     | per-harness files under `home/`                            | `~/.claude`, `~/.pi`, `~/.omp`, `~/.codex`, …                     | [Tool configs](tool-configs/index.md)         |
| Local inference     | llama.cpp router and launchers                             | `~/bin/,llama-cpp`, `,*-llama-cpp`                                | [llama.cpp](llama-cpp/index.md)               |

## Harnesses

| Harness                                | Default model                    | Notes                                                            |
| -------------------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| Claude Code                            | `claude-sonnet-5-5`, effort high | `,claude-openrouter` and `,claude-llama-cpp` switch the backend  |
| Pi                                     | `openai-codex/gpt-6.1-sol`       | `pi-subagents` with built-in agents disabled; repo profiles only |
| OMP                                    | `openai-codex/gpt-6.1-sol:high`  | native `scout`; repo `k-agent-reviewer`                          |
| Codex                                  | `gpt-6.1-sol`                    | `,codex`, `,codex-openrouter`, `,codex-llama-cpp`                |
| OpenCode, Antigravity, Crush, freebuff | per-harness config               | basic config and MCP only; no custom flows                       |

## Principles

- **Inline by default.** A subagent rebuilds context at full price, so subagents only do broad read-only searches or a review: one automatic review of a risky finished change (including rule changes in the SOP, skills, and `k-agent-*` profiles), or one the user asks for.
- **Bounded verification.** Checks run once on the finished change. Before reporting, the agent runs the change once on a realistic target, tests state-changing operations against each other, and lists each claim with its evidence in a `Checked:` line; the review gets those results. An independent review gets one fix round and one re-check, then stops (`k-review` verify mode). A fix that adds a file or rewrites a function's body (not edits lines in it) gets one review of its diff only, and that review's findings stay open. The medium threshold applies to the agent's report, not to a reviewer's: reviewers report every severity.
- **On-demand memory.** `,ai-kb search` when it can help; `,ai-kb remember` only for verified, reusable gotchas.
- **Explicit handoffs.** "handoff X" writes a short note with `,handoff`; "continue X" reads it in any harness.
- **Behavior maps, not diagrams.** Each repo keeps a short map of critical behaviors seen from the user side; agents update only the entries their diff touches.

Related: [Reviewing agent diffs](reviewing-diffs.md), [Elastic and Kibana overlay](elastic-and-kibana.md).
