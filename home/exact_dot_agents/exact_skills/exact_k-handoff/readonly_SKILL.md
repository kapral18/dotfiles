---
name: k-handoff
description: "Use when the user says handoff, save a handoff, continue, resume, or pick up <topic>, or switches harness mid-task; saves or resumes a task across sessions and harnesses with ,task handoff."
---

# Handoff

`,task handoff` stores one note per topic in `~/.local/share/agent-handoffs/<repo>/<topic>.md`, with the saving session's intent card beside it.
Every harness reads the same files, and every worktree of a repo shares one namespace.
Run `,task handoff --help` for the interface.

## Save ("handoff X")

Write the note from what is verified in this session, then pipe it in:

```sh
,task handoff save <topic> <<'NOTE'
...
NOTE
```

Add `--session <id>` (to `save` and `resume`) when a hook named this session's id; otherwise leave it out.
Use a lowercase topic slug (`auth-fix`, `ai-setup-rewrite`). Keep the note under 4 KB.
The saved card already carries the goal, `Done when` items, scope, decisions (stances), claims, and the last five user corrections;
do not repeat them.
The note holds what the card does not:

- **Approvals**: each commit, push, or PR request still in force, with its repo, branch, and the user's words verbatim,
  and each PR the task opened (`owner/repo#number`).
  Write `none` when there is none.
- **State**: what is done, what is changed but unverified, the last check result with its command,
  the task's starting commit and the paths already changed when it started (or where their task-start copies are), and the path of any `k-review` Verify baseline.
- **Remaining**: remaining work in order, plus blockers and questions for the user.
- **Files**: the paths that matter, one per line.
- **Verify**: the commands that prove the work is done.

A session without a card also writes **Goal** (the user's request and success criteria, in their terms)
and **Decisions** (each settled decision with its reason, user corrections verbatim).

Do not paste diffs, logs, or transcripts; point to paths instead.
Do not include secrets or tokens.
Mark anything not verified as `Unknown`; do not state guesses as facts.

## Continue ("continue X")

1. Run `,task handoff resume <topic>`. It prints the note and makes the saved card this session's card,
   reopening each `Done when` item whose evidence no longer verifies here.
   If the topic is unknown, run `,task handoff list` (or `--all`) and ask which one.
   If this session already has a card for other work, ask the user before `,task card clear`.
2. Treat the note and card as a starting point, not as proof. Check the git state and files they name before you rely on them.
3. A request under **Approvals** carries over to this session (`~/AGENTS.md` §5): a commit request for the same repo,
   a push or PR request for the same repo and branch. Check the repo and branch before you rely on it.
4. Continue the first remaining item. Do not redo work the card marks as checked unless the evidence contradicts it.
5. Save an updated note when the user asks for a handoff again or the work changes direction.
