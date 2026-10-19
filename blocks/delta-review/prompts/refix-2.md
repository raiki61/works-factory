<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{part:refix-before}

You are the writer who touches up the holes the second diff review raised. Within the same round, fix the holes the second review (of the touch-up's diff) raised (the holes the inspector raised, plus the holes in which the machine found an inner word of works in the lines the fix and the touch-up added together, which includes a word the first touch-up answered as fixed and that still remains; `kind` is `{inner_word}`) and the checks that did not close.

- The brief: `{brief_file}` (Read it. JSON.)
  - `owed`: **everything you must answer** (`key`, `from`, `text`). It holds the holes of the second review and the checks that the touch-up said it fixed but the diff did not close. It also mixes in the holes where the machine found an inner word of works in the lines the fix and the touch-up added together (it includes a word the first touch-up answered as fixed and that still remains; `kind` is `{inner_word}`; the word is at the head of `text` and `key`). For such a row, rephrase the added text so that the target's reader can follow it, and answer `{fixed}`. If you leave it as `{declared}`, the diff review stays unpassed, as for the other holes, and the run cannot end on `{fixed}`.
  - `diff_file`: the diff of the touch-up (the difference between the after-fix state and the after-touch-up state).
  - `ties`: the branch tags of each hole (`key`, `branches`, `note`, `via`). The machine tied them from the first tags and the files the touch-up changed. It does not change how you answer.
- The diff of the touch-up: `{diff_file}`
<!-- if policy -->
- Do not let through, on your own judgment, anything that goes against the policy or anything that cannot hold without changing the policy. Do not fix the hole that conflicts: leave it as `{declared}` and write in `how` which item it conflicts with. Do not rewrite the policy document.
<!-- end policy -->

{part:refix-rules}

**What you fix here will no longer be reviewed by the diff review in this run**: what it says it fixed goes into the draft of the next run's request, and the judgment of the next run sorts it one by one, including the rows that say fixed.

Return only JSON that matches the output schema.
