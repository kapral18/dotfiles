# PR Context Audits

Conditional context-gathering gates for PR review modes, split out of `pr_common.md`.
Load this file when either gate below is triggered; `pr_common.md` remains the entry point for PR setup.

## Ambient Topic Exploration (conditional — complete before judging contested context)

Run this second layer only when direct PR/issue context does not settle shared understanding:

- the PR/issue discussion shows disagreement, conflicting claims, or unclear ownership/requirements
- the user asks for deep context, history, "why", precedent, or whether a claim matches team/product understanding
- a candidate finding depends on product intent, team convention, prior incidents, or decisions not proven by the directly referenced artifacts
- direct references are sparse, contradictory, or appear to omit the rationale behind the current disagreement

Skip it for routine implementation reviews where the diff, base context, and direct references are enough.

Keep it bounded. Before using the results, write:

- topic
- queries
- sources searched
- hits read
- stop reason

1. Build a topic map from the current artifact and diff: product/feature names, code symbols, error text, labels, team names, user-visible phrases, and disputed terms.
2. Search GitHub beyond direct references:
   - Issues:
     - `gh search issues --repo OWNER/REPO "<terms>" --match title,body,comments --json number,title,state,commentsCount,updatedAt,url --limit 20`
     - omit `--state` to search both open and closed
   - PRs:
     - `gh search prs --repo OWNER/REPO "<terms>" --match title,body,comments --json number,title,state,commentsCount,updatedAt,url --limit 20`
     - omit `--state` to search both open and closed
   - Discussions when the repo uses them:
     - use GitHub GraphQL `search(query: "repo:OWNER/REPO <terms>", type: DISCUSSION, first: N)`
     - GraphQL exposes `DISCUSSION`, `Discussion.comments`, and `DiscussionComment.replies`
     - `gh search` has no discussion subcommand
3. If Slack MCP tools are available in the current runtime:
   - search relevant public/team channels for the topic terms
   - read full matching threads
   - examples in this setup: `slack_search_public`, `slack_search_channels`, `slack_read_user_profile`, `slack_search_public_and_private` with explicit user consent
   - search private channels or DMs only with explicit consent
4. For each promising ambient hit, read enough full context to decide whether it informs the disputed topic:
   - GitHub issues/PRs/discussions: body, comments/replies/threads, linked references, and relevant diffs/files using the GitHub Context Intake + Reference Resolution rules in `pr_common.md`
   - Slack: the complete thread/conversation around the hit, not just the matching message;
     preserve timestamps/order and distinguish decisions from speculation
5. Stop when:
   - searches produce no new decision-relevant facts
   - a small representative set of high-signal hits has been read
   - tools/access are exhausted
   - Record skipped sources with reasons (e.g. `Slack MCP unavailable`, `private channel requires consent`, `GitHub Discussions disabled/unavailable`).
6. Use ambient evidence only as context/precedent.
   The current PR diff and directly relevant artifacts remain the source of truth for what is actually changing.

## PR Necessity + Correctly-Open Audit (conditional)

Run this audit when reviewing a PR whose author is not the user (`authorship: other` or `unknown`).
It is part of other-authored PR review, not a user opt-in.

Skip it for local changes and routine self-review.

This audit does not approve, reject, close, or post. It produces evidence for draft feedback or controller judgment.

1. Reconstruct author intent:
   - Use the full GitHub Context Intake + Reference Resolution results.
   - Read the PR description, discussion, review threads, referenced issues/PRs, linked artifacts, and relevant changed files as one intent record.
   - Distinguish the author's stated goal from inferred goals, reviewer suggestions, and ambient precedent.
2. Check whether the PR is correctly open:
   - Verify state, draft/readiness, base/head refs, branch staleness, merge-conflict status, linked issue state, labels/milestone when relevant, and whether the described problem exists on base.
   - Treat "open" as procedural correctness, not a merge verdict. A PR can be correctly open while still needing changes.
   - If the PR appears mis-targeted, stale, premature, missing a linked issue, or scoped differently from its stated intent, record the exact evidence.
3. Check whether the work is still needed:
   - Search for duplicate, overlapping, superseding, or recently merged work using the topic map from Ambient Topic Exploration.
   - Search GitHub issues/PRs/discussions beyond direct references with the existing Ambient Topic Exploration commands and rules.
   - For recent merged work, include terms like `is:pr is:merged merged:>=YYYY-MM-DD` in GitHub search queries instead of assuming closed PRs are relevant.
   - Compare any high-signal hit against the current PR's actual diff before calling it overlapping or superseding.
4. Inspect git history for touched files/symbols and topic terms:
   - Prefer bounded history such as `git log --all --since=<range> -- <paths>` for touched files.
   - Use `git log --all --grep=<terms>` for topic-level history.
   - Use blame or line history only when it can prove why the existing behavior exists or whether a prior fix already addressed the same issue.
   - Record the range and refs inspected.
5. Inspect Slack topic discussions when Slack tools are available:
   - Search relevant public/team channels for topic terms.
   - Read complete matching threads in timestamp order.
   - Distinguish decisions from speculation, proposals, and unresolved questions.
   - Search private channels or DMs only with explicit user consent.
   - If Slack is unavailable, or private-channel consent would be required, record that as skipped-with-reason.
6. Classify the audit:
   - `intent`: clear / unclear / conflicting
   - `correctly_open`: yes / no / unclear
   - `needed`: yes / no / unclear
   - `similar_or_recent_work`: none found / open overlap / recently merged overlap / superseded / unknown
   - `recommended_review_action`: continue normal review / ask author a clarifying question / suggest narrowing / suggest closing as duplicate or superseded / block on missing evidence
7. Use the result conservatively:
   - Claim a PR is unnecessary only when evidence beyond ambient evidence alone supports it.
   - Claim overlap only when a diff comparison supports it, not matching terminology alone.
   - Draft feedback only when the classification is anchored in the current PR plus direct or high-signal ambient evidence.
