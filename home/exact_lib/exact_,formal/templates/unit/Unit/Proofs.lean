/-!
F3-tier proofs (Lean theorems over `Reachable`/`step`, no `sorry`/`axiom`/`native_decide`). Ships
empty for F2 -- `,formal build --proofs` still succeeds against an empty namespace, but
`,formal prove` (and an F3 unit's `audit` `prove` stage) fails until at least one theorem is
added: F3 exists specifically to add proofs, so zero theorems is a failure, never a vacuous pass.
Fill this in only once the unit is promoted to F3 (behavior-relevant state is unbounded, `explore`
reports `bounded`, or the user asks). `,formal prove`'s `formalcheck` executable (see
`lean/FormalKit/FormalKit/Check.lean`) loads this module's own compiled output at runtime and
axiom-checks every theorem defined in this file (public or `private`) directly, so `private`
theorems are checked the same as public ones.
-/

namespace Unit

end Unit
