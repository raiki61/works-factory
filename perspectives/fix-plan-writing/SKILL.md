---
name: fix-plan-writing
description: Writes the plan for a fix before any code is touched, so that a different reviewer can hit it first — every item says what it removes or merges before what it adds, what existing capability it narrows and why no non-narrowing form works, which existing helper or home of a concept it reuses, where the change ripples, which acceptance tests show the fix, and which paths it may write. Use when findings or a request are to be fixed and the fix should be planned first, or when asked to "plan this fix", "write the fix plan before changing code", "what exactly will we change and why".
---

# Write a fix plan before touching the code

**Core rule: before writing the fix, write a plan that a different reviewer can hit — and in every item think first of closing the problem by removing or merging, not by adding.**

Why: when every step that judges a fix comes after the fix, a fix that makes a new copy, a new entry point, or a drifted contract is found only in the next round, and the next round's fix makes the next hole (measured once: 8 of the findings of the third round were made by the second round's fix). A plan written first, reviewed by a different eye, and corrected with the predicted holes, moves that finding to before the fix.

## Pitfalls (read first)

- **Read only while you plan.** Do not change a single character of the working tree. The fix comes after the plan is reviewed.
- **What you leave out is not reviewed.** A review of the plan does not look at what is not in the plan. Write every file, every name added or removed, every test.
- **A fence becomes the seed of the next finding.** A fix that only "adds a check" leaves the paths the check does not watch as the next entry point.
- **Do not decide on your own to accept a narrowing as a cost.** If you leave a narrowing out, a later review raises it as a regression, and it goes to a person all the same.
- **Code comments, docstrings, and test descriptions are not the owner's decisions.** Do not use them as earlier decisions or as policy to justify what you leave out or narrow. If the fix disagrees with such text, put the rewrite of that text in the plan.
- **Do not rebuild the plan from a summary.** When a person or the request tells you to follow a document or check against it, check against its text. If you cannot read its text anywhere, say which document and what you tried, and stop instead of planning from a summary.

## The one axis of judgment

Does the whole become simpler while the purpose is met and the protecting mechanisms keep working? Measure simplicity not by the number of lines but by the number of places that know a design concept.

## What each item of the plan holds

