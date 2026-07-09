---
sidebar_position: 5
title: External tools and media
---

# External tools and media

These skills route non-code tools, browser automation, and generated visual assets.

## `artifact`

| Field    | Value                                                                                                                 |
| -------- | --------------------------------------------------------------------------------------------------------------------- |
| Use when | creating cache-only local HTML artifacts or injecting a local feedback overlay into an already-open live browser page |
| Source   | [`exact_artifact`](../../../../home/exact_dot_agents/exact_skills/exact_artifact/)                                    |
| Tool     | `,artifact`                                                                                                           |
| Boundary | writes only under `~/.cache/agent-artifacts`; worktrees are identity metadata, not storage                            |

## `google-workspace`

| Field    | Value                                                                                              |
| -------- | -------------------------------------------------------------------------------------------------- |
| Use when | inspecting or changing Gmail, Drive, Calendar, Admin, Docs, Sheets via `gws`                       |
| Source   | [`exact_google-workspace`](../../../../home/exact_dot_agents/exact_skills/exact_google-workspace/) |
| Tool     | `gws` CLI                                                                                          |

## `letsfg`

| Field    | Value                                                                          |
| -------- | ------------------------------------------------------------------------------ |
| Use when | searching flights, fares, airline tickets, routes, dates, or travel prices     |
| Source   | [`exact_letsfg`](../../../../home/exact_dot_agents/exact_skills/exact_letsfg/) |
| Tool     | local LetsFG CLI connectors                                                    |

## `nano-banana`

| Field    | Value                                                                                    |
| -------- | ---------------------------------------------------------------------------------------- |
| Use when | generating raster images from a text prompt                                              |
| Source   | [`exact_nano-banana`](../../../../home/exact_dot_agents/exact_skills/exact_nano-banana/) |
| Tool     | `,nano-banana`                                                                           |

## `playwriter`

| Field    | Value                                                                                     |
| -------- | ----------------------------------------------------------------------------------------- |
| Use when | real browser control, rendered UI checks, browsing flows, screenshots, or visual QA       |
| Source   | [`exact_playwriter`](../../../../home/exact_dot_agents/exact_skills/exact_playwriter/)    |
| Boundary | rendered browser behavior only; prefer non-browser tools for static file or source checks |

## `ui-proof`

| Field    | Value                                                                                                                                                                                                                              |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | verifying a built/changed UI matches its intended visual and capturing screenshot proof for a PR                                                                                                                                   |
| Source   | [`exact_ui-proof`](../../../../home/exact_dot_agents/exact_skills/exact_ui-proof/)                                                                                                                                                 |
| Related  | creation-side sibling of `live-ui-review`; shares [`live-ui-runtime.md`](../../../../home/exact_dot_agents/exact_skills/exact_agent-review/exact_references/readonly_live-ui-runtime.md); runs inline in `/build` and `compose-pr` |
| Boundary | head-only proof capture; not for reviewing others' changes (`review`/`/agent-review` own `live-ui-review`)                                                                                                                         |

## `live-ui-windows`

| Field    | Value                                                                                                                                                                 |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Use when | verifying a UI inside a Windows guest running in VirtualBox, over CDP through a host NAT port-forward                                                                 |
| Source   | [`exact_live-ui-windows`](../../../../home/exact_dot_agents/exact_skills/exact_live-ui-windows/)                                                                      |
| Routing  | manual                                                                                                                                                                |
| Related  | adds the Windows/VirtualBox environment to whichever check you're running (`ui-proof` or `live-ui-review`); shares `live-ui-runtime.md`                               |
| Boundary | never auto-triggered by `/agent-review`, `/build`, `ui-proof`, or `live-ui-review` — load it by hand only on an explicit user request for Windows/VirtualBox coverage |
