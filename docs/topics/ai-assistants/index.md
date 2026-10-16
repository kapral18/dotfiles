---
sidebar_position: 1
---

# AI Assistants

The AI layer is a short global instruction file, a set of skills, a few read-only subagent profiles, and two small CLIs.
Agents work inline by default. Memory recall is manual.
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

| Harness                   | Default model                   | Notes                                                            |
| ------------------------- | ------------------------------- | ---------------------------------------------------------------- |
| Claude Code               | `claude-opus-5-5`, effort high  | `,claude-openrouter` and `,claude-llama-cpp` switch the backend  |
| Pi                        | `openai-codex/gpt-6.1-sol`      | `pi-subagents` with built-in agents disabled; repo profiles only |
| OMP                       | `openai-codex/gpt-6.1-sol:high` | native `scout`; repo `k-agent-reviewer`                          |
| Codex                     | `gpt-6.1-sol`                   | `,codex`, `,codex-openrouter`, `,codex-llama-cpp`                |
| OpenCode, Crush, freebuff | per-harness config              | basic config and MCP; OpenCode also runs the intent-guard plugin |

## Principles

- **Inline by default.** A subagent rebuilds context at full price, so subagents only do broad read-only searches, a review the user asks for, or automatic review rounds (two parallel reviewers each) of a risky finished change (including rule changes in the SOP, skills, and `k-agent-*` profiles), each with up to three fix-diff reviews, until a round is clean or three rounds have run.
- **Bounded verification.** Checks run once on the finished change. Before reporting, the agent runs the change once on a realistic target, tests state-changing operations against each other and against edge inputs (with the real command, on a copy, where a test fake replaces it), and lists each claim with its evidence in a `Checked:` line; the review gets those results. An independent review (two reviewers in parallel, on the whole task change, or on the diff since the last review's baseline for a later change in the same task) is followed by a bounded fix loop: the agent fixes every supported finding, and one reviewer checks each fix diff (a wording-only fix gets none), again while a supported medium or higher finding remains, for at most three fix-diff reviews; a cause that comes back at the same place gets a read-only investigation and one more fix; a full round that found a medium or higher finding is followed by another, reporting only new findings, until one finds none, for at most three full rounds (`k-review` verify mode). Findings of the last review are still fixed, and fixes that are not wording-only are marked "(unreviewed)" in `Checked:`; a cause that returns twice goes under `Open:`. The agent applies fixes it checked against source, inside its write scope and `k-review` Fix Scope, without asking. Done means every known in-scope issue is fixed, whatever its severity. Before reporting, the agent does every in-scope step that it can still do now, that the request named or that is reversible and changes nothing outside this machine the request did not name, and that needs no §5 approval and is not a review round past the `k-review` caps; the report has no slot for doable work: `Proposed:` holds only out-of-scope defects and actions, and `Open:` only items with a blocker the agent cannot remove.
- **On-demand memory.** `,ai-kb search` when it can help; `,ai-kb remember` only for verified, reusable gotchas.
- **Intent card.** Before its first edit the agent writes the task's goal, reading, `Done when` items, and scope; hooks in every harness check each iteration against it ([Staying on the goal](staying-on-goal.md)).
- **Explicit handoffs.** "handoff X" writes a short note with `,handoff`; "continue X" reads it in any harness.
- **Behavior maps, not diagrams.** Each repo keeps a short map of critical behaviors seen from the user side; agents update only the entries their diff touches.

Related: [Reviewing agent diffs](reviewing-diffs.md).
