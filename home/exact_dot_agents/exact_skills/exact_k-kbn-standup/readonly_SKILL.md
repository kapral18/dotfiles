---
name: k-kbn-standup
description: "Prepare Karen's #admin-ux-internal daily update from Slack and GitHub activity."
disable-model-invocation: true
---

# Standup

Process: baseline → gather → compile → show and ask, then `pbcopy`.

## Resolve first (don't hardcode IDs)

Team channel is `#admin-ux-internal`.
GitHub scope is every repository in the Elastic organization that the current account can access, including private/internal repositories.
Resolve the rest at runtime:

- `USER` = current Slack user id from `slack_read_user_profile` (no arg).
- `GH` = `gh api user --jq .login`.

## 1. Baseline

`BASELINE` = the `Message_ts` of the user's own **last multi-bullet standup post** in `#admin-ux-internal` (not a Slackbot reminder, not chatter).
Find it via `slack_search_public` `from:<@USER> in:#admin-ux-internal`.
Read it fully — you must not repeat its items and should report status deltas (e.g. `waiting on review` → `merged`).

Done when `BASELINE` is that newest `#admin-ux-internal` post's `Message_ts` and the post has been read.

## 2. Gather (only events strictly after BASELINE)

Search `--created`/`after:` filters are day-granular; always compare the exact timestamp before including an item.

GitHub (author `GH`, owner `elastic`):

