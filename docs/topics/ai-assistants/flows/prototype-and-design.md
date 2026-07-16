---
sidebar_position: 5
title: "Prototype a design question"
---

# Prototype a design question

For decisions you can't settle by talking: "which ordering feels right?", "should this be a state machine?", "what should the panel look like?". The agent builds **throwaway code whose only job is to let you (or it) observe the answer**, then deletes it. The verdict survives; the code doesn't.

**Prerequisites:** a session in the repo the question is about.

## Start it

```text
prototype this: should `list` sort priority-then-id flat, or group by priority with headers?
```

Two branches, picked from your question automatically:

- **Logic question** ("does this state model feel right?") → a tiny terminal harness that renders the same data under each candidate model, including the awkward interaction cases (what happens after a delete? after an add?). You read the outputs side by side.
- **UI question** ("what should this look like?") → up to three _structurally different_ variants on one route, switchable with `?variant=` and a floating bar. You click through them in the browser.

Expect deliberate crudeness — no tests, no error handling, full state printed after every action. That's the contract: learn fast, then delete. Each prototype is clearly marked (`PROTOTYPE — wipe me`).

## Give the verdict

The prototype's output is only half the artifact; the other half is your reaction:

```text
flat sort — the grouped headers break grep-ability
```

The agent records the verdict **with the deciding observation**, deletes the prototype, and the decision lands wherever it's needed (a spec packet's Context line, a commit message, durable memory). If you're away, the agent judges from the observable evidence itself and records that it did.

## Pivots from here

- The verdict feeds a feature → continue straight into [spec + build](spec-and-build.md); the closed fork is already in the packet.
- The question turned out architectural (seams, module boundaries) → `k-codebase-design` picks it up ("design this interface twice and compare").
