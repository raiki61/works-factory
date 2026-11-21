---
name: rule-on-fix-conflict
description: Decides, as a separate read-only eye, which side gives way when a fixer has declared that the test, the request, or the code must bend to get green, and hands to a person only what lowers capability or changes policy. Use when a fixer reports "the test and the request disagree". Not for the fixer's own work of declaring the contradiction.
---

# Rule on a fix that cannot go green without bending something

**Core rule: never get to green by weakening a test. Decide yourself every ruling that does not lower capability; hand to a person only what lowers capability, changes the policy, or cannot be decided from the materials.**

A fixer who is stuck often declares that the test, the request, and the code cannot all hold. The declaration is a claim, not a fact. This perspective reads the places it names, decides which side is wrong, and says how to fix it — without changing anything itself.

The materials, as words used below:

- **The request**: what the person asked to be fixed, in their own words (and any answers they already wrote into it).
- **The policy**: the person's written rules for the repository, if any.
- **The judgment**: the earlier finding of what the defect is, why, where it came from, and the check that counts every instance of its shape ("the check that counts the defect").
- **The plan**: the agreed fix plan, split into items, each with its scope (paths it may touch, what it excludes), its acceptance tests, and the files it adds or removes. A **unit** is one root-cause defect that a plan item fixes.
- **Capability**: what the code and its tests can do and check today. Lowering it means removing, narrowing, or weakening behavior or checks.
- **A person**: the owner who decides for the repository.

## Pitfalls (read first)

- **Read only.** You rule; you do not change the working tree or any file.
- **Do not take the declaration's claims as they are.** Open every place it names and check it yourself.
- **Read the request and the policy first.** If the person's answer to this very conflict is already written in the request, rule with it and cite that line.
- **Read the plan item's scope before you rule.** Open the item the unit belongs to and check its scope, what it excludes, and its acceptance tests before you name places that may change or consider fixing the plan.
- **Do not weaken tests to get green.** No ruling that fits the expectations to the implementation, loosens a check, skips a test, or removes one.
- **Do not hand a person a mere overlap of names.** If the person's answer would not change the direction or the scope of the fix, it is not a question for a person.
- **Cite the grounds.** Every ruling names the lines (of the request, the judgment, the tests, the code) it rests on, in a form someone else can open.

## Steps

Read "The ruling rules" and "What each ruling binds the fixer to" for every conflict; "Special cases" adds rules for the three kinds of conflict it names.

### The ruling rules

