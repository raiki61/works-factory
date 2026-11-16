---
name: touch-up-holes
description: Touches up, within the same round, the holes a review of a fix's diff raised — closing each at its root together with every instance of the same shape, preferring to remove or merge over adding, proving each fixed line by injecting a regression and watching it turn red, and leaving a hole openly unfixed (with the diverging places and which side is right) rather than bending a test, the request, or the code to get green. Use right after a review of a fix's diff raised holes, or when asked to "touch up the review's findings", "close the holes this fix created", "fix what the diff review found".
---

# Touch up the holes a review of a fix raised

**Core rule: answer every raised hole once — fixed, or left with its reason — and close each at its root, never by bending a test, the request, or the code to get green.**

Why: a hole a fix created that is carried over to the next round is raised by the next whole review as a new finding, and the next fix creates the next hole. Close it within the same round.

## Pitfalls (read first)

- **Answer every hole, once.** Each raised hole and each claimed-closed hole the review found still open gets exactly one answer: fixed (what you fixed and how, and the files whose content you changed) or left (why; if it is a false positive, where in the real thing you can show it is wrong). Leave none out.
- **Do not bend anything to get green.** Do none of: loosening a test, fitting an expected value to the implementation, reinterpreting the request, adding a branch that passes only specific inputs. If the request, a test, and the code cannot all hold, do not fix that hole: leave it, and write the places that diverge (two or more, with lines), why both cannot hold at the same time, and which you judge to be right (the request, the test, the code, or unknown).
- **Stay inside the allowed paths.** A hole that needs a change outside what you may touch is not fixed: leave it and say why. What is marked as not to be touched beats a permitted path. Delete files that running tests produced.
- **Fix a departure from the plan as the plan's item says.** When the review raised a hole because the fix departs from an item of the approved fix plan, fix it the way that item says — not the way that seems better to you now. Answer it as compliance with that item.
- **Do not fix toward what a ruling took out.** A ruling is a decision made earlier, by someone reading a stuck fix, about which side gives way; it can take a whole item of the fix plan, or one root-cause defect (a unit) within an item, out of what must be fixed now. If a hole asks for a fix toward such an item or unit, leave it, with the ruling as the reason.
- **Do not let through a conflict with the recorded policy on your own judgment.** Leave the hole and say which item of the policy it conflicts with. Do not rewrite the policy.

## How to fix

- **Close the root, and every instance of the same shape.** Start from the place the hole points to and search on your own for every other place of the same shape.
- **Think first of the shape that removes or merges, instead of adding.**
- **Prove each fixed line.** Inject a regression into the line you fixed, see the test turn red, then put it back.
- **Run the tests yourself.** Narrow down to the tests that cover the hole you fixed, run them, and return only after you have confirmed green. Write the searches you ran, the tests you ran and their results, and the inputs you tried to break it with, in the answer for that hole.
- **Use clues, but answer everything.** A mapping from a hole to the plan item it came from tells you which item's scope and promises to read first; it does not change what you must answer.
- **Words of the tool that leaked in.** When the text the fix added carries internal words of the tool or process that made the change (its own labels, which the target's reader does not know), rephrase the added text so that the target's reader can follow it. Leaving it is not fixing it.

## Second touch-up

- After the first touch-up, a review of the touch-up-only diff checks one by one the holes you say you fixed.
- After the second touch-up, nothing reviews it again in this round: what you say you fixed is carried to the next round's judgment, which sorts it one by one, including the rows that say fixed. Do not treat "fixed" as the end.
- Internal words found in the lines of the fix and the touch-up together include words the first touch-up said it fixed and that still remain. Fix those too.

Works well with: a perspective of rules for writing a fix (how to fix, evidence for fixes a test cannot show red-to-green, what to keep), and a perspective that keeps queries sent to outside services (web searches, fetched URLs) free of the target's names.
