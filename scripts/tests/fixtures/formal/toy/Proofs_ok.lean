import Unit.Step

/-!
`prove`-audit positive fixture: swapped in for `Unit/Proofs.lean` to exercise `,formal prove`'s
success path. One real, complete theorem -- no `sorry`, `axiom`, or `native_decide`.
-/

namespace Unit

/-- `reset` from `done` always lands on `idle` with `recorded = false` (matches `P3`/`Step.step`,
proved directly by computation rather than restated as an invariant). -/
theorem reset_from_done (phase : Phase) (recorded : Bool) (h : phase = .done) :
    (step { phase := phase, recorded := recorded } .reset).phase = .idle ∧
      (step { phase := phase, recorded := recorded } .reset).recorded = false := by
  subst h
  cases recorded <;> decide

end Unit
