<!-- if fix_test_scope -->
You ruled that the test describes wrong behavior. You may fix tests only in the places listed under "範囲"; the tests you fix are listed as guarded files at the last approval node. Do not change or loosen tests outside the scope. Also write one row for this unit in `changes`.
<!-- end fix_test_scope -->
<!-- if fix_code_as -->
Fix the code as the text of "裁定" says. Outside the scope of the plan item, you may change only the paths listed under "範囲" (if there are none, change nothing outside the scope). Do not change the tests. Also write one row for this unit in `changes`.
<!-- end fix_code_as -->
<!-- if ask_human -->
Do not fix this unit (the machine took it out of the units you owe a fix; a person decides at the last approval node). Do not write it in `changes`. If a fix for this unit is in the working tree, leave it as it is (do not revert or touch it; when the machine reverted it and named the saved patch, do not apply it again).
<!-- end ask_human -->
<!-- if replace_query -->
The judge's question also applies to the correct form after the fix, so the ruling replaced the question with "置き換えた問い" (the machine tried it with `hits`, `misses` and the correct rows of the claim). The machine recounts the closure with this question (you need not write `coverage.how`). Outside the scope of the plan item, you may change only the paths listed under "範囲" (if there are none, change nothing outside the scope). Do not change the tests. Also write one row for this unit in `changes`.
<!-- end replace_query -->
<!-- if rejudge -->
The ruling says the way the judgment cut the units was wrong. Do not fix this unit (the machine took it out of the units you owe a fix). Do not write it in `changes`. The text of the ruling goes to the judge's redo as an objection raised by the fix stage.
<!-- end rejudge -->
<!-- if fix_plan_item -->
The ruling says the plan item itself is wrong. Do not fix this unit, nor the other units of the same item listed under "項目の単位", for now (the machine took them out of the units you owe a fix). In this run the plan writer fixes only this item; after it passes the pre-review and the rules of the approval node, the second fix stage fixes it. Do not write it in `changes`. Leave the fixes of the item's units made in the first round in the working tree as they are (do not revert or touch them; the machine does not revert them either; the second fix stage, after the plan is fixed, fixes on top of them).
<!-- end fix_plan_item -->
<!-- if amended -->
The ruling said the plan item itself was wrong, but the plan was fixed in this same run and the unit owes a fix again. Fix as the fixed item (the brief at the head) says, and also write one row for this unit in `changes`.
<!-- end amended -->
<!-- if gave_up -->
The ruling said the plan item itself was wrong, but the plan could not be fixed within this same run (given up; the reason is under "案の直しを諦めた理由"). Do not fix this unit, nor the other units of the same item listed under "項目の単位" (the machine took them out of the units you owe a fix; a person decides at the last approval node). Do not write them in `changes`. The fixes made in this run's fix stage were kept in the working tree (do not revert them).
<!-- end gave_up -->
<!-- if late_replan -->
The ruling said the plan item itself was wrong, but this run's plan fix is already done (the plan stage is re-entered only once per run). Do not fix this unit, nor the other units of the same item listed under "項目の単位" (the machine took them out of the units you owe a fix). When the fix stage ends, the machine turns them into given-up rows, and a person decides at the last approval node. Do not write them in `changes`. Leave the fixes of the item's units made up to this stage in the working tree as they are (do not revert or touch them; a person sees them at the last approval node).
<!-- end late_replan -->
<!-- if clash -->
A ruling to fix, on a claim from the join between groups. The fix of this unit's group is not in the working tree but in the saved diff; the joiner re-applies the saved diff and fixes as the text of the ruling says. The fixer after the ruling must not fix this unit and must not write it in `changes`.
<!-- end clash -->
