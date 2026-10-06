---
name: k-handoff
description: "Use when the user says handoff, save a handoff, continue, resume, or pick up <topic>, or switches harness mid-task; writes or reads a cross-harness session note with ,handoff."
---

# Handoff

`,handoff` stores one short Markdown note per topic in `~/.local/share/agent-handoffs/<repo>/<topic>.md`.
Every harness reads the same files, and every worktree of a repo shares one namespace.
Run `,handoff --help` for the interface.

## Save ("handoff X")

Write the note from what is verified in this session, then pipe it in:

```sh
,handoff save <topic> <<'NOTE'
...
NOTE
```

Use a lowercase topic slug (`auth-fix`, `ai-setup-rewrite`). Keep the note under 4 KB with these sections:

- **Goal**: the user's request and success criteria, in their terms.
- **Decisions**: each settled decision with its reason. Include user corrections verbatim.
- **State**: what is done, what is changed but unverified, and the last check result with its command.
- **Open**: remaining work in order, plus blockers and questions for the user.
- **Files**: the paths that matter, one per line.
- **Verify**: the commands that prove the work is done.

Do not paste diffs, logs, or transcripts; point to paths instead.
Do not include secrets or tokens.
Mark anything not verified as `Unknown`; do not state guesses as facts.

## Continue ("continue X")

1. Run `,handoff show <topic>`. If the topic is unknown, run `,handoff list` (or `--all`) and ask which one.
2. Treat the note as a starting point, not as proof. Check the git state and files it names before you rely on them.
3. Continue the first open item. Do not redo work the note marks as done and verified unless the evidence contradicts it.
4. Save an updated note when the user asks for a handoff again or the work changes direction.
