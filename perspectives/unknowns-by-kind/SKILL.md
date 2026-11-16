---
name: unknowns-by-kind
description: Names, for each request line, the one kind of unknown left (none, cause, shape, or scope), each backed by a verbatim quote, so the heaviest kind decides what happens next. Use when a request is about to be fixed, or when asked "do we know enough to fix this yet". Not for remeasuring the request's numeric claims.
---

# Name the kind of unknown in each request line, and do what that kind asks

**Core rule: a request line is not equally clear everywhere. Name what is unknown about it, and do the work that kind of unknown asks — no more, no less. Give a lighter kind only where you can show it with quotes; when in doubt, choose "cause".**

Why the asymmetry: light handling is only for a request where the place to fix and the way to fix it are known on every line. A request wrongly handled lightly hides, until after the fix, holes that should have been found before it. Standard handling, wrongly chosen, only costs more and does no harm. Heavier handling (a second check of the judgment, a per-item review of the plan) costs much more again. The heaviest kind among the lines decides the handling of the whole request.

## Pitfalls (read first)

- **How much the requester investigated is not a reason to raise or lower the kind.** Even if the requester did not name the cause or the place to fix, choose "none" if you can show the place to fix with the repository's lines.
- **Quotes are word for word.** A quote from the request is copied from that line's text; a quote from the repository is copied from inside the named line range. For a "none" line, that range is narrow enough to name the place to fix.
- **Read only while naming the kinds.** Do not change a single character of the working tree.
- **Do not widen silently.** If the quoted place turns out to be the wrong place, say so with quotes and name the real place; do not quietly fix somewhere else.
- **A choice needs its rejected options.** Wherever you choose a shape, write why you chose it and why you set the others aside.

## Steps

Read "Naming the kind, for each line" when you sort a request, and "Doing what each kind asks" when you fix or plan from lines already sorted; the other subsections apply to both.

### The four kinds

- **none**: you can show the cause and the place to fix with quotes from the request's text and the repository's lines.
- **cause**: there is only a symptom, and the cause is not visible in the code.
- **shape**: a choice is needed — which shape to take, or what to add.
- **scope**: the change alters a public contract (types, configuration keys, the shape of input and output with the outside), or spans more than one separately run part. If this applies, choose scope even when a choice is also needed.

### Never "none" when

- the line is ambiguous (you cannot read what happens or where to fix) — choose cause;
- it asks for a design choice — choose scope if scope applies, otherwise shape;
- the cause is not visible in the code (no line in the repository matches the written symptom) — choose cause;
- it changes a public contract — choose scope.

### Naming the kind, for each line

- Give every request line exactly one kind.
- For none, shape, and scope, name the place in the repository (path and lines). For cause, a place is not needed.

### Doing what each kind asks

1. **none (the place is quoted)**: first check that the quoted place is really the place to fix. If it is off, name with quotes why it is off and the real place to fix.
2. **cause**: follow the quotes from the line of the symptom to the line of the cause, and find the cause.
3. **shape**: lay out two or more shapes, and write why you chose one and why you set the others aside.
4. **scope**: list the contracts you touch (types, setting keys, input and output shapes, separately run parts) and name the effect on each. When a choice is needed, lay out two or more shapes, with why you chose one and set the others aside.

## Done when

- Every request line has exactly one kind, and every lighter kind rests on quotes.
- No line got "none" where one of the "never none" cases applies.
- The working tree is unchanged while you named the kinds.
- Each kind's work is done: the quoted place confirmed or corrected, the cause found, two or more shapes laid out, or the touched contracts listed with their effects.

## How to report

- **For each line when naming**: its kind; a quote of the part of the request line the kind rests on; for none, shape, and scope, the place in the repository with a quote from inside it, and for shape and scope which applies (a design choice, a change to a public contract, or spanning more than one part); for cause, the request quote alone is enough, and if you name a place, quote from it too; and in one or two sentences why the line got its kind.
- **For each line when doing the work**: what that kind asked for, with quotes.
- When the unknowns of the lines were not sorted, say so and why.

## Example

Input: a request line says "The total on the invoice page is off by one cent." The repository has one function that sums the line amounts and rounds each line before adding.

Reply:
- Kind: none. Request quote: "off by one cent". Place: the summing function, the two lines that round each line before adding, quoted as they are. Why: the rounding of each line before the sum shows both the cause and the place to fix.

## Works well with

- Sorting a fix request by its root causes before planning.
- Writing the conditions under which the work counts as done, before the plan.
