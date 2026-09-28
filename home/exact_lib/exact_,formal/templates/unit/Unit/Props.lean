import FormalKit
import Unit.Step

/-!
Properties over this unit's state/events. Every property row in `PROPERTIES.md` corresponds to
one entry here.
-/

namespace Unit

open FormalKit

/-- Properties take the step function as a *parameter* (never `Unit.step` directly), so every
mutant in `Mutants.lean` automatically re-exercises this exact same property with no duplicated
statement -- `check` is handed whichever step is currently under test. Replace this example with
the real properties; give each one a `PROPERTIES.md` row citing its source. -/
def props : List (Prop' St Ev) := [
  { name := "P1 toggle is an involution"
    expect := .holds
    check := fun f st => f (f st .toggle) .toggle == st }
]

end Unit
