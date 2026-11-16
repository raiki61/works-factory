---
name: fix-plan-writing
description: Writes the plan for a fix before any code is touched, each item saying what it removes before what it adds, what it reuses, where it ripples, which tests show it, and which paths it may write. Use when findings should be planned before coding, or when asked to "plan the fix first". Not for reviewing a plan someone else wrote.
---

# Write a fix plan before touching the code

**Core rule: before writing the fix, write a plan that a different reviewer can hit — and in every item think first of closing the problem by removing or merging, not by adding.**

Why: when every step that judges a fix comes after the fix, a fix that makes a new copy, a new entry point, or a drifted contract is found only by the next review, and the fix for that finding makes the next hole (measured once: 8 of the findings of the third review were made by the fix that followed the second). A plan written first, reviewed by a different eye, and corrected with the predicted holes, moves that finding to before the fix.

The one axis of judgment: does the whole become simpler while the purpose is met and the protecting mechanisms keep working? Measure simplicity not by the number of lines but by the number of places that know a design concept.

Below, "the general structure" of a system means how systems of the same kind are commonly built (their usual parts, boundaries, and places for each concern, as standards and well-known software show). A place "points the same way" when it follows that shape, and "departs" when it does not.

## Pitfalls (read first)

- **Read only while you plan.** Do not change a single character of the working tree. The fix comes after the plan is reviewed.
- **What you leave out is not reviewed.** A review of the plan does not look at what is not in the plan. Write every file, every name added or removed, every test.
- **A fence becomes the seed of the next finding.** A fix that only "adds a check" leaves the paths the check does not watch as the next entry point.
- **Do not decide on your own to accept a narrowing as a cost.** If you leave a narrowing out, a later review raises it as a regression, and it goes to a person all the same.
- **Code comments, docstrings, and test descriptions are not the owner's decisions.** Do not use them as earlier decisions or as policy to justify what you leave out or narrow. If the fix disagrees with such text, put the rewrite of that text in the plan.
- **Do not rebuild the plan from a summary.** When a person or the request tells you to follow a document or check against it, check against its text, and say which version of it you read. If you cannot read its text anywhere, say which document and what you tried, and stop instead of planning from a summary.
- **Do not drop a finding you owe because a check doubted it.** The findings may come sorted by an earlier judgment into units, one per root, with notes from a separate check of each unit. A unit that the check reported as not the root, in a different place, or without evidence still stays in the plan: put it in the same item as the unit of the real root, or write in the approach your answer to that note (how you handle it). Use the notes on duplicates, relations at the same place, and order for grouping items; a relation between different places (only touching different places in the same file) is only a hint for the order of items, not a reason to merge. Read a unit the check could not check as the judgment has it.
- **A test turned red after an earlier attempt points at that attempt.** If CI turned a test red after an earlier attempt at the same work, assume that attempt's fix turned it red, and write a plan whose fix does not turn the same test red again. Where, in an earlier attempt, a comparison with an independent design (one made from the purpose alone, without seeing the plan or the implementation) said a redesign was needed, that is a hole to fix: fix it before the rest. Separately, when a mechanical check of the form of an answer (one that accepts or rejects it by fixed rules) rejected something in an earlier attempt, that rejection is a caution so you do not fail at the same place again; it is not a defect to fix.
- **Check a library's API against its documents.** When the change relies on a library's signature, arguments, or usage, confirm it in the documents of the version installed in the target (read from the installed code) and in the library owner's official documents, matched to that version where possible; fetch the official documents yourself when none are at hand.

## Steps

Read "When the plan is sent back" only when a review returned the plan or an item of an approved plan was judged wrong; the other subsections apply every time.

### What each item of the plan holds

