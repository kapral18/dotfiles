---
sidebar_position: 5
title: External tools and media
---

# External tools and media

These skills route non-code tools, browser automation, and generated visual assets.

## `k-artifact`

| Field    | Value                                                                                                                                                                             |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | creating cache-only local HTML artifacts or injecting a local feedback overlay into an already-open live browser page                                                             |
| Source   | [`exact_k-artifact`](../../../../home/exact_dot_agents/exact_skills/exact_k-artifact/)                                                                                            |
| Tool     | `,artifact`                                                                                                                                                                       |
| Boundary | writes only under `~/.cache/agent-artifacts`; worktrees are identity metadata, not storage                                                                                        |
| UX       | generated artifacts start with feedback capture hidden behind a fixed top-right Feedback button; semantic IDs and manifests let feedback name entities and relationships directly |

## `k-google-workspace`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | inspecting or changing Gmail, Drive, Calendar, Admin, Docs, Sheets, or Slides via `gws`                |
| Source   | [`exact_k-google-workspace`](../../../../home/exact_dot_agents/exact_skills/exact_k-google-workspace/) |
| Tool     | `gws` CLI                                                                                              |
| Related  | generic Slides deck geometry and automation live in `references/slides-deck-design-and-automation.md`  |

## `k-letsfg`

| Field    | Value                                                                              |
| -------- | ---------------------------------------------------------------------------------- |
| Use when | searching flights, fares, airline tickets, routes, dates, or travel prices         |
| Source   | [`exact_k-letsfg`](../../../../home/exact_dot_agents/exact_skills/exact_k-letsfg/) |
| Tool     | local LetsFG CLI connectors                                                        |

## `k-nano-banana`

| Field    | Value                                                                                             |
| -------- | ------------------------------------------------------------------------------------------------- |
| Use when | the user names Nano Banana, `,nano-banana`, Gemini/Google image, or a `gemini-*-image` model      |
| Source   | [`exact_k-nano-banana`](../../../../home/exact_dot_agents/exact_skills/exact_k-nano-banana/)      |
| Tool     | `,nano-banana`                                                                                    |
| Boundary | not the default image lane; unnamed image/icon/sticker/illustration work must not load this skill |

## `k-omp`

| Field    | Value                                                                                                                              |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Use when | operating under OMP and selecting native structured-read, code-intelligence, or agent-handoff tools                                |
| Source   | [`exact_k-omp`](../../../../home/exact_dot_agents/exact_skills/exact_k-omp/)                                                       |
| Boundary | runtime adapter only; generic skills retain workflow, evidence, and publication rules. Real-browser work stays with `k-playwriter` |

## `k-playwriter`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | real browser control, rendered UI checks, browsing flows, screenshots, or visual QA        |
| Source   | [`exact_k-playwriter`](../../../../home/exact_dot_agents/exact_skills/exact_k-playwriter/) |
| Boundary | rendered browser behavior only; prefer non-browser tools for static file or source checks  |

Playwriter documentation loads common safeguards plus complete operation recipes before use. The bundled `scripts/read_docs.py` selects sections only for its audited installed version and exact document hash; unknown sources and recorder work read the whole manual. After compaction, reload common guidance and active profiles. Callers use this same contract, avoiding a second unconditional full read. The original document stays installed and unchanged. Recorder and fallback paths can cost more than the former single full read. Conflicting recipes remain subordinate to explicit rules, caller limits, and narrowly scoped verified domain exceptions.

## `k-ui-capture`

| Field    | Value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | proving a built/changed UI matches its intended visual/behavior, auditing a diff for capturable UI changes, or capturing/uploading before/after PR screenshots and videos                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Source   | [`exact_k-ui-capture`](../../../../home/exact_dot_agents/exact_skills/exact_k-ui-capture/)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Related  | creation-side sibling of `k-agent-live-ui-review`; proof mechanics live in its shared `references/proof-mode.md`, loaded directly by `/k-build` and `k-compose-pr`; existing-PR targets pass the published-proof gate, which reuses pairs passing adequacy (media type + frame match the behavior) and freshness checks instead of recapturing; claim map requires every embed claim to map to an adequate asset; shares [`live-ui-runtime.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-review/exact_references/readonly_live-ui-runtime.md); upload via the `k-github` attachments flow                                                        |
| Boundary | head-only proof capture with gated upload; upload requires explicit approval or an approval packet defined by the current workflow; publication requires the proof-mode return shape through `claim_map`; synthetic clips, test-result clips, and prose caveats are inadequate publication assets; per-behavior proof coverage (dedicated pairs by default, shared pair for same-trigger behaviors each plainly visible in it), video for interaction-only deltas; `baseline` (base↔head) vs `intra-change` (tip↔tip) framing with separate publication channels; not for reviewing others' changes (`k-review`/`/k-deep-review` own `k-agent-live-ui-review`) |

## `k-live-ui-windows`

| Field    | Value                                                                                                                                                                                |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Use when | verifying a UI inside a Windows guest running in VirtualBox, over CDP through a host NAT port-forward                                                                                |
| Source   | [`exact_k-live-ui-windows`](../../../../home/exact_dot_agents/exact_skills/exact_k-live-ui-windows/)                                                                                 |
| Routing  | manual                                                                                                                                                                               |
| Related  | adds the Windows/VirtualBox environment to whichever check you're running (`k-ui-capture` or `k-agent-live-ui-review`); shares `live-ui-runtime.md`                                  |
| Boundary | never auto-triggered by `/k-deep-review`, `/k-build`, `k-ui-capture`, or `k-agent-live-ui-review` — load it by hand only on an explicit user request for Windows/VirtualBox coverage |
