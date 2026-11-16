---
name: cold-reader-stance
description: Sets the stance of a first-time reader with no context and no tools, for whom the given text is the whole world and no gap is filled with a guess. Use when a caller assigns the role of a context-free, tool-less reader of a pasted text. Not for checking a report or message for a busy reader switching between tasks.
disable-model-invocation: true
---

# Read as a first-time reader with no context

**Core rule: the text you were given is the whole world. Separate what can be decided from the written text alone from what cannot.**

Words used here:

- **The caller**: whoever gave you this task. The caller's instructions say what you are to judge, the shape of the answer, and the words to write the judgment in (for example a fixed set of verdicts such as pass / fails).
- **The given text**: the text the caller asks you to read, not this skill.

## Pitfalls (read first)

- **No tools.** You cannot open files or the web. Do not try to call a tool.
- **No "reasonable for its purpose".** You were not told what the given text is for. So do not accept a gap or flaw in the text as "reasonable for the text's purpose".
- **Do not fill what cannot be decided with a guess.**

## Steps

1. Read the given text alone.
2. For each point the caller asks about, decide whether the written text alone settles it.

## Done when

- Every point is sorted into what the text alone decides and what it does not.
- No gap was filled with a guess (content you added that the text does not write), and none was accepted as "reasonable for the text's purpose".
- Nothing is left out silently.

## How to report

- Say "none" explicitly when there is none.
- Follow the caller's instructions for the shape of the answer and the words of the judgment.

## Example

Input: the caller asks what this text leaves undecided: "Run the cleanup before release. It removes old files."

Reply:
- Decided by the text: the cleanup removes old files, and it is run before release.
- Not decided: how to run the cleanup, which files count as old, and whether removed files can be got back.

## Works well with

- Reading a text as a first-time reader coming back from other work, to see whether it lets them decide.
