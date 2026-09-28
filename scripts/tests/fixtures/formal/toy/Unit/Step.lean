import Lean.Data.Json
import Unit.Model

/-!
The toy machine's transition function. See `TRANSITIONS.md` for the row-per-case extraction
table and `README.md` for the exact expected `explore`/`mutate`/`replay`/`prove` outcomes.
-/

namespace Unit

/-- Dispatch/enabledness is modeled directly in `step`: every case first checks whether its event
is even reachable in the current `phase` (`start` only from `idle`, `finish`/`cancel` only from
`running`, `reset` only from `done`) and is a no-op otherwise -- a guard FormalKit never sees is a
guard the explorer cannot falsify. -/
def step (st : St) : Ev → St
  | .start =>
      if st.phase == .idle then { st with phase := .running } else st
  | .finish ok =>
      if st.phase == .running then
        if ok then { st with phase := .done, recorded := true }
        else { st with phase := .idle }
      else st
  | .cancel =>
      -- This fixture's own (deliberately chosen) semantics: cancelling a run still marks
      -- `recorded`, unlike a clean rollback -- this is exactly what makes `P2` (`idle` implies
      -- `not recorded`) false, and false specifically by way of `[start, cancel]` (see
      -- `README.md`).
      if st.phase == .running then { st with phase := .idle, recorded := true } else st
  | .reset =>
      if st.phase == .done then { st with phase := .idle, recorded := false } else st

def inits : List St := [{ phase := .idle, recorded := false }]

/-- The full, finite enumeration of events, including both `finish` outcomes. -/
def events : List Ev := [.start, .finish true, .finish false, .cancel, .reset]

private def phaseNum : Phase → UInt64
  | .idle => 0
  | .running => 1
  | .done => 2

/-- BFS state identity. `recorded` is a finite property-relevant history summary: dispatch does
not branch on it, but properties inspect it and successors preserve or update it. Equal keys must
therefore retain both fields to preserve property truth and successor behavior. -/
def key (st : St) : UInt64 := phaseNum st.phase * 2 + (if st.recorded then 1 else 0)

private def phaseStr : Phase → String
  | .idle => "idle"
  | .running => "running"
  | .done => "done"

/-- Observables a real reimplementation can expose -- `replay`'s adapters compare against
exactly this shape (see `adapter_ok.py`). -/
def obs (st : St) : Lean.Json :=
  Lean.Json.mkObj [("phase", Lean.Json.str (phaseStr st.phase)), ("recorded", Lean.Json.bool st.recorded)]

def evJson : Ev → Lean.Json
  | .start => Lean.Json.mkObj [("name", Lean.Json.str "start"), ("args", Lean.Json.mkObj [])]
  | .finish ok =>
      Lean.Json.mkObj [("name", Lean.Json.str "finish"), ("args", Lean.Json.mkObj [("ok", Lean.Json.bool ok)])]
  | .cancel => Lean.Json.mkObj [("name", Lean.Json.str "cancel"), ("args", Lean.Json.mkObj [])]
  | .reset => Lean.Json.mkObj [("name", Lean.Json.str "reset"), ("args", Lean.Json.mkObj [])]

end Unit
