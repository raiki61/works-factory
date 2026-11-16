---
name: grow-review-checklist
description: Maintains a list of review points as a regression asset grown from escaped defects, adding only points for a recurring class and pruning points that never fire. Use when a defect slipped past review, or when asked "what check would have caught this". Not for applying an existing checklist to a change.
---

# Grow a review checklist from incidents

**Core rule: the list of review points is a regression asset grown from incidents, not a complete enumeration. Include the procedure that keeps it from diverging.**

## Pitfalls (read first)

- **Do not add points by principle or pattern name** ("does it follow the single-responsibility principle", "is it the right design pattern"). Such points (1) cannot be refuted (an "it violates the principle" claim turns into an endless dispute, and worsens the known weakness that there is no path to correct an over-strict grader); (2) work only toward adding abstraction ("it violates the open-closed principle, so add a strategy" findings pile up, against the judgment that reduces lines and abstractions). Add a principle's working part only after **translating it into a question that reading the imports settles** (dependency inversion and interface segregation become "who owns the abstraction"; single responsibility becomes "do details leak inward"). Do not add a principle you cannot translate.
- **Do not admit or keep a point because its prose is persuasive.** Decide by the red and green of a retest (does it catch the miss or not). This applies the rule "run rather than read" to the review points themselves.
- **When a new point did not fire, you may rebuild the teaching material only when the material has a bug in its problem setting** (something the judgment needs was missing from it). If you cannot write that reason in one sentence, do not rebuild: rebuilding without it degenerates into "change the problem until it fires", and the admission test itself becomes always true. Record how many times you rebuilt and why.

## Steps

Read "After an escape" when a review missed something, and "Prune and admit" and "Audit the five questions" when adding or pruning points; "Add only by class" applies to both.

### After an escape

When a finding that slipped past an earlier review is found later (by a later review, by a production incident), each time decide and reflect in the list:

1. which point would have caught it;
2. whether it is a recurring class or a one-off;
3. whether merging into an existing point, adding a new one, or dropping it is right.

### Add only by class

Add not a copy of an individual incident but a class bundled so that its recurrence mechanism can be said in one sentence. Do not add a one-off that cannot be bundled.

### Prune and admit

- Merge or delete points that never fire in real reviews and points that overlap others. A swollen list thins attention per point and actually lowers detection.
- Before adding a new point, measure whether it fires on its own: give the past real miss it was supposed to catch to a grader that holds only that lens, with the context (feature name, purpose, the right answer) hidden. If it does not fire, do not add it.
- After admission, prune by the firing record in real reviews.

### Audit the five questions

Tag each section with the basic review questions it owns, and track that every question has an owning section:

1. Does it work correctly?
2. Is it the standard way in this field?
3. Is the cleanup clean, without leaks?
4. Is it good to use, read, and operate?
5. What did it break where no one looks?

A question whose owner disappears through pruning or merging becomes a whole class of misses. (Seen once: the absence of an owner for question 4 actually caused a chain of misses — the loss of the inner development loop (the quick edit-and-check cycle a developer runs locally), unsuitable default values, and procedure documents swelling with notes.)

## Done when

- For each escape, the three questions are decided and reflected in the list.
- Every point added is a class whose recurrence mechanism fits in one sentence, and it fired on the old miss for a grader holding only that lens.
- Every one of the five questions still has an owning section.

## How to report

For an escape: the point that would have caught it, recurring class or one-off, and the decision (merge, add, or drop). For a point added: its one-sentence recurrence mechanism, whether it fired in the admission test, and how many times the material was rebuilt and why. Name any of the five questions left without an owner.

## Example

Input: a later review found that a change's new in-memory cache never dropped entries; the first review had missed it.

Reply: Would have caught it: none of the current points. Class: recurring — "state added without a bound or expiry grows without limit". Decision: add, as a question the code settles ("does every added store have a bound or expiry?"). Admission test: a grader holding only this point, given the old diff with the feature name hidden, flagged it; material rebuilt 0 times. Owner: question 3.

## Works well with

- A stance for a reader given no context, for the grader in the admission test.
