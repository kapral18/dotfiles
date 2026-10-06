---
name: k-spec
description: "Use when a request needs a compact implementation plan with explicit acceptance criteria before coding."
---

# Spec

Turn the request into the smallest actionable plan.

1. Establish the actual problem from source evidence. Reuse research already done.
   If the requested outcome already exists or is superseded, report the evidence instead of planning redundant work.
2. Resolve forks from evidence. Ask one direct question only for a decision that is genuinely the user's.
   When a verified domain overlay supplies a planning checklist (for example `k-elastic-domain`), apply it to the fork list.
3. Record the semantic delta: old rule, new rule, intended differences, preserved differences, and evidence.
4. Record the impact map: affected callers and consumers, invariants, and the co-edit set (tests, docs, generated outputs, completions, diagrams) with evidence.
5. Define acceptance criteria as `check:` commands or `judgment:` evidence.
   Read `~/.agents/skills/k-spec/references/check-strength.md` for check design.
   Do not run checks merely to approve the plan; unrun checks are `planned`, not passed.
6. Write the plan with `~/.agents/skills/k-spec/references/packet-template.md` and show it in chat.
   When the user wants it kept or will continue in another session, include it in `,handoff save <topic>` (see `k-handoff`).

Keep target, constraints, in and out of scope, side effects, compatibility intent, and decisions owned by others explicit.
Criteria cover intended and preserved behavior when both exist; a test command alone is not proof of coverage.
The plan is not authority to commit, publish, or start other work. If implementation is already approved, continue without asking again.

## Output

The plan, its planned checks, and the open user decisions.
