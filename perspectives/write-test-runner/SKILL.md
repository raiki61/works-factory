---
name: write-test-runner
description: Writes a small runner script that runs a project's tests and writes each test's outcome as JUnit XML to a path given as its first argument, keeping the test command exactly as given, keeping the test tool's exit code, running every part of an "&&" chain even after one is red and merging their reports, writing one reserved error testcase when the tool exits red before writing any report, never synthesizing a report when the command could not be run at all, and refusing to produce a body for form's sake when it cannot tell how. Use when a pipeline needs per-test outcomes from a project whose test command does not write JUnit XML, or when asked to "wrap the test command so it writes JUnit XML", "make a test runner that reports every test".
---

# Write a test runner that reports every outcome

**Core rule: the runner must never lose a red. Keep the test command and its exit code as they are, and make every way the tests can fail show up in the report — but never invent a report for a command that could not run.**

## Pitfalls (read first)

- **Copy the given test command without changing a single character**, and only add after it the option that makes the tool write JUnit XML. A runner that holds the command as typed is the same thing as the command.
- **Exit with the test tool's exit code as it is** (non-zero if any test is red).
- **A tool that exits red before writing its report is a red, not "no tests".** Write one reserved testcase whose error says `exit <n>` and where the log is.
- **Exit codes 126 and 127 mean the command could not be found or run.** Write nothing to the report path then; the reader must see "could not be run", not a red test.
- **Do not produce a body for form's sake.** If you cannot decide how to make it write JUnit XML, or what to run, say so in one line (what you read and what was missing). Never assume green.

## The runner's contract

- It starts with the target root as its working directory.
- Its first argument is the absolute path to write the JUnit XML to.
- Arguments may follow (test files, test names, filter expressions). Pass them to the tool as they are whenever it can take them — that keeps the run short. If the tool cannot take them, drop them and run the whole suite (it checks the same thing).
- Its first line is a `#!` line.

## A chain joined only by "&&"

An option placed after the whole chain reaches only its last part, and a red part would stop the later parts. Write it part by part:

1. Copy each part unchanged, add the JUnit option, and have each part write to its own temporary file.
2. Run the later test parts even if an earlier part is red; keep each part's exit code.
3. If a part with the JUnit option exited 126 or 127, write nothing to the report path, and exit with that part's code.
4. Otherwise, after all parts ran, gather every report's test suites under one root and write it to the report path.
5. A part with the JUnit option that wrote nothing, whatever its exit code (0 included), is not dropped silently: put the reserved testcase in the gathered report once, listing every such part's number, exit code, and log place. Keep the other parts' outcomes.
6. A part that does not run tests (a build step) and fails stops the chain: exit with its code; unless it is 126 or 127, write a report holding the reserved testcase with that part's code and log place (the build failed before any test could report — a red, not a runner that cannot run).
7. Pass test-file arguments only to the parts that can take them; if you cannot tell which can, run every part whole.
8. Exit with the first non-zero code among the parts, or 0 if all are 0 (what the chain itself would return); a part that exited 126 or 127 wins, as above.

## When no test command is given

Decide the command from the CI definitions and the project's own declaration of how to run its tests. If the target has no tests yet, you may write a runner that runs the place the target's conventions put tests and, when it finds none, writes a JUnit XML with zero tests.
