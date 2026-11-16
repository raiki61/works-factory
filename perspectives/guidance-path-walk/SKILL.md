---
name: guidance-path-walk
description: Tests whether a repository's guidance (its agent instruction files, design documents, and examples) leads a first-time contributor to the place where a typical change should close — by walking the repository from its entry files with only that guidance for one change request, recording every file opened and why, where the change would go, and which file would be copied as a model — and, when the walk ends in the wrong place, finding the first step where the guidance led off and proposing the smallest fix to the guidance, not to the reader. Use when checking that a repository's onboarding or contributor guidance works, or when asked "would a newcomer put this change in the right place", "where does our guidance mislead", "walk the repo as a new contributor".
---

# Walk a repository as a first-time contributor, and fix the guidance where it leads off

**Core rule: the reader had only the guidance. When a first-time reader puts a change in the wrong place, the guidance is what is wrong — fix the guidance, not the reader.**

This perspective has two sides that are used together: a walk by a fresh reader, and a review of where the walk went wrong.

## Pitfalls (read first)

- **The walker starts fresh**, in a new conversation, knowing nothing beyond what it reads. It does not make the change; it reports where it would make it.
- **Follow only what the files point to.** Start from the entry files. Follow links, paths, and names the files you read mention, and searches for names you have already seen there. Do not pick a place from the habits of other projects.
- **Do not judge the walker.** The fix goes to the guidance.
- **Prefer the smallest fix** that would have led this reader to the right place. Do not propose rewriting documents wholesale.

## The walk (one change request)

- Record every file opened, in order, with one line on what pointed you to it.
- Say where you would put the change: each file or folder you would create or edit (it may not exist yet), with one line on what you would change there.
- Say what you would copy as a model: each existing file whose shape you would follow, and why it is the model.
- Write down where you got stuck (a question the documents did not answer) and what you filled in by guessing.

## The review (for each request whose walk missed)

Read the walker's path and the files on it. Find the first step where the guidance pointed away from the place the change should close, or pointed nowhere. Propose one or more fixes, of three kinds:

- **Guide**: add or change guidance where the reader stands at that step — a line in the instruction file or design document they were reading.
- **Model**: change which example the guidance points to, when the reader copied the wrong model.
- **Block**: close the wrong path with the shape of the places — a folder layout or an interface that makes the wrong place impossible to use — when guidance alone would not hold.

For each fix: which request, which kind, the path to change, what to change there, and which step of the walk it fixes.
