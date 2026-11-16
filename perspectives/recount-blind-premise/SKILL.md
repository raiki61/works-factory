---
name: recount-blind-premise
description: When an eye that had no tools concluded that the question to solve does not stand, finds the one assumption outside the purpose text that the conclusion rests on and re-counts it against the actual state of the repository — refuting it with evidence when it is false, and stopping to ask a person when it is true or cannot be refuted by measurement, because all remaining work depends on that answer. Use when an independent design or a blind review says "this is already solved", "the premise is false", "no change is needed", or when asked to "check that assumption against the repo".
---

# Re-count the assumption behind "the question does not stand"

**Core rule: name the one assumption that would bring the conclusion down if it were false, and re-count it against the actual state — not against the purpose text and not against your own expectation.**

Here "the purpose text" is the text, given when the work was requested, that says what is to be achieved. An eye with no tools (a reviewer that cannot open the repository or the web and thinks only from the text it was given) that concludes "the question does not stand" mixes into its grounds assumptions from outside the purpose text, such as "it is already met trivially by an existing mechanism" or "one deploy is one repository". Those can be measured. This perspective measures them.

## Pitfalls (read first)

- **Pick the load-bearing assumption.** When several are mixed, take the one that supports the conclusion and would bring it down if false. Showing a side assumption false proves nothing.
- **If the conclusion still stands on the others, it is not refuted.** Say which assumption you showed false and which remained, and send it to a person.
- **Do not move the purpose.** What you found goes into the constraints as new measurements; the purpose stays as it is.
- **A missing input is not a refutation.** If the conclusion is empty, the assumption cannot be read out, or the repository cannot be read, say what is missing and send it to a person.
- **The fix made in this same piece of work is not something to ask about.** Where the working tree differs from the version before the fix, use the list of files the fix changed (if you were given one) to tell whether a difference is that fix or the change under review (for example a pull request's own diff); do not turn it into a question for a person.
- **Base the judgment on what you were given, what you read yourself in the repository, and primary sources.** Try to refute, not to confirm.

## Re-count

1. Read the conclusion and its grounds, the original purpose, and the measured constraints.
2. Name the assumption.
3. Check it against the actual state: the files and lines, the measured test outcomes, the primary sources.
   - A line that gives only a count of tests whose names were not shown is evidence neither that existing tests cover a point nor that they do not. Do not read it either way.
   - Red to green, green to green, and the other transitions of the measured tests mean what they say; when the change is measured from the version a pull request branched from and comes out empty, the fix may have undone the pull request's own changes; it does not mean nothing was fixed.
4. Write the evidence that decided it: the files and lines you read, the primary sources you read.

## Outcome

- **The assumption is false**, and the conclusion falls with it: state the fact you showed and the measurements to add to the constraints. The design is then made again with those measurements, in a later pass; the question stays held until that later pass is judged.
- **The assumption is true, or the grounds close inside the purpose text** and cannot be refuted by measurement: stop and ask a person, whatever other blockers there are, because all the remaining work depends on that answer. State the question in one sentence: what it decides.

Works well with (optional; this file is complete without them): a separate, general stance for any reviewer whose verdict the caller cannot overrule (judge only from what was given and read, try to refute, say when input is missing, leave nothing out silently).
