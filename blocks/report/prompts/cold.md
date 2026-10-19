{shared:role-cold-reader}

{shared:report-head-check}

You have no context: you are given none of the history, the record, or the diff. Read only the text below, which is the part of the final report that asks a person to decide.

==== text begins ====
{body}
==== text ends ====

Return (1) where you could not follow the meaning and stopped (`stops`), (2) what you filled in by guessing (`guessed`), and (3) whether this text alone lets a person decide (`decidable`). If there is at least one stop or one guess, set `verdict` to `redesign-needed`; otherwise set it to `pass`.

Return only JSON that matches the output schema.
