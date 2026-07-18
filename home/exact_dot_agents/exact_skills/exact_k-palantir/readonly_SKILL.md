---
name: k-palantir
description: Use only when the user explicitly asks to use Palantír, summon a legion, operate an existing legion, or open the seeing-stone dashboard.
---

# Palantír

`,palantir` orchestrates autonomous legions: one legion = one effort = one tmux session on a disposable `,w` worktree.
SOP §8 owns the contract (opt-in boundary, escalation, autonomy boundary, memory routing); this skill owns the mechanics.

## Resolve the live interface first

Run `,palantir --help` (and `<sub> --help`) rather than trusting memory; the CLI is the source of truth.

## Model

- **Legion**: tmux session `legion-<id>` + `,w` worktree + manifest under `$PALANTIR_STATE_HOME/legions/<id>/` (default `~/.local/state/palantir`).
- **Stages**: `summon → triage → [diagnose → investigate →] implement → adversarial_review → verify → cleared_for_human`, with `holding` (parked on a question, triage rejection, or exhausted budget) and `banished` (terminal).
- **Deterministic supervisor** (one per legion, fcntl-locked): consumes role handshake files (`stages/<stage>.result.json`), drives the machine, durably drains transition actions and coordinator wakes, machine-runs `verify` (criteria checks from the worktree, exit 0 = green), and records per-stage changed-path provenance.
- **Roles are interactive agent panes** (per-role harness/model in `~/.config/palantir/config.toml`);
  `adversarial-review` must resolve to a different model family than `implement` — summon refuses otherwise.
- **Coordinator pane** (window 0) takes `[palantir] {…}` event lines and owns judgment: answering, sending word, and arbitration.
  It reacts to supervisor events; it must not poll, monitor, restart, or directly drive role panes.
- **Guard rails**: `cleared_for_human` only via green verify + blocker-free review; injects only into composer-`empty` panes;
  agent panes carry `PALANTIR_AGENT_ROLE` and cannot summon, grant, or banish (no recursive legions);
  no publication without explicit human approval.
- **Palantír is strictly opt-in** (SOP §8.0): the chat agent MUST NOT propose, summon, or hand work to a legion unless the user explicitly asks to use Palantír in the current conversation.
  Task size, complexity, duration, or convenience never count as that request;
  ordinary instructions to continue or edit are not Palantír authorization.
- **Agent-initiated summons are propose-only after that request**: present the goal packet, acceptance criteria, and base ref, then wait for explicit human approval before running `,palantir summon`.
  Do not summon mid human-driven iteration; converge the spec first (`k-spec` skill).
  `--no-worktree` requires the user to have asked for it by name.

## Commands

| Move                       | Command                                                                          |
| -------------------------- | -------------------------------------------------------------------------------- |
| Summon a legion            | `,palantir summon "<goal>" [--criteria '<json>'] [--base <ref>] [--no-worktree]` |
| Open the dashboard         | `,palantir` (Textual stone; also tmux prefix+A)                                  |
| Survey every legion        | `,palantir farsee`                                                               |
| Behold one legion          | `,palantir behold <id>`                                                          |
| Answer a holding condition | `,palantir answer <id> "<msg>"`                                                  |
| Send word to a role        | `,palantir send-word <id> [--window <stage>] "<msg>"`                            |
| Put criteria to trial      | `,palantir trial <id>`                                                           |
| Grant landed work          | `,palantir grant <id>` (persists closeout packet + tears down)                   |
| Banish a legion            | `,palantir banish <id> [--force]` (fail-closed)                                  |
| Keep supervisor watch      | `,palantir keep-watch <id> [--stop]`                                             |

## Handshake contract (for agents running inside a legion)

A role finishes its stage by writing JSON to the path named in its brief:

```json
{
  "kind": "stage_result",
  "stage": "implement",
  "verdict": "done",
  "summary": "..."
}
```

- `triage` verdicts: `implement` | `diagnose` | `reject`.
- `adversarial_review` adds `"blockers": []` — required, fail-closed: list only findings that survive refutation; empty means clean.
- `adversarial_review` receives the implementation stage's changed-path provenance and treats a vacuous acceptance command as a blocker.
- A genuine human fork: write `{"kind": "question", "text": "..."}` instead and stop; the legion parks in `holding`.

## Criteria discipline

Summon with red-provable checks (the `k-spec` skill's discipline): each criterion `{"text": ..., "check": "<shell, exit 0 = pass>"}`.
Checks run from the legion worktree at every `verify`; judgment-only criteria (no `check`) stay for the human and never block the machine.
The supervisor owns the full acceptance run.
Implementers run focused development checks; reviewers audit observability instead of duplicating the entire suite.
