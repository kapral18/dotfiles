---
name: k-converge
description: "Use when the user explicitly asks to loop fix and re-review (converge) a claim or changeset until a round yields no correctness findings; never for routine recovery."
---

# Converge

Subagent dispatch: refute (implement for fixes) — every round uses fresh adversarial refuter packets and implementation-band fixes;
the root owns the loop.

Loop adversarial rounds against a claim or changeset until **dry**: the complete exit condition declared in Step 1.

Enter only on an explicit user request for this loop (`/k-converge` or plain words); never start it automatically or for routine recovery.
An explicitly invoked `k-build`, `k-review`, or `k-light-review` flow may hand off here only where that caller defines a handoff trigger;
before any handoff, load and follow `~/.agents/skills/k-converge/references/workflow-handoff.md` in full.
Authorship never gates entry: run the loop on your own changes or on someone else's.
Write scope (`~/.agents/skills/k-review/references/authorship.md`) decides only whether a Step 5 fix is applied or returned as a proposal.

Convergence fails in two directions, and both are defects:

- **Stopping early**: one refutation pass, then declaring confidence. Unverified claims survive.
- **Never stopping**: each round rewrites prose, so "no changes" is never reachable. Churn masquerades as rigor.

The filter below is what makes dry reachable. Set it before round 1, not after a round you dislike.

## Step 1 — Declare the exit, the filter, and the limits

State all of these in the open, before the first round:

- **Exit**: a full round with zero changes to code, tests, or published text, completed required verification and fresh refutation of every dimension Step 4 selects,
  and no unresolved correctness findings or mutation verdicts.
- **Filter**: act only on a **correctness** finding. Three classes:
  - (a) a test that can pass while the code is broken — vacuous, non-discriminating, passes for the wrong reason
  - (b) a production bug: wrong behavior, unhandled input, regression against base
  - (c) a factually false statement in instruction text (skills, SOPs, prompts, agent profiles), a commit message, or published text (docs, help text, user-facing output).
    A false internal code comment or docstring is not class (c); refuse it.
- **Threat model**: who produces the inputs and which failures count (for example, an honest but fallible author on a normal setup).
  Refuse a finding that needs an actor or environment outside it.
- **Scope**: the paths and claims the loop covers.
  When the scope mixes independent surfaces (a tool, policy text, docs), propose separate loops to the user before round 1.
- **Round cap**: the most rounds the loop runs before Step 6 stops and asks; 3 unless the user sets another number.
- **Severity floor**: a finding is low severity when it is class (c), or class (a)/(b) whose failure is cosmetic
  or fails closed (a wrong message or count, a refusal of valid input) and never yields a wrong pass/fail verdict or data loss.
- **Slow oracles**: mark each oracle that takes minutes per run (real toolchain builds, end-to-end suites) for Step 3.

Everything else — wording, clarity, naming, "could mention", anything phrased as _consider_ — is **refused, not deferred**.
Say what you refused and why; a silent refusal reads as an oversight.

Completion criterion: exit, filter, threat model, scope, round cap, severity floor, and slow oracles are written down, and the filter names the three classes.

## Step 2 — Pin the baseline

Record the original review scope, HEAD sha, `git status --porcelain`, and a git-owned snapshot of the whole dirty tree:
`git stash create` (returns a commit sha and leaves the working tree untouched) plus `git ls-files -s | sha256sum` for the logical index.
On a clean tree `git stash create` prints nothing; pin `HEAD` instead and use `HEAD` in place of the stash sha when restoring.
Untracked files a probe may touch MUST be added to that snapshot (`git add -N` or a listed copy); git restores only what it tracks.
Hash any targeted published text (PR/issue body); record not applicable when there is no publication target.
Existing staged or unstaged changes are valid input. Never clean, reset, or unstage them to establish a baseline.

Mutate in place by default; the restore set is every tracked path, enforced by git, not a hand-maintained copy list.
Isolate only when the root must keep editing the same tree during rounds or a probe writes under untracked build outputs:

- small repo: `git worktree add --detach /tmp/converge-<id>/tree HEAD` then `git apply` the pinned dirty diff;
- large repo (node_modules or build outputs required by oracles): sparse worktree of the mutation scope with `node_modules`/`target`/`data` symlinked from the main checkout;
  every probe path MUST be checked against those symlinked roots before it runs;
- APFS full tree: `cp -c` (clonefile) of the checkout.

