---
name: touch-up-holes
description: Touches up the holes a review of a fix's diff raised, closing each at its root with every same-shaped instance and proving each fixed line by injecting a regression. Use when such a review has just listed holes, or when asked to "close the holes the review found". Not for the first fix of a defect.
---

# Touch up the holes a review of a fix raised

**Core rule: answer every raised hole once — fixed, or left with its reason — and close each at its root, never by bending a test, the request, or the code to get green.**

Why: a hole a fix created that is left for the next full review is raised there as a new finding, and the next fix creates the next hole. Close it right after the review of the fix, before the next full review.

## Pitfalls (read first)

- **Answer every hole, once.** Each raised hole and each claimed-closed hole the review found still open gets exactly one answer: fixed (what you fixed and how, and the files whose content you changed) or left (why; if it is a false positive, where in the real thing you can show it is wrong). Leave none out.
- **Do not bend anything to get green.** Do none of: loosening a test, fitting an expected value to the implementation, reinterpreting the request, adding a branch that passes only specific inputs. If the request, a test, and the code cannot all hold, do not fix that hole: leave it, and write the places that diverge (two or more, with lines), why both cannot hold at the same time, and which you judge to be right (the request, the test, the code, or unknown).
- **Stay inside the allowed paths.** A hole that needs a change outside what you may touch is not fixed: leave it and say why. What is marked as not to be touched beats a permitted path. What any item of the fix plan marks as not to be touched applies to every path you change, not only to that item's own paths; only a path that an agreement lifted from an item's not-to-touch list is free, and only under that item. Delete files that running tests produced.
- **Fix a departure from the plan as the plan's item says.** When the review raised a hole because the fix departs from an item of the approved fix plan, fix it the way that item says — not the way that seems better to you now. Answer it as compliance with that item.
- **Do not fix toward what an earlier decision took out.** Someone reading a stuck fix may have decided earlier which side gives way; such a decision can take a whole item of the fix plan, or one root-cause defect within an item, out of what must be fixed now. If a hole asks for a fix toward such an item or defect, leave it, with that decision as the reason.
- **Do not let through a conflict with the recorded policy on your own judgment.** Leave the hole and say which item of the policy it conflicts with. Do not rewrite the policy.

## Steps

Read every subsection for a first touch-up; for a second touch-up (of the holes a review of the first touch-up raised), also read "Second touch-up".

### How to fix

- **Close the root, and every instance of the same shape.** Start from the place the hole points to and search on your own for every other place of the same shape.
- **Think first of the shape that removes or merges, instead of adding.**
- **Prove each fixed line.** Inject a regression into the line you fixed, see the test turn red, then put it back.
- **Run the tests yourself.** Narrow down to the tests that cover the hole you fixed, run them, and return only after you have confirmed green.
- **Use clues, but answer everything.** A mapping from a hole to the plan item it came from tells you which item's scope and promises to read first; it does not change what you must answer.
- **Words of the tool that leaked in.** When the text the fix added carries internal words of the tool or process that made the change (its own labels, which the target's reader does not know), rephrase the added text so that the target's reader can follow it. Leaving it is not fixing it.

### Second touch-up

- Look for internal words in the lines the fix and the touch-up added together. They include words the first touch-up said it fixed and that still remain. Fix those too.
- "Fixed" is a claim that someone still checks one by one, including the rows that say fixed. Do not treat "fixed" as the end.

## Done when

- Every raised hole, and every claimed-closed hole the review found still open, has exactly one answer.
- Each fixed line was shown to turn a test red when broken, and was put back.
- The tests that cover each fixed hole ran green after your change.
- Nothing you changed lies outside the allowed paths or inside what is marked as not to be touched, and the files that running tests produced are deleted.
- No internal word of the tool is left in the text the fix and the touch-up added.

## How to report

One answer per hole, under the name the review gave it, copied without changing a character:

- **Fixed**: what you fixed and how; the files whose content you changed; the searches you ran, the tests you ran and their results, and the inputs you tried to break it with.
- **Left**: why. For a false positive, where in the real thing you can show it is wrong. For a hole that cannot hold without bending something, the places that diverge (two or more, with lines), why both cannot hold, and which you judge to be right. For a hole outside the allowed paths, an earlier decision, or the policy, the path, the decision, or the policy item that stops it.

## Example

Input: the review raised two holes. "retry-limit-copied" (copy): the fix wrote the retry limit as a new constant in a second module although one already exists. "guide-stale" (drift): a guide still describes the old retry behavior, but item 2 of the fix plan marks the guide as not to be touched.

Reply:
- "retry-limit-copied" — fixed: removed the new constant and used the existing one; a search for the same value found one more copy, removed too. Broke the shared constant, the covering test turned red, put it back; the covering tests are green.
- "guide-stale" — left: item 2 marks the guide as not to be touched, and that applies to every path changed, so closing this needs a change outside what may be touched.

## Works well with

- Rules for writing a fix: how to fix, evidence for fixes a test cannot show red-to-green, and what to keep.
- Rules that keep queries sent to outside services (web searches, fetched URLs) free of the target's names.
