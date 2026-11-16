---
name: procedure-trace
description: Traces the procedures a change touches — procedure documents such as a README, scripts, and CI definitions — by running them where they can be run without changing state, and by simulating the rest in your head, step by step from the initial state as a first-time reader would — tracking at each command whether its prerequisites (resources, installed tools, environment variables, working directory) were set up by earlier steps, what happens when implicit environment state (current cluster context, logged-in account, default branch) differs from what was assumed, and how far a run in the wrong environment would reach — and returns every step that could not be confirmed on a real machine as an unmeasured hypothesis. Use when a change edits setup or run instructions, scripts, or CI, or when asked "would these steps work from scratch", "trace this procedure", "does the README still run", "does this script assume something".
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

## What to trace

- **Step by step from the initial state**: assume a first-time reader with no context runs the steps from the top in order. At each command, check that its prerequisites (resources, installed tools, environment variables, working directory) were established by earlier steps, tracking the state as you go.
- **Implicit environment state**: list the state a command silently relies on (the current context of a cluster tool, the logged-in account, the default branch, and the like) and ask what happens if it runs in a state different from the one assumed.
- **Blast radius**: how far the damage reaches when the procedure runs in the wrong environment, and whether a guard (a check before running, an explicit context) prevents it.

## Before submitting a finding

- **Mechanism**: one sentence on the causal chain.
- **Measurement**: run what can be run; otherwise say "unmeasured" and present it as a hypothesis.
- **Refute it yourself first**: if you cite a rule, check that its condition applies and read the surrounding reality; submit only what you could not kill.
- **False-positive estimate**: one line on when the finding would be wrong.

Works well with (optional; this file does not need it): a perspective that sets the stance of a read-only investigator who goes to primary sources.
