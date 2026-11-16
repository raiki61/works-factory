---
name: multi-lens-collect
description: Runs a declared set of review lenses (review skills and review agents) on one diff, starting each one by name and passing the target explicitly, collects what each finds without scoring it, and records one honest row per lens so that "not started" or "not seen" can never pass as "looked and found nothing". Use when several review tools should look at the same change, or when asked to "run all the review lenses on this diff", "collect the findings of every reviewer", "make sure each review tool actually ran".
---

# Run several review lenses on one diff and collect what they find

**Core rule: one row per declared lens, without exception — and a lens that was not started, or whose answer never arrived, must never look like a lens that looked and found nothing.**

Why: if rows could be left out, a lens that was never started passes in the same form as "looked and found nothing" (measured once: the type-design lens was not started three rounds in a row, and nothing in the record turned red).

## Pitfalls (read first)

- **Start every lens one by one, by name.** Do not put an umbrella reviewer in between that decides which lenses to run. Its routing depends on the shape of the diff (error handling, type definitions, presence of tests), but the classes the lenses catch — checks silently disabled, guards that became always true, designs that hold invariants in flat values, gaps in behavior coverage — appear regardless of that shape.
- **Pass the target to every detector explicitly.** If you do not, each one rebuilds its own default target, and empty findings about something else enter the record in the same form as "looked and found nothing". A version range does not include the working tree; pass file paths when the change is in the working tree.
- **Only collect; do not score, settle labels, or weed out false positives.** Weeding out is the job of a later refutation. Do not carry a lens's own verdict into the findings, not even inside the text.
- **Change nothing.** Call any lens that can go as far as fixing only in a form that forbids fixing, and do not call a lens whose job is to apply changes instead of reporting them. Forbid fixing with the sentence "do not change the working tree" — do not write the spelling of a forbidden flag (the command-line option of the tool that posts comments or applies fixes, typically a word starting with `--`), not even inside a sentence that says not to use it: the tool may read it as the flag (seen once: a fix flag written inside a prohibition was taken).
- **Do not read the request.** The one who collects is given only the diff, the list of changed files, and the review viewpoints — neither the request nor any other material — so that what the lenses look at is not narrowed to what the request expected.
- **Do not turn something missing into "not applicable". A lens whose call failed is a failure, written with the call you made and the error it returned.

## One row per lens

- The declared lenses are the list of lenses handed to you with the task (the owner's set below is an example of what it holds). Every declared lens gets exactly one row, including a lens that is optional or does not apply. Merge several rows of one lens into one. Use the lens name exactly as the list spells it. Do not add lenses that were not declared; they are not counted.
- In each row, record whether you started the lens.
- **Started and found something**: the findings, all of them; drop none (the lens refutes its own candidates before submitting; you do not weed out what it submitted).
- **Started and found nothing**: say that it was started and found nothing, and what it looked at. A row with neither findings nor a reason cannot be told from a lens that was not started.
- **Not started, or does not apply**: say why.
- **Started, but its answer did not reach you** (for example the tool reports only that it completed): say that the text did not arrive and what target you passed. Do not write "found nothing" — that makes something not seen look like zero findings. Do not start it again just to get the same form back.
- **An optional lens whose call failed**: write the failure in its row, and mark the collection as waiting for a person to decide about that lens, with the reason.
- **A lens that must run and whose call failed**: start it again. Do not hand it to a person on your own; handing over is decided by whoever runs you, after repeated failures.

## What each finding must carry

Read the review viewpoints (labels and viewpoints come from there); if the target repository has its own review viewpoints, read those too. Writing submission criteria in a viewpoints file does not make them reach a lens. Put them into the instructions you give each lens:

- **Mechanism**: one sentence on the cause in the code.
- **Measurement**: run what can be run; if you cannot, say "not measured" and submit it as a hypothesis.
- **Self-refutation before submitting**: if it cites a rule, check whether the rule's condition applies, read the surrounding facts, and submit only what you could not refute.
- **Estimate of false positives**: one line on when it would be wrong.

## The owner's set of lenses

What each lens is for, in the owner's set:

- **A general code review** that covers both compliance and bug detection. Do not drop it.
- **Simplification** (reuse, simplification, efficiency, and altitude — whether a piece of code sits at the right level or layer): one lens and one row; start each of its viewpoints and have them return findings only. By default it rewrites the working tree, so call it only in the form that forbids fixing.
- **Silent failures**: checks that are silently disabled and failures that are swallowed.
- **Type design**: designs that hold invariants in flat values; routing by the shape of the diff does not reach this class.
- **Test coverage**: behavior coverage; nothing else looks at it.

In the first round, a lens's result is not carried over from an earlier round: start it.

Works well with (for reference only; nothing here needs them): a written set of review viewpoints with criteria for submitting a finding, and rules that keep the target's names out of queries sent to outside services (web searches, fetched URLs).
