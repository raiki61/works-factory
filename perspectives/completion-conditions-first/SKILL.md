---
name: completion-conditions-first
description: Before any fix plan exists, writes one by one the conditions under which a request can be called complete — digging out the ones the request does not state (default behaviour unchanged, second and later rounds, failure, nobody answering, undo, combination with other options) — writes each one's acceptance condition as an executable test that is red now, and has an eye other than the writer's raise the missing, ambiguous, and out-of-scope conditions. Use before planning a fix or a feature, or when asked "what has to hold for this to be done", "write the acceptance tests first", "review these requirements for gaps".
---

# Write the conditions for completion before the plan

**Core rule: before any plan, write one by one what must hold for the work to be complete, and have an eye that did not write them look for the gaps.**

Why: conditions the request does not state do not enter the fix plan, and surface only when a later review raises them as holes. (Measured once: a run that built a new entry point listed 6 requirements but not "from the second round on, run the first checks as usual". The first plan kept those checks from coming back until the end of the run, and the plan review stopped it as must-fix.)

## Pitfalls (read first)

- **Do not write the fix yet.** Only test files may be written at this stage; not one character of the implementation.
- **A test that is red now is correct.** The fix is not in yet. A test already green before the fix shows nothing; record it as "red was not seen".
- **The test file is the source of the condition's text.** Write the premise, the action, and the expectation inside the test as Given / When / Then. Point to the test from elsewhere; do not copy its text.
- **Put the test where the repository's test suite (what CI runs) picks it up.** A test placed where CI does not look guards nothing.
- **Show a person the exact command that runs the tests before it runs.** The person reads its literal text and approves; only then is it run and its exit code recorded.
- **The writer of the conditions is not a neutral eye.** Whoever will also write the fix may write only the conditions that suit their own plan. The review is done by eyes that did not write them.

## 1. Write the conditions

- **Requirements**: one condition per entry under which the request is complete; a short unique key (R1, R2, …) and one sentence each.
- Dig out and add the conditions the request needs even when it does not state them:
  - the default behaviour does not change (nothing changes when the option is not chosen);
  - the behaviour across rounds or stages (not only the first time, but the second and later);
  - what happens on failure, when it is stopped, and when nobody answers;
  - how to undo;
  - combination with other features that can be chosen at the same time.
- **Acceptance**: for each requirement, at least one acceptance condition, written now into the target as an executable test (where it is, its name, and the command that runs it).
- **Out of scope**: what you decided is outside the request's scope (empty if nothing).

## 2. Review the conditions (another eye)

Read the request, the written requirements, and the text of each acceptance test. Find gaps in the conditions for completion before the plan. Three kinds of hole:

1. **Missing**: conditions the request needs that are in neither the requirements nor the acceptance conditions. Look in particular at the default behaviour, behaviour across rounds and stages, how it ends (stopped, failed, nobody answering), how to undo, and combination with other features that can be chosen at the same time.
2. **Ambiguous**: a sentence that does not settle to one condition under which the test holds; a test whose Then is weaker than the requirement (passes whatever is returned); a test that checks something other than the requirement; a test placed where the repository's test suite does not pick it up.
3. **Out of scope**: requirements or acceptance conditions that go beyond the request's scope.

For each hole, say where it is (a requirement, an acceptance condition, or a file) and the line of reasoning that makes it a hole.

- The reviewer only reads; it does not change a single character of the working tree.
- When there is no hole, say what you checked that lets you say there is none.
- **When input is insufficient** (the request or the spec cannot be read, or the test file of an acceptance condition does not exist), do not say there are no holes. Raise one missing hole for each thing that cannot be read or does not exist, starting its reason with "insufficient:" and what you could not check.

## 3. Answer the review

- Answer each hole **exactly once**. Either absorb it (say which requirements and acceptance conditions you added) or declare that you leave it (say why; if the hole is wrong, say where in the actual code or documents it is wrong). No hole is left unanswered.
- Return the whole revised set of conditions, not only what changed, and write the tests of any added acceptance condition before you answer.
- Still only test files may be written; the implementation stays untouched.
- A person then approves the conditions, seeing the conditions, the holes, the answers, and the literal text of each test command.

Works well with: a perspective that keeps the target repository's names and paths out of queries sent to outside services such as web search, and one that writes the questions a person must decide so that someone without the history can decide from the text alone.
