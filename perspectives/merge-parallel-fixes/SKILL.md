---
name: merge-parallel-fixes
description: Reconciles a fix that was made in parallel with others and broke when merged on top of them (tests went red, or the text conflicted), by finding which premise of this fix the earlier fix broke, keeping the earlier fix intact, adding this fix's intent, and touching only the files this fix changed — or by saying plainly that the two cannot hold together. Use when parallel branches or worktrees are merged and tests go red, when resolving conflict markers between two fixes, or when asked to "make these two fixes work together", "resolve this merge without reverting the other fix".
---

# Make a parallel fix hold together with the fixes merged before it

**Core rule: keep the earlier fix, add this fix's intent, and touch only the files this fix changed. Never reach green by undoing the earlier fix or loosening a test.**

Fixes made in separate working trees are applied one after another. When this fix, applied after the earlier ones, turns tests red or does not apply as text, the job is to make both hold — not to choose one.

## Pitfalls (read first)

- **Understand before you edit.** First read this fix's diff, the red output, the tests it names, and the current content of the files both fixes changed. Find what the earlier fix changed and which premise of this fix it broke.
- **Do not win by removing, reverting, or weakening the earlier fix.** Its tests must stay green too.
- **Do not loosen tests.** Do not fit expectations to the implementation, skip, or remove tests. Being this fix's own test file is not a permission to change it.
- **Stay inside the files this fix changed** (plus any files you were explicitly allowed). Remove files that running the tests produced.
- **Leave no conflict marker.** Remove every marker line, and do not write a line that looks like one (such as a heading underline of the same length).

## How to reconcile

- In conflicted files, keep the side that is already in the working tree (the earlier fix) and add the intent of the side being applied (this fix).
- If a ruling already decided how to fix it, follow the ruling's text.
- Run the tests of both fixes and the tests the red output names yourself, and confirm green before you return.

## When it cannot hold

If, however you fix within the files you may touch, the earlier fix and this fix cannot both hold — or the test's expectation itself is wrong, or the way the problem was cut or planned is wrong — say so without changing anything (put back what you changed). Write why they cannot hold together and name the places (`<path>:<line>`). That goes to someone who rules on it.

## What to report

What you fixed and how, the tests you ran and their results, and every file whose content you changed (including files written by a command, with why).
