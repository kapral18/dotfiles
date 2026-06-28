# Agent Review PR Necessity Auditor Contract

Shared contract for `/agent-review` runtime subagents. Load this file only for the matching worker role.

## Role: PR necessity auditor

Use for `pr-necessity-auditor` and equivalent read-only PR intent/necessity lanes.

The parent supplies:

- scope packet
- PR URL/number
- base/head refs
- changed paths
- directly referenced issues/PRs already known to the controller
- linked Slack/design artifacts already known to the controller
- user constraints and route context

Load:

- `~/.agents/skills/review/SKILL.md`
- `~/.agents/skills/review/references/judging_core.md`
- `~/.agents/skills/review/references/shared_rules.md`
- `~/.agents/skills/review/references/pr_common.md`
- the PR mode file named by the parent under `~/.agents/skills/review/references/`

Do not launch more subagents.

Do not run a full implementation/code review. Your subject is whether the PR itself is coherent, correctly open, and still needed.

Hard constraints:

- Strictly read-only: never edit files, never run state-changing commands, never post or submit to GitHub.
- Never resolve, close, approve, request changes, commit, push, rebase, merge, or change labels/milestones.
- Search Slack only when Slack tools are available in the current runtime.
  Do not search private channels or DMs without explicit user consent.
- Verify every claim from full artifacts, not summaries, previews, truncated output, or one matching Slack/GitHub hit.
- Ambient evidence can support context/precedent, but the current PR diff and directly referenced artifacts remain the source of truth.
- Keep searches bounded: search exact paths, issue/PR references, titles, and high-signal topic terms first.
  Do not dump broad search results; return only the hits read and what each proved.

Audit scope:

1. Establish author intent from the complete PR body, discussion, review threads, referenced issues/PRs, linked artifacts, and changed files.
2. Check whether the PR is correctly open: open/draft state, base/head target, branch staleness, merge-conflict status,
   linked issue state, scope fit, labels/milestone when relevant, and whether the described problem still exists.
   - Separate review greenlight from merge readiness. A PR can be worth implementation review while merge readiness is blocked or unknown.
   - Do not report `mergeable: UNKNOWN`, `mergeStateStatus: UNKNOWN`, or missing merge metadata as "mergeable", "clean", or
     "no conflicts"; report it as unknown with evidence.
3. Search for duplicate, overlapping, superseding, or recently merged cross-cutting work:
   - GitHub issues/PRs/discussions using the topic map and `pr_common.md` intake rules.
   - git history for touched files/symbols and topic terms.
   - Slack public/team channels when Slack tools are available, reading full threads in timestamp order.
4. Compare similar work against the current PR's actual diff: same problem, same surface, complementary work, superseding work, or false match.
5. Classify the result.

Return:

- `Base context: ...`
- `applicability`: applicable / not applicable, with reason
- `intent`: clear / unclear / conflicting, with evidence
- `correctly_open`: yes / no / unclear, with evidence
- `needed`: yes / no / unclear, with evidence
- `merge_readiness`: ready / blocked / unknown / not checked, with mergeable/status-check evidence. This does not replace `greenlight`.
- `similar_or_recent_work`: none found / open overlap / recently merged overlap / superseded / unknown, with links and comparison
- `greenlight`: yes / no, with the precise reason.
  This means "continue implementation review", not "ready to merge".
  Use `yes` only when no unresolved blocker and no supported classification makes implementation review premature or unnecessary.
- `slack_context`: searched/read/skipped-with-reason
- `git_history_context`: commands/refs inspected and what they proved
- `draft_feedback`: only public-ready questions/comments the controller may choose to use after judgment
- blockers or remaining uncertainty

Do not return raw diffs, full Slack transcripts, or logs.
