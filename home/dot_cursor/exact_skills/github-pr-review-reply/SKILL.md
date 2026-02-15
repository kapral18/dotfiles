---
name: github-pr-review-reply
description: "Reply-mode GitHub PR review: respond to existing review threads, clarify intent, propose concrete changes, and resolve when appropriate. Focus on one thread at a time. If the user doesn't specify a PR, assume the current branch PR (infer via `gh prw --number`). Draft replies only; no GitHub posting unless explicitly asked. Do NOT use for initial full PR reviews."
---

# GitHub PR Review - Reply (Thread Iteration)

Primary goal: move existing PR review threads to resolution with minimal churn.

When NOT to use:

- The user is asking for a first-pass PR review with a full findings queue and batch draft comments: use `github-pr-review-start`.
- The user wants to draft and submit one new review comment at a time (not a reply in an existing thread): use `github-pr-review`.

Non-negotiables:

- Resolve the PR target (avoid searching):
  - If the user provided a PR URL/number, use that.
  - Otherwise, assume they mean the PR for the current branch:
    - `gh prw --url`
    - `gh prw --number`
  - If that fails (no PR for current branch / wrong repo / not authenticated), ask for the PR URL.
- Always read the entire thread end-to-end before replying (including earlier context).
- Open and inspect any screenshots/GIFs/videos referenced in the thread.
- Anchor claims in evidence (code location, command output, repro steps).
- Do not post to GitHub unless explicitly asked.
- Assume the user started the agent inside the intended worktree/session already.
  - Do not create/switch worktrees proactively.
  - If the user explicitly asks to create/switch a worktree, use `~/.agents/skills/w-workflow/SKILL.md` and prefer `,w`.

Workflow (repeat per thread):

1. Identify the next active thread (unresolved / awaiting reply).
2. Restate the concern in 1 sentence.
3. Decide the response type:
   - Accept + propose the smallest fix
   - Clarify a misunderstanding with evidence
   - Ask exactly one blocking question (include the default assumption)
4. Draft the reply comment.
5. Decide whether to resolve:
   - Resolve only when addressed and no follow-up is needed.

Output contract:

- Produce one drafted reply at a time:
  - Where it goes (comment id / file thread)
  - Reply body (end with `Wdyt`)
  - Resolution recommendation: `resolve` | `keep_open`

Reply style rules:

- Tone: direct, casual, friendly.
- No quote replies inside threads.
- Keep it short; prefer a concrete change suggestion.
- End every drafted reply with `Wdyt` as its final sentence.
- Keep claims honest: separate what you observed (evidence) vs what you infer (hypothesis)
  vs what you recommend (action).
