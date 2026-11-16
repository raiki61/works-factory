---
name: merge-parallel-fixes
description: Reconciles a fix made in parallel that broke when merged on top of others, by finding which premise the earlier fix broke, keeping the earlier fix intact, and touching only this fix's files. Use when parallel branches conflict, or when "tests went red after merging both branches". Not for checking open pull requests for overlap before anything is merged.
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

## Steps

The subsections apply both to a first merge and to a merge retried after someone ruled how to fix the clash; the retried case adds one rule in "How to reconcile".

### How to reconcile

- In conflicted files, keep the side that is already in the working tree (the earlier fix) and add the intent of the side being applied (this fix).
- If someone has already ruled how to fix the clash, follow the text of that ruling.
- Run the tests of both fixes and the tests the red output names yourself, and confirm green before you return.

### When it cannot hold

If, however you fix within the files you may touch, the earlier fix and this fix cannot both hold — or the test's expectation itself is wrong, or the way the problem was cut or planned is wrong — say so without changing anything (put back what you changed).

## Done when

- The tests of both fixes and the tests the red output names are green, run by you.
- The earlier fix is intact, and no test was loosened.
- You changed only the files this fix changed (plus any you were explicitly allowed), no conflict marker or marker-like line is left, and files produced by running the tests are removed.
- Or, when the two cannot hold, everything you changed is put back.

## How to report

What you fixed and how, the tests you ran and their results, and every file whose content you changed (including files written by a command, with why). When the two cannot hold, write why they cannot hold together and name the places (`<path>:<line>`).

## Example

Input: an earlier fix made `load` return an empty list instead of nothing for a missing file. This fix, applied after it, adds a caller that checks for nothing, and `test/report_test:12` goes red.

Reply:

- What broke: this fix assumed `load` returns nothing for a missing file; the earlier fix changed that.
- Fix: the new caller at `src/report:30` now checks for an empty list. The earlier fix is unchanged.
- Tests run: the tests of both fixes and `test/report_test:12` — all green.
- Files changed: `src/report`.

## Works well with

- A read-only view that rules which side gives way when two fixes cannot be made to hold together.
