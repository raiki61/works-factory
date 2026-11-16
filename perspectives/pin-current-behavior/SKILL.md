---
name: pin-current-behavior
description: Adds tests that pin down today's behaviour without changing any code, each passing on the current version, stable when repeated, and proved to bind by breaking the code. Use when a review says "no test catches this". Not for changing behaviour or fixing a defect.
---

# Pin down the current behavior with tests

**Core rule: do not change code. Add tests that hold the behavior as it is now, and prove each one would catch a change.**

## Pitfalls (read first)

- **No code change.** The defect is that no test catches the behavior; the fix is the tests. Do not rewrite configuration files that exist in the version before the change either.
- **Each new test passes on the version before the change.** If it does not, the current code may be wrong: do not bend the test to pass and do not fix the code. Raise it as "the pinned test fails on the current version", saying either that you see the test as right or that you cannot tell which is right, and leave that defect unfixed.
- **No unstable output.** A pinned test is run more than once on the old version; anything that differs between runs (time, order, randomness, paths of temporary places) breaks it. Pin only what is stable.
- **A test that never went red proves nothing.**

## Steps

### How to pin

1. For each behavior to pin, write a test that asserts what the code does now.
2. Run it on the version before the change: it passes. Run it again: it still passes.
3. **Prove it binds.** Break the code the test is meant to bind, see the test go red; restore the code, see it go green. Do this for every test you add, and record it per test (the test's id, and that red was seen).
4. Since no code changed, there is no fixed line range to point at; the evidence is the red-to-green per test.

### What not to do

- Do not loosen or delete existing tests.
- Do not add a test that no red-to-green proof stands behind.

## Done when

- No code and no configuration file of the version before the change was changed.
- Every new test passes on the version before the change, twice.
- Every new test has a red you saw when its code was broken, and a green after restoring it.
- Every new test that fails on the current version is raised, not bent and not fixed.

## How to report

Per new test: its id, the behavior it pins, and that you saw it red when the code was broken and green after restoring. Separately, each pinned test that fails on the current version: the test, and whether you see the test as right or cannot tell which is right.

## Example

Input: a review says nothing tests how invoice totals are rounded.

Reply:

- Added a test asserting that a total of 10.005 is shown as 10.01, through the same call that prints the invoice. It passes on the current version, twice.
- Changed the rounding in the code to round down: the test went red. Restored it: green.
- No code changed. No pinned test fails on the current version.

## Works well with

- A way of tidying or refactoring without changing behavior, once the behavior is pinned.
