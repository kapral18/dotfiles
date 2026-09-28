import FormalKit.Types
import FormalKit.Explore
import FormalKit.Cli

/-!
`FormalKit`: the generic, unit-independent BFS explorer/mutation-tester/trace-generator every
`,formal` unit compiles against. See `FormalKit.Types` for `Spec`/`Prop'`/`Mutant`,
`FormalKit.Explore` for the BFS pass, and `FormalKit.Cli` for `FormalKit.main` (a unit's whole
`Main.lean` builds a local `spec : FormalKit.Spec Unit.St Unit.Ev` record from `Unit`'s own
definitions, then calls `def main (args : List String) : IO UInt32 := FormalKit.main spec
Unit.mutants args`).

`FormalKit.Check` (compiled separately into the kit's own `formalcheck` executable, see
`FormalCheck.lean`'s exe root and `lakefile.toml`) is the F3 semantic prove checker `,formal
prove` runs by absolute path against a unit's already-built modules; it is not imported here
since it is never part of a unit's own `Unit`/`Main` build graph.
-/
