---
sidebar_position: 5
title: Code-quality and dotfiles policy
---

# Code-quality and dotfiles policy

The SOP's coding rules are intentionally conservative: minimal edit scope, no unrequested compatibility, verification before completion, and internal time/effort estimates treated as non-constraints.

## Code-change rules

| Rule                  | Effect                                                            |
| --------------------- | ----------------------------------------------------------------- |
| Cost/time discipline  | never shortcut because the correct path feels slow or costly      |
| Local style matching  | match surrounding structure, terms, and contract strength         |
| Minimal edit scope    | no unrelated cleanup or behavior removal                          |
| Semantic dedupe       | preserve intentional point-of-entry guardrails during refactors   |
| Simplicity discipline | no abstractions/features beyond the ask                           |
| Artifact necessity    | prove a new file/config/dependency has a runtime/tooling consumer |
| Dead-code handling    | remove only dead code introduced by the change unless asked       |
| Type safety           | avoid broad casts and success-shaped fallbacks                    |

## Style matching

Changes should read like they belong in the file they modify: same structure, terminology, formatting, level of detail, and contract strength. Prefer the smallest in-style edit over a pasted standalone rule or helper from another surface.

## Cost/time discipline

Agents must not use their internal sense of elapsed time, effort, or verification expense to decide how much rigor to apply. Quality, simplicity, robustness, scalability, and long-term maintainability outrank speed of completion. Planning, implementation, review, and handoff stay evidence-driven: inspect load-bearing details from multiple angles, seek counterexamples, and stop only when success criteria are satisfied or remaining gaps are explicitly marked `Unknown`.

## Refactor guardrails

When removing duplication, classify repeated checks, instructions, config, or workflow steps before deleting them. Some repetition is an intentional point-of-use guard.

Keep a local guard unless every entry path necessarily passes through the shared rule or helper. If extracting, route every entry point through the shared helper/reference and verify each one.

## Dotfiles overlay

| Concern                   | Rule                                                                                |
| ------------------------- | ----------------------------------------------------------------------------------- |
| Chezmoi source of truth   | resolve target -> `chezmoi source-path` -> edit `home/**` source                    |
| Read-only `$HOME` targets | investigate `readonly_` source; never `chmod` deployed output                       |
| Validation                | run `make check` then `make fmt` after repo changes                                 |
| Docs hygiene              | behavior changes under `home/`, `scripts/`, or `tools/` update docs and `.mermaids` |
| Shell scripts             | shell stays glue; non-trivial logic goes under `scripts/` helpers                   |
| `~/bin` commands          | command updates require fish completion and docs/catalog updates                    |
