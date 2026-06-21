---
title: Skills
---

# Skills

Skills are the intent router below the SOP. The SOP says "load the matching skill"; each skill says what to do for that intent.

| Slice                                                                         | Covers                                                           |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| [Review and delivery](review-and-delivery.md)                                 | reviews, GitHub, PR/issue text, communication                    |
| [Repo workflow and code intelligence](repo-workflow-and-code-intelligence.md) | git/worktrees, semantic tools, clone research, cleanup scanners  |
| [Memory and orchestration](memory-and-orchestration.md)                       | durable memory, Ralph, improvement/interview workflows           |
| [Elastic and Kibana](elastic-and-kibana.md)                                   | domain overlay, Buildkite, labels, ownership, backports, standup |
| [External tools and media](external-tools-and-media.md)                       | Google Workspace, flights, browser control, image generation     |

## Entry contract

Every skill should make four things obvious near the top:

| Field           | Purpose                               |
| --------------- | ------------------------------------- |
| `Use when`      | routing triggers                      |
| `Do not use`    | boundaries and escalation             |
| `First actions` | mandatory first probes or skill loads |
| `Output`        | expected deliverable                  |

The `description` frontmatter is the primary routing signal. Keep it specific, include non-obvious trigger words, and state repo/org constraints when a skill is gated.

## Source map

| Surface    | Path                                                                                     |
| ---------- | ---------------------------------------------------------------------------------------- |
| Source     | [`home/exact_dot_agents/exact_skills/`](../../../../home/exact_dot_agents/exact_skills/) |
| Target     | `~/.agents/skills/`                                                                      |
| Entrypoint | `SKILL.md` in each skill folder                                                          |
| References | optional `references/` under the skill folder                                            |

## Cross-skill hygiene

- Composition skills sanitize public GitHub text before drafting or posting.
- `compose-pr`, `compose-issue`, and `github` reuse review's GitHub context intake when output depends on existing PR/issue/comment context.
- Domain-specific PR/issue rules live in overlay skills instead of generic compose/GitHub skills.
- GitHub issue worktrees prefer `,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>`.
