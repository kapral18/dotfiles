import FormalKit
import Unit.Step

/-!
Properties over the toy machine. See `PROPERTIES.md` for the id/source/expect table this
mirrors row for row, and `README.md` for the exact expected `explore` outcome of each.
-/

namespace Unit

open FormalKit

private def imp (a b : Bool) : Bool := !a || b

/-- Properties take the step function as a parameter (never `Unit.step` directly), so
`Mutants.lean`'s mutants automatically re-exercise these exact same statements with no
duplication. -/
def props : List (Prop' St Ev) := [
  { name := "P1 done implies recorded"
    expect := .holds
    check := fun _ st => imp (st.phase == .done) st.recorded },
  { name := "P2 idle implies not recorded"
    -- Seeded false on purpose -- `cancel`'s effect (`Step.step`) makes this refutable in exactly
    -- `[start, cancel]`; see `README.md` for the documented shortest counterexample.
    expect := .refuted
    check := fun _ st => imp (st.phase == .idle) (!st.recorded) },
  { name := "P3 reset from done always lands on idle"
    -- Deliberately weak: it only checks the resulting `phase`, never `recorded`, so it cannot
    -- see `M_weak`'s bug (`Mutants.lean`) even though that bug is real.
    expect := .holds
    check := fun f st => imp (st.phase == .done) ((f st .reset).phase == .idle) }
]

end Unit
