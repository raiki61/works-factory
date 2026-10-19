<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{part:role}

Your tools are Read, Grep, Glob, WebSearch, and WebFetch, plus Agent to start sub-agents and Write for the answer files a sub-agent writes (outside the working tree). Do not change a single character of the working tree: the acceptance check compares it with a copy taken before you were started and rejects your answer if it changed.

{part:head}

<!-- if excluded -->
Ranges of parallel PRs: the section "Excluded ranges" of the material names a file that lists ranges other PRs handle. Read that file first. Do not touch those ranges, and do not put them in units.
<!-- end excluded -->

## Material

Read the whole material file {material_file} with Read. It holds everything the machine pasted for this review, under these sections when they apply: "Inputs read with defaults", "Excluded ranges", "Library documents", "Independent design", "Deviations recorded in the plan", "Works fields of the plan items", "Items that write design_map", "Previous passes", "Replan items", and "Machine-pasted material". The last one holds the plan items (from the second pass on, the diffs and ripple lists of the open items, and "Overlaps and other items' scope"), `Units:`, `Judge's view:`, `Judge's precedents (world):`, and the `Repository:` line: the repository, the read version, BASE, and the canonical rules `REVIEW.md` (BASE is the version before this run started fixing, and the baseline of check 6). You need not read any other instruction file (do read the code you need as evidence).

<!-- if defaults -->
Some inputs were read with defaults: the section "Inputs read with defaults" of the material names them and why. Read each of those inputs as absent.
<!-- end defaults -->

<!-- if purpose -->
## Purpose

{purpose}
<!-- end purpose -->

## Independent design

<!-- if design_stands -->
{part:design-ask}
<!-- end design_stands -->
{part:design-absent}

<!-- if design_diff -->
From the second pass on, compare with the design only the sentences the diffs added and removed, and the keys in the key list of the section "Items that write design_map". The machine carries over the comparison of unchanged rows from the earlier pass (do not write rows for keys not in the list).
<!-- end design_diff -->

<!-- if map_items -->
How to read the section "Items that write design_map": write `design_map` rows only for the items it lists after `Items:`. Rows for other items are not needed (if you write them, they are not checked, and their `design_ref` does not count toward coverage). The elements it lists as received by the other items in earlier passes are already counted toward coverage; you need not write design-to-plan rows for them. Write plan-to-design rows exactly one per key listed after `Keys`, with `item`, `path`, and `symbol` as the key says; rows for other keys are not needed (if you write them, they are not checked, and their `design_ref` does not count toward coverage). When it says `no keys`, the `files` of this pass's items have no key for a plan-to-design row (a row whose op is modify and that adds or removes no name has no key): write no plan-to-design rows, and write every element of the independent design as a design-to-plan row with `item`, `path`, and `symbol` null.
<!-- end map_items -->

<!-- if fields -->
## How to read the works fields

The works fields are what the plan role wrote for each item: `route`, the acceptance tests `tests`, the existing tests to rewrite `rewrite_tests`, the refactor declaration `refactor`, the paths it may write `allowed_paths`, and what it does not touch `out_of_scope` (in the section "Works fields of the plan items" of the material, or, in a replan, inside the items of the section "Replan items"). Once approved, they become each item's brief, the canonical requirements of the fixing stage. Check that the acceptance tests go through the real route, do not assert the return value of a mock, and do not lean on comparing wording; that the red named by each `tests` row's `red_kind` (the kind of failure the test shows before the fix) really happens with the current code; and that `rewrite_tests` rewrites only behaviour the request changes, not expected values bent to fit the implementation. Also check that `allowed_paths` is enough for the item's fix and not too wide, and that `out_of_scope` covers what the request does not touch.

The rows after the label "{machine_key} (added by the machine)" are permits the machine added: existing tests, before the fix, that use as a code identifier a symbol that the item's `files` remove with change=remove (a removed name). The plan role did not write them and cannot change them; they only permit rewriting or removing those tests, and they are neither an instruction to remove them nor a duty. The acceptance check rejects a block whose `where` names `{machine_key}`. If you think a permit is too wide or too narrow, name the change=remove symbol in that item's `files`. Raise holes in `faces`.

When the material has the section "Deviations recorded in the plan" (the reasons the plan's `structure` field gives for departing from the way to avoid a problem in the input `structure`, from the judgment's prescription, or from the world solution), check that each reason holds.
<!-- end fields -->

<!-- if later -->
## From the second pass on

{part:rereview-ask}

{part:origin-ask}

{part:diff-ask}
<!-- end later -->

<!-- if replan -->
## Review of a replan

The section "Replan items" of the material holds, for each ruled item, the earlier form of the approved plan item, the objections and rulings from the fixing stage, and the form the plan role revised in response. Check whether the revised form fixes what the text of each ruling points out, and whether it creates a new regression or a new conflict with policy. Do not raise again a hole the earlier form already had. Raise holes in `faces`. The `unit_keys` line of each item there is the item's units, word for word.
<!-- end replan -->

{part:checks}

{part:plan-checks}

{shared:recorded-policy}

{part:policy-example}

<!-- if policy -->
{shared:policy}
<!-- end policy -->

{shared:concept-map}

## How to answer

- In `unit_keys`, point at units by the integer `no` that the machine numbered after `Units:` in the material. Do not copy the key: the machine turns the number back into the unit's name and records it.
- `kind` is exactly one of the eight words of "What to look at".
- {part:absorb-ask}
- Write the text of `where`, `why`, `no_add`, the text part of `decided_by`, `undecided_because`, `world`, `recommend.note`, `recommend.why`, `no_narrow`, the `alternative` and `why` of `shrink`, `faces_none`, `reason`, `stuck_recommend.note`, `stuck_recommend.why`, and the `why` of `design_map` in {lang}. Keep keys, paths, identifiers, commands, error texts, and the characters inside quotes 「…」 as they are. Write the fixed heads ("{drift_head}", "{unpaired_head}", "{minimal_head}", "{short_head}", "{home_prefix}") as they are, whatever the language.

Return only JSON that matches the output schema.
