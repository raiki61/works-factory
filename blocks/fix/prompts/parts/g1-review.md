{template}

## works rules (for the subagent; they win over the template above and over the reading rules unattended.md)

- Even when you read the reading rules (unattended.md), these rules win where they collide. The reviewer may also read the git diff with Bash (GIT-RANGE's "the reviewer has no Bash" in the reading rules does not apply to this subagent).
- Do not commit, stash, reset, or checkout. Do not move HEAD, the index, or the branch; leave the diff in the working tree (read the template's "Commit your work" accordingly).
- Do not ask a person (no answer comes even if you ask). Where you do not know, do not stop: write NEEDS_CONTEXT or BLOCKED and what you do not know in your last message.
- Do not write the report to a file; write it in your last message.
- Write to the working tree with the Edit and Write tools (they appear in the record of writes). For files you wrote with Bash, write the path and why you wrote it with Bash in your last message.
- Do not run the whole suite (later stages run the whole suite and test_cmd). Run only the tests the files you changed reach.
- Do not start subagents.
- The main material for the diff is the diff file the fixer wrote (the absolute path of the Diff file above). Read it first. Only when it is missing or unreadable, run `git diff <the Base version>` with the Base version above (the diff between the working tree and base; works does not commit, so no diff appears in a commit range), get the names of new untracked files with `git ls-files --others --exclude-standard`, and Read each of them.
- The diff is the whole from base and includes the previous items' fixes. Review what concerns the current item's brief; do not review the previous items' fixes themselves (point it out if the current item's fix breaks them).

Rules for queries to outside services (from the works wrapper; these rules win over the template's text):

{shared:query-rule}
