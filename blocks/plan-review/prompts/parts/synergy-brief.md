## This sub-agent's task: the synergy review

You are the synergy sub-agent. Of the instructions above, the parts written for an item's sub-agent (looking only at one item, the answers to hits in "How each sub-agent answers", the answer type and the last line there) do not apply to you; the review rules, the independent design, and the recorded policy above do.

Look only at how the items relate; do not raise holes inside one item. Look for conflicting changes to the same line or the same hunk, order dependencies, duplicated work, and one root split into different items. Items that only touch different places of the same file (a different function, a different class, a test added to a different class) are not a hole (do not make them merge). Raise holes in `faces`, and put in their `unit_keys` the names of the units of every item involved, word for word (only the items you name reopen). Write in `why` what you looked at and, if there is no hole, why there is none. The material for this review (every item's state and row, closed items too, and the overlaps between items) is below, after "## This sub-agent's review: synergy".

<!-- if later -->
From the second pass on, write the origins of your new blocks in `origins`, as the rule "Origins of new blocks" above says.
<!-- end later -->

Make the answer one JSON object that matches the JSON Schema below, and Write it to {answer_file} (write nowhere else). After writing it, return one line in your last message: `synergy: clean` or `synergy: block <key>, <key>`.

```json
{synergy_schema}
```
