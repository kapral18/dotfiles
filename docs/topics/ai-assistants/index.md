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

| Harness                   | Default model                    | Notes                                                            |
| ------------------------- | -------------------------------- | ---------------------------------------------------------------- |
| Claude Code               | `claude-opus-5-5`, effort high   | `,claude-openrouter` and `,claude-llama-cpp` switch the backend  |
| Pi                        | `anthropic/claude-opus-5-5`      | `pi-subagents` with built-in agents disabled; repo profiles only |
| OMP                       | `anthropic/claude-opus-5-5:auto` | native `scout`; repo `k-agent-reviewer`                          |
| Codex                     | `gpt-6-astra`                    | `,codex`, `,codex-openrouter`, `,codex-llama-cpp`                |
| OpenCode, Crush, freebuff | per-harness config               | basic config and MCP; OpenCode also runs the intent-guard plugin |

## Principles

- **Inline by default.** A subagent rebuilds context at full price, so subagents only do broad read-only searches, a review the user asks for, or automatic review rounds (two parallel reviewers each) of a risky finished change (including rule changes in the SOP, skills, and `k-agent-*` profiles), each with fix-diff reviews, until a whole-scope round is clean.
- **Verification until clean, statically.** Verification and review stay short, so feedback reaches the user and any orchestrating agent quickly. The project's unit and static checks for what the change touches run once on the finished change; one that is a live check (below) waits for the user's ask instead. Before reporting, the agent prefers evidence it controls: it reads the source of every system the change relies on, runs static checks and local code that ends on its own (unit tests, the change's own command on a temp copy, fakes for external commands), scoped to the change, tests state-changing operations against each other and against edge inputs, and lists each claim with its evidence in a `Checked:` line, marking a claim only a live check could settle "(unverified: …)" and offering that check under `Decision needed:`; the review gets those results. A live check waits on something outside this machine: the network, an external service, a model or agent session, or an interactive browser session (for example an e2e or smoke run against a deployed system). Self-contained local code that ends on its own is not one, even when it starts a local server or headless browser or waits on timers (code that also reaches any of those outside things is live), and neither is reading a source. A live check runs only when the user asks, as its own invocation with a hard time limit, on a copy when it would change anything outside this machine or delete or overwrite user data; this replaces any harness default to run or demo a change. Every check command runs under a time limit set above its normal run time: an optional probe that hits it settles nothing and gives way to cheaper evidence, a required check that hits it gets its cause found, and no check repeats without new information. Reviewers follow the same method. An independent review (two reviewers in parallel, on the whole task change, or on the diff since the last review's baseline for a later change in the same task) is followed by a fix loop ([Skills](skills.md#review-and-verification) describes it): each fix round checked against every consumer of the rule or function it touches and every trigger earlier rounds raised on it, a returned cause handled by replacing the approach or reverting rather than patching again, narrowed rounds, then a whole-scope round that ends the loop when it finds no new medium or higher finding. Rounds aim at about 3 minutes per reviewer and 5 per round, and the report shows the round trend. No count of rounds stops the loop, and it never asks whether to continue. Findings of the last review are still fixed, and fixes that are not wording-only are marked "(unreviewed)" in `Checked:`. The agent applies fixes it checked against source, inside its write scope and `k-review` Fix Scope, without asking. Done means every known in-scope issue is fixed, whatever its severity. Before reporting, the agent does every in-scope step that it can still do now, that the request named or that is reversible and changes nothing outside this machine the request did not name (or that is a cleanup `k-cleanup` allows, done by the agent and never left to the user), that needs no §5 approval, and that is no live check §3 step 4 keeps for the user's ask; the report has no slot for doable work: `Proposed:` holds only out-of-scope defects and actions, and `Open:` only items with a blocker the agent cannot remove.
- **On-demand memory.** `,ai-kb search` when it can help; `,ai-kb remember` only for verified, reusable gotchas, or `--supersedes` to retire a stale capsule.
- **Intent card.** Before its first edit the agent writes the task's goal, reading, `Done when` items, and scope; hooks in every harness check each iteration against it ([Staying on the goal](staying-on-goal.md)).
- **Explicit handoffs.** "handoff X" writes a short note with `,handoff`; "continue X" reads it in any harness.
- **Behavior maps, not diagrams.** Each repo keeps a short map of critical behaviors seen from the user side; agents update only the entries their diff touches.

Related: [Reviewing agent diffs](reviewing-diffs.md).
