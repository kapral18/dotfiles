# Agent Review Runtime Contracts

This file is a compatibility index. Do not load it for worker prompts unless a harness cannot select a role-specific file.

Load the smallest role contract instead:

- Reviewer workers: `~/.agents/skills/agent-review/references/reviewer-worker.md`
- PR necessity auditor: `~/.agents/skills/agent-review/references/pr-necessity-auditor.md`
- Findings auditor: `~/.agents/skills/agent-review/references/findings-auditor.md`
- Live UI reviewer: `~/.agents/skills/agent-review/references/live-ui-review.md`
- Post-review auditor: `~/.agents/skills/agent-review/references/post-review.md`
- Change auditor: `~/.agents/skills/agent-review/references/change-auditor.md`
- Researcher: `~/.agents/skills/agent-review/references/researcher.md`
- Code searcher: `~/.agents/skills/agent-review/references/code-searcher.md`

The controller contract in `~/.agents/skills/agent-review/SKILL.md` owns phase ordering, aggregation, judgment, and side-effect gates.
