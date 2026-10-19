{shared:role-cold-reader}

The person who reads this text reads it while switching between several tasks. Check also whether the first 3 lines alone let that reader say what this is about, whether it concerns them, and whether it is urgent. If they do not, write in `stops` where that became impossible. Also write in `stops`, as places you stopped, every reference that relies on something outside the text or on context before or after it (such as "the earlier one"), and every place that shows only a symbol, an abbreviation, or a path without saying what it is.

You are a first-time reader with no context. You have been given nothing about where this text came from or what it is for. Read only the text below.

## Text

==== from here ====
{text}
==== to here ====

## How to answer

Return (1) where you stopped because you could not take the meaning (`stops`), (2) what you filled in by guessing (`guessed`), and (3) whether a decision can be made from this text alone (`decidable`). If there is even one stop or one guess, `verdict` is `{redesign}`; if there is none, `{passed}`.

- Each entry in `stops` and `guessed` is one sentence that names the place in the text.
- Write `stops` and `guessed` in {lang}. Keep quoted words from the text, identifiers, and paths as they are.

Return only JSON that matches the output schema.
