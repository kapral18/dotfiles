---
sidebar_position: 2
title: Truth and verification
---

# Truth and verification

The SOP turns "don't guess" into a workflow. A claim is either verified, labeled unknown, or not used.

## Verification stack

| SOP section              | Contract                                                                                |
| ------------------------ | --------------------------------------------------------------------------------------- |
| `2.0 Compatibility Gate` | classify compatibility before edits; no unrequested shims                               |
| `2.1 External Truth`     | inspect local source, binaries, versions, and docs before relying on behavior           |
| `2.2 Runtime Truth`      | setup questions require source config -> rendered config -> consumer -> safe live probe |
| `2.3 Completion`         | stop only after locally-verifiable unknowns are resolved                                |
| `2.4 Compacted output`   | compacted/capped output is an index; recover full output when complete lists matter     |

## Evidence ladder

| Question type      | Required evidence                                                            |
| ------------------ | ---------------------------------------------------------------------------- |
| CLI behavior       | binary path, `--version`, `--help`, or source                                |
| Library behavior   | exact package/version and local implementation when available                |
| Runtime setup      | source declaration, applied config, consumer implementation, safe live probe |
| Build/test failure | full output when compacted markers or capped lists appear                    |
| Review judgment    | base truth, change truth, and smallest safe repro/probe when needed          |

## Compatibility line

Every implementation summary includes one of:

| Value                       | Meaning                                        |
| --------------------------- | ---------------------------------------------- |
| `none`                      | no compatibility path added/removed            |
| `removed (requested)`       | user asked to remove/replace old behavior      |
| `kept existing (requested)` | user explicitly asked to preserve old behavior |
