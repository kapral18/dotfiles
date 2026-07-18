---
name: k-proof
description: "Use only for non-review/non-build freeform work when the user explicitly requests a proof ledger/receipt, a security/auth, data-migration, or destructive effect needs an auditable record, or a named handoff/resume consumer needs criteria, attempt history, or a blocker preserved."
tool_version: ",proof 0.2.0"
---

# Proof

Use `,proof` to create a durable local receipt for qualifying non-review/non-build freeform work without forcing `/k-spec`, `/k-build`, or a Palantír legion.
The ledger records criteria, evidence assessments, blockers, and a machine-readable gate.
It is not verification itself: the SOP's source reads, probes, tests, and inline evidence remain mandatory whether or not a ledger exists.

Use `,proof` only when at least one receipt trigger applies:

- the user explicitly asks for a proof ledger, durable receipt, or handoff artifact
- a security/auth, data-migration, or destructive effect needs an auditable record
- a named handoff or resume consumer needs multiple criteria, flaky-attempt history, or a blocker preserved

No other task property is a trigger by itself.

Do not use:

- runtime, UI, browser, or external-service verification merely because it needs a live probe
- multi-file, multi-subsystem, or multi-evidence work merely because of its size
- a failed command, retry, or Requirements Reset unless a named handoff/resume consumer needs that history
- "are you sure?", "is it done?", "verify this", or "how do you know?" when re-running and citing the relevant evidence inline answers the question
- ordinary answer-only, docs, wording, mechanical, or code work whose final answer can cite evidence directly
- formal `/k-build` or palantir legions that already carry a criteria ledger, unless the user asks for a separate freeform proof receipt
- `k-review`, `k-light-review`, `/k-agent-review`, or PR-fix flows unless the user explicitly asks for a separate freeform proof receipt
- human-visible publication; compose/posting skills own publication packets and may consume an already-finalized receipt
- evidence likely to contain secrets, tokens, private customer data, or paste-only local paths that would be unsafe in a handoff
- because the task merely feels "non-trivial"

## Workflow

1. **Decide before collecting ledger-bound evidence.**
   Name the receipt trigger and its consumer or audit need at intent/readiness, or as soon as that need becomes known.
   Do not create a ledger near the final answer merely to repackage checks that are already sufficient inline.

2. **Start one ledger for one goal.**
   Pick a stable topic slug and run `,proof --topic <topic> start "<goal>"` once the goal is clear enough to state.
   `start` refuses to reuse a topic whose existing goal differs.
   Choose a new topic, or use `--force` only when intentionally replacing that ledger and deleting its prior managed evidence/reports.
   Done when `,proof --topic <topic> status` shows the right goal/topic.

3. **Add criteria before claiming completion.**
   Add only observable criteria: `,proof --topic <topic> add-criterion --requires test "The targeted regression test passes"`.
   Use `--requires diff` for scoped-change review, `file-read` for docs/content inspection, `screenshot` or `browser` for UI/runtime proof, and `log` or `manual-user-confirmation` only when the criterion is explicitly weak.
   Done when every material completion claim has a matching criterion.

4. **Attach evidence immediately after collecting it.**
   Prefer command-backed evidence: `,proof --topic <topic> add-evidence --criterion AC-001 --type test --command "npm test -- --runInBand path/to/test"`.
   Attach artifacts with `--artifact-path`; the CLI copies them into proof state and hashes them.
   Do not attach raw logs or reports that contain secrets; capture a redacted artifact or use a narrower command instead.
   Done when each criterion lists the evidence IDs that are meant to satisfy it.

5. **Assess the evidence before trusting it.**
   Inspect with `,proof --topic <topic> show EV-001`, then record why it supports or does not support the criterion:
   `,proof --topic <topic> review --criterion AC-001 --evidence EV-001 --verdict supports --notes "The test log shows exit 0 and the regression assertion passed."` Do not record `supports` from memory or from the command name alone.
   `review` records an assessment; it is not an independent or adversarial certification, even when `--reviewer` names another actor.
   Done when every current proof artifact has a review note tied to its criterion.

6. **Finalize the receipt.** Run `,proof --topic <topic> finalize`; it evaluates the gate and seals only a passing ledger.
   Use `check --json` for read-only diagnosis before finalization, not as the handoff boundary.
   If evidence is missing, collect it before finalizing.
   For a named blocked handoff only, record the blocker, seal the failing state with `finalize --allow-failing`, and state that completion is not proven.
   Use `reopen` only when continuing work on a sealed ledger.
   Generate `,proof --topic <topic> report` after finalization when handing work to another agent/human or when the user asks for the receipt; `report` refuses an unfinalized ledger.
   Answer from the sealed criteria, evidence IDs, assessments, and verdict without pasting raw logs.

## CLI reference

Load `~/.agents/skills/k-proof/references/cli.md` when you need command syntax, evidence type rules, storage details, JSON shape, or report behavior.