1. **Which findings it closes.** Every finding you owe a fix goes into some item.
2. **The approach**: what you change and how, concretely, with the names of functions, fields, and documents.
3. **Every file it touches**, one row per file: whether it is created, changed, removed, or moved; the one responsibility of that file; the names added or removed in it; the concept this file becomes the home of and why this place; and the other places you considered and why you set them aside.
4. **What it removes or merges** (copies, unused entry points, old text) is listed as well, each with why it goes and what replaces it, if anything.
5. **Shrink first**: before adding a mechanism, state in one sentence the premise it makes up for ("add X; it is needed because Y does not do Z"), and look first for a form that removes that premise (for example, letting a value flow from the one place it is born instead of rebuilding it where it is used). If you still add, say why the removing form is not taken. That the premise holds in the target today is not a reason.
6. **What it narrows**: everything the plan removes or narrows among the capabilities that existed before the change. Count as capabilities not only functions but also the speed of iteration, the means of debugging, observation, and the default safety devices.
7. **The kind of fix**: test-first (a failing acceptance test, then the fix); direct (no test first); static (nothing a test can show: documents, comments, setting values, instruction wording, CI settings); tidy (removing something unused that no user can reach; a removal a user can see is direct); pin (the code is right and only a test that would catch the defect is missing, so the fix adds tests that pin the current behaviour and changes no code). The word says what kind of fix it is, not a preference.
8. **Acceptance tests**: for each new test, the behaviour it checks, how it goes through the real path (never asserting a mock's return value), and why it fails with the current code. Place it the way the existing tests in that file (or a sibling file) are placed. When the target has no tests yet, choose where the first ones go from the target's conventions.
9. **Tests to rewrite**: only existing tests whose expectation changes because the request changes the behaviour, each with the old and the new expectation. Never rewrite an expectation only to match the implementation.
10. **The scope it may write**, and what inside that scope it will not touch with why. Include documents that come with the fix (records of policy, design documents, change logs). A whole-tree permission is not a scope.

## Look for a form that does not narrow

Before you list a narrowing, check a form that avoids it: apply the new behaviour only to the cases you want to fix, and where it cannot apply (the field is not there, it cannot be counted, the tool is different), keep the earlier behaviour and say so out loud (in the report or on standard error) instead of staying silent. If there is such a form, take it and do not list the narrowing. Only when there is none, list it, and write which non-narrowing form you checked and why it cannot be taken.

## Use what already exists

- Before you add a new mechanism (a script, a subcommand, a helper function, a test fixture such as a fake tool or a test bundle), search the files the plan touches and their siblings (other steps of the same workflow, other files in the same module or place) for a helper that already does the job.
- If there is one and it points the same way as the general structure of the system, use it. If it points away, it is a precedent, not a form to reuse: moving it in line is part of the fix.
- If you still add a new one, name the existing thing you found and why you do not take it — or, if you found none, where and how you looked.

## Use the homes of concepts

For each concept the plan touches (a rule of the design: outcome words, stop reasons, a policy), first find the one place in the repository that holds it (its home): a map of where concepts live, if the repository has one; otherwise the README, the module boundaries, and the places that hold the same word as a constant.

- If there is a home, change the concept there; do not copy the same word, field name, value, or decision rule to other places.
- A place counts as a home only when it points the same way as the general structure. A place that holds the concept in a departing form is a precedent; the plan moves the concept to where the general structure puts it.
- If a file still makes a new place know the concept, name the home and why you do not use it.
- When the concept has no home yet, gather it into one of the places that already use it, rather than adding another place that knows it.

## Bringing the touched part in line

The paths needed to bring the touched part in line with the general structure of the system belong to the fix's scope, not to what it leaves out. Draw no new line for how far that goes.

## How to group items

- Merge findings into one item only when they share a root and close with one fix, or when they change the same line or the same hunk.
- When one fix depends on the result of another (it cannot be fixed or tested before the other), do not merge them: split them, and say in the later item what it receives from the earlier one.
- Touching different places in the same file (a different function, a different class, a test added to a different class) is not a reason to merge.

## Follow the ripple

Every caller of a name you change and every test that asserts a literal value you change is either put in the item's scope or tests now, or shown to be unaffected. A reference to a name you remove breaks after the removal. When a name has hits in many files, read them and decide which the fix touches; do not assume the list is complete.

## Follow given prescriptions and means — or say why not

- When an earlier judgment wrote a way to fix a finding, take it. If you do not, say why for that finding; do not drop its conditions silently.
- When the request itself named a means, either follow it or say why the plan does not take it, including when you set it aside to match practice, an independent design, or the repository's rules. Write that reason for a reader who knows neither the run nor the tool. A departure from the requester's means goes to a person before the fix starts.

## What goes to a person, and with what

- Every narrowing names the source that decides whether it is acceptable: a URL and its section, a place in the target that solves the same problem the same way as the general structure, a recorded decision, or a quote from the request. The request's suggested means is not such a source.
- Before you send something to a person, look up how the world solves the same problem (standards, well-known open-source software, official documents). If the practice settles the answer on one, decide it yourself and name that source.
- These always go to a person regardless: writing outside, an operation that cannot be undone, a change to the policy document, widening a protection (credentials, sandbox), a web result that raised a new doubt.
- For what goes to a person, give one recommended answer (let it through, with its scope and conditions; or stop, with why), written so that it can be copied as the answer.

## When the plan is sent back

- For each blocking hole the review raised, either fix the plan and say where, or dispute it without fixing and give your grounds. Answer every suggestion on an item that is still open the same way.
- Change only the items the holes are on. Items already closed with no hole raised stay exactly as they were; do not rewrite them.
- Suggestions on closed or held items, and suggestions the review said are gone, need no answer. You may take them or not, but do not reopen an item for them.
- Holes closed in earlier passes are rules to keep: before changing an item, check the change does not bring an earlier harm back in another form (for example, giving up what an earlier fix protected in order to close a new hole). If a new hole cannot be fixed without bringing one back, say so and name which.
- After the fix of the plan, a central blocking hole that remains stops the work before the fix; only peripheral ones are passed on into the fix.
- When, during the fix, an item of the approved plan is ruled wrong, fix only that item and only the places the ruling names. A change to what the item promised (the findings it closes, what it narrows, what it removes, its scope, what it leaves out, the tests it rewrites, the behaviour its tests check) goes back in front of a person.

## Write for the reader

Write the free text that people read (approach, every reason, what narrows, recommendations) plainly, for a reader who does not know the run.

Works well with: a perspective that pre-reviews a plan as a different eye, and one that states the grounds for departing from the general structure of a system.
