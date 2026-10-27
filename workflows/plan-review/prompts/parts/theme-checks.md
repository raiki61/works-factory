## What to look at in a design draft

What you review is a design draft: not code and not a fix plan. Besides the eight checks of "What to look at" above, look at these eight points of the draft. Each one names the kind you usually raise it under; if another of the eight kind words of those checks names its harm better, use that kind.

1. **Asking and deciding** (usually kind=scope_creep): a question the draft asks the person (`asks`) that the target's rules already decide (it belongs in `decided`, with the line of the rule that decides it), and a decision the draft makes by itself (`decided`) that needs the person's answer. When a row of the section "Recorded policy" decides it, raise it as kind=policy and name that row in `decided_by`.
2. **Missing options and costs** (usually kind=scope_creep): a question with no option that adds to what already exists, or no option that does nothing, and an option whose cost or gain is left out or empty in substance.
3. **New parts where existing ones are enough** (usually kind=copy): a part the draft adds whose reason why the existing parts are not enough (`reuse`) is weak. Read the existing parts it names, and the ones it should have named.
4. **Content the rework drops** (usually kind=regression): in the rework inventory (`inventory`), a row whose destination is `drop` but that has no row in `narrows` (the draft's rows of what the design narrows in what exists now), and a row whose destination has nothing that receives it. These are contents the rework loses.
5. **Changes that cannot go down to the fix** (usually kind=dead_path): a row of `changes` that is not concrete enough to be handed on as a request row (a place and what changes there).
6. **Difference from the independent design** (the kind that names its harm): where the draft and the independent design (if one is given) differ in structure, a mechanism one has and the other does not, and which of the two the difference favours.
7. **The person's answers left out** (usually kind=contract_drift): a row of `answers_used` that says the answer was applied, but whose content is not in the draft.
8. **Unasked premises** (usually kind=contract_drift): a premise the writer assumed (`premises` with `by: assumed`) that would change the design if it fell, but that the draft does not ask the person about in `asks`.

In a design draft, "the fix" in the definitions of `reach` above means building the design: a hole that forces the design to be redone is `forces_redesign`, and a fine adjustment that can be handed on to the planning stage is `peripheral`.
