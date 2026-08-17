---
name: k-converge
description: "Manual-only loop that re-attacks a claim or changeset until a round yields no correctness findings."
disable-model-invocation: true
---

# Converge

Loop adversarial rounds against a claim or changeset until a round comes back **dry**.
Dry means one full round produced zero changes to code, tests, or published text.

`disable-model-invocation: true` blocks direct auto-invocation of this skill only.
Sibling skills' explicitly invoked flows (`k-build`, `k-review`, `k-light-review`) may still load this file by path as their bounded-loop procedure.

Convergence fails in two directions, and both are defects:

- **Stopping early**: one refutation pass, then declaring confidence. Unverified claims survive.
- **Never stopping**: each round rewrites prose, so "no changes" is never reachable. Churn masquerades as rigor.

The filter below is what makes dry reachable. Set it before round 1, not after a round you dislike.

## Step 1 — Declare the exit and the filter

State both in the open, before the first round:

- **Exit**: a round with zero changes to code, tests, or published text.
- **Filter**: act only on a **correctness** finding. Three classes:
  - (a) a test that can pass while the code is broken — vacuous, non-discriminating, passes for the wrong reason
  - (b) a production bug: wrong behavior, unhandled input, regression against base
  - (c) a factually false statement in a comment, commit message, or published text

Everything else — wording, clarity, naming, "could mention", anything phrased as _consider_ — is **refused, not deferred**.
Say what you refused and why; a silent refusal reads as an oversight.

Completion criterion: exit and filter are written down and the filter names the three classes.

## Step 2 — Pin the baseline

Record what a change would be measured against: HEAD sha, `git status` (expect clean), and a hash of any published text (PR/issue body) you might edit.

Without a pinned baseline you cannot tell a dry round from an unobserved one.

Completion criterion: sha, tree state, and body hash captured.

## Step 3 — Mutate before you argue

**Mutation is the strongest available signal, and it is cheap.** Run it before spawning any reviewer.

For every behavioral change in the diff, break the production code deliberately and check whether a test fails.
Cover each branch of each new predicate: invert it, force each return value, neuter each guard, make each regex match nothing and everything, and raise each cap to effectively infinite.

A mutation no test catches is a class (a) finding.
Record mutation-count caught vs total; that ratio is the confidence claim you are entitled to make.

Restore after each mutation and verify the tree is clean at the end.

Completion criterion: every behavioral change in the diff has at least one mutation, each with a caught/uncaught verdict, and the tree is clean.

## Step 4 — Fan out refuters under the filter

Spawn independent refuters, each on a distinct dimension (correctness, published claims, test integrity, environment/CI).
Give each the filter verbatim and tell it to return "no correctness findings" rather than pad.

Two rules that come from real failures:

- **Isolate**: a refuter that mutates source must run in its own worktree.
  Refuters mutating the tree you are testing in produce transient failures you will misattribute to your own edit.
- **Forward-chain only on verdicts you re-verified.** Re-verify every material finding against the artifact yourself.
  Refuters confidently assert wrong things; in practice they have inverted a real finding and invented a stale-test claim that would have broken passing code.

Completion criterion: each refuter returned findings or an explicit "none", and every finding you plan to act on was independently re-verified.

## Step 5 — Act, refuse, and re-verify discrimination

Fix class (a)/(b)/(c) findings. List refusals with reasons.
Class (c) fixes that amend commits or edit published text must pass the SOP §3.1 commit gate and §3.6 publication approval before being applied; working-tree fixes need no gate.

After fixing, re-run the mutation probes that cover the touched code.
A fix that quietly weakens a test is the failure this step exists to catch — a test-harness "improvement" can neutralize the very tests it was meant to protect.

Beware the **no-op revert**: `git stash` on a file whose change is already committed stashes nothing, so the tests trivially pass and you conclude "verified by reverting".
Mutate in place and restore from a copy instead.

Completion criterion: every finding is fixed or explicitly refused, and post-fix mutation coverage is unchanged or better.

## Step 6 — Round verdict

Compare against the Step 2 baseline. Changed anything? Increment the round and return to Step 3 — the fix itself is now unverified.
Changed nothing? The loop is dry; stop.

Report per round: mutations caught/total, findings by class, refusals, and what changed.

Completion criterion: a dry round is reached, or a blocker is named that no further round can clear.

## Honest residue

Convergence bounds what your evidence covers; it does not extend it.
When the loop goes dry, state plainly what remains unverified — the end-to-end run you never executed, the environment you could not reproduce.

Let a dry loop imply only the coverage you actually exercised.
If a real run is merely inconvenient rather than blocked, run it instead of writing it off:
pin the tool version you need, fetch the matching binary, and match the harness's transport and auth expectations.
