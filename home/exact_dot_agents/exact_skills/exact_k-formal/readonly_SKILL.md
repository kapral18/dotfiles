---
name: k-formal
description: "Use when SOP §3.6 selects a stateful or parser-like verification tier: build, diagnose, or review a `,formal` catalog unit (anchored Lean model, exhaustive search, mutation, trace replay, optional proofs)."
---

# Formal Verification

Subagent dispatch: inline (research, implement slices) —
research extracts the transition table and proposes anchors for a new or stale unit;
implement authors the model, properties, mutants, and adapter for one unit; the root or another explicitly authorized execution category persists anchors and runs catalog-writing diagnostics, and the root runs `,formal audit` plus any review or refute lens.

This skill owns the mechanics SOP `### 3.6 State-Machine Verification` points at.
The SOP already decided the trigger applies; this skill does not re-route that decision.

## When this applies

SOP §3.6 triggers on stateful, parser-like, ordered, retry/workflow, permission, compatibility-sensitive, or flag-dependent changes.
Pure input-to-output behavior (parsers, formatters, predicates, permission matrices with no history) stays on the disposable independent-oracle harness from SOP §3.6 only when production tests cannot express the cases.
`,formal` is not required for it.
Everything else stateful is a `,formal` catalog unit under this skill: one modeled lifecycle slice of one repo (a scan/cancel/delete lifecycle, a flyout save flow, a retry loop), never a whole repo.

## Tiers

Pick the tier at Scope and record it in the unit `MANIFEST.json`.

- **F1** — pure input→output behavior. No unit; use the disposable independent-oracle harness from SOP §3.6 only when production tests
  cannot express the cases: one harness for the whole task under `/tmp/formal-oracle/<pwd>/<topic>/<slug>/`, never one per worker, with a
  manifest naming target, requested behavior, compatibility intent, and snapshot. Report `formal=tests` and write no manifest when the
  focused tests are the only executable check.
- **F2** — stateful behavior: lifecycles, retries, ordered or flag-dependent state, permissions over time. The default tier.
  Anchors → model → exhaustive search → mutants → trace replay.
- **F3** — F2 plus Lean proofs.
  Add proofs only when behavior-relevant state is unbounded, `explore` reports `bounded` (state or depth budget hit), or the user explicitly asks.
  F3 never replaces F2's search/mutation/replay; it adds a proof stage on top.
- **`--design`** — a design unit models intended behavior before code exists (planning, spec review).
  Anchors may point at plan or spec text instead of code; replay is `n/a-design`.

## Concepts

- **Unit**: `TRANSITIONS.md` (extraction table, every row anchored to `file:start-end`), `Unit/Model.lean` (state/event types), `Unit/Step.lean` (deterministic `step`, event enumeration, `key`, `obs`), `Unit/Props.lean`, `Unit/Mutants.lean`, `Unit/Proofs.lean` (F3), `PROPERTIES.md`, `MANIFEST.json`.
  Full file layout, anchor normalization, and the FormalKit library contract: `~/.agents/skills/k-formal/references/lean-model.md`.
- **Catalog**: a persistent per-machine store of unit versions, content-addressed by a sha256 over the sorted (relative path, per-file
  sha256) pairs of every unit file, excluding the top-level working dirs `tmp/`, `traces/`, `receipts/`, `.lake/`, every `lake-manifest.json`
  file at any depth, and, within `MANIFEST.json`, the `branch`/`source_commit` fields that `checkout`/`init --from-version` rewrite on every
  checkout.
  A version stays valid for a working tree exactly when every one of its anchors still resolves unchanged in that tree;
  it is reused across branches, worktrees, and squash merges on that basis, never by branch name.
  Layout, staleness, resolution order, anchor identity, audit/snapshot identity, and the `catalog` subcommands:
  `~/.agents/skills/k-formal/references/catalog.md`.
- **Adapter**: the bridge from a unit's exhaustive-search traces to the real code's observed behavior, used by `replay` and `audit`.
  Contract, process-boundary choices, and the `--against` differential mode for refactors:
  `~/.agents/skills/k-formal/references/adapters.md`.
- **Proofs**: F3-only Lean theorems over the same `step`, the audit checks `,formal prove` enforces, and the stop-after-2-repair-rounds rule.
  Pattern and recipes: `~/.agents/skills/k-formal/references/proofs.md`.

## Lifecycle

