<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

<!-- if rulings_first -->
Read the file with the rulings on the conflict declarations, {rulings_file}, all of it, first. Fix as the rulings say and return the whole answer again (the text of the rulings itself is not pasted here).
<!-- end rulings_first -->

<!-- if ruled_reply -->
The first fixer's answer (saved by the machine): {saved_reply}. Read it all first. Learn the earlier fixes and declarations from this file and the rulings file (the fixes in the working tree are still there).
<!-- end ruled_reply -->

<!-- if briefs -->
## The requirement (briefs)

{brief_rows}

Read them all first with Read. Follow "Brief rules (the source of the requirement and the background)" in the rules below.
<!-- end briefs -->

<!-- if faces -->
## Pre-review keys to answer (plan_faces)

Answer every key below in the answer's `plan_faces`, one row per key (copy the key without changing a single character; do not write keys that are not in this list). The acceptance asks `plan_faces` for an answer to all of them.

{faces_rows}
<!-- end faces -->

<!-- if scope -->
## Paths you may change and what you must not touch

The acceptance checks the paths you changed against these values and rejects what is off. If a path you declared in `changes[].files` is explicitly allowed by one of that unit's items (allowed_paths, the test files), it is checked only against the `out_of_scope` of that unit's items (the `out_of_scope` of other items does not apply). For every other path, the `out_of_scope` of every item is stronger than the scope and also wins over the permitted paths (only a path excluded through a scope consultation does not apply for that item). The paths and test permissions allowed by scope consultations are included here too.

{scope_rows}
<!-- end scope -->

<!-- if tests -->
## Tests you may add or change, and frozen tests

The acceptance checks the tests you added, the existing tests whose bodies you changed, and the frozen test files against these names, and rejects what is off. If you need something off the list, ask in a scope consultation before you change it.

{tests_rows}
- Changing or removing the body of any other existing test function is rejected.
<!-- end tests -->

<!-- if tests_how -->
## How the tests were run before the fix

These are the forms the test stage before the fix actually ran.

{tests_how}

Run tests in this form without searching for environments or commands (narrow them as the rules below say).
<!-- end tests_how -->

<!-- if policy -->
The policy document: {policy_path} (read it all first).
<!-- end policy -->
<!-- if no_policy -->
There is no policy document.
<!-- end no_policy -->
<!-- if request -->
The request file: {request_file} (read it all first).
<!-- end request -->
<!-- if no_request -->
There is no request file.
<!-- end no_request -->

<!-- if rules -->
# Fixing (the writer's job)

You are the fixer. You read the judgment, cut into root units (unit) and passed by the acceptance, and fix the units you owe a fix on the working tree. The machine (the shared board) accepts your answer and recounts before and after the fix with the judgment's way of counting.

## What to read

