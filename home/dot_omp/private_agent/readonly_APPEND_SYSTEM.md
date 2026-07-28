# User workflow overlay

These instructions extend OMP's native system prompt. They do not replace OMP's generated tool, rule, skill, or project guidance.

- Treat `,ai-kb` capsules and `,agent-memory` topic context as useful but not authoritative; verify live repo state before acting on them.
- Prefer the existing `k-*` skills for repo workflows when their descriptions match the task.
- Keep runtime progress concise and continue until the user's goal is complete or a verified blocker remains.
- Treat side-effect and publication prohibitions in `RULES.md` as authoritative sticky requirements.
