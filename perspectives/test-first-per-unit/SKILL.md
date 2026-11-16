---
name: test-first-per-unit
description: Fixes root-cause units one at a time as test, fix, refactor, making each new test fail on its own check for the expected reason and freezing it while fixing. Use when asked to "write the failing test first" for a set of defects. Not for adding tests that keep current behaviour.
---

# Fix each unit test-first: red, then green, then refactor

**Core rule: one unit at a time, test → fix → refactor. Red and green are what running the tests says, not what you say. If you can only get green by bending a test, the request, or the code, stop and declare the conflict.**

Words used below:

- **Unit**: one root-cause defect. Symptoms that come from the same cause are one unit, and fixing it means fixing every place of the same shape. How defects are cut into units is decided by the earlier judgment of the defect.
- **Judgment**: the finding of what the defect is, why, where it came from, and the check that finds and counts every place of its shape (a search pattern or a probe; below, "the check that counts the defect").
- **Plan**: the agreed fix plan, if there is one. For each item it names the scope that may be touched and the acceptance tests (tests decided beforehand, by name, that go from red to green to show the item is fixed) or existing tests to rewrite. Without a plan, the judgment is the source of what to fix.
- **Request**: what the person asked to be fixed.
- Red, green, refactor: the test fails; the test passes; tidy while staying green.

## Pitfalls (read first)

- **Red must be a failure of the test's own check.** A failure to load, build, or set up is not red, and a test that never ran is not red. A test that already passes or is skipped is not red.
- **Red for the expected reason.** Quote the failure text as the test output shows it, and say why it failed for the reason you meant (the feature is missing — not a typo). Never make up a quote.
- **The test is frozen while you fix and refactor.** Everything on the test side that you changed in the red step is frozen with it: expected output, test helpers, and test data, whatever their names or folders. If you notice an error in a test, do not fix it then; note it. If you cannot go on without changing it, declare the conflict.
- **Do not touch existing tests' bodies** beyond those you were told to rewrite. Imports, helpers, and new tests are fine. If you cannot go on without changing one, declare the conflict.
- **Do not touch later units or the direct units** while working on the current one (the direct units are fixed separately, after the test-first units), and do not revert or redo the fixes of earlier units.
- **Run the tests the way they were already run.** If the tests have been run before the fix in a known form, run them in that form (narrowed to what you need) instead of searching for environments or commands.
- **When a finding comes back after an earlier fix**, do not reuse the acceptance tests the earlier fix already took from red to green (they are frozen), even if the plan lists them for this unit; write a new test for the returned finding that fails on the current working tree.

## Steps

### 1. Sort the units

Sort every unit exactly once, without changing the working tree:

- **Test-first**: you can write, in the repository's test suite, a test that fails before the fix and passes after it.
- **Direct**: you cannot write such a test first (a fix only to documents, instructions, notes, settings, and so on). Give the reason.

If, while writing the test, you find a unit cannot have a test written first after all, send it to direct with the reason. But if the plan already decided its acceptance tests, do not: declare a conflict instead.

### 2. Red: write a test that reproduces the defect and fails now

- Write it so it does not fail at loading or building, and fails on the check inside the test.
- Only when you cannot do that because a name you are about to add does not exist yet, add a minimal stub outside the test file — shape only, returning a value that fails the check. The real implementation replaces it in the fix step.
- If the test itself is wrong, fix the test and run again.
- When the plan names acceptance tests or existing tests to rewrite for this unit, write or rewrite those, and make them fail with the current code. Treat the plan's description of how it should fail only as the intended way; if written as planned it does not fail, or fails differently, do not bend the test — declare the conflict.
- Tests that passed before must still pass.

### 3. Green: fix only the current unit

- Fix the current unit — every instance of the same shape of the defect — and nothing else.
- Do not change the frozen test files.
- Run the tests yourself and fix what remains red before you report.
- When the person gave a command that runs the whole test suite, make that command green too, not only the named tests.
- If there is something you want to tidy after green (duplication, names, code that became unneeded), declare a refactor and say why. Without a declaration (yours, or the plan item's), there is no refactor step.

### 4. Refactor: only what was declared

Tidy what you or the plan item declared while staying green, without changing the test files. If nothing is left to tidy, change nothing.

### Units fixed together

Units on the same plan item that share one approach are handled together with the current unit in every step: the red step makes all of the item's acceptance tests fail, and the green step makes them pass including those units' fixes.

### Declaring a conflict (do not bend to get green)

At any step, if the unit can only go green by bending a test, the request, or the code, declare a conflict instead. Name two or more places that disagree (`<path>:<line>` or a line range), say why both cannot hold at once, and say which side you think is right: the request, the test, the code, unknown, or the check that counts the defect (when that check also matches the lines after a correct fix, so the count does not drop even when fixed correctly; then copy into the declaration the correct lines it still matches, to show the check is what is wrong). Typical situations:

- the plan's description of the unit disagrees with the judgment of the defect;
- a test nobody named broke;
- the named test will not go red;
- the fix needs something outside the agreed scope;
- the check that counts the defect matches the fixed lines too;
- the fix needs context you were not given.

You stop fixing a declared unit; the working tree returns to where the unit started, and someone else rules on it.

## Done when

- Every unit is sorted exactly once, with a reason for each direct one.
- For each test-first unit, the new test failed on its own check for the expected reason, and the failure text is quoted from the test output.
- The tests you ran yourself are green after the fix — the named tests, the tests that passed before, and the whole-suite command if the person gave one — and the frozen test files did not change.
- A refactor was done only when declared, and left everything green.
- Or a conflict is declared for the unit instead.

## How to report

- The sorting: test-first or direct for each unit, with the reason for each direct one.
- For the red step: each named test, its failure text quoted as the output shows it, and why it failed for the reason you meant.
- For the green and refactor steps: what you fixed or tidied, any error you noticed in a frozen test, and whether you declare a refactor and why.
- For a conflict: the places that disagree, why both cannot hold, which side you think is right, and for the check that counts the defect, the correct lines it still matches.

## Example

Input: a unit "an empty line makes parsing raise instead of returning nothing". The plan names the acceptance test `test/parse_test::empty_line`.

Reply:

- Sorting: test-first.
- Red: `test/parse_test::empty_line` fails with "expected nothing, got error: unexpected end" — the handling of an empty line is missing, not a typo.
- Green: fixed `src/parse:20` and the same shape at `src/parse:55`; the named test and the tests that passed before are green.
- Refactor: none declared.

## Works well with

- A read-only ruling on a declared conflict between the test, the request, and the code.
- A view for showing that a fix closes the defect it targets.
