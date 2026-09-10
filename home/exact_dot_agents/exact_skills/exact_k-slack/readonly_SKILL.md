---
name: k-slack
description: "Use for Slack MCP effects: send/schedule messages, thread replies, reactions, canvas create/update, Slack drafts."
---

# Slack (MCP Mechanics)

Owns the mechanics of Slack side effects through the Slack MCP tools available in the current runtime.
Wording is owned by `~/.agents/skills/k-communication/SKILL.md`; whether to publish is the Human-Visible Publication Gate (SOP §3.8, `~/AGENTS.md`).
This skill restates neither.

Use when:

- the user asks to post, reply, schedule, react, or create/edit a canvas in Slack
- another skill needs a Slack side effect after its own draft is approved

Do not use:

- read-only Slack research: call the read/search tools directly; no gate applies
- standup composition: `~/.agents/skills/k-kbn-standup/SKILL.md` (it never sends)
- GitHub effects: `~/.agents/skills/k-github/SKILL.md`; Gmail/Chat: `~/.agents/skills/k-google-workspace/SKILL.md`

## Tool classes (names in this setup)

- Read-only, no gate: `slack_search_channels`, `slack_search_users`, `slack_search_public`, `slack_search_public_and_private`, `slack_read_channel`, `slack_read_thread`, `slack_read_user_profile`, `slack_read_canvas`, `slack_read_file`, `slack_get_reactions`, `slack_search_emojis`, `slack_list_channel_members`.
- Human-visible mutations, SOP §3.8 gated: `slack_send_message`, `slack_schedule_message`, `slack_add_reaction`, `slack_create_canvas`, `slack_update_canvas`.
- User-only mutation: `slack_send_message_draft` writes into the user's own Slack Drafts.
  Use it only when the user asks for a draft in Slack; it never replaces showing the exact payload in session, and it strips link targets from markdown links.

## Before any mutation

1. Resolve ids from live reads, never from memory: `channel_id` via `slack_search_channels` (a user id is the DM channel id), `thread_ts` from `slack_read_thread` or a search hit's message `ts`.
   Done when every id in the payload came from a read in this session.
2. Load `~/.agents/skills/k-communication/SKILL.md` and draft the exact text in standard markdown (≤5000 characters per text element).
   Never emit Slack's stored `<URL|label>` link form.
   Done when the text passes that skill's register, budget, and session-invisibility rules.
3. Preflight: show target (channel or DM, `thread_ts` or top-level, `reply_broadcast`, `post_at` for schedules, canvas id and section ids), exact text, and effect.
   Wait unless existing SOP §3.8 authorization covers this exact target, payload, and effect.
   A harness tool-approval prompt does not replace this step.
4. Send exactly once. On an ambiguous result, read back before any retry; NEVER re-send to recover.
5. Read back: report the returned message or canvas link; when the link is missing, confirm with `slack_read_thread`.
   Done when the reported link resolves to the sent content.

## Constraints (from the tool contracts)

- Externally shared (Slack Connect) channels reject send and schedule.
- `slack_schedule_message`: `post_at` is a Unix timestamp 2 minutes to 120 days ahead; a scheduled message cannot be edited via the API.
- Reactions are human-visible mutations; a duplicate reaction succeeds silently, so read `slack_get_reactions` before adding one.
- Canvas section ids change after every update; read `slack_read_canvas` immediately before each `slack_update_canvas` and NEVER reuse stale ids.
- Private channels and DMs: read only with the user's explicit consent for that source;
  NEVER republish DM permalinks or private-channel content on another surface.

## Leaf boundary

A delegated leaf MUST NOT call any mutation tool; it returns the draft and resolved ids to the root.
`~/.agents/hooks/publish_gate.py` denies leaf publication calls where wired; the boundary holds without it.
