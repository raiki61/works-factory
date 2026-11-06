## The runner's contract

- It is started with the target root as its working directory.
- Its first argument is where to write the JUnit XML (an absolute path). It writes each test's outcome there as JUnit XML.
- It exits with the test tool's exit code as it is (non-zero if any test is red). When the test_cmd is a chain of commands joined only by `&&`, it exits with the value the chain itself would return: the first non-zero exit code among the parts, or 0 if every part exits 0.
- Arguments may follow the first argument (test files, test names, filter expressions), and the environment variable `{only_env}=1` may be set. When the person gave no test command and the root has no run declaration, the machine runs only the tests related to the change by passing their file paths here, so pass them to the tool as they are whenever it can take them (that is what keeps the run short). If the tool cannot take them, drop them and run the whole suite (running the whole suite checks the same thing).

## How to write it

1. If there is a test_cmd, write it into the runner without changing a single character, and add after it the option that makes the tool write JUnit XML to the first argument. The machine treats a runner that contains the test_cmd as typed as the same thing as the test_cmd, and does not run the test_cmd twice in the later TDD loop.
   - This holds when the test_cmd is one command, or commands joined by `;`, `||` or a pipe (including a mix of them).
   - When the test_cmd is a chain of test commands joined only by `&&` at the top level, the option placed after the whole chain would reach only its last part, and a red part would stop the chain before the later parts run. Write it part by part instead:
     - Copy each part without changing a single character, add after it the option that makes the tool write JUnit XML, and have each part write to its own temporary file.
     - Run the later test parts even if an earlier part is red; keep each part's exit code in a variable.
     - After every part has run, gather the `testsuite` elements of all the temporary files under one `testsuites` root and write it to the first argument.
     - If a part to which you added the JUnit option ended without writing its outcome, do not drop it silently: put one testcase into the gathered file that holds a `<error>` element (a `<error>` testcase). Put only the part's number in its name (the name must not change from run to run) and the part's exit code in the `message` of the `<error>`. Do not do this for a part that does not get the JUnit option.
     - If a part that does not run tests (a build step, for example) fails, stop there and exit with its non-zero code.
     - Pass the test-file arguments only to the parts that can take them. If you cannot decide which parts can, run every part as a whole suite.
     - Exit with the first non-zero exit code among the parts, or 0 if all are 0 (the value the `&&` chain itself returns).
2. If there is no test_cmd, decide the command that runs the tests from the CI definitions and `{decl_name}`. If the target has no tests yet, you may write a runner that runs the place where the target's conventions put tests and, when it finds none, writes a JUnit XML with zero tests.
3. Make the first line of the body a `#!` line (the machine does not place a body that does not start with `#!`).
4. If you cannot decide how to make it write JUnit XML, or what to run, do not return a body for form's sake: set `made` to false and write in `why`, in one line, what you read and what was missing. Do not assume green.

## How to answer

- `made`: true if you wrote a runner, false if not.
- `body`: the runner's body (an empty string when `made` is false).
- `why`: why `made` is false (an empty string when it is true).
- Write `why` in {lang}. Keep commands, option names, file names, and paths as they are.
