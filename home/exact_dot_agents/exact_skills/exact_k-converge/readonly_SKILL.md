---
name: k-converge
description: "Manual-only loop that re-attacks a claim or changeset until a round yields no correctness findings."
disable-model-invocation: true
---

# Converge

Loop adversarial rounds against a claim or changeset until **dry**: the complete exit condition declared in Step 1.

`disable-model-invocation: true` blocks direct auto-invocation of this skill only.
Explicitly invoked `k-build`, `k-review`, or `k-light-review` flows may hand off here.
Before a handoff, load and follow `~/.agents/skills/k-converge/references/workflow-handoff.md` in full.

Convergence fails in two directions, and both are defects:

- **Stopping early**: one refutation pass, then declaring confidence. Unverified claims survive.
- **Never stopping**: each round rewrites prose, so "no changes" is never reachable. Churn masquerades as rigor.

The filter below is what makes dry reachable. Set it before round 1, not after a round you dislike.

## Step 1 — Declare the exit and the filter

State both in the open, before the first round:

- **Exit**: a full round with zero changes to code, tests, or published text, completed required verification and fresh refutation, and no unresolved correctness findings or mutation verdicts.
- **Filter**: act only on a **correctness** finding. Three classes:
  - (a) a test that can pass while the code is broken — vacuous, non-discriminating, passes for the wrong reason
  - (b) a production bug: wrong behavior, unhandled input, regression against base
  - (c) a factually false statement in a comment, commit message, or published text

Everything else — wording, clarity, naming, "could mention", anything phrased as _consider_ — is **refused, not deferred**.
Say what you refused and why; a silent refusal reads as an oversight.

Completion criterion: exit and filter are written down and the filter names the three classes.

## Step 2 — Pin the baseline

Record the original review scope, HEAD sha, `git status`, index state, and recoverable contents/hashes of scoped working files, including untracked files.
Hash any targeted published text (PR/issue body); record not applicable when there is no publication target.
Existing staged or unstaged changes are valid input. Never clean, reset, or unstage them to establish a baseline.

Pin a new snapshot at each round's start; retain the original scope, prior fixes, findings, and mutation inventory across rounds.
Compare round changes against that round's snapshot. Never narrow review or regression scope to only the latest fixes.
Unexpected source, input, dependency, or environment drift invalidates affected evidence;
resolve it and rerun affected verification before relying on that evidence.

Completion criterion: original scope and current round snapshot captured; pre-existing changes recoverable;
publication hash or non-applicability recorded.

## Step 3 — Mutate before you argue

Run mutation probes before spawning any reviewer in every round.
First verify the unmutated control passes the checks used as mutation oracles.

For every behavioral change in the diff, break the production code deliberately and check whether a test fails.
Cover each branch of each new predicate: invert it, force each return value, neuter each guard, make each regex match nothing and everything, and raise each cap to effectively infinite.

Verify each mutation actually applied and exercises the intended contract.
Count it as caught only when a test fails for that violation; unrelated setup, syntax, or harness failures do not count.
A surviving contract-breaking mutation is a class (a) finding.
Exempt an equivalent mutation only with evidence of unchanged observable behavior across its affected contract;
uncertainty remains unresolved. Repair invalid probes and replace equivalent probes where needed to exercise the behavioral change.
Never use those classifications to erase a coverage gap.
Report caught/total valid contract-breaking mutations, equivalent and invalid probes with evidence, and unresolved verdicts separately.
The ratio measures the selected mutations' coverage, not confidence in correctness.
For instruction artifacts, distinguish text/structure preservation from consumer behavior;
string-presence or deletion checks do not prove agent compliance.

Restore after each mutation from a copy and verify exact restoration of working contents and index state, including pre-existing changes.

Completion criterion: every behavioral change has a valid contract-breaking probe, every verdict has evidence, and no mutation residue remains.
Unresolved probes prevent a dry verdict.

## Step 4 — Fan out refuters under the filter

Spawn fresh refutation passes every round, each on a distinct dimension (correctness, published claims, test integrity, environment/CI).
Keep their judgments independent.
Verified raw artifacts may be reused after checking identity, hashes, and dependencies;
prior verdicts never replace fresh refutation or required checks.
Give each the filter verbatim and tell it to return "no correctness findings" rather than pad.

Two rules that come from real failures:

- **Isolate**: a refuter that mutates source must run in its own worktree.
  Refuters mutating the tree you are testing in produce transient failures you will misattribute to your own edit.
- **Never forward-chain on a refuter's verdict.** Re-verify every material finding against the artifact yourself.
  Refuters confidently assert wrong things; in practice they have inverted a real finding and invented a stale-test claim that would have broken passing code.

Completion criterion: each refuter returned findings or an explicit "none", and every finding you plan to act on was independently re-verified.

## Step 5 — Act, refuse, and re-verify discrimination

Fix class (a)/(b)/(c) findings. List refusals with reasons.
Class (c) fixes that amend commits or edit published text must pass the SOP §3.2 commit gate and §3.8 publication approval before being applied; working-tree fixes need no gate.

After fixing, re-run the mutation probes that cover the touched code.
Every round must also rerun all required regression checks for the full review scope; targeted post-fix probes do not replace them.
A fix that quietly weakens a test is the failure this step exists to catch — a test-harness "improvement" can neutralize the very tests it was meant to protect.

Beware the **no-op revert**: `git stash` on a file whose change is already committed stashes nothing, so the tests trivially pass and you conclude "verified by reverting".
Mutate in place and restore from a copy instead.

Completion criterion: every finding is fixed or explicitly refused, and post-fix mutation coverage is unchanged or better.

## Step 6 — Round verdict

Compare against this round's Step 2 snapshot. Changed anything?
Increment the round, pin its snapshot in Step 2, and repeat Steps 3–5 over the full retained scope. Changed nothing?
Stop as dry only after required verification and fresh refutation finish with no unresolved correctness findings or mutation verdicts.
Incomplete checks, pending refuters, unexplained drift, and unresolved findings are not dry.
Continue locally resolvable work; report a verified external blocker when it prevents completion.

Report per round: mutations caught/total, findings by class, refusals, and what changed.

Completion criterion: a dry round is reached, or a blocker is named that no further round can clear.

## Honest residue

Convergence bounds what your evidence covers; it does not extend it.
When the loop goes dry, state plainly what remains unverified — the end-to-end run you never executed, the environment you could not reproduce.

Do not let a dry loop imply coverage you never had.
If a real run is merely inconvenient rather than blocked, run it instead of writing it off:
pin the tool version you need, fetch the matching binary, and match the harness's transport and auth expectations.
