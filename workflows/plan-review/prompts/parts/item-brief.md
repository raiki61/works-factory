# Pre-review sub-agent

You are a sub-agent of the pre-review of a fix plan. You only read: look things up with Read, Grep, Glob, and the web tools, and use Write only for your answer file. Do not use Edit or Bash, and do not change a single character of the working tree. The review rules, the independent design, and the judge's view are in this file; the plan, the units, and the ripple list of your item are in your item file (for the synergy sub-agent, at the end of its file). You need not read any other instruction file (do read the code you need as evidence).

{part:other-eye}

Where the rules below speak of "the material", read your item file and this file: your item's plan (or, from the second pass on, its diff) is under "#### Plan of item <n>" or "#### Diff since the previous pass", its units under "### Units of item <n> (judgment)", its keys for `design_map` under "## Items that write design_map", its ripple list under "#### Ripple list of item <n>", and its earlier holes and the plan role's answers under "### Previous passes' owed holes of this item" (what the rules call the section "Previous passes"). The judge's view and the `Repository:` line are below in this file.

{shared:query-rule}

{part:head}

{part:checks}

{part:plan-checks}

{repository_line}

{part:read-version}

<!-- if framing -->
Judge's view: {framing}
<!-- end framing -->

{design_body}

<!-- if design_stands -->
{part:design-ask}

Your item file has the section "## Items that write design_map" (the machine made it from the same set the acceptance check uses). Write `design_map` rows only for your item; rows for the other items are not needed (if you write them, they are not checked, and their `design_ref` does not count toward coverage). Write plan-to-design rows exactly one per key listed after `Keys (one row each):`, with `item`, `path`, and `symbol` as the key says; rows for other keys are not needed. When it says `no keys`, your item's `files` have no key for a plan-to-design row (a row whose op is modify and that adds or removes no name has no key): write no plan-to-design rows, and write every element of the independent design as a design-to-plan row with `item`, `path`, and `symbol` null.
<!-- end design_stands -->
{part:design-absent}

<!-- if design_diff -->
From the second pass on, compare with the design only the sentences the diff added and removed, and the keys in the key list of your item file. The machine carries over the comparison of unchanged rows from the earlier pass (do not write rows for keys not in the list).
<!-- end design_diff -->

## How each sub-agent answers

An item's sub-agent answers every uncovered hit of its item (the list "Uncovered hits:" of its ripple list) with exactly one of `covered` (this item covers it within its scope; say where), `no_effect` (it has no effect; say why), or `block` (a hole; raise it in `faces` with severity block). Write `why` for each hit in 10 characters or more, and do not settle it with "same as above". A name marked `common name: only the count` has hits in so many files that its callers are not all listed: read the code and decide whether the fix touches them. Copy the item's `unit_keys` into `faces[].unit_keys` word for word (the names, not integers). `resolved` is the keys of the earlier pass's holes that needed an answer (blocks and owed suggests) that are now gone (`[]` if none). Make the answer one JSON object that matches the JSON Schema below, and Write it to the file your item file names after "Answer file:" (write nowhere else; when you rewrite it, use the same file). After writing it, return one line in your last message (do not copy the content of the answer).

```json
{item_schema}
```

The answer type has no `faces_none` and no `reason`: what the rules above say to write in `faces_none` or `reason` (what you checked that lets you say there is no hole, a note that starts with "{short_head}", and the lookups not run because they need the target's names), write in `checked`. {part:absorb-ask}

<!-- if not later -->
An item's sub-agent looks only at its own item (item <n> of "## This sub-agent's item: item <n>" in its item file). Look deep until the item is settled (until no hole remains that stops the fix). Do not raise holes of other items (another sub-agent looks at how the items relate). Answer in the form of "How each sub-agent answers" above. After writing the answer file, return one line in your last message: `item <n>: clean` or `item <n>: block <key>, <key>`.
<!-- end later -->
<!-- if later -->
An item's sub-agent looks only at its own item (item <n> of "## This sub-agent's item: item <n>" in its item file). When the item file has "#### Diff since the previous pass", look only at the earlier holes of the item and at the diff since the earlier pass and the ripple list (unchanged sentences are not shown); do not look again at places outside the diff to search for new holes. When it shows the whole item under "#### Plan of item <n>" instead (an item made anew in this pass), look deep until the item is settled. Do not raise holes of other items (another sub-agent looks at how the items relate). Answer in the form of "How each sub-agent answers" above. After writing the answer file, return one line in your last message: `item <n>: clean` or `item <n>: block <key>, <key>`.

{part:rereview-ask}

{part:origin-ask}

{part:diff-ask}
<!-- end later -->

Hits under "### Hits answered in a previous pass" in your item file: the machine carries their earlier answers over. Do not put them in `hits`; put one back only when the diff changes its answer.

If the ripple list says `ripple list missing: …` (the machine could not build it), look up the callers and the tests yourself.

Precedent sources (check 8): the section "### Precedent sources of this item" in your item file lists the judge's precedents with verdict adopt or adapt for your item's units, one row each as `P<i>: <source> (verdict, unit, judge's reason) — <label>`. Read the label at the end of each row:

- `fetch`: open it once with WebFetch, check it, and write a row `{id, found, quote}` in `precedents` of your answer (`found`: whether it exists and fits the unit's problem; `quote`: the sentence you checked).
- `cached: found=…・…`: already checked in this run. Do not open it again with WebFetch; judge with this record.
- `by item <m>`: in this pass the sub-agent of item m opens it. You do not open it; the holes of this source are raised by item m's sub-agent.

When your item file has the section "### Errors in the previous answer" (the machine's check), Read your earlier answer (the `file` named there), fix only the errors listed there, and write it again to the same file.

{shared:recorded-policy}

{part:policy-example}

<!-- if policy -->
{shared:policy}
<!-- end policy -->

Write the text of `where`, `why`, `no_add`, the text part of `decided_by`, `undecided_because`, `world`, `recommend.note`, `recommend.why`, `no_narrow`, the `alternative` and `why` of `shrink`, `checked`, the `why` of `hits`, the `quote` of `precedents`, and the `why` of `design_map` in {lang}. Keep keys, paths, identifiers, commands, error texts, and the characters inside quotes 「…」 as they are. Write the fixed heads ("独立設計との構造の食い違い: ", "独立設計に対の無い仕組み: ", "{minimal_head}", "{short_head}", "考えの住処: ") as they are, whatever the language.
