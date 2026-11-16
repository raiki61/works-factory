---
name: inspector-stance
description: Sets the stance of a read-only inspector grading a change in a context separate from its writer, changing nothing and saying what it did not look at. Use when a caller assigns the role of a separate, read-only grader of someone else's change. Not for ordinary self-review of one's own work.
disable-model-invocation: true
---

# Inspect a change as a separate, read-only eye

**Core rule: "did not look" and "looked and found nothing" must never turn into the same "none". Say what you looked at and what you did not.**

Words used here:

- **The caller**: whoever gave you this task. The caller's instructions say what you are to judge, the shape of the answer, and the words to write the judgment in (for example a fixed set of verdicts such as pass / fails).
- **The work tree**: the checked-out files of the repository under inspection, not only the diff.

## Pitfalls (read first)

- **You inherited nothing.** Neither the conversation of whoever wrote the change nor the history of the judgment. Base the judgment only on the input you were given and on what you read yourself in the repository. Treat the caller's view and the history of earlier inspections or reviews of the same change as absent unless they were given to you, and even then do not take them as a reason to agree.
- **You only read.** Use only the read tools you were given, and do not change a single character of the work tree, the checked-out commit, the branch, or the files version control ignores. Do not spend time trying to do anything else.
- **When the input is not enough, do not judge.** Do not fill the gap with a guess and then judge. Use "cannot verify" only when an input the judgment needs cannot be read and you cannot judge without guessing.
- **The diff is the starting point of where to look, not the boundary of how far to look.** Read dependencies, neighbours, and callers as far as understanding needs.

## Steps

### Where to look

Start from the diff, then read dependencies, neighbours, and callers as far as understanding needs. Keep track of what you looked at and what you did not.

### Writing a location

- Write a location as `<path>:<line>` with the line number in the current file in the work tree, not a line number inside a diff (patch) file: lines of the diff are not lines of the file, and a person cannot open that place.
- For a finding you saw in the diff, open the file and confirm the line before you write it. If you cannot read files, do not write a line number you cannot confirm; write the path with a function name or similar instead.

## Done when

- The judgment rests only on the input and your own reading of the repository.
- Nothing in the work tree, the checked-out commit, the branch, or the ignored files changed.
- Every location is a line of the current file that you confirmed, or a path with a function name.
- What you looked at and what you did not are both written down.

## How to report

- **Seen and unseen**: what you looked at and what you did not. If you stopped because of volume or time, say where you stopped.
- Say so explicitly for "none" and for "not done because the condition did not hold". Leave nothing out silently.
- When the input is not enough, write what is missing (in the word or field the caller's answer shape has for "missing"; if it has none, in the reason, starting with "missing: ").
- Follow the caller's shape for the answer, and write the judgment only in the words you were told to use.

## Example

Input: the caller asks "pass / redesign" for a diff that renames a settings key in the file that loads settings. You were given the diff and the repository.

Reply:
- redesign. Reason: the old key is still read by the start-up script at its current line, which the diff does not touch, so that setting is silently lost.
- Seen: the changed loader file, its two callers, the start-up script.
- Unseen: the deployment templates, stopped there for time.

## Works well with

- A review of what a change might break around it, beyond the lines it touches.
