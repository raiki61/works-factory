---
name: multi-lens-collect
description: Starts a declared set of review tools on one diff by name, collects their findings unscored, and records one honest row per tool so that a tool that never started cannot pass as one that found nothing. Use when asked to "run every reviewer on this diff". Not for judging or ranking the findings.
---

# Run several review lenses on one diff and collect what they find

**Core rule: one row per declared lens, without exception — and a lens that was not started, or whose answer never arrived, must never look like a lens that looked and found nothing.**

Why: if rows could be left out, a lens that was never started passes in the same form as "looked and found nothing" (measured once: the type-design lens was not started three reviews in a row, and nothing in the record turned red).

## Pitfalls (read first)

- **Start every lens one by one, by name.** Do not put an umbrella reviewer in between that decides which lenses to run. Its routing depends on the shape of the diff (error handling, type definitions, presence of tests), but the classes the lenses catch — checks silently disabled, guards that became always true, designs that hold invariants in flat values, gaps in behavior coverage — appear regardless of that shape.
- **Pass the target to every detector explicitly.** If you do not, each one rebuilds its own default target, and empty findings about something else enter the record in the same form as "looked and found nothing". A version range does not include the working tree; pass file paths when the change is in the working tree.
- **Only collect; do not score, settle labels, or weed out false positives.** Weeding out is the job of a later refutation. Do not carry a lens's own verdict into the findings, not even inside the text.
- **Change nothing.** Do not change a single character of the target's working tree, its head commit, its branch, or the files version control ignores; others may be working on the same working tree at the same time. Call any lens that can go as far as fixing only in a form that forbids fixing, and do not call a lens whose job is to apply changes instead of reporting them. Forbid fixing with the sentence "do not change the working tree" — do not write the spelling of a forbidden flag (the command-line option of the tool that posts comments or applies fixes, typically a word starting with `--`), not even inside a sentence that says not to use it: the tool may read it as the flag (seen once: a fix flag written inside a prohibition was taken).
- **Work from what you were given.** You may be given only the diff, the list of changed files, and the review viewpoints, without the request or other material; then do not guess what is missing to fill it in.
- **Do not turn something missing into "not applicable".** A lens whose call failed is a failure, written with the call you made and the error it returned.
- **Point at lines of the current file, not of the diff.** Lines of a diff (patch) file are not lines of the file, and a person cannot open that place. For a finding seen in the diff, read the file and confirm the line before you write it; if you cannot read files, write the path with a function name or similar instead of a line you cannot confirm.

## Steps

### Which lenses to start

- The declared lenses are the list of lenses handed to you with the task (the owner's set below is an example of what it holds). Use the lens name exactly as the list spells it. Do not add lenses that were not declared; they are not counted.
- A lens that must run is always started. An optional lens whose condition for applying holds must be started too; one whose condition does not hold need not be.
- Do not write a lens's result from an earlier review as if you had started it now; in a first review, start every lens in this one.

### What each finding must carry

Read the review viewpoints (labels and viewpoints come from there); if the target repository has its own review viewpoints, read those too. Writing submission criteria in a viewpoints file does not make them reach a lens. Put them into the instructions you give each lens:

- **Mechanism**: one sentence on the cause in the code.
- **Measurement**: run what can be run; if you cannot, say "not measured" and submit it as a hypothesis.
- **Self-refutation before submitting**: if it cites a rule, check whether the rule's condition applies, read the surrounding facts, and submit only what you could not refute.
- **Estimate of false positives**: one line on when it would be wrong.

### The owner's set of lenses

What each lens is for, in the owner's set:

- **A general code review** that covers both compliance and bug detection. Do not drop it.
- **Simplification** (reuse, simplification, efficiency, and altitude — whether a piece of code sits at the right level or layer): one lens and one row; start each of its viewpoints and have them return findings only. By default it rewrites the working tree, so call it only in the form that forbids fixing.
- **Silent failures**: checks that are silently disabled and failures that are swallowed.
- **Type design**: designs that hold invariants in flat values; routing by the shape of the diff does not reach this class.
- **Test coverage**: behavior coverage; nothing else looks at it.

### When an answer does not arrive or a call fails

- **Started, but its answer did not reach you** (for example the tool reports only that it completed): this is "not seen", not "found nothing". If starting it again is known to return the same form (seen with one review skill whose results were lost every time because of how it was started), do not start it again; it only costs time.
- **An optional lens whose call failed**: the collection waits for a person to decide about that lens.
- **A lens that must run and whose call failed**: start it again. Do not hand it to a person on your own, even when you find that the lens is not installed; whoever runs you decides whether to hand it over.

## Done when

- Every declared lens has exactly one row, with whether it was started; rows of one lens are merged into one, and no undeclared lens has a row.
- Every lens that must run, and every optional lens whose condition holds, was started.
- No row reads "found nothing" unless the lens was started, its answer arrived, and it found nothing.
- Every finding a lens submitted is in its row; none was dropped or scored.
- Nothing in the working tree, the head commit, the branch, or the ignored files changed.

## How to report

One row per declared lens, under its name as the list spells it, saying whether you started it:

- **Started and found something**: the findings, all of them; drop none (the lens refutes its own candidates before submitting; you do not weed out what it submitted). Each carries its mechanism, measurement, and estimate of false positives, and points at a line of the current file.
- **Started and found nothing**: that it was started and found nothing, and what it looked at. A row with neither findings nor a reason cannot be told from a lens that was not started.
- **Not started, or does not apply**: why.
- **Started, but its answer did not reach you**: that the text did not arrive, and what target you passed. Do not write "found nothing" — that makes something not seen look like zero findings.
- **A call that failed**: the call you made and the error it returned. For an optional lens, also mark the collection as waiting for a person to decide about that lens, with the reason.

## Example

Input: four declared lenses on a diff in the working tree: a general code review and silent failures (both must run), type design (optional; its condition — the diff defines a type — holds), and test coverage (optional; its condition does not hold).

Reply:
- General code review — started, passed the changed file paths; its answer arrived with only "completed" and no text: not seen; target passed: the two changed files.
- Silent failures — started; one finding: an error is caught and dropped (mechanism, not measured, wrong if the caller logs it), at a line of the current file.
- Type design — started; found nothing; looked at the two type definitions in the diff.
- Test coverage — not started: its condition does not hold for this diff.

## Works well with

- A written set of review viewpoints with criteria for submitting a finding.
- Rules that keep the target's names out of queries sent to outside services (web searches, fetched URLs).
