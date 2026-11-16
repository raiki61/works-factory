---
name: repair-test-runner
description: Repairs a test runner script that writes JUnit XML when tests break inside it before reaching their content while the project's own test command passes alone, treating the runner as the broken side and keeping its contract. Use when "the tests pass on their own but fail through the runner". Not for writing a new test runner from scratch.
---

# Repair a test runner that breaks tests the project's own command runs fine

**Core rule: if the project's own test command passes alone but the same tests break before reaching their content when run through the test runner, the test runner is what is broken — not the tests.**

## Pitfalls (read first)

- **Do not touch the tests.** They are not the broken part.
- **Read narrowly.** Read the test runner's body, the logs of both runs, the project's own declaration of how to run its tests if there is one, its CI definitions, and the test configuration files those name. Do not search further.
- **Do not run the tests, install dependencies, or write files** while diagnosing. A short command that prints a test tool's usage, to see whether it can write JUnit XML, is fine.
- **If you cannot tell what broke them, say so** and say what you read. Do not guess a rewrite.

## Steps

### What to look for

From the log, find what the test runner does that the test command alone does not. A common cause: it changes the environment the tests start in — the module search path, the working directory, the interpreter, or other variables — so that something the tests need is no longer found.

### How to fix

Keep what the test runner must do — write JUnit XML where its first argument says, pass the arguments after it through to the tests, keep the tests' exit code — and stop doing the thing that broke the tests.

## Done when

- You found, from the log, what the test runner does that the test command alone does not, or you said you cannot tell.
- The tests are untouched, and you ran no tests, installed nothing, and wrote no files while diagnosing.
- The new body still writes JUnit XML where its first argument says, passes the later arguments through, and keeps the tests' exit code.

## How to report

The new body of the test runner and what it stopped doing (the cause you found in the log). If you cannot tell what broke the tests, give no body; say so and say what you read.

## Example

Input: the project's own test command passes alone. Through the test runner, every test errors before its content with "module not found". The runner's body changes to its own folder before running the command.

Reply:

- Cause: the test runner changes the working directory to its own folder, so the tests' modules are not found from there.
- New body: runs the command from the target's root, as the command alone does; it still writes JUnit XML to the first argument, passes the rest through, and keeps the exit code.
- Read: the runner's body, the logs of both runs, the CI definition.

## Works well with

- A view for writing a test runner that reports every test's outcome as JUnit XML.
