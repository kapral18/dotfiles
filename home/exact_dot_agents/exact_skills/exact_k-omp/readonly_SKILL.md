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

## Handoffs and GitHub context

Use `task` and `hub` for typed agent work and process lifecycle.
Pass large packets with `local://`; inspect worker results through `agent://`, `history://`, and `artifact://`.

`issue://` and `pr://` are fast cached read paths only.
Before a GitHub mutation, reconciliation, or readback gate, obtain live `gh`/API evidence required by the owning generic skill.
