---
name: k-codebase-design
description: "Use for module interfaces, seams, deepening, testability, AI navigation, or deep-module vocabulary."
---

# Codebase Design

Design **deep modules**: much behaviour behind a small interface at a clean seam, testable through that interface.
This skill owns design vocabulary; the SOP owns compatibility, edit scope, and verification, and `k-code-quality` owns implementation style.
When the design is settled and you write tests through the new interface, load `~/.agents/skills/k-code-quality-tests/SKILL.md`.

## Use when

- deciding a module's interface, or where a seam goes
- judging whether a module is too shallow, or hunting deepening opportunities
- making code testable through its interface rather than past it
- another skill needs the deep-module vocabulary (e.g. a review or improvement pass)

## Do not use

- for pure implementation style, naming, or async idioms — that is `k-code-quality`
- as license to refactor beyond the request — the SOP's minimal edit scope still binds

## Glossary

Use these definitions in design discussions; retain established names and more precise domain terms.

- **Module** — anything with an interface and an implementation; scale-agnostic (a function, class, package, or tier-spanning slice).
- **Interface** — everything a caller must know to use the module correctly: the type signature, but also invariants, ordering constraints, error modes, required config, and performance characteristics.
- **Implementation** — what is inside a module, its body of code.
- **Depth** — leverage at the interface: how much behaviour a caller (or test) exercises per unit of interface it must learn.
  **Deep** = large behaviour behind a small interface; **shallow** = interface nearly as complex as the implementation.
- **Seam** _(Feathers)_ — a place where you can alter behaviour without editing in that place;
  the _location_ at which a module's interface lives. Where to put it is its own decision.
- **Adapter** — a concrete thing that satisfies an interface at a seam. Describes _role_ (which slot it fills), not substance.
- **Leverage** — what callers get from depth: more capability per unit of interface learned.
  One implementation pays back across N call sites and M tests.
- **Locality** — what maintainers get from depth: change, bugs, knowledge, and verification concentrate in one place.
  Fix once, fixed everywhere.

## Deep vs shallow

A **deep module** hides substantial complexity behind a small interface; a **shallow module** makes callers understand nearly as much as its implementation.
When designing an interface, ask:

- Can I reduce the number of methods?
- Can I simplify the parameters?
- Can I hide more complexity inside?

## Principles

- **Make invalid states unrepresentable in application data.**
  Enforce domain invariants through data types, data structures, ownership, or state-transition logic:
  tagged states, one owner of mutable data, or validated values used internally.
  Do not count UI visibility, display formatting, or error suppression alone as preventing invalid state.
  Trace every reachable construction, deserialization, and mutation path; passing examples alone do not prove impossibility.
- **Depth is a property of the interface, not the implementation.**
  A deep module can be internally composed of small, mockable parts — they just are not part of the interface.
  It can have **internal seams** (private to its implementation, used by its own tests) as well as the **external seam** at its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, it was a pass-through.
  If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.** Callers and tests cross the same seam.
  If you want to test _past_ the interface, the module is probably the wrong shape.
- **A seam needs a purpose.**
  Introduce one for a caller contract, ownership isolation, or actual dependency substitution; adapter count alone does not justify it.

## Designing for testability

1. **Accept dependencies, do not create them.**
   Passing `gateway` to `processOrder(order, gateway)` lets tests substitute it without intercepting construction.
2. **Prefer returned results to mutated inputs.**
   `calculateDiscount(cart): Discount` exposes a result directly; test `applyDiscount(cart): void` through observable cart changes.
3. **Small surface area.**
   Reduce concepts and setup callers must understand; test coverage follows behavior, not method or parameter counts.

## Rejected framings

- **Depth as implementation-lines ÷ interface-lines** — rewards padding the implementation. Use depth-as-leverage.
- **"Interface" as just the type-level surface** — too narrow; interface here includes every fact a caller must know.

## Going deeper

When the task is to deepen a real cluster given its dependencies, or to explore several radically different interfaces for one module, load `~/.agents/skills/k-codebase-design/references/going-deeper.md`: dependency categories, seam discipline, replace-don't-layer testing, and the parallel design-it-twice pattern.
