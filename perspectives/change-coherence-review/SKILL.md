---
name: change-coherence-review
description: "Reviews whether a finished diff lines up with the rest of the repository: callers updated, declarations matched by uses, connected sides kept in step, the neighbouring code's own mechanism used. Use when asked \"did we update every caller\" or whether a change fits the code around it. Not for comparing code with outside libraries or standards, nor for counting how many places know a concept."
---

# Review a change for coherence across the repository

**Core rule: does the whole become simpler, while it still meets the purpose and the guarding mechanisms keep working? Measure simplicity not by line count but by the number of places that know a design concept.**

This rule is the axis for judging; this review does not count those places itself. It uses a count only when one is given to it (the last item of "Homes of concepts").

Coherence here means the range the diff touched: whether what changed lines up with what already exists (naming, conventions, interfaces, documents kept in step). Cross-cutting risks the diff did not touch are a different perspective.

Two checks are done independently of each other: (1) consistency across the repository; (2) bypasses of standard mechanisms, where the change does by hand what the code around it does through a shared mechanism.

## Pitfalls (read first)

- **Not found in the repository is not undefined.** Before calling a name undefined, consider that an outside runtime (a framework, the operating system, CI) provides it.
- **What the neighbours actually use is the standard,** not the ideal a document describes — and a mismatch between those two is a finding in itself.
- **Do not start from other reviewers' findings.** When findings are shared, every reviewer anchors on that frame and stops noticing a mechanism that the neighbouring code bypasses. Look with your own eyes first.
- **Learn the conventions afresh** from the target's primary sources: the README, lint settings, package manifests, CI definitions, and the neighbouring code. Do not carry them over from an earlier look as settled. If the target repository has its own review guide, read it too.
- **The diff is where you start looking, not where you stop.** Read dependencies, neighbouring code, and callers as far as you need to understand the change.
- **"Did not look" is not "found nothing".** Say what range you looked at and what range you did not. If you stopped because of volume or time, say where you stopped. Otherwise a silent omission is read as "none".
- **Read only.** Do not change the working tree. Read a fixed version, not one that may move while you read; if you read the working tree, make sure nobody changes it meanwhile, so the line numbers you write are the real ones.
- **Build the set from the diff, not from earlier findings.** List every place, one by one.
- **One use of the mechanism in a file is not "no bypass".** Judge each place (especially user-facing string literals) on whether it goes through the mechanism, not on whether the file imports it.
- **Do not raise a home you cannot point to.** What you cannot name is not raised as a finding; say so.

## Steps

### Homes of concepts

For each concept the diff touches, check its home (the one place that holds it) inside the target repository.

- If the repository has a map of where concepts live, take its lines as the truth. The map of the folder that holds the file under review is the one that counts.
- If not, find the home from the repository's own structure: the README, module boundaries, places that hold the same word as a constant.
- If the diff writes a concept outside its home, or holds the same concept again in a form different from its home, and you can name the home's path and line, it needs a redesign: write the concept's name, its home, and the place outside.
- Say which maps you read (or which homes you found from the structure), and which concepts' homes you could not find.
- If you were given a measurement of the structure after the change (counts of the places that know each concept), also check the places it says grew.

### Repository-wide checks

- **Declaration and use**: for a declarative change (a schema definition, a function signature, a type definition, a settings schema, an enumeration of literal values), find its uses by search and check that they match, with nothing missing or extra.
- **Bypassing the standard mechanism**: a bypass leaves no symbol undefined, so declaration-and-use checks do not catch it. Search and read the files near the diff to find the mechanism they use as standard for the diff's domain, and list every place where the diff re-implements the same kind of processing by hand instead of going through it.
- **Connected sides left behind**: the existing sides of each connection the change creates or alters (callers, callees, shared state, conventions) follow it: tests, callers, documents.
- **Semantic consistency**: identifiers that describe a contract (type annotations, dictionary keys, enumeration values) match existing contracts of the same kind and the actual usage.
- **Comments and descriptions**: setting comments match the values implemented; file paths in the change's description match.
- **One default across documents**: extract into a table the recommendations and defaults (tools, clusters, procedures, versions) that the documents, scripts, and settings the change touches present to the reader, and compare them. Treat a recommendation in free text as a declaration too. A semantic split ("the main subject of one sibling document never appears in the other", "the recommended one and the one verified on a real machine are different") does not show up in string matching; find it by extracting and comparing.
- **Collision with other open changes**: check other open change requests that touch the changed files: (a) whether a gap you point out is already being handled in another, and (b) whether the fix you propose collides with a rewrite of the same function or area that an unmerged change is leading. Where another change leads that area, take it out of this change's scope and hand the fix to that change as a comment on it, not as a new issue.

## Done when

- Both checks were done, each without the other's or other reviewers' findings, and every place was listed from the diff.
- Each finding has: **the mechanism** (one sentence on the causal chain in the code — not just pointing at a symptom); **a measurement** (run what can be run; if you cannot, for example because you can only read, say it was not measured and submit it as a hypothesis); **a self-refutation** done first (if you cite a rule, check that its condition applies here, and read the actual neighbouring code; submit only the findings you could not kill); and **a false-positive estimate** (one line on when the finding would be wrong).
- The maps read, the homes not found, and the range looked at and not looked at are all written.

## How to report

Keep consistency findings and bypass findings in two separate lists. For each finding: where (a path and a line in the current file, confirmed by reading it — not a line number inside the patch), what is wrong, the mechanism, whether it was measured, and when it would be a false positive. If the input is not enough (for example you cannot read the diff), say that neither check was done and what is missing.

## Example

Input: a diff adds a handler whose error message is a string literal; the neighbouring handlers pass every user-facing message through a shared translation helper.

Reply: Bypass findings: the handler's message line (path and line in the current file) is a literal that does not go through the translation helper the neighbours use. Mechanism: the literal is returned as it is, so it is never translated. Measured: no (read only), a hypothesis. False positive if: the message is never shown to users. Consistency findings: none. Looked at: the diff and the neighbouring handlers; not looked at: the tests.

## Works well with

- A view that looks, around a change, for the cross-cutting risks the diff did not touch.
- A stance for a separate, read-only inspector of a change.
