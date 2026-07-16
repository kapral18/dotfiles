# `,proof` CLI reference

`tool_version`: `,proof 0.1.0`

`--help` truth:

```bash
,proof --version
,proof --help
,proof <subcommand> --help
```

## State

State lives outside the worktree:

```text
$AGENT_PROOF_HOME/<workspace-hash>/<topic>/
$XDG_STATE_HOME/agent-proof/<workspace-hash>/<topic>/
~/.local/state/agent-proof/<workspace-hash>/<topic>/
```

The current workspace is the git root when available, otherwise `cwd`.
The topic is `--topic`, `$AGENT_PROOF_TOPIC`, `$PROOF_TOPIC`, or `current`.
Agent-run proof should pass `--topic` explicitly so unrelated freeform proof is not mixed into `current`.
Only `start` creates a ledger; other commands fail instead of creating hidden proof state.
If the resolved proof directory would sit under the selected workspace, the CLI fails;
proof state is always repo-external unless the selected workspace is the home directory itself.

## Commands

```bash
,proof --topic <topic> start [--force] "<goal>"
,proof --topic <topic> path
,proof list [--json] [--all-workspaces]
,proof --topic <topic> add-criterion --requires test,diff "Observable criterion"
,proof --topic <topic> add-evidence --criterion AC-001 --type test --command "make test"
,proof --topic <topic> add-evidence --criterion AC-002 --type file-read --artifact-path ./read-proof.txt
,proof --topic <topic> show EV-001
,proof --topic <topic> review --criterion AC-001 --evidence EV-001 --verdict supports --notes "Why the artifact supports the criterion."
,proof --topic <topic> block "Need external signoff"
,proof --topic <topic> resolve-blocker B-001
,proof --topic <topic> finalize [--allow-failing]
,proof --topic <topic> reopen
,proof --topic <topic> status --json
,proof --topic <topic> check --json
,proof --topic <topic> report
,proof prune --older-than 14 [--dry-run]
```

Common flags on subcommands:

- `--workspace <path>` selects the workspace identity.
- `--topic <name>` selects the proof topic.

## Discovery

`,proof list` lists ledgers for the current workspace by default; `--all-workspaces` scans every workspace hash under the proof state root.

```bash
,proof list --json
```

## Evidence types

Supported types:

```text
test build lint typecheck diff screenshot browser log file-read manual-user-confirmation
```

Rules:

- `test`, `build`, `lint`, and `typecheck` require `--command`; exit code must be `0` to satisfy the gate.
- `diff`, `browser`, and `file-read` require command output or an artifact.
- `screenshot` requires an image artifact.
- `log` and `manual-user-confirmation` are weak evidence and satisfy only criteria that require those exact types.
- Externally captured command evidence must include both `--artifact-path` and `--exit-code`.
- Relative `--artifact-path` values resolve from the selected workspace, matching command evidence.
- Artifacts are copied into the proof directory and recorded with SHA-256, byte size, MIME hint, and capture time.
- Evidence records expose `provenance`: `executed` when `,proof` ran `--command` itself for `test`, `build`, `lint`, or `typecheck`, otherwise `attached` for agent-supplied artifacts or summaries.
- `add-evidence` scans text summaries, text-decodable artifacts up to 1 MiB, and captured command output for conservative secret-like patterns before persisting.
  It refuses matches by pattern name unless `--allow-secrets` is passed, in which case it prints a warning and proceeds.

## Gate

`,proof check` passes only when:

- at least one criterion exists
- each criterion has every required evidence type
- each satisfying evidence item belongs to that criterion
- command evidence exits `0`
- artifact hashes and sizes still match
- the latest review for each satisfying evidence item is `supports` and has notes
- review-time artifact hash/size still match current evidence metadata
- no unresolved blockers remain
- if the ledger is finalized, the recomputed seal still matches the stored seal

Use `,proof check --json` for automation.
The JSON includes `allowed`, `verdict`, `goal`, `workspace`, `topic`, `proof_dir`, criterion counts, finalized seal status, issues, blockers, and per-criterion status plus provenance counts.
The verdict means "proof recorded", not "the code is globally correct"; `,proof` does not run /build or palantir adversarial/scope gates.

## Finalize and reopen

`finalize` stores `finalized_at` and a SHA-256 seal over the canonical criteria, evidence, reviews, and blockers state.
It refuses to seal a failing ledger unless `--allow-failing` is passed.
After finalization, `start` on that ledger and other mutating commands refuse until `reopen` clears the seal and appends `{reopened_at, previous_seal}` to `reopen_history`.
`status`, `check`, `show`, and `report` recompute the seal; a mismatch reports `seal broken`, and `check` fails.

## Prune

`prune --older-than DAYS [--dry-run]` scans every workspace hash under the proof state root and removes topic directories whose `proof.json` mtime is older than `DAYS`.
`--older-than` is required and must be at least `1`; use `--dry-run` first to list what would be removed.

## Reports

`,proof report` writes a Markdown receipt under the proof directory's `reports/`.
Reports include seal status and per-criterion provenance counts.
Reports are handoff artifacts; they do not replace the final answer's concise evidence summary.
Treat reports as local proof receipts unless a publication skill sanitizes them for an external surface.
