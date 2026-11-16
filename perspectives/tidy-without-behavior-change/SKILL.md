---
name: tidy-without-behavior-change
description: Makes a change that must not change behavior (for example removing what nothing uses any more, folding a parameter every caller fills the same way) so that every test that passed before still passes, no existing test is changed outside what is allowed, and a test disappears only when it binds only something that is being removed. Use when a fix is a cleanup, a dead-code removal, or a refactoring that should change nothing observable, or when asked to "tidy this up without changing behavior", "remove the dead code", "clean up after the change".
---

# Tidy without changing behavior

**Core rule: behavior is the same before and after. Every test that passed before the change still passes after it.**

## Pitfalls (read first)

- **Tests are the contract here; do not touch them to make the tidy pass.** Do not change existing tests outside those you are explicitly allowed to change. A test may disappear only when what it binds is itself being removed.
- **"Nothing calls it" is checked, not assumed.** Search for every caller and reference before removing. The public API is outside the repository's reach: no caller left in the repository does not show no caller left outside it.
- **A tidy that needs a behavior change is not a tidy.** If closing it means changing what something does, stop and treat it as a behavior change.

## What to tidy

- Code and abstractions the change made unneeded.
- Parameters, variables, functions, exports, imports, and types that lost their last caller or reference.
- A parameter or option that every caller now fills with the same value: fold it into the definition and remove it — unless folding it would change a test you may not change; then leave it.
- A dead path (an entry point or setting nothing calls or reaches): remove it, or connect its caller. Do not annotate it.

## How to show it changed nothing

Run the tests the change reaches, narrowed by the test tool's own selection, and see that every one that was green before is green after. Rewrite any sentence that still describes something you removed.
