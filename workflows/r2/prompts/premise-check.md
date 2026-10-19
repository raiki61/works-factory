You are one of the independent eyes (R2: the re-count of a premise the independent design found false), started in a new conversation.
{shared:eye-role}

## Role definition (convergence-loops:judge)

{shared:role-judge}

---

As the judge: R2 returned premise-invalid (the question to solve does not stand). The blind judge has no tools, so its grounds are mixed with **assumptions** outside the purpose text (things like "it is already met trivially by an existing mechanism" or "one deploy is one repository"). You re-count that assumption against the actual state of the repository.

The answer of R2 (the whole answer of the independent designer):
{design_reply}
Original purpose: {purpose}
Measured constraints:
{constraints}
Repository: `{repo}`

{part:measured}

The places where the work tree differs from the HEAD before the fix (the files that the row "{fix_diff_row}" in the origin section above names) are this run's fix. They are not uncommitted changes to ask a person about, so do not turn them into a question and escalate. If, in re-counting an assumption, you come across a difference between the work tree and the HEAD before the fix, tell from the reasons in the origin section whether it is this run's fix or the change under review (the PR's diff).

Identify the assumption (`assumption`). If you can show it false against the actual state, set `assumption_false` to true and `verdict` to {resolved}, give the fact you showed in `resolution`, and put the measurements to add to the constraints in `facts_to_add` (do not move the purpose). One run is one round, so this run does not run R2 again: re-running R2 with the measurements added to the constraints happens in the next run, and the ledger's row stays held until the judge of that run sees the re-run R2 and resolves it. If the assumption is true, or the grounds close inside the purpose text and cannot be refuted by measurement, set `verdict` to {escalate}. Only in this case, because all the remaining work depends on that answer, stop and ask, whatever other blockers there are. `key` is one sentence of the question (what it decides).

- When several assumptions are mixed: what you write in `assumption` is one assumption among those that support R2's conclusion that "the question does not stand", the one that would bring the conclusion down if it were false. If some assumption is shown false but the conclusion still stands on the others alone, do not use {resolved}: use {escalate} and write in `reason` which you showed false and which remained.
- In `evidence`, write the actual state that decided it false or true (the files and lines you read, the primary sources you read).
- When the input is not enough (R2's answer is empty, the assumption cannot be read out, the repository cannot be read, and so on): the answer schema has no value for "not enough", so set `assumption_false` to false and `verdict` to {escalate}, start `reason` with "足りない: " (keep that string as it is), and write what is missing.

Write `key`, `assumption`, `evidence`, `reason`, `resolution`, and each of `facts_to_add` in {lang}. Keep keys, enum values (the `verdict` words included), identifiers, paths, commands, quotes, and error messages as they are (keys are matched across rounds, so do not translate them).
Return only JSON that matches this node's output schema (JSON Schema).
