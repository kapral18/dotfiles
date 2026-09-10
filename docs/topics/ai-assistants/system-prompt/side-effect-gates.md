---
sidebar_position: 4
title: Side-effect gates
---

# Side-effect gates

The SOP separates local reasoning from actions that affect people, git history, or owned areas. These gates keep read-only investigation from silently turning into publication, ownership crossings, or history changes.

## Mental model

| Gate                      | Blocks until                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Git commit                | explicit user request in the current conversation; content approval is not enough                            |
| Git push                  | explicit push request; its described commit is authorized, and rejected pushes stop instead of auto-rebasing |
| CODEOWNERS                | affected paths are in the user's ownership or user approves crossing ownership                               |
| Human-visible publication | exact payload and target are approved, or a relevant skill/reference approval packet applies                 |
| Approved action series    | user approval defines target, scope, intended outcome, allowed effects, and the later step is necessary      |
| Bot thread carve-out      | author is verified as a bot and flow was explicitly invoked                                                  |
| GitHub mutation           | `k-github` skill is loaded and side-effect rules are followed                                                |

## Using it

### Publication split

| Target                        | Default                                                                                              |
| ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| Human-authored thread/comment | use explicit authorization for the scoped effect; otherwise draft and wait                           |
| Mixed/unknown participants    | treat as human                                                                                       |
| Verified bot-authored thread  | auto-reply/resolve only inside an explicitly invoked flow                                            |
| Existing PR body/title        | `k-github` PR packet decides whether the user's approval for the current PR workflow covers the edit |

SOP §3.8 owns authorization across all publication skills. Authorization persists for the approved target, scope, and effect types until completion or revocation, including across follow-ups, corrections, compaction, and continuation of the same task. Record its scope and evidence in the topic handoff, re-check current preconditions without resetting permission, and do not repeat completed one-shot actions. Execute a conditional action once its condition holds or the user removes that condition; do not request the same permission again. New targets, broader effects, and unapproved substantive text still require approval. An explicit PR approval request permits a brief standard acknowledgement without adding substantive feedback. Approval does not authorize merging or bypassing CI.

Human-visible text has a single wording owner. The [communication skill](../skills/review-and-delivery.md#k-communication) owns tone, and loaded mechanics skills such as `k-github`, `k-slack`, `k-google-workspace`, or `k-review` do not re-derive it per surface. SOP §3.8 names that skill as a duty before drafting, so composers (`k-compose-pr`, `k-compose-issue`) and `k-git` commit messages load it even when no side effect follows yet; it also lists the session artifacts (SOP references, skill/agent/packet names, `Compatibility impact:` lines, spec paths, ledger references) that never reach external text.

Enforcement is layered. `home/exact_dot_agents/exact_hooks/executable_publish_gate.py` runs on `PreToolUse` in Claude Code and Codex: it denies GitHub, Slack, and Google Workspace publication calls from a delegated leaf (SOP §3.7 leaf contract) and rides a §3.8 checklist along with the root's call. Setting `AGENT_PUBLISH_GATE_ROOT=ask` turns the root path into a harness confirmation; `AGENT_PUBLISH_GATE=off` disables the hook. Repo-authored Claude subagent profiles that inherit every tool also deny the six Slack mutation tools by exact name in `disallowedTools`; Slack reads stay available.

The SOP states this as a boundary, not a routing trigger. Skill discovery is driven by the skill's own `description`; a skill file named in the SOP (a fail-closed gate, a mechanics owner, or a §3.1 shared-assessment owner such as `k-github` intake, `k-semantic-code-search`, or `k-diagnosing-bugs`) is a duty at that step, not a discovery trigger.
