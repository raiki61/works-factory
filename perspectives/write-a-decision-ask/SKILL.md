---
name: write-a-decision-ask
description: Writes a question asking a person to decide something so that a first-time reader can decide from the text alone, in the fixed order title, now, proposal, cost, recommendation. Use when drafting options and a recommendation for someone to choose from, or when asked to "write this up as a question for them". Not for deciding whether to ask at all.
---

# Write a decision question a first-time reader can answer

**Core rule: the reader has not seen the work that led to the question, and does not know your internal words. Each item must let them decide from its own text alone.**

## Pitfalls (read first)

- **Complete facts come before shortness.** Give every fact the decision needs, even if the text gets longer. Say what a thing is and why it matters before you name it.
- **No pointers into the internals.** No `<path>:<line>` references, no positions inside records (such as "item 0" of some list), no internal keys, item numbers, or ids, no names of record files. Say in plain words what the thing is ("the function that computes the average", not a file and a line).
- **One point, one item.** When the same point comes up from several angles (a narrowed capability, the policy, how the world solves it), raise it once and mention the other angles inside that one item.

## Steps

### The shape of an item

In this order, each part as its own sentence (the title is one short line):

1. **Title**: what is to be decided, said so that a person can answer it, as one short line (no line break, no list).
2. **Now**: the current state, with the fact that makes it a question.
3. **Proposal**: what would be done.
4. **Cost**: what that costs, and whether and how it can be undone.
5. **Recommendation**: which answer you recommend, and why.

## Done when

- Each item lets a reader who has not seen the work decide from its own text alone.
- Each item has the five parts in order, each as its own sentence.
- No item points into the internals.
- No point is raised in more than one item.

## How to report

- Write each item in the shape above. When the form or document the item goes into has separate places for its parts (for example a title field and a body field), put each part in its place and keep this order across them.
- Some items start with a short mark that says why a person is asked: for example "case 2", when you follow separate rules that list the cases in which a person is asked, and the mark names which of them applies. That mark is not an internal reference: keep it at the very start of the item and put "Now" right after it.
- References that a machine checks (deciding sources, grounds, evidence) belong in their own fields, not in the text a person reads.

## Example

Input: you must ask whether to drop support for an old export format. A draft item reads "Remove the old export path? See item 2 of the plan."

Reply:
- Title: Stop offering the old export format?
- Now: the app still writes the old spreadsheet format, and keeping it blocks the fix to how dates are written.
- Proposal: remove the old format and keep only the current one.
- Cost: people who still open exports in the old format can no longer do so; it can be undone by restoring the removed code.
- Recommendation: remove it, because the current format opens in the same tools and the fix needs it gone.

## Works well with

- A way of deciding which questions need a person at all before you write them.
- Reading a text as a first-time reader with no context, to check the item stands alone.