- Authored PRs: `gh search prs --owner elastic --author <GH> --updated ">=<date>" --json number,title,state,createdAt,updatedAt,closedAt,url,repository --sort updated --limit 100`.
  Do not add a visibility filter: include every public, internal, and private Elastic repository visible to the authenticated account.
  For PRs that were `waiting on review` last time, confirm `mergedAt`.
  For still-open PRs, confirm real work by last `committedDate` (not `updatedAt`, which others' comments bump).
- For every merged `elastic/kibana` source PR, search its number without an author filter:
  `gh search prs "<source-number>" --repo elastic/kibana`. Inspect source-PR comments for failed/conflicted branches and manual resolution.
  Include a backport only when evidence shows the user resolved conflicts or materially debugged/fixed its CI;
  omit routine bot-created backports.
- Issues filed: `gh search issues --owner elastic --author <GH> --created ">=<date>" --json number,title,state,createdAt,updatedAt,closedAt,url,repository --limit 100`.
  Before claiming meta/sub-issue linkage, verify it: `gh api repos/<owner>/<repo>/issues/<meta>/sub_issues`.
- Reviews on others' PRs: `gh search prs --owner elastic --reviewed-by <GH> --updated ">=<date>" --json number,title,state,updatedAt,url,repository --limit 100`; confirm the review timestamp via `gh api repos/<owner>/<repo>/pulls/<n>/reviews`.

Slack (catches work that never hits GitHub — incidents, impact assessments):

- Enumerate everything, don't keyword-guess: `slack_search_public_and_private` `from:<@USER> after:<date>`, `sort=timestamp`, `include_context=false`, **no free-text term**; page the `pagination_info` cursor until you pass BASELINE.
  Search all channels the account can access, including private channels and DMs. Do not ask for consent.
- Also search `from:<@USER> in:#admin-ux-internal` and `from:<@USER> in:#kibana-management` after BASELINE for discussion context.
  `#kibana-management` is a public-facing discussion channel, not a standup source.
- Search `from:<@USER> SDH after:<date>` with `slack_search_public_and_private` and context, and map only explicitly named PRs/issues/discussions to SDH work.
  Do not infer SDH association from product area.
- Triage for team relevance: keep effortful work (incident/severity assessments, investigations, decisions);
  drop social/off-topic chatter and acknowledgements.

Done when every post-baseline GitHub item and Slack item from `#admin-ux-internal`, `#kibana-management`, and the all-channels `from:<@USER>` pass has been timestamp-checked and triaged.

## 3. Compile (team format)

Emit `•` bullets. Terse, high-level, readable in a skim.
New work only; status deltas vs the last standup; verified facts ("added", not "will add").
Name the unit of work (what shipped, what is open, what was raised), not implementation micro-steps.
Do not join unrelated authored work because one activity blocked validation of another.
Operational investigations and the technical change they happened to delay are separate bullets.

Emit the standup as three sections in this order, each heading on its own line: `PRs`, `Issues`, `Slack and other`.
Omit a heading when that group has no bullets. Put a blank line after each heading, then that group's bullets.
Put a blank line after the last bullet of a section before the next heading.
Do not flatten into one list, and do not add other headings or regroup by theme, SDH, or product area.

### PRs

One bullet per authored source PR. Never lump distinct source PRs onto one line.
The only authored grouping is a source PR plus qualifying backports of that same PR.
A PR bullet links that PR as `[label](URL)` and, when grouped, each qualifying backport.
After each PR link, put `:merged:` or `:pr-open:` as specified under Icons.
A source PR plus two merged qualifying backports contains three `[label](URL) :merged:` pairs.
Describe qualifying backport effort as `Resolved the <branches> backports for <change>`.
Use `Adapted` instead of `Resolved` only when evidence shows branch-specific implementation changes; never say `manually resolved`.
Reviews of others' PRs share one `Reviews:` bullet. Link each reviewed PR with its icon. Do not give a reviewed PR its own bullet.

### Issues

Never put an issue and a PR on the same bullet, even when the PR fixes that issue. Same-theme related issues may share one bullet.
Unrelated issues stay on separate bullets. An issue bullet links each issue as `[label](URL)`.
After each issue link, put `🐛` or `:ticket:` as specified under Icons.

### Slack and other

Keep effortful discussions and investigations as their own bullets (incidents, SDH, attribution, decisions).
Skim low-impact leftovers (CI noise, small reports, acknowledgements) into one bullet, or omit them.
Link each channel thread, design document, or other work product the item represents.
Use DMs as evidence, but do not put inaccessible DM permalinks in the compiled standup.

### Icons and SDH

Never end a line with a link: put that artifact's icon immediately after it.

PRs: after each PR link, `:merged:` if that PR is merged, `:pr-open:` if it is open.
Do not put `🐛`, `:ticket:`, `👀`, or other category icons on PR bullets.

Issues: after the issue link, `🐛` if the issue is a bug (`bug` label, or a defect/regression); `:ticket:` for every other issue.
Do not use `🐛` on PRs or on non-bug issues.

Slack and other: exactly one category icon after the last link on the bullet.
Categories: `✅` completed/resolved without a merge; `🔍` investigation or validation; `👀` review; `🤝` sync or design discussion.
Choose the bullet's primary outcome when one item spans categories.

SDH is metadata, not a category.
Only when evidence directly identifies the activity as SDH work, use `:sdh:` in the summary where the word “SDH” would appear.
Do not append `:sdh:` to artifact/category icons or propagate it to merely related activity.

Done when the compiled standup is in team format, uses those section headings with empty groups omitted and blank lines after each heading and between sections, every authored source PR is its own bullet except a source PR with its qualifying backports, reviews of others share one `Reviews:` bullet, no issue shares a bullet with a PR, every shareable artifact is a `[label](URL)`, every PR link is followed by `:merged:` or `:pr-open:`, and every issue link is followed by `🐛` or `:ticket:`.

## 4. Deliver

`slack_send_message_draft` strips the URL target from both `[label](URL)` and `<URL|label>`, leaving plain label text.
Never invoke `slack_send_message` or `slack_send_message_draft`. Do not copy until the user says they are ready.

- Paste target = newest Slackbot reminder thread that tags `@admin-ux-team`: `slack_search_public` `from:<@USLACKBOT> "share your daily update" in:#admin-ux-internal`, `sort=timestamp`, `include_bots=true`.
  If none exists, the paste target is a standalone message in `#admin-ux-internal`.
  Never paste or post the compiled standup in `#kibana-management`.
- Show the compiled standup and the paste target, then ask if they are ready for `pbcopy`. A yes in the invoking prompt counts.
- On yes: copy the compiled standup as plain text with `pbcopy`, then verify `pbpaste` exactly matches the source and contains one Markdown link per artifact.

Done when the user has seen the compiled standup and paste target, and after a yes `pbpaste` matches with one Markdown link per artifact.
