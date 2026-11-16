---
name: report-for-decision
description: Writes the final report of a piece of automated or delegated work so that a person who did not watch it, coming back from other work, can tell from the head alone what it is about, whether it concerns them, whether it is urgent, and what they must decide — gathering every decision in one place, making each item readable on its own, keeping the facts' numbers unchanged, and checking the head with a reader who has no context. Use when writing the report at the end of a run, a handoff, or a summary someone must act on, or when asked to "write the report", "make this decidable", "summarize for someone who wasn't there".
---

# Write a report a returning reader can decide from

**Core rule: the head alone (the first lines, the plain summary, and the one section of decisions) must let a reader with no context say what it is about, whether it concerns them, whether it is urgent, and what to decide.**

The reader runs several tasks in parallel and reads this between switches. They did not watch the work and have none of the conversation. Write for that reader, first time, every time.

Words used below: a *run* is one execution of the work; a *stage* is one step of it (a check, a review, a fix); the *record* is what the stages left behind; the *request* is the text that asked for the work.

## Pitfalls (read first)

- **Do not change the facts.** Every number that exists in the facts you were given is written with the same value. A number you counted yourself names where you counted it from. Do not rewrite an outcome that was already decided.
- **Do not repeat what is appended anyway.** If the facts are attached to the report as they are, do not list them again in the body; add what happened and what a person should decide.
- **Do not recommend a new option yourself.** Give only the options and recommendations that the record already holds, with their reasons and where they come from. If the record holds none, say that it holds none.
- **A question written only in internal vocabulary cannot be decided.** Labels, stage names, internal marks, stable keys and ids must be replaced with plain words.
- **When there is nothing to decide, say nothing about it.** Do not write a stock phrase that there is nothing to decide, and do not put an empty decisions section. Asking nothing tells the reader no input is awaited.
- **You only read** while writing the report.

## The head

- **Plain summary, 2 to 3 lines, no jargon**: what the task was (what was wrong, in the request's own words), what was found and what changed, the gist of why it ended as it did, what to decide (if several, how many and the most urgent one), and whether it is urgent — and whether anything is broken now. Lines built by a machine carry no reasons; the summary supplies them.
- **For danger or failure, say first whether it is broken now or only could break.**
- **Gloss every term the fixed head lines use** that only the work itself knows (stage and role names, the request's own domain words, identifiers from the diff) in one plain phrase, in the order they appear. A gloss that lives only in a later section does not count for a reader who reads only the head.

## The decisions section

Gather every decision in one place right after the summary. Do not scatter questions in later sections; held or escalated items of work that stopped without finishing go here too.

- Separate what is urgent from what can wait, and give the counts first.
- **One point, one item.** When the same point arrives from several stages (a capability the version before the change had and now lacks, a conflict with a rule a person recorded, a departure from standard practice), make it one item and name the other stages inside it.
- Each item can be read on its own, in this order: what to decide (one sentence) → background (why it came up; one line each for the pull requests, issues, and files involved) → what happens with each option (the actual work, the effort, what breaks) → the recommendation and its reason (only one written in the record, and say how far it can be trusted: a person's, or one an unattended run adopted) → what happens after the answer (only what is in the record) → what stops if nobody decides.
- When work stopped (because the request itself said "stop here", because a person stopped it, or because it waits for a person), always include as one item where it stopped, the reason, and the questions left unanswered — and that continuing means starting new work, and that the stages after the stop did not run.
- Keep "needs a fix" and "needs a redesign" apart; "needs a fix" is not a reason to discard the change.
- A sign that a correct fix may have been dropped (for example a group removed because it turned red on a re-check) is an item too.
- Do not point into internals in an item (`<path>:<line>`, positions in a record, unit keys, row ids, record file names). Say in plain words what the thing is; leave references to later sections and name those sections by heading.
- A choice phrased as "pass" or "do not pass", or a command shown without its consequence: say what is being passed, what happens after each choice, and what happens if nobody chooses.
- A bare reference (an issue or pull request number, a file name, a command): say in a few words what it is and what a person does with it.
- Several findings that may or may not be the same decision: say whether they are separate, which comes first, and who does it (a person or the next run).
- A notice that is not a decision: say in one sentence what it means for the reader, and what to do if they must act.

## The body after the head

Fold the details briefly under headings; do not narrate progress or your own work. Useful sections, after the head (each only when it applies):

- How the work was entered and every request it carried, with origins and counts; do not lump a person's request and a machine's request together, and drop none. If no review looked beyond the request before the fix, say so even if the work looks finished.
- The outcome and the stopping stage, as the facts give them.
- For each unit of work, what was done or why nothing was needed; the defects accepted to be fixed later.
- The verdict and reason of each independent review, unchanged, with an explanation for the reader; what the review of the code comments the change added removed and what it kept. If a review did not run, say so.
- The state of each open question and the grounds it was settled or the reason it went to a person.
- The raw answer of the judgment, copied as it is (in a code fence), the source of the original purpose, and the version before the fix.
- Observation of the main path: what was run where and what was observed. "The tests are green" is not an observation.
- An inventory, without judging, of the new mechanisms the change introduces (build settings, environment variables, CI jobs, template knobs, scripts).
- If the premises drifted, the re-measured constraints and why the earlier ones became false.

## Format

- Write symbols, abbreviations, paths, and made-up labels as "content (symbol)" at first use, so a reader who starts in the middle can resolve them. Name things inside the system with the words of the request or general words.
- Tables only for short values of a few words (states, counts, dates). **No explanatory sentences in cells**: a terminal table gives each column a share of the width and folds a long cell into unreadable pieces. If you need to explain, use bullets or prose. Number the steps.
- Use established IT terms in the report's language; avoid consulting jargon, literal translations, and elaborate metaphors.
- No references that rely on context outside the text ("the one mentioned earlier", "the section above").
- Write in the report's language even if the sources are in another; keep keys, enum values, identifiers, paths, commands, and error messages as they are.

## Check the head with a reader who has no context

Hand only the head to a reader with no tools and no context, told that detailed sections follow it. That reader returns where they stopped (could not follow the meaning) and what they filled in by guessing, line by line, and whether the text alone lets a person decide. Even one stop or one guess means rewrite. A detail left to a later section and named by heading is not a stop.

When the head is sent back:

- If the reader stopped, rewrite so that the places they named can be understood from the head alone.
- If table cells hold sentences or are too long, drop the table for bullets or prose, or cut each cell to a few words and write the explanation outside the table.
- Fix every point, including those from earlier rounds, and return the whole body again, not only the parts you fixed.

Works well with (optional; this file is complete without them): a habit of writing that keeps the names of the project being reported on out of words sent to outside services such as web search, and the stance of a reader who checks a text with no context and no tools.
