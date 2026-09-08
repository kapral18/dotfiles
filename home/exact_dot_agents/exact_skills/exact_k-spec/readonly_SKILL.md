---
name: k-spec
description: "Use when a request needs a compact implementation packet with explicit final acceptance criteria."
---

# Spec

Develop the active intent topic into the smallest actionable packet. The SOP owns the session lifecycle and safety gates.

1. Establish the actual problem and source evidence. Reuse existing research; do not create a separate necessity-review ceremony.
2. Resolve material forks from evidence; ask one direct question only for a user-owned decision.
   Do not prototype or call advisors automatically.
3. Record the semantic delta: old rule, new rule, intended differences, preserved differences, and evidence.
4. Define final acceptance conditions using `check:` commands or `judgment:` evidence.
   Read `~/.agents/skills/k-spec/references/check-strength.md` for check design.
   Do not execute red/green or mutation probes merely to approve the packet; record unrun checks as planned, not passed.
5. Use `~/.agents/skills/k-spec/references/packet-template.md`, persist the packet under the active `/tmp/specs/<pwd>/<topic>.spec.md`, and add its pointer to the compact topic handoff.

Keep target, action, constraints, in/out scope, side effects, compatibility intent, and externally owned decisions explicit.
Criteria cover intended and preserved behavior when both exist; a test command alone is not proof of coverage.
The packet is an artifact, not authority to commit, publish, or begin another workflow.
If implementation is already approved, continue to Produce without asking again.
Otherwise present the decision/packet requested by the user.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Use a strong research packet for substantial context-heavy questions; keep decisions and packet assembly in the root.
Do not delegate each criterion, run a mechanical check agent, or invoke memory merely to satisfy a step.

## Output

The packet or concise decision plus packet pointer, planned final checks, and unresolved user-owned decisions.
