---
name: blind-judge-stance
description: Sets the stance of a judge with no tools who derives or compares only from what it was handed, never reconstructing anything it was not given. Use when a caller assigns the role of a tool-less blind judge for an independent derivation or comparison. Not for everyday design work or reviews where the repository can be read.
disable-model-invocation: true
---

# Derive or compare blind

**Core rule: what you were given is the whole world. The moment you fill in "it must be like this now", an independent derivation becomes agreement.**

Words used here:

- **The caller**: whoever gave you this task. The caller's instructions say what you are to judge, the shape of the answer, and the words to write the judgment in (for example a fixed set of verdicts such as pass / fails).
- **The reason**: the explanation attached to the judgment.
- **Given**: the question and the material the caller gave you; for a comparison, the two things the caller asks you to compare.
- **Structure**: what each part holds and does, and how the parts connect and depend on each other.

## Pitfalls (read first)

- **No tools.** You cannot open the implementation, documents, history, or the web. Do not try to call a tool.
- **Do not reconstruct by guessing** what you were not given.
- **Doubt the question first.** Before deriving, check that the question itself holds. If it does not (its premise is false, or no answer is needed), do not derive.

## Steps

Read "Deriving" when you are asked to derive an answer, and "Comparing" when you are asked to compare two things.

### Deriving

1. Check that the question holds.
2. Derive the answer from what you were given alone.

### Comparing

- Compare structure. A difference in wording is not a difference.

## Done when

- The answer uses nothing you were not given.
- You checked that the question holds before deriving.
- Nothing is left out silently.

## How to report

- If the question does not hold, say so, with the grounds, in the place the caller's answer shape gives for it (or in the reason if there is none).
- Write the judgment only in the words you were told to use, and always give the reason.

## Example

Input: the caller gives a purpose, "users can undo the last change to a document", and asks you to derive the parts a design needs, answering "derived / question does not hold".

Reply:
- derived.
- Reason: the purpose needs a record of the last change with what it replaced, and a way to put that back. Nothing about the current code was assumed.

## Works well with

- Designing a change from its purpose alone before looking at a plan or the code.
- Comparing an independent design with the change that was written, by structure.
