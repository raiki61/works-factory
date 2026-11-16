---
name: prune-added-comments
description: Reviews the comments a change added or rewrote and sorts every one of them into a removal candidate or a kept comment — a removal candidate must name the place where the same content already lives, and a kept comment must state in one sentence the fact it carries — so that neither removing nor keeping is an unargued opinion. Use after a change is written, before it is accepted, or when asked to "check the comments in this diff", "which of these comments should go", "remove redundant comments".
---

# Sort the comments a change added: remove or keep, each with its reason

**Core rule: remove a comment only when you can name where the same content already lives; keep a comment only when you can say in one sentence the fact it carries.**

If only removals carry a duty, keeping a comment silently becomes the cheaper choice. Both sides carry one here, and both can be checked later, so the result does not stay an opinion.

The general stance of a comment reviewer — verify every claim of a comment against the code, prefer "why" over "what", flag comments that will rot, write for the least experienced future maintainer, advise only — is defined by the comment-analysis review agent the owner relies on (`comment-analyzer` of the `pr-review-toolkit` plugin). When that definition is available, it is the stance; this file does not copy it. What this file keeps is the owner's rule for turning that stance into removals and keeps.

## Pitfalls (read first)

- **Read only.** You advise; you do not change a comment or the code.
- **The target is only the comments the change added or rewrote** (the added side of the diff), in the files the change touches. Other comments in the same files may be read as places where the same content lives, but they are not judged.
- **No name, no removal.** If you cannot name where the same content lives, the comment is not a removal candidate, however obvious it looks.
- **No silent keep.** Every target comment that is not a removal candidate is listed as kept, with its fact.
- **A wrong or lacking comment is not a third category.** Put it among the removal candidates if it meets the conditions of one, otherwise among the kept.

## Which comments may stay

The only notes that may be written are the reason another solution was rejected (the why) and the documentation of public interfaces. A comment that only says what the code does is a removal candidate — but its removal still needs the named place below.

## For each target comment

- **Removal candidate**: where it is (file:line), its text, **where the same content lives** (the code itself, another comment, a document, a test name), and why it should go.
- **Kept**: where it is, and **one sentence on the fact it carries**.

## Search explicitly for these triggers

- Commented-out code.
- Running commentary on the edit ("added …", "changed to …").
- A comment that restates a name right next to that name.

Works well with (optional; this file is complete without them): a perspective that judges whether a change is minimal by the number of places that know each concept.
