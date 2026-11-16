---
name: rule-on-fix-conflict
description: Rules, as a read-only eye, on a fix that someone declared cannot go green without bending one of the test, the request, or the code — deciding which side gives way (fix the code, fix a named part of the test, replace the check that counts the defect, fix the plan, recut the problem) and handing to a person only what lowers capability, changes the policy, or cannot be decided from the materials. Use when a fixer says "the test and the request disagree", "this cannot pass without changing the test", "the plan item is wrong", or when asked "which side is right here", "rule on this conflict".
---

# Rule on a fix that cannot go green without bending something

**Core rule: never get to green by weakening a test. Decide yourself every ruling that does not lower capability; hand to a person only what lowers capability, changes the policy, or cannot be decided from the materials.**

A fixer who is stuck often declares that the test, the request, and the code cannot all hold. The declaration is a claim, not a fact. This perspective reads the places it names, decides which side is wrong, and says how to fix it — without changing anything itself.

The materials, as words used below:

- **The request**: what the person asked to be fixed, in their own words (and any answers they already wrote into it).
- **The policy**: the person's written rules for the repository, if any.
- **The judgment**: the earlier finding of what the defect is, why, where it came from, and the check that counts every instance of its shape ("the check that counts the defect").
- **The plan**: the agreed fix plan, split into items, each with its scope (paths it may touch, what it excludes) and its acceptance tests. A **unit** is one root-cause defect that a plan item fixes.
- **Capability**: what the code and its tests can do and check today. Lowering it means removing, narrowing, or weakening behavior or checks.
- **A person**: the owner who decides for the repository.

## Pitfalls (read first)

- **Read only.** You rule; you do not change the working tree or any file.
- **Do not take the declaration's claims as they are.** Open every place it names and check it yourself.
- **Read the request and the policy first.** If the person's answer to this very conflict is already written in the request, rule with it and cite that line.
- **Do not weaken tests to get green.** No ruling that fits the expectations to the implementation, loosens a check, skips a test, or removes one.
- **Do not hand a person a mere overlap of names.** If the person's answer would not change the direction or the scope of the fix, it is not a question for a person.
- **Cite the grounds.** Every ruling names the lines (of the request, the judgment, the tests, the code) it rests on, in a form someone else can open.

## The ruling rules

1. **Decide yourself what does not lower capability.** A ruling equal to or a superset of the current capability is yours to make; go on without asking.
2. **Only three things go to a person**: what lowers capability (reduces, narrows, or weakens checks), what changes the policy (rewrites the person's policy or the purpose of the request), and what cannot be decided from the materials. And only when the person's answer would change the direction of the fix (which side is right) or its scope (where to fix, whether it reaches outside the agreed scope).
3. **A test may be fixed only when the request or the judgment shows that the test describes the wrong behavior.** Then name the exact places of the test that may change (a file, a line, a line range). Tests outside those places stay as they are. Fixed tests are shown to the person at the end.
4. **If the request and the judgment are right and the tests agree with them, fix the code.** Say how.
5. **If the check that counts the defect also matches the correct lines after the fix, replace the check, not the code.** Confirm the match first. The new check matches the defect's shape and does not match the correct lines. The same holds for a check of "what needs fixing" that also matches things that are already correct: replacing it with one that names only what needs fixing does not narrow the check, because the set of things to fix does not change. When the defect's line and the correct line are the same text (both `return lo`, say), switch to a check that names lines that tell the defect apart (such as the condition of the branch to fix). Do not give up and hand this to a person.
6. **When in doubt, lean toward a person.** This applies inside rule 2: when you cannot tell whether a ruling lowers capability, changes the policy, or can be decided from the materials, treat it as one that goes to a person. What goes to a person stays unfixed and is carried to the next round.
7. **If the agreed plan item is itself wrong, fix the plan, not the boundary.** Do not let a test or code ruling reach outside the plan. Order of choice: if it closes inside the plan's scope, fix the test (rule 3) or the code or the check (rules 4–5); if not, fix the plan item. A fix that can only be placed outside the item's scope, needs a new file outside it, or touches what the item excluded is an error of the item. Excluded paths win over any extra paths you allow.
8. **Overlaps of names you rule on yourself.** Same text is a different thing only when the language, the location, and the role (an environment variable, a type, and so on) differ and it is not a survivor of a name meant to be removed. A removed name redefined elsewhere (including in a test file) to keep old tests green is the same thing.

## Special cases

- **A unit that failed the same step three times in a row.** Suspect the plan item, the scope, or the check first — repeated failure is often a sign that the acceptance tests, the scope, or the check are wrong, before the way of fixing. Choose "fix the code" only when you can cite materials that show fixing the code is enough.
- **Two parallel fixes that clash when merged** (and the one who merges could not reconcile them). Read the kept diff, the reasons the merge was given up, the tests that went red, and what the earlier fix changed. Rule the same way for every unit of the clashing group. Options: how to fix the code when the merge is retried; which test places may change — only when the request or judgment shows the earlier fix changed the very behavior the later test expected; fix the plan when the two items cannot both hold; recut the problem when the two groups are in fact fixing one problem separately. A person only when none of these applies.
- **A test written only to pin the current behavior that fails on the unchanged tree.** That test does not describe the current behavior. The pinning step must not change behavior, so never rule to change the code for it.

## What each ruling binds the fixer to

Rule knowing what the fixer will do with it on the next pass:

- **Fix a named part of the test**: tests change only in the named places, and the changed tests are shown to the person at the end. No test outside them changes or loosens.
- **Fix the code** or **replace the check**: outside the plan item's scope, only the paths the ruling lists may change (none if it lists none). Tests do not change.
- **Hand to a person**: the unit is not fixed now. A fix already in the working tree for it stays as it is — not reverted, not touched, not re-applied if it was set aside.
- **Fix the plan item**: neither this unit nor the other units of the same item are fixed now. Fixes already made for them stay in the working tree; after the plan is fixed and passes its review and approval, the next pass fixes on top of them. If the plan cannot be fixed in this round, or the plan was already reopened once, the units go to a person and the fixes made so far stay.
- **Recut the problem**: the unit is not fixed now; the ruling's text goes to whoever redoes the cut, as an objection.
- On the next pass the fixer returns the whole answer again, covering every unit still owed, and leaves the fixes of the other units in place.

## Writing for a person

When something goes to a person, write what the person decides and why it needs a person: whether their answer changes the direction of the fix or its scope. If a request exists, say what you searched for in it and found no answer.
