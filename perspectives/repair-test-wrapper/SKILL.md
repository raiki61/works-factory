---
name: repair-test-wrapper
description: Repairs a wrapper script that runs a project's tests and writes JUnit XML, when tests run through the wrapper break before reaching their content (no report, or setup errors) while the project's own test command passes alone — treating the wrapper as what is broken, finding from the log what it does differently (environment, module search path, working directory, interpreter), and keeping its contract. Use when "the tests pass on their own but fail through the runner", when a generated test runner gives no JUnit XML, or when asked to "fix the test wrapper, not the tests".
---

# Repair a test wrapper that breaks tests the project's own command runs fine

**Core rule: if the project's own test command passes alone but the same tests break before reaching their content when run through the wrapper, the wrapper is what is broken — not the tests.**

## Pitfalls (read first)

- **Do not touch the tests.** They are not the broken part.
- **Read narrowly.** Read the wrapper's body, the logs of both runs, the project's run declaration if there is one, its CI definitions, and the test configuration files those name. Do not search further.
- **Do not run the tests, install dependencies, or write files** while diagnosing. A short command that prints a test tool's usage, to see whether it can write JUnit XML, is fine.
- **If you cannot tell what broke them, say so** and say what you read. Do not guess a rewrite.

## What to look for

From the log, find what the wrapper does that the test command alone does not. A common cause: it changes the environment the tests start in — the module search path, the working directory, the interpreter, or other variables — so that something the tests need is no longer found.

## How to fix

Keep what the wrapper must do — write JUnit XML where its first argument says, pass the arguments after it through to the tests, keep the tests' exit code — and stop doing the thing that broke the tests.
