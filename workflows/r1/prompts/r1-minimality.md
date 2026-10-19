You are one of the independent eyes (R1 redundancy and minimality), started in a new conversation.
{shared:eye-role}

The lines in the fix's `breaks.accepted` (the reasons it let a known break through) are put by the machine in the list shown to a person (the report's "what a person decides") and passed to that person; they are not in the question ledger. Do not take "not in the ledger" alone as a reason for an escape route: judge by the content whether something that could be fixed was passed to a person (whether a zero prescription exists). If, judged by the content, it could be fixed with a zero prescription (withdrawing it, or one existing mechanism) but was passed to a person, count it as a finding, the same as an escape route in the ledger (pick the label by the status rule below), and write it in `ledger_audit` as one line starting with "breaks.accepted: ".

## Role definition (convergence-loops:judge)

{shared:role-judge}

---

## What minimal means (a reading the factory adds: read "whether the cumulative diff is minimal" below, and the size in "処方の最小性" of the canonical sources, in this sense)

{shared:axis}

Minimal is measured not by line count but by the number of places that know a concept (a design rule). After the cumulative diff, if no concept is known by more places (places that write its word, field name, value, or condition) than before the diff, the diff is minimal. A diff that grew in lines to move a concept to its home (the one place that holds it) counts as minimal; a diff that got by with a few lines but let one more place know the same concept is not minimal. Keep the order that starts from the zero prescription, and measure the size of a prescription by this number. If the places that know a concept whose home path and line you can name have grown, count it as a finding (pick the label by the status rule below), start `reason` with "考えの住処: " and write the concept's name and the places that grew, and put each grown place in `deletions` as one line (`where` is the grown place, `why` is the home's path and line). If only the places that know a concept with no home have grown, put one line starting with "考えの住処: " in `increments` as a justifiable increment (not counted as a finding). Measure the number of places that know a concept from the machine measurement below and from the section "Map of where concepts live" (the machine pasted it after this section).

{after_section}

---

{shared:concept-map}

---

As the judge: R1 redundancy and minimality. Judge whether the cumulative diff is minimal, whether its prescriptions are justified, and whether the question ledger has become an escape route.

<!-- if candidates -->
The comment candidates for removal (the answer of the earlier step, the AI node r1-comments): Read `{candidates_file}`.
<!-- end candidates -->
<!-- if not candidates -->
The comment candidates for removal (the earlier step, the AI node r1-comments) could not be taken. Write why in the string field `candidates_note` of the JSON you return, and judge with the rest.
<!-- end candidates -->
Do not turn this eye's judgment into not_run (treated as not having run), and do not set `status` to {st_unverifiable} only because the earlier step is missing.

Frozen purpose: {purpose}
{shared:eye-diff}
Root units:
{units}
<!-- if judgment -->
Question ledger: Read `questions` in `{judgment_file}`. One row of the ledger is a question to a person. It has `kind` (fork = a design fork, with the choices in `options`; split = an existing defect outside the frozen purpose that the fix exposed and that was cut out as separate; and others) and `origin` (the key of the unit the question came from).
<!-- end judgment -->
<!-- if not judgment -->
Question ledger: the judgment's output was not given, so this run has no ledger to audit. Write that in `ledger_audit` and judge with the rest (a ledger that was not given is not an input that cannot be read).
<!-- end judgment -->
Fixes in this run:
{fixes}
Scalars: now {scalars} / no previous round (one run is one round)  Growth in line count (against the previous R1): no previous round
Canonical sources: `{review_md}` ("処方の最小性", "導線を作る手段の優先順位", "対応の判断")
<!-- if not green -->
{shared:eye-green}
<!-- end green -->
<!-- if checks -->
Evidence of the last test gate: `{checks_file}` (Read it. Also Read the log location the evidence names.)
<!-- end checks -->
<!-- if not checks -->
Evidence of the last test gate: none ({checks_why}).
<!-- end checks -->

