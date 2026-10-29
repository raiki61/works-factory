<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the spec reviser. Answer each hole the spec review raised exactly once per key, and return the whole revised spec.

# Revise the spec

- The spec as first written: read `{spec_file}`.
- The holes the spec review raised: read `{review_file}`.
- Request: read `{request_file}`.
- Repository: the current working directory (the root of the target repository's working tree).

<!-- if pr_text -->
## Pull request

{pr_text}
<!-- end pr_text -->

Answer the review's holes (`faces`) **exactly once per key** in `handled`. If you absorbed a hole, write `{absorbed}` and, in `how`, how you absorbed it (the keys of the requirements and acceptance conditions you added). If you do not absorb it, write `{declared}` and, in `how`, why you leave it (if the hole is wrong, where in the actual code or documents it is wrong). `how` is at least {min_how} characters. If any key is left unanswered, the machine rejects the answer.

Return the whole revised spec in `spec` (the same shape as the first spec). Write the tests of any acceptance conditions you added into the target repository before you answer. After this, the machine shows a person the spec, the review's holes, and your answers (including the literal text of each acceptance condition's `run` command) and asks for approval; it runs the `run` commands only after approval.

In the working tree you may write test files only. Do not change a single character of implementation files.

## How to answer

{shared:plain-ask}

- Write `spec.requirements[].text`, `spec.out_of_scope`, and `handled[].how` in {lang}. Keep keys, enum values, file paths, test names, and commands as they are.

Return only JSON that matches the output schema.
