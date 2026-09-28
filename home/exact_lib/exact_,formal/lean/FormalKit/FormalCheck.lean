import FormalKit.Check

/-!
`formalcheck`'s exe root: `def main` is Lake's required entry point for the `[[lean_exe]] name =
"formalcheck"` target in `lakefile.toml`. All real logic lives in `FormalKit.Check` (kept
separate from this root so `FormalKit.Check`'s own definitions stay importable/testable on their
own, mirroring `FormalKit.lean`/`FormalKit.Cli`'s split for the `unit` executable).
-/

def main (args : List String) : IO UInt32 := FormalKit.Check.main args
