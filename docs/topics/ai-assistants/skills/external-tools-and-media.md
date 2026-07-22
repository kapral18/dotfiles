---
sidebar_position: 5
title: External tools and media
---

# External tools and media

These skills route non-code tools, browser automation, and generated visual assets.

## `k-artifact`

| Field    | Value                                                                                                                 |
| -------- | --------------------------------------------------------------------------------------------------------------------- |
| Use when | creating cache-only local HTML artifacts or injecting a local feedback overlay into an already-open live browser page |
| Source   | [`exact_k-artifact`](../../../../home/exact_dot_agents/exact_skills/exact_k-artifact/)                                |
| Tool     | `,artifact`                                                                                                           |
| Boundary | writes only under `~/.cache/agent-artifacts`; worktrees are identity metadata, not storage                            |
| UX       | generated artifacts start with feedback capture hidden behind a fixed top-right Feedback button                       |

## `k-google-workspace`

| Field    | Value                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------ |
| Use when | inspecting or changing Gmail, Drive, Calendar, Admin, Docs, Sheets via `gws`                           |
| Source   | [`exact_k-google-workspace`](../../../../home/exact_dot_agents/exact_skills/exact_k-google-workspace/) |
| Tool     | `gws` CLI                                                                                              |

## `k-letsfg`

| Field    | Value                                                                              |
| -------- | ---------------------------------------------------------------------------------- |
| Use when | searching flights, fares, airline tickets, routes, dates, or travel prices         |
| Source   | [`exact_k-letsfg`](../../../../home/exact_dot_agents/exact_skills/exact_k-letsfg/) |
| Tool     | local LetsFG CLI connectors                                                        |

## `k-nano-banana`

| Field    | Value                                                                                        |
| -------- | -------------------------------------------------------------------------------------------- |
| Use when | generating raster images from a text prompt                                                  |
| Source   | [`exact_k-nano-banana`](../../../../home/exact_dot_agents/exact_skills/exact_k-nano-banana/) |
| Tool     | `,nano-banana`                                                                               |

## `k-playwriter`

| Field    | Value                                                                                      |
| -------- | ------------------------------------------------------------------------------------------ |
| Use when | real browser control, rendered UI checks, browsing flows, screenshots, or visual QA        |
| Source   | [`exact_k-playwriter`](../../../../home/exact_dot_agents/exact_skills/exact_k-playwriter/) |
| Boundary | rendered browser behavior only; prefer non-browser tools for static file or source checks  |

## `k-ui-proof`

| Field    | Value                                                                                                                                                                                                                                    |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | verifying a built/changed UI matches its intended visual and capturing screenshot proof for a PR                                                                                                                                         |
| Source   | [`exact_k-ui-proof`](../../../../home/exact_dot_agents/exact_skills/exact_k-ui-proof/)                                                                                                                                                   |
| Related  | creation-side sibling of `live-ui-review`; shares [`live-ui-runtime.md`](../../../../home/exact_dot_agents/exact_skills/exact_k-agent-review/exact_references/readonly_live-ui-runtime.md); runs inline in `/k-build` and `k-compose-pr` |
| Boundary | head-only proof capture; not for reviewing others' changes (`k-review`/`/k-agent-review` own `live-ui-review`)                                                                                                                           |

## `k-live-ui-windows`

| Field    | Value                                                                                                                                                                       |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | verifying a UI inside a Windows guest running in VirtualBox, over CDP through a host NAT port-forward                                                                       |
| Source   | [`exact_k-live-ui-windows`](../../../../home/exact_dot_agents/exact_skills/exact_k-live-ui-windows/)                                                                        |
| Routing  | manual                                                                                                                                                                      |
| Related  | adds the Windows/VirtualBox environment to whichever check you're running (`k-ui-proof` or `live-ui-review`); shares `live-ui-runtime.md`                                   |
| Boundary | never auto-triggered by `/k-agent-review`, `/k-build`, `k-ui-proof`, or `live-ui-review` — load it by hand only on an explicit user request for Windows/VirtualBox coverage |
