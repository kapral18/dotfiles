---
name: palantir
description: Use when summoning, farseeing, beholding, sending word, answering, granting, banishing, or keeping watch over ,palantir legions, or opening the seeing-stone dashboard.
---

# Palantír

`,palantir` orchestrates autonomous legions: one legion = one effort = one tmux session on a disposable `,w` worktree.
SOP §8 owns the contract (chat-agent read-only boundary, escalation, autonomy boundary, memory routing); this skill owns the mechanics.

## Resolve the live interface first

Run `,palantir --help` (and `<sub> --help`) rather than trusting memory; the CLI is the source of truth.

## Model

- **Legion**: tmux session `legion-<id>` + `,w` worktree + manifest under `$PALANTIR_STATE_HOME/legions/<id>/` (default `~/.local/state/palantir`).
- **Stages**: `summon → triage → [diagnose → investigate →] implement → adversarial_review → verify → cleared_for_human`, with `holding` (parked on a question or exhausted budget) and `banished` (terminal).
- **Deterministic supervisor** (one per legion, fcntl-locked): consumes role handshake files (`stages/<stage>.result.json`), drives the machine, machine-runs `verify` (criteria checks from the worktree, exit 0 = green), dedupes coordinator wakes.
- **Roles are interactive agent panes** (per-role harness/model in `~/.config/palantir/config.toml`);
  `adversarial-review` must resolve to a different model family than `implement` — summon refuses otherwise.
- **Coordinator pane** (window 0) takes `[palantir] {…}` event lines and owns judgment:
  answering, nudging, arbitration, memory routing on close.
- **Guard rails**: `cleared_for_human` only via green verify + blocker-free review; injects only into composer-`empty` panes;
  agent panes carry `PALANTIR_AGENT_ROLE` and cannot grant or banish; no publication without explicit human approval.

## Commands

| Move                      | Command                                                                          |
| ------------------------- | -------------------------------------------------------------------------------- |
| Summon a legion           | `,palantir summon "<goal>" [--criteria '<json>'] [--base <ref>] [--no-worktree]` |
| Farsee every legion       | `,palantir` (Textual stone; also tmux prefix+A) / `,palantir farsee`             |
| Behold one legion         | `,palantir behold <id>`                                                          |
| Answer a holding question | `,palantir answer <id> "<msg>"`                                                  |
| Send word to a role       | `,palantir send-word <id> [--window <stage>] "<msg>"`                            |
| Put criteria to trial     | `,palantir trial <id>`                                                           |
| Grant landed work         | `,palantir grant <id>` (closes + routes memory)                                  |
| Banish a legion           | `,palantir banish <id> [--force]` (fail-closed)                                  |
| Keep supervisor watch     | `,palantir keep-watch <id> [--stop]`                                             |

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
- A genuine human fork: write `{"kind": "question", "text": "..."}` instead and stop; the legion parks in `holding`.

## Criteria discipline

Summon with red-provable checks (the `spec` skill's discipline): each criterion `{"text": ..., "check": "<shell, exit 0 = pass>"}`.
Checks run from the legion worktree at every `verify`; judgment-only criteria (no `check`) stay for the human and never block the machine.
