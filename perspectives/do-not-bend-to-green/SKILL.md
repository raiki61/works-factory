---
name: do-not-bend-to-green
description: Keeps whoever is fixing from loosening a test, refitting an expectation, reinterpreting the request, or leaving the agreed scope just to get green, and has them declare the contradiction instead. Use when, in the middle of a fix, it is tempting to "just tweak the test so it passes". Not for deciding, as a separate eye, which side of a declared contradiction gives way.
---

# Do not bend anything to get green

**Core rule: rather than bend a test, the request, or the code to get green, declare the conflict. Do not count that defect as fixed; keep fixing the others.**

## Pitfalls (read first)

- **Do not loosen a test, fit an expectation to the implementation, reinterpret the request, or add a branch that lets only a particular input through.**
- **Do not remove, skip, or loosen existing tests.** If no test catches a defect you fixed, you may add one. An existing test your change breaks and that does not recover when you fix it is declared, not loosened.
- **Do not change things outside the agreed scope silently.** Ask first; if it is allowed, go on fixing.
- **Do not let through on your own judgment anything that goes against the person's policy** or only holds if the policy changes. That is the person's decision. (The policy document is the person's written policy that the fix must follow; a defect you must fix is one the diagnosis or plan marks to fix now, and the others are outside what you must fix.) For a defect you must fix: if a fix that stays within the policy closes it, put that fix in; if none does, do not count it as fixed, and declare it with the line of the policy document among the places. For a defect outside what you must fix, say which rule of the policy it collides with. Do not rewrite the policy document.
- **A doubt is not a conflict.** If only a doubt remains and both sides can hold, fix as asked, and record the doubt.

## Steps

Read "When two cannot hold at once" when a test, the request, and the code disagree, and "Tests and scope" when a test or a path outside the agreed scope seems to need changing; the other subsections apply throughout.

### When two cannot hold at once

When you find that two of the test's expectation, the request (the diagnosis's original text and the person's request), and the current code cannot hold at the same time, declare only that defect with:

- **Between**: two or more places that disagree, each as a path and line (or line range).
- **Why both cannot hold**: in sentences.
- **Which is right**: one of the request, the test, the code, or unknown — or, instead, name the counting query as the side that is wrong. Name the counting query when the query that counts the defect (the search that counts how many instances of the defect remain, used to check the fix closed them all) also hits the correct form after the fix: the fix is right and the query miscounts. Then copy, and attach, the lines of correct code after the fix that the query still hits. The same holds for a population query (a search that counts every thing to fix rather than the defects) that also hits things already correct: copy and attach the lines of those correct things.
- **What happened**: the agreed requirement disagrees with the diagnosis, the request, or conditions the person answered; an existing test that no one named breaks or can only be removed; a planned acceptance test does not go red as planned, goes red another way, or cannot be written first; it cannot go green without touching something outside the scope, or the count with the counting query does not close; the counting query hits the fixed form; the policy, the request's intent, or which side is right cannot be decided from the materials; or a test added to pin the current behavior fails on the current version (the current code may be wrong; leave the defect unfixed).

Name only places that exist. What only a person can settle — a fix that needs a policy change, a request whose intent the materials do not decide, a case where you cannot tell which of test, request, and code is right — goes here, as "unknown", never into an objection to the diagnosis.

### The agreed requirement and the background

- **The agreed requirement (the item of the approved plan you are fixing) is the only source of what to fix and how.** The diagnosis (the earlier analysis that named the defects, their root, and the query that counts them) is background: read it to look up the shape of the defect and where it came from. If the two disagree, the requirement wins; fix as it says, without reinterpreting it to fit the diagnosis. Its background section is reference only.
- **If you think the requirement itself is wrong, do not reinterpret it; declare it**, with its line and the line of the diagnosis or request that disagrees.
- **The conditions a person answered before the fix win over the requirement.** A condition is a scope to let through; do not cut beyond it. If the requirement goes beyond a condition, fix as the condition says and declare the part beyond.
- **Where there is no agreed requirement**, the diagnosis is the source; read it all first.
- **A decision made on an earlier declaration wins over the requirement within the place the decision names**; outside it, the requirement stands.

### Tests and scope

- **Rewrite only the existing tests the requirement names to rewrite**, each to the expectation it names. That is to rebind a behavior the request changes, not to fit an expectation to the implementation. A rewrite whose limit (the bound on which test and which part of it may change) could not be looked up is not allowed. To rewrite any other existing test, or to add a new test the plan does not name, ask first, as for a path outside the scope below.
- **Acceptance tests decided beforehand** bind the written behavior through the written real route and go red in the written way.
- **Tests that were already broken before the fix** and relate to your fix may be fixed along with it so that they test what they were meant to test; do not weaken or remove what they check. Say that you fixed them.
- **Outside the agreed paths, or on a path explicitly excluded**: before changing it, ask the side that owns the plan, saying what you tried within the scope, why it cannot be fixed within the scope (how far you got and what you hit), and the files and lines that ground it — whoever answers has not seen your work, so write it so they can decide from what you wrote alone. For a path the plan explicitly excluded, give the plan's reason for excluding it and say why that reason does not hold for this fix. If allowed, add only what was allowed. If denied, fix within the scope, and declare only when the request cannot be met inside it and your view and the plan owner's view of what the change should do differ. If deferred, say what you did not fix and why. If you cannot ask, do not change it; declare it. Do not ask to rewrite tests to fit expectations to the implementation.
- **Do not let the requirement's narrower scope silently narrow the fix.** If closing the defect needs something outside the scope, ask, or declare.

### What goes to a person

Things the person checks after you fix them — leaving a disagreement with the target repository's own decision records (different from a conflict with the person's policy, which is declared), or letting through something you know breaks — are written, with the reason and the place, where the person reads what they must decide (for example, the part of your report addressed to the person). Writing "hand to a person" anywhere else does not reach the person.

## Done when

- No test was loosened, skipped, or removed, no expectation was fitted to the implementation, the request was not reinterpreted, and no branch lets only one input through.
- Every defect where two sides cannot hold is declared with places that exist, and is not counted as fixed.
- Nothing outside the agreed scope, and no test beyond those named, was changed without asking first and being allowed.
- What goes against the person's policy is declared, not let through.
- Doubts that are not conflicts are recorded, and those defects are fixed as asked.

## How to report

For each declared defect: between (the places), why both cannot hold, which is right, and what happened. Then: the scope questions you asked and their answers; the tests that were already broken and that you fixed along the way; and, written where the person reads it, what the person checks after the fix (with reason and place). The defects you fixed are reported as usual.

## Example

Input: the request asks for a new error message; an existing test, not named for rewriting, expects the old message and fails after the fix.

Reply:

- Declared, not counted as fixed.
- Between: the test's expected message at its line, and the request's line that gives the new message.
- Why both cannot hold: the test asserts the old text; the request replaces it.
- Which is right: the request. What happened: an existing test that no one named breaks.
- The test was not changed.

## Works well with

- A way for someone who reads but does not change the code to decide each declared conflict: fix the code, fix a named part of the test, or hand it to a person.
