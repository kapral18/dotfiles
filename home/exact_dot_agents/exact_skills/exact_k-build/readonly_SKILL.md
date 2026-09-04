---
name: k-build
description: "Manual-only controller contract for /k-build: hands-free implementation of an approved spec packet, gated by a criteria ledger, adversarial verification, and a final report."
disable-model-invocation: true
---

# Build

This is the controller contract for `/k-build` — the creation-side sibling of `/k-deep-review`.
It implements an approved **spec packet** (from the `k-spec` skill) hands-free: the human touches the flow at exactly two gates —
packet approval before execution, and the final report. Everything between runs without asking, inside the side-effect boundary below.

The SOP owns the surrounding gates: per-step verification loops (§3.5), requirements reset (§3.4), compatibility (§2.1), and state-machine verification (`### 3.6 State-Machine Verification`).
The `k-code-quality` skill owns minimal edit scope at point of use.
This skill owns the phase order, the criteria ledger, and the verification topology.

## Do not use

- no spec packet exists and the change is trivial or intent is already unambiguous — work directly under the SOP
- the target is reviewing existing changes or a PR: the `k-review` / `k-deep-review` skills

## Side-effect boundary

Packet approval authorizes working-tree edits and verification mutations (installs, codegen, running tests) for the packet's in-scope work —
nothing else.
Commits, pushes, issue/PR creation, comments, and every other publication keep their own explicit-approval gates (`k-git`/`k-github` skills, SOP §3.8).
The packet's **Out of scope** list is binding: an edit that serves no criterion is scope expansion — revert it or stop and re-approve.

## Criteria ledger

The ledger is the run's spine: one row per acceptance criterion, updated as phases progress, reported in full at the end. Statuses:

- `red` — check exists, currently failing (the starting state proven by the packet)
- `green` — check run this flow, exit 0, with the invocation as evidence
- `judgment-met` / `judgment-unmet` — judgment criterion, with the evidence named by the packet
- `blocked` — cannot be evaluated, with the exact blocker and the command the user must run

The verification phase adds a verdict per row: `confirmed` / `refuted` / `undecidable (needs <check>)`.
Verdicts are evidence, not decisions: the controller flips a ledger row only after checking the refutation addresses the row's actual claim.
A fix made in response to a verdict is itself unverified: re-run the row's check afterwards, and prefer mutating the code so the row's claim would be false to confirm the check actually catches it.
When rows keep reopening across verification passes, run `~/.agents/skills/k-converge/SKILL.md` and follow its workflow-handoff contract with the approved spec packet and criteria ledger.

## Phase order (strict)

Do not start a later phase until the current one completes.

1. **Spec gate (human gate 1).**
   Obtain the spec packet: the active `/tmp/specs/<pwd>/<topic>.spec.md`, a user-supplied file, or — when none exists —
   run the `k-spec` skill now.
   If any criterion lacks a run-once red check or a `judgment:` tag, return to the `k-spec` skill;
   criteria are authored there, never backfilled mid-build. Present the packet and stop for explicit approval.
   If the packet is not proven mechanical-only and lacks a semantic delta, return to `k-spec` before presenting it:
   old rule, new rule, intended differences, preserved differences, and evidence belong in the packet, not mid-build memory.
   Approval of the packet is the hands-free authorization; proceed on in-scope work after it without re-asking permission.

2. **Plan and wave topology.**
   Decompose into steps, each with its own verification (SOP §3.5) — a criterion check, a targeted test, or a probe.
   Group independent, non-conflicting steps touching disjoint contracts into parallel execution waves (foundational types/schema first, parallel domain modules second, integration third).
   Run the Ownership Gate (SOP §3.3) over the paths the plan touches before any edit.
   Carry the packet's semantic delta into the plan: every intended difference and every locally observable preserved difference needs a check, probe, or named judgment row.
   For stateful/parser-like/branch-heavy targets, plan the SOP State-Machine Verification harness during planning.

3. **Execute.**
   Work waves in order; serial steps execute inline in the controller, while parallel steps dispatch subagent workers in category `implement` (resolved via `tiering.yaml`).
   Enforce scratch-isolated worker returns: each delegated worker writes detailed implementation logs, traces, and file diffs to `/tmp/scratch/<pwd>/<topic>/step-<N>.log` and returns a single compact status line to the controller (`step <N>: green|red|blocked (<check> exit <N>, touched: <paths>)`).
   Update the ledger after each step or wave. Run checks bare — a piped check (`cmd | tail`) reports the pipe's exit code, not the check's.
   Never proceed past a red step verification — fix or replan.
   Two consecutive failed attempts on the same criterion trigger the SOP §3.4 reset:
   stop implementing and end the flow as `blocked` with the captured failure, instead of thrashing.
   If evidence found mid-build contradicts the packet (wrong premise, wrong scope, missing intended difference, or missing preserved difference), stop, state the correction, and return to gate 1 with the revised packet — implementing a silently different spec is a flow violation.

