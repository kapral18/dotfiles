---
name: k-codebase-design
description: "Shared vocabulary for designing deep modules. Use when designing or improving a module's interface, deciding where a seam goes, finding deepening opportunities, making code more testable or AI-navigable, or when another skill needs the deep-module vocabulary."
---

# Codebase Design

Design **deep modules**: a lot of behaviour behind a small interface, placed at a clean seam, testable through that interface.
Use this language and these principles wherever code is being designed or restructured.
The aim is leverage for callers, locality for maintainers, and testability for everyone.

This skill owns design vocabulary only.
The SOP owns compatibility, minimal edit scope, and verification; `k-code-quality` owns implementation style.
When the design is settled and you write tests through the new interface, load `~/.agents/skills/k-code-quality-tests/SKILL.md`.

## Use when

- deciding a module's interface, or where a seam goes
- judging whether a module is too shallow, or hunting deepening opportunities
- making code testable through its interface rather than past it
- another skill needs the deep-module vocabulary (e.g. a review or improvement pass)

## Do not use

- for pure implementation style, naming, or async idioms — that is `k-code-quality`
- as license to refactor beyond the request — the SOP's minimal edit scope still binds

## Glossary — use these terms exactly

Do not substitute "component", "service", "API", or "boundary". Consistent language is the whole point.

- **Module** — anything with an interface and an implementation; scale-agnostic (a function, class, package, or tier-spanning slice).
  _Avoid_: unit, component, service.
- **Interface** — everything a caller must know to use the module correctly: the type signature, but also invariants, ordering constraints, error modes, required config, and performance characteristics.
  _Avoid_: API, signature (too narrow).
- **Implementation** — what is inside a module, its body of code.
- **Depth** — leverage at the interface: how much behaviour a caller (or test) exercises per unit of interface it must learn.
  **Deep** = large behaviour behind a small interface; **shallow** = interface nearly as complex as the implementation.
- **Seam** _(Feathers)_ — a place where you can alter behaviour without editing in that place;
  the _location_ at which a module's interface lives. Where to put it is its own decision. _Avoid_: boundary (overloaded with DDD).
- **Adapter** — a concrete thing that satisfies an interface at a seam. Describes _role_ (which slot it fills), not substance.
- **Leverage** — what callers get from depth: more capability per unit of interface learned.
  One implementation pays back across N call sites and M tests.
- **Locality** — what maintainers get from depth: change, bugs, knowledge, and verification concentrate in one place.
  Fix once, fixed everywhere.

## Deep vs shallow

A **deep module** is a small interface over a large implementation; a **shallow module** is a large interface over a thin implementation that mostly passes through.
When designing an interface, ask:

- Can I reduce the number of methods?
- Can I simplify the parameters?
- Can I hide more complexity inside?

## Principles

- **Depth is a property of the interface, not the implementation.**
  A deep module can be internally composed of small, mockable parts — they just are not part of the interface.
  It can have **internal seams** (private to its implementation, used by its own tests) as well as the **external seam** at its interface.
- **The deletion test.** Imagine deleting the module. If complexity vanishes, it was a pass-through.
  If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.** Callers and tests cross the same seam.
  If you want to test _past_ the interface, the module is probably the wrong shape.
- **One adapter means a hypothetical seam. Two adapters means a real one.**
  Do not introduce a seam unless something actually varies across it (typically production + test).

## Designing for testability

1. **Accept dependencies, do not create them.**
   `processOrder(order, gateway)` is testable; `processOrder(order)` that news up a gateway internally is not.
2. **Return results, do not produce side effects.**
   `calculateDiscount(cart): Discount` is testable; `applyDiscount(cart): void` that mutates is not.
3. **Small surface area.** Fewer methods = fewer tests; fewer params = simpler setup.

## Rejected framings

- **Depth as implementation-lines ÷ interface-lines** — rewards padding the implementation. Use depth-as-leverage.
- **"Interface" as just the type-level surface** — too narrow; interface here includes every fact a caller must know.
- **"Boundary"** — overloaded with DDD's bounded context. Say **seam** or **interface**.

## Going deeper

When the task is to deepen a real cluster given its dependencies, or to explore several radically different interfaces for one module, load `~/.agents/skills/k-codebase-design/references/going-deeper.md`: dependency categories, seam discipline, replace-don't-layer testing, and the parallel design-it-twice pattern.
