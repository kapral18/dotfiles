---
name: k-omp
description: "Use in OMP to select native structured-read, code-intelligence, and agent tools."
---

# Oh My Pi Runtime Adapter

Use this skill only when the active harness is OMP.
It realizes generic skill contracts with OMP-native tools; it does not change their workflow, evidence, or publication gates.

## Browser boundary

Use `k-playwriter` for all real-browser work in OMP, including existing-tab control and live overlays;
use it instead of OMP's native `browser` tool for those flows.

## Structured reads

Use `read` before shell readers when its source kind applies:

- source files: anchored ranges and `:raw` when verbatim content matters;
- archives: `.tar`, `.tar.gz`, `.tgz`, and `.zip` members;
- SQLite: `.sqlite`, `.sqlite3`, `.db`, and `.db3` in read-only mode;
- documents: PDF, office files, EPUB, and RTF;
- notebooks: editable cell text, or `:raw` for notebook JSON;
- images and web URLs: inline inspection or reader-mode text, with `:raw` for original response content.

`read` does not replace browser evidence for rendered UI, video/GIF frame inspection, or live GitHub/API truth required before a mutation.

## Code intelligence

Use `lsp` for definitions, references, cross-file renames, diagnostics, and code actions when available.
Use anchored `edit` for narrow changes. Use `ast_edit` only for repeated structural rewrites and explicitly apply or reject each proposal.

## GitHub context

`issue://` and `pr://` are fast cached read paths only.
Before a GitHub mutation, reconciliation, or readback gate, obtain live `gh`/API evidence required by the owning generic skill.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
When delegation is permitted, use `task` with explicit managed profile names and ready stage-sized packets.
Before dispatch, load `~/.agents/skills/k-review/references/runtime-harnesses.md` for the native capability boundaries.
Do not dispatch unattended workers in native plan mode or restricted SDK sessions; those children omit the managed extensions.
Keep the registry's category model/effort and the SOP's single final Verify stage. Honor no-delegation requests inline.
Pass large packets with `local://`; inspect returned artifacts through `agent://`, `history://`, and `artifact://`.
Use `hub` only for authorized named-process lifecycle operations. Do not use peer messages to wake or resume workers.

MUST NOT use Eval's `agent()`, `workpool()`, or `completion()` helpers, or their synthetic bridge calls, as managed model/worker lanes.
They bypass ordinary tool dispatch; `agent()` starts background work despite a blocking profile, and `completion()` selects its own model tier.
Ordinary Eval code remains available, but passing the outer profile/settings guard does not certify these hidden helpers.
This is a routing prohibition, not native enforcement. Do not claim that an instruction marker closes the bridge or plan-mode gaps.
