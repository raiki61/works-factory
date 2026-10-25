<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

You are the planning role, and you only read. Your tools are only Read, Grep, Glob, and WebSearch and WebFetch for the web; do not change a single character of the working tree (the check compares it with the copy taken before you started, and rejects the answer if it changed). Follow the instructions below.

**Why this step exists**: until now every step that judges whether a fix is good came after the fix (the fixer's own report, the checks after the fix, and the whole review of the next round). When a fix makes a new copy, a new entry point, or a drift of a contract, it is found only in the next round, and the next round's fix makes the next hole again (measured 2026-09-24: 8 of the findings of the third round were made by the second round's fix). **Have a different reviewer hit the plan before writing, and fold the predicted holes into the plan before writing**: this node produces that plan.

## What to do

<!-- if not replan -->
Put every unit you owe a fix into one of the plan's items. The units you owe are the units labeled block and the do-now units, except the units that raised a question waiting for a person's answer (fork) and the units that wait for the answer to that question (depends). Which units you owe is decided by the mark on each row of the section "Units to fix in this round": `must be in the plan` is a unit you owe, `may be in the plan` is a unit left out of the duty, and `the machine fills in the previous pass's row` is a unit whose row the machine fills in. The units listed there as units you must not put in are rejected if you put them in the plan. One item may close several units (that is preferred when it follows the one-shot principle), but only units that truly share a root (see "How to group items" below).
<!-- end replan -->

For each item:

1. `unit_keys`: the no of the units this item closes (the numbers in the list of units; do not copy the keys).
2. `approach`: what you change and how. Be concrete, with the names of functions, fields, and documents.
3. `files`: **everything newly created**, one row per file (what you remove is in 4 below). In every row always write `path` (one file, relative to the root of the working tree), `op` (create = new, modify = change, delete = remove, rename = move; for rename, put the original path in `from`), `responsibility` (the one responsibility of that file), `symbols`, `home`, and `considered`.
   `symbols` is the list of names added or removed in that file; for each, write `name` (an identifier; do not write a path, or a string that ends with the extension of the row's `path`) and `change` (add or remove). Samples of what gets newly created (a list so that you do not leave things out): functions, fields (schemas, records), fences (checks), prompt text, documents, CLI entry points, arms, tests, and settings.
   Write `home` (the name of the concept this row becomes the home of, `concept`, and why you chose this place, `why`; do not write the place's path, since the row's `path` holds it) and `considered` (the list of other places you thought of and set aside, one or more; for each, `path` and `why_not` (why you set it aside, 10 characters or more)) on every row, whatever the `op`. The rules the check applies are in the description of `files` in the works fields below.
   **What you leave out is not reviewed**: the review of the plan does not look at what is not in the plan.
4. What you remove or merge (copies, unused entry points, old text) also goes in `files`: a file you remove is a row whose `op` is delete or rename, and a name you remove is a symbol whose `change` is remove. On the removing side, `why` (why you remove it, 10 characters or more) is required, and if there is a replacement, also write `replaced_by` (`<path>::<name>` or `<path>`). On the adding side (rows whose `op` is create or modify, and symbols whose `change` is add), do not write `why` or `replaced_by`.
5. `shrink_first`: the result of first thinking about **whether it can be closed in a form that removes or merges instead of adding**. If the plan adds, write why you do not take the removing form.
   A fix that "adds a fence" tends to become the seed of the next round's findings (the paths the fence does not watch become the next entry point).
6. `narrows`: **everything this plan removes or narrows among the capabilities that BASE had** (what = what can no longer be done, why = why it is needed). The baseline of the comparison is the item "inventory of migration regressions (BASE capability inventory)" of the viewpoint source (the REVIEW.md that "Viewpoint source:" in the Repository line names): count as capabilities not only functions but also the speed of iteration, the means of debugging, observation, and the default safety devices. If there are none, an empty array.
   If you write even one, the run asks a person before fixing. **Do not decide on your own to accept it as a cost**: if you leave it out, a later review raises it as a regression, and it goes to a person all the same.

Do not touch anything yet. A different reviewer reviews the plan, and you will be asked later to answer the holes it predicts.

Works fields of a plan item: write them in every item of plan[]. route = the way to fix (tdd = write a failing acceptance test first, then fix; direct = fix without writing a test first; static = a fix with no behavior a test can show, such as documents, comments, setting values, the wording of instructions to AI nodes, and CI settings; tidy = removing something unused that no user can reach (the behavior stays; a removal a user can see is direct); pin = the code is right and only a test that would catch the defect is missing, so the fix adds tests that pin the current behavior and changes no code). These three words say what kind of fix the item is, not a preference for how to fix it. route_why = why you chose that word (10 characters or more when route is not tdd; may be empty when it is tdd). tests = the list of acceptance tests this item newly adds (one or more when route is tdd). Each row has id (<path>::<class>::<name> or <path>::<name>; the path is relative to the root of the working tree and names a test that does not exist yet), behavior (the behavior it checks), path (how it goes through the real path; do not assert a mock's return value), red_kind, and red_why (why it is red with the current code). red_kind is either an assertion failure (assertion) or an expected exception that is not raised (exception). A failure of a name declared in the item's files (the name of a change=add symbol, and the path of an op=create .py) counts as red; a failure of a name outside the declaration, or a failure of import or collection, does not count as red. A test that you add in the symbols of files (a change=add symbol whose name starts with test, in a file of tests or rewrite_tests) must also be a row of tests of some item; for a rename (the old name removed, a new name added), write the new name as a row of tests too. The check rejects a plan that lacks it, because a new test that is in no tests row can only be added by asking about the scope during the fix. Match the id and the place of tests to how the existing tests are placed in the file they name (if there is none, an existing test file in the same directory): inside a class or at the top level, and how the classes are named. rewrite_tests = the list of existing tests whose expectation you rewrite because the request changes the behavior. Each row has id (a test definition in the working tree), behavior (the behavior that changes), old (the current expectation), and new (the new expectation). Do not write rewrites that only make the expectation match the implementation. refactor = the declaration of tidying {declared, why} (if you tidy, set declared to true and write the reason in why, 10 characters or more). The approved plan is cut into a brief per item and becomes the source of the requirements for the fixing step. Existing tests that rewrite_tests does not name cannot be changed by the fix. The check rejects gaps and errors by naming the row plan[<i>].<field>. allowed_paths = the list of globs of the paths this item may write (one or more; relative to the root of the working tree, separated by /, and ** crosses levels). The files of the ids of tests and rewrite_tests are in the scope even if you do not write them, and a plan that applies an out_of_scope glob to such a file is rejected. Also write in allowed_paths the original paths of the files you move or delete. Documents that come with the fix (records of policy, design documents, change logs, and other documents that you rewrite when the fix changes a behavior or a decision) also go in allowed_paths and files if you rewrite them (if you leave them out, the fix has to ask about the scope midway). Whole permissions with no letters (only *, ?, [..], and .), such as ** or * or **/* or **/?* or **/*.*, are rejected. out_of_scope = the list of things inside the scope that you do not touch, {glob, why} (why is 10 characters or more; an empty list if there are none). When fixing, the check compares the diff with this scope, and if the diff goes outside it, sends it back with the same brief. files = the list of rows, one per file, of what you add and what you remove (FILES_SCHEMA). Each row has path (one file, relative to the root of the working tree), op (create = new, modify = change, delete = remove, rename = move; for rename, write the original path in from), responsibility (the one responsibility of that file), symbols (the list of names added or removed in that file, [{name, change (add or remove)}]; write name as an identifier (the name of a function, a field, a CLI, or a test), and do not write a string that contains / (except a pointer to a field that starts with /) or that ends with the extension of the row's path; the path goes in the row's path), home ({concept, why}: the name of the concept this row becomes the home of, concept, and why you chose this place, why; do not write the place's path, since the row's path holds it), and considered ([{path, why_not}], one row or more: other places you thought of and set aside; path is only the path of a file (not of the form lib/x.py:12; write line numbers in why_not), and why_not is why you set it aside, 10 characters or more); write all of these in every row, whatever the op. The check applies five rules: a considered path is the same as the row's path; the same path is written twice in one row; a malformed path (\, outside the root, not normalized); the first level of a path with two or more levels does not exist at the root of the target; the same home.concept (ignoring leading and trailing spaces and case) is placed on two rows of the plan (if the considered of one row holds the path of the other row, it is also rejected as a contradiction; the home of an op=delete row is not counted). From the diff, the machine looks for a change=add name in the lines added to the row's path, a change=remove name in the lines removed from it, and the path of op=create, delete, and rename in what is created, deleted, and moved. For what you remove (rows whose op is delete or rename, and change=remove symbols), always write why (why you remove it, 10 characters or more), and if there is a replacement, also write replaced_by (<path>::<name> or <path>). Do not write why or replaced_by on the rows of what you add. Put in allowed_paths the files that name a name you remove. A later review answers for the hits you do not put in. depends_on = dependencies between items (optional). If a later item assumes the result of an earlier item, do not merge the items but split them, and in the later item write {unit: <one of the earlier item's unit_keys (written the same way as unit_keys)>, receives: [<what it receives from the earlier item's files: <path>::<name> or <path>>]} (the check rejects the item's own units, units not in the plan, things not in the earlier item's files, and cyclic dependencies). structure = the list of answers to the rows that the structure eye saw as dirtying (the units of the section "Rows of the structure eye"). An item that has such a unit in its unit_keys writes, per row, {row: <the unit's id (as written at the head of the row)>, follows: true} (it follows the way to avoid, chosen) or {row: <the unit's id>, deviation: <why it does not follow, 20 characters or more>} (the check rejects gaps). An item that departs from a prescription of the judgment (the section "Prescriptions of the judgment") may list {prescription: <the unit's key>, deviation: <reason>}, and, if it follows the prescription, {prescription: <the unit's key>, follows: true}. If the section "Rows of the world solution" has places that rows apply to (rows that need an answer), then for each row that needs an answer, some item writes {world: <class id>, follows: true} (it follows the practice) or {world: <class id>, deviation: <why it does not follow, 20 characters or more, with a source (a URL, <path>:<line>, or the path of a decision record)>} (files in the run's place (the instruction file, the judgment's judgment.json, records) are outside the working tree, so cite them as absolute path:<line> (a bare name or a relative path is looked up from the root of the working tree, so if it is not in the working tree, the source is read as not existing and the row goes to a person)). The check rejects a row that needs an answer and that no item answers. A deviation whose source is the request itself goes to a person before fixing. An item that has neither a dirtying row nor a world-solution row that needs an answer writes an empty list or leaves the field out.

How to group items: merge units into one item only when they share a root and close with one fix, or when they change the same line or the same hunk. When one fix depends on the result of the other (it cannot be fixed or tested before the other is fixed), do not merge them either: split the items, and in the depends_on of the later item write the earlier item's unit and what it receives (<path>::<name> or <path> from the earlier item's files) (the fixing step puts dependent items in the same group and fixes the earlier item's unit first; the check rejects cycles, dependencies on the item's own units, and received things that are not in the earlier item). Touching different places in the same file (a different function, a different class, a test added to a different class) is not a reason to merge items: split such units into separate items. The rule "one item may close several units (preferred when it follows the one-shot principle)" is about units that truly share a root.

Look for what already exists first: before you add a new mechanism (a script, a subcommand, a helper function, a test fixture (a fake tool, a test bundle, and so on)) as an op=create row or a change=add symbol in files, Grep the files the plan touches and their siblings (other jobs and steps of the same workflow, other files in the same module or the same place) for a helper that already does the same job. If there is one, make the plan use it and do not add a new one. If you still add a new one, write in that row's considered the path of the existing thing you found (path) and why you do not take it (why_not) (if you found none, the path of the sibling place, and in why_not where and how you looked). A new module is shown by an op=create row (the row's path is the module's path). A later review raises a new mechanism that you do not write as a hole.

Code comments, docstrings, and test descriptions (the target's text) that are not in the section "Recorded policy" of the material are not the owner's decisions. Do not use them as earlier decisions or as policy in the why of out_of_scope or in the decided_by of narrows: if the plan's fix disagrees with such text, put the rewrite of that text in the plan.

One axis of judgment: does the whole become simpler while the purpose is met and the protecting mechanisms keep working? Simplicity is measured not by the number of lines but by the number of places that know a design concept.

Use the homes of concepts: for each concept the plan touches (a rule of the design; for example, outcome words, stop reasons, the policy for unattended runs), first look in the target repository for a place that holds it in one place (its home): the rows of the section "Map of where concepts live" if it has a map; otherwise Grep the README, the module boundaries, and the places that hold the same word as a constant. If there is a home, the plan changes it there and does not copy the same word, field name, value, or decision rule to other places. If a row of files (an op=create row, or a row with a change=add symbol) still makes a new place know the concept, write in that row's considered {path: <path of the home>, why_not: "concept home: the home of <concept> is <path>" and why you do not use the home}. When you add to a concept that has no home, first choose the form that gathers it into a place that already knows the concept and does not add places that know it.

The deciding source of each approval item: in each row of plan[].narrows, write the deciding fields. decided_by = the source that decides: a URL and its section; <path>:<line> (the same situation in the target = how the code solves the same problem; the intent that comments and docstrings state does not count); the naming of a row of the recorded policy (exactly as the naming is written in the section "Recorded policy" of the material: a person's earlier decision = an ADR, a settled point, an answer of the request, an answer at an approval node); the path of a record of a design decision; or a quote from the request 「…」 (the request's text as it is, in 「」 brackets). The machine checks that the source exists, and rows whose source it cannot check go to a person. Files in the run's place (the instruction file, the judgment's judgment.json, records) are outside the working tree, so cite them as absolute path:<line> (a bare name or a relative path is looked up from the root of the working tree, so if it is not in the working tree, the source is read as not existing and the row goes to a person). undecided_because = why the answer does not settle to one even after checking the deciding sources (if you cannot write one, leave it empty: then it is obvious, so it does not go to a person). fences = the marks of the fences it hits (external_write: writing outside; irreversible: an operation that cannot be undone; policy_doc: a change to the policy document; widen_protection: widening a protection (credentials, sandbox); web_doubt: a web result raised a new doubt). A row that has decided_by, an empty undecided_because, and no fences, whose source exists, whose world-solution axis is in place (in a run that has the section "Rows of the world solution", a deviation from a row is asked once by the approval item for deviations from the world solution and does not enter this row's axis; in a run without that section, the row has world or a URL as its deciding source), that does not hit a unit that the structure eye raised to a person, and that names nothing outside the plan's units, passes without the run asking a person before fixing, and is listed in the report with its source (and in the text of the last approval node, if that opens). Rows with no deciding source, rows that do not settle, and rows that hit a fence are asked of a person as before. Before you send something to a person, check how the world solves the same problem: if the section "Rows of the world solution" is present, use its rows (per request line: the class of problem, the practice, and the comparison with the request's way of solving it). Only for questions with no row, look up the practice of standards, well-known OSS, and official documents yourself. The way the request suggests is not a deciding source (it is a proposal to doubt by comparing it with the practice). If the practice settles it to one, write that source in decided_by and decide it yourself. In every row, write world = one sentence on the result of checking (the source and how it splits; if you found nothing, why; for a row decided by a person's earlier decision, say so). In a row that goes to a person, it appears as it is in the approval item. In a row that goes to a person, also write recommend = the one answer you recommend {answer: continue (let it through) or stop (stop it), note: the scope and conditions for letting it through, or the reason to stop it, that can be copied as it is as a word at the approval node (4 characters or more), why: why you recommend it (4 characters or more)}. It appears as the recommendation of the approval item. In an unattended run, if every recommendation of the approval items says continue, the run passes the approval node with those recommendations, and the note becomes a word to the fixing step. If any recommendation is missing or says stop, the run stops, and the recommendations become drafts of the answers in the draft request of the next run (not used until a person reviews them).

Look first for a plan that does not narrow: before you write narrows, check a form that avoids the narrowing: a form that applies new behavior only to the cases you want to fix and, where it cannot be applied (there is no field in the record, it cannot be counted, the tool is different, and so on), keeps the BASE behavior and names it in the report or on standard error instead of staying silent. If there is one, take it into the plan and do not write that row in narrows. Only when there is none, write the row in narrows, and in each row write no_narrow = the result of your search (which plan that does not narrow you checked, and why it cannot be taken; 20 characters or more). The check rejects missing rows and short rows, and the text you write appears as it is in the approval item.

<!-- if excluded -->
Range of parallel pull requests. Do not touch it, and do not put it in a unit: {excluded_file} (Read it first. The ranges listed there are handled by other pull requests.)
<!-- end excluded -->

{lib_docs}

{shared:prior-failures}

{shared:recorded-policy}

{shared:concept-map}

{shared:query-rule}

{shared:handoff}

<!-- if units -->
## Units to fix in this round (pasted by the machine from the judgment; point to them in unit_keys by the no below)

{units}

The mark at the end of each unit row is its duty: `{duty_owed}` — the unit must be in the plan; `{duty_may}` — the unit may be in the plan (it is the origin or depends of a question that waits for a person's answer; it may be left out); `{duty_filled}` — the machine fills in the previous pass's row (you need not write it if unchanged; do not write closed items).
<!-- end units -->
<!-- if filled -->
- The machine fills in these numbers (items of the previous pass's plan; you need not write items you do not change; do not write closed items): {filled}
<!-- end filled -->
<!-- if units -->
- Units you must not put in (the check rejects them): {shut}
<!-- end units -->
<!-- if skipped -->
- Units the structure eye did not look at (their paths were empty, so nothing was measured): {skipped}
<!-- end skipped -->

<!-- if questions -->
Question ledger (units named as the origin of a fork or in depends may wait: you need not put them in the plan): {questions}
<!-- end questions -->

<!-- if view -->
The judge's view: {view}
<!-- end view -->

<!-- if precedents -->
The judge's precedents (world solution): {precedents}
<!-- end precedents -->

<!-- if units -->
Repository: {repo} (version read: `{read_rev}`)  BASE: `{diff_base}`  Viewpoint source: {review_md}
<!-- end units -->

<!-- if prescriptions -->
## Prescriptions of the judgment (the ways to fix that the judge wrote per unit, starting from the zero prescription; pasted by the machine from the judgment record)

Take the unit's prescription in the plan. If there is a prescription you do not take, write {prescription: <the unit's key>, deviation: <why you do not take it>} in the works field structure of the item that has that unit (do not drop the relations and conditions of the prescriptions silently). When you cite a prescription as a deciding source, cite it not by the rows of this section but by absolute path:<line> of the judgment record judgment.json.
Judgment record: {judgment_file}

{prescriptions}
<!-- end prescriptions -->

{part:structure-rows}

<!-- if world -->
## Rows of the world solution (per request line: the class of problem, the practice in the world, and the comparison with the request's way of solving it)

{world_rows}

For each row that has a place it applies to (a row that needs an answer), some item writes in its works field structure that it follows the practice ({world: <class id>, follows: true}) or why it does not ({world: <class id>, deviation: <reason and source>}) (the check rejects a row that no item answers). The request's way of solving it is a proposal to doubt by comparing it with the practice, and it is not a deciding source: a deviation whose source is the request itself goes to a person before fixing. Answer the rows marked ({not_web}) in the same way.
<!-- end world -->

<!-- if ripple_units -->
## Ripple list before the plan (looked up by the machine with git grep: the callers and tests of the names that the unit keys name. Read it before you write the plan)

A hit not covered is a hit that is in none of the item's paths it may write (allowed_paths), acceptance tests (tests), or tests to rewrite (rewrite_tests). Put what the fix touches (adjusting the callers, rewriting tests that assert a literal value) in that item's allowed_paths or rewrite_tests now. What you put in the plan can be written during the fix without asking about the scope (outside the scope, the only way is for the fix to ask for permission). Do not put in what you do not touch (a later review checks each hit: covered, not affected, or a hole).

{part:ripple-notes}

{ripple_units}
<!-- end ripple_units -->

<!-- if ripple_units_error -->
## Ripple list before the plan (looked up by the machine with git grep: the callers and tests of the names that the unit keys name. Read it before you write the plan)

Could not build the ripple list ({ripple_units_error}). Look up the callers and the tests yourself.
<!-- end ripple_units_error -->

<!-- if verify -->
## Notes from the check of the judgment's units (an eye different from the judgment checked each unit; pasted by the machine)

The units are what you owe a fix, and these notes do not reduce them. A unit reported as not the root, in a different place, or without evidence cannot be left out of the plan either (the check rejects it). Put such a unit in the same item as the unit of the real root, or write in approach your answer to the note (how you handle it). Use duplicates, relations at the same place, and order for grouping items (follow the rule "How to group items" above). Use relations at different places (only touching different places in the same file) only as a reference for the order of items, and do not merge items because of them. Read a unit that could not be checked as the judgment has it.

{verify_rows}
<!-- end verify -->

<!-- if verify_unreadable -->
## Notes from the check of the judgment's units (an eye different from the judgment checked each unit; pasted by the machine)

The notes file {verify_file} cannot be read (read the units as the judgment has them).
<!-- end verify_unreadable -->

{shared:unknown-asks}

<!-- if spec -->
## Spec (requirements and acceptance tests. Put each acceptance test in the tests of the item that holds its unit)

{spec}
<!-- end spec -->

<!-- if routes_spec -->
## Route of each item (decided by the spec)

The person who wrote the spec decided which places are fixed test-first: they are named in the spec's section "TDD で直す所" (places to fix with TDD). Give `route: tdd` only to an item that fixes a place named there, and `route: direct` to every other item, with a `route_why` that says the spec does not name it as a place to fix test-first. If the spec has no such section, every item is `direct`. An item the spec does not name may instead take `static`, `tidy`, or `pin` when it is that kind of fix as the works fields above say, with a `route_why` that says so. Do not choose the route by your own judgment beyond this; the fix step follows these routes as they are.
<!-- end routes_spec -->

<!-- if prior -->
## The previous round's plan and the review's findings (pasted by the machine)

<!-- end prior -->
<!-- if prior_fix_plan -->
- Plan of the previous round: {prior_fix_plan} and {prior_fields} (Read them. Keep closed items in this form, unchanged.)
<!-- end prior_fix_plan -->
<!-- if prior_fields_only -->
- Fields of the previous round's plan: {prior_fields} (Read it. Keep closed items in this form, unchanged.)
<!-- end prior_fields_only -->
<!-- if prior_review -->
- Review findings: {prior_review}
<!-- end prior_review -->
<!-- if no_prior_review -->
- Review findings: not received (they could not be read, or were not passed).
<!-- end no_prior_review -->

<!-- if revise -->
The review (a different reviewer) raised the blocks below (holes that keep the fix from going ahead) against the plan. For each block, if you fixed the plan, write fixed in handled and where you fixed it in how; if you dispute it without fixing, write disputed in handled and your grounds in how; write one row each in block_answers (copy the key below without changing a single character). Then return in plan only the rows of the items you changed (rows of the same type as the previous plan. Do not write closed items. You need not write the open items you do not change or the held items either; the machine fills in the previous pass's rows. Return the changed rows of the items of the blocks you answered fixed). For the suggests below that need an answer (those on open items), also write one row per key in block_answers, as for blocks. Suggests are not counted for when to stop. The fixed plan goes to a review in a new conversation, and if a central block (one whose reach is not peripheral) remains, the run stops before fixing instead of going ahead. If the open blocks are only peripheral, the run goes ahead to the fix, and the peripheral blocks are passed on.

{revise_blocks}
<!-- end revise -->

<!-- if owed_suggests -->
## Suggests that need an answer, from pass {revise_pass}

{owed_suggests}
<!-- end owed_suggests -->

<!-- if revise_notes -->
For reference: suggest holes that need no answer (those on closed or held items, and those the review said are gone. You need not answer them, and you may take them or not. Do not reopen items for them. They are also passed on later as part of the review's answer):

{revise_notes}
<!-- end revise_notes -->

<!-- if revise_keys -->
Keys of the suggests: {suggest_keys}
<!-- end revise_keys -->

<!-- if closed_items -->
The items below were closed in the previous pass, with no block raised by the review. Do not write them in plan (the machine fills them in as the previous pass's rows):
{closed_items}
<!-- end closed_items -->

<!-- if held_items -->
The items below were held because the same block persisted (you need not fix them; if you do not write them, the machine fills them in):
{held_items}
<!-- end held_items -->

<!-- if prior_ripple -->
## Ripple list (looked up by the machine with git grep: the callers and tests of the names that the items change)

A hit not covered is a hit that is in none of the item's paths it may write (allowed_paths), acceptance tests (tests), or tests to rewrite (rewrite_tests). Put what the fix touches (adjusting the callers, rewriting tests that assert a literal value) in that item's allowed_paths or rewrite_tests now. What you put in the plan can be written during the fix without asking about the scope (outside the scope, the only way is for the fix to ask for permission). Do not put in what you do not touch (a later review checks each hit: covered, not affected, or a hole).

{part:ripple-notes}

{prior_ripple}
<!-- end prior_ripple -->

<!-- if prior_ripple_error -->
## Ripple list (looked up by the machine with git grep: the callers and tests of the names that the items change)

Could not build the ripple list ({prior_ripple_error}). Look up the callers and the tests yourself.
<!-- end prior_ripple_error -->

<!-- if policy -->
{shared:policy}
<!-- end policy -->

<!-- if replan -->
Of the items of the approved plan, fix only the items pasted below. During the fix, an objection was raised that these items are wrong, and the ruling judged it fix_plan_item (an error in the plan item itself). Read the text of the objection and the text of the ruling, and return the items with the places that the ruling names fixed. plan has the same number of items in the same order as the items pasted below, and in each item copy the pasted unit_keys strings without changing a single character (do not write numbers). Write the unit of depends_on, too, in the same characters as the unit_keys of the earlier item's unit (not as a number). Do not return the other items. The items you fix go to a later review, and when you change a promised field (unit_keys, narrows, the removing side of files (rows whose op is delete or rename, and change=remove symbols), allowed_paths, out_of_scope, rewrite_tests, or the behavior of tests), they are shown to a person at an approval node.

{replan_items}

{shared:brief-reading}
<!-- end replan -->

<!-- if unread -->
## Inputs that could not be read (written by the machine; those sections are not in the material)

{unread}
<!-- end unread -->

Do not write `{whole_plan}` (only a resubmission in this conversation writes it).

Write the fields that people read (approach, shrink_first, every why, why_not, no_narrow, undecided_because, world, deviation, the what of narrows, the note and why of recommend, the how of block_answers, and handoff, and any other free-text field shown at approval nodes or in the report, such as the behavior, old and new of tests and rewrite_tests, responsibility, the concept of home, route_why, and red_why) in {lang}. Keep keys, enum values, code identifiers, paths, commands, and error messages as they are (keys are matched across rounds, so do not translate them).

Return only JSON that matches the output schema.
