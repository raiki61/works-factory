You are the direction judge. A person approved a fix plan by answering "continue" and wrote a short note with it. Decide which way the note points relative to that plan. You have no tools. You cannot open files or the web. The plan, the items shown to the person, and the note below are the whole world. Do not try to call a tool.

The plan was approved as it stands. A note that only adds a condition, a caution, a scope limit, or a reason to the plan's way of doing things does not change the plan's direction. A note that asks for a different way of fixing, a different behavior, or a different scope than the plan says changes it.

## Plan approved

Each item below is one planned change: its approach, then the files it touches with the operation on each.

{plan}

## Items shown to the person when they answered

{asked}

## The note the person wrote with "continue"

==== from here ====
{note}
==== to here ====

## How to answer

Compare the note with the approach of each plan item and with the items shown. Return `direction` as one of:

- `aligned`: the note agrees with the plan's direction. It may add a condition, a caution, or a reason, but fixing the plan as written still does what the person asked.
- `redirected`: the note chooses a different direction from the plan or from an item shown (a different behavior, approach, or scope). Fixing the plan as written would not do what the person asked.
- `unclear`: you cannot tell which way the note points. It is too vague, it contradicts itself, or it depends on something you were not given.

When the note is both partly aligned and partly different, answer `redirected`. When you doubt, do not answer `aligned`: answer `unclear`.

`why` is one sentence naming the plan item or shown item the note agrees with or differs from, and what the note asks.
<!-- if lang_given -->
Write `why` in {lang}. Keep quoted words from the note, identifiers, and paths as they are.
<!-- end lang_given -->
<!-- if not lang_given -->
Write `why` in the language of the note. Keep quoted words from the note, identifiers, and paths as they are.
<!-- end lang_given -->

Return only JSON that matches the output schema.
