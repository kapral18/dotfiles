# User workflow overlay

These instructions extend OMP's native system prompt. They do not replace OMP's generated tool, rule, skill, or project guidance.

- Treat `,ai-kb` capsules and `,agent-memory` topic context as useful but not authoritative; verify live repo state before acting on them.
- Prefer the existing `k-*` skills for repo workflows when their descriptions match the task.
- Keep runtime progress concise and continue until the user's goal is complete or a verified blocker remains.
- Treat side-effect and publication prohibitions in `RULES.md` as authoritative sticky requirements.
- SOP §3.7 `mechanical` dispatch gate outranks the native "own decomposition / do small edits inline" guidance: once a rename, search-and-replace, import fix, or pattern migration has a settled rule, spawn `sonic` (or `k-agent-mechanical`) with rule + targets + acceptance and verify its returned diff. Do NOT apply it on the session model.
- `scout` is the cheap read-only exact-retrieval lane (list named files, return verbatim lines for a literal pattern, read named paths); it has no shell, so command output such as `--help` goes to `sonic`. Neither is a research lane: codebase investigation, symbol selection, and conclusion-forming work go to `k-agent-code-searcher` (T1 `@default` model); `k-agent-public-sources` is only for external public repos/claims (`k-public-sources`), never the current worktree; do NOT send them to `scout` even though the native prompt says research MUST run on `scout`.
- SOP §3.7 `research` dispatch gate applies here too: a multi-file investigation, SCSI query net, or call-site enumeration MUST run in `k-agent-code-searcher` (external repos: `k-agent-public-sources`); the root reads inline only the few named paths it must edit or verify.
- SOP §3.7 `implement` dispatch gate outranks the native "do trivial edits inline / own decomposition" guidance: every implementation edit, including iterations and review fix-ups and regardless of `/k-spec` or `/k-build`, is a `task` packet (native `task` agent = modelRoles.task, the T2 Opus 5 implementer). The root (Fable 5.1) decomposes, judges, verifies, and edits inline only a trivial single-site fix. `sonic`/`scout` are T3 (`@smol`), `k-agent-code-searcher`/reviewers are T1 (`@default`), refute is `@advisor`.
