---
name: completion-conditions-first
description: Writes, before any plan exists, the conditions under which a request counts as done, including unstated ones such as default behaviour unchanged, failure, and undo, each as a test that is red now. Use when no plan exists yet, or when asked "what does done mean for this request". Not for writing the fix plan itself.
---

# Write the conditions for completion before the plan

**Core rule: before any plan, write one by one what must hold for the work to be complete, and have an eye that did not write them look for the gaps.**

Why: conditions the request does not state do not enter the fix plan, and surface only when a later review raises them as holes. (Seen once: a piece of work that built a new entry point listed 6 requirements but not "from the second pass on, run the first checks as usual". The first plan kept those checks from coming back until the work ended, and the plan review stopped it as must-fix.)

## Pitfalls (read first)

- **Do not write the fix yet.** Before the plan, only test files may be written; not one character of the implementation.
- **A test that is red now is correct.** The fix is not in yet. A test already green before the fix shows nothing; record it as "red was not seen".
- **The test file is the source of the condition's text.** Write the premise, the action, and the expectation inside the test as Given / When / Then. Point to the test from elsewhere; do not copy its text.
- **Put the test where the repository's test suite (what CI runs) picks it up.** A test placed where CI does not look guards nothing.
- **Show a person the exact command that runs the tests before it runs.** The person reads its literal text and approves; only then is it run and its exit code recorded.
- **The writer of the conditions is not a neutral eye.** Whoever will also write the fix may write only the conditions that suit their own plan. The review is done by eyes that did not write them.

## Steps

Read "Write the conditions" when you write them, "Review the conditions" when you are the other eye, and "Answer the review" when you answer its holes.

### Write the conditions

- **Requirements**: one condition per entry under which the request is complete; a short unique key (R1, R2, …) and one sentence each.
- Dig out and add the conditions the request needs even when it does not state them:
  - the default behaviour does not change (nothing changes when the option is not chosen);
  - the behaviour across repeated passes or steps (not only the first time, but the second and later);
  - what happens on failure and when nobody answers;
  - how to undo.
- **Acceptance**: for each requirement, at least one acceptance condition, written now into the target as an executable test.
- **Out of scope**: what you decided is outside the request's scope (empty if nothing).

### Review the conditions (another eye)

Read the request, the written requirements, and the text of each acceptance test. Find gaps in the conditions for completion before the plan. Three kinds of hole:

1. **Missing**: conditions the request needs that are in neither the requirements nor the acceptance conditions. Look in particular at the default behaviour, behaviour across repeated passes and steps, how it ends (stopped, failed, nobody answering), how to undo, and combination with other features that can be chosen at the same time.
2. **Ambiguous**: a sentence that does not settle to one condition under which the test holds; a test whose Then is weaker than the requirement (passes whatever is returned); a test that checks something other than the requirement; a test placed where the repository's test suite does not pick it up.
3. **Out of scope**: requirements or acceptance conditions that go beyond the request's scope.

- The reviewer only reads; it does not change a single character of the working tree.
- **When input is insufficient** (the request or the spec cannot be read, or the test file of an acceptance condition does not exist), do not say there are no holes. Raise one missing hole for each thing that cannot be read or does not exist, starting its reason with "insufficient:" and what you could not check.

### Answer the review

- Answer each hole **exactly once**. Either absorb it (add requirements and acceptance conditions) or declare that you leave it (with a reason; if the hole is wrong, where in the actual code or documents it is wrong).
- Write the tests of any added acceptance condition before you answer.
- Still only test files may be written; the implementation stays untouched.

## Done when

- Every requirement has at least one acceptance condition written as a test where CI picks it up, with Given / When / Then inside it.
- The unstated conditions (default behaviour, second and later passes, failure, nobody answering, undo) were each considered when writing; in the review, stop and combination with other features were also looked for.
- Not one character of the implementation changed.
- Every hole the review raised has exactly one answer; none is left unanswered.
- A person has approved the conditions, seeing the conditions, the holes, the answers, and the literal text of each test command, before any test command runs.

## How to report

- **Writing**: the requirements (key and one sentence each); for each acceptance condition, where the test is, its name, and the command that runs it (not the test's text); and what is out of scope.
- **Reviewing**: for each hole, its kind, where it is (a requirement, an acceptance condition, or a file), and the line of reasoning that makes it a hole. When there is no hole, say what you checked that lets you say there is none.
- **Answering**: for each hole, absorbed (which requirements and acceptance conditions you added) or left (and why); then the whole revised set of conditions, not only what changed.

## Example

Input: A request: "add an option to export the report as a file." The written requirements are R1 "the export writes the report to the named file" and R2 "the export fails with a message when the file cannot be written."

Reply:
- Hole H1, missing, at the requirements: nothing says that the report shown on screen stays the same when the option is not chosen. The request adds an option, so the default behaviour is a condition it needs.
- Hole H2, ambiguous, at R2's test: its Then only checks that the export ended, not that it failed with a message, so it passes whatever is returned.

## Works well with

- keeping the target repository's names and paths out of queries sent to outside services such as web search;
- writing the questions a person must decide so that someone without the history can decide from the text alone.
