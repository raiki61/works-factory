---
name: unknowns-by-kind
description: Before fixing or planning, names for each line of a request the one kind of unknown still left — none (the cause and the place to fix can be shown), cause (only a symptom), shape (a design choice is needed), or scope (a public contract changes, or the change spans more than one separately run part) — each backed by a word-for-word quote from the request and, where it applies, from the repository's lines, erring toward more checking when in doubt, so that the heaviest kind decides how much checking the work needs before the fix; then does the work each kind asks (confirm the quoted place, trace from symptom to cause, lay out two or more shapes, list the contracts touched). Use when triaging a request, when starting a fix or a plan from a request whose lines are not equally clear, or when asked "how well understood is this request", "can we skip the checks for this one", "what don't we know yet", "where exactly is the fix", "what does this change touch".
---

# Name the kind of unknown in each request line, and do what that kind asks

**Core rule: a request line is not equally clear everywhere. Name what is unknown about it, and do the work that kind of unknown asks — no more, no less. Give a lighter kind only where you can show it with quotes; when in doubt, choose "cause".**

Why the asymmetry: light handling is only for a request where the place to fix and the way to fix it are known on every line. A request wrongly handled lightly hides, until after the fix, holes that should have been found before it. Standard handling, wrongly chosen, only costs more and does no harm. Heavier handling (a second check of the judgment, a per-item review of the plan) costs much more again. The heaviest kind among the lines decides the handling of the whole request.

## Pitfalls (read first)

- **How much the requester investigated is not a reason to raise or lower the kind.** Even if the requester did not name the cause or the place to fix, choose "none" if you can show the place to fix with the repository's lines.
- **Quotes are word for word.** A quote from the request is copied from that line's text; a quote from the repository is copied from inside the named line range, and the range is narrow enough to name the place to fix.
- **Read only while naming the kinds.** Do not change a single character of the working tree.
- **Do not widen silently.** If the quoted place turns out to be the wrong place, say so with quotes and name the real place; do not quietly fix somewhere else.
- **A choice needs its rejected options.** Wherever you choose a shape, write why you chose it and why you set the others aside.

## The four kinds

- **none**: you can show the cause and the place to fix with quotes from the request's text and the repository's lines.
- **cause**: there is only a symptom, and the cause is not visible in the code.
- **shape**: a choice is needed — which shape to take, or what to add.
- **scope**: the change alters a public contract (types, configuration keys, the shape of input and output with the outside), or spans more than one separately run part. If this applies, choose scope even when a choice is also needed.

## Never "none" when

- the line is ambiguous (you cannot read what happens or where to fix) — choose cause;
- it asks for a design choice — choose scope if scope applies, otherwise shape;
- the cause is not visible in the code (no line in the repository matches the written symptom) — choose cause;
- it changes a public contract — choose scope.

## Naming the kind, for each line

- Give every request line exactly one kind.
- Quote the part of the request line the kind rests on.
- For none, shape, and scope, name the place in the repository (path and lines) and quote text from inside it. For shape and scope, say which applies: a design choice, a change to a public contract, or spanning more than one part.
- For cause, the request quote alone is enough; if you name a place, quote from it too.
- Say in one or two sentences why each line got its kind.

## Doing what each kind asks

1. **none (the place is quoted)**: first check that the quoted place is really the place to fix. If it is off, name with quotes why it is off and the real place to fix.
2. **cause**: follow the quotes from the line of the symptom to the line of the cause, and find the cause.
3. **shape**: lay out two or more shapes, and write why you chose one and why you set the others aside.
4. **scope**: list the contracts you touch (types, setting keys, input and output shapes, separately run parts) and name the effect on each. When a choice is needed, lay out two or more shapes, with why you chose one and set the others aside.

When the unknowns of the lines were not sorted, say so and why.
