import FormalKit
import Unit.Step

/-!
Mutants: alternative `step` functions reintroducing a specific historical or hypothesized bug,
explored and checked against every property in `Props.lean` exactly like the real model's
`step`. `,formal mutate`/`audit` fail on an empty list (a vacuous "every mutant killed" proves
no property adequate) and on any mutant with an empty `killedBy` (undocumented intent) -- add at
least one mutant, each naming the property expected to catch it, before `,formal audit` can pass.
-/

namespace Unit

open FormalKit

/-- Add one entry per seeded bug, each with a `killedBy` list of the property names *expected*
to catch it -- required non-empty even for a mutant you expect to survive (that survival is
itself the finding: the named property is too weak). Cross-checked, not enforced structurally,
by `,formal mutate`/`audit` (see `wrong-killer`). -/
def mutants : List (Mutant St Ev) := []

end Unit
