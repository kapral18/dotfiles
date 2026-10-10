---
sidebar_position: 4
---

# Subagents

Subagents are rare by design. The main session already holds the context; a child starts from scratch (about 25k tokens before it reads anything) and returns a summary the main session must then trust or re-check.

## When a subagent is worth it

| Use                                                                                                                                                                                                 | Why it pays                                             | Profile                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------------- |
| Broad read-only search across many files or unknown locations                                                                                                                                       | the child reads a lot and returns a little              | Claude `Explore`, OMP `scout`, Pi `k-agent-scout`, Codex fresh native agent |
| A finished change that adds a command or module, changes persisted state, a parser, or concurrency, or changes a rule in the SOP, a skill, or a `k-agent-*` profile; or a review the user asked for | a fresh context does not share the author's blind spots | `k-review` Reviewer launch procedure                                        |

Everything else stays inline: implementation, verification, memory, and routine reads of known files.

## Rules

- A reviewer is read-only and returns at most 10 findings once. Verify mode runs two reviewers in parallel on the whole task change (with its map and memory writes) and merges their findings. When the main session may edit the reviewed code, it fixes supported findings and runs the bounded fix loop (`k-review` verify mode).
- One full review per change. After it, a bounded fix loop: one reviewer checks only each fix diff, until no supported medium or higher finding remains, at most three times, or until the same cause comes back at the same place. A wording-only fix (no rule, command, or behavior change) skips the review; findings of the last review are listed, not fixed, except wording-only lows.
- For a full review, the caller passes only scope, the user's request in their words, intent, check results, assumptions, and known gaps, and reviewers check that every part of the request is covered by evidence. A fix-diff reviewer gets the fix diff, the findings it fixes, the rerun checks, the known gaps, and the rejected findings. Reviewers never run a command that prints a secret, not even faked: a fake `pass` or `gh` loses to the real one in a login or nested shell. A shell probe uses a made-up name such as `probe_secret`. Reviewers report every severity; the medium threshold applies only to the agent's own report.
- Reviewers must not start subagents. Claude enforces `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, Pi sets `maxSubagentDepth: 0`, and OMP sets `task.maxRecursionDepth: 1`. Codex receives this restriction in the shared reviewer prompt; its native fresh-fork tool exposes no per-child tool or depth control.

## Profiles

The reviewer body is shared: `home/.chezmoitemplates/reviewer-prompt.md` (scope in; adversarial method: refute each finding, test state-changing operations against each other, question whether each added piece is needed; `file:line` findings with evidence; read-only).

| Harness               | Reviewer                                                                                                                     | Search                                                                |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Claude Code           | `home/dot_claude/exact_agents/k-agent-reviewer.md.tmpl` (`model: opus`, no CLAUDE.md)                                        | built-in `Explore`                                                    |
| Pi                    | `home/dot_pi/agent/exact_agents/k-agent-reviewer.md.tmpl` (`gpt-6.1-sol`, high)                                              | `home/dot_pi/agent/exact_agents/k-agent-scout.md` (`gpt-6-luna`, low) |
| OMP                   | `home/dot_omp/private_agent/exact_agents/k-agent-reviewer.md.tmpl`                                                           | native `scout`; overlay in `APPEND_SYSTEM.md`                         |
| Codex                 | native `spawn_agent` with `fork_turns: "none"`; shared prompt from `~/.agents/skills/k-review/references/reviewer_prompt.md` | fresh native agent for broad read-only searches                       |
| OpenCode, Antigravity | none; review inline with the same output format                                                                              | native tools                                                          |

Pi's `pi-subagents` built-in agents stay disabled (`subagents.disableBuiltins`), so only these profiles exist there.
OMP disables its own `reviewer` and `security-reviewer` agents in `task.disabledAgents`.

Codex 0.161.0 exposes `spawn_agent` without a named-profile selector. `k-review` passes the shared prompt and review packet directly, keeping the parent's model and effort. Full reviews launch two fresh agents; fix-diff reviews launch one.

Claude, Codex, Pi, and OMP share the SOP, skills, `,ai-kb`, `,handoff`, and `,behavior-map` workflow. Only Claude runs the SOP, checked-answer, stop-review, and behavior-map mods. OMP's `Gate` advisor applies the checked-answer rules to the final answer ([Oh My Pi](tool-configs/other-harnesses.md#oh-my-pi)); the other harnesses follow the written rules without enforcement.