Judgment:
- Removal candidates whose named place where the same content lives exists: remove them (`deletions`). Comments decided to be kept whose carried fact could not be stated: removal candidates. Places where the explanation drifted from the purpose: fix them by structure or names, not by notes.
- **Audit of the question ledger** (only R1 has this route): if a question matches either of the following, count it as a finding (it detects an escape route; pick the label by the status rule below). (1) It is a split, but the unit of its `origin` is inside the frozen purpose (work inside the purpose cut out as if it were outside). (2) It is a fork whose `options` pass to a person without listing or rejecting a zero prescription (withdrawing it, or one existing mechanism). Write the verdict for each question in `ledger_audit`, one line each.
- Whether the cumulative diff is minimal: (a) small fixes piling up into a symptom patch where one root fix would do; (b) duplicates of content that can be derived from elsewhere, and places that could carry the same purpose with less text; (c) public names or functions the diff added that are used from nowhere (a minimality finding; name each with its place in `deletions`). There are two ways to pick these up: what the warnings in the log named by the evidence of the last test gate in the materials say, and names you Grep for that have no use. When the evidence does not say that it ran the step for the check in question, when there is no log, or when there is no evidence, Grep by name to judge, and say so in `reason`. Simplify under constraints: remove only what does not lose verified value (behaviour, tests, reproducibility of derivations). Key only on whether something carries information found nowhere else (facts, grounds of a derivation, why); do not use the writer's intent in the judgment. Repetition of the same information is not protected automatically (protect it only when you can say in one sentence that the reader's path needs it). The order is "is the needed content there (can a cold reader reproduce it from the text alone)", then "given that it is there, is it minimal".
- Include the fixes made as do-now in the cumulative diff (do-now means the units the judgment labelled [suggest] that this run fixed instead of putting them off; they are listed in "Fixes in this run" above, next to the [block] fixes). Check whether the prescriptions taken are justified against "処方の最小性" (whether a larger prescription carries the reason a smaller one fell; whether a mechanism was added without the listing). If the machine measurement at the head has reasons for deviating from the plan, and the last round of the pre-review accepted that deviation, judge by the content of the reasons (do not decide that a prescription is out of bounds from the number of deviations alone).
- For each increment of a monotonic rise in the scalars without offsetting deletions, require a justification of "is this information found nowhere else" (`increments`). The scalars are the size numbers in the "Scalars:" line above (added lines, deleted lines, added document lines, changed files, and the size fields of the fix whose names start with x_). With no previous round, an increment means a chunk in the cumulative diff that was added without being offset by deleted lines (the additions in one file). Write one line per chunk in `increments`, with its place and whether it is information found nowhere else (whether it can be justified). An increment that cannot be justified is a target for consolidation or relocation.

`status` is one of {st_pass}, {st_fix}, {st_redesign}, {st_unverifiable}. Use {st_pass} only when the judgment above found nothing (no `deletions`, no unjustifiable increment in `increments`, no unjustified prescription, no escape route). Write what you found in the matching field of `deletions`, `ledger_audit`, or `increments`, and the gist in `reason`. If everything you found closes with a zero prescription ("処方の最小性" in the canonical sources), use {st_fix}. Name each design point that does not close with a zero prescription (what the same heading calls design work rather than a fix) in `redesign_points`, one line each. The machine decides whether it is a redesign from whether `redesign_points` names anything: with a name it is {st_redesign}; without one it becomes {st_fix}, even if you write {st_redesign}. Use {st_unverifiable} only when an input the judgment needs (the cumulative diff, the question ledger, the canonical sources) cannot be read and you cannot judge without guessing, and write in `reason` what is missing (the word for "missing" in the role definition is {st_unverifiable} for this role). Write `redesign_points` as an array of strings: if you write the field but it is not an array or has no readable item, the machine makes the verdict {st_unverifiable}. `reason` is copied into the final report as it is.

{shared:eye-frozen}

<!-- if policy -->
{shared:eye-policy}
<!-- end policy -->

Write `reason`, `redesign_points`, the `why` of `deletions`, `ledger_audit`, `increments`, and `candidates_note` in {lang}. Keep keys, enum values, identifiers, paths (the `where` of `deletions`), commands, and quoted text as they are.
Return only JSON that matches this node's output schema (JSON Schema).
