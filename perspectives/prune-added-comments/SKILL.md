---
name: prune-added-comments
description: Sorts every comment a change added or rewrote into remove, naming where the same content already lives, or keep, stating the fact it carries. Use when asked "which of these comments should go". Not for reviewing the code's logic.
---

# Sort the comments a change added: remove or keep, each with its reason

**Core rule: remove a comment only when you can name where the same content already lives; keep a comment only when you can say in one sentence the fact it carries.**

If only removals carry a duty, keeping a comment silently becomes the cheaper choice. Both sides carry one here, and both can be checked later, so the result does not stay an opinion.

The general stance of a comment reviewer — verify every claim of a comment against the code, prefer "why" over "what", flag comments that will rot, write for the least experienced future maintainer, advise only — is defined by the comment-analysis review agent the owner (the person who wrote this perspective) relies on (`comment-analyzer` of the `pr-review-toolkit` plugin). When that definition is available, it is the stance; this file does not copy it. When it is not, work from the summary above. What this file keeps is the owner's rule for turning that stance into removals and keeps.

## Pitfalls (read first)

- **Read only.** You advise; you do not change a comment or the code.
- **The target is only the comments the change added or rewrote** (the added side of the diff), in the files the change touches. Other comments in the same files may be read as places where the same content lives, but they are not judged.
- **No name, no removal.** If you cannot name where the same content lives, the comment is not a removal candidate, however obvious it looks.
- **No silent keep.** Every target comment that is not a removal candidate is listed as kept, with its fact.
- **A wrong or lacking comment is not a third category.** Put it among the removal candidates if it meets the conditions of one, otherwise among the kept.

## Steps

### Which comments may stay

The only notes that may be written are the reason another solution was rejected (the why) and the documentation of public interfaces. A comment that only says what the code does is a removal candidate — but only if you can name where the same content lives; if you cannot, it goes among the kept, like every other comment that is not a removal candidate.

### Search explicitly for these triggers

- Commented-out code.
- Running commentary on the edit ("added …", "changed to …").
- A comment that restates a name right next to that name.

## Done when

- Every target comment is in exactly one of the two lists.
- Every removal candidate names where the same content lives.
- Every kept comment has its one-sentence fact.
- The three triggers above were searched for explicitly.

## How to report

Two lists, one entry per target comment:

- **Removal candidate**: where it is (file:line), its text, **where the same content lives** (the code itself, another comment, a document, a test name), and why it should go.
- **Kept**: where it is, and **one sentence on the fact it carries**.

## Example

Input: a change adds two comments: "loop over the orders" above a loop over `orders`, and "not a set: the order of retries matters" above a list.

Reply:
- Removal candidate: the first comment, file:line. The same content lives in the code itself (the loop over `orders`). It only says what the code does.
- Kept: the second comment, file:line. Fact: a set was rejected because the retries must keep their order.

## Works well with

- A perspective that judges whether a change is minimal by the number of places that know each concept.
