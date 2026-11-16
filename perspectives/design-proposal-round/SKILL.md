---
name: design-proposal-round
description: "Writes one draft of a design proposal for a question to settle before coding, so a person can judge it: premises, what exists now, reuse considered, and person-only questions with options and a recommendation. Use when asked to \"draft a design proposal\" for a theme rather than a defect. Not for planning the fix of a known defect."
---

# Write one version of a design proposal

**Core rule: give the person a proposal they can judge, with only the questions they alone can answer — and never write that the person decided something they did not.**

A theme is a design question to settle before anything is turned into code; it is not a defect to fix. A separate reviewer attacks each version of the proposal, and the person decides when the design is settled.

## Pitfalls (read first)

- **Read only.** Read the target and look things up; do not change files.
- **Read what the theme names.** It may name sections of design documents, and may carry research the person already asked for.
- **Keep the person's words as they are.** The person's own words are carried as written, not replaced with your reading of them. A relayed reading of the person is a reading, not their words.
- **Do not drop a person's answer silently.** For every answer, either say what you changed because of it or say why you did not use it.
- **Prefer adding to what exists over making something new.**
- **Do not ask what a rule already settles.**

## Steps

For the first version read "How to write the design" and "Compare with how the world solves it"; for a later version read "Later versions" as well.

### How to write the design

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

### Compare with how the world solves it

When there are practices for this class of problem, compare the design with them. Where the design departs from a practice, say why in that part's reason.

### Later versions

- Build on your previous version; keep what no hole and no answer asked you to change.
- Answer each hole the reviewer raised exactly once: fixed (say where you changed the design) or disputed (give the grounds).
- Give every answer of the person one entry: what you changed because of it, or why you did not use it.

## Done when

- No premise is marked as decided by the person unless you can say where they decided it.
- Every new part names the existing things you looked at first, or where you looked and found nothing.
- Every question left for the person changes what happens next; what a rule settles is recorded as decided.
- A reworked file's inventory covers every non-empty line, and every drop has a reason and an entry in what the design narrows.
- In a later version, every hole and every answer of the person has exactly one entry.

## How to report

Return the proposal in the order of the steps: question and purpose, premises, what exists now, parts, reuse, policy checks, decided items and real questions (with options, costs, gains, and your recommendation), changes, inventory of any reworked file, and what it narrows. In a later version, add one entry per hole (fixed and where, or disputed and why) and one per answer of the person (changed and where, or why not used).

## Example

Input: The theme asks how to let users choose the language of the reports. The person answered "keep the current language as the default." The target's rules say a new setting goes in the existing settings file.

Reply:
- Premise P1, decided by the person (their answer): the current language stays the default.
- Decided, not asked: where the setting lives — the target's rules put new settings in the existing settings file.
- Question Q1: should a report already written be rewritten when the language changes? Options: (a) no, only new reports — costs nothing, but old and new reports differ; (b) yes — keeps them alike, but rewrites files the user may have kept. Recommendation: (a), because it does not touch files the user kept.

## Works well with

- deciding what counts as recorded policy and how to treat a person's standing policy;
- comparing a request's means with how practitioners solve the same kind of work;
- keeping outside queries free of the target's names, and writing questions to a person so a first-time reader can decide from the text alone.