The SOP owns stage transitions (Scope → Understand → Produce → Verify → Deliver);
this skill supplies the per-stage work, not a second lifecycle.

1. **Scope.**
   Run `,formal doctor` to check `elan`/`lake`/`lean` and the pinned toolchain (`,formal doctor --install` when the toolchain is missing).
   Pick the tier.
   Run `,formal status [--json]` for every known unit's anchor state (`valid`/`stale`/`no-anchors`), `,formal catalog stale --base <merge-base>` and `,formal catalog uncovered --base <merge-base>` to find units whose anchors moved and changed hunks (including untracked files) no unit covers.
   Retain an existing branch work dir for repair.
   With no work dir, use `,formal catalog checkout <unit>` only when a valid version resolves, `,formal init <unit> --from-version <id>` when intentionally repairing from a selected saved version, or `,formal init <unit> [--tier F2|F3] [--design]` for a genuinely new unit.
2. **Understand.**
   Extraction: a research worker returns proposed `TRANSITIONS.md` rows and anchor ranges without writing the catalog;
   the root or an explicitly authorized execution category persists accepted rows and records anchors with `,formal anchors add <unit> <path>:<start>-<end>` (never hand-edit `ANCHORS.json`).
   For diagnosis, that authorized executor may run `,formal explore <unit>`, `,formal traces <unit> --mode failures`, and `,formal replay` as an Understand baseline reproduction, then give the returned diagnostics to research for analysis.
   These are not acceptance evidence; acceptance replay stays inside the root's Verify `audit`.
3. **Produce.**
   Author `Unit/Model.lean`, `Unit/Step.lean`, `Unit/Props.lean`, `Unit/Mutants.lean` (and `Unit/Proofs.lean` for F3), plus the replay adapter.
   Genuine generation required to create those artifacts remains part of Produce.
   Implement workers MUST NOT run `,formal build`, directly smoke-run an adapter, or run `explore`, `mutate`, `replay`, `prove`, or `audit` as a production check.
4. **Verify.**
   The root runs `,formal audit <unit> --json` once per snapshot.
   The default audit orders its build before dependent expensive stages; a custom `--require` selection does not universally add or normalize prerequisites.
   Only when useful, the root first runs a cheap, distinct bootstrap needed by the real adapter consumer, such as starting its harness or preparing its environment.
   This is not an adapter smoke run, conformance evidence, or a duplicate standalone formal build.
   For real-code units, audit replay generates `--mode cover` traces; a manual `,formal traces` run is only needed for `--mode failures` diagnosis.
   Cover generation does not guarantee the original defect schedule appears.
   The root identifies the generated trace that exercises each defect witness or cites existing targeted regression/replay evidence and reports any gap.
   The root also runs a fidelity review lens: every `TRANSITIONS.md` row and enabled event matches its anchors.
   For real-code units, verify the real dispatch path and invoked consumer, each compared field's observed source,
   and every init-rooted defect and preserved-invariant witness event by event in real code.
   For `--design` units, judge intended plan/spec behavior and model witnesses instead;
   production observations and replay remain `n/a-design`.
   Never invent a production consumer or runtime evidence for a design unit.
   For F3 units or high-risk findings, add a refute lens on property adequacy and discriminating mutants.
   Conformance is executable evidence for the exact current snapshot.
   Fidelity is a separate judgment over anchored extraction and witness evidence.
   An edit invalidates each affected judgment and check, but unaffected evidence remains valid.
   For a stateful replacement, the root also runs `,formal replay <unit> --against <base>` and cites its parity result separately.
5. **Deliver.** Report the audit `certifies` string verbatim.
   Save only with a passing audit receipt for the exact current snapshot and inputs: `,formal catalog save <unit>`.

## Certification wording

A model result certifies the model, not the code.
Report conformance (replay) and fidelity (review lens) as separate facts, never folded into one verdict.
A `bounded` search result (state or depth budget hit) is never reported as an unbounded pass; state it as "holds within budget".
An `unverified` conformance stage (no runnable adapter) is never reported as passing replay.
A design model (`--design`) never certifies runtime enforcement; it certifies only that the modeled properties hold against the intended design.
**Threat model:** `,formal prove`'s Lean-side checks (`~/.agents/skills/k-formal/references/proofs.md`) assume an honest but fallible agent, catching accidental unsound or vacuous shortcuts (`sorry`/`admit`/`axiom`, `native_decide`, `unsafe`/`implemented_by`/`extern` changing what actually executes, an unkilled mutant, model drift), never a user deliberately trying to defeat the checker itself (a `macro_rules` takeover, a runtime-built kernel-bypass option, a fake tool binary, a lexer trick); a passing audit certifies the model under honest authorship, never a security boundary against a determined attacker.

