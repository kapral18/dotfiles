# Dotfiles Project - Agent Instructions

## Architecture Map Preload

For an unfamiliar repo or subsystem, read [`.mermaids/README.md`](.mermaids/README.md) and the relevant concepts in [`.mermaids/S0-concepts.mmd`](.mermaids/S0-concepts.mmd) before settling the approach.
For known paths, consult the relevant row in [`.mermaids/SR-index.mmd`](.mermaids/SR-index.mmd) and only its matching flow/catalog when needed to resolve impact or a co-edit set.
Reuse unchanged architecture context already loaded. Do not preload the whole map for every task.
Before editing, establish the applicable concept/invariant, what breaks and the co-edit set from the targeted map and source.
[`.mermaids/00-overview.mmd`](.mermaids/00-overview.mmd) remains the catalog index when the target is not yet known.

These diagrams are documentation.
When a change under `home/`, `scripts/`, or `tools/` alters a flow, command, or state shown in a `.mmd` file, update that file in the same change (see Documentation Hygiene below).

## Chezmoi Source-of-Truth (Mandatory)

This is a **chezmoi-managed dotfiles repo**. Chezmoi deploys files from `home/` in this repo to `$HOME`.
The deployed copies are outputs — editing them directly creates drift that `chezmoi apply` will silently overwrite.

**Any time you encounter, read, or are about to edit a dotfile, you MUST check whether chezmoi manages it before making changes.**
This applies whether the path is absolute (`/Users/.../bin/utils/...`), tilde-based (`~/bin/...`), or provided by the user.

1. **Resolve symlinks first.** `chezmoi source-path` does not follow symlinks.
   Run `realpath <path>` (or `readlink -f`) to get the canonical path. Use that resolved path for all subsequent steps.
2. Run `chezmoi source-path <resolved-path>` to check.
3. If it returns a source path: edit **only** that source file (under `home/` in this repo).
   Then deploy with `chezmoi apply --no-tty <target>` and verify.
4. If the command fails (not managed) **and** the file is user-writable: edit the file directly.
5. If the command fails **but** the file is read-only (`r--r--r--`): **stop**.
   Read-only files under `$HOME` are likely deployed by chezmoi with a `readonly_` prefix.
   Investigate before editing — search the chezmoi source tree (`home/`) for the filename. Never `chmod` a read-only deployed file.

**This applies to every file under `$HOME`**.
Examples include shell configs, scripts in `~/bin/`, app configs in `~/.config/`, SOP files, skill files, tmux scripts, and anything else chezmoi might manage.

**Chezmoi naming conventions:** `exact_` = exact directory, `readonly_` = read-only, `executable_` = executable.
`dot_` = dotfile (leading `.`), `.tmpl` = template.

---

## Project Validation

- During Produce, run `make fmt`; run `make check` on the integrated candidate in Verify, deduplicated per snapshot under SOP §3.5.
- Do not run checks after every edit.
  Apply SOP §3.5 for evidence-backed recovery within existing authority; rerun only failed or affected checks after a relevant change.
- `make check` is affected-only (`bin/check` vs dirty paths).
- Agents must not run `make check-full`, `bin/check --full`, or `make test`; those are human-only.
  Pre-commit runs `bin/check --staged` and must not run the full suite.
- When adding or renaming production code or tests, keep them on the affected map in the same change.
  Name tests so `scripts/check.py` convention hits, or add a `TEST_RULES` row.
  Convention: `scripts/foo.py` / `foo.sh` → `test_foo.py` or `tests/test_foo.py`; `home/exact_lib/exact_,name/` → `tests/test_name.py`.
  Do not leave a new shard reachable only by `make check-full`.
- If either command fails, apply SOP §3.5 for scoped recovery and §3.4 for repeated attempts without progress;
  report blocked work with the relevant output.

---

## AI Setup Contribution Boundary

When changing AI functionality in this chezmoi repo, keep generic mechanics and domain policy separate.

- **Generic surfaces:** portable behavior such as global SOP mechanics, shared skills, generic subagent/runtime profiles, hooks, model/MCP/package generators, and registries.
  Cross-repo AI workflow docs are also generic surfaces.
- **Domain surfaces:** repo/org/product policy such as `k-elastic-domain`, `k-kibana-*`, Elastic/Kibana labels, ownership, Buildkite routing, and bot allowlists.
  PR templates, live-UI targets, endpoints, and data setup are also domain surfaces.
- **Future domains:** any future repo/org/product overlay with comparable policy.

Rules:

1. Generic surfaces may verify the target, load the matching overlay, and pass through overlay results or concrete packets;
   they must not inline Elastic/Kibana defaults, examples, allowlists, labels, hosts, target packets, templates, or fallback behavior.
2. Domain overlays add policy to a primary generic workflow.
   They must not duplicate or replace generic routing, review methodology, publication gates, side-effect gates, memory, or verification discipline.
3. When an interaction changes, update both sides.
   The generic side documents the dispatch/packet boundary, and the domain side owns the concrete policy/data.
4. Treat existing domain-specific content in generic surfaces as non-precedent.
   If a task touches it, move it behind a verified overlay or domain skill instead of expanding it.
5. If no verified domain overlay applies, generic workflows should block or report `Unknown` rather than borrow Elastic/Kibana behavior.
6. Keep documentation aligned: cross-repo mechanics belong in generic AI docs;
   Elastic/Kibana specifics belong in `docs/topics/ai-assistants/skills/elastic-and-kibana.md` or the relevant domain page.

