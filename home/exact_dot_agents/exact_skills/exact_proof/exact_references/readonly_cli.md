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
,proof --topic <topic> add-criterion --requires test,diff "Observable criterion"
,proof --topic <topic> add-evidence --criterion AC-001 --type test --command "make test"
,proof --topic <topic> add-evidence --criterion AC-002 --type file-read --artifact-path /tmp/read-proof.txt
,proof --topic <topic> show EV-001
,proof --topic <topic> review --criterion AC-001 --evidence EV-001 --verdict supports --notes "Why the artifact supports the criterion."
,proof --topic <topic> block "Need external signoff"
,proof --topic <topic> resolve-blocker B-001
,proof --topic <topic> status --json
,proof --topic <topic> check --json
,proof --topic <topic> report
```

Common flags on subcommands:

- `--workspace <path>` selects the workspace identity.
- `--topic <name>` selects the proof topic.

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

Use `,proof check --json` for automation.
The JSON includes `allowed`, `verdict`, `goal`, `workspace`, `topic`, `proof_dir`, criterion counts, issues, blockers, and per-criterion status.
The verdict means "proof recorded", not "the code is globally correct"; `,proof` does not run /build or Ralph adversarial/scope gates.

## Reports

`,proof report` writes a Markdown receipt under the proof directory's `reports/`.
Reports are handoff artifacts; they do not replace the final answer's concise evidence summary.
Treat reports as local proof receipts unless a publication skill sanitizes them for an external surface.
