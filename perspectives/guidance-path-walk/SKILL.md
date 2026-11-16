---
name: guidance-path-walk
description: Tests whether a repository's guidance (instruction files for AI, design documents, examples) leads a first-time contributor to where a typical change belongs, by walking from the entry files for one request and fixing the guidance where it leads off. Use when asked "would a new contributor find the right place to change". Not for checking whether one text reads on its own.
---

# Walk a repository as a first-time contributor, and fix the guidance where it leads off

**Core rule: the reader had only the guidance. When a first-time reader puts a change in the wrong place, the guidance is what is wrong — fix the guidance, not the reader.**

This perspective has two sides that are used together: a walk by a fresh reader, and a review of where the walk went wrong.

## Pitfalls (read first)

- **The walker starts fresh**, in a new conversation, knowing nothing beyond what it reads. It does not make the change; it reports where it would make it.
- **Follow only what the files point to.** Start from the entry files. Follow links, paths, and names the files you read mention, and searches for names you have already seen there. Do not pick a place from the habits of other projects.
- **Do not judge the walker.** The fix goes to the guidance.
- **Prefer the smallest fix** that would have led this reader to the right place. Do not propose rewriting documents wholesale.

## Steps

Read 'The walk' when you walk the repository for one change request, and 'The review' when you look at walks that missed; the pitfalls apply to both.

### The walk (one change request)

- Record every file opened, in order, with one line on what pointed you to it.
- Say where you would put the change: each file or folder you would create or edit (it may not exist yet), with one line on what you would change there.
- Say what you would copy as a model: each existing file whose shape you would follow, and why it is the model.
- Write down where you got stuck (a question the documents did not answer) and what you filled in by guessing.

### The review (for each request whose walk missed)

Read the walker's path and the files on it. Find the first step where the guidance pointed away from the place the change should close, or pointed nowhere. Propose one or more fixes, of three kinds:

- **Guide**: add or change guidance where the reader stands at that step — a line in the instruction file or design document they were reading.
- **Model**: change which example the guidance points to, when the reader copied the wrong model.
- **Close off**: close the wrong path with the shape of the places — a folder layout or an interface that makes the wrong place impossible to use — when guidance alone would not hold.

## Done when

- For the walk: every file opened is in the list in order with what pointed to it, and the places for the change, the models, where you got stuck, and the guesses are written down.
- For the review: every request that missed has at least one fix, and each fix goes to the guidance at the first step that led off, not to the reader.

## How to report

- **From the walk**: the files opened, in order, each with what pointed to it; each place for the change with what you would change there; each model file with why; where you got stuck; what you guessed. Write paths from the repository root.
- **From the review**: for each fix, which request, which kind, the path to change, what to change there, and which step of the walk it fixes.

## Example

Input: the request "add a new export format". The walker put it in the scripts folder, because the root guide names only that folder; new formats belong in the formats folder, which no file on the path mentions.

Reply: Request 1, kind Guide. Path: the root guide. Change: add a line saying that new export formats go in the formats folder, and which existing format to copy. It fixes step 1, where the root guide pointed only to the scripts folder.

## Works well with

- A reading of a single text as a first-time reader with no context, to see where one document stops a newcomer.
