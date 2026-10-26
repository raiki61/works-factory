<!-- if rejected -->
{shared:rejected}

The acceptance ran all its checks. Fix every line listed under the headings, all in one resubmission.
<!-- end rejected -->

<!-- if rulings_first -->
Read the file with the rulings on the conflict declarations, {rulings_file}, all of it, first. Fix as the rulings say and return the whole answer again (the text of the rulings itself is not pasted here).
<!-- end rulings_first -->

<!-- if ruled_reply -->
The first fixer's answer (saved by the machine): {saved_reply}. Read it all first. Learn the earlier fixes and declarations from this file and the rulings file (the fixes in the working tree are still there).
<!-- end ruled_reply -->

<!-- if briefs -->
{shared:brief-head}
<!-- end briefs -->

<!-- if faces -->
## Pre-review keys to answer (plan_faces)

Answer every key below in the answer's `plan_faces`, one row per key (copy the key without changing a single character; do not write keys that are not in this list). The acceptance asks `plan_faces` for an answer to all of them.

{faces_rows}
<!-- end faces -->

<!-- if scope -->
## Paths you may change and what you must not touch

The acceptance checks the paths you changed against these values and rejects what is off. If a path you declared in `changes[].files` is explicitly allowed by one of that unit's items (allowed_paths, the test files), it is checked only against the `out_of_scope` of that unit's items (the `out_of_scope` of other items does not apply). For every other path, the `out_of_scope` of every item is stronger than the scope and also wins over the permitted paths (only a path excluded through a scope consultation does not apply for that item). The paths and test permissions allowed by scope consultations are included here too.

{scope_rows}

The permits that apply to all items (the permission to change tests, and the paths added by rulings to fix) do not win over `out_of_scope`.
<!-- end scope -->

<!-- if tests -->
## Tests you may add or change, and frozen tests

The acceptance checks the tests you added, the existing tests whose bodies you changed, and the frozen test files against these names, and rejects what is off. If you need something off the list, ask in a scope consultation before you change it.

{tests_rows}
<!-- end tests -->
<!-- if tests_new -->
- A new test that is not in "足してよい新しいテスト" is rejected when you add it.
<!-- end tests_new -->
<!-- if tests_tail -->
- The ranges in "本体を変えてよい既存のテストの範囲": `<path>` is the whole file, `<path>:<line>` is the whole function that contains the line, and `<path>:<line>-<line>` is the lines as written.
<!-- end tests_tail -->
<!-- if tests_broken -->
- The files under "直す前から壊れていた関わる試験" hold tests related to your fix that were already failing before the fix (in the TDD loop's first run). You may fix them along with your fix, so that they test what they were meant to test; do not weaken or remove what they check. They are shown to a person at the final approval as tests fixed along the way.
<!-- end tests_broken -->
<!-- if frozen_files -->
- Rewriting a frozen test file outside the names and ranges above is rejected. The functions of new tests you only added do not count as frozen; they are checked against "足してよい新しいテスト" above.
<!-- end frozen_files -->
<!-- if tests_tail -->
- Changing or removing the body of any other existing test function is rejected.
<!-- end tests_tail -->

<!-- if tests_how -->
## How the tests were run before the fix

These are the forms the test stage before the fix actually ran.

{tests_how}

Run tests in this form without searching for environments or commands (narrow them as the rules below say).
<!-- end tests_how -->

<!-- if policy -->
The policy document: {policy_path} (read it all first).
<!-- end policy -->
<!-- if no_policy -->
There is no policy document.
<!-- end no_policy -->
<!-- if request -->
The request file: {request_file} (read it all first).
<!-- end request -->
<!-- if no_request -->
There is no request file.
<!-- end no_request -->
