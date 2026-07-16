---
sidebar_position: 6
title: "Understand a codebase"
---

# Understand a codebase (yours or someone else's)

Three tools depending on whose code and what kind of answer you need.

**Prerequisites:** a session; for your own repo, opened inside it.

## Your repo, guided tour: `/walkthrough`

```text
/walkthrough how does the session picker decide what to show?
```

You get an evidence-anchored explanation — every claim points at a file:line you can click — or, for structure questions, an ASCII architecture map. It's read-only by contract; nothing gets edited. Steer it like a conversation: `go deeper on the caching part`, `draw the flow between these three modules`.

## Someone else's project: just ask "how does X work"

```text
figure out how playwriter's session isolation works
```

The `k-research` skill clones the public repo to `/tmp` and answers **from the actual source** — not from training memory, not from blog posts. Expect answers with paths into the clone (`src/relay/session.ts:42`). The clone stays cached in `/tmp` for follow-up questions.

## Concept search in a big repo: describe what you're looking for

```text
where do we handle retry backoff for failed uploads?
```

Semantic code search (SCSI) finds code by meaning when you don't know the symbol names, then symbol analysis maps every caller and test of what it found. Works where grep can't — you describe behavior, it finds the implementation. (Availability depends on the repo being indexed; the agent tells you when it isn't and falls back to structural search.)

## Reading the answers

Trust the shape: file:line anchors everywhere, `Unknown because …` for what couldn't be verified locally. An answer without anchors is the agent violating its contract — call it out.

## Pivots from here

- Found the code, want it changed → [spec + build](spec-and-build.md) with what you learned as context.
- Found something broken on the way → [debug flow](debug-a-bug.md); the location you found becomes the repro's starting point.
- Want the tour preserved for teammates → `turn this walkthrough into a doc page` (text lands in your tree, publication stays yours).