## Cost controls

Use the unit template and the tactic recipes in `~/.agents/skills/k-formal/references/proofs.md` instead of deriving Lean idiom from scratch.
Keep build receipts compact: first-N errors, trimmed goals, counts, never a full raw Lean build log in an agent's context.
One unit gets exactly one implement packet, never several units bundled into a single one.
Give a repair round fresh context; do not carry a failed round's transcript into the next one.
Stop after 2 repair rounds on the same unit and report the remaining open properties/mutants honestly rather than continuing to iterate.

## Other uses

- **Review-only mode** (reviewing someone else's PR): make no writes to the target repo. Units still live in the machine-local catalog.
  Run `replay` only when the reviewed code runs locally; otherwise the audit's conformance stage reports `unverified`, never a pass.
- **Refactor / replacement parity**: run `,formal replay <unit> --against <base-ref>` —
  a differential run where the pre-refactor code is the oracle, comparing observed outputs at `<base-ref>` and at the current head on the same traces, ignoring the model's own expectations.
- **Diagnosis**: an authorized executor runs `,formal explore <unit>` for the shortest trace to a bad state, writes failure traces with `,formal traces <unit> --mode failures`, and runs `,formal replay` as a baseline reproduction; research analyzes the returned diagnostics.
  This is not a Verify audit stage. When the task owns the repo, an admissible trace becomes a regression test.
- **Claims**: turn a plan's, PR's, or review's "never/always/cannot" claim into a named property with status `holds`, `refuted`, or `unmodeled`, instead of trusting the prose.
- **Converge**: model mutants join the mutation-probe set; the SOP's control/mutation/restoration rule still applies, and model mutants never touch the target repo.
  Count a model mutant as caught only when `,formal mutate` reports a conclusive kill by its own declared `killedBy` property.
  A bounded search with no required `.refuted` counterexample is inconclusive, never a kill;
  `wrong-killer`, `survived`, and inconclusive outcomes are findings.

## Never

Never write a unit's model, adapter, or Lean sources into the target repo; a unit lives only in the catalog.
Only a regression test derived from an admissible trace goes into the repo, and only when the task owns that repo.
Never trust a worker's status report as a passing verdict; only `,formal audit <unit> --json`, run by the root in Verify, certifies a snapshot.
Never treat a `holds`-within-`bounded` result as an unbounded proof, and never skip the fidelity review lens because the audit passed.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Launch one research packet to extract and return proposed transition rows and anchor ranges for each new or stale unit named by `,formal catalog uncovered --base <merge-base>` (or `catalog stale` for an existing unit); the root persists the accepted extraction and anchors.
The root MUST NOT substitute its own inline extraction for that packet absent an explicit user no-delegation instruction;
if the lane is unavailable report blocked.
Launch one implement packet per unit for model, property, mutant, and adapter authoring, pointed at `~/.agents/skills/k-formal/references/lean-model.md` plus `~/.agents/skills/k-formal/references/adapters.md` (and `~/.agents/skills/k-formal/references/proofs.md` for F3); the root MUST NOT substitute its own inline authoring for that packet absent an explicit user no-delegation instruction; if the lane is unavailable report blocked.
The root runs catalog-writing diagnosis commands during Understand and `,formal audit <unit> --json` itself in Verify, including `,formal replay <unit> --against <base>` for a stateful replacement.
Research receives and analyzes diagnostic outputs but MUST NOT run `anchors add`, `traces`, `replay`, `catalog save`, or another command that writes catalog state or executes the real-code adapter.
A worker packet MUST NOT run `build` or `audit`, directly smoke-run an adapter, treat `mutate`/`explore` as a self-verification pass, or run `catalog save`.
Assign a review lens for fidelity and, on F3 units or high-risk findings, a refute lens for property adequacy;
keep them as distinct questions over the same audit evidence, never a chain of one certifying the other.
Dispatch ready stage-sized packets, not an agent per command or test. Honor an explicit no-delegation request inline.

## Output

Report the tier, the unit(s) touched, the audit `certifies` string, review/refute findings with evidence, and any open properties/mutants left after the repair-round cap.
