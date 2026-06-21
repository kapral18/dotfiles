---
sidebar_position: 1
title: Roles and diversity
---

# Roles and the diversity gate

Roles are configured in [`~/.config/ralph/roles.json`](../../../../home/dot_config/ralph/roles.json):

| Role          | Default harness | Default model                    | Mode flag     |
| ------------- | --------------- | -------------------------------- | ------------- |
| `planner`     | `cursor`        | `claude-opus-4-8-thinking-xhigh` | `--mode plan` |
| `executor`    | `cursor`        | `composer-2.5`                   | `--force`     |
| `reviewer`    | `cursor`        | `claude-opus-4-8-thinking-xhigh` | `--mode ask`  |
| `re_reviewer` | `cursor`        | `gpt-5.5-extra-high`             | `--mode ask`  |
| `reflector`   | `cursor`        | `claude-opus-4-8-thinking-xhigh` | `--mode ask`  |

Anthropic-side roles pin **Opus 4.8 at xhigh effort**.

Why:

- Fable 5 is listed by `cursor-agent models` but is not usable on this account.
- other effort tiers (`max`, `high`, …) are deliberately not used.
- the TUI picker and `CURSOR_MODELS` exclude Fable and non-xhigh Opus variants.

Cursor model ids are **Cursor-internal aliases**. They are resolved by Cursor's own routing and are not entries in `ai_models.yaml`. Refresh Ralph's `CURSOR_MODELS` snapshot from `cursor-agent models` when Cursor rotates model generations.

Role-scoping rules:

| Role / harness                    | Safety scope  |
| --------------------------------- | ------------- |
| planner / Cursor                  | `--mode plan` |
| reviewer / Cursor                 | `--mode ask`  |
| re_reviewer / Cursor              | `--mode ask`  |
| executor / Cursor                 | `--force`     |
| planner/reviewer/re_reviewer / Pi | `--no-tools`  |

The orchestrator enforces `family_of(re_reviewer.model) != family_of(reviewer.model)` with substring matching over `claude|gpt|gemini|llama|mistral|deepseek`.

Per-role prompts live at [`home/dot_config/ralph/prompts/`](../../../../home/dot_config/ralph/prompts/).

Local models (llama-cpp / qwen3.6) are opt-in only; defaults never depend on `,llama-cpp serve` being up. Swap them in by editing `roles.json` (e.g. point `executor.harness=pi`, `executor.model=llama-cpp/local`). See [llama.cpp local inference](../llama-cpp/index.md).

## Domain-gated `/review` skill invocation

For domain-belonging codebases, reviewer roles can invoke the operator's [`review` skill](../reviews/index.md) through a domain review policy.

Effect:

- the review skill's verification disciplines become the primary instruction.
- Ralph's JSON output contract stays the wire format.
- workspaces with no matched domain policy are unchanged.

- **Detection**: [`review_domain_for_workspace(path)`](../../../../scripts/ralph.py) parses `git remote -v` and checks `REVIEW_DOMAIN_POLICIES`. The current policy set includes `elastic`, matching `(github\.com[:/])elastic/` against any remote URL (HTTPS or SSH; `origin` or `upstream`). Best-effort — non-git directories, missing paths, or `git` failures yield no domain.
- **Wiring**: [`domain_review_preamble(domain, role)`](../../../../scripts/ralph.py) reads `~/.agents/skills/review/references/{judging_core,shared_rules,local_changes}.md` and renders the selected policy heading (currently `## REVIEW SKILL HEURISTICS (elastic)`) containing (a) "you are running the `/review` skill in local_changes mode", (b) the skill's `judging_core.md` content verbatim, (c) the skill's `shared_rules.md` content verbatim, (d) the skill's `local_changes.md` content verbatim, and (e) a format-normalization note translating the skill's "fix in working tree" guidance into Ralph's `criteria_unmet` + `next_task` JSON fields. The block is prepended to the dynamic context BEFORE `## SPEC`, so the model reads the skill instruction first then applies it to the inputs.
- **Override**: `RALPH_REVIEW_SKILL_DIR=<path>` swaps in a different skill source directory (useful for testing alternate review heuristics without touching `~/.agents/`).
- **Graceful degradation**: when the domain is unknown or the skill files are missing, the preamble silently degrades to empty (no crash) and the default review path runs unchanged. Operators without the skill installed see no behavior change.
- **Output contract**: unchanged. Reviewer still emits `{verdict, criteria_met, criteria_unmet, next_task, blocking_reason, notes}`; re-reviewer still emits `{agree_with_primary, final_verdict, ...}`. The orchestrator's verdict parser is not aware that a domain preamble was injected.
