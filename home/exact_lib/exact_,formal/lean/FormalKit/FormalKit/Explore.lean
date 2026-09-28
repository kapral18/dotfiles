import FormalKit.Types
import Std.Data.HashSet

/-!
The single BFS pass every subcommand (`explore`, `mutate`, `traces`) runs on top of. One pass
computes state/transition counts, the `bounded` budget flag, compact parent links for the shortest
trace to every distinct reachable `key` (in discovery order), and, for every property, whether it
held at every dequeued state and, if not, the shortest counterexample trace.

The queue is two plain `List`s (a `front` to consume and a `back` of newly discovered entries,
swapped when `front` empties) rather than an indexed `Array`, so `St`/`Ev` need no `Inhabited`
instance. Traces share parent links and are expanded only for a counterexample or selected
`traces` output; a chain of N states therefore retains O(N), not O(N²), event entries.
-/

namespace FormalKit

variable {St Ev : Type}

/-- One property's outcome from a single BFS pass. `trace` is `(initIndex, initState, events)`
with `events` in chronological (oldest-first) order and `initState` the actual state `events`
starts from (carried directly so callers never need to re-index `spec.inits`) -- `none` when the
property held everywhere explored. -/
structure PropOutcome (St Ev : Type) where
  holds : Bool
  trace : Option (Nat × St × List Ev)

/-- A compact trace node. Each discovered non-initial state stores one event and the index of its
parent node; initial nodes alone retain their initial state. -/
inductive CoverNode (St Ev : Type) where
  | root (initIdx : Nat) (st0 : St)
  | child (parent : Nat) (event : Ev)

/-- Expand one compact cover node into `(initIndex, initState, events)`. Expansion is intentionally
deferred until a caller emits a selected trace or records a counterexample. -/
def coverTrace? (covers : Array (CoverNode St Ev)) (idx : Nat) :
    Option (Nat × St × List Ev) :=
  let rec walk (fuel current : Nat) (events : List Ev) :=
    match fuel with
    | 0 => none
    | fuel + 1 => do
        let node ← covers[current]?
        match node with
        | .root initIdx st0 => some (initIdx, st0, events)
        | .child parent event => walk fuel parent (event :: events)
  walk (covers.size + 1) idx []

/-- Everything a single BFS pass over one `step` function produces. `covers` contains compact
parent links in BFS discovery order. `propOut` is parallel to the `props` list passed in. -/
structure BfsResult (St Ev : Type) where
  statesCount : Nat
  transitions : Nat
  depth       : Nat
  bounded     : Bool
  covers      : Array (CoverNode St Ev)
  propOut     : List (Prop' St Ev × PropOutcome St Ev)

/-- Breadth-first exploration of every state reachable from `inits` over `events`, deduped by
`key` (`Std.HashSet UInt64`), evaluating `props` (against `step`, which may be the real model's
or a mutant's) at every dequeued state.

Budgets: `maxStates` caps the distinct state count (a state discovered once that count is already
reached is simply never enqueued); `maxDepth` (`none` = unbounded) caps how many events a trace
may carry before its successors stop being explored. `bounded := true` whenever either budget
actually cut the closure short -- a `holds` property result under `bounded := true` only means
"held within budget", never a full-closure guarantee. -/
def bfs (inits : List St) (events : List Ev) (key : St → UInt64) (step : St → Ev → St)
    (props : List (Prop' St Ev)) (maxStates : Nat) (maxDepth : Option Nat) :
    BfsResult St Ev := Id.run do
  let mut seen : Std.HashSet UInt64 := {}
  -- queue entry: (current state, compact cover-node index, depth). `front` is consumed
  -- head-first; `back` accumulates discoveries in reverse and is flipped when `front` empties.
  let mut front : List (St × Nat × Nat) := []
  let mut back  : List (St × Nat × Nat) := []
  let mut covers : Array (CoverNode St Ev) := #[]
  -- Successor keys observed exactly at maxDepth are checked against the final discovered set.
  -- A key may be reached through another path within the limit, so deciding immediately would
  -- falsely call a genuinely closed graph bounded.
  let mut depthFrontier : Std.HashSet UInt64 := {}
  let mut bounded := false
  let mut idx := 0
  for s in inits do
    let k := key s
    if seen.contains k then
      pure ()
    else if seen.size >= maxStates then
      bounded := true
    else
      seen := seen.insert k
      let coverIdx := covers.size
      covers := covers.push (.root idx s)
      back := (s, coverIdx, 0) :: back
    idx := idx + 1
  front := back.reverse
  back := []
  let mut found  : Array Bool := Array.replicate props.length false
  let mut traces : Array (Option (Nat × St × List Ev)) := Array.replicate props.length none
  let mut transitions := 0
  let mut depth := 0
  while !front.isEmpty || !back.isEmpty do
    match front with
    | [] =>
        front := back.reverse
        back := []
    | (st, coverIdx, d) :: rest =>
      front := rest
      if d > depth then depth := d
      for (p, pi) in props.zipIdx do
        if !found[pi]! && !(p.check step st) then
          found := found.set! pi true
          traces := traces.set! pi (coverTrace? covers coverIdx)
      let atDepthLimit := match maxDepth with
        | some md => decide (d ≥ md)
        | none => false
      if atDepthLimit then
        for e in events do
          depthFrontier := depthFrontier.insert (key (step st e))
      else
        for e in events do
          transitions := transitions + 1
          let t := step st e
          let k := key t
          if !seen.contains k then
            if seen.size >= maxStates then
              bounded := true
            else
              seen := seen.insert k
              let childIdx := covers.size
              covers := covers.push (.child coverIdx e)
              back := (t, childIdx, d + 1) :: back
  for k in depthFrontier do
    if !seen.contains k then
      bounded := true
  let propOut := props.zipIdx.map fun (p, pi) =>
    (p, ({ holds := !found[pi]!, trace := traces[pi]! } : PropOutcome St Ev))
  return { statesCount := seen.size, transitions, depth, bounded, covers, propOut }

end FormalKit
