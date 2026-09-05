---
name: k-kbn-standup
description: "Prepare Karen's #admin-ux-internal daily update from Slack and GitHub activity."
disable-model-invocation: true
---

# Standup

Process: baseline → gather → compile → show and ask, then `pbcopy`.

## Resolve first (runtime values, not hardcoded IDs)

Team channel is `#admin-ux-internal` (private; id resolved at runtime, historically `C06HA5KB0SF`).
GitHub scope is every repository in the Elastic organization that the current account can access, including private/internal repositories.
Resolve the rest at runtime:

- `USER` = current Slack user id from `slack_read_user_profile` (no arg).
- `GH` = `gh api user --jq .login`.

## 1. Baseline

`BASELINE` = the `Message_ts` of the user's own **last multi-bullet standup post** in `#admin-ux-internal` (not a Slackbot reminder, not chatter).
Find it via `slack_search_public_and_private` `from:<@USER> in:#admin-ux-internal` (`slack_search_public` misses this private channel).
Read it fully — you must not repeat its items and should report status deltas (e.g. `waiting on review` → `merged`).
Read it for content only, never for format.
Slack stores posted links as `<URL|label>`, so a correct prior standup renders in a syntax that section 3 forbids.
Take items and status from it; take link syntax only from section 3.

Done when `BASELINE` is that newest `#admin-ux-internal` post's `Message_ts` and the post has been read.

## 2. Gather (only events strictly after BASELINE)

Search `--created`/`after:` filters are day-granular; always compare the exact timestamp before including an item.
Run every GitHub lane below across `--owner elastic` with no visibility filter; union candidates, then timestamp-triage.
`--author` alone is incomplete: it misses commits and comments on other people's PRs/issues.

GitHub (`GH`, owner `elastic`):

