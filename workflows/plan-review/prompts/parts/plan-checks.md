How the checks above read the plan (for each plan item, and for each row of `files`):

- Copy: a row is a copy when the concept home in `home.concept` is among the places `considered` turned down, yet the row puts the same concept in a new place (also check that the reason it was turned down, `why_not`, holds).
- Scope creep and minimality: for each plan item, open `shrink_first` and check that smaller prescriptions are listed in the order of the canonical rules' "処方の最小性" (minimality of the prescription) and that one sentence holds for why each smaller one falls. Also check that the plan does not widen beyond the way of fixing that the `reason` of the material's units and the `one_shot` of the judge's view name.
- Regression: look for what the plan's `narrows` does not list. Raise anything that disappears or narrows but is not in `narrows` as severity block, and have it written back into `narrows`. The rows of `narrows` are asked of a person before the fix; a row written back is asked as a row of `narrows` too.
- Policy: raise a kind=policy hole the way the example at the end of the section "Recorded policy" shows.
- Precedent source: the precedents to open are the judge's precedents whose `verdict` is adopt or adapt.
- `unit_keys`: on a `faces` row, the units that make the hole; on a `shrink` row, the units the alternative closes.
- From the second pass on, when no open block has a central `reach`, the plan goes on to the fix, and the `peripheral` blocks are handed on to the fixing stage.
