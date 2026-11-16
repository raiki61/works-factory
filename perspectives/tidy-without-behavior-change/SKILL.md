---
name: tidy-without-behavior-change
description: Makes a cleanup that must not change behaviour, such as removing unused code or folding a parameter every caller fills the same way, so every passing test still passes and no test changes beyond what is allowed. Use when a refactoring should be invisible, or when asked to "tidy this without changing what it does". Not for removing a named feature with its tests.
---

# Tidy without changing behavior

**Core rule: behavior is the same before and after. Every test that passed before the change still passes after it.**

## Pitfalls (read first)

- **Tests are the contract here; do not touch them to make the tidy pass.** Do not change existing tests outside those you are explicitly allowed to change. A test may disappear only when what it binds is itself being removed.
- **"Nothing calls it" is checked, not assumed.** Search for every caller and reference before removing. The public API is outside the repository's reach: no caller left in the repository does not show no caller left outside it.

## Steps

### What to tidy

- Code and abstractions the change made unneeded.
- Parameters, variables, functions, exports, imports, and types that lost their last caller or reference.
- A parameter or option that every caller now fills with the same value: fold it into the definition and remove it — unless folding it would change a test you may not change; then leave it.
- A dead path (an entry point or setting nothing calls or reaches): remove it, or connect its caller. Do not annotate it.

### How to show it changed nothing

Run the tests the change reaches, narrowed by the test tool's own selection, and see that every one that was green before is green after. Only when the project has no way to narrow (to select tests by id or name), run the whole suite once just before you answer. Rewrite any sentence that still describes something you removed.

## Done when

- Every test that was green before the change is green after it.
- No existing test changed outside those you were allowed to change, and a test disappeared only with what it binds.
- Every removal rests on a search for callers and references, short of the public API.
- No sentence still describes something you removed.

## How to report

What you removed or folded, and the search that showed nothing calls it; the tests you ran and that every one green before is green after; the tests that disappeared and what they bound; the sentences you rewrote.

## Example

Input: after a change, a formatting option is set to the same value by every caller.

Reply:

- Searched for the option: 4 callers, all pass the same value; it is not part of the public API.
- Folded the value into the function and removed the option from its signature and the 4 callers.
- Ran the tests that reach the function: 12 green before, 12 green after; no test changed.
- Rewrote the function's doc comment, which described the option.

## Works well with

- A way of pinning today's behavior with tests before tidying code that has none.
