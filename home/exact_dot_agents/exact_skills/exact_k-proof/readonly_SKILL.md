---
name: k-proof
description: "Use when the user explicitly asks how do you know/prove it/receipt, when non-review/non-build freeform work needs handoff proof, when verifying runtime/UI/external behavior, when prior attempts failed, or when a freeform completion claim depends on multiple evidence sources."
tool_version: ",proof 0.1.0"
---

# Proof

Use `,proof` to turn a hard-triggered non-review/non-build freeform task into a small proof ledger without forcing `/spec`, `/build`, or a palantir legion.
The ledger records criteria, evidence, explicit review notes, blockers, and a machine-readable gate.

Use `,proof` only when at least one hard trigger applies:

- the user explicitly asks for proof, a receipt, "how do you know?", or whether work is done/fixed/verified/safe to hand off
- the final claim depends on runtime, UI, browser, external-service, security/auth, data-migration, destructive-action, or human-handoff evidence
- the freeform change spans multiple files or subsystems and needs two or more independent evidence items to verify
- an earlier attempt failed, verification is flaky, or an unresolved blocker must be tracked

Do not use:

- trivial answer-only work where inline anchors are enough
- docs-only, wording-only, or single-file mechanical edits that can be verified with one inline anchor or one command
- ordinary single-step code edits whose final answer can cite the command/diff directly
- formal `/build` or palantir legions that already carry a criteria ledger, unless the user asks for a separate freeform proof receipt
- `k-review`, `k-light-review`, `/agent-review`, or PR-fix flows unless the user explicitly asks for a separate freeform proof receipt
- human-visible publication; compose/posting skills still own publication packets and approval gates
- evidence likely to contain secrets, tokens, private customer data, or paste-only local paths that would be unsafe in a handoff
- because the task merely feels "non-trivial"

## Workflow

1. **Start a ledger only after a hard trigger fires.**
   Pick a stable topic slug for this proof and run `,proof --topic <topic> start "<goal>"` once the goal is clear enough to state.
   Done when `,proof --topic <topic> status` shows the right goal/topic.

2. **Add criteria before claiming completion.**
   Add only observable criteria: `,proof --topic <topic> add-criterion --requires test "The targeted regression test passes"`.
   Use `--requires diff` for scoped-change review, `file-read` for docs/content inspection, `screenshot` or `browser` for UI/runtime proof, and `log` or `manual-user-confirmation` only when the criterion is explicitly weak.
   Done when every material completion claim has a matching criterion.

3. **Attach evidence immediately after collecting it.**
   Prefer command-backed evidence: `,proof --topic <topic> add-evidence --criterion AC-001 --type test --command "npm test -- --runInBand path/to/test"`.
   Attach artifacts with `--artifact-path`; the CLI copies them into proof state and hashes them.
   Do not attach raw logs or reports that contain secrets; capture a redacted artifact or use a narrower command instead.
   Done when each criterion lists the evidence IDs that are meant to satisfy it.

4. **Review the evidence before trusting it.**
   Inspect with `,proof --topic <topic> show EV-001`, then record why it supports or does not support the criterion:
   `,proof --topic <topic> review --criterion AC-001 --evidence EV-001 --verdict supports --notes "The test log shows exit 0 and the regression assertion passed."` Do not record `supports` from memory or from the command name alone.
   Done when every current proof artifact has a review note tied to its criterion.

5. **Gate the final answer.** Run `,proof --topic <topic> check --json`.
   If it passes, answer from the criteria, evidence IDs, review notes, and verdict.
   If it fails, either collect the missing proof or record a blocker with `,proof --topic <topic> block "<reason>"` and say what remains unverified.
   Finalize a passing handoff ledger with `,proof --topic <topic> finalize`; use `reopen` only when continuing work on a sealed ledger.
   Generate `,proof --topic <topic> report` when handing work to another agent/human or when the user asks for a receipt.

## CLI reference

Load `~/.agents/skills/k-proof/references/cli.md` when you need command syntax, evidence type rules, storage details, JSON shape, or report behavior.
