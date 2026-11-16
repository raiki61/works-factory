---
name: fix-at-the-root
description: Writes a fix to a working tree by closing the root that a diagnosis named rather than the symptoms one by one — fixing every instance of the same shape, taking a ready-made or build-nothing solution first, removing what the fix makes unneeded, never hiding doubt behind a fallback or a stub, keeping the run's own words out of the target, rewriting every sentence that still describes the old behavior, and stopping when the fix would grow into a new mechanism. Use when about to write the fix for a diagnosed defect, when asked to "fix the root, not the symptom", "fix it properly", or when a fix keeps coming back with holes the next review finds.
---

# Write a fix that closes the root

**Core rule: close the root the diagnosis names, everywhere it has the same shape, with the smallest thing that already exists — and leave nothing in the target that only makes sense to whoever made the fix.**

## Pitfalls (read first)

- **Do not squash findings one by one.** A list of findings is the symptom; the diagnosis's reason and its account of where the defect came from name the root. Close that.
- **Do not stop at the one place that was named.** Use the diagnosis's query for the shape (or write one) and find every instance.
- **Do not hide doubt.** No default value, no catch that swallows the error, no silent fallback that makes an unsure case look handled. No TODO or FIXME, empty implementation, stub, or commented-out old code standing in for the finished fix in the final diff (a minimal stub a red step adds and a later step replaces is not in the final diff). A doubt only a person or the request can settle is raised, not hidden.
- **Do not write the run's words into the target.** Code notes, docstrings, documents, test names, identifiers, strings, file names, and rejection messages are read after the merge by people who never saw how the fix was made. No words of the process that made the fix (its stage names, role names, "unit", "round", "this run") and no circumstances of making it ("could not be measured here", "not in this working tree"). A reason given in the target is one its readers can follow from the target's code and documents alone; "the instructions said so", "the review asked for it", or "common practice says" is not such a reason.
- **Do not say "done" without changing anything.**

## How to fix

1. **Ready-made first.** Before writing anything, check whether a dependency already in use (the platform's standard library, version control, the tools the project already runs) or a well-known open-source project already does it; if one does, use it. If the diagnosis lists a prescription that builds nothing (withdraw, delete, use one existing mechanism), take it first. Do not make things more complex than needed, and do not rebuild an existing mechanism.
2. **Root, then every instance.** Fix the root, then every place of the same shape.
3. **Close dead paths; do not annotate them.** An added entry point or setting that nothing calls or reaches is fixed by connecting the caller or removing what is unreachable, not by a note.
4. **Remove what became unneeded, in the same change.** After editing, scan your own diff for parameters, variables, functions, exports, imports, and types that lost their last caller or reference because of what you removed or changed, and remove them. A parameter or option that every caller now fills with the same value is folded into the definition and removed. This does not reach the public API: that no caller remains in the repository does not show that none remains outside it. Do not fold a parameter when folding it would force a change to a test you may not change; leave it.
5. **Rewrite every sentence that describes the old behavior.** When you change behavior, search notes, docstrings, test names, rejection messages, and documents for sentences that still describe the behavior before the change, and fix or remove them. Keep the searches you ran as evidence. Do not add a note where a test name, a message, or a name can say it; a note says only why.
6. **Look before you add a mechanism.** For a fix that adds a mechanism or changes a shape, first search outside the target (the web and other outside services) for primary sources (standards, well-known open-source projects, official documentation) on how the world solves the same problem, and record the problem, the source you actually opened, and whether you adopt it, adapt it, find it does not apply, or found nothing (then say what you searched). If you build your own, say with sources why the world's solution does not exist or cannot be used.
7. **When several fixes touch the same file**, compare them per surface: does one make the other unneeded (then apply only the smaller one); does the order of applying them change the result; is there a state that arises only when they are combined. Record what you checked and what arises.

## When to stop instead of fixing

- **Stop as soon as the fix reaches a new mechanism or widens a shared surface** (a new module, type, settings key, or common entry point; something other places also read or call). That is design work, and no mechanism that has not been weighed against the build-nothing options may come out of a fix. Put in the fix that adds no mechanism, mark it as closing a symptom with that reason, and ask for the diagnosis to be redone. Keep fixing the other defects.
- **Do not build on a question that is still open.** A defect that is the origin of an unanswered question, or depends on one, is left with that reason. Once a person answers (or, in an automatic run with no person present, a recommended answer was recorded as taken in the person's place), it is owed again: fix it with the option the answer chose, or, if the answer does not touch it, with the option the question recommended.
- **Disagreeing with how the diagnosis cut the problem is not a reason to re-cut it yourself.** Record the objection to the framing so the next diagnosis reads it, and fix as the diagnosis says this time. Questions for a person do not go in that objection.
- **Root or symptom, said out loud.** For each fix, say whether it closed the root the diagnosis named or a symptom; for a symptom, say why you stop there now.

## Answering a pre-review

When the plan you follow was pre-reviewed, answer every hole and every smaller alternative it raised: taken in, and how; or left, and why (for a false positive, where in the real code it is wrong). Leaving a blocking hole means the next review will raise it again as blocking. Saying "hand it to a person" inside an answer does not reach the person; put it in the list of what the person decides (the part of the report shown to the person).

## When the work is split across helpers

- Check the working tree's diff yourself; do not trust a helper's report of what it changed.
- A reviewer of one item reviews what concerns that item; it does not review earlier items' fixes themselves, but points it out if the current item's fix breaks them.
- On a resubmission, redo only the items the rejection names; the other fixes stay as they are.

## When a fix comes back rejected

- Fix every line the rejection lists, all in one resubmission.
- In the same conversation, fix only what was rejected. Do not read the material again; read only what you need to confirm the reason for the rejection.

Works well with: a perspective on how to word the outside searches of step 6 so that they carry none of the target's private names.
