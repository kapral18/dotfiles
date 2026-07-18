---
name: k-spec
description: "Use when developing an idea, feature request, or bug report into a spec packet with red-capable acceptance checks — before implementing, filing an issue, or summoning a palantir legion. Also when another skill needs testable acceptance criteria for a change."
---

# Spec

Develop an intent into a **spec packet**: the smallest artifact that lets implementation run hands-free and verification run without judgment calls.
A spec packet is the hardened, hand-off-able form of the SOP §3.0 intent spec —
same discipline, plus acceptance criteria a machine can check.

The SOP owns the surrounding gates: the Intent Loop mechanics (§3.0), compatibility intent (§2.0), and external/runtime truth (§2.1/§2.2).
This skill owns the packet contract and the acceptance-criteria discipline.
Consumers: `/k-build` (in-session hands-free implementation), `,palantir summon --criteria` (detached legion), `~/.agents/skills/k-compose-issue/SKILL.md` (GitHub issue text + publication packet), and the `k-review` skill's plan mode (adversarial review of the packet itself).

## Do not use

- trivial single-edit changes where intent is already unambiguous — just do the work under the SOP
- drafting issue/PR text from an already-clear problem: `~/.agents/skills/k-compose-issue/SKILL.md` / `k-compose-pr`
- reviewing an existing plan/design document: the `k-review` skill (plan mode)

## Workflow

1. **Necessity check.**
   Before developing the idea, verify the work is needed: search for existing or superseding work (`git log`, `gh` issue/PR search when a repo target exists, `,ai-kb search` with the concrete goal).
   Done when you can state one of: `new work`, `duplicates <ref>`, `superseded by <ref>`, or `already exists at <path>` — with the evidence.
   On anything but `new work`, stop and surface it instead of drafting.

2. **Close the forks.**
   Run the SOP §3.0 Intent Loop with the interview discipline from `~/.agents/skills/k-interview-me/SKILL.md`:
   answer from evidence before asking, one fork-closing question at a time with a recommended answer.
   Route **empirical** forks — "which state model feels right", "what should this look like" —
   to the `k-prototype` skill instead of asking the user to imagine the answer; the prototype verdict closes the fork.
   In a delegated/hands-free flow the agent records the verdict itself, with the deciding observation, in the packet's Context line.
   When the verified target repo has a domain overlay exposing a planning fork checklist, consult it to seed the fork inventory (current concrete overlay: `~/.agents/skills/k-elastic-domain/SKILL.md` for `elastic/kibana`); evidence-first still applies.
   A fork that cannot close locally — another team's sign-off, a compliance confirmation, an external owner's choice between observably different behaviors — does not block packet assembly: record it under `External dependencies` with an owner, the criteria it blocks, and a recommended default, and keep drafting.
   Done when every remaining interpretation produces the same packet.

3. **Draft acceptance criteria — make them red.** Each criterion is one observable statement plus exactly one of:
   - `check:` — a shell command run from the repo root, non-interactive, idempotent, passing iff exit 0 (`test -f`, `grep -q`, a targeted test command)
   - `judgment:` — for qualities no command can decide, naming the evidence that settles it (a diff property, a screenshot comparison, a named reviewer question)

   **Run every `check` now and paste the invocation + result.**
   The expected state is **red** — the feature is absent, the bug is present —
   which proves the command is runnable and tests the right thing.
   A check that is already green tests nothing: rewrite it, or keep it only as a labelled regression guard.
   A check that has never been run is a hypothesis, not a criterion.
   Check strength (every observed contract failure has been a check under-testing its criterion):
   - a check must fail under a plausible wrong implementation, not just before any implementation —
     a no-op that prints the right words is the counterexample to beat
   - a check verifies the outcome, not the rationale: it must assert what observably changes, never restate why the change is correct (the model's own explanation is not evidence the change works)
   - coverage checks target invocation sites (`grep 'run_x(\["cmd"'`), never bare keywords a data field can satisfy
   - ordering/content criteria assert exact output ("store truth": `test "$(cmd)" = "expected"`), not first-line or substring greps
   - exit codes must be the checked command's: `OUT=$(cmd) && test "$OUT" = ...`, never `cmd | grep` (the pipe reports grep);
     run checks bare, unpiped

   Banned wording in criteria: "works", "correctly", "properly", "as expected" —
   if you cannot say what observable changes, the fork behind it is still open; go back to step 2.
   Done when every criterion carries a run-once red check or an explicit `judgment:` tag, and at least one criterion is checked for any workspace-mutating goal.

4. **Assemble and persist the packet.**
   If the active topic is a session fallback (`session-<id>` — the hook default on main/master/dev with no named topic), bind this session to a named topic first: `,agent-memory select <stable-kebab-topic> --create --session-id <session-id>`.
   Use the session id from the current Topic Buckets prompt when it is shown; do not write `_active_topic.txt`.
   Fill the template below, write it to `/tmp/specs/<pwd>/<topic>.spec.md` (same `<topic>` key as the active SOP intent spec), and show the full packet in the response — the packet is the deliverable.
   Then add or update a single `packet: /tmp/specs/<pwd>/<topic>.spec.md — <one-line status>` line in the intent spec `<topic>.txt`, so session-start injection carries the pointer and a fresh session knows the contract exists.
   One packet in flight per topic: consumers (build lanes, plan review, palantir legions) read this file mid-flow, so do not author the next packet until the current one's outcome is recorded in the `.txt` chain; parallel work belongs on separate topics.
   Never store secrets in it; `/tmp` is best-effort.

5. **Hand off.** The packet is text only — this skill implements nothing and publishes nothing.
   Name the consumer moves and stop for the user's pick:
   - `/k-build` — hands-free implementation in this session, gated on this packet
   - `,palantir summon "<goal>" --criteria '<json>'` — detached legion; criteria come from the packet's checks
   - `k-compose-issue` / `k-compose-pr` — publishable text from the packet (that skill owns sanitization and handoff packet)
   - `k-review` skill plan mode — adversarial review of the packet before any implementation, for high-stakes changes

## Packet template

```markdown
# Spec packet: <topic>

Goal: <one sentence — what exists after, that does not exist now>
Context: <why now; links: issue/PR/thread/prototype verdict>

In scope:

- <...>

Out of scope (binding for /k-build):

- <...>

Acceptance criteria:

1. <observable statement>
   check: `<command>`            # run from repo root; pass = exit 0
   now: red (exit <N>, <date>)   # paste of the run proving it
2. <observable statement>
   judgment: <what evidence settles it>

Risks / unknowns:

- <risk + probe> | Unknown because <reason>

External dependencies (omit section when none; consumers must not start blocked criteria):

- <decision/sign-off needed> — owner: <who>; blocks: criterion <N>; recommended default: <what to assume if forced>

Compatibility intent: none | removes existing behavior (requested) | preserves existing behavior (requested)
```

For a detached legion, pass the packet's checks as summon criteria (each `check` becomes a machine-run verify gate):

```bash
,palantir summon "<goal>" --criteria '[{"text": "<criterion 1>", "check": "<command, exit 0 = pass>"}]'
```

## Output

- The full packet (and the summon command when a detached legion is intended).
- The path it was written to.
- Each check's pasted red run.
- Remaining `Unknown`s and the named consumer moves.
