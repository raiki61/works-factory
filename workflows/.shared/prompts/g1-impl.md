{template}

## works rules (for the subagent; they win over the template above and over the reading rules unattended.md)

- Even when you read the reading rules (unattended.md), these rules win where they collide. The reviewer may also read the git diff with Bash (GIT-RANGE's "the reviewer has no Bash" in the reading rules does not apply to this subagent).
- Do not commit, stash, reset, or checkout. Do not move HEAD, the index, or the branch; leave the diff in the working tree (read the template's "Commit your work" accordingly).
- Do not ask a person (no answer comes even if you ask). Where you do not know, do not stop: write NEEDS_CONTEXT or BLOCKED and what you do not know in your last message.
- Do not write the report to a file; write it in your last message.
- Write to the working tree with the Edit and Write tools (they appear in the record of writes). For files you wrote with Bash, write the path and why you wrote it with Bash in your last message.
- Do not run the whole suite (later stages run the whole suite and test_cmd). Run only the tests the files you changed reach.
- Do not start subagents.

{weapon_rule}

{shared:brief-reading}

{shared:query-rule}
<!-- if ask -->

## When you need something outside the scope (rules for the subagent)

The coordinating role that started this subagent does the scope consultation in its answer fields (a subagent cannot consult itself). If you need to rewrite a file outside the brief's `allowed_paths` (including things that hit `out_of_scope`) or a frozen test (the test files of units the TDD loop made green), do not change it; write "a scope consultation is needed" in your report, and list the item number, the paths you want to add, the range of tests you want to rewrite (`<path>` or `<path>:<line>`), and the reason (why it is needed and what you will change how). You may go on finishing the fixes inside the scope.
Before you report, run the same fact checks as the acceptance (frozen tests, the origin of writes, the approved fix plan's scope, the Markdown links the diff added; no tests are run) with the following, and fix the lines in `rejects` before you return (exit code 0 passes, 1 means there are lines).
   {check_cmd}
<!-- end ask -->
