---
name: test-double-fidelity
description: Checks whether the test doubles (mocks, stubs, fakes) at the seams a change touches — another process, another service, a browser, an outside API, a protocol — have the same shape as the real thing, using one value actually taken from the real thing, because a double whose input shape differs from the real one lets tests pass on a shape only the double accepts. Use when a change touches an outside seam and its tests rely on doubles, or when asked "does this mock match the real API", "are these tests testing the fake", "check the stubs against reality".
---

# Check that test doubles at a seam have the real thing's shape

**Core rule: judge a double not by how faithfully it reproduces the real thing, but by whether an error in the implementation can be observed through it — and check its shape against one value taken from the real thing.**

A double whose input shape differs from the real thing cannot observe the error: the test turns green on a shape that only the double accepts.

## Pitfalls (read first)

- **Applies when the change touches a seam with the outside**: another process, another service, a browser, an outside API, a protocol.
- **Compare with a real value, not with documentation or memory.** Take one value from the real thing and hold the double's shape against it.
- **Do not break the real working tree.** Make any copy you need for running in a fresh temporary directory outside it.

## How to report

One row per mismatch: where (the path and line in the current file), and what differs — with the mechanism, whether it was measured, and when it would be a false positive, when useful. If there is none, say what you compared with what.

Works well with (optional; this file does not need it): a set of rules that keeps the reviewed repository's own names and text out of queries sent to outside services (web searches, fetched URLs).
