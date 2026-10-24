{shared:role-cold-reader}

{shared:report-head-check}

You have no context: you are given none of the history, the record, or the diff. Read only the text below, which is the part of the final report that asks a person to decide. It comes in two parts that a person reads as one text, in this order: the lines the machine built from the record, and the text the writer wrote right after them.

==== lines the machine built begin ====
{machine}
==== lines the machine built end ====

==== text the writer wrote begins ====
{body}
==== text the writer wrote ends ====

Return (1) where you could not follow the meaning in the text the writer wrote and stopped (`stops`), (2) what you filled in by guessing in the text the writer wrote (`guessed`), (3) where you stopped or filled in by guessing in the lines the machine built, when the text the writer wrote does not make it clear either (`machine_lines`), and (4) whether this text alone lets a person decide (`decidable`). Put each place in exactly one of `stops`, `guessed`, and `machine_lines`, by the part where it is. If there is at least one entry in `stops`, `guessed`, or `machine_lines`, set `verdict` to `redesign-needed`; otherwise set it to `pass`.

Return only JSON that matches the output schema.
