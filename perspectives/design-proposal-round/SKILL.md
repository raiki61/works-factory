---
name: design-proposal-round
description: Writes one round of a design proposal for a design question (a theme to settle before anything is coded, not a defect) so that a person can judge it — question and purpose, premises marked as decided by the person or assumed, an inventory of what exists now, parts that prefer adding to what exists, the reuse considered, answers to the target's policy checks, questions only the person can answer (with options, costs, gains, and a recommendation) kept apart from what rules already decide, concrete changes, a line-by-line inventory of any file it reworks, and everything it narrows. Use when asked to "draft a design for this", "propose a design before we build", or to revise a design round after review holes and the person's answers.
---

# Write one round of a design proposal

**Core rule: give the person a proposal they can judge, with only the questions they alone can answer — and never write that the person decided something they did not.**

A theme is a design question to settle before anything is turned into code; it is not a defect to fix. A separate reviewer attacks each round, and the person decides when the design is settled.

## Pitfalls (read first)

- **Read only.** Read the target and look things up; do not change files.
- **Read what the theme names.** It may name sections of design documents, and may carry research the person already asked for.
- **Keep the person's words as they are.** The person's own words are carried as written, not replaced with your reading of them. A relayed reading of the person is a reading, not their words.
- **Do not drop a person's answer silently.** For every answer, either say what you changed because of it or say why you did not use it.
- **Prefer adding to what exists over making something new.**
- **Do not ask what a rule already settles.**

## How to write the design

Work in this order, and keep each step apart.

1. **Question and purpose**: restate the question in one to three sentences, and what the design is for.
2. **Premises**: a premise the person decided names where they decided it (their answer, or a line of the theme). A premise you assumed says why you assumed it. When the design would change if an assumed premise turned out wrong, ask about it.
3. **What exists now**: before you design, list each thing the design touches or could reuse, with its place in the repository (path and lines).
4. **Parts**: one entry for each part you add or change.
5. **Reuse**: for each new part, the existing things you looked at first and why they are not enough. When you found nothing to reuse, say where you looked.
6. **Policy checks**: when the target's policy documents require checks before something is added, answer each, naming the rule and where the design answers it.
7. **Ask only what changes what happens next.** A question a rule already settles is not a question: record it as decided, with the rule that settles it and why. For each real question, write it so a first-time reader can follow, give at least two options, each with what it costs and what it gains, give your recommendation with its reason, and include the option of adding to what exists or doing nothing when it is a real option.
8. **Changes**: one entry for each place — where, what in one line, whether it adds, edits, reworks, or removes, and which parts it carries out. Each becomes a line of the request once the design is approved, so make it concrete enough to diagnose and plan from. Leave the rewriting detail and the tests to the planner.
9. **Inventory of a reworked file**: when a change reworks a file that exists now, list its current content so nothing is lost. Cover every non-empty line of the file at the version the design starts from, with ranges that do not overlap; give each range its gist and where it goes (keep, move, merge, or drop, and what receives a move or a merge). Do not drop a line whose purpose you cannot tell; keep or move it. A drop needs a reason and an entry in what the design narrows.
10. **What it narrows**: every place the design narrows what the target can do now, with what decided it (a rule or the person), or why it is not decided.

## Compare with how the world solves it

When there are practices for this class of problem, compare the design with them. Where the design departs from a practice, say why in that part's reason.

## Later rounds

- Build on your previous round; keep what no hole and no answer asked you to change.
- Answer each hole the reviewer raised exactly once: fixed (say where you changed the design) or disputed (give the grounds).
- Give every answer of the person one entry: what you changed because of it, or why you did not use it.
- When you correct part of a round, return every entry of a list you correct, not only the changed ones.

Works well with: a perspective that says what counts as recorded policy and how to treat a person's standing policy, one that compares a request's means with how practitioners solve the same kind of work, one that keeps outside queries free of the target's names, and one that writes questions to a person so a first-time reader can decide from the text alone.
