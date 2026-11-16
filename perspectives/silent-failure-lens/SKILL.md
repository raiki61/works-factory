---
name: silent-failure-lens
description: Reviews a finished change (its diff) through one viewpoint only — failures that end up silent — reading the diff together with its callers and readers, and reports each finding with its place, a verbatim quote of the current text, and what fails silently and who cannot notice it. Use after a change is written and before it is accepted, or when asked to "look for silent failures", "check how this change handles errors", "review this diff for swallowed errors".
---

# Look at a change for failures that go silent

**Core rule: look only through this one viewpoint, and for every finding say what fails silently and who cannot notice it.**

The viewpoint itself — what counts as a failure that goes silent — is defined by the silent-failure review agent the owner relies on (`silent-failure-hunter` of the `pr-review-toolkit` plugin). When that definition is available, it is the viewpoint; this file does not copy it. What this file keeps is the owner's stance for applying such a viewpoint to a change.

## Pitfalls (read first)

- **You are a fresh eye.** Do not take over the reasoning of whoever wrote the change, or the history of how it was decided. Read the change as it is.
- **Read only.** Do not change a single character of the working tree while you review.
- **The diff is a starting point, not a border.** Read the callers of what changed and the readers of what it writes. A failure is often silent only from where the caller stands.
- **Report only findings inside the changed files.** What you read outside them is evidence, not a place to raise findings.
- **A finding is a candidate.** Someone else confirms it before it counts as a defect; write it so that they can check it.

## What to look at

Read the change through the viewpoint above. When the agent's definition is not available, the minimum it covers is: a failure that is caught and dropped; a fallback or default that the caller cannot tell from a real result; a check or a step that turns a failure into an apparent success; and a failure reported only where nobody reads it. (This minimum was written as a placeholder when the perspective was saved. It is not the agent's definition and does not replace it.)

## How to report

For each finding:

- **Where**: the path of the changed file, exactly as the change lists it.
- **Quote**: a string that exists in that file as it is now, copied as it is, so that the reader can find the spot.
- **Why**: what fails silently, and who cannot notice it.

If there is no finding, say so, and say what you read that lets you say there is none.
