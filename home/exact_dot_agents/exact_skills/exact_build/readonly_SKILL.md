---
name: build
description: "Manual-only controller contract for /build: hands-free implementation of an approved spec packet, gated by a criteria ledger, adversarial verification, and a final report."
disable-model-invocation: true
---

# Build

This is the controller contract for `/build` — the creation-side sibling of `/agent-review`.
It implements an approved **spec packet** (from the `spec` skill) hands-free: the human touches the flow at exactly two gates —
packet approval before execution, and the final report. Everything between runs without asking, inside the side-effect boundary below.

The SOP owns the surrounding gates: per-step verification loops (§3.4), the state-machine harness (§3.5), requirements reset (§3.3), minimal edit scope (§5), and compatibility (§2.0).
This skill owns the phase order, the criteria ledger, and the verification topology.

The same packet drives `,ralph go --spec <file>` for a detached run; `/build` is the in-session form.

## Do not use

- no spec packet exists and the change is trivial or intent is already unambiguous — work directly under the SOP
- the target is reviewing existing changes or a PR: the `review` / `agent-review` skills
- the user wants a detached/background run: the `ralph` skill (`,ralph go --spec`)

## Side-effect boundary

Packet approval authorizes working-tree edits and verification mutations (installs, codegen, running tests) for the packet's in-scope work —
nothing else.
Commits, pushes, issue/PR creation, comments, and every other publication keep their own explicit-approval gates (`git`/`github` skills, SOP §3.6).
The packet's **Out of scope** list is binding: an edit that serves no criterion is scope expansion — revert it or stop and re-approve.

## Criteria ledger

The ledger is the run's spine: one row per acceptance criterion, updated as phases progress, reported in full at the end. Statuses:

- `red` — check exists, currently failing (the starting state proven by the packet)
- `green` — check run this flow, exit 0, with the invocation as evidence
- `judgment-met` / `judgment-unmet` — judgment criterion, with the evidence named by the packet
- `blocked` — cannot be evaluated, with the exact blocker and the command the user must run

The verification phase adds a verdict per row: `confirmed` / `refuted` / `undecidable (needs <check>)`.
Verdicts are evidence, not decisions: the controller flips a ledger row only after checking the refutation addresses the row's actual claim.

## Phase order (strict)

Do not start a later phase until the current one completes.

1. **Spec gate (human gate 1).**
   Obtain the spec packet: the active `/tmp/specs/<pwd>/<topic>.spec.md`, a user-supplied file, or — when none exists —
   run the `spec` skill now.
   If any criterion lacks a run-once red check or a `judgment:` tag, return to the `spec` skill;
   do not backfill criteria yourself mid-build. Present the packet and stop for explicit approval.
   Approval of the packet is the hands-free authorization; do not re-ask permission for in-scope work after it.

2. **Plan.** Decompose into steps, each with its own verification (SOP §3.4) — a criterion check, a targeted test, or a probe.
   Run the Ownership Gate (SOP §3.2) over the paths the plan touches before any edit.
   For stateful/parser-like/branch-heavy targets, plan the §3.5 harness now, not after the fact.

3. **Execute.** Work the steps in order; after each, run its verification and update the ledger.
   Run checks bare — a piped check (`cmd | tail`) reports the pipe's exit code, not the check's.
   Never proceed past a red step verification — fix or replan.
   Two consecutive failed attempts on the same criterion trigger the SOP §3.3 reset:
   stop implementing and end the flow as `blocked` with the captured failure, instead of thrashing.
   If evidence found mid-build contradicts the packet (wrong premise, wrong scope), stop, state the correction, and return to gate 1 with the revised packet — do not silently implement a different spec.

4. **Mechanical gates.**
   Discover the repo's lint / type-check / test commands from repo sources (do not guess), prefer scoped commands for the affected package, and run them.
   An unprepared environment is a setup step to perform, not a blocker; loop fix → verify until green.
   Only undiscoverable or failing setup itself is a blocker — report the exact command and error.

5. **Live-UI proof.**
   Run this when any acceptance criterion's evidence is visual — a `judgment:` criterion naming a screenshot/visual comparison, or an in-scope UI-facing change with a stated visual goal.
   Load `~/.agents/skills/ui-proof/SKILL.md` and run it inline (this flow already holds Playwriter and local/dev mutation permissions), head-only against the built runtime.
   Supply the built worktree/branch, the changed UI paths, the visual criterion as the intended-visual oracle, the selected target packet (for verified `elastic/kibana`, the overlay's `~/.agents/skills/elastic-domain/references/kibana-live-ui.md`; otherwise the explicit user/repo-documented local/dev packet), the required runtime config, and the `/tmp` output location (each visual criterion's proof set in its own distinct `/tmp/<folder-name>/` folder).
   Require `ui-proof` to open/reveal each proof folder for the user when possible, or provide the folder path and the reason opening was not possible.
   Set each visual criterion's ledger row from the returned verdict with the captured screenshot as its evidence:
   `met` -> `judgment-met`, `unmet` -> back to phase 3 like a red step, `blocked` -> `blocked` with the exact blocker.
   Skip only when no criterion is visual; record the skip reason.
   A read-only/Ask-mode Playwriter block or an unstartable runtime is a valid `blocked`, not a silent skip.

6. **Adversarial verification.** First re-run every packet check once from the current tree — machine truth before judgment.
   Then delegate one isolated **read-only** refutation lane with the packet, the full implementation diff, and the ledger.
   Launch it via the harness's named `criteria-verifier` profile (rendered per harness with the `agent_review_models` **verifier** model —
   the same cross-family pick `/agent-review` uses); on a harness without that profile (Claude), run the lane as a generic read-only subagent on the session model that loads `~/.agents/skills/build/references/criteria-verifier.md`, with refutation framing, and report `families=same (degraded)` — never skip the phase silently.
   Judge the returned verdicts; a `refuted` row goes back to phase 3 (or `blocked` with the reason).

7. **Post-review stage.**
   Run the Post-Review Stage from `~/.agents/skills/review/references/judging_core.md` over the full implementation diff, applying the four canonical dimensions by name — redundancy, verbosity, semantic + logical duplication, gaps.
   Resolve each finding in the working tree; re-run the mechanical gates if the cleanup touched code.

8. **Report (human gate 2).** Emit the Output block. Nothing is committed, pushed, or published here.

## Completion gate

Do not declare `/build` complete while any ledger row is `red`, `judgment-unmet`, or `undecidable` without an explicit blocker, while a mechanical gate is un-run, while a triggered live-UI proof was skipped without a valid blocker, or while the verification lane was skipped.
A blocked flow ends as `blocked` with the ledger as-is — never as a success summary with hedged wording.

## Output

- Spec packet: path + approval reference.
- Criteria ledger: every row with status, evidence (command + exit), and verification verdict.
- Adversarial verification: families used (`<session-family> vs <verifier-family>` or `same (degraded)`), verdict counts, scope-audit result.
- Mechanical gates: commands run with results, or the exact blocker.
- Live-UI proof: per-criterion `met` / `unmet` / `blocked` verdicts and the screenshot manifest (each set in its own `/tmp/<folder-name>/`, with folder-open/provided status), or `skipped (no visual criterion)`.
- Post-review stage: result per dimension (clean, or what was cleaned).
- Scope: files changed, each traced to a criterion; out-of-scope confirmation.
- Remaining unknowns / blockers, and the suggested next move (commit via `git` skill, PR via `compose-pr` —
  which can embed the captured screenshots — or fixes).
- Completion gate: clear, or blocked with the unresolved rows.
- `Compatibility impact: none | removed (requested) | kept existing (requested)`.
