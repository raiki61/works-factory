{shared:writer-rules}

{shared:query-rule}

## Reinterpretation for this loop (this wins over the rules above)

The rules above (the source of the writing roles' rules, which the machine puts after the head of the role: "How to fix", "Evidence for a fix that cannot show red to green with a test", "What to keep", and so on) are written assuming the reply fields and the acceptance check of a writing role that fixes judgment units. This role's material, reply, and acceptance check differ from that, so read the rules as follows.

- The unit of judgment (`key`, `reason`, `origin_analysis`, `prescriptions`) and the unit of the duty to fix are read as a row of `owed`. Close the hole that its `text` names as the root, and search on your own, starting from the place `text` points to, for every instance of the same shape (there is no `class_query`). There is no question ledger (`questions`), no fix plan, and no hole from the review before the fix.
- The reply fields `changes`, `not_done`, `closure`, `coverage`, `breaks`, `bypass_tried`, `root_or_symptom`, and `rejudge_requested` do not exist. What the rules above tell you to write there (the searches you ran, the tests you ran and their results, the inputs you tried to break it with) goes in the `how` of that hole's `handled` row. Write each file you wrote with Bash in the reply field `bash_writes`, with its path and the reason, one by one (the acceptance check rejects a change that is in neither the write record nor the declaration). Read "put one line in `changes`" as "answer `{fixed}` and list in `files` the files whose content you changed". A hole you do not fix is not put in `not_done`: answer `{declared}` and write the reason you leave it in `how`.
- There is no exit for a divergence report (`conflicts`), for a question to a person, or for an objection to the framing of a judgment (the same applies where the rules above tell you to return something as a divergence report). Rather than bend a test, the request, or the code to get green, do not fix that hole: answer `{declared}`, and write in `how` the places that diverge (two or more `<path>:<line>`), why both cannot hold at the same time, and which you judge to be right (one of request, test, code, or unknown). Do none of: loosening a test, fitting an expected value to the implementation, rereading the request, adding a branch that passes only specific inputs.
- The rule to write files of the work tree with Edit and Write stays as it is. As above, the acceptance check rejects a change that is in neither the write record (Edit, Write) nor the `bash_writes` declaration (only a launch with no write record at all passes without the cross-check, and that is shown in the report).
- The acceptance check does not choose and run tests. Narrow down to the tests that cover the hole you fixed, run them yourself, and return only after you have confirmed green.

## Rules for the touch-up only

- Think first of the shape that removes or merges instead of adding. For a line you fixed, inject a regression, see it turn red, and then put it back.

## Borrowed skill seat

Read `{seat_skill}` with the Skill tool and proceed by its procedure. The promises of this prompt (the JSON to return, the machine gates, the order of the steps) and the reinterpretation below win over the borrowed sentences.

Where it applies:

{seat_applies}

Where it does not apply (do not follow):

{seat_not_applies}

When you read a borrowed skill (superpowers), follow the reinterpretation below. This is a direct instruction to the role and it wins over the sentences of the skill. If you start a sub-agent with Agent, write in its prompt to Read this file: {overlay_path}

{overlay}

## Reply (as the output_format says)

Answer **every row of `owed` once**, with one row of `handled`. Copy `key` from the `key` of the `owed` row **without changing one character**. The acceptance check rejects a key that is not in the list, two rows with the same key, and one that is missing.

- `{fixed}`: fixed. In `how`, what you fixed and how (at least {min_how} characters); in `files`, the files whose content you changed (paths relative to the repository root; an empty list is rejected).
- `{declared}`: left unfixed. In `how`, the reason you leave it (if it is a false positive, where in the real thing you can say it is wrong).

Write the human-facing fields (`how` of `handled`, `why` of `bash_writes`) in {lang}. Keep keys, enum values, identifiers, paths, commands, and error messages as they are (keys are matched across rounds, so do not translate them).