NEVER run a full `git worktree add` of a large repository for a convergence round.

Pin a new snapshot at each round's start; retain the original scope, prior fixes, findings, and mutation inventory across rounds.
Compare round changes against that round's snapshot. Never narrow review or regression scope to only the latest fixes.
Unexpected source, input, dependency, or environment drift invalidates affected evidence;
resolve it and rerun affected verification before relying on that evidence.

Completion criterion: original scope, stash sha, status, and index hash captured; pre-existing changes recoverable from the stash sha;
isolation mode named with its reason (or "in place"); publication hash or non-applicability recorded.

## Step 3 — Mutate before you argue

Run mutation probes before spawning any reviewer in every round.
First verify the unmutated control passes the checks used as mutation oracles.
Run each mutant first against the tests that cover the mutated module (fast tests before slow or end-to-end ones);
rerun the full oracle set only for mutants that survive that first pass, and record SURVIVED only after the full set.
Verdicts must stay identical to a full-set run — a caught mutant needs a failing test for that violation either way.
Round 1 runs every mutant; so does any round whose mutation operators, oracle set, or oracle environment changed.
After that, run the full procedure above for every mutant on code changed since the previous round's pin, every mutant with no identical prior mutant, and every prior non-CAUGHT verdict.
Revalidate every other prior CAUGHT mutant by running it against its recorded killing test on the current tree;
keep CAUGHT only when that test still fails for that violation, and otherwise run the mutant through the full procedure.
NEVER carry a verdict forward without that run. NEVER reuse a SURVIVED, TIMEOUT, INVALID, or unresolved verdict.
Report revalidated and fully rerun counts separately.
After round 1, run a slow oracle only for mutants in code that oracle exercises directly, and record which oracles each verdict used.

For every behavioral change in the diff, break the production code deliberately and check whether a test fails.
Cover each branch of each new predicate: invert it, force each return value, neuter each guard, make each regex match nothing and everything, and raise each cap to effectively infinite.
For a change with a resolvable `,formal` unit (SOP `3.6`), run `,formal mutate <unit>` and fold its model mutants into this round's mutation inventory
alongside the code-level probes above; a model mutant never touches the repo, so the restore contract below applies only to code-level probes.
Count a model mutant as caught only when `,formal mutate` reports it killed by its own declared `killedBy` property; `wrong-killer` (killed,
but not by a declared property) and `survived` are both findings, never folded into the caught count.

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

Restore after each mutation from the Step 2 stash sha, without touching the git index by hand:
`git read-tree <stash-sha>^2` (pinned index; `git read-tree HEAD` when the pin is a clean `HEAD`),
then `GIT_INDEX_FILE=<tmp-index> git read-tree <stash-sha>` and `GIT_INDEX_FILE=<tmp-index> git checkout-index -a -f` with a throwaway index path outside `.git` (pinned working files, including symlinks and probe-deleted files; use `HEAD` for a clean pin), then delete `<tmp-index>`,
then `git ls-files --others --exclude-standard -z | xargs -0 rm -f` (probe-created files).
Do not use `git checkout <sha> -- .` for this: it stages the restored files and changes the pinned status.
Do not use `git archive <sha> | tar -x`: it honors `export-ignore`/`export-subst` attributes, so it skips or rewrites those files.
Then verify `git status --porcelain` and the `git ls-files -s` hash equal the pinned values.
A restore whose verification differs marks the probe `INVALID`, stops the round, and MUST be repaired before another probe runs;
do not count later probes from a tree that never restored.
Physical `.git/index` bytes may differ by stat cache alone; compare the logical index, not the file.

Completion criterion: every behavioral change has a valid contract-breaking probe, every verdict has evidence, and no mutation residue remains.
Unresolved probes prevent a dry verdict.

## Step 4 — Fan out refuters under the filter

Each round runs fresh `refute`-lane passes under the filter, each on a distinct dimension (correctness, published claims, test integrity, environment/CI); Root moves below owns how they start.
Round 1 runs all four. After that, select dimensions from the previous fix's dependency and claim impact, not only from edited file types:
production behavior can affect correctness, test integrity, published claims about that behavior, and environment/CI assumptions;
tests can affect test integrity and any correctness or published conclusion they support;
instruction or published text affects published claims;
build, deploy, or environment configuration can affect environment/CI and every correctness or test conclusion that depends on it.
Retain a dimension's prior result only when both its reviewed surface and every supporting source, input, dependency, and environment are unchanged.
Every selected or invalidated dimension gets fresh refutation. Keep their judgments independent.
Verified raw artifacts may be reused after checking identity, hashes, and dependencies;
a retained verdict is evidence only for an unchanged dimension and never replaces fresh refutation for a selected dimension or a required check.
Give each the filter and the threat model verbatim and tell it to return "no correctness findings" rather than pad.

