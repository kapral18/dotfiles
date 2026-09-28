# toy fixture

A complete, synthetic `,formal` unit (tier F2, not tied to any real repo or code) used by
`scripts/tests/test_formal_e2e.py`'s end-to-end section. `lakefile.toml` uses the same `@@KIT_PATH@@`
placeholder as `home/exact_lib/exact_,formal/templates/unit/lakefile.toml`; the test substitutes
it before building.

Machine: `phase ∈ {idle, running, done}` plus one flag `recorded : Bool`. Events: `start`,
`finish(ok)`, `cancel`, `reset`. See `TRANSITIONS.md` for the guard/effect table and
`PROPERTIES.md` for the property table -- both below document the exact expected tool output for
each.

`recorded` is the machine's finite summary of property-relevant history. Event dispatch branches
only on `phase`, but properties inspect `recorded` and transitions preserve or update it, so
`Unit.key` deliberately includes both fields. Omitting `recorded` would merge states with
different property truth and could hide the reachable `P2` counterexample.

## Expected `explore` outcome

- `P1` (`done implies recorded`): `holds`.
- `P2` (`idle implies not recorded`, seeded false): `violated`. Shortest counterexample trace is
  exactly `init: 0, events: [{"name":"start","args":{}}, {"name":"cancel","args":{}}]` -- see
  "P2's exact shortest trace" below for why.
- `P3` (`reset from done always lands on idle`, deliberately weak): `holds`.

## Expected `mutate` outcome

- `control`: `ok = true` (every property's actual outcome matches its declared `expect`).
- `M_killed` (forgets to set `recorded` on a successful `finish`): `killed_by = ["P1 done implies
recorded"]`, `status = "killed"`.
- `M_weak` (forgets to clear `recorded` on `reset`): `killed_by = []`, `status = "survived"` --
  `P3` only checks the resulting `phase` (still correct), never `recorded`, and `P1`/`P2` never
  observe a state reachable only through this bug.
- The control and both mutants report `bounded = false` and `inconclusive = []`. A bounded run
  lists still-holding properties as inconclusive; those outcomes are never mutant kills, while a
  witnessed violation of a `.holds` property remains conclusive.

## Expected `replay` outcome

- `--adapter adapter_ok.py`: passes on every trace (a faithful reimplementation).
- `--adapter adapter_diverge.py`: fails on any trace whose `steps` include a `cancel` event,
  naming that trace's `trace_id` -- the adapter's `cancel` never sets `recorded`, unlike the
  model (`Unit/Step.lean`'s `step`).

## Expected `prove` outcome

- `Unit/Proofs.lean` replaced by `Proofs_sorry.lean`: exit 1, output mentions `sorry`.
- `Unit/Proofs.lean` replaced by `Proofs_ok.lean`: exit 0 (one theorem, no `sorry`/`axiom`/
  `native_decide`, `collectAxioms` reports no disallowed axioms).

## P2's exact shortest trace

`P2` ("idle implies not recorded") is seeded false on purpose. The _only_ way to reach `idle`
with `recorded = true` in this machine is through `cancel`'s effect (`phase := idle, recorded :=
true`, see `Unit/Step.lean`) -- `reset` always lands on `idle` with `recorded` freshly cleared to
`false`, and no other event touches `recorded` while leaving `phase = idle`. The shortest path:

1. `start` -- `{"phase":"idle","recorded":false}` → `{"phase":"running","recorded":false}`
2. `cancel` -- `{"phase":"running","recorded":false}` → `{"phase":"idle","recorded":true}`

No trace shorter than two events reaches `idle` with `recorded = true` (the only `init` is
`{"phase":"idle","recorded":false}` itself, which does not violate `P2`), so `explore`'s `P2`
entry reports exactly:

```json
{
  "init": 0,
  "events": [
    { "name": "start", "args": {} },
    { "name": "cancel", "args": {} }
  ]
}
```
