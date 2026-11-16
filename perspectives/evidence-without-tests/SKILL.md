---
name: evidence-without-tests
description: Gives evidence for a change no test can show red-to-green (documents, instructions to an AI, notes, setting values, CI settings, types) by checking it per kind of change — names, paths, links, and quoted headings resolve in the real tree and the text reads on its own to a first-time reader; instructions are actually rendered with every hole filled and every copy matching; settings pass their validators; notes and types pass the static checks — and writes down what was run, never "I re-read it". Use when a fix touches only documents, prompts, settings, or types, or when asked "how do you know this doc/config change is right", "verify a change that has no test".
---

# Evidence for a change no test can show

**Core rule: instead of red-to-green, check each kind of change you made with something you can run or search, and write down what you ran and what it showed. "I re-read it" is not evidence.**

## Pitfalls (read first)

- **Do not add, change, or remove tests for such a change.** The evidence is the checks below, not a test bent to touch the text.
- **Every reference you wrote must resolve in the real tree.** Section names, headings, file names, quotes of other documents: look each one up again in the current tree, spelled exactly as it is at the target. Prefer a link (relative path and heading) where one can be written, and check that it reaches the file and the heading. What you fix when one does not resolve is the reference you wrote.
- **A check you did not run is written as not run**, with the reason; never as passed.

## Checks by kind of change

- **Documents**: search to confirm that the names and paths you wrote exist. Links reach their targets (the file and the heading). Re-read from the top as a first-time reader who does not know the premises, and the text makes sense on its own (a cold read).
- **Instructions to an AI (prompts)**: actually render them, with the rendering mechanism if there is one, and see that every hole is filled and nothing breaks. If copies of the same text exist elsewhere, all of them match. Say that the changed instructions take effect from the next run and do not reach runs already in progress.
- **Settings, workflow definitions, CI**: run the validator of the tool that reads them and the repository's own settings checks, and they pass.
- **Notes and types**: run the static checks the repository has (type checks, lint, and so on), and they pass.

## What to write

One entry per kind of change you checked: the kind, and what you did (the searches you ran, the commands you ran and their results).
