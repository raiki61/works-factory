---
name: do-not-bend-to-green
description: Keeps a fixer from bending a test, the request, the code, or the scope to get green — when two of them cannot hold at once, declaring that one defect with the places that disagree instead of loosening a test, fitting an expectation to the implementation, reinterpreting the request, or adding a branch for one input; reading the agreed requirement as the source and the background as reference; consulting before touching anything outside the agreed scope; and handing to a person only what the materials cannot decide or what crosses their policy. Use while fixing, when a test and the request seem to disagree, when a fix seems to need files outside the agreed scope, when tempted to "just adjust the test", or when asked "can we change the test to pass".
---

# Do not bend anything to get green

**Core rule: rather than bend a test, the request, or the code to get green, declare the conflict. Do not count that defect as fixed; keep fixing the others.**

## Pitfalls (read first)

- **Do not loosen a test, fit an expectation to the implementation, reinterpret the request, or add a branch that lets only a particular input through.**
- **Do not remove, skip, or loosen existing tests.** If no test catches a defect you fixed, you may add one. An existing test your change breaks and that does not recover when you fix it is declared, not loosened.
- **Do not change things outside the agreed scope silently.** Ask first; if it is allowed, go on fixing.
- **Do not let through on your own judgment anything that goes against the person's policy** or only holds if the policy changes. That is the person's decision. Do not rewrite the policy document.
- **A doubt is not a conflict.** If only a doubt remains and both sides can hold, fix as asked, and record the doubt.

## When two cannot hold at once

When you find that two of the test's expectation, the request (the diagnosis's original text and the person's request), and the current code cannot hold at the same time, declare only that defect with:

- **Between**: two or more places that disagree, each as a path and line (or line range).
- **Why both cannot hold**: in sentences.
- **Which is right**: the request, the test, the code, unknown — or the counting query itself, when the query that counts the defect also hits the correct form after the fix (then copy the lines of correct code, after the fix, that the query still hits; the same holds for a population query that hits things already correct).
- **What happened**: the agreed requirement disagrees with the diagnosis, the request, or conditions the person answered; an existing test that no one named breaks or can only be removed; a planned acceptance test does not go red as planned, goes red another way, or cannot be written first; it cannot go green without touching something outside the scope, or the recount does not close; the counting query hits the fixed form; the policy, the request's intent, or which side is right cannot be decided from the materials; or a test added to pin the current behavior fails on the current version (the current code may be wrong; leave the defect parked).

Name only places that exist. What only a person can settle — a fix that needs a policy change, a request whose intent the materials do not decide, a case where you cannot tell which of test, request, and code is right — goes here, as "unknown", never into an objection to the diagnosis.

## The agreed requirement and the background

- **The agreed requirement (the item of the approved plan you are fixing) is the only source of what to fix and how.** The diagnosis (the earlier analysis that named the defects, their root, and the query that counts them) is background: read it to look up the shape of the defect and where it came from. If the two disagree, the requirement wins; fix as it says, without reinterpreting it to fit the diagnosis. Its background section is reference only.
- **If you think the requirement itself is wrong, do not reinterpret it; declare it**, with its line and the line of the diagnosis or request that disagrees.
- **The conditions a person answered before the fix win over the requirement.** A condition is a scope to let through; do not cut beyond it. If the requirement goes beyond a condition, fix as the condition says and declare the part beyond.
- **Where there is no agreed requirement**, the diagnosis is the source; read it all first.
- **A ruling on an earlier declaration wins over the requirement within the place the ruling names**; outside it, the requirement stands.

## Tests and scope

- **Rewrite only the existing tests the requirement names to rewrite**, each to the expectation it names. That is to rebind a behavior the request changes, not to fit an expectation to the implementation. A rewrite whose limit could not be looked up is not allowed.
- **Acceptance tests decided beforehand** bind the written behavior through the written real route and go red in the written way.
- **Tests that were already broken before the fix** and relate to your fix may be fixed along with it so that they test what they were meant to test; do not weaken or remove what they check. Say that you fixed them.
- **Outside the agreed paths, or on a path explicitly excluded**: before changing it, ask the side that owns the plan, saying what you tried within the scope, why it cannot be fixed within the scope (how far you got and what you hit), and the files and lines that ground it — that side starts fresh and learns your work only from that. For an excluded path, say why the reason for the exclusion does not hold for this fix. If allowed, add only what was allowed. If denied, fix within the scope, and declare only when the request cannot be met inside it and the views of the specification are split. If deferred, say what you did not fix and why. If you cannot ask, do not change it; declare it. Do not ask to rewrite tests to fit expectations to the implementation.
- **Do not let the requirement's narrower scope silently narrow the fix.** If closing the defect needs something outside the scope, ask, or declare.

## What goes to a person

Things the person checks after you fix them — leaving a disagreement with the target repository's own decision records (different from a conflict with the person's policy, which is declared), or letting through something you know breaks — are written, with the reason and the place, in the list of what the person decides (the part of the report shown to the person). Writing "hand to a person" anywhere else does not reach the person.
