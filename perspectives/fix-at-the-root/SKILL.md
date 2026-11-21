---
name: fix-at-the-root
description: Writes a fix that closes the root a diagnosis named rather than its symptoms, fixing every same-shaped instance and removing what becomes unneeded. Use when a diagnosis exists and the code change is about to be written, or when asked to "fix the root, not the symptom". Not for pinning today's behaviour with tests, nor for cleanups that change no behaviour.
---

# Write a fix that closes the root

**Core rule: close the root the diagnosis names, everywhere it has the same shape, with the smallest thing that already exists — and leave nothing in the target that only makes sense to whoever made the fix.**

## Pitfalls (read first)

- **Do not squash findings one by one.** A list of findings is the symptom; the diagnosis's reason and its account of where the defect came from name the root. Close that.
- **Do not postpone what the diagnosis says to fix now.** Fix every defect it marks as blocking and every smaller finding it marks to fix now; do not move any of them to later on your own judgment. Even if doubts remain about its premise or its way of fixing, put in the best fix that stays within the policy (say it closes only a symptom if it does), and record the doubt as an objection. Only a defect whose way of fixing cannot be decided without a person's answer is left unfixed, and raised.
- **Do not stop at the one place that was named.** Use the diagnosis's query for the shape (or write one) and find every instance.
- **Do not hide doubt.** No default value, no catch that swallows the error, no silent fallback that makes an unsure case look handled. No TODO or FIXME, empty implementation, stub, or commented-out old code standing in for the finished fix in the final diff (a minimal stub a red step adds and a later step replaces is not in the final diff). A doubt only a person or the request can settle is raised, not hidden.
- **Do not write the words of the fixing process into the target.** Code notes, docstrings, documents, test names, identifiers, strings, file names, and rejection messages are read after the merge by people who never saw how the fix was made. No words of the process that made the fix (the names of its steps and roles, and its own words for a piece of work or for one pass over it, such as "unit" or "this round") and no circumstances of making it ("could not be measured here", "not in this working tree"). A reason given in the target is one its readers can follow from the target's code and documents alone; "the instructions said so", "the review asked for it", or "common practice says" is not such a reason.
- **Do not say "done" without changing anything.**
- **A test turned red after an earlier attempt points at that attempt.** If CI turned a test red after an earlier attempt at the same work, assume that attempt's fix turned it red, and write a fix that does not turn the same test red again. Separately, when an automatic check of the form of an answer (one that accepts or rejects it by fixed rules) refused something in an earlier attempt, that refusal is a caution so you do not fail at the same place again; it is not a defect to fix.
- **Check a library's API against its documents.** When the change relies on a library's signature, arguments, or usage, confirm it in the documents of the version installed in the target (read from the installed code) and in the library owner's official documents, matched to that version where possible; fetch the official documents yourself when none are at hand.

## Steps

Read "How to fix" and "When to stop instead of fixing" for every fix; read "Following a plan reviewed before the fix", "When the work is split across helpers", and "When a fix comes back with problems" only in those situations.

### How to fix

