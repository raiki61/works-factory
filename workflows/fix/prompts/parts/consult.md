Answer as the author of the fix plan. Read the fix plan {plan_file} first, all of it, and treat it as the plan you wrote.
<!-- if ripple -->
Read the ripple list {ripple_file} too (it names hits that are not in the scope).
<!-- end ripple -->

# Scope consultation (from the fixing stage)

Another role is fixing the fix plan you wrote. From the fixing side, {count} scope consultation(s) came. Whether to widen the scope is a specification decision, and you decide it. Decide from your thinking when you wrote the plan and from the current repository (you can read it with Read, Grep, and Glob; you have no tools that write).
Each consultation from the fixing side also carries what it tried, why it cannot fix the unit within the scope (how far it got and what it hit), and the files and lines that ground it. You start in a new conversation and do not see the fixing side's work otherwise, so open those lines yourself before you decide.
For a consultation whose requested paths hit out_of_scope (things not to touch), the hit globs and the reasons for excluding them are listed. If you wrote it in this item's out_of_scope, reconsider whether the reason for the exclusion still holds, compared with the fixing side's reason: if allow, only that path leaves out_of_scope for this item and enters the scope. If the reason still holds, deny. If you allow something that hits another item's out_of_scope, it passes only as a change of this item's units (that item's out_of_scope does not change).
<!-- if plain -->

How to answer a request for paths and tests: allow only from what was requested (things not requested are dropped by the machine).
<!-- end plain -->
<!-- if gate -->

How to answer a consultation about a condition given at the approval node (the condition is quoted as is; it is what a person answered before the fix, or the recommendation an unattended run took (marked "無人の run が採った推し" on the line just before it), and it cannot be cut beyond the scope and conditions it lets through): decide the paths to add, the ranges of existing tests to rewrite, and the new tests to add (id and red kind) that this item needs to meet the condition. If the condition does not concern this item, deny.
<!-- end gate -->

<!-- if history -->

Earlier consultations in this run and their answers (oldest first; the machine wrote them from the record, and the text after each arrow is the answer or why it was not asked). Keep your answers consistent with them; if the repository now shows a reason to answer differently, say so in `reason`:
{history}
<!-- end history -->

{asks}

{shared:query-rule}

Return only this JSON (`answers`, one row per consultation number; the number is "相談 <number>" above):
- ask: the consultation number
- decision: allow (may be added to the scope), deny (not added; fix within the scope), or defer (not fixed in this run; work for the next run)
- paths: the paths that may be added (from what was requested; only for allow. The machine drops what was not requested. A consultation about "a condition given at the approval node" has no list of requested things; you may list yourself what the condition needs. The machine drops only paths outside the repository root)
- tests: the ranges of tests that may be rewritten (from what was requested; only for allow. Do not allow rewrites that fit expectations to the implementation)
- new_tests: the new tests that may be added (from what was requested; only for allow; omit if none). A list of {{id, red_kind}}. red_kind is {red} for a test that goes red (failure) on the check inside the test in the tree before adding, and {guard} for a guard test that is green even in the tree before adding (the type "check that X does not break" of a person's condition). If you allow the same id again, the later answer wins (a correction of the kind). Do not grant permission to fit expectations to the implementation
- spec: a supplement to the specification the fixing side follows (empty if none)
- reason: the reason for the decision ({min_why} characters or more)

Write `reason` and `spec` in {lang}.
