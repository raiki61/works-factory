---
name: remeasure-premises
description: Before a request is diagnosed or planned, measures again in the current working tree every claim it makes about numbers, sizes, counts, "exists / does not exist", "X can arrive", and "X turns red", never trusting the requester's own measurement as written, and hands on a list of constraints where each one is either measured (with the command run and its output attached) or marked as a hypothesis. Use at the start of work on a request, or when asked "check the premises of this request", "is this number still true", "verify what the issue claims before we act on it".
---

# Measure the request's premises again before anything is built on them

**Core rule: a claim becomes a premise only after it is a value measured in this working tree, or a fact that names a file, shown with the command that was run and its output. Anything else is a hypothesis.**

Why: whoever comes later reads these premises as given. A wrong fact handed on here sends every judgment and fix built on it off course, and a wrong premise still passes their judgment.

## Pitfalls (read first)

- **Do not trust the requester's measurement as written.** It may come from another version, another working tree, or a path that is gone. Measure it again here; if it does not match, write the value you measured and the difference from the request's value.
  - A real case: in "the body is up to about 4MB", the 4MB was measured on a path that the same change deleted. The real size was 5,411 bytes, and five rounds of work were built on that wrong premise.
- **Only "measured" is trusted without a recheck.** So a wrong "measured" is passed on unquestioned even to later roles that question everything else from zero, and their judgments are built on it.
  - A real case: "the repository has no CI definition" was recorded as measured, but a CI workflow file existed. Even when other work in the same run was written on that premise, it was not corrected.
- **Do not hand on memory, an earlier measurement, or a general statement as a premise.**
- **"Does not exist" needs where you looked.** Paste the place and the command; an empty listing or an empty search is also output.
- **Do not change a single character of the working tree, or move its history.** What you measured would otherwise mix into the diff of the later fix. Write any output outside the working tree; if you create something by mistake, remove it, or restore a tracked file you rewrote, before you finish.

## Steps

1. From each request line, pick up every claim about numbers, sizes, counts, exists / does not exist, "X can arrive", and "X turns red" — in what it says, the mechanism it gives, and the condition under which it would be a false alarm.
2. For every line that carries a measured value, write at least one constraint, and quote that line's location in it exactly as written.
3. Measure each claim in this working tree (counting, sizes, listings, the history, running tests, and so on).
4. A fact that names a file also needs a command that shows it (a listing, a search with line numbers). Run it and attach its output.
5. For every constraint, say how you measured it.
6. Mark each constraint:
   - **measured**: you can show the command you ran and its output (only the needed lines if it is long; start command lines with `$ `);
   - **hypothesis**: you cannot — for example production input or things outside the target. Say the location and why it cannot be measured. Never copy the requester's value as measured.
7. When what you measured contradicts what a request line claims or assumes, say which line it contradicts.
8. If the request has no claim to measure, the list may be empty.

A lookup that could not be run because it needs the target's names is handed on as a hypothesis, saying what you wanted to confirm and that it was not run; that mark sends it to a person.

Works well with: a perspective that keeps the target repository's names and paths out of queries sent to outside services such as web search (so that possibly private names do not stay in outside records).
