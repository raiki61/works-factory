---
name: fix-diff-review
description: Reviews only the diff one fix just made and finds the holes the fix itself created (copies, routes a new guard does not see, stale readers, dead paths, scope creep, loosened checks), then checks the holes the fixer claims to have closed. Use when a fix has just been written, or when asked to "review just this fix". Not for reviewing a plan before code exists, nor a whole pull request.
---

# Review the diff of a fix for the holes it created

**Core rule: read only the diff of this fix, and find the holes the fix itself newly created, right after the fix and before the next review of the whole change — not the holes that were there before.**

Why: when the holes a fix creates are found only by the next review of the whole change, the next fix creates the next hole (measured once: 8 of the findings of one review of the whole change were products of the fix before it). Looking right after the fix closes that loop before the next review of the whole change.

## Pitfalls (read first)

- **Read only.** Do not write or delete files and do not move the version-control state while you review.
- **Inspect the current state.** The thing under review is the state after the fix; the version from before the fix does not contain it. Quote from the current state.
- **The fixer's report is a claim, not evidence.** Check every claim against the diff and the current state.
- **The diff is a starting point, not a boundary.** Read the readers and callers of what changed as well.
- **Raise holes only in files that changed.** What you read outside them is evidence, not a place for a finding.
- **A finding from another review tool is not copied unchecked.** Check it against the diff and the current state; if it is right, raise it as your own hole and keep the name of the tool it came from, spelled exactly as that tool's result spells it. A tool that failed or was not run means nobody looked at its viewpoint; say so.
- **Do not raise a regression or an unchecked precedent as a hole of the fix diff, and do not use "policy" as a kind of its own here.** Those are kinds of the review before the fix; a regression after the fix is raised for a person to decide. A conflict with the recorded policy is still raised here, under the nearest of the kinds below (see "Policy").

## Steps

Read every subsection for the review of a fix; for the review of a touch-up of that fix, read "Reviewing a touch-up" first — it says which of the other subsections apply.

### The three points

Read what the diff added, and look only at these (plus the quality points below):

1. **Copy**: what the fix added copies, into another place, a rule, a type, a vocabulary, or a procedure that already has an authoritative home.
2. **Entrance**: a guard the fix added does not see another route into the same set, and that route stays open.
3. **Drift between declaration and implementation**: the readers of what the fix changed (instructions, rejection messages, documents, tests, docstrings) are left stale.

Two more kinds of hole may be raised: a **dead path** (something the fix added that nothing reaches) and **scope creep** (a change widened beyond what was asked).

**Protected files** (tests, fences, acceptance entrances of the target): if any changed, read whether the change loosens a check — deleting or weakening a test, rewriting an expectation, removing a fence or an acceptance check. If it does, it is a hole. A protected file that changed is also always listed for the person who decides on the change.

**Policy**: when a change conflicts with the recorded policy of the project, say in the hole which item it conflicts with. If no kind fits, treat it as drift, because the policy is also a promise to keep.

### Check the holes the fixer says it closed

Go through, one by one, every hole the fixer answered "closed" (or "fixed") to, and say for each whether the diff actually closed it, and why. Leave none out. A hole the diff did not close is answered here; you need not raise it again as a new hole. A hole the fixer chose to leave open is not checked here.

### Two verdicts: compliance first, then quality

Judge compliance first, then quality. Do not mix a compliance deviation into a quality hole.

1. **Compliance with the approved plan**: for each item of the plan, do not trust the fix report; read the diff and the current state and check whether the fix was made as the item says. Each deviation is one of:
   - **Missing**: something the item said to add, remove, or pass is not in the diff.
   - **Extra**: something outside the item (a file outside the scope, a feature nobody asked for) was added.
   - **Misunderstood**: the item was misread and fixed into another shape.
   - **Unverifiable**: the diff and the current state cannot confirm it; say what is missing.

   Tie each missing, extra, or misunderstood deviation to a hole at its place in the diff (extra is scope creep; the others are drift), so that whoever touches it up answers that hole. For a missing change in a file the fix did not touch, put the hole at the nearest changed file of that item; if the item has no changed file, it is unverifiable.
   Items, or root-cause defects within an item, that an earlier decision took out of what must be fixed now are not deviations; check only what remains. Paths that such a decision, or an agreement to widen an item's scope, added to the scope are not extra. Tests that an agreement merely allowed are a permission, not a duty, and are not missing.
   The verdict follows from the rows: fail if there is any missing, extra, or misunderstood row; otherwise unverifiable if there is an unverifiable row; pass if there are none. With no plan, compliance does not apply. Say what you read to judge.
2. **Quality**: in addition to the three points, look at whether the tests that were added go through the real path (they do not assert the return value of a mock, and do not lean on comparing wording), and at ease of maintenance. A hole in the shape or maintainability of a test is drift. Quality fails if any hole is not tied to a compliance deviation. Say what you looked at.

### Reviewing a touch-up

- **The review of a touch-up** reads only the diff of the touch-up (the fix's own lines are not in it), looks only at the same three points as the first review (with protected files and policy), and checks one by one the holes the touch-up says it fixed. It does not check the holes the touch-up said it leaves. It gives no compliance or quality verdict.
- **A hole you raised is not dropped silently.** If you are told its place or quote did not match, read the current state of the file again and quote it correctly.

## Done when

- Every hole sits in a changed file, with a quote that exists as it is in the current state.
- Every hole the fixer (or the touch-up) says it closed has its own answer: closed or not, and why.
- For the review of a fix, every missing, extra, or misunderstood deviation is tied to a hole, and both verdicts are the ones the rows decide.
- Where there is no hole or no deviation, you said what you read to be able to say so.
- No file and no version-control state changed while you reviewed.

## How to report

- **Each hole**: a unique name that calls it; its kind (copy, entrance, drift, dead path, scope creep); where — only the path of a changed file, exactly as the change lists it, with lines, function names, and "several places" put in the reason; a quote that exists as it is in the current state of that file (do not paraphrase, summarize, or abbreviate); why, in full; and, for a hole taken from another tool, that tool's name.
- **No hole**: what you read to be able to say so — the files, the readers, and the callers.
- **Each claimed-closed hole**: its name, closed or not, and why.
- **For the review of a fix**: the compliance verdict with its deviation rows (item, kind, the hole it is tied to, why) and what you read; the quality verdict and what you looked at.
- When a hole needs a decision from a person, write the question so that a first-time reader can answer it from the text alone.

## Example

Input: a fix added a check that rejects an empty name in the form that creates a user, and the fixer says it closed the hole "form-accepts-empty-name". The same file also has a bulk import that creates users and that the fix did not touch.

Reply:
- Hole "bulk-import-skips-empty-name-check" (entrance). Where: the changed file. Quote: the new check line, copied as it is. Why: the bulk import creates users by another route that never reaches the new check, so an empty name still gets in.
- Check "form-accepts-empty-name": closed — the form route now rejects an empty name.
- Compliance: pass — the one plan item (guard empty names in the form) is in the diff. Quality: fail — the entrance hole is not tied to a compliance deviation.

## Works well with

- A way of writing questions to a person so a first-time reader can decide from the text alone.
- A review that predicts holes before the change is written.
