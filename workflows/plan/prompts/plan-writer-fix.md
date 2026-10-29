{shared:resubmit}

{shared:query-rule}

{shared:plain-ask}

<!-- if not replan -->
For `plan`, the rule above that a field you return replaces the previous field as a whole does not apply; `plan` is merged by the rules below.

- Return in `plan` only the items the rejection names, as whole items of the same type as before. A previous item that shares even one of its `unit_keys` with a returned item is replaced by the returned item (a unit counts as the same whether you write it by its no or by the unit's name; when you merge two items or move a unit to a neighboring item, return all the items involved). An item that overlaps no previous item is added at the end. A previous item that holds no unit to fix in this round (an item with unknown keys, or with only units to leave out) disappears when you return `plan`.
- When you fix `block_answers`, return every row (the field is replaced as a whole).
- When you fix `handoff`, return all of it (the field is replaced as a whole).
- Only when you remove an item (including when you take out an item the rejection told you not to write), write true in `{whole_plan}`, and return in `plan` the whole plan except the closed items (`plan` is replaced as a whole, and the machine fills in only the rows of the closed items; later resubmissions are also merged into this whole plan).
<!-- end replan -->
<!-- if replan -->
- When you fix `plan`, return all the pasted items in the pasted order (`plan` is replaced as a whole).
- When you fix `handoff`, return all of it (the field is replaced as a whole).
<!-- end replan -->
