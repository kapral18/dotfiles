import FormalKit.Explore
import Lean.Data.Json

/-!
The compiled `unit` executable's CLI: `explore`, `mutate`, `traces`. Every unit's `Main.lean`
defines `spec : FormalKit.Spec Unit.St Unit.Ev` from `Unit.inits`/`Unit.events`/`Unit.step`/
`Unit.key`/`Unit.obs`/`Unit.evJson`/`Unit.props`, then
`def main (args : List String) : IO UInt32 := FormalKit.main spec Unit.mutants args`
(`Unit.mutants := []` for a unit with none yet). All output is one JSON document on stdout for
`explore`/`mutate`; `traces` writes one JSON object per line (JSONL). Exit code is `0` unless the
executable itself failed (bad subcommand/flag); pass/fail against expectations is a `,formal`
(Python CLI) concern, read from this JSON, not this executable's exit code.
-/

namespace FormalKit

open Lean (Json)

variable {St Ev : Type}

def defaultMaxStates : Nat := 200000
def defaultTracesMax : Nat := 500

/-- Whether an observed outcome conclusively mismatches a property's declaration. A witnessed
violation of `.holds` is conclusive even when another frontier was budget-truncated. An absent
counterexample for `.refuted` is a mismatch only after complete closure. -/
def conclusiveMismatch (bounded : Bool) (p : Prop' St Ev) (o : PropOutcome St Ev) : Bool :=
  match p.expect with
  | .holds => !o.holds
  | .refuted => o.holds && !bounded

/-- Property names whose observed outcomes conclusively mismatch their declared expectations. -/
def mismatchNames (bounded : Bool) (propOut : List (Prop' St Ev × PropOutcome St Ev)) : List String :=
  propOut.filterMap fun (p, o) => if conclusiveMismatch bounded p o then some p.name else none

/-- Properties that still hold when closure was budget-truncated. Their expected truth or expected
counterexample is unproven, so they are inconclusive. A witnessed violation is excluded and may
still be a conclusive `.holds` mutant kill. -/
def inconclusiveNames (bounded : Bool) (propOut : List (Prop' St Ev × PropOutcome St Ev)) :
    List String :=
  if !bounded then [] else
    propOut.filterMap fun (p, o) => if o.holds then some p.name else none

def jsonStrArr (xs : List String) : Json := Json.arr (xs.map Json.str).toArray

/-- `explore`'s per-prop counterexample shape: `{"init":i,"events":[evJson...]}` -- just enough
to identify the trace, no walked observables (that is `traces`'s job, see `tracesLineJson`). -/
def exploreTraceJson (evJson : Ev → Json) (initIdx : Nat) (events : List Ev) : Json :=
  Json.mkObj [
    ("init", Json.num initIdx),
    ("events", Json.arr (events.map evJson).toArray)
  ]

def propEntryJson (evJson : Ev → Json) (p : Prop' St Ev) (o : PropOutcome St Ev) : Json :=
  Json.mkObj [
    ("name", Json.str p.name),
    ("expect", Json.str p.expect.toJsonString),
    ("status", Json.str (if o.holds then "holds" else "violated")),
    ("trace", match o.trace with
      | some (i, _st0, evs) => exploreTraceJson evJson i evs
      | none => Json.null)
  ]

/-- `traces`'s JSONL record shape: `{"trace_id","init","init_obs","steps":[{"event","expect"}]}`
-- `steps[i].expect` is the state's `obs` immediately after applying `steps[i].event`, walked
chronologically from `st0` via `step`. `,formal replay` (§5) compares an adapter's observed
output against exactly this `expect` field, step by step. -/
def tracesLineJson (evJson : Ev → Json) (obs : St → Json) (step : St → Ev → St)
    (traceId : String) (initIdx : Nat) (st0 : St) (events : List Ev) : Json :=
  let steps := (events.foldl (fun (acc : List Json × St) e =>
      let st' := step acc.2 e
      (acc.1 ++ [Json.mkObj [("event", evJson e), ("expect", obs st')]], st')
    ) ([], st0)).1
  Json.mkObj [
    ("trace_id", Json.str traceId),
    ("init", Json.num initIdx),
    ("init_obs", obs st0),
    ("steps", Json.arr steps.toArray)
  ]

def runExplore (spec : Spec St Ev) (maxStates : Nat) (maxDepth : Option Nat) : Json :=
  let r := bfs spec.inits spec.events spec.key spec.step spec.props maxStates maxDepth
  Json.mkObj [
    ("kind", Json.str "explore"),
    ("states", Json.num r.statesCount),
    ("transitions", Json.num r.transitions),
    ("depth", Json.num r.depth),
    ("bounded", Json.bool r.bounded),
    ("props", Json.arr (r.propOut.map fun (p, o) => propEntryJson spec.evJson p o).toArray)
  ]

def runMutate (spec : Spec St Ev) (mutants : List (Mutant St Ev)) (maxStates : Nat)
    (maxDepth : Option Nat) : Json :=
  let ctrl := bfs spec.inits spec.events spec.key spec.step spec.props maxStates maxDepth
  let ctrlViolations := mismatchNames ctrl.bounded ctrl.propOut
  let ctrlInconclusive := inconclusiveNames ctrl.bounded ctrl.propOut
  let mutantsJson := mutants.map fun m =>
    let r := bfs spec.inits spec.events spec.key m.step spec.props maxStates maxDepth
    let killedBy := mismatchNames r.bounded r.propOut
    let inconclusive := inconclusiveNames r.bounded r.propOut
    Json.mkObj [
      ("name", Json.str m.name),
      ("bounded", Json.bool r.bounded),
      ("inconclusive", jsonStrArr inconclusive),
      ("killed_by", jsonStrArr killedBy),
      ("expected", jsonStrArr m.killedBy),
      ("status", Json.str (if killedBy.isEmpty then "survived" else "killed"))
    ]
  Json.mkObj [
    ("kind", Json.str "mutate"),
    ("control", Json.mkObj [
      ("ok", Json.bool (ctrlViolations.isEmpty && ctrlInconclusive.isEmpty)),
      ("bounded", Json.bool ctrl.bounded),
      ("inconclusive", jsonStrArr ctrlInconclusive),
      ("violations", jsonStrArr ctrlViolations)]),
    ("mutants", Json.arr mutantsJson.toArray)
  ]

/-- `traces --mode cover`: the shortest trace to every distinct reachable state, in BFS discovery
order, capped at `max`. `trace_id` is `t<position>` in the (capped) output order. -/
def runTracesCover (spec : Spec St Ev) (maxStates : Nat) (maxDepth : Option Nat) (max : Nat) :
    List Json := Id.run do
  let r := bfs spec.inits spec.events spec.key spec.step spec.props maxStates maxDepth
  let mut out : List Json := []
  let mut i := 0
  for coverIdx in List.range (min max r.covers.size) do
    match coverTrace? r.covers coverIdx with
    | some (initIdx, st0, events) =>
        out := out ++ [tracesLineJson spec.evJson spec.obs spec.step s!"t{i}" initIdx st0 events]
        i := i + 1
    | none => pure ()
  return out

/-- `traces --mode failures`: the shortest counterexample trace for every property whose observed
outcome is `violated`, `trace_id` is the property's own name -- capped at `max`. -/
def runTracesFailures (spec : Spec St Ev) (maxStates : Nat) (maxDepth : Option Nat) (max : Nat) :
    List Json :=
  let r := bfs spec.inits spec.events spec.key spec.step spec.props maxStates maxDepth
  let entries := r.propOut.filterMap fun (p, o) =>
    match o.trace with
    | some (initIdx, st0, events) => some (p.name, initIdx, st0, events)
    | none => none
  (entries.take max).map fun (name, initIdx, st0, events) =>
    tracesLineJson spec.evJson spec.obs spec.step name initIdx st0 events

private def natOf? (s : String) : Option Nat := s.toNat?

/-- Scans `args` for `flag` and returns the token immediately after its first occurrence. -/
private partial def findFlag (flag : String) : List String → Option String
  | [] => none
  | a :: rest =>
      if a == flag then
        match rest with
        | v :: _ => some v
        | [] => none
      else
        findFlag flag rest

private def usage : String :=
  "usage: unit (explore|mutate|traces) [--max-states N] [--max-depth N] [--mode cover|failures] [--max N]"

/-- The compiled `unit` executable's entry point, called from `Main.lean` as
`def main (args : List String) : IO UInt32 := FormalKit.main spec Unit.mutants args`. -/
def main (spec : Spec St Ev) (mutants : List (Mutant St Ev)) (args : List String) :
    IO UInt32 := do
  match args with
  | [] =>
      IO.eprintln usage
      return 2
  | sub :: rest =>
      let maxStates := ((findFlag "--max-states" rest).bind natOf?).getD defaultMaxStates
      let maxDepth := (findFlag "--max-depth" rest).bind natOf?
      match sub with
      | "explore" =>
          IO.println (runExplore spec maxStates maxDepth).compress
          return 0
      | "mutate" =>
          IO.println (runMutate spec mutants maxStates maxDepth).compress
          return 0
      | "traces" =>
          let mode := (findFlag "--mode" rest).getD "cover"
          let max := ((findFlag "--max" rest).bind natOf?).getD defaultTracesMax
          if mode != "cover" && mode != "failures" then
            IO.eprintln s!"unknown --mode {mode}"
            return 2
          else
            let lines := if mode == "cover"
              then runTracesCover spec maxStates maxDepth max
              else runTracesFailures spec maxStates maxDepth max
            for l in lines do
              IO.println l.compress
            return 0
      | other =>
          IO.eprintln s!"unknown subcommand {other}\n{usage}"
          return 2

end FormalKit
