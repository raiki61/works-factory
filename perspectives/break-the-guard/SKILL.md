---
name: break-the-guard
description: Judges a check, gate, or test by asking how it could be silently defeated, and proves it turns red on a deliberately injected violation. Use when a change adds or alters a CI job, an assertion, or a hook, or when asked "would this check actually catch it". Not for proving that a code fix closed its defect.
---

# Ask how a guard could be fooled, and prove it turns red

**Core rule: for a check, gate, or guard, do not ask first "is it written correctly". Ask "how could it be silently defeated, and what input or state would make it give a false pass". A guard counts as verified only when, for each of its arms, three things are seen: a violation made for that arm turns it red, an unbroken copy is green, and the run is shown to pass through the line that arm guards.**

Words used here:

- **A guard (fence)**: a check, gate, assertion, or test that is meant to stop a kind of mistake.
- **Red / green**: the guard fails (catches something) / the guard passes.
- **The guarded set**: everything the guard claims to protect. **An entrance** is one route by which something enters that set (one place the rule can be broken).
- **An arm**: one conditional branch of the guard — one condition under which it should fail — and the one violation deliberately injected for it (a mutation: a deliberate break put into a copy of the code), written so the guard should go red on it. **A runner** is the tool that applies the arms one at a time; **the control** is the run with no violation injected, which must stay green; **marks** are what the runner shows to tell which arm made the guard go red; **to fire** an arm is to apply it and run the checks.
- **The target repository**: the repository whose guard you are judging.

## Pitfalls (read first)

- **Run rather than read.** For anything executable (procedures, scripts, gates, tests), confirm by the result of running it, not by reasoning about it. When reading and running disagree, running is right. Do not treat as working a protection you have never once seen go red.
- **The two principles stand above the listed checks.** "Run rather than read" and "ask how it could be fooled" are the principles; the checks below are examples of applying them. If you find a place that violates either principle in a form not listed, you may raise it even though no listed check names it.
- **A red inside the covered part is not evidence of coverage.** Narrowness is not detected by seeing one case inside the cover go red.
- **One injection is not enough for coverage.** Count first every route into the set the guard binds, then inject one regression per entrance and watch it go red. An entrance that does not go red is not closed. (Measured once: a report said all 13 arms went red. Another reviewer then broke two of the same guards at other places, and both stayed green. One guard checked references to headings by the heading's word: there were 8 such references, and in 4 of them the same word also appeared in the body text, so a broken heading still matched. The other checked a constant by its name: 10 constants had that name, so breaking one still matched another. The red at one place had not shown that the guard covered the rest.)
- **A red from removing the whole check is not evidence that an arm is guarded.** (Measured once: the form the design forbade most strongly turned red when the whole check was removed, yet that arm had never been hit.) Make one violation per arm.
- **Run an unbroken copy once and see it green (the control).** If the harness itself is broken, every arm shows the same colour, and you can write the opposite conclusion.
- **A red is not evidence that the red came from the line you want to guard.** See "Proving it" below.
- **Never break the real working tree.** Do not change the working tree, the checked-out commit (HEAD), the branch, or the files version control ignores. For each arm, make a copy of the repository in a fresh temporary directory outside it, break the copy, and run the whole set of checks there. A copy inside the repository dirties the working tree; breaking a shared tree and restoring it cannot, in principle, be detected afterwards.
- **Do not kill the run from outside after a time limit.** (Measured once: a sub-agent fired all arms under a hard timeout and answered that it had written results when there were none.) Wait until it finishes; if other work shares the machine, run it at low priority.
- **If the answer to "how would I fool it" is not among the existing review points, that is itself a finding** — and a candidate for a new review point.

## Steps

### What to check when a change adds or alters a check

1. **Fail-closed**: when the check itself cannot run (a command fails, it runs only partly), does it go red?
2. **Empty is not a pass**: when the target is empty or has shrunk, can the result be told apart from "passed"? (Is there a check that the target is not empty? Where a run writes an empty result file on purpose to mean "there was nothing to check", could a target that shrank to nothing produce that same empty file by chance, and be read as that case or as a pass?)
3. **Platform defaults**: does a default of the execution platform swallow a failure? (For example, a CI platform's default shell that does not fail a pipeline on an inner failure unless told to.)
4. **The set is as wide as the name**: is the set the fence covers narrower than the range it claims? When a check's name, a comment, or a document says "protects X", it often covers only part of X. Three typical forms: the files to scan are listed by hand; the matching is a flat substring match; there is only one arm.

### Proving it

- Do not treat a new gate as working until you have deliberately made one violation it should catch and seen it go red — one per arm, and one per entrance into the guarded set.
- See the control green.
- **Show the run passed through the guarded line.** For each arm, make one more copy in which the value that the arm's branch produces — its error message, return value, or the line it writes to a log or result file — is replaced with a unique marker string, and see that the marker appears in the output or in the records the run leaves (logs, result files). If it does not, that scenario never passed through the guarded line. (Measured once: injecting a regression into a check of whether a value may be carried over left the checks green, and the marker did not appear either.)

### Use the repository's own mutation list and runner

- If the target has a list of arms and a runner, fire with them: on a copy, one at a time, and look at the control's green and its marks. Look for where they are and how to call them in what the target itself names (README, contributing guide, CI definitions, its own review guide); the runner's own help is the authority on its options.
- If the runner can build the report from what it fired, take that output as it is; do not rebuild it by hand. A throwaway script written on the spot silently drops arms whose replaced string disappeared when the code was rewritten, and nobody can fire the same arm next time. (Measured once: 25 arms dropped out on the first pass and 18 on the second.)
- If earlier results exist and the runner can carry them over, pass them and fire fewer arms. If the runner rewrites its results after each arm, a stop partway can be resumed by passing the same results.
- A diff that adds or fixes a fence adds or fixes its arms in the list in the same diff. Fixing the list is not the reviewer's job: if you find an arm that is missing or out of date, fire it by hand on a copy and record that the list needs it, so the fix includes it.
- In a repository with no list, do the steps above by hand on copies.

## Done when

- For each arm and each entrance, a violation on a copy was seen red, the control was seen green, and the marker was seen in the output or records.
- Every run was waited on until it finished, and the real working tree was never broken.
- Each of the four checks was asked of the changed guard.

## How to report

For each arm: the gate, the arm, whether red was confirmed, whether the control was green, and the evidence that the run passed through the guarded line. Point to a place by its path and a line number in the current file, confirmed by reading it — not a line inside a patch; if you cannot read the file, give the path and a function name instead.

## Example

Input: a change adds a check that every file in a hand-written list has a license header.

Reply: Arm "header missing": on a copy, removed one listed file's header; red. Control: green. Marker: replaced the failure message with a unique string; it appears in the output. Entrance "a new file": added a file with no header outside the list; stayed green. Finding: the set is narrower than the name (files listed by hand).

## Works well with

- A set of rules that keeps the reviewed repository's own names and text out of queries sent to outside services (web searches, fetched URLs).
