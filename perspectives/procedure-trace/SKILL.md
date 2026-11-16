---
name: procedure-trace
description: Traces the procedures a change touches (README steps, scripts, CI definitions) by running what can safely be run and simulating the rest from a clean start, checking each command's prerequisites. Use when asked "do these setup steps still work from scratch". Not for running a user-visible code path to observe its values.
---

# Trace a changed procedure by running it

**Core rule: do not check only that the document agrees with itself. Confirm a procedure by running it, not by reading it; where you cannot run it, simulate running it. When reading and running disagree, the run is right.**

Missing prerequisites and the wrong environment slip past reading; they are usually found only when the procedure is run on a real machine.

## Pitfalls (read first)

- **Assume the reader has no context** and starts from the initial state.
- **Read the full text of every changed procedure document, script, and CI definition** before you follow it — not just the changed lines.
- **Run nothing that changes state.** Run the instruments that already exist (the test suite, existing check scripts) only if they do not rewrite files; do not create files yourself. Whatever you could not confirm on a real machine is returned as unmeasured, as a hypothesis.
- **When a command is refused or stopped**, return that step as unmeasured, with the command you ran and how it was refused. Do not respell the command to get it through.
- **Do not install or download to make a run possible.** Run with the tools already present.

## Steps

### What to trace

- If the target repository has its own review guide, read it too.
- **Step by step from the initial state**: assume a first-time reader with no context runs the steps from the top in order. At each command, check that its prerequisites (resources, installed tools, environment variables, working directory) were established by earlier steps, tracking the state as you go.
- **Implicit environment state**: list the state a command silently relies on (the current context of a cluster tool, the logged-in account, the default branch, and the like) and ask what happens if it runs in a state different from the one assumed.
- **Blast radius**: how far the damage reaches when the procedure runs in the wrong environment, and whether a guard (a check before running, an explicit context) prevents it.

## Done when

- Every changed procedure was followed from the initial state, step by step, with the state tracked.
- Each step was run, or returned as unmeasured with the command and how it was refused or why it was not run.
- Each finding has: **the mechanism** (one sentence on the causal chain); **a measurement** (run what can be run; otherwise say "unmeasured" and present it as a hypothesis); **a self-refutation** done first (if you cite a rule, check that its condition applies and read the surrounding reality; submit only what you could not kill); and **a false-positive estimate** (one line on when the finding would be wrong).

## How to report

The findings, each with the four items above, and every step you could not confirm on a real machine as an unmeasured hypothesis, with the command and how it was refused. Point to a place by its path and a line number in the current file, confirmed by reading it — not a line inside a patch; if you cannot read the file, give the path and a function name instead.

## Example

Input: a change edits a README's setup steps. Step 3 runs the database migration; the step that creates the database was moved below it, to step 5.

Reply: Finding: a first-time reader following from the top fails at step 3, because the database it needs is created only in step 5. Mechanism: the move put the creation after its first use. Measurement: unmeasured (the migration changes state), a hypothesis. False positive if: a database exists by default in a fresh environment. Where: the step 3 line of the README in the current file.

## Works well with

- A stance for a read-only investigator who goes to primary sources.