---

## Task-Triggered Dotfiles Recipes

Before adding or changing package/app installation entries, changing shell/helper architecture, or adding/updating deployed commands, load and follow the complete [dotfiles agent recipes](docs/topics/ai-assistants/system-prompt/dotfiles-recipes.md).
This reference owns the existing installation-priority exceptions, registry verification, thin-shell/helper rules, comma command namespace, completions and catalog/census co-edits.
Do not load these recipes for unrelated tasks; reuse their complete, unchanged text while it remains in context.

## Documentation Hygiene

- Any change to dotfiles that affects behavior, commands, or workflows MUST be reflected in `docs/`.
  Dotfiles include anything under `home/`, including templates, scripts, and app/package install logic.
- If a dotfiles change does not require a docs change, state why in the PR/commit context (briefly) so the docs/code divergence is explicit.

## AI-Facing Text Formatting

Use these rules when editing LLM-guidance text: text whose purpose is to steer model behavior.
Examples include SOPs, skills, prompts, agent profiles, hooks docs, and instruction/reference `.md` or `.txt` files.
Do not apply this rule to arbitrary prose or data solely because it may be passed to an LLM as context.

**Instruction boundaries (mandatory for instruction text):** when adding, generating, or rewording any LLM instruction, load `home/exact_dot_agents/exact_skills/exact_k-instruction-boundaries/readonly_SKILL.md` (deployed: `~/.agents/skills/k-instruction-boundaries/SKILL.md`) and apply it: default to hard standalone prohibitions for forbidden behavior; add affirmative wording only when it sharpens execution.
The skill also owns the fidelity boundaries — factual negations, quoted examples, enumerated gate contracts, and complete standalone prohibitions stay as written.

- Treat line breaks as prompt-ingestion affordances, not as a fixed-width prose formatter.
- Do not hard-wrap mid-sentence just to satisfy a target column. A line around 140 characters is a soft boundary, not a target.
- Keep a sentence intact by default. Move the next sentence to a new line when appending it would cross the soft boundary.
- When a line exceeds roughly 150 characters, review it manually.
  Split or reword it into separate complete sentences only when doing so preserves every condition, qualifier, and example.
- Do not force every long line under 150 characters.
  Leave dense single-sentence rules, exact gate contracts, command examples, URLs, paths, tables, frontmatter, and code blocks long when splitting would weaken precision or continuity.
- If a single sentence is too long, prefer a meaning-preserving rewrite into two complete sentences.
  If no safe rewrite exists, keep the long sentence rather than cutting it at connector words or whitespace.
- Never drop modal strength (`MUST`, `MAY`, `do not`, `only when`), scope qualifiers, examples, paths, flags, commands, or exception clauses to make a line shorter.
- For Markdown, rely on `bin/fmt` / `,format-md` after editing. For plain text files, apply the same policy manually and inspect the diff.

## Agent Skill Naming (Mandatory)

Repo-owned skills MUST use the `k-` namespace.
Source directories live under `home/exact_dot_agents/exact_skills/exact_k-<name>/`, and the skill entrypoint frontmatter `name` MUST be `k-<name>`.
References to those skills MUST use the deployed path `~/.agents/skills/k-<name>/SKILL.md`.
Do not add unprefixed repo-owned skill directories, frontmatter names, or skill references.

---

## Updating Home SOP Files

Home SOPs are installed into `$HOME` by chezmoi. `home/readonly_AGENTS.md` is the generated core SOP.
Native global entrypoints link to it; `~/CLAUDE.md` uses Claude's native `@AGENTS.md` import instead of a second full body.
`~/.claude/CLAUDE.md` is Claude's global entrypoint. `CLAUDE.md` imports `AGENTS.md`.
The compiled ownership model lives in `docs/topics/ai-assistants/system-prompt/source-of-truth.md`.

| Source                                         | Target                         |
| ---------------------------------------------- | ------------------------------ |
| `home/readonly_AGENTS.md`                      | `~/AGENTS.md`                  |
| `home/readonly_CLAUDE.md`                      | `~/CLAUDE.md`                  |
| `home/dot_claude/symlink_CLAUDE.md`            | `~/.claude/CLAUDE.md`          |
| `home/dot_gemini/config/symlink_AGENTS.md`     | `~/.gemini/config/AGENTS.md`   |
| `home/dot_config/opencode/symlink_AGENTS.md`   | `~/.config/opencode/AGENTS.md` |
| `home/dot_omp/private_agent/symlink_AGENTS.md` | `~/.omp/agent/AGENTS.md`       |
| `home/exact_dot_agents/exact_skills/`          | `~/.agents/skills/`            |

Codex has no `AGENTS.md` entrypoint: `07-merge-codex-config` writes the SOP into `~/.codex/config.toml` as the root `developer_instructions`; each managed child role replaces it with its own.

Rules:

1. Edit the compiled source set: `home/readonly_AGENTS.md` for core text, plus disposition/consumer files for moved rules.
2. Run `python3 scripts/compile_ai_policy.py generate` and `make verify-agent-policy` after policy edits.
3. Keep referenced skill files under `home/exact_dot_agents/` in sync.
4. Review with `chezmoi diff`, apply with `chezmoi apply`, and verify only the rendered content or runtime behavior relevant to the change.