1. **Which findings it closes.** Every finding you owe a fix goes into some item.
2. **The approach**: what you change and how, concretely, with the names of functions, fields, and documents.
3. **Every file it touches**, one row per file: whether it is created, changed, removed, or moved; the one responsibility of that file; the names added or removed in it; the concept this file becomes the home of and why this place; and the other places you considered and why you set them aside.
4. **What it removes or merges** (copies, unused entry points, old text) is listed as well, each with why it goes and what replaces it, if anything.
5. **Shrink first**: before adding a mechanism, state in one sentence the premise it makes up for ("add X; it is needed because Y does not do Z"), and look first for a form that removes that premise (for example, letting a value flow from the one place it is born instead of rebuilding it where it is used). If you still add, say why the removing form is not taken. That the premise holds in the target today is not a reason.
6. **What it narrows**: everything the plan removes or narrows among the capabilities that existed before the change. Count as capabilities not only functions but also the speed of iteration, the means of debugging, observation, and the default safety devices.
7. **The kind of fix** (when a spec written by a person names the places to fix test-first, only those are test-first, the rest are direct unless they are static, tidy, or pin; do not choose beyond that on your own): test-first (a failing acceptance test, then the fix); direct (no test first); static (nothing a test can show: documents, comments, setting values, instruction wording, CI settings); tidy (removing something unused that no user can reach; a removal a user can see is direct); pin (the code is right and only a test that would catch the defect is missing, so the fix adds tests that pin the current behaviour and changes no code). The word says what kind of fix it is, not a preference.
8. **Acceptance tests**: for each new test, the behaviour it checks, how it goes through the real path (never asserting a mock's return value), and why it fails with the current code. It fails by an assertion or by an expected exception that is not raised. Only a failure of something the item declares (a name it adds, a file it creates) counts as failing; a failure of a name outside the declaration, or a failure to import or collect the tests, does not. Place it the way the existing tests in that file (or a sibling file) are placed. When the target has no tests yet, choose where the first ones go from the target's conventions. When a spec written by a person lists acceptance tests, put each in the item that holds the finding it belongs to.
9. **Tests to rewrite**: only existing tests whose expectation changes because the request changes the behaviour, each with the old and the new expectation. Never rewrite an expectation only to match the implementation.
10. **The scope it may write**, and what inside that scope it will not touch with why. Include the original paths of files you move or remove, and, when the target has no tests yet, the files needed to run the first ones. Include documents that come with the fix (records of policy, design documents, change logs). A whole-tree permission is not a scope. Ranges that other pull requests running in parallel hold are not touched and not put in any item.

### Look for a form that does not narrow

Before you list a narrowing, check a form that avoids it: apply the new behaviour only to the cases you want to fix, and where it cannot apply (the field is not there, it cannot be counted, the tool is different), keep the earlier behaviour and say so out loud (in the report or on standard error) instead of staying silent. If there is such a form, take it and do not list the narrowing. Only when there is none, list it, and write which non-narrowing form you checked and why it cannot be taken.

### Use what already exists

- Before you add a new mechanism (a script, a subcommand, a helper function, a test fixture such as a fake tool or a test bundle), search the files the plan touches and their siblings (other steps of the same workflow, other files in the same module or place) for a helper that already does the job.
- If there is one and it points the same way as the general structure of the system, use it. If it points away, it is a precedent, not a form to reuse: moving it in line is part of the fix.
- If you still add a new one, name the existing thing you found and why you do not take it — or, if you found none, where and how you looked.

### Use the homes of concepts

For each concept the plan touches (a rule of the design: outcome words, stop reasons, a policy), first find the one place in the repository that holds it (its home): a map of where concepts live, if the repository has one; otherwise the README, the module boundaries, and the places that hold the same word as a constant.

- If there is a home, change the concept there; do not copy the same word, field name, value, or decision rule to other places.
- A place counts as a home only when it points the same way as the general structure. A place that holds the concept in a departing form is a precedent; the plan moves the concept to where the general structure puts it.
- If a file still makes a new place know the concept, name the home and why you do not use it.
- When the concept has no home yet, gather it into one of the places that already use it, rather than adding another place that knows it.

### Bringing the touched part in line

The paths needed to bring the touched part in line with the general structure of the system belong to the fix's scope, not to what it leaves out. Draw no new line for how far that goes.

### How to group items

- Merge findings into one item only when they share a root and close with one fix, or when they change the same line or the same hunk.
- When one fix depends on the result of another (it cannot be fixed or tested before the other), do not merge them: split them, and say in the later item what it receives from the earlier one.
- Touching different places in the same file (a different function, a different class, a test added to a different class) is not a reason to merge.

### Follow the ripple

Every caller of a name you change and every test that asserts a literal value you change is either put in the item's scope or tests now, or shown to be unaffected. A reference to a name you remove breaks after the removal. When a name has hits in many files, read them and decide which the fix touches; do not assume the list is complete.

### Follow given prescriptions and means — or say why not

- When an earlier judgment wrote a way to fix a finding, take it. If you do not, say why for that finding; do not drop its conditions silently.
- When a different eye has marked places where the change would grow forms that a later person who does not know the design would add, and chose a way to avoid each, the item that holds such a place either follows that way or says why not, for each marked place.
- When the request itself named a means, either follow it or say why the plan does not take it, including when you set it aside to match practice, an independent design, or the repository's rules. Write that reason for a reader who saw neither the work nor the tool. A departure from the requester's means goes to a person before the fix starts. Do not write a recommendation for such a departure yourself: a different eye that reviews the plan writes it.
- When the practice of the world for a class of problem in the request has been laid out, some item either follows that practice or says why it does not, with the source. The request's own way of solving it is a proposal to doubt against the practice, not a source: a departure whose only source is the request goes to a person before the fix.

### What goes to a person, and with what

- Every narrowing names the source that decides whether it is acceptable: a URL and its section, a place in the target that already solves the same problem following the general structure, a recorded decision, or a quote from the request. The request's suggested means is not such a source.
- Before you send something to a person, look up how the world solves the same problem (standards, well-known open-source software, official documents). If the practice settles the answer on one, decide it yourself and name that source. For every narrowing, write in one sentence what that check found (the source and how the answers split; if you found nothing, why; if a person's earlier decision settles it, say so).
- These always go to a person regardless: writing outside, an operation that cannot be undone, a change to the policy document, widening a protection (credentials, sandbox), a web result that raised a new doubt.
- For what goes to a person (except a departure from the requester's means, above), give one recommended answer (let it through, with its scope and conditions; or stop, with why), written so that it can be copied as the answer.

### When the plan is sent back

- For each blocking hole the review raised, either fix the plan and say where, or dispute it without fixing and give your grounds. Answer every suggestion on an item that is still open the same way.
- Change only the items the holes are on. Items already closed with no hole raised stay exactly as they were; do not rewrite them.
- Suggestions on closed or held items, and suggestions the review said are gone, need no answer. You may take them or not, but do not reopen an item for them.
- Holes closed in earlier reviews are rules to keep: before changing an item, check the change does not bring an earlier harm back in another form (for example, giving up what an earlier fix protected in order to close a new hole). If a new hole cannot be fixed without bringing one back, say so and name which.
- If, after you correct the plan, a blocking hole at the core of the plan still remains, do not start the fix; only holes at the edges may be carried into the fix.
- When, while the fix is being made, it is judged that an item of the approved plan was wrong, correct only that item and only the places that judgment names. A change to what the item promised (the findings it closes, what it narrows, what it removes, its scope, what it leaves out, the tests it rewrites, the behaviour its tests check) goes back in front of a person.

### Write for the reader

Write the free text that people read (approach, every reason, what narrows, recommendations) plainly, for a reader who did not see the work.

## Done when

- The working tree is unchanged.
- Every finding you owe is in some item, including the units a check doubted.
- Every item holds the ten parts above, with every file, every name added or removed, and every test written out.
- Every narrowing names the non-narrowing form you checked, its deciding source, and what checking the world found.
- Every new mechanism names the existing helper or home you found and why you do not take it, or where you looked.
- Every given prescription, marked place, requester's means, and laid-out practice is followed or has its reason.
- When the plan was sent back: every blocking hole and every suggestion on an open item has an answer, and the closed items are unchanged.

## How to report

- The plan: its items in order, each with the ten parts above.
- What goes to a person: each with its deciding source, what checking the world found, and one recommended answer that can be copied as it is (none for a departure from the requester's means).
- When the plan was sent back: per hole, fixed (and where) or disputed (and the grounds), and only the items you changed.
- When a document you were told to follow cannot be read: which document and what you tried, and no plan.

## Example

Input: a finding says the import command drops unknown columns without a word. The first idea is to reject any file with an unknown column, but files written by older versions carry an extra column and import fine today.

Reply:
- Item 1 closes the finding. Approach: keep importing; name each dropped column on standard error.
- Files: the import module, changed (adds the warning); its test file, changed (adds one test).
- Narrows: nothing. Checked first: rejecting such files; not taken, because the warning closes the finding without taking away what older files can do.
- Kind: test-first. Acceptance test: importing a file with an extra column prints the column's name on standard error; fails today because nothing is printed.
- Scope: the import module and its test file.

## Works well with

- A different eye that reviews a plan before the fix is written.
- A look at the grounds for departing from the general structure of a system.
