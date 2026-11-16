---
name: pin-current-behavior
description: Closes a defect of the kind "no test catches this" by adding tests that pin down today's behavior without changing any code — each new test passes on the version before the change, stays stable when run twice, and is proved to bind its code by breaking that code to see red and restoring it to see green; a new test that fails on the current version is raised as a sign the current code may be wrong, not fixed. Use when a review says a behavior is untested, when asked to "add tests that pin the current behavior", "characterization tests", "lock this down before we refactor".
---

# Pin down the current behavior with tests

**Core rule: do not change code. Add tests that hold the behavior as it is now, and prove each one would catch a change.**

## Pitfalls (read first)

- **No code change.** The defect is that no test catches the behavior; the fix is the tests. Do not rewrite configuration files that exist in the version before the change either.
- **Each new test passes on the version before the change.** If it does not, the current code may be wrong: do not bend the test to pass and do not fix the code. Raise it as "the pinned test fails on the current version", saying either that you see the test as right or that you cannot tell which is right, and leave that defect parked.
- **No unstable output.** A pinned test is run more than once on the old version; anything that differs between runs (time, order, randomness, paths of temporary places) breaks it. Pin only what is stable.
- **A test that never went red proves nothing.** A test that passes on any code is not a pin.

## How to pin

1. For each behavior to pin, write a test that asserts what the code does now, through the route a real caller uses.
2. Run it on the version before the change: it passes. Run it again: it still passes.
3. **Prove it binds.** Break the code the test is meant to bind, see the test go red; restore the code, see it go green. Do this for every test you add, and record it per test (the test's id, and that red was seen).
4. Since no code changed, there is no fixed line range to point at; the evidence is the red-to-green per test.

## What not to do

- Do not loosen or delete existing tests.
- Do not add a test that no red-to-green proof stands behind.
