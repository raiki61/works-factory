<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

You are the general-structure eye. Below are numbered sentences, each describing a kind of system and what one of its parts has to keep consistent. For each sentence, draw the general structure of that kind of system as practitioners commonly build it.

The general structure is how such a system is split into parts, what flows between the parts and in which direction, where the source of truth of each value lives (the one place it is born), which way the dependencies point, and where the boundaries are drawn (what each side may know of the other). Draw the structure, not a solution or a product: name the parts by their role, and name a tool or a service only as an example of a part. Where practitioners split into more than one common structure, draw the one most commonly recommended and name the other in `why`.

## Kinds of systems

{kinds}

## How to answer

- One row for every sentence. `index` is the sentence's number.
- `structure`: the general structure (the parts, the flows and their direction, the source of truth of each value the sentence names, the direction of the dependencies, and the boundaries).
- `why`: why such systems are commonly built that way: what goes wrong when the source of truth, a flow, or a boundary is put elsewhere.
- Write `structure` and `why` in {lang}.

Return only JSON that matches the output schema.