- The judgment file: {judgment_file} — background (the source of the requirement is the briefs at the head. If there is no briefs section at the head, the judgment is the source; follow rule 6 of "Brief rules (the source of the requirement and the background)" below. The machine puts that section after these lines, and rule 6 says "in a run without briefs and for a unit without a brief, the judgment file is the source; Read it all first"). Read it with Read when you look up the fields of the briefs' units. Each unit in `units` has `key`, `label`, `disposition`, `reason` (facts and refutation), `origin_analysis` (where it came from), `class_query` (the query that finds every instance of the same shape), and `prescriptions` (prescriptions, listed starting from the zero prescription = withdraw, and from the proposal that makes do with one existing mechanism), and there are `framing`, `one_shot`, `questions` (the question ledger), and `precedents` (the precedent rows).
- The keys of the units you owe a fix (a JSON array; the same set the acceptance reads. The origins of questions waiting for an answer and the units of rulings not to fix (ask_human, fix_plan_item) are not in it, and units a person answered and returned are in it): {open_units}
- The fix plan (written by another role and attacked by another eye in the pre-review): {plan_file} — you need not read the whole fix plan (the requirement is cut out into the briefs; if there is no briefs section at the head and this is not empty, Read it). The keys of the pre-review's holes (`faces`) and alternatives (`shrink`) you answer in `plan_faces` are all in the section "Pre-review keys to answer (plan_faces)" the machine pasted into these instructions. If empty, the run has no fix plan and no answer to the pre-review is needed.
- The person's policy document: {policy_path} — if not empty, read it all first.
- The result of the TDD loop: {summary_file} — if empty, the loop did not run (fix every unit as these instructions say). If not empty, Read it all. The "units the loop fixed" are already fixed in the working tree, and the machine confirmed the test's red-to-green. Do not fix those units again; write one row in `changes` (in `files`, the fixed files and the test files; in `closure`'s `red_seen`, the red-to-green the machine saw). Do not change those units' test files (the acceptance rejects it; only what the fix plan names in `rewrite_tests` and the scope of a fix_test_scope ruling are exceptions). The "direct units" are fixed here (the units listed under the summary file's heading "## direct の単位（ここで直せ）": units the TDD loop did not take, for reasons such as not being able to write a test first, and assigned to be fixed with these instructions).
- The file with what was answered at the approval node (answers to questions about changes that reduce or narrow capability, or changes to the person's policy or the policy document; a person's answer, or the recommendation an unattended run took, and a recommended answer has "無人の run が採った推し" on the line just before it): {notes_file} — if empty, nothing was asked. If not empty, Read it all (the body of the comments is only in the file). A comment is a scope and a condition to let through; **do not cut beyond it**.
<!-- end rules -->

{part:brief}

{shared:writer-rules}

<!-- if rules -->
- Do not say "done" without changing anything. A fixed check later finds the empty diff and fails the run.
<!-- end rules -->

<!-- if ask -->
## Scope consultation and the pre-check

Whether to widen the scope is a specification decision, and the fix plan's side decides it (a role that reads the fix plan and answers as its author). Do not change things outside the scope silently. Do not end your start by returning a conflict declaration only because you need something outside the scope. Consult first, and if it is allowed, go on fixing.

