---
sidebar_position: 4
title: Side-effect gates
---

# Side-effect gates

The SOP separates local reasoning from actions that affect people, git history, or owned areas.

## Gate map

| Gate                      | Blocks until                                                                   |
| ------------------------- | ------------------------------------------------------------------------------ |
| Git commit                | explicit approval for the exact commit command                                 |
| Git push                  | explicit push request; rejected pushes stop instead of auto-rebasing           |
| CODEOWNERS                | affected paths are in the user's ownership or user approves crossing ownership |
| Human-visible publication | exact payload and target are approved                                          |
| Bot thread carve-out      | author is verified as a bot and flow was explicitly invoked                    |
| GitHub mutation           | `github` skill is loaded and side-effect rules are followed                    |

## Publication split

| Target                        | Default                                                   |
| ----------------------------- | --------------------------------------------------------- |
| Human-authored thread/comment | draft and wait                                            |
| Mixed/unknown participants    | treat as human                                            |
| Verified bot-authored thread  | auto-reply/resolve only inside an explicitly invoked flow |

For wording on any human-visible surface, the SOP routes to the centralized [communication skill](../skills/review-and-delivery.md#communication).
