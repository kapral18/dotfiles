# Lean model authoring

Owner: `~/.agents/skills/k-formal/SKILL.md`. Load this reference when authoring or extending `Unit/Model.lean`,
`Unit/Step.lean`, `Unit/Props.lean`, or `Unit/Mutants.lean` for an F2 or F3 unit.

## What `,formal init` generates

`,formal init <unit> [--tier F2|F3] [--design]` materializes the template into the unit's work dir:

- `lean-toolchain` pinned to the exact Lean version (`leanprover/lean4:v4.34.1`).
- `lakefile.toml` with the `[[require]] name = "FormalKit" path = "<state-root>/_kit/<kit-hash>"` require.
- A fixed `Main.lean` (see below) — never edited per unit.
- `MANIFEST.json` with `tier`/`design` set from the `init` flags; see MANIFEST.json fields below.
- `PROPERTIES.md`/`TRANSITIONS.md` skeleton tables (headers only, no rows yet).
- `Unit/{Model,Step,Props,Mutants,Proofs}.lean` stubs: a minimal two-state `St`/`Ev` example, a `step` that toggles between the two states (structured as a no-op guard away from the real dispatch/enabledness shape — see `Step.lean`'s docstring; it is not itself a no-op), an empty `mutants` list, and an empty `Unit.Proofs` namespace.

`Main.lean` is fixed and requires `FormalKit` plus every `Unit.*` module it assembles from.
Every unit must define these literal names in namespace `Unit` (`Unit` is the fixed module/namespace name for every unit, not a placeholder): `Unit.St`, `Unit.Ev`, `Unit.inits`, `Unit.events`, `Unit.step`, `Unit.key`, `Unit.obs`, `Unit.evJson`, `Unit.props`, `Unit.mutants`.
Only `Unit/Props.lean` and `Unit/Mutants.lean` import `FormalKit` directly; `Unit/Model.lean` and `Unit/Proofs.lean` have no imports, and `Unit/Step.lean` imports `Lean.Data.Json` and `Unit.Model` instead.
Generated JSON and TOML values are encoded for their own file formats; branch names and state paths containing quotes or backslashes
must remain data rather than breaking either file.

## Setup

- Toolchain: `elan` manages Lean; pin `lean-toolchain` to the exact version, e.g. `leanprover/lean4:v4.34.1`.
  `,formal doctor` checks it; `,formal doctor --install` installs it.
- Core Lean only, no Mathlib. `simp`, `decide`, `omega`, `split`, and structural induction cover a finite
  control-state model without a multi-gigabyte dependency cache.
- The kit (`FormalKit`) is required by path from `<state-root>/_kit/<kit-hash>/`, never from the deployed
  `~/lib/,formal/` tree directly — a unit's `lake build` must never write under `~/lib`.

## FormalKit API (`FormalKit.Types`)

- `structure Prop' (St Ev : Type) where name : String; expect : Expect; check : (St → Ev → St) → St → Bool` — `check` receives whichever
  step function is currently under test (the model's own `step`, or a mutant's) plus the state, so one property statement automatically
  re-exercises every mutant with no duplicated statement.
- `inductive Expect where | holds | refuted` — `holds` is an ordinary invariant; `refuted` is a seeded, documented false claim kept in the
  property list so `explore`/`audit` still report on it explicitly instead of silently dropping a known-false statement.
- `structure Spec (St Ev : Type) where inits : List St; events : List Ev; step : St → Ev → St; key : St → UInt64; obs : St → Lean.Json;
evJson : Ev → Lean.Json; props : List (Prop' St Ev)`. A trace's `init` field is a positional index into `inits`, never a value — `inits`
  is the enumeration, `init` is one index into it. Equal keys MUST preserve property truth and successor keys for the model and every mutant.
  Include property-relevant history summaries in `key`; `obs` is the observable surface `replay` compares against.
- `structure Mutant (St Ev : Type) where name : String; step : St → Ev → St; killedBy : List String` — `killedBy` names the properties
  _expected_ to catch this mutant; `,formal mutate`/`audit` cross-check that declared list against the properties whose outcome actually
  mismatches (the JSON output's `killed_by`), never enforce it structurally: a mismatch against a name outside `killedBy` is a `wrong-killer`
  finding, not a pass.
- **Registration**: `Main.lean` assembles `spec : FormalKit.Spec Unit.St Unit.Ev` from `Unit.inits`/`Unit.events`/`Unit.step`/`Unit.key`/`Unit.obs`/
  `Unit.evJson` plus `Unit.props` (all in namespace `Unit`, defined across `Unit/Step.lean` and `Unit/Props.lean`), then calls `FormalKit.main spec Unit.mutants args`.
  `explore`/`mutate` never discover properties or
  mutants by scanning source — a property or mutant left out of `spec.props`/`Unit.mutants` runs nowhere.
- **Result names and budgets**: a property's `status` is `holds` or `violated`; each search also reports whether a state/depth budget
  genuinely truncated closure. `holds` under a bounded search means "held within budget", never a full-closure guarantee. Mutation JSON
  retains its existing keys and adds bounded/inconclusive evidence. Without a required `.refuted` counterexample, a bounded run is
  inconclusive rather than a kill, and the control's `ok` remains false.

## Explore semantics

`,formal explore` evaluates every property's `check` on every state the BFS reaches from `inits` over the full `events` enumeration.
Any reachable state where `check` returns `false` marks that property `violated`. A property declared `expect := .holds` reports `holds`
only when no reachable state violates it; `violated` on a `.holds` property is a failure. A property declared `expect := .refuted` (a
seeded, documented false claim) is expected to hit exactly this: `violated` there reads as "refuted as expected", and a `.refuted`
property that reports `holds` instead (never actually falsified) is the failure.

## Unit template walkthrough

`,formal init <unit> [--tier F2|F3] [--design]` creates the work dir. Fill it in this order:

For `--design` units, the anchors and witnesses below describe intended plan/spec behavior rather than real code.
Mark production consumers, observations, and replay `n/a-design`; never invent runtime evidence.
Real-code units retain every production observation and replay requirement below.

1. **`TRANSITIONS.md`** — the extraction table, one row per transition:
   state variable and modeled field | event and modeled function/key | guard/enabledness | effect | anchor ids (`A1`, `A2`, …).
   Every row cites the controllable real event and dispatch/enabledness anchors recorded with
   `,formal anchors add <unit> <path>:<start>-<end>`. Write this before any Lean file; a model with no extraction
   row behind it is a guess, not an anchor.
2. **Abstractions and unmodeled list** — name every reduction explicitly in `MANIFEST.json`'s `abstractions`
   (e.g. tree contents reduced to `{real, stub, none}`, a filesystem call reduced to an outcome boolean) and
   list every path deliberately left out of the model in `unmodeled`. Treat each abstraction as a place a bug
   can hide: an abstraction that collapses two code paths that actually diverge hides the divergence.
3. **`Unit/Model.lean`** — state and event types, `deriving Repr, BEq, DecidableEq` where useful
   (the explorer dedups on `key : St → UInt64` in a `Std.HashSet UInt64`, so `St` itself needs no
   `BEq`/`Hashable` instance for that; `BEq` is only for a property's own `==` comparisons, and `DecidableEq` is for proofs).
4. **`Unit/Step.lean`** — the deterministic `step : St → Ev → St`, mirroring the real code case by case, with
   anchor comments on the event source, dispatch/enabledness, and effect for every case. `inits : List St`,
   `events : List Ev` (the full finite enumeration, including argument values), `key : St → UInt64`, `obs : St → Lean.Json`, `evJson`.
5. **`Unit/Props.lean`** — properties, each taking the step function as a parameter (`(step : St → Ev → St)`)
   so mutants in `Unit/Mutants.lean` reuse the same property definitions instead of a second copy. Map every
   original defect and preserved invariant to an init-rooted event schedule and its targeted replay/regression evidence.
6. **`Unit/Mutants.lean`** — alternative `step` functions with a `killedBy` list naming the properties expected
   to kill each one. Write mutants together with the properties. Each mutant must discriminate the named defect
   or preserved invariant rather than merely perturb unrelated state.

## MANIFEST.json fields

| field           | meaning                                                                                                                                                                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `unit`          | the unit name                                                                                                                                                                                                                                                       |
| `tier`          | `"F2"` or `"F3"`, set by `,formal init --tier`                                                                                                                                                                                                                      |
| `design`        | `true` for a `--design` unit, set by `,formal init --design`                                                                                                                                                                                                        |
| `repo_id`       | first 16 hex of sha256 of the git common dir                                                                                                                                                                                                                        |
| `branch`        | the current branch (or `detached-<shortsha>`)                                                                                                                                                                                                                       |
| `source_commit` | `git rev-parse HEAD` at unit creation or checkout time                                                                                                                                                                                                              |
| `toolchain`     | the pinned Lean toolchain, e.g. `leanprover/lean4:v4.34.1`                                                                                                                                                                                                          |
| `kit_hash`      | this unit's `FormalKit` copy's content hash, under `<state-root>/_kit/<kit_hash>`                                                                                                                                                                                   |
| `adapter`       | `null`, or `{"cmd": str, "cwd": "repo"\|"unit"}` for the replay adapter                                                                                                                                                                                             |
| `replay`        | `{"differential": bool}` (default `false`) — must be `true` before `replay --against REF` runs; see `references/adapters.md`                                                                                                                                        |
| `budgets`       | `{"max_states": int, "max_depth": int\|null, "max_traces": int}` — search, mutate, and replay-cover budgets (`max_traces` default 500); `,formal explore`/`mutate`/`traces` fall back to these when `--max-states`/`--max-depth` are not passed on the command line |
| `abstractions`  | every modeling reduction named explicitly (see Modeling method below)                                                                                                                                                                                               |
| `unmodeled`     | every path deliberately left out of the model                                                                                                                                                                                                                       |

## PROPERTIES.md columns

`id | statement | source | expect | killing mutants | status`. `id` matches the property's name in
`Unit/Props.lean`; `source` names the anchored requirement, claim, or finding and its init-rooted defect or
preserved-invariant witness. For real-code units, also name the invoked consumer, production source, actual
fields observed and targeted replay/regression evidence. For `--design`, cite intended plan/spec behavior and
model witness evidence; production observations and replay are `n/a-design`.
`expect` is `holds` or `refuted`; `killing mutants` lists the
discriminating `Unit/Mutants.lean` entries whose `killedBy` names this property; `status` tracks the last
`,formal audit`/`explore` outcome (`holds`, `violated`, `bounded`) and is updated after each run, never computed
by hand. If generated cover traces omit a mapped defect schedule, record the real targeted evidence or the
coverage gap; Markdown mapping alone does not prove execution.

## Modeling method

- Put nondeterminism in event arguments (scan results, outcome flags, timing, identity), never inside `step`.
  `step` stays a pure function of the current state and one concrete event.
- Model the dispatch/enabledness layer from the start: which events are legal in which state/view/modal mode.
  Without it, preconditions become unstated hypotheses and a counterexample trace can be one the real code
  cannot actually produce (an event the real dispatcher would reject).
- `key : St → UInt64` defines search equivalence. Equal keys must preserve every property's truth and equivalent successor behavior
  for the model step and every mutant. Preserve finite property-relevant ghost history in `key`; never omit it merely to collapse states.
- Add ghost state only for history properties. If no sound finite identity exists, bound the search honestly rather than silently
  merging states. Do not invent synthetic phases or state solely to inflate or force coverage.
- `obs : St → Lean.Json` is the observable surface the real code can actually expose. `replay` compares each
  trace step's expected `obs` fields against fields observed from the invoked real consumer. Record the source
  and actual compared fields. Shadow state, copied expectations, and unconditional flags are not production observations.
- Reachability/search starts from every real entry state in `inits` and closes under `step` over the full
  event enumeration. Do not add synthetic initial states or phases solely to force a witness into generated cover traces.
- The explorer retains shared parent/reverse-path information and materializes a forward trace only when emitting it; a small trace
  output limit must not require storing a separate full trace for every discovered state.

## Property rules

- Every property names the mutant expected to kill it (`killedBy` in the mutant, cross-checked by
  `,formal mutate`/`audit`). A property no mutation breaks is measuring nothing — write the property and its
  killing mutant together, and if no historical bug or plausible mistake breaks it, drop or strengthen it.
  `,formal mutate`/`audit` enforce the minimum shape of this: zero mutants, or any mutant with an empty
  `killedBy`, fails the stage outright (a vacuous "every mutant killed", or an undocumented intent, is never a
  pass) — this holds even for a mutant you expect to survive; name the property that _should_ catch it, even
  though it currently does not, so the gap the mutant demonstrates stays legible. `,formal explore`/`audit`
  equally fail a unit with zero properties.
- Turn every historical bug from the real code's history into a mutant. A regression that already happened
  once is exactly the shape of mistake the property set exists to catch again.
- Counterexample traces start at `init` and only at `init`; never hand-build a starting state. Before trusting
  a `violated` trace, walk each event of it against the real code with anchors, confirming the dispatch layer
  would actually accept that event in that state (see the enabledness rule above).
- A property can be true only because of how the model logs or derives a value, not because the real code
  guarantees it. Check this by writing a mutant that changes the field the property inspects; if the property
  still reports `holds`, the property or the log is vacuous.
- Bundle related invariants when one needs another to stay inductive (e.g. "field X implies session A or B"
  together with "outcome Y implies session C"); an unbundled invariant can fail induction even when the
  combined fact is true at every reachable state.

## Common Lean errors and fixes

| Symptom                                                                     | Cause                                                                        | Fix                                                                                                                                         |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `unknown identifier` on a qualified theorem name                            | Missing `namespace`/`import`, or a root module absent                        | Use fully qualified names; when there is no root module, import the leaf module directly (e.g. `Unit.Proofs`, not `Unit`).                  |
| `sorryAx` in `formalcheck`'s axiom-check output                             | An unfinished proof, even one that "compiles"                                | Treat as unproved; `,formal prove` fails the forbidden-token scan on `sorry`/`admit` before this even runs.                                 |
| A mutant survives every property                                            | The property is too weak, or the mutant changes a field no property inspects | Write the mutant and the property that should catch it together (see Property rules); strengthen the property to inspect the changed field. |
| A trace fires an event the real dispatcher rejects                          | Enabledness/dispatch not modeled                                             | Add the dispatch layer (state/view/mode → legal events) to `Step.lean` before trusting any `explore`/`mutate` trace.                        |
| Two invariants each fail induction alone but the combined fact holds        | Under-bundled invariant                                                      | Merge them into one `Inv` and prove one step lemma, per Property rules bundling.                                                            |
| Duplicate `step` behavior verified by a helper lemma, not the named theorem | A second copy of the step spec (e.g. `stepFoo_eq`)                           | Prove the named property theorem directly from `step`; keep exactly one step spec (see `references/proofs.md`).                             |
