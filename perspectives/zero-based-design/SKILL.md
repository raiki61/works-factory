---
name: zero-based-design
description: Designs the ideal solution from the original purpose and the measured constraints alone, without seeing the fix plan, the implementation, the history of how it was judged, or the diff — first doubting that the problem exists at all, then covering the everyday flows of the people the purpose serves, and listing the design as numbered elements of what it adds and removes so that a plan can be compared against it. Use when a plan or a change should be checked against an independent design, or when asked to "design this from scratch", "what would the ideal look like ignoring the current plan", "does this problem even exist".
---

# Design from the purpose alone, before seeing the plan

**Core rule: start from nothing but the purpose and the measured constraints — and before designing, doubt that the question exists.**

Why: a design made after reading the plan, the code, or the history agrees with them. A design made from the purpose alone is a second input that the plan can be compared with, and it catches the case where the whole plan answers a question that did not need asking.

## Pitfalls (read first)

- **You inherit nothing.** Not the fix plan, not the history of the judgment, not the implementation, not the cumulative diff, not the points already settled. What you are given is the original purpose, the measured constraints, the premises a person set, and the person's policy (when there is one).
- **A hypothesis is not a constraint.** A constraint marked as a hypothesis is not taken as given.
- **An unchecked judgment is not grounds.** An earlier judgment may have said the purpose has to be cut down ("this part of the purpose cannot be met, so drop it"). If that judgment has not passed its own check and nobody has recounted the grounds for cutting, do not use it as a reason to design for less than the whole purpose.
- **The change under review does not prove itself.** Lines that the change under review itself added are not grounds for "already met by an existing mechanism"; judge whether the question stands by the state before that change.
- **Do not stop at one launch of the deliverable.** A design that only works the first time is not a design.

## 1. Doubt that the question exists

Before designing, ask:

- Does the problem this change solves exist?
- Is it already met trivially by an existing mechanism? (For example, if one deploy is one repository, the repository itself is the identifier, and the question of recording it separately does not arise.)
- Is the work stepping into implementation while the requirement is still undecided?

If the question does not exist, is met trivially, or rests on an undecided requirement, do not design. Give the grounds instead. When the grounds name something real, point to it exactly (a path and a line, or a line range) in the repository as it was when the request was made (the commit the request is based on), so that it can be checked. An answer that the question does not exist is handled apart from an answer that the design must be redone: before it reaches a person, a separate reviewer recounts these grounds.

## 2. If the question stands, design

- Write the ideal solution, designed independently.
- **Include the flows the people the purpose serves run every day** — iterative development, operation, teardown — not only the first launch.
- Where the design departs from the general structure of this kind of system, it needs a ground just as a plan does.
- Return only the design. Comparing it with the plan and settling the verdict is a separate role's job.

## 3. List the design as elements

List the design's elements, one for each unit of what the design adds or removes, numbered D1, D2, D3, … in order. For each, what it adds and what it removes (empty if nothing). Another reader will point at a plan's rows by these numbers, so the elements must not disagree with the design text.

## How to answer

- Whether the question stands, and the reason — never empty.
- When it does not stand: the grounds, with an exact place for anything real you name.
- When it stands: the design and its elements.

Works well with: a perspective that judges blind from only what it was given, one that states the grounds for departing from the general structure of a system, and one that pre-reviews a plan against such a design.