Refuters are read-only (`~/.agents/skills/k-review/references/adversarial-verifier.md`:
no working-tree writes, git/GitHub writes, installs, or shared-state mutation) —
mutation belongs to Step 3 alone, so a refuter never collides with the tree under test and needs no isolation of its own.

**Never forward-chain on a refuter's verdict.** Re-verify every material finding against the artifact yourself.
Refuters can assert wrong things confidently, including inverting a real finding or calling a passing test stale.

Completion criterion: each refuter returned findings or an explicit "none", and every finding you plan to act on was independently re-verified.

## Step 5 — Act, refuse, and re-verify discrimination

Route class (a)/(b)/(c) fixes per Root moves below; edit inline only trivial single-site fixes.
List refusals with reasons.
Fix packets keep each code comment to current behavior in one line: no history, no probe narratives such as "confirmed against ...", no rationale paragraphs.
Each added sentence is a new claim the next round must check.
Class (c) fixes that amend commits or edit published text must pass the SOP §3.2 commit gate and §3.8 publication approval before being applied; working-tree fixes need no gate.

After fixing, re-run the mutation probes that cover the touched code.
Every round must also rerun all required regression checks for the full review scope; targeted post-fix probes do not replace them.
A fix that quietly weakens a test is the failure this step exists to catch — a test-harness "improvement" can neutralize the very tests it was meant to protect.

Beware the **no-op revert**: `git stash` on a file whose change is already committed stashes nothing, so the tests trivially pass and you conclude "verified by reverting".
Mutate in place and restore from the Step 2 stash sha instead.

Completion criterion: every finding is fixed or explicitly refused, and post-fix mutation coverage is unchanged or better.

## Step 6 — Round verdict

Compare against this round's Step 2 snapshot. Changed anything?
Increment the round, pin its snapshot in Step 2, and repeat Steps 3–5 over the full retained scope. Changed nothing?
Stop as dry only when Step 1's exit condition holds in full.
Incomplete checks, pending refuters, unexplained drift, and unresolved findings are not dry.
Continue locally resolvable work; report a verified external blocker when it prevents completion.
Stop and ask the user before starting another round when the round cap is reached, or when every finding in the round just finished is at or below the severity floor.
Report the findings, per-round wall time and token usage when available, and the residue.
NEVER start another round in either case without the user's explicit go-ahead.

Report per round: mutations caught/total, findings by class, refusals, and what changed.

Completion criterion: a dry round is reached, the loop stopped and asked under the rule above, or a blocker is named that no further round can clear.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Launch distinct fresh `refute`-lane passes for each dimension Step 4 selects (all four in round 1:
correctness, published claims, test integrity, environment/CI), each as `k-agent-adversarial-verifier`;
pass the applicable launch instructions from `~/.agents/skills/k-review/references/runtime-harnesses.md` (and, for Pi/OMP, `~/.agents/skills/k-review/references/runtime-harnesses-pi-omp.md`) as a packet pointer only — the root does not open them; report the resolved model/effort.
Dispatch class (a)/(b)/(c) fixes to the `implement`-category worker per SOP §3.7 (`~/.agents/skills/k-build/references/implement-worker.md`).
Size those fix packets per `~/.agents/skills/k-build/SKILL.md` Root moves.
Run Step 3 and post-fix mutation probes in a `mechanical` packet or script; NEVER inside an implement packet.
Per-harness profile names live in `~/.config/ai/agent-bands.v1.json` → `harnesses.<h>.agents`.
The root MUST NOT substitute its own inline refutation or inline fixes for those packets absent an explicit user no-delegation instruction;
if a required lane or tool is unavailable, report blocked.

## Honest residue

Convergence bounds what your evidence covers; it does not extend it.
When the loop goes dry, state plainly what remains unverified — the end-to-end run you never executed, the environment you could not reproduce.

Do not let a dry loop imply coverage you never had.
If a real run is merely inconvenient rather than blocked, run it instead of writing it off:
pin the tool version you need, fetch the matching binary, and match the harness's transport and auth expectations.
