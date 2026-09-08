---
sidebar_position: 1
title: Deep-review topology
---

# Deep review topology

Deep review is deeper source/risk coverage inside one final Verify stage, not a longer orchestration graph.

![Staged workflow](../assets/deep-review-flow.svg)

Understand resolves PR intent, target/base/head, relevant source, and existing evidence once. Known authorized fixes are produced and formatted before final review. The root retains strong artifact review and adversarial challenge, assigning distinct questions against the same frozen candidate and shared evidence. A blind fresh-eyes lane remains available for comprehension risk; it receives no PR narrative, history, previous findings, or pack metadata. Distinct specialists are useful only for independent risk questions or tools; they consume the same frozen candidate and do not verify one another. Final UI evidence uses the verified target/config/data packet and shared runtime safety rules. Missing evidence is a reported condition, not an automatic worker rerun. Results are consolidated without another findings-audit, post-review, or convergence stage. Review alone does not authorize source edits or publication. Pending-review reconciliation, exact-payload approval, and transaction readback still apply before/after authorized GitHub writes.

Every delegated worker is a leaf. The active root/main controller owns fan-out and the compact task handoff. Late events do not grant permission to reopen terminal workers. Native enforcement varies by harness; see [staged workflows](../subagents.md).

PR intake reads the complete primary discussion and only references needed to settle a named material question. It does not recursively crawl every reachable link. Final Verify checks snapshot freshness once; drift or a missing worker snapshot produces a stale/blocked result, not automatic pack rebuilding or a new review. Authorized publication retains its immediate target and anchor checks.
