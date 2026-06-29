---
name: standup
description: "Prepare Karen's #kibana-management standup from Slack and GitHub activity, then await approval."
disable-model-invocation: true
---

# Standup

## Resolve first (don't hardcode IDs)

Team is `#kibana-management` on `elastic/kibana`. Resolve the rest at runtime:

- `USER` = current Slack user id from `slack_read_user_profile` (no arg).
- `GH` = `gh api user --jq .login`.
- `CHAN` = `#kibana-management` id from `slack_search_channels kibana-management` (only needed to post in step 4;
  the `in:#kibana-management` search modifier takes the name directly).

## 1. Baseline

`BASELINE` = the `Message_ts` of the user's own **last multi-bullet standup post** (not a Slackbot reminder, not chatter).
Find via `slack_search_public` `from:<@USER> in:#kibana-management`.
Read it fully — you must not repeat its items and should report status deltas (e.g. `waiting on review` → `merged`).

## 2. Gather (only events strictly after BASELINE)

Search `--created`/`after:` filters are day-granular; always compare the exact timestamp before including an item.

GitHub (author `GH`):

- Authored PRs: `gh search prs --repo elastic/kibana --author <GH> --json number,title,state,createdAt,updatedAt,closedAt,url --sort updated --limit 30`.
  For PRs that were `waiting on review` last time, confirm `mergedAt`.
  For still-open PRs, confirm real work by last `committedDate` (not `updatedAt`, which others' comments bump).
- Issues filed: `gh search issues --repo elastic/kibana --author <GH> --created ">=<date>"`.
  Before claiming meta/sub-issue linkage, verify it: `gh api repos/elastic/kibana/issues/<meta>/sub_issues`.
- Reviews on others' PRs: `gh search prs --repo elastic/kibana --reviewed-by <GH> --updated ">=<date>"`;
  confirm the review timestamp via `gh api repos/elastic/kibana/pulls/<n>/reviews`.

Slack (catches work that never hits GitHub — incidents, impact assessments):

- Enumerate everything, don't keyword-guess: `slack_search_public` `from:<@USER> after:<date>`, `sort=timestamp`, `include_context=false`, **no free-text term**; page the `pagination_info` cursor until you pass BASELINE.
  For private channels/DMs use `slack_search_public_and_private` (ask consent once).
- Triage for team relevance: keep effortful work (incident/severity assessments, investigations, decisions);
  drop social/off-topic chatter and acknowledgements.

## 3. Draft (team format)

- One `•` per item, terse; bare GitHub URLs (no `[text](url)` — Slack auto-links).
- Group backports on one bullet: `Merged 9.4/9.3/8.19 backports for <fix> — <url>, <url>, <url>`.
- New work only; report status deltas vs the last standup; state verified facts ("added", not "will add");
  high-level units, not micro-steps.

## 4. Approve, then post

- Post target = newest Slackbot reminder thread: `slack_search_public` `from:<@USLACKBOT> "share your daily update" in:#kibana-management`, `sort=timestamp`, `include_bots=true` → its `thread_ts`.
- Show the draft + target and **wait for explicit approval** (human-visible post; "show/prepare it" is not approval).
  On approval: `slack_send_message` `channel_id=<CHAN>`, `thread_ts=<reminder ts>`; return the link.
  Draft-only / tweak first → `slack_send_message_draft`.
- The `Sent using Cursor` suffix is auto-appended; don't add it. If no reminder thread exists yet, ask whether to post standalone.
