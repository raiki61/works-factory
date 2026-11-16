---
name: write-test-runner
description: Writes a small test runner script that runs the given test command unchanged and writes each outcome as JUnit XML, keeping the exit code and never synthesizing a report. Use when a project needs per-test results in JUnit XML and has no test runner script yet. Not for repairing an existing test runner that breaks tests.
---

# Write a test runner that reports every outcome

**Core rule: the runner must never lose a red. Keep the test command and its exit code as they are, and make every way the tests can fail show up in the report — but never invent a report for a command that could not run.**

## Pitfalls (read first)

- **Copy the given test command without changing a single character**, and only add after it the option that makes the tool write JUnit XML. This holds for one command, and for commands joined by `;`, `||`, or a pipe (or a mix of them, `&&` included), all copied as one command with the option added once, after the whole of it. Only a chain whose every top-level join is `&&` is written part by part (below).
- **Exit with the test tool's exit code as it is** (non-zero if any test is red).
- **A tool that exits red before writing its report is a red, not "no tests".** Write one reserved testcase whose error says `exit <n>` and where the log is. The reserved testcase carries a classname and name fixed in advance by whoever reads the report (they give them to you, the writer of the runner, along with the test command; they are not arguments of the runner, so write them into the runner as fixed values), copied exactly as given, so that the reader can tell it from a test result.
- **Exit codes 126 and 127 mean the command could not be found or run.** Write nothing to the report path then; the reader must see "could not be run", not a red test. When the command is one tool, a JUnit XML file the tool did write is left as it is.
- **Do not produce a body for form's sake.** If you cannot decide how to make it write JUnit XML, or what to run, say so in one line (what you read and what was missing). Never assume green.

## Steps

Read "The runner's contract" always; read the subsection on a chain joined only by "&&" when the given command is such a chain, and "When no test command is given" when there is none.

### The runner's contract

- It starts with the target root (the root folder of the project whose tests it runs) as its working directory.
- Its first argument is the absolute path to write the JUnit XML to.
- Arguments may follow (test files, test names, filter expressions). Pass them to the tool as they are whenever it can take them — that keeps the tests quick to run. If the tool cannot take them, drop them and run the whole suite (it checks the same thing).
- Its first line is a `#!` line.

### A chain joined only by "&&"

An option placed after the whole chain reaches only its last part, and a red part would stop the later parts. Write it part by part:

1. Copy each part unchanged, add the JUnit option, and have each part write to its own temporary file.
2. Run the later test parts even if an earlier part is red; keep each part's exit code.
3. If a part with the JUnit option exited 126 or 127, write nothing to the report path, and exit with the code of the first such part.
4. Otherwise, after all parts ran, gather every report's `testsuite` elements under one `testsuites` root element and write it to the report path.
5. A part with the JUnit option that wrote nothing, whatever its exit code (0 included), is not dropped silently: put the reserved testcase in the gathered report once — its `exit <n>` is the code the chain itself exits with — listing every such part's number, exit code, and log place. Keep the other parts' outcomes. Do not do this for a part that does not get the JUnit option.
6. A part that does not run tests (a build step) and fails stops the chain: exit with its code; unless it is 126 or 127, write a report holding the reserved testcase once, with that part's code, its number, and its log place (the build failed before any test could report — a red, not a runner that cannot run).
7. Pass test-file arguments only to the parts that can take them; if you cannot tell which can, run every part whole.
8. Exit with the first non-zero code among the parts, or 0 if all are 0 (what the chain itself would return); a part that exited 126 or 127 wins, as above.

### When no test command is given

Decide the command from the CI definitions and the project's own declaration of how to run its tests. If the target has no tests yet, you may write a runner that runs the place the target's conventions put tests and, when it finds none, writes a JUnit XML with zero tests.

## Done when

- The runner holds the given command (or each part of an "&&" chain) unchanged, with only the JUnit option added.
- It exits with the tool's exit code (or the chain's), and writes nothing when the command could not be found or run.
- Every red shows up in the report: a tool or part that exited red, or wrote nothing, has the reserved testcase.
- Its first line is a `#!` line.
- Or, when you could not decide how, there is no body and one line says what you read and what was missing.

## How to report

Either the runner's body, or that you made none and, in one line, what you read and what was missing. Keep commands, option names, file names, and paths as they are.

## Example

Input: the test command is `build && test-a && test-b`; only `test-a` and `test-b` run tests.

Reply: a runner that

- runs `build`; if it fails, exits with its code and, unless that is 126 or 127, writes one reserved testcase naming part 1 and its log;
- runs `test-a` and `test-b`, each unchanged with the JUnit option and its own temporary file, the second even if the first is red;
- gathers both reports under one root, adds the reserved testcase once if either wrote nothing, and exits with the first non-zero code.

## Works well with

- A way of repairing a test runner that breaks tests which pass when run on their own.
