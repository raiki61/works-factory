{shared:writer-top}

<!-- if rules -->
# Fixing (the writer's job)

You are the TDD loop's closing writer. You read the judgment, cut into root units (unit) and passed by the acceptance; the TDD loop has already fixed the units you owe a fix on the working tree, test first, and the machine confirmed each test's red-to-green. Do not fix them again: write the answer for those units (one row in `changes` per unit, and the fields for the whole round), as the result of the TDD loop below says. The machine (the shared board) accepts your answer and recounts before and after the fix with the judgment's way of counting.

The result of the TDD loop: {summary_file} — Read it all. The "units the loop fixed" are already fixed in the working tree, and the machine confirmed the test's red-to-green. Do not fix those units again; write one row in `changes` (in `files`, the fixed files and the test files; in `closure`'s `red_seen`, the red-to-green the machine saw). Do not change those units' test files (the acceptance rejects it; only what the fix plan names in `rewrite_tests` and the scope of a fix_test_scope ruling are exceptions).
<!-- end rules -->

{shared:writer}
