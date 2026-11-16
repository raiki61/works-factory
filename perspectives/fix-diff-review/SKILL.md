---
name: fix-diff-review
description: Reviews only the diff that one fix just made, right after the fix and before the next round, and finds the holes the fix itself newly created — copies, unwatched entrances, readers left stale, dead paths, scope creep, loosened protected checks — then checks one by one the holes the fixer says it closed, and gives two verdicts in order: compliance with the approved plan first, then quality. Use right after a fix or a touch-up is written, or when asked to "review just this fix", "did this fix create new holes", "check the fix against the plan".
---

# Review the diff of a fix for the holes it created

**Core rule: read only the diff of this fix, and find the holes the fix itself newly created, within the same round — not the holes that were there before.**

Why: when the holes a fix creates are found only by the next whole review, the next fix creates the next hole (measured once: 8 of the findings of one round were products of the previous round's fix). Looking right after the fix closes that loop inside the round.

## Pitfalls (read first)

- **Read only.** Do not write or delete files and do not move the version-control state while you review.
- **Inspect the current state.** The thing under review is the state after the fix; the version from before the fix does not contain it. Quote from the current state.
- **The fixer's report is a claim, not evidence.** Check every claim against the diff and the current state.
- **The diff is a starting point, not a boundary.** Read the readers and callers of what changed as well.
- **Raise holes only in files that changed.** What you read outside them is evidence, not a place for a finding.
- **A finding from another review tool is not copied unchecked.** Check it against the diff and the current state; if it is right, raise it as your own hole and keep the name of the tool it came from. A tool that failed or was not routed means nobody looked at its viewpoint; say so.
- **Do not raise regressions, policy questions, or unchecked precedents here** as holes of the fix diff. Those belong to the review before the fix; a regression after the fix goes to a person.

## The three points

Read what the diff added, and look only at these (plus the quality points below):

1. **Copy**: what the fix added copies, into another place, a rule, a type, a vocabulary, or a procedure that already has an authoritative home.
2. **Entrance**: a guard the fix added does not see another route into the same set, and that route stays open.
3. **Drift between declaration and implementation**: the readers of what the fix changed (instructions, rejection messages, documents, tests, docstrings) are left stale.

Two more kinds of hole may be raised: a **dead path** (something the fix added that nothing reaches) and **scope creep** (a change widened beyond what was asked).

**Protected files** (tests, fences, acceptance entrances of the target): if any changed, read whether the change loosens a check — deleting or weakening a test, rewriting an expectation, removing a fence or an acceptance check. If it does, it is a hole. A protected file that changed should also always be shown to the person who approves at the end.

**Policy**: when a change conflicts with the recorded policy, say in the hole which item it conflicts with. If no kind fits, treat it as drift, because the policy is also a promise to keep.

## How to write a hole

- **A unique name** that calls this hole.
- **Where**: only the path of a changed file, exactly as the change lists it. Put lines, function names, and "several places" in the reason.
- **Quote**: a string that exists as it is in the current state of that file. Do not paraphrase, summarize, or abbreviate.
- **Why**: the reason, in full.
- If there is no hole, say what you read to be able to say so: the files, the readers, and the callers.

## Check the holes the fixer says it closed

Go through, one by one, every hole the fixer answered "closed" (or "fixed") to, and say for each whether the diff actually closed it, and why. Leave none out. A hole the fixer chose to leave open is not checked here.

## Two verdicts: compliance first, then quality

Judge compliance first, then quality. Do not mix a compliance deviation into a quality hole.

1. **Compliance with the approved plan**: for each item of the plan, do not trust the fix report; read the diff and the current state and check whether the fix was made as the item says. Each deviation is one of:
   - **Missing**: something the item said to add, remove, or pass is not in the diff.
   - **Extra**: something outside the item (a file outside the scope, a feature nobody asked for) was added.
   - **Misunderstood**: the item was misread and fixed into another shape.
   - **Unverifiable**: the diff and the current state cannot confirm it; say what is missing.

   Tie each missing, extra, or misunderstood deviation to a hole at its place in the diff (extra is scope creep; the others are drift), so that whoever touches it up answers that hole. For a missing change in a file the fix did not touch, put the hole at the nearest changed file of that item; if the item has no changed file, it is unverifiable.
   Items or units that a ruling took out of the duty to fix are not deviations; check only what remains. Paths a ruling or an agreed scope widening added are not extra. Tests that an agreement merely allowed are a permission, not a duty, and are not missing.
   The verdict follows from the rows: fail if there is any missing, extra, or misunderstood row; otherwise unverifiable if there is an unverifiable row; pass if there are none. With no plan, compliance does not apply. Say what you read to judge.
2. **Quality**: in addition to the three points, look at whether the tests that were added go through the real path (they do not assert the return value of a mock, and do not lean on comparing wording), and at ease of maintenance. A hole in the shape or maintainability of a test is drift. Quality fails if any hole is not tied to a compliance deviation. Say what you looked at.

## Second and later passes

- **A rejected finding is not dropped silently.** If its place or quote did not match, read the current state of the file again and quote it correctly.
- **The review of a touch-up** reads only the diff of the touch-up (the fix's own lines are not in it), looks only at the same three points as the first review, and checks one by one the holes the touch-up says it fixed. It does not check the holes the touch-up said it leaves.
- **There is no third review.** What is fixed after the second review is not reviewed again in this round; it is carried to the next round's judgment, which sorts it one by one, including the rows that say fixed.

Works well with: a perspective that writes questions to a person so a first-time reader can decide from the text alone, and a perspective that predicts holes before the change is written.
