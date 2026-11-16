---
name: write-a-decision-ask
description: Writes a question that asks a person to decide something (at an approval point, or in the "what you must decide" part of a report) so that a first-time reader coming back from other work can decide from the text alone — every fact the decision needs, no pointers into internal records, and the fixed order title, now, proposal, cost, recommendation, one point per item. Use whenever you write a question, an option list, or a recommendation for a person to answer, or when asked "write this up for the owner to decide", "make this approval question readable".
---

# Write a decision question a first-time reader can answer

**Core rule: the reader knows neither this run nor your internal words. Each item must let them decide from its own text alone.**

## Pitfalls (read first)

- **Complete facts come before shortness.** Give every fact the decision needs, even if the text gets longer. Say what a thing is and why it matters before you name it.
- **No pointers into the internals.** No `<path>:<line>` references, no positions inside records (such as "item 0" of some list), no internal keys, item numbers, or ids, no names of record files. Say in plain words what the thing is ("the function that computes the average", not a file and a line). References that a machine checks (deciding sources, grounds, evidence) belong in their own fields, not in the text a person reads.
- **One point, one item.** When the same point comes up from several angles (a narrowed capability, the policy, how the world solves it), raise it once and mention the other angles inside that one item.

## The shape of an item

In this order, each part as its own sentence:

1. **Title**: what is to be decided, said so that a person can answer it, as one short line.
2. **Now**: the current state, with the fact that makes it a question.
3. **Proposal**: what would be done.
4. **Cost**: what that costs, and whether and how it can be undone.
5. **Recommendation**: which answer you recommend, and why.

When the item is split over several fields, put each part in the field that holds it and keep this order across the fields. A mark that names why a person is asked (for example, which of the cases for asking applies) is not an internal reference: keep it first and put "Now" right after it.
