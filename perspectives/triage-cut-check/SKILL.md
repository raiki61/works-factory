---
name: triage-cut-check
description: Checks, as a read-only eye other than the judge's, how a judge cut a fix request into root-cause units — for each unit, whether fixing it really removes the symptom or it is only an appearance of another root, whether the facts its reason states are in the code, and whether its named place is the place to fix; and across units, duplicates, overlapping fixes, and fix order — without proposing fixes or removing units. Use after root-cause units are decided and before a fix plan is written, or when asked "check this triage", "are these really the root causes", "do these units overlap".
---

# Check a judge's cut into root-cause units

**Core rule: check the cut with an eye other than the judge's, and report only facts you saw in the code. A unit is a duty to fix; this check never reduces it.**

## Pitfalls (read first)

- **Read only.** Look into the code behind the evidence; do not change a single character of the working tree.
- **Do not write how to fix anything.** You only check how the units were cut; planning the fix is separate work, not yours.
- **Do not propose removing, adding, or relabelling units.** Even if a unit turns out not to be the root cause, that is a note for whoever plans and reports, not a reason to drop it.
- **Facts, not guesses.** Write each reason and piece of evidence as what you saw (path:line and what was there). If it is a guess, answer "unsure".
- **Use the web only when the code behind the evidence does not settle it.** Do not reopen the sources of the judge's precedents.

## For each unit

1. **Root cause**: if this unit is fixed, does the symptom in the request go away? Or is it the result — one appearance of the symptom — of another unit, or of a place no unit covers? Answer root, not root, or unsure. If not root, name the real root (its path and name) and why it can be called the root. Overlaps between units are a separate check.
2. **Evidence**: did you confirm in the code the facts the judgment's reason states? Say where you checked and what you saw.
3. **Place**: are the path and name the unit names the place to fix? If not, give the right place.

## Across units

Look only at how the units relate:

- **Duplicates**: other appearances of the same root, closed by the same fix.
- **Relations**, split in two by place:
  - **same**: they change the same line or the same block, or one fix changes a premise of the other (a name, a type, a way of calling);
  - **apart**: they only touch different places of the same file or the same test file (another function, another class, a test added to another class) and the fixes do not overlap. Do not call them "same" only because the file is the same.
- **Order**: one cannot be fixed or tested until the other is fixed first.

If there are none, say what you looked at and why there are none.

Works well with: a perspective that keeps web searches and other queries to outside services free of the reviewed repository's own names and text.
