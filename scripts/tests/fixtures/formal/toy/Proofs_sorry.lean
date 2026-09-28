import Unit.Step

/-!
`prove`-audit negative fixture: swapped in for `Unit/Proofs.lean` to exercise `,formal prove`'s
forbidden-token scan. Same statement as `Proofs_ok.lean`, left unfinished with `sorry` on purpose.
-/

namespace Unit

theorem reset_from_done (phase : Phase) (recorded : Bool) (h : phase = .done) :
    (step { phase := phase, recorded := recorded } .reset).phase = .idle ∧
      (step { phase := phase, recorded := recorded } .reset).recorded = false := by
  sorry

end Unit
