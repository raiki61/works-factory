---
name: evidence-without-tests
description: Gives evidence for a change no test can show red-to-green (documents, AI instructions, settings, CI configuration, types) by checking it per kind and writing down exactly what was run. Use when asked "how do we verify a docs-only change". Not for code changes a failing test can cover.
---

# Evidence for a change no test can show

**Core rule: instead of red-to-green, check each kind of change you made with something you can run or search, and write down what you ran and what it showed. "I re-read it" is not evidence.**

## Pitfalls (read first)

- **Do not add, change, or remove tests for such a change.** The evidence is the checks below, not a test bent to touch the text.
- **Every reference you wrote must resolve in the real tree.** Section names, headings, file names, quotes of other documents: look each one up again in the current tree, spelled exactly as it is at the target. Prefer a link (relative path and heading) where one can be written, and check that it reaches the file and the heading. What you fix when one does not resolve is the reference you wrote.
- **A check you did not run is written as not run**, with the reason; never as passed.

## Steps

### Checks by kind of change

- **Documents**: search to confirm that the names and paths you wrote exist. Links reach their targets (the file and the heading). Re-read from the top as a first-time reader who does not know the premises, and the text makes sense on its own (a cold read).
- **Instructions to an AI (prompts)**: actually render them into the finished text with their values filled in, with the rendering mechanism if there is one, and see that every hole (a slot where a value goes) is filled and nothing breaks. If copies of the same text exist elsewhere, search for all of them and confirm that every one matches. Say that the changed instructions take effect from the next time they are used and do not reach work already under way.
- **Settings, workflow definitions, CI**: run the validator of the tool that reads them and the repository's own settings checks, and they pass.
- **Code notes (comments) and types**: run the static checks the repository has (type checks, lint, and so on), and they pass.

## Done when

- Each kind of change you made has its check run, and it passed — or it is written as not run, with the reason.
- Every reference you wrote resolves in the current tree, and every link reaches its file and heading.
- No test was added, changed, or removed for the change.

## How to report

One entry per kind of change you checked: the kind, and what you did (the searches you ran, the commands you ran and their results).

## Example

Input: a change renames a section of the setup guide and updates two documents that link to it.

Reply:

- Documents: searched for the old section name (0 hits) and the new one (3: the heading and the two links). Both links reach the file and the heading. Re-read the section cold: it reads on its own.
- No other kind of change was made.

## Works well with

- A reading of the text as a first-time reader who has none of its context.
