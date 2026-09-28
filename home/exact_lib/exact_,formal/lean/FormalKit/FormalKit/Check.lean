import Lean
import Lean.Compiler.ImplementedByAttr
import Lean.Compiler.ExternAttr

/-!
`formalcheck`'s semantic prove logic (see `formal/prove.py`'s module docstring for the Python
side of the contract). This module is compiled once into the kit's own `formalcheck` executable
(`lean/FormalKit/lakefile.toml`'s `[[lean_exe]] name = "formalcheck"`) and never re-elaborated
together with a unit's own source: `main` below calls `Lean.importModules` on the unit's already
-compiled `.olean`s **at runtime**, with `loadExts := false` and `enableInitializersExecution`
never called. Confirmed against a real Lean 4.34.1 toolchain (source read,
`Lean/Environment.lean`'s `finalizePersistentExtensions`/`runInitAttrs`): `loadExts := true`
always throws `` `enableInitializersExecution` must be run before calling `importModules
(loadExts := true)` `` unless that unsafe call happens first, because it unconditionally runs
every imported module's `[init]`/`initialize`/`builtin_initialize` attribute entries -- real,
arbitrary compiled IO a hostile `Unit` module could use to do anything (spawn processes, mutate
this very process's state) the instant its module is imported. `loadExts := false` skips that
entirely, and a live probe (`/tmp/converge-fix-r5-U1/probe1`) confirms `env.find?`'s
`ConstantInfo.isUnsafe`/`isPartial`, `Lean.isExtern`, and `Lean.Compiler.getImplementedBy?` all
still see the real, correct answer for a module imported this way (the constant map and its
attribute data are populated by `importModulesCore`'s own module-loading pass, independent of
`finalizePersistentExtensions`) -- `loadExts` only gates *running* `[init]` code, never reading
already-elaborated declaration/attribute data back out of the environment. Because this checker
is a separately-compiled program that only ever *loads* a unit's already-elaborated `.olean`s
(never elaborates the unit's own syntax itself), a `macro_rules`/`elab_rules` a unit's own module
defines can never reach or rewrite this checker's own code either -- the vulnerability the old
generated-`Axioms.lean`-elaborated-with-`import Unit.Proofs` design had (round 5's root design
decision) does not exist here at all, on top of the `loadExts := false` guard above.
-/

namespace FormalKit.Check

open Lean

/-- True for a character that can appear *inside* a Lean identifier -- used to tokenize a
declaration's stripped pre-text on non-identifier boundaries, so a whole-token match for
`theorem` never fires on a longer identifier that merely contains it as a substring. -/
def isIdentChar (c : Char) : Bool :=
  c.isAlphanum || c == '_' || c == '\''

-- NOTE: this doc comment deliberately spells the two comment-delimiter characters with a
-- space between them (dash, space, slash / slash, space, dash) wherever it would otherwise
-- write the literal two-character token -- writing the real token here would close *this*
-- comment early, which is the exact bug this function fixes.
/-- Strips every slash-dash-...-dash-slash (nested) block comment, a double-dash line comment,
and a `"..."` plain-string literal's *content* (comments and strings are both replaced with
nothing, never left in the output) from a declaration's leading modifier/attribute/doc-comment
text -- so neither a doc comment nor a string argument (`@[deprecated "use --x instead" ...]`)
can ever be mistaken for a real `theorem` keyword by `hasTheoremKeyword` below.

Block-comment closing is checked one character at a time, never by matching a fixed
two-character window greedily: for a doc comment's own closer (dash, dash, slash, space, as in
slash-dash-dash so on so forth dash-dash-slash), the first dash of that trailing run never
combines with the dash right after it into a spurious double-dash line-comment match while at
block-comment depth greater than zero -- doing so (the old generated `Axioms.lean`'s bug) would
skip past the position where the *second* dash and the slash right after it actually form the
real closer, leaving the comment open through the rest of the file and silently hiding the real
`theorem` keyword that follows it (confirmed against a real Lean 4.34.1 toolchain: a doc comment
`Trivial fact` closed the normal way, immediately followed by `theorem t : True := trivial`,
really does close right there and `t` is a real, compiling theorem). A double-dash/opener
sequence is therefore only ever treated specially at block-comment depth zero; at any deeper
depth, only an exact two-character closer/opener window changes the level, and anything else
(including a lone dash not yet followed by a slash) advances by exactly one character so the
very next position can still see it. -/
partial def stripPreText (s : String) : String :=
  let rec go (cs : List Char) (depth : Nat) (inStr : Bool) : List Char :=
    match cs with
    | [] => []
    | c1 :: c2 :: rest =>
      if inStr then
        if c1 == '\\' then go rest depth inStr
        else if c1 == '"' then go (c2 :: rest) depth false
        else go (c2 :: rest) depth inStr
      else if c1 == '"' && depth == 0 then
        go (c2 :: rest) depth true
      else if c1 == '/' && c2 == '-' then
        go rest (depth + 1) inStr
      else if depth > 0 && c1 == '-' && c2 == '/' then
        go rest (depth - 1) inStr
      else if depth == 0 && c1 == '-' && c2 == '-' then
        go (rest.dropWhile (· != '\n')) depth inStr
      else if depth == 0 then
        c1 :: go (c2 :: rest) depth inStr
      else
        go (c2 :: rest) depth inStr
    | [c] =>
      if inStr then []
      else if depth == 0 then [c]
      else []
  String.ofList (go s.toList 0 false)

/-- Splits a stripped string into maximal identifier-character runs, so `"theorem"` can be
matched as its own whole token rather than as a substring of a longer name. -/
partial def tokens (s : String) : List String :=
  let rec go (cs : List Char) (cur : List Char) (acc : List String) : List String :=
    match cs with
    | [] => if cur.isEmpty then acc else (String.ofList cur.reverse) :: acc
    | c :: rest =>
      if isIdentChar c then go rest (c :: cur) acc
      else
        let acc' := if cur.isEmpty then acc else (String.ofList cur.reverse) :: acc
        go rest [] acc'
  (go s.toList [] []).reverse

/-- True when a declaration's own leading modifier/attribute/doc-comment text contains a real
`theorem` keyword: comments and string-literal content stripped first (see `stripPreText`), then
matched as a whole token, never a substring. -/
def hasTheoremKeyword (preText : String) : Bool :=
  (tokens (stripPreText preText)).contains "theorem"

/-- Runs `x` against `env` in a fresh `CoreM` context -- `collectAxioms`/`findDeclarationRanges?`
both only need `MonadEnv`, which a bare `CoreM.State { env }` already provides. `,formal prove`
(not this program) decides pass/fail from the `axioms`/`scope_violations` fields printed below;
`propext`/`Quot.sound`/`Classical.choice` are named directly in `violationsFor` (kept in sync
with `formal/prove.py`'s `ALLOWED_AXIOMS`) only to decide what to print, never to gate anything
on the Lean side. -/
def runCore {α : Type} (env : Environment) (x : CoreM α) : IO α :=
  x.toIO' { fileName := "<formalcheck>", fileMap := FileMap.ofString "" } { env := env }

/-- The user-facing name for a (possibly compiler-mangled) private declaration -- see
`Lean.privateToUserName?`; a compiler-private auxiliary (not a user `private` declaration)
returns `none` from that function, and the raw mangled name is used as-is, still checked, never
skipped. -/
def displayName (name : Name) : Name :=
  if isPrivateName name then (privateToUserName? name).getD name else name

/-- One JSON violation entry: `{"name", "kind", ...}`. `kind` is one of `axiom_declaration`
(a user `axiom` declaration), `unsafe` (`ConstantInfo.isUnsafe`), `extern` (`Lean.isExtern`),
`implemented_by` (`Lean.Compiler.getImplementedBy?`, with a `target` field naming the
implementation), or `disallowed_axiom` (`collectAxioms` found an axiom outside
`propext`/`Quot.sound`/`Classical.choice`, with an `axioms` field listing every axiom found).

Round 5's threat-model amendment (honest authorship; deliberate metaprogramming bypass is out of
scope) drops `partial` (`ConstantInfo.isPartial`) from this list: a `partial def`'s logical
declaration is a genuinely opaque constant, so it cannot make a proof unsound, and its compiled
code is its own body, so there is nothing else it could substitute in. Enumerating every constant
in scope (not only user-named ones) still matters here for a different reason -- the compiler
also emits a `<name>._unsafe_rec` sibling holding the real recursive body -- but a live probe
against a real Lean 4.34.1 toolchain (`/tmp/converge-fix-r5-U6/probe1`) shows that sibling's
`isUnsafe`, `Lean.isExtern`, and `Lean.Compiler.getImplementedBy?` are all clean (`false`,
`false`, `none`) for both a literal `partial def` and an ordinary structurally-recursive
`def`/`theorem` that never used `partial` at all, so no separate exemption is needed for those
three checks either: removing the `isPartial` branch below leaves nothing in `violationsFor` a
partial def or its compiler-generated sibling can ever trip. A hand-written `@[implemented_by]`
on a constant the user wrote directly is unaffected and still fails, because `getImplementedBy?`
on that name/target pair is unchanged. -/
def violationsFor (env : Environment) (name : Name) (info : ConstantInfo) (axiomNames : List Name) :
    Array Json := Id.run do
  let mut out : Array Json := #[]
  let disp := (displayName name).toString
  match info with
  | .axiomInfo _ => out := out.push (Json.mkObj [("name", Json.str disp), ("kind", Json.str "axiom_declaration")])
  | _ => pure ()
  if info.isUnsafe then
    out := out.push (Json.mkObj [("name", Json.str disp), ("kind", Json.str "unsafe")])
  if Lean.isExtern env name then
    out := out.push (Json.mkObj [("name", Json.str disp), ("kind", Json.str "extern")])
  match Lean.Compiler.getImplementedBy? env name with
  | some target =>
    out := out.push (Json.mkObj [("name", Json.str disp), ("kind", Json.str "implemented_by"), ("target", Json.str target.toString)])
  | none => pure ()
  let disallowed := axiomNames.filter (fun a => a != `propext && a != `Quot.sound && a != `Classical.choice)
  if !disallowed.isEmpty then
    out := out.push (Json.mkObj [
      ("name", Json.str disp), ("kind", Json.str "disallowed_axiom"),
      ("axioms", Json.arr (disallowed.map (fun a => Json.str a.toString)).toArray)])
  return out

/-- A module is trusted only when it belongs to the environment produced by separately importing
the pinned toolchain and FormalKit roots. This is exact module membership, not a namespace-prefix
allowlist: an ordinary dependency cannot become trusted merely by naming a module `Lean.Extra`,
`Std.Extra`, or `FormalKit.Extra`. -/
def isTrustedModule (trustedModules : Array Name) (m : Name) : Bool :=
  trustedModules.contains m

/-- Checks every constant defined by a non-trusted module in the imported environment. The
`Unit.Proofs` theorem/user-written classification remains restricted to that exact module for the
F3 vacuity guard; dependency declarations participate only in semantic violations. -/
def run (trustedModules : Array Name) (m proofsModule : Name) :
    CoreM (Array Json × Array Name × Array Json) := do
  let env ← getEnv
  let moduleNames := env.header.moduleNames
  let mut theorems : Array Json := #[]
  let mut userWritten : Array Name := #[]
  let mut violations : Array Json := #[]
  let mut proofsSrc? : Option String := none
  if m == proofsModule then
    proofsSrc? ← try some <$> IO.FS.readFile "Unit/Proofs.lean" catch _ => pure none
  let fileMap? := proofsSrc?.map FileMap.ofString
  let entries := env.constants.fold (init := #[]) fun acc name info =>
    match env.getModuleIdxFor? name with
    | some midx =>
      match moduleNames[midx]? with
      | some modName =>
          if isTrustedModule trustedModules modName then acc else acc.push (name, info, modName)
      | none => acc
    | none => acc
  for (name, info, definingModule) in entries do
    let axioms ← collectAxioms name
    let axiomNames := axioms.toList
    violations := violations ++ violationsFor env name info axiomNames
    if m == proofsModule && definingModule == proofsModule && info.isTheorem then
      let disp := displayName name
      theorems := theorems.push (Json.mkObj [
        ("name", Json.str disp.toString),
        ("axioms", Json.arr (axiomNames.map (fun a => Json.str a.toString)).toArray)])
      match fileMap?, proofsSrc?, ← findDeclarationRanges? name with
      | some fileMap, some src, some ranges =>
        let fullStart := fileMap.ofPosition ranges.range.pos
        let selStart := fileMap.ofPosition ranges.selectionRange.pos
        let preText := (src.toRawSubstring.extract fullStart selStart).toString
        if hasTheoremKeyword preText then
          userWritten := userWritten.push disp
      | _, _, _ => pure ()
  return (theorems, userWritten, violations)

/-- `formalcheck <module>...`: every arg is a root module to `importModules` at runtime; checks
cover its complete non-trusted import environment. Roots are loaded **one module per
`importModules` call**, never all combined into one shared environment: two independently-compiled root modules
that each declare their own unqualified `def main` (e.g. `Main.lean` and a second `lean_exe`'s own
root, the exact round-5 "leanchecker-shadow" finding's own shape) are real, ordinary, non-hostile
Lean and add the same bare name `main` to the root namespace when loaded -- confirmed live against
a real Lean 4.34.1 toolchain that combining both into one `importModules` call fails outright with
`environment already contains 'main' from ...`, before any check here even runs, on completely
unrelated, legitimate units. Checking each module in its own fresh environment avoids that
entirely: a module that itself references another in scope (the round-5 `Evil`/non-`Unit`-prefix-
lib finding's `theorem boom : False := Evil.bogus`) still sees it correctly, because that
reference is resolved through the *referencing* module's own already-recorded `import Evil`
header, not through `main` combining separate top-level roots together. Exits `2` on a bad module
name or an `importModules` failure (an environment/build problem, not a proof problem --
`formal/prove.py` classifies a nonzero, non-JSON-producing exit as an error rather than a parsed
result); exits `0` and prints one JSON document, merged across every module's own separate run,
otherwise. -/
def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  if args.isEmpty then
    IO.eprintln "usage: formalcheck <module>..."
    return 2
  let modules := args.map String.toName
  if let some bad := modules.find? (·.isAnonymous) then
    IO.eprintln s!"formalcheck: could not resolve module name (from {args}, near {bad})"
    return 2
  try
    -- Establish trust from the actual pinned roots before loading any unit module. Failure to
    -- resolve this environment is caught below and closes the proof stage.
    let trustedEnv ← importModules #[
      ({ module := `Lean } : Import),
      ({ module := `Std } : Import),
      ({ module := `FormalKit } : Import),
      ({ module := `FormalKit.Check } : Import)] {} (trustLevel := 0) (loadExts := false)
    let trustedModules := trustedEnv.header.moduleNames
    let mut theorems : Array Json := #[]
    let mut userWritten : Array Json := #[]
    let mut violations : Array Json := #[]
    for m in modules do
      let env ← importModules #[({ module := m } : Import)] {} (trustLevel := 0) (loadExts := false)
      let (t, u, v) ← runCore env (run trustedModules m `Unit.Proofs)
      theorems := theorems ++ t
      userWritten := userWritten ++ (u.map (fun n => Json.str n.toString))
      violations := violations ++ v
    let payload := Json.mkObj [
      ("theorems", Json.arr theorems),
      ("user_written", Json.arr userWritten),
      ("scope_violations", Json.arr violations)]
    IO.println payload.compress
    return 0
  catch e =>
    IO.eprintln s!"formalcheck: {e}"
    return 2

end FormalKit.Check
