{shared:role-cold-reader}

{shared:report-head-check}

You have no context: you are given none of the history, the record, or the diff. Read only the text below, which is the part of the final report that asks a person to decide. It comes in two parts that a person reads as one text, in this order: the lines the machine built from the record, and the text the writer wrote right after them. Every non-empty line starts with a mark and " | " (such as `M2 | ...` or `W5 | ...`): the lines the machine built carry `M` and their number, and the text the writer wrote carries `W` and its number. The mark is not part of the text; it only names the line.

==== lines the machine built begin ====
{machine}
==== lines the machine built end ====

==== text the writer wrote begins ====
{body}
==== text the writer wrote ends ====

Return (1) where you could not follow the meaning and stopped (`stops`), (2) what you filled in by guessing (`guessed`), and (3) whether this text alone lets a person decide (`decidable`). If there is at least one entry in `stops` or `guessed`, set `verdict` to `redesign-needed`; otherwise set it to `pass`.

- Each entry in `stops` and `guessed` is an object with `line` and `text`. In `line`, write only the mark characters of the line where you stopped or guessed, such as `M2` or `W5`, with nothing else. If the place spans several lines, use the mark of the line where it starts. If you stopped in a line the machine built, write that line's mark, but only when the text the writer wrote does not make it clear either.
- `text` is one sentence that names the place in the text. Do not put the mark in `text`.
<!-- if lang_given -->
- Write the `text` of `stops` and `guessed` in {lang}. Keep quoted words from the text, identifiers, and paths as they are.
<!-- end lang_given -->
<!-- if not lang_given -->
- Write the `text` of `stops` and `guessed` in the language of the text. Keep quoted words from the text, identifiers, and paths as they are.
<!-- end lang_given -->

Return only JSON that matches the output schema.
