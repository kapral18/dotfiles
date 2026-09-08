# Workflow handoff

Entry is explicit user invocation.
An explicitly invoked `k-build`, `k-review`, or `k-light-review` flow may also hand off here only where that caller defines a handoff trigger; none does today, and SOP §1.1/§3.5 forbid automatic convergence.
That invocation authorizes the scoped handoff without another invocation approval.
Merely loading a caller skill does not authorize its flow.

Authorship and write scope never gate entry; convergence is a verification depth, not a repair grant.
Write scope (see `~/.agents/skills/k-review/references/authorship.md`) decides only Step 5:
a finding inside the caller's write scope is fixed; one outside it (someone else's branch, a read-only packet) is returned as a proposal with the smallest change.
A caller's ordinary one-round fix pass (`k-review/references/review_fixes.md`) is not convergence and must not be looped to imitate it.

Before entry, retain pointers in the existing ledger/spec to the caller and phase, original target/scope, findings, evidence, required checks, open gates/decisions, and existing authorization.
Include the approved spec packet and criteria ledger for `k-build`; keep the selected mode and review gates for `k-review`.
For `k-light-review`, recheck its eligibility predicate; if an escalation trigger holds, route to `k-review` before convergence.

`k-converge` owns repetition and per-round verification once entered; its cadence replaces the caller's ordinary bounded-pass count and once-only check schedule.
All caller checks remain required.
Never bypass caller fix-scope limits, read-only boundaries, ownership, requirements resets, user-only decisions, or publication gates.
The handoff grants no additional edit, commit, push, or publication permission.
Report a finding outside existing fix authority as an unapplied proposal or decision; do not fix it through convergence.

Return the convergence verdict, findings, and current evidence to the caller's ledger/spec, then resume its remaining gates and output contract.
A dry convergence round does not establish caller completion; do not mark unmet criteria or open gates complete.
