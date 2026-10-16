---
sidebar_position: 4
---

# Subagents

Subagents are rare by design. The main session already holds the context; a child starts from scratch (about 25k tokens before it reads anything) and returns a summary the main session must then trust or re-check.

## When a subagent is worth it

| Use                                                                                                                                                                                                                                                                                                                                                            | Why it pays                                             | Profile                                                                     |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------------- |
| Broad read-only search across many files or unknown locations                                                                                                                                                                                                                                                                                                  | the child reads a lot and returns a little              | Claude `Explore`, OMP `scout`, Pi `k-agent-scout`, Codex fresh native agent |
| A finished change on the `~/AGENTS.md` §3 step 5 list (a new command or module, persisted data, a parser, concurrency, auth/secrets/crypto, a public API, deleting user data or files, a rule in the SOP, a skill, a `k-agent-*` profile, the shared reviewer prompt, or a hook or advisor prompt that judges against the SOP); or a review the user asked for | a fresh context does not share the author's blind spots | `k-review` Reviewer launch procedure                                        |

Everything else stays inline: implementation, verification, memory, and routine reads of known files.

## Rules

- A reviewer is read-only and returns at most 10 findings once. Verify mode runs two reviewers in parallel on the whole task change (with its map and memory writes), or on the diff since the last review's baseline for a later change in the same task, and merges their findings. When the main session may edit the reviewed code, it fixes supported findings and runs the bounded fix loop (`k-review` verify mode).
- Full review rounds per change: after each, a bounded fix loop where one reviewer checks each fix diff (a wording-only fix gets none), again while a supported medium or higher finding remains, at most three times; a cause that comes back at the same place gets a read-only investigation and one more fix, and stops the loop if it returns again. Lows a fix-diff review finds are fixed in the same round without another review. A full round that found a medium or higher finding is followed by another full round on the whole scope, reporting only new findings, until one finds none, for at most three full rounds.
- A wording-only fix round (typos, reflow, a rename with no change in meaning) skips the review. Findings of the last review are still fixed; fixes that are not wording-only are marked "(unreviewed)" in `Checked:`. A cause that returned twice, or any finding that cannot be fixed, goes under `Open:`.
- For a full review, the caller passes only scope, the user's request in their words, intent, check results, assumptions, and `Open:` items (a later full round, or a verify-again run, also gets every finding fixed, rejected, or proposed so far), and reviewers check that every part of the request is covered by evidence. A fix-diff reviewer gets the fix diff, the user's request in their words, the findings it fixes, the rerun checks, the `Open:` items, and the rejected and proposed findings. Reviewers report an `Open:` item the caller could do now. Reviewers never run a command that prints a secret, not even faked: a fake `pass` or `gh` loses to the real one in a login or nested shell. A shell probe uses a made-up name such as `probe_secret`. Reviewers report every severity; the agent fixes every supported finding the change caused or the request covers and lists the rest under `Proposed:`.
- Reviewers must not start subagents. Claude enforces `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, Pi sets `maxSubagentDepth: 0`, and OMP sets `task.maxRecursionDepth: 1`. Codex receives this restriction in the shared reviewer prompt; its native fresh-fork tool exposes no per-child tool or depth control.

## Profiles

The reviewer body is shared: `home/.chezmoitemplates/reviewer-prompt.md` (scope in; adversarial method: refute each finding, test state-changing operations against each other, question whether each added piece is needed; `file:line` findings with evidence; read-only).

| Harness     | Reviewer                                                                                                                                                                   | Search                                                                |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Claude Code | `home/dot_claude/exact_agents/k-agent-reviewer.md.tmpl` (`model: opus`, no CLAUDE.md); launched with `run_in_background: false`, so the turn waits for a round's reviewers | built-in `Explore`                                                    |
| Pi          | `home/dot_pi/agent/exact_agents/k-agent-reviewer.md.tmpl` (`gpt-6.1-sol`, high)                                                                                            | `home/dot_pi/agent/exact_agents/k-agent-scout.md` (`gpt-6-luna`, low) |
| OMP         | `home/dot_omp/private_agent/exact_agents/k-agent-reviewer.md.tmpl`                                                                                                         | native `scout`; overlay in `APPEND_SYSTEM.md`                         |
| Codex       | native `spawn_agent` with `fork_turns: "none"`; shared prompt from `~/.agents/skills/k-review/references/reviewer_prompt.md`                                               | fresh native agent for broad read-only searches                       |
| OpenCode    | none; review inline with the same output format                                                                                                                            | native tools                                                          |

Pi's `pi-subagents` built-in agents stay disabled (`subagents.disableBuiltins`), so only these profiles exist there.
OMP disables its own `reviewer` and `security-reviewer` agents in `task.disabledAgents`.

Codex 0.161.0 exposes `spawn_agent` without a named-profile selector. `k-review` passes the shared prompt and review packet directly, keeping the parent's model and effort. Full reviews launch two fresh agents; fix-diff reviews launch one.

Claude, Codex, Pi, and OMP share the SOP, skills, `,ai-kb`, `,handoff`, `,task`, and `,behavior-map` workflow; the intent-guard hooks run in every harness ([Staying on the goal](staying-on-goal.md)). Only Claude runs the SOP, checked-answer, stop-review, and behavior-map mods. OMP's `Gate` advisor reviews the final answer against `~/AGENTS.md` ([Oh My Pi](tool-configs/other-harnesses.md#oh-my-pi)); the other harnesses follow the written rules without enforcement.