1. **Ready-made first.** Before writing anything, check whether a dependency already in use (the platform's standard library, version control, the tools the project already runs) or a well-known open-source project already does it; if one does, use it. If the diagnosis lists a prescription that builds nothing (withdraw, delete, use one existing mechanism), take it first. Do not make things more complex than needed, and do not rebuild an existing mechanism.
2. **Root, then every instance.** Fix the root, then every place of the same shape.
3. **Close dead paths; do not annotate them.** An added entry point or setting that nothing calls or reaches is fixed by connecting the caller or removing what is unreachable, not by a note.
4. **Remove what became unneeded, in the same change.** After editing, scan your own diff for parameters, variables, functions, exports, imports, and types that lost their last caller or reference because of what you removed or changed, and remove them. A parameter or option that every caller now fills with the same value is folded into the definition and removed. This does not reach the public API: that no caller remains in the repository does not show that none remains outside it. Do not fold a parameter when folding it would force a change to a test you may not change; leave it.
5. **Rewrite every sentence that describes the old behavior.** When you change behavior, search notes, docstrings, test names, rejection messages, and documents for sentences that still describe the behavior before the change, and fix or remove them. Keep the searches you ran as evidence. Do not add a note where a test name, a message, or a name can say it; a note says only why.
6. **Look before you add a mechanism.** For a fix that adds a mechanism or changes a shape, first search outside the target (the web and other outside services) for primary sources (standards, well-known open-source projects, official documentation) on how the world solves the same problem, and record the problem, the source you actually opened, and whether you adopt it, adapt it, find it does not apply, or found nothing (then say what you searched). A precedent the diagnosis already recorded for the same defect may be taken as it is; say that you took it. If you build your own, say with sources why the world's solution does not exist or cannot be used.
7. **When several fixes touch the same file**, compare them per place they touch: does one make the other unneeded (then keep only one of the two: the smaller change); does the order of applying them change the result; is there a state that arises only when they are combined. Record what you checked and what arises.

### When to stop instead of fixing

- **Stop as soon as the fix reaches a new mechanism or widens a shared surface** (a new module, type, settings key, or common entry point; something other places also read or call). That is design work, and no mechanism that has not been weighed against the build-nothing options may come out of a fix. Put in the fix that adds no mechanism, mark it as closing a symptom with that reason, and ask for the diagnosis to be redone. Keep fixing the other defects.
- **Do not build on a question that is still open.** A defect that is the origin of an unanswered question, or depends on one, is left with that reason. Once a person answers (or, when no person is present, a recommended answer was recorded as taken in the person's place), it is owed again: fix it with the option the answer chose, or, if the answer does not touch it, with the option the question recommended.
- **Disagreeing with how the diagnosis cut the problem is not a reason to re-cut it yourself.** Record the objection to how it grouped the defects, read the root, or decided what to do with each, so that a redone diagnosis reads it, and fix as the diagnosis says this time. Questions for a person do not go in that objection.
- **Root or symptom, said out loud.** For each fix, say whether it closed the root the diagnosis named or a symptom; for a symptom, say why you stop there now.

### Following a plan reviewed before the fix

Answer every hole and every smaller alternative the review of the plan raised: taken in, and how; or left, and why (for a false positive, where in the real code it is wrong). A blocking hole you answer as left does not go away; expect the next review to raise it again as blocking. Saying "hand it to a person" inside an answer does not reach the person; put it where the person reads what they must decide.

### When the work is split across helpers

- Check the working tree's diff yourself; do not trust a helper's report of what it changed.
- A reviewer of one item reviews what concerns that item; it does not review earlier items' fixes themselves, but points it out if the current item's fix breaks them.
- An item whose review still has findings after the last retry is still fixed and reported, as closing a symptom, with the remaining findings as the reason. Only a defect that cannot be fixed at all — its way of fixing cannot be decided without a person's answer, or the helper reported that it lacks the context or is blocked — is not counted as fixed and is raised.

### When a fix comes back with problems

- Fix every problem the list names, all at once.
- Redo only the items the list names; the other fixes stay as they are.

## Done when

- Every defect marked blocking or fix-now is fixed, or — only when its way of fixing needs a person's answer — raised.
- Every instance of the same shape was searched for and fixed, not only the named place.
- The final diff holds no stand-in for the finished fix and no words of the fixing process, and something was actually changed.
- Every sentence that described the old behavior is rewritten or removed, and what lost its last caller is removed.
- Each fix is labelled root or symptom; each symptom says why you stop there.
- When the plan was reviewed before the fix, every hole and alternative it raised is answered.
- The working tree's diff was checked by you, not taken from a helper's report.

## How to report

For each fix: what you changed, root or symptom (for a symptom, why you stop there now), how many places of the same shape you fixed, and the searches you ran (for the shape, and for sentences that described the old behavior). For a fix that adds a mechanism: the problem, the source you opened, and whether you adopt, adapt, find it does not apply, or found nothing. Where fixes share a file: what you compared and what arises. Then, separately: the defects you did not fix and why; objections to how the diagnosis cut the problem; and what a person must decide, written where the person reads it.

## Example

Input: the diagnosis names one fix-now defect — a shared date helper returns today's date when the input cannot be read, and the callers trust it.

Reply:

- Root closed: the helper now raises an error on unreadable input instead of returning a default.
- Same shape: a search for the helper's name found 3 callers; all 3 now handle the error.
- Removed the default-date parameter that no caller sets any more.
- Rewrote the helper's doc comment, which said "falls back to today". Searches run: the helper's name; "falls back".
- Not fixed: none.

## Works well with

- A way to word outside searches so that they carry none of the target's private names (used in step 6 of "How to fix").
