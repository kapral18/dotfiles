---
name: blackboard
description: "Run-scoped shared typed ledger for multi-agent work via the local ,blackboard CLI: typed findings with provenance, an open-question (signal) queue, a synthesis-blocking gate, and a survival check that final artifacts surface what must surface. Use when coordinating fan-out agents (Workflow runs, deep research, Ralph roles, large audits) whose intermediate findings must be shared, queryable, and auditable. Not for durable cross-session knowledge (,ai-kb) or per-session intent specs (/tmp/specs)."
---

# Blackboard Skill

A shared typed ledger for in-flight multi-agent runs, backed by the local `,blackboard` CLI (SQLite WAL, safe for concurrent agent writers). One board per run/topic, stored under `~/.local/share/blackboard/<board>.sqlite3`, so state survives session boundaries and runs are resumable. The mechanics follow the validated core of the irys stateful-swarm pattern: typed entries with provenance, an explicit signal queue, operational-gap blocking, and an artifact survival check.

Use when:

- orchestrating fan-out work (Workflow scripts, deep-research style runs, Ralph roles, multi-agent audits) where agents produce findings other agents or a later synthesis step must see
- a run needs an explicit, machine-checkable queue of open questions instead of prose notes
- a final report/synthesis must provably include the load-bearing findings, contradictions, and undisclosed gaps

Do not use:

- durable cross-session knowledge (verified gotchas, decisions, patterns): `,ai-kb`
- per-session intent/working context: `/tmp/specs` via `,agent-memory`
- single-agent tasks with no synthesis step — the ledger only pays off when state is shared

First actions:

1. Resolve the live interface from `,blackboard --help` (and `<subcommand> --help`); do not rely on memory.
2. Pick one board name per run/topic (kebab-case). Reuse the active topic key when one exists.
3. Seed the board: open `signal`s for the questions the run must answer (priority `critical`/`high` for anything that must not be skipped), then dispatch workers.

Core loop:

- Workers append findings: `,blackboard add --board B --type observation|analysis|calculation|strategy|gap|contradiction --content ... --source-doc ... --source-ref ... --evidence ... --confidence 0.9 --by <worker> --addresses s1`
  - `--addresses sN` marks that signal answered; `--contradicts eN` disputes the target entry (contradictions are always must-surface); `--supersedes eN` retires it; `--must-surface` pins a finding the final artifact must include.
- The orchestrator steers from `,blackboard state --board B --json` (entry counts, open blocking signals) and `,blackboard query` (filter by `--type/--status/--signal/--grep`).
- Anything that turns out to be out of scope gets `,blackboard waive --signal sN --reason ...` — never silently dropped.

Before synthesis (operational-gap blocking):

- `,blackboard gate --board B` exits non-zero while critical/high signals are open. Do not synthesize past a failing gate: either dispatch workers to address the signals, or waive them with a recorded reason. Waived and still-open signals must be disclosed in the final artifact.

After synthesis (survival check):

- `,blackboard survival --board B --report <artifact>` exits non-zero when must-surface entries, contradictions, or open/waived signals are not detected in the artifact (token-containment heuristic — treat a pass as necessary, not sufficient). On failure, run one repair pass that adds the missing items, then re-check.

Output:

- The board is the audit trail: every conclusion traceable to entries, every entry to a source, every dropped question to a waive reason. Reference entry/signal ids (`e12`, `s3`) when summarizing a run.