1. **Scope consultation (the answer field `consult`)**: when you need to change a file outside the brief's `allowed_paths` (a record of changes, documents, and the like that go with the fix; also things that hit the brief's `out_of_scope`), and when you need to rewrite a frozen test (the test files of units the TDD loop made green), write a request in the answer's `consult` field and return before you change it. One entry is one item: `item` (the fix plan's item number), `paths` (the paths you want to add, relative to the repository root), `tests` (the range of existing tests you want to rewrite: `<path>` or `<path>:<line>`; the line is the line in the version before the fix), `new_tests` (optional; the ids of new tests not in the fix plan's `tests` that you want to add, `<path>::<class>::<name>`), and `why` (why it is needed and what you will change how; concrete enough for the other side to judge it as a specification). List requests for different items one by one.
   - In a round where you return `consult`, the acceptance does not run. You may fill the other fields in their current, in-progress form (the machine does not look at them). Leave the fixes in the working tree as they are (do not remove them). Even without your asking first, when the acceptance finds a change outside the scope, a test outside the fix plan, or a rewrite of a frozen test or of an existing test function outside the named ones, the machine may send it to the same consultation (in that round an instruction comes to return the same JSON as the previous answer without changing the working tree).
   - A role that reads the fix plan answers on behalf of its author, and the machine checks the answer and keeps it on the shared board. In the next round, in the continuation of this conversation, an instruction naming the answer file comes.
   - What hits `out_of_scope` was excluded by the fix plan's side itself. The machine passes the consultation with the reason for the exclusion, and that side reconsiders and decides. In `why`, write why the reason for the exclusion does not hold for the current fix.
   - If allow, you may add only "what entered the scope" in the answer file and fix (if there is a supplement to the specification, follow it). The acceptance puts it in the scope.
   - If deny, fix within the scope. Only when you see that the request cannot be met within the scope and that the views of the specification are split, return a conflict declaration (`kind` is `scope_needed`).
   - If defer, do not fix it in this run. Write that you did not fix that place, and why, in `what` (per unit) or in `not_done`.
   - If there is no answer (refused, unavailable, invalid), read the reason in the answer file. If it could not be asked, return a conflict declaration (`which_is_right` request, `kind` `scope_needed`) as the rule before consultation says (rule 8 of "Brief rules (the source of the requirement and the background)" above: do not change things outside the scope).
   - Consultation rounds have a budget ({budget} in this stage's loop). A `consult` after the budget is used up is rejected by the acceptance. If you still need something outside the scope after it is used up, do not change things outside the scope, and return that unit as a conflict declaration (`which_is_right` request, `kind` `scope_needed`) (units that close within the scope may be fixed). Do not ask to rewrite tests to fit expectations to the implementation.
   - A subagent (an implementer started with Agent) cannot consult itself. If a subagent reports that it needs something outside the scope, this role writes it in `consult` and returns (the subagent's fixes may stay as they are in the working tree or the unit's worktree).
2. **The pre-check**: before you give your answer, Write a draft identical to the JSON you return to {draft} (do not write it into the working tree), and run the following with Bash. Subagents run it without `--reply`.
   {check_cmd} --reply {draft}
   The rejection lines of the same fact checks as the acceptance (frozen tests, the origin of writes, the approved fix plan's scope, the references you wrote (the answer's `wrote_refs` and the Markdown links the diff added); no tests are run) are listed in `rejects` (exit code 0 passes, 1 means there are lines). If there are lines, fix them or consult before you return.
<!-- end ask -->
<!-- if ask_ripple -->

The ripple list: {ripple_file} (the callers and tests of the names the approved fix plan's items change. It names hits that are not in the scope. If you find you need to touch such a hit in the fix, ask in the scope consultation above before you write).
<!-- end ask_ripple -->

<!-- if libdocs -->
## Library documents (installed version and official)

The machine fetched the documents of the libraries the files of this unit use from two sources and kept them whole as files on the shared board (the bodies are not pasted here; below, each library has a block with its name, version, source, and file paths): (1) the installed version: signatures and descriptions read, without importing, from the code of the version installed in the run's working tree or in the main working tree of the same repository (the installed code itself); (2) official: the library owner's documents (the README on PyPI or npm, llms.txt in the docs location; matched to the version where possible). When you need an API's signature, arguments, or usage, Read that library's file (you may decide whether to read it by whether you need it; search by the names the unit uses). For the libraries below under "no document from anywhere" and for what is missing here, fetch the official documents yourself with WebSearch and WebFetch.

{libdocs_rows}
<!-- end libdocs -->

<!-- if g1 -->
## Running subagents

1. In the order of the items below, start one implementer subagent with the Agent tool, and give it the whole content of the implementer file in the prompt, without changing a character. The subagent starts in a new conversation for each item (it has no history of the previous item's conversation). From the second item on, add a section with the heading `## Handoff from the previous items (written by the fixer from the earlier implementers' reports)` after the file's content, and write one line per finished item (the item number, and the changed files and tests made green from the implementer's report). The previous items' fixes are in the working tree, so do not have them reverted or redone.
2. When you receive the implementer's last message, run that item's diff command with Bash (it writes to an absolute path in the per-run place; new untracked files are included as full diffs), and start a reviewer subagent with a separate Agent. In its prompt, paste the whole content of the reviewer file and, after it, the implementer's last message. The diff is the whole from base and includes the previous items' fixes (the reviewer file says so too).
3. If the review's answer is `❌` or `Needs fixes`, start the same item's implementer again with the findings and start the review once more. At most 3 implementers per item. Even if the third review does not pass, that item's units you owe a fix go in changes like every other form (a unit you owe a fix always has one row in changes). Write the remaining findings in that row's root_or_symptom, with kind symptom and the findings in why. If the acceptance rejects that unit, the acceptance's last round reverts only that unit's fix and stops it (the other units pass). Only when a unit cannot be fixed at all (its way of fixing cannot be decided without a person's answer), and when the implementer returned NEEDS_CONTEXT or BLOCKED, return it as a conflict declaration (conflicts) without fixing it (ASK of the reading rules below).
4. When the acceptance asks you to resubmit (the rejection paragraph at the head names the reasons) and in the second round after a ruling (the rulings file is named), start again only the subagents of the items the rejection reasons or the rulings name (the other items' fixes remain in the working tree).
5. When all items are done, check the working tree's diff yourself (do not trust the subagents' reports; DELEGATE of the reading rules), and return only the JSON of the answer fields. Write the files a subagent reported writing with Bash in the answer's bash_writes with path and reason (writes with Edit and Write appear in the record).
6. The machine's gates are applied after the answer: the acceptance test's red-to-green and the freezing of existing tests by the fix acceptance's bundle, the tests the change reaches by the acceptance, and test_cmd by later stages. For the subagents' "commit" and "ask a person", the works rules at the end of the subagent file apply.

The units the TDD loop fixed (the "units the loop fixed" in the loop's summary file) are not in the items below. Do not start subagents for them; write one row in changes as the result of the TDD loop in "What to read" says.

{g1_items}
<!-- end g1 -->

<!-- if seat_one -->
## The borrowed seat

The promises of these instructions' stage (the JSON to return, the machine's gates, the order of the stage) and the reading rules below win over the borrowed text.

### The helper template (superpowers {seat_file}, wrapped in works sections)

{seat_body}
<!-- end seat_one -->

<!-- if rules -->
When the implementer template's status words NEEDS_CONTEXT or BLOCKED (the works word divergence) apply, do not count that unit as fixed; return it as one entry of the conflict declarations in conflicts. `kind` is the situation that occurred, one of the following (the rules of the fields are in the section "Conflict declarations (do not bend to get green)" of these instructions):
- `brief_vs_judgment`: the brief disagrees with the judgment, the request, or the conditions answered at the approval node before the fix (put that unit's brief line in `between`)
- `unnamed_test_broke`: an existing test named neither in the fix plan nor in a ruling fails when you fix, or can only be removed
- `not_red`: an acceptance test or a named rewrite does not go red even when written as the plan says, or goes red in a different way than the plan says
- `scope_needed`: it does not go green without touching something outside the brief's or the plan's scope, or the recount with the judge's query does not close (when there is a scope consultation section, only after you consulted first in the answer's consult and were not allowed; a subagent reports to the coordinating role that a consultation is needed)
- `query_hits_fixed`: the judge's query also hits the correct form after the fix (`which_is_right` is query, and `correct_lines` is needed)
- `needs_context`: the policy, the intent of the request, or which is right cannot be decided from the materials, and a person's or the request's answer is needed (`which_is_right` is unknown)
<!-- end rules -->

<!-- if g1 -->
DISPATCH (do not start subagents) and DELEGATE's "a role never hands work to other agents" in the reading rules below do not apply to this fixer: start subagents with Agent as the steps of this section say. A subagent never starts further subagents (both templates forbid it). The reading rules' instruction to tell a helper started with Agent to Read a file is not written to subagents either: the works rules at the end of each subagent file carry the subagent's reading rules instead.
<!-- end g1 -->

<!-- if rules -->
## Reading borrowed skills

When you read a borrowed skill (superpowers), follow the reading rules below. They are direct instructions to you and win over the skill's text. If you start a subagent with Agent, write in its prompt to Read this file: {overlay_file}.

{unattended}
<!-- end rules -->

<!-- if rules -->
## What to write for each fix (one changes row)

In `changes`, write **exactly one row per unit you fixed**. Do not split the same `unit_key` into two rows (the acceptance rejects it). If one unit spans several files, list them all in `files`.

- `unit_key`: copy the judgment unit's `key` **without changing a single character** (one of the values in "the keys of the units you owe a fix" above)
- `files`: the files whose content you changed to fix that unit (paths relative to the repository root). The later check looks at whether every file you write here really changed from the version (do not write caches and the like produced by running tests)
- `what`: what you fixed and how (how you closed the root, how many places of the same shape you fixed, the tests you ran and their results), in 1 to 3 sentences
- `closure` (proof of closure): `mechanism` (the defect's mechanism), `fix_mechanism` (the mechanism by which the fix closes it), `verified_how` (how you confirmed it closed), and `sites`. For a fix to a check or a guard, first list every place that shares that invariant (`sites`), inject a regression into each place one by one, see red and, after restoring, green, and write it in `red_seen` (do not stop at "I tried one and it was red"). In each row of `sites`, write in `path` the one file where that site is, as a path relative to the target root. The machine ties a site to the files hit by `class_query` through `path`, and compares the number of hits covered, not the number of sites, with the population (listing sites in the same file does not increase the count. Sites in tests and documents become visible to the person as paths "fixed outside the query". A site without `path` is not counted as coverage: coverage is counted by the sites with `path` and, of that row's `files`, the files the fix changed, and the fact that there was a site without `path` appears as a reason in the per-unit table. Only when the count per hit file cannot be looked up, the files the fix changed are counted by the number of sites whose `path` points at them). For a structural fix, a machine check (grep, execution) that the moved destination is actually used; for a wording fix, the real text after the change
- `coverage` (the population of coverage): for a unit whose judgment has a `class_query`, you need not write it; if you do not, the machine fills in the judgment's how. **The machine counts before and after the fix**: before the fix in the same fixed version the judgment read, after the fix in the current working tree (including untracked files, excluding what .gitignore hits), and the direction (defects/population) uses the judgment's value. For a unit with a `class_query`, do not write counts. **The number closed is counted by the machine from the hit files pointed to by `path` of the `closure` `sites` or in that row's `files` that the fix actually changed** (files named in a site but not changed are not counted). If you think the judgment's query misses targets or counts only the one line at the root, you may rebuild the how (write the rebuilt how; if it is narrower than the judgment's population, `remaining` needs a reason). Only for a unit whose judgment has no `class_query`, the machine has no query to use, so write how (the query that counts) and counts (the direction; the word defects or population, not a number). **Leaving something is not itself forbidden. Leaving it silently is forbidden**: if the sites you proved do not reach the population, write in `remaining` "what you leave and why you do not close it this round". **Whether it closed is decided by the machine with the recount of the judgment's query**: if the declaration (the number of hits the `sites` cover, `remaining`) does not match the recount, the machine records the disagreement in the per-unit table and shows it to the person to decide. If you say you closed everything with a query that counts the defect's shape (defects) but it still counts after the fix, the unit appears in the table as not closed (it counts even if you only left the old expression in a note). If the judgment's query also hits the correct form after the fix, do not silence it by narrowing how; have the query's replacement ruled with a conflict declaration (`which_is_right`: query and `correct_lines`)
- `root_or_symptom`: has the fields `kind` and `why`. `kind` is whether this fix closed the root the judgment named (root) or closed a symptom (symptom). **If symptom, write in why "why you stop with that now"** (if hitting the root means a new mechanism or a widened shared surface, say so and write it in `rejudge_requested`)
- `bypass_tried`: **the inputs you tried in order to break the fix while keeping it, and the results**. "It went red when I removed the fix" is detection of absence, not evidence of completeness. If it broke, fix it before you submit. If it did not break, write what you tried; do not write "not tried"
- `breaks`: **look up with the machine** the surfaces this fix may break (how = the command that finds places sharing the same path, the same invariant, the same calling order). In result, the confirmation that they still work (running the checks, grep results). If you let it through knowing it breaks, the reason in accepted
- `precedent`: for a fix that adds a mechanism or changes a shape, check with primary sources (standards, well-known open-source projects, official documentation) how the world solves the same problem before you write it: problem, source, verdict (adopt = take as is / adapt = take with changes / does_not_apply = does not apply / not_found = not found), reason. Fetch primary sources yourself with WebSearch and WebFetch (the same tools as the original graphloops writers. The original graphloops leaves web research to an investigator to protect the context, but this role's Agent is the entry for starting per-unit subagents and is not used for research, so limit what you fetch to the pages you need). Write the source of what you fetched (a URL, or a document and section) in source; if you fetched but nothing applies, make it not_found and write in searched what you searched and how. If you took the judgment's `precedents` row for the same unit as is, write from_judge_row: true, verdict is that row's value, and reason says which row (the unit key). If you build your own mechanism, write in reason, with sources, why the world's solution does not exist or cannot be used

## What to write for the whole round

- `not_done`: the units you did not fix and why (`unit_key`, `why`). A unit you owe a fix ([block] and do-now) must be fixed unless it is the origin of a fork (the origin of a question answered before the fix (a person's answer, or the recommendation an unattended run took) is back in the units you owe a fix, and the acceptance rejects it if you write it in `not_done`. The "origin of a fork" in the rejection message "if it is not the origin of a fork, you owe a fix" means the origin of a question that has no answer yet (a fork, and a question whose status is escalate)). If you leave one out, the acceptance rejects it
- `interactions`: **when two or more fixes touched the same file, one entry per surface (`surface`)**. The machine derives the list of surfaces from `changes`' `files`, so leaving one out is rejected (do not write the list of fixes that touched it). For each surface, compare: ① does one make the other unneeded (if so, apply only the smaller one) ② does the order of application change the result ③ is there a state that arises only when they are combined. Write the result in `checked`, and if a state arises, what arises in `combined_effect`
- `fix_closure`: the result of the round's proof of closure. In a round with fixes, `clean` (in `checked`, what you confirmed; clean without ever having seen red is rejected) or `found`. Only a round with 0 fixes may be `not_applicable` (silent values such as not_applicable when there are fixes are rejected)
- `plan_faces`: one row per `key` of the pre-review's holes (`faces`) and alternatives (`shrink`): if you took it in, `absorbed` and how you took it in, in how. If you do not take it in, `declared` and the reason you leave it, in how (if it is a false positive, where in the real code you can say it is wrong). If there is a key you do not answer, the machine rejects it. If you leave a block hole as declared, write it on the premise that the next whole review will raise the same hole as [block]. Writing "hand to a person" in how does not reach the person: write what goes to a person in that unit's `breaks.accepted` (the machine puts it in the list shown to the person). A run without a fix plan, or a run where neither holes nor alternatives were raised, is an empty array
- `wrote_refs`: **references that cannot be links that you newly wrote this round** (section names, headings, file names, quotes of other documents), one by one: `kind` (file if you pointed at the file itself, text if you pointed at a string inside the file), `target` (the file you point at), `where` (the file you wrote it into), and for text, `cite` (the spelling exactly as it is at the target; one per line). The machine looks them up again in the current working tree and rejects what it cannot find; what you fix is the reference you wrote into the document, not the declaration. You may point at files created and headings added this round. A round that wrote no new references is an empty array. Write new references, where you can, as Markdown links (`[name](relative path#heading)`): the machine picks up links in the .md lines the diff added regardless of the declaration, looks them up to the target file and heading, and rejects them if they do not reach
- `rejudge_requested` (optional): an objection to the judgment's framing or disposition. This round fixes as the judgment says
- `conflicts` (optional): conflict declarations (the fields `unit_key`, `between`, `why_both_cannot_hold`, `which_is_right`, `kind` of the section above with the heading "## Conflict declarations (do not bend to get green)" among the common rules the machine always puts in these instructions, and `correct_lines` too for query; the meanings of the values are in that section too; one per unit). A declared unit is written neither in `changes` nor in `not_done`
- `consult` (optional): requests for scope consultation (only when the section "Scope consultation and the pre-check" above is present; if present, the acceptance does not run that round). Do not write it in an answer that needs nothing outside the scope
- Declarations of changes in the diff's shape (used to apply later viewpoints; not scoring): `mechanism_changed` (added or replaced a mechanism), `premise_drift` (removed or replaced the target on which a premise's constraint was measured; if true, in premise_drift_note the constraint measured again and why the previous constraint became false), `gates_changed` (verification gates), `seams_changed` (test doubles and seams with the outside), `security_surface_changed` (touched authentication, authorization, the handling of secrets or personal data, or input and output with the outside; **if in doubt, true**), `path_changed` (paths the user can see). Optionally decision_records_changed (true only in a round that added decision records outside the repository, such as issues)
- The 4 fixed size numbers (added_lines, comment_lines, comment_ratio_pct, doc_lines) are counted by the machine; write only the numbers you want to add on the spot in x_scalars, with names starting with `x_`

The acceptance checks whether every unit you owe a fix appears in `changes` (or in `not_done` as the origin of a fork or escalate question that has not been answered before the fix: no answer from a person and no recommendation an unattended run took), whether the recounted numbers match the proof of closure, whether the references you wrote can be looked up in reality, and whether you answered the pre-review. If even one is off, it rejects, and the reasons are given at the top of the next round.
<!-- end rules -->

<!-- if resume -->
# The answer to your scope consultation (continued)

An answer came to the `consult` of your previous answer (or to the consultation the machine asked about conditions a person answered beforehand). Read the answer file {answer_file} with Read, all of it (an answer the machine checked; only what was allowed entered the scope).
Go on fixing as the answer says, and return the whole JSON of the answer fields of the instructions given earlier in this conversation (the rules are as given earlier in this conversation; if you did not read them in full, Read {first_prompt} again).
If you still need something outside the scope, you may return `consult` again (consultation rounds left in this stage: {left}).
<!-- end resume -->

<!-- if queued -->
# Overflow the acceptance found (sent to consultation)

In your previous answer, the acceptance found overflow outside the scope (files outside the scope, new tests not in the fix plan's `tests`, rewrites of frozen tests or of existing test functions outside the named ones) and sent it to a consultation with the fix plan's side. The answer comes in the next round.
Without changing the working tree, return the whole JSON of the answer fields of the instructions given earlier in this conversation, with the same content as your previous answer (the rules are as given earlier in this conversation; if you did not read them in full, Read {first_prompt} again).
<!-- end queued -->

<!-- if overflow_answer -->
# The answer about the overflow (continued)

An answer came about the overflow the acceptance found. Read the answer file {answer_file} with Read, all of it (an answer the machine checked; only what was allowed entered the scope).
What was allowed may stay. What was denied, deferred, or got no answer is returned to its original state by the machine at the next acceptance (do not revert it yourself; the machine also removes it from the files of changes).
Return the whole JSON of the answer fields of the instructions given earlier in this conversation, in the same form as your previous answer (the rules are as given earlier in this conversation; if you did not read them in full, Read {first_prompt} again).
If you need something else outside the scope, you may return `consult` again (consultation rounds left in this stage: {left}).
<!-- end overflow_answer -->

Write the human-facing fields (`changes[].what`, the text fields of `closure`, `coverage.remaining`, `root_or_symptom.why`, `bypass_tried`, the text fields of `breaks`, `precedent.problem`, `precedent.reason`, `precedent.searched`, `not_done[].why`, `interactions[].checked`, `combined_effect`, `plan_faces[].how`, `rejudge_requested`, `premise_drift_note`, `conflicts[].why_both_cannot_hold`, `consult[].why`, `bash_writes[].why`) in {lang}. Keep keys, enum values, code identifiers, paths, commands, and error messages as they are.
