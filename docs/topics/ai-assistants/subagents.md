---
sidebar_position: 4
---

# Subagents

Subagents are rare by design. A child starts without the main session's context, spends about 25k tokens before it reads anything, and returns a summary the main session must check.

## When a subagent is worth it

- Broad read-only search across many files or unknown paths: use Claude `Explore`, OMP `scout`, Pi `k-agent-scout`, or a fresh Codex agent. The child returns a focused result.
- Independent review required by `~/AGENTS.md` §3 step 5 or requested by the user: use the `k-review` Reviewer launch procedure.

Everything else stays inline: implementation, verification, memory, and routine reads of known files.

## Rules

- A reviewer is read-only and returns at most 10 findings once. Verify mode launches two fresh reviewers in parallel, merges their findings, and runs the fix loop in [Skills](skills.md#review-and-verification). The [review skill](../../../home/exact_dot_agents/exact_skills/exact_k-review/readonly_SKILL.md) defines the exact packet and scope; the [fix procedure](../../../home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_review_fixes.md) owns the loop.
- A wording-only fix round skips review. Findings from the last review still need fixes. Mark each fix after the last review that is not wording-only "(unreviewed)" in `Checked:`; a cause that returns twice, or a finding that cannot be fixed, goes under `Open:`.
- Reviewers check request coverage against source evidence and report every severity. They run static checks under a time limit, start no live checks, and put claims only a live check could settle under `Not checked:`. They never run a secret-printing command, even a fake named after a real command. Every review applies `k-code-quality`'s De-slop section, which loads `k-anti-slop`.
- Reviewers must not start subagents. Claude enforces `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, Pi sets `maxSubagentDepth: 0`, and OMP sets `task.maxRecursionDepth: 1`. Codex receives this restriction in the shared reviewer prompt; its native fresh-fork tool exposes no per-child tool or depth control.
- Claude reviewers use the session's effort (`medium` in `settings.json`). `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` disables the advisor for the main session and its subagents, since an agent profile has no key to turn it off (2.1.304); OMP keeps task advisors off (`task.agentAdvisor`).

## Profiles

The reviewer body is shared: `home/.chezmoitemplates/reviewer-prompt.md`. It collects candidates across correctness, removed safeguards, contracts, simplification, conflicting state operations, edge inputs, instruction text, project rules, and slop, then deduplicates and refutes them before reporting evidence-backed `file:line` findings.
Its verdict follows the evidence: there is no finding quota, and the caller's or author's preferred outcome does not justify inventing, suppressing, or withdrawing a finding.

| Harness     | Reviewer                                                                                                                     | Search                                     |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| Claude Code | `home/dot_claude/exact_agents/k-agent-reviewer.md.tmpl` (Opus, session effort, `omitClaudeMd`), launched in the foreground   | built-in `Explore`                         |
| Pi          | `home/dot_pi/agent/exact_agents/k-agent-reviewer.md.tmpl` (`claude-opus-5-5`, medium)                                        | `k-agent-scout` (`gpt-6-luna`, low)        |
| OMP         | `home/dot_omp/private_agent/exact_agents/k-agent-reviewer.md.tmpl`                                                           | native `scout`, `APPEND_SYSTEM.md` overlay |
| Codex       | native `spawn_agent` with `fork_turns: "none"`; shared prompt from `~/.agents/skills/k-review/references/reviewer_prompt.md` | fresh native agent                         |
| OpenCode    | none; review inline                                                                                                          | native tools                               |

Pi's `pi-subagents` built-in agents stay disabled (`subagents.disableBuiltins`), so only these profiles exist there.
OMP disables its own `reviewer` and `security-reviewer` agents in `task.disabledAgents`.

Codex 0.163.0 `spawn_agent` exposes a role selector (`agent_type`) only when agent roles are defined (`[agents.<name>]` in `config.toml` or a `~/.codex/agents/` file); this repo defines none. `k-review` passes the shared prompt and review packet directly, keeping the parent's model and effort. Full reviews launch two fresh agents; fix-diff reviews launch one.

Claude, Codex, Pi, and OMP share the SOP, skills, `,ai-kb`, `,handoff`, `,task`, and `,behavior-map` workflow; the intent-guard hooks run in every harness ([Staying on the goal](staying-on-goal.md)). Only Claude runs the SOP, checked-answer, stop-review, and behavior-map mods. OMP's `Gate` advisor reviews the final answer against `~/AGENTS.md` ([Oh My Pi](tool-configs/other-harnesses.md#oh-my-pi)); the other harnesses follow the written rules without enforcement.
