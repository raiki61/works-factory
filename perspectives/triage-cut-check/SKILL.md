---
name: triage-cut-check
description: "Checks, as a second read-only eye, how a judge already cut a fix request into root-cause units: whether each unit's fix removes the symptom, whether its stated facts are in the code, and overlaps across units. Use when the units are set and planning has not begun, or when asked \"is this cut into units right\". Not for making the cut from raw findings."
---

# Check a judge's cut into root-cause units

**Core rule: check the cut with an eye other than the judge's, and report only facts you saw in the code. A unit is a duty to fix; this check never reduces it.**

Here a unit is one item of the judge's cut: a defect the judge decided to fix with one fix, with its label, its reason, and the place (path and name) it names.

## Pitfalls (read first)

- **Read only.** Look into the code behind the evidence; do not change a single character of the working tree.
- **Do not write how to fix anything.** You only check how the units were cut; planning the fix is separate work, not yours.
- **Do not propose removing, adding, or relabelling units.** Even if a unit turns out not to be the root cause, that is a note for whoever plans and reports, not a reason to drop it.
- **Facts, not guesses.** Write each reason and piece of evidence as what you saw (path:line and what was there). If it is a guess, answer "unsure".
- **Use the web only when the code behind the evidence does not settle it.** Do not reopen the precedents the judge cited as grounds (the sources on how others solve the same problem).

## Steps

Read "For each unit" when you check one unit and "Across units" when you check how the units relate; the pitfalls apply to both.

### For each unit

1. **Root cause**: if this unit is fixed, does the symptom in the request go away? Or is it the result — one appearance of the symptom — of another unit, or of a place no unit covers? Answer root, not root, or unsure. If not root, name the real root (its path and name) and why it can be called the root. Overlaps between units are a separate check.
2. **Evidence**: did you confirm in the code the facts the judgment's reason states? Say where you checked and what you saw.
3. **Place**: are the path and name the unit names the place to fix? If not, give the right place.

### Across units

Look only at how the units relate:

- **Duplicates**: other appearances of the same root, closed by the same fix.
- **Relations**, split in two by place:
  - **same**: they change the same line or the same stretch of code, or one fix changes a premise of the other (a name, a type, a way of calling);
  - **apart**: they only touch different places of the same file or the same test file (another function, another class, a test added to another class) and the fixes do not overlap. Do not call them "same" only because the file is the same.
- **Order**: one cannot be fixed or tested until the other is fixed first.

If there are none, say what you looked at and why there are none.

## Done when

- Each unit you check has an answer on root cause, evidence, and place, each written as what you saw (path:line and what was there), or "unsure".
- For the check across units, duplicates, relations, and order are each listed, or you said what you looked at and why there are none.
- You wrote no fix and proposed no removal, addition, or relabelling of a unit.

## How to report

- For each unit: root, not root, or unsure, and for not root the real root (path and name) and why; whether the evidence was found, where you checked and what you saw; whether the place is right, and if not the right place.
- Across units: the duplicates, the relations each marked same or apart, and the order; or what you looked at and why there are none.

## Example

Input: two units. Unit 1: a function returns the total without the last item. Unit 2: the summary page shows a wrong total.

Reply:
- Unit 2: not root. The page shows the value unit 1's function returns, unchanged (its path:line); the real root is that function.
- Evidence and place of unit 1: confirmed (the loop's end condition, path:line); the place is right.
- Across units: order — unit 1 first, because unit 2 cannot be tested before it is fixed.
- Unit 2 stays a unit; that it is not root is a note for whoever plans the fix.

## Works well with

- A perspective that keeps web searches and other queries to outside services free of the reviewed repository's own names and text.
