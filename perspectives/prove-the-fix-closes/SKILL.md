---
name: prove-the-fix-closes
description: Proves that a fix closed the defect rather than claiming it — finding every place that shares the defect's invariant, injecting a regression at each place to see red and restoring it to see green, trying inputs that break the fix while keeping it, looking up with the machine what else the fix may break, counting what was closed against the whole population and saying out loud what is left, naming tests that fail before and pass after, and never reporting a check that was not run or failed as passed. Use after writing a fix and before saying it is done, especially for a behavior change that did not go through test-first steps, or when asked "prove the fix holds", "did you fix every place", "how do you know it is closed".
---

# Prove that a fix closes the defect

**Core rule: a fix is closed only where you saw it hold. "It went red when I removed the fix" is detection of absence, not evidence of completeness.**

## Pitfalls (read first)

- **Never write a check you did not run, or that failed, as passed.** A check not run is written as not run, with the reason; a failed check as failed, with what failed. Mark a red as seen only when you saw it.
- **Do not stop at "I tried one place and it was red".** Each place that shares the invariant is proved on its own, and each defect needs at least one red seen at one of its own places; a red seen at another defect's place does not count for this one.
- **Leaving something is not forbidden. Leaving it silently is.** If the places you proved do not reach the whole population, say what you leave and why you do not close it now.
- **Do not narrow the count to make it close.** If the query that counts the defect also hits the correct form after the fix, do not silence it by narrowing the query; raise that the query is wrong, with the correct lines it still hits.

## 1. Find every place that shares the invariant

For a fix to a check, a guard, or any behavior change that did not go through test-first steps, first list every place that shares the defect's invariant (the same path, the same rule, the same calling order). Use the query that found the defect's shape; if there is none, write the query that counts it. Fix them all.

## 2. Prove each place

For each place:

- **Mechanism**: the defect's mechanism, and the mechanism by which the fix closes it.
- **Red, then green**: inject a regression into that place, see the check go red; restore it, see it go green. Do this place by place.
- **Where**: the file and the line of the place as it was before the fix, and the lines you changed to fix it.
- For a structural fix (something moved), check with the machine (a search, a run) that the new place is actually used. For a wording fix, quote the real text after the change.

## 3. Try to break the fix while keeping it

Try inputs that would break the fix with the fix still in place, and record them and their results. If one breaks it, fix it before you submit. If none does, say what you tried; never "not tried".

## 4. Look up what the fix may break

Find with the machine — not by memory — the surfaces that share the same path, the same invariant, or the same calling order, and confirm they still work (run the checks, show the search results). If you let something through knowing it breaks, give the reason and one short sentence in plain words of what a person is being asked to accept: the reader has not seen the code, so no function, file, key, or role names; say it as the thing that changes.

## 5. Count against the population

Count before the fix and after it with the same query, in the same version the diagnosis read and in the current tree. What counts as closed is the places the fix actually changed, not the places you listed. If you believe the query misses targets or counts only one line at the root, you may rebuild it, but write the rebuilt query; if it is narrower than the original population, say why what it leaves out is left.

## 6. Tests that show the change

- Name the tests that show the behavior you changed: tests that fail on the version before the fix and pass on the fixed tree. A test that was already green shows nothing.
- A removal needs no such test when every removed name is gone from the tree — from callers, tests, and documents alike.
- Run only the tests the change reaches, narrowed by the test tool's own selection (by id or name). Run the whole suite once, just before answering, only when the project has no way to narrow. If red remains, fix it before returning. A test that was red before the fix too need not be chased.

## Before saying it is closed

State the result of the proof for the whole round: clean (and what you confirmed), something found, or not run (and why — that counts as not measured, never as passed). "Clean" without ever having seen red is not clean.
