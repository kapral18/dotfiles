---
sidebar_position: 2
title: Truth and verification
---

# Truth and verification

The SOP turns "don't guess" into a workflow. A claim is either verified, labeled unknown, or not used.

## Verification stack

| SOP section                  | Contract                                                                                                                                                                                                          |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `2.0 Compatibility`          | classify and state compatibility before edits; no unrequested shims, aliases, wrappers, or deprecation paths                                                                                                      |
| `2.1 External Truth`         | inspect local source, binaries, versions, docs, and locally-verifiable guesses before relying on behavior; hypotheses cannot gate downstream steps                                                                |
| `2.2 Runtime Truth`          | setup questions require source config -> rendered config -> consumer -> safe live probe                                                                                                                           |
| `2.3 Completion`             | stop only after locally-verifiable unknowns are resolved                                                                                                                                                          |
| `2.4 Complete Artifacts`     | compacted/sliced/capped output is an index; recover raw context before relying on content or composing human-visible output                                                                                       |
| `2.5 Self-Report Skepticism` | a model's own rationale, chain-of-thought, "done", status, and plan (and any sub-agent/reviewer/verifier report) are hypotheses about the process, not evidence; verify the outcome against an independent signal |

## Evidence ladder

| Question type      | Required evidence                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------- |
| CLI behavior       | binary path and provenance, then `--version`, `--help`, or source                         |
| Library behavior   | exact package/version from lockfile, import path, and local implementation when available |
| Runtime setup      | source declaration, applied config, consumer implementation, safe live probe              |
| Build/test failure | full output when compacted markers or capped lists appear                                 |
| Review judgment    | base truth, change truth, and smallest safe repro/probe when needed                       |

Compacted output without full recovery is a hypothesis, not a fact. Unknowns are resolved in order: local probes, local source/tests, official docs fetched live, then user questions. When a public cloneable codebase can answer a web/source question, inspect it locally with `rg`, file reads, and `git log`.

## Compatibility line

Every implementation summary includes one of:

| Value                       | Meaning                                        |
| --------------------------- | ---------------------------------------------- |
| `none`                      | no compatibility path added/removed            |
| `removed (requested)`       | user asked to remove/replace old behavior      |
| `kept existing (requested)` | user explicitly asked to preserve old behavior |
