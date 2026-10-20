Two rejections have a fixed way to fix them.

- If the reason says that lines of `policy_conflicts` do not name any line of the recorded policy: rewrite each such line so that it copies the name of a line of the "Recorded policy" section character for character. If the line is a comment, a docstring, or the description of a test in code that is not in the list (a statement about the target, not a policy), take it out of `policy_conflicts` instead. Fix every line the reason lists, and return `policy_conflicts` whole, including the lines you do not change.
- If the reason says that the R3 answer (the field `r3` with its `status`, `reason`, `seen`, and `unseen`) is missing or has the wrong shape: write `r3` by the rules of the R3 view and return it.
