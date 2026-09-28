import FormalKit
import Unit.Step

/-!
Two seeded mutants: one every property should catch (`M_killed`), one deliberately too subtle
for this unit's property list (`M_weak`) -- see `README.md`/`PROPERTIES.md` for the expected
`mutate` outcome of each.
-/

namespace Unit

open FormalKit

/-- `M_killed`: `finish true` forgets to set `recorded`. Breaks `P1` ("done implies recorded")
immediately, at `[start, finish true]`. -/
def mKilledStep (st : St) : Ev → St
  | .finish ok =>
      if st.phase == .running then
        if ok then { st with phase := .done } else { st with phase := .idle }
      else st
  | e => step st e

/-- `M_weak`: `reset` forgets to clear `recorded`. A real bug, but `P3` -- its declared intended
killer -- only checks that `reset` still lands on `idle` (it still does); `P1`/`P2` never observe
a state reachable only through this bug either, so nothing in this unit's property list actually
catches it (the intended killer is too weak, which is exactly the finding this mutant
demonstrates: `,formal mutate` reports it `survived`). -/
def mWeakStep (st : St) : Ev → St
  | .reset => if st.phase == .done then { st with phase := .idle } else st
  | e => step st e

def mutants : List (Mutant St Ev) := [
  { name := "M_killed", step := mKilledStep, killedBy := ["P1 done implies recorded"] },
  { name := "M_weak", step := mWeakStep, killedBy := ["P3 reset from done always lands on idle"] }
]

end Unit