4. **Mechanical gates.**
   Discover the repo's lint / type-check / test commands from repo sources (do not guess), prefer scoped commands for the affected package, and run them.
   An unprepared environment is a setup step to perform, not a blocker; loop fix → verify until green.
   Only undiscoverable or failing setup itself is a blocker — report the exact command and error.

5. **Live-UI proof.**
   Run this when any acceptance criterion's evidence is visual — a `judgment:` criterion naming a screenshot/visual comparison, or an in-scope UI-facing change with a stated visual goal.
   Load `~/.agents/skills/k-ui-capture/references/proof-mode.md` and run it inline (this flow already holds Playwriter and local/dev mutation permissions), head-only against the built runtime.
   Supply the built worktree/branch, the changed UI paths, the visual criterion as the intended-visual oracle, the selected target packet (for verified `elastic/kibana`, the overlay's `~/.agents/skills/k-elastic-domain/references/kibana-live-ui.md`; otherwise the explicit user/repo-documented local/dev packet), the required runtime config, and the `/tmp` output location (each visual criterion's proof set in its own distinct `/tmp/<folder-name>/` folder).
   The proof-mode contract verifies the local browser only; when the user explicitly wants Windows/VirtualBox coverage too, add the manual `~/.agents/skills/k-live-ui-windows/SKILL.md` skill to this turn's work by hand instead of inferring it from the spec/issue context.
   Set each visual criterion's ledger row from the returned verdict with the captured visual proof (screenshot or video) as its evidence:
   `met` -> `judgment-met`, `unmet` -> back to phase 3 like a red step, `blocked` -> `blocked` with the exact blocker.
   Skip only when no criterion is visual; record the skip reason.
   A read-only/Ask-mode Playwriter block or an unstartable runtime is a valid `blocked`, not a silent skip.

6. **Adversarial verification.** First re-run every packet check once from the current tree — machine truth before judgment.
   Then delegate one isolated **read-only** refutation lane with the packet, the full implementation diff, and the ledger.
   Launch it via the harness's named `k-agent-criteria-verifier` profile (rendered per harness with the review-model resolver's **verifier** slot — the same cross-family pick `/k-deep-review` uses).
   In Antigravity, define a dynamic `k-agent-criteria-verifier` from `~/.agents/skills/k-build/references/criteria-verifier.md` and invoke it with the registry's `pro` tier.
   On a harness without a named profile (Claude), run the lane as a generic read-only subagent on the session model that loads the same contract, with refutation framing, and report `families=same (degraded)` — never skip the phase silently.
   The verifier must try to refute the semantic delta, not only the positive criteria:
   look for behavior that changed outside intended differences and for intended differences not covered by checks.
   Judge the returned verdicts; a `refuted` row goes back to phase 3 (or `blocked` with the reason).

7. **Post-review stage.**
   Run the Post-Review Stage from `~/.agents/skills/k-review/references/judging_pipeline.md` over the full implementation diff, applying the four canonical dimensions by name — redundancy, verbosity, semantic + logical duplication, gaps.
   Resolve each finding in the working tree; re-run mechanical gates for changed artifacts when applicable.
   Repeat the Post-Review Stage until it returns clean, or until a verified blocker/requirements reset stops the loop.
   If cleanup changed any in-scope artifact, rerun packet checks and adversarial verification before reporting.

8. **Report (human gate 2).** Emit the Output block. Nothing is committed, pushed, or published here.

## Completion gate

Do not declare `/k-build` complete while any ledger row is `red`, `judgment-unmet`, or `undecidable` without an explicit blocker, while a mechanical gate is un-run, while a triggered live-UI proof was skipped without a valid blocker, or while the verification lane was skipped.
A blocked flow ends as `blocked` with the ledger as-is — never as a success summary with hedged wording.

## Output

- Spec packet: path + approval reference.
- Criteria ledger: every row with status, evidence (command + exit), and verification verdict.
- Semantic delta: old rule, new rule, intended differences, preserved differences, and which ledger rows proved each locally observable item.
- Adversarial verification: families used (`<session-family> vs <verifier-family>` or `same (degraded)`), verdict counts, scope-audit result.
- Mechanical gates: commands run with results, or the exact blocker.
- Live-UI proof: per-criterion `met` / `unmet` / `blocked` verdicts and the screenshot manifest (each set in its own `/tmp/<folder-name>/`), or `skipped (no visual criterion)`.
- Post-review stage: result per dimension (clean, or what was cleaned).
- Scope: files changed, each traced to a criterion; out-of-scope confirmation.
- Remaining unknowns / blockers, and the suggested next move (commit via `k-git` skill, PR via `k-compose-pr` —
  which can embed the captured visual proof — or fixes).
- Completion gate: clear, or blocked with the unresolved rows.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
