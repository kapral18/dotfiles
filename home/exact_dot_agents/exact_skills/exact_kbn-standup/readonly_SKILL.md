---
name: kbn-standup
description: "Prepare Karen's #admin-ux-internal daily-update draft from Slack and GitHub activity."
disable-model-invocation: true
---

# Standup

## Resolve first (don't hardcode IDs)

Team channel is `#admin-ux-internal`.
GitHub scope is every repository in the Elastic organization that the current account can access, including private/internal repositories.
Resolve the rest at runtime:

- `USER` = current Slack user id from `slack_read_user_profile` (no arg).
- `GH` = `gh api user --jq .login`.
- `CHAN` = `#admin-ux-internal` id from `slack_search_channels admin-ux-internal` (only needed to create the draft in step 4;
  the `in:#admin-ux-internal` search modifier takes the name directly).

## 1. Baseline

`BASELINE` = the `Message_ts` of the user's own **last multi-bullet standup post** (not a Slackbot reminder, not chatter).
Find it in both `#admin-ux-internal` and `#kibana-management` via `slack_search_public` and choose the newest result.
`#kibana-management` is historic baseline-only; never draft or post there.
Read it fully — you must not repeat its items and should report status deltas (e.g. `waiting on review` → `merged`).

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

- Enumerate everything, don't keyword-guess: `slack_search_public` `from:<@USER> after:<date>`, `sort=timestamp`, `include_context=false`, **no free-text term**; page the `pagination_info` cursor until you pass BASELINE.
  For private channels/DMs use `slack_search_public_and_private` (ask consent once).
- Search `from:<@USER> SDH after:<date>` with context and map only explicitly named PRs/issues/discussions to SDH work.
  Do not infer SDH association from product area.
- Triage for team relevance: keep effortful work (incident/severity assessments, investigations, decisions);
  drop social/off-topic chatter and acknowledgements.

## 3. Draft (team format)

- One `•` per item, terse. Count final items after grouping related work: use no category emojis for three or fewer items.
  For four or more items, end each non-merge bullet with exactly one category emoji.
- For merged work, put one `:merged:` immediately after each merged PR URL.
  A source PR plus two qualifying backports contains three `URL :merged:` pairs.
- Categories: `:merged:` merged; `✅` completed/resolved without a merge; `🐛` defect or issue; `🔍` investigation or validation; `👀` review;
  `🤝` sync or design discussion. Choose the bullet's primary outcome when it spans categories.
- SDH is metadata, not a category.
  Only when evidence directly identifies the activity as SDH work, use `:sdh:` in the summary where the word “SDH” would appear.
  Do not append `:sdh:` to artifact/category icons or propagate it to merely related activity.
- Use bare URLs; Slack's draft composer does not reliably make Markdown-label or mrkdwn links clickable.
  Never end a line with a URL: put its category icon immediately after it.
- Link every shareable artifact represented by an item: source PR, each qualifying conflict/CI-work backport, issue, channel thread, design document, or other referenced work product.
  Use DMs as evidence, but do not put inaccessible DM permalinks in a team-channel draft.
- Describe qualifying backport effort as `Resolved the <branches> backports for <change>`.
  Use `Adapted` instead of `Resolved` only when evidence shows branch-specific implementation changes; never say `manually resolved`.
- Do not join unrelated work because one activity blocked validation of another.
  Operational investigations and the technical change they happened to delay are separate bullets.
- New work only; report status deltas vs the last standup; state verified facts ("added", not "will add");
  high-level units, not micro-steps.

## 4. Submit draft

- Draft target = newest Slackbot reminder thread that tags `@admin-ux-team`: `slack_search_public` `from:<@USLACKBOT> "share your daily update" in:#admin-ux-internal`, `sort=timestamp`, `include_bots=true` → its `thread_ts`.
- Show the exact draft + target, then create it with `slack_send_message_draft` using `channel_id=<CHAN>` and `thread_ts=<reminder ts>`.
  Never invoke `slack_send_message`.
- If no reminder thread exists, create a standalone draft in `#admin-ux-internal`.
- Return the draft link. Do not add a `Sent using Cursor` suffix.