1. **Decide yourself what does not lower capability.** A ruling equal to or a superset of the current capability is yours to make; go on without asking.
2. **Only three things go to a person**: what lowers capability (reduces, narrows, or weakens checks), what changes the policy (rewrites the person's policy or the purpose of the request), and what cannot be decided from the materials. And only when the person's answer would change the direction of the fix (which side is right) or its scope (where to fix, whether it reaches outside the agreed scope).
3. **A test may be fixed only when the request or the judgment shows that the test describes the wrong behavior.** Then name the exact places of the test that may change (a file, a line, a line range; a single line may be read as that line only, so for a whole test write its first and last lines). Tests outside those places stay as they are. Fixed tests are shown to the person at the end.
4. **If the request and the judgment are right and the tests agree with them, fix the code.** Say how.
5. **If the check that counts the defect also matches the correct lines after the fix, replace the check, not the code.** Confirm the match first. The new check matches the defect's shape and does not match the correct lines. The same holds for a check of "what needs fixing" that also matches things that are already correct: replacing it with one that names only what needs fixing does not narrow the check, because the set of things to fix does not change. When the defect's line and the correct line are the same text (both `return lo`, say), switch to a check that names lines that tell the defect apart (such as the condition of the branch to fix). Do not give up and hand this to a person.
6. **When in doubt, lean toward a person.** For example, when you cannot tell whether a ruling lowers capability, changes the policy, or can be decided from the materials, treat it as one that goes to a person. What goes to a person stays unfixed. When the fixer declared only after fixing (the check that counts the defect still matched the fixed lines), that fix stays where it is, and only whether it closed waits for the person.
7. **If the agreed plan item is itself wrong, fix the plan instead of letting the fix go past the plan's scope.** Do not let a test or code ruling reach outside the plan. Order of choice: if it closes inside the plan's scope, fix the test (rule 3) or the code or the check (rules 4–5); if not, fix the plan item. The paths that a test, code, or check ruling lists as places that may change are added to the scope of the whole fix (the scopes of all plan items together), not only to that unit's item, so any change of the fix may also touch them. Adding those paths does not change the item: the unit's fix is still placed inside the item's scope and still meets the item's acceptance tests and the files it adds or removes; the allowed paths only let the fix also touch those places. A fix that can only be placed outside the item's scope, needs a new file outside it, or touches what the item excluded is an error of the item. Excluded paths win over any extra paths you allow. When you rule to fix an item, cite the line of that item for the unit (a unit with no plan item to cite cannot be ruled this way), and in the same answer do not rule to fix the test, the code, or the check for any unit on that item.
8. **Overlaps of names you rule on yourself.** Same text is a different thing only when the language, the location, and the role (an environment variable, a type, and so on) differ and it is not a survivor of a name meant to be removed. A removed name redefined elsewhere (including in a test file) to keep old tests green is the same thing, and its place is not added to what may change. If you rule it a different thing, add the other place to what may change and rule to fix the code. If it needs a change to the plan item's path or to the name itself (renaming to avoid a collision of test file names, say), fix the plan item.

### Special cases

- **A unit that failed the same step three times in a row.** Suspect the plan item, the scope, or the check first — repeated failure is often a sign that the acceptance tests, the scope, or the check are wrong, before the way of fixing. Choose "fix the code" only when you can cite materials that show fixing the code is enough.
- **Two parallel fixes that clash when merged** (and the one who merges could not reconcile them). The clashing fix was taken out of the working tree and its diff set aside. Read that set-aside diff, the reasons the merge was given up, the tests that went red, and what the earlier fix changed. Give the same ruling to every unit the clashing fix covered. Options: how to fix the code when the merge is retried (list the paths outside what the clashing fix changed that the retry needs to touch, if any); which test places may change — only when the request or judgment shows the earlier fix changed the very behavior the later test expected; fix the plan when the two items cannot both hold; recut the problem when the two fixes are in fact fixing one problem separately. A person only when none of these applies. Recutting the problem is for this case only: use it only when the cut of the problem into units is wrong, and for no other conflict.
- **A test written only to pin the current behavior that fails on the unchanged tree.** That test does not describe the current behavior. Work meant only to pin the current behavior must not change behavior, so only two rulings are open: fix the plan item, or hand it to a person. Never rule to change the code, fix the test, or replace the check for it.

### What each ruling binds the fixer to

Rule knowing what the fixer will do with it next:

- **Fix a named part of the test**: tests change only in the named places, and the changed tests are shown to the person at the end. No test outside them changes or loosens.
- **Fix the code** or **replace the check**: outside the plan item's scope, only the paths the ruling lists may change (none if it lists none). Tests do not change.
- **Hand to a person**: the unit is not fixed now. A fix already in the working tree for it stays as it is — not reverted, not touched, not re-applied if it was set aside.
- **Fix the plan item**: neither this unit nor the other units of the same item are fixed now. Fixes already made for them stay in the working tree. If the plan cannot be fixed now, the units go to a person and the fixes made so far stay.
- **Recut the problem**: the unit is not fixed now; the ruling's text goes to whoever redoes the cut, as an objection.
- **A ruling to fix on a clash of two parallel fixes**: the clashing fix is not in the working tree but in the set-aside diff. Whoever merges re-applies that diff and fixes as the ruling says; the fixer after the ruling does not fix that unit and does not answer for it.
- After the ruling, the fixer's answer covers every unit it still owes and leaves the fixes of the other units in place. It no longer owes the units handed to a person, the units of an item ruled for a plan fix (waiting for the fix or given up), or the units already accepted before the conflict; units that come back after their plan item is fixed are owed again.

## Done when

- You opened every place the declaration names, the request and the policy, and the plan item of each unit.
- Every declaration has exactly one ruling, and every ruling cites the lines it rests on.
- No ruling weakens a test, and nothing goes to a person unless it lowers capability, changes the policy, or cannot be decided from the materials, and the person's answer changes the direction or the scope of the fix.
- No unit on an item you ruled to fix also has a ruling to fix the test, the code, or the check.

## How to report

For each declaration: which ruling (fix the code, fix a named part of the test, replace the check, hand to a person, fix the plan item, recut the problem), the reason and how to fix, the places that may change, and the lines it rests on. When something goes to a person, write what the person decides and why it needs a person: whether their answer changes the direction of the fix or its scope. If a request exists, say what you searched for in it and found no answer.

## Example

Input: the fixer declares that `test/parse_test:40-48` expects the old error message, the request asks for a new message, and the fix cannot pass without changing the test.

Reply:

- Ruling: fix a named part of the test, at `test/parse_test:40-48` only.
- Reason: the request (`request:3`) asks for the new message, so the test describes the wrong behavior. Rewrite its expected message to the one the request gives; no other test changes. The changed test is shown to the person at the end.
- Grounds: `request:3`, `test/parse_test:44`.

## Works well with

- A view, from the fixer's side, that refuses to bend a test, the request, or the code to get green and declares the conflict instead.
- A guide to writing a question that a person coming in cold can answer.
