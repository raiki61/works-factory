---
name: run-the-changed-path
description: Actually runs, once, the path a change touches that users can see or that crosses a seam with the outside, and records the real values that passed through it — not a test turning green — so that defects that appear only when the code runs (runtime-specific behaviour, values altered by a middle layer, rendering) are seen; when the path cannot be run, says why and what a person must run and look at. Use after a change to a user-visible path or an outside seam and before accepting it, or when asked "did anyone actually run this", "show me what really comes out", "observe the main path".
---

# Run the changed path once and observe what flows through it

**Core rule: do not treat a path you did not run as verified. Run it once, the same way it runs in production, and write down the values you saw.**

Every other way of reviewing reads the diff. Defects that only appear when the code runs — behaviour specific to the runtime environment, values altered by a middle layer, rendering — do not appear however many times the diff is read. What you observe is the real thing that flowed through the same path as in production, not a test turning green.

## Pitfalls (read first)

- **Applies when the change touches a path users can see, or a seam with the outside.**
- **A green test is not an observation.** Record the value that actually passed through the path.
- **"Observed" needs at least one observation.** Do not report "found something" or "all clean" without at least one path you ran and the value you saw on it.
- **Do not break the real working tree.** Make any copy you need for running in a fresh temporary directory outside it.
- **When you cannot run it, do not pretend.** If there is no environment, no permission, or it needs real hardware, say so: why it cannot be run, and what a person has to run and look at. A person decides whether there is really no way.

## How to report

For each path you ran: the path, and the value you observed on it. Or, if you could not run it: why, and what a person must run and look at.

Works well with (optional; this file does not need it): a set of rules that keeps the reviewed repository's own names and text out of queries sent to outside services (web searches, fetched URLs).
