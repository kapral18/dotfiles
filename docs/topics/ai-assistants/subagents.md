---
sidebar_position: 4
---

# Subagents

Subagents are rare by design. The main session already holds the context; a child starts from scratch (about 25k tokens before it reads anything) and returns a summary the main session must then trust or re-check.

## When a subagent is worth it

| Use                                                           | Why it pays                                             | Profile                                           |
| ------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------- |
| Broad read-only search across many files or unknown locations | the child reads a lot and returns a little              | Claude `Explore`, OMP `scout`, Pi `k-agent-scout` |
| A review the user asked for                                   | a fresh context does not share the author's blind spots | `k-agent-reviewer`                                |

Everything else stays inline: implementation, verification, memory, and routine reads of known files.

## Rules

- A reviewer is read-only and returns at most 10 findings once. When the main session may edit the reviewed code, it fixes supported findings once and stops (`k-review` verify mode).
- No review → fix → review loops.
- Children cannot start their own subagents: Claude `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, Pi `maxSubagentDepth: 0` in each profile, OMP `task.maxRecursionDepth: 1`.

## Profiles

The reviewer body is shared: `home/.chezmoitemplates/reviewer-prompt.md` (scope in; method; `file:line` findings with evidence; read-only).

| Harness                      | Reviewer                                                                              | Search                                                                |
| ---------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Claude Code                  | `home/dot_claude/exact_agents/k-agent-reviewer.md.tmpl` (`model: opus`, no CLAUDE.md) | built-in `Explore`                                                    |
| Pi                           | `home/dot_pi/agent/exact_agents/k-agent-reviewer.md.tmpl` (`gpt-6.1-sol`, high)       | `home/dot_pi/agent/exact_agents/k-agent-scout.md` (`gpt-6-luna`, low) |
| OMP                          | `home/dot_omp/private_agent/exact_agents/k-agent-reviewer.md.tmpl`                    | native `scout`; overlay in `APPEND_SYSTEM.md`                         |
| Codex, OpenCode, Antigravity | none; review inline with the same output format                                       | native tools                                                          |

Pi's `pi-subagents` built-in agents stay disabled (`subagents.disableBuiltins`), so only these profiles exist there.
OMP disables its own `reviewer` and `security-reviewer` agents in `task.disabledAgents`.
