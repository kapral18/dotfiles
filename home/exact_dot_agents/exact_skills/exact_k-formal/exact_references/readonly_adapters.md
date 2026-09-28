# Replay adapters

Owner: `~/.agents/skills/k-formal/SKILL.md`. Load this reference when authoring or running a unit's replay
adapter, or when deciding the adapter's process boundary.

## Contract

`,formal replay <unit> [--adapter CMD] [--against REF]` feeds the model's traces to a real command and
compares observed behavior field by field.

- The adapter command comes from `--adapter` or the unit's `MANIFEST.json` `adapter.cmd`/`adapter.cwd`
  (`cwd` is `"repo"` for the target repo root, or `"unit"` for the unit work dir).
- `replay` runs the adapter as a shell command with four environment variables set:
  - `FORMAL_TRACES` — path to the input traces JSONL (one line per trace, from `,formal traces`).
  - `FORMAL_OUT` — path the adapter must write its output JSONL to.
  - `FORMAL_UNIT_DIR` — the unit's work directory, for adapters that need unit-local files.
  - `FORMAL_REPO_ROOT` — the root of the code under test: the real workspace for an ordinary or `--against`
    head run, the plain export of `<base-ref>` for an `--against` ref run (see below). Always set, even
    when `cwd` is `"unit"`, so an adapter that lives in the unit work dir (outside the target repo) can still reach the real code.
- The adapter reads each input trace `{"trace_id","init":i,"init_obs":obs,"steps":[{"event":evJson,"expect":obs}]}`
  and writes exactly one UTF-8 JSON output line for every distinct input `trace_id`, with no duplicate ids:
  `{"trace_id","steps":[{"observed":obs}]}` on success, or `{"trace_id","error":str}` when it could not replay
  that trace at all. `init` is a positional index into `inits`; `init_obs` is that initial state's rendered `obs`.
- Each successful output has exactly the expected number of steps. Every `observed` field must come from the
  invoked real consumer, and the unit must identify that source and the actual fields compared. Never report
  shadow state, copied `expect` values, or unconditional success flags as production observations.
- A missing field is distinct from a JSON `null`; comparison preserves valid JSON numeric equality while
  rejecting missing rows, extra/missing steps, duplicate ids, invalid UTF-8, and malformed JSON with a CLI
  error rather than an uncaught exception.
- Ordinary replay compares each `expect` object against `observed` field by field over the keys in `expect`.
  Differential replay enforces both head and base output lengths before comparing them.
- Adapter-reported errors, mismatches, and non-environment crashes fail replay. Standalone `replay` exits 1.
  Inside `audit`, exit 124 or 127 is an environment error: no stage receipt is persisted and audit exits 2.

## Bootstrap prerequisite (Verify)

Only the root may run a cheap, distinct bootstrap that the real adapter consumer needs before audit, and only
when useful. Start or prepare the actual harness/environment; do not invoke the adapter against a hand-written
trace as a production smoke check. The bootstrap is neither conformance evidence nor a duplicate formal build.

## Choosing the process boundary

Pick the adapter shape by how the real code actually runs; never invent an in-process shortcut that the real system does not offer.

- **In-process, via the repo's own test runner**: when the repo already has a harness that can drive one
  lifecycle step at a time and report state (a test utility, a headless driver), write the adapter as a thin
  script that calls into that harness per event and reports its observable state. This is the cheapest and
  most reliable option when it exists.
- **Process boundary — TUI**: drive the real terminal UI through `~/.agents/skills/k-tmux/SKILL.md` and read
  its rendered state back as the observable.
- **Process boundary — CLI**: invoke the real binary as a subprocess per event (or per trace, replaying the
  full event sequence against one process) and parse its output/exit state as the observable.
- **Process boundary — web UI**: drive the real UI through `~/.agents/skills/k-playwriter/SKILL.md` and read
  DOM/network state back as the observable.

Repo- or product-specific adapter policy (which runner a given surface uses, environment setup, fixture data)
belongs in a verified domain overlay, never inlined into this generic reference or into a generic unit.

## `--against` differential mode (refactors and replacements)

`,formal replay <unit> --against <base-ref>` runs a differential comparison instead of a model-vs-code
comparison. It requires the unit's own `MANIFEST.json` to opt in with `"replay": {"differential": true}`
(default `false`); without it, `--against` refuses (exit 2) with a message that the adapter must execute the
code under `FORMAL_REPO_ROOT`, never a shared live deployment, before differential replay means anything. A
differential adapter that ignores `FORMAL_REPO_ROOT` and instead talks to one fixed running deployment (e.g. an
always-on server/UI instance) produces the _same_ observed output on both sides regardless of what actually
changed between `HEAD` and `<base-ref>` — a differential comparison that always reads as parity. The gate does
not verify this by itself; it only requires the unit's author to explicitly attest the adapter satisfies it.

- Exports `<base-ref>` into a temporary directory under the state root through a throwaway index
  (`GIT_INDEX_FILE=<tmp> git read-tree <base-ref>`, then `git checkout-index -a --prefix=<dir>/`), so
  `.gitattributes` `export-ignore`/`export-subst` never alter it — no `.git` writes: no worktree, no branch,
  no change to the target repo's index.
- Runs the same adapter against the same traces once against that exported tree (`FORMAL_REPO_ROOT` points at
  it) and once at the current head (`FORMAL_REPO_ROOT` points at the real workspace).
- Compares the two `observed` outputs against each other, field by field — the model's own `expect` values are
  ignored entirely in this mode; the pre-change code is the oracle.
- Removes the temporary export afterward regardless of outcome.

Use this mode for refactor or replacement parity, where the question is "does the new code behave like the
old code on the same event sequences", not "does the code match the model's stated expectations".

## `conformance=unverified`

When a unit has no adapter configured and none is supplied with `--adapter`, `,formal audit` records the
replay stage as `unverified`, not as passed and not as failed by default. Reasons this happens legitimately:

- Review-only mode over someone else's PR, where the reviewed code does not run locally.
- A design unit (`--design`), where there is no real code yet to replay against — this case reports `n/a-design` instead, not `unverified`.
- A unit modeling a surface with no runnable local harness yet.

`,formal audit` exits 1 on an `unverified` conformance stage unless `--allow-unverified-conformance` is
passed, and even then the verdict text states conformance is unverified rather than omitting the fact. Never
report an `unverified` replay stage as a passing conformance result, and never let a passing `explore`/`mutate`
stand in for conformance the adapter never actually checked.