- Authored PRs: `gh search prs --owner elastic --author <GH> --updated ">=<date>" --json number,title,state,createdAt,updatedAt,closedAt,url,repository --sort updated --limit 100`.
  For PRs that were `waiting on review` last time, confirm `mergedAt`.
  For still-open PRs, confirm real work by last `committedDate` (not `updatedAt`, which others' comments bump).
- For every merged `elastic/kibana` source PR, search its number without an author filter:
  `gh search prs "<source-number>" --repo elastic/kibana`. Inspect source-PR comments for failed/conflicted branches and manual resolution.
  Include a backport only when evidence shows the user resolved conflicts or materially debugged/fixed its CI;
  omit routine bot-created backports.
- Issues filed: `gh search issues --owner elastic --author <GH> --created ">=<date>" --json number,title,state,createdAt,updatedAt,closedAt,url,repository --limit 100`.
  Before claiming meta/sub-issue linkage, verify it: `gh api repos/<owner>/<repo>/issues/<meta>/sub_issues`.
- Reviews on others' PRs: `gh search prs --owner elastic --reviewed-by <GH> --updated ">=<date>" --json number,title,state,updatedAt,url,repository --limit 100`.
  Confirm via `gh api repos/<owner>/<repo>/pulls/<n>/reviews` filtered to `user.login == GH`:
  - Include when `submitted_at` is after BASELINE.
  - When `state` is `PENDING` and `submitted_at` is null, load `gh api repos/<owner>/<repo>/pulls/<n>/reviews/<id>/comments`.
    Include the PR as reviewed when any of those comments has `created_at` after BASELINE (pending drafts with inline comments count).
- Involves net (commits / comments on others' artifacts — required, not optional):
  - PRs: `gh search prs --owner elastic --involves <GH> --updated ">=<date>" --json number,title,state,updatedAt,url,repository,author --limit 100`.
    For each hit whose `author.login != GH`, list commits with `gh api repos/<owner>/<repo>/pulls/<n>/commits`.
    Treat as contributed PR work when any commit has `author.login == GH` (or commit author email matching the user) and committer/author date after BASELINE.
  - Issues: `gh search issues --owner elastic --involves <GH> --updated ">=<date>" --json number,title,state,updatedAt,url,repository,author --limit 100`.
    For each hit whose `author.login != GH`, load `gh api repos/<owner>/<repo>/issues/<n>/comments`.
    Include when GH left a post-BASELINE comment that is effortful (investigation, decision, attribution); drop ack-only replies.
- Events net (catch misses from search lag): page `gh api users/<GH>/events?per_page=100` while `created_at` is after BASELINE.
  Keep `elastic/*` events of type `PushEvent`, `PullRequestEvent`, `PullRequestReviewEvent`, `PullRequestReviewCommentEvent`, `IssueCommentEvent`, `IssuesEvent`.
  For every PR/issue number in those events that is not already triaged, run the same commit / review / comment checks as above.

Slack (catches work that never hits GitHub — incidents, impact assessments):

- Enumerate everything instead of keyword-guessing: `slack_search_public_and_private` `from:<@USER> after:<date>`, `sort=timestamp`, `include_context=false`, **no free-text term**; page the `pagination_info` cursor until you pass BASELINE.
  Prefer `channel_types=public_channel,private_channel` when paging past DM noise;
  still use DMs as evidence without publishing their permalinks.
  Search all channels the account can access, including private channels and DMs, without asking for consent.
- Strict timestamp comparison: compare each message's `Message_ts` numerically as a float against `BASELINE` (`msg.Message_ts > BASELINE`).
  Discard any message with `Message_ts <= BASELINE`.
- Anti-resurrection guard: ignore all previous standup posts returned in search results (messages containing multi-bullet updates from earlier days).
  Never extract items or bullet points from past standup messages.
- Thread link target guard: the URL for a bullet in `Slack and other` must link directly to the specific discussion thread where the work happened.
  NEVER link to a standup/daily update thread, a Slackbot reminder (`from:USLACKBOT`), or the thread where you are about to post.
- Also search `from:<@USER> in:#admin-ux-internal` and `from:<@USER> in:#kibana-management` after BASELINE for discussion context.
  `#kibana-management` is a public-facing discussion channel, not a standup source.
- Search `from:<@USER> SDH after:<date>` with `slack_search_public_and_private` and context, and map only explicitly named PRs/issues/discussions to SDH work.
  Do not infer SDH association from product area.
- Triage for team relevance: keep effortful work (incident/severity assessments, investigations, decisions);
  drop social/off-topic chatter and acknowledgements.

Done when authored PRs/issues, involves-contributed commits, reviews (including pending-with-comments), effortful issue comments, events-derived candidates, and Slack items from `#admin-ux-internal`, `#kibana-management`, and the all-channels `from:<@USER>` pass have been timestamp-checked (strictly `> BASELINE`), validated against old-standup resurrection, and triaged.

## 3. Compile (team format)

Emit `•` bullets. Terse, high-level, readable in a skim.
New work only; status deltas vs the last standup; verified facts ("added", not "will add").
Name the unit of work (what shipped, what is open, what was raised), not implementation micro-steps.
Do not join unrelated authored work because one activity blocked validation of another.
Operational investigations and the technical change they happened to delay are separate bullets.

Emit the standup as four sections in this order, each heading on its own line: `PRs`, `Reviews`, `Issues`, `Slack and other`.
Omit a heading when that group has no bullets. Put a blank line after each heading, then that group's bullets.
Put a blank line after the last bullet of a section before the next heading.
Keep the four-section structure exactly: use only those headings, in that order, grouped as specified rather than flattened into one list or regrouped by theme, SDH, or product area.

### PRs

One bullet per authored source PR. Never lump distinct source PRs onto one line.
Also one bullet per other-author PR that has post-BASELINE commits by `GH` (contributed push);
lead with `Contributed` (or `Pushed` when that is the only change).
The only authored grouping is a source PR plus qualifying backports of that same PR.
A PR bullet links that PR as `[label](URL)` and, when grouped, each qualifying backport.
After each PR link, put `:merged:` or `:pr-open:` as specified under Icons.
A source PR plus two merged qualifying backports contains three `[label](URL) :merged:` pairs.
Describe qualifying backport effort as `Resolved the <branches> backports for <change>`.
Use `Adapted` instead of `Resolved` only when evidence shows branch-specific implementation changes;
use those two words, never `manually resolved`.
When the same other-author PR has both post-BASELINE commits by `GH` and review activity, keep the contributed-commit PR bullet under `PRs` and omit that PR from the `Reviews` section.

### Reviews

List reviewed PRs here instead of inside the `PRs` section. One bullet per reviewed PR (or concise grouped bullets for related PRs).
Link each reviewed PR as `[label](URL)` followed immediately by `:merged:` or `:pr-open:`.

### Issues

Never put an issue and a PR on the same bullet, even when the PR fixes that issue. Same-theme related issues may share one bullet.
Unrelated issues stay on separate bullets. An issue bullet links each issue as `[label](URL)`.
After each issue link, put `🐛` or `:ticket:` as specified under Icons.
Include effortful post-BASELINE comments on others' issues here (same issue-link rules), not only issues `GH` filed.

### Slack and other

Keep effortful discussions and investigations as their own bullets (incidents, SDH, attribution, decisions).
Skim low-impact leftovers (CI noise, small reports, acknowledgements) into one bullet, or omit them.
Link each channel thread, design document, or other work product the item represents.
Use DMs as evidence, but do not put inaccessible DM permalinks in the compiled standup.

### Icons and SDH

Never end a line with a link: put that artifact's icon immediately after it.

PRs & Reviews: after each PR link, `:merged:` if that PR is merged, `:pr-open:` if it is open.
Those are the only icons on PR and review bullets; `🐛`, `:ticket:`, `👀`, and other category icons belong elsewhere.

Issues: after the issue link, `🐛` if the issue is a bug (`bug` label, or a defect/regression); `:ticket:` for every other issue.
Do not use `🐛` on PRs or on non-bug issues.

Slack and other: exactly one category icon after the last link on the bullet.
Categories: `✅` completed/resolved without a merge; `🔍` investigation or validation; `👀` review; `🤝` sync or design discussion.
Choose the bullet's primary outcome when one item spans categories.

SDH is metadata, not a category.
Only when evidence directly identifies the activity as SDH work, use `:sdh:` in the summary where the word “SDH” would appear.
Do not append `:sdh:` to artifact/category icons or propagate it to merely related activity.

Done when every rule in this Compile section passes: section order/spacing, per-artifact grouping and deduplication, shareable links, per-link icons, and evidence-backed SDH placement.

## 4. Deliver

Emit `[label](URL)` only.
Never emit `<URL|label>`: Slack's composer converts pasted `[label](URL)` into real hyperlinks, so the Markdown form is what the paste path needs.
(`slack_send_message_draft` strips the URL target from both forms, leaving plain label text — one more reason it is not the delivery path.)
Never invoke `slack_send_message` or `slack_send_message_draft`. Do not copy until the user says they are ready.

- Paste target = newest Slackbot reminder thread that tags `@admin-ux-team`: `slack_search_public_and_private` `from:<@USLACKBOT> "share your daily update" in:#admin-ux-internal`, `sort=timestamp`, `include_bots=true` (private channel; `slack_search_public` misses it).
  If none exists, the paste target is a standalone message in `#admin-ux-internal`.
  Never paste or post the compiled standup in `#kibana-management`.
- Show the compiled standup inside a fenced raw code block (` ```text `) so the assistant UI rendering layer does not obscure or render Markdown links, and show the paste target, then ask if they are ready for `pbcopy`. A yes in the invoking prompt counts.
- On yes: copy the compiled standup as plain text with `pbcopy`, then verify `pbpaste` exactly matches the source and contains one `[label](URL)` per artifact.
  Also run the negative check `pbpaste | grep -c '<https'` and require `0`; a grep built from what you just wrote confirms itself and catches nothing.

Done when the user has seen the compiled standup inside a fenced code block and paste target, and after a yes `pbpaste` matches with one `[label](URL)` per artifact and `grep -c '<https'` returns `0`.
