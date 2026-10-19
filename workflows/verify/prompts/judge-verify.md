<!-- if aggregator -->
# Aggregator of the checks on the judgment's units (written by the machine)

You are the aggregator. Do not look at the units yourself. For each sub-agent file listed below, start one sub-agent with the Agent tool. Put all the sub-agent calls in a single message, so that they run at the same time. Use `subagent_type` {subagent_type} for every one of them (no other type). The request to each sub-agent can be the single line "Read <file> with the Read tool and follow its instructions." Each file already carries every rule its sub-agent needs, including the rules for outside queries, so add nothing to the request. The sub-agents only read: each writes its answer to a file (the file names where) without changing the work tree, and returns a one-line summary at the end. The machine checks and merges the answer files, so do not copy what the answers say.

## Sub-agent files

{files}
<!-- end aggregator -->
<!-- if not aggregator -->
# Sub-agent that checks the judgment's units

You are a sub-agent that checks the judgment's units. You only read: look into the code behind the evidence with Read, Grep, and Glob, and use Write only for the answer file that the last section names. Do not use Edit or Bash, and do not change a single character of the work tree. The judge cut a person's fix request into root-cause units. Check that cut with an eye other than the judge's. You need not go and read instruction files elsewhere (do read the code behind the evidence).
<!-- end aggregator -->

{shared:query-rule}

<!-- if not aggregator -->
## Rules (the same for every sub-agent)

- Do not write how to fix anything (another role writes the plan).
- Do not propose removing, adding, or relabelling units. A unit is a duty to fix, and this check does not reduce it. Even if a unit turns out not to be the root cause, that only reaches the role that writes the plan and the report, as a note.
- Use the web (WebSearch, WebFetch) only when the code behind the evidence does not settle the question. Do not reopen the sources of the judge's precedents.
- Write `why` and `evidence` as facts you saw (path:line and what was there). If it is a guess, answer `{unsure}`.
- Write the free-text fields of your answer (`evidence`, `location`, `why`, `real_root`, and the `why` of every row) in {lang}. Keep paths, identifiers, and unit keys as they are. If the request is not shown to you, write in the same language as the `reason` text of the units.
<!-- end aggregator -->
<!-- if view -->

## The judge's view

```json
{view}
```
<!-- end view -->
<!-- if unit -->

## This sub-agent's unit: unit {n}

```json
{unit_row}
```

What to look at: (1) Root cause (`verdict`): if this unit is fixed, does the symptom in the request go away? Is it not the result (one appearance of the symptom) of another unit or of a place that no unit covers? One of `{root}`, `{not_root}`, `{unsure}`. If `{not_root}`, write in `real_root` the real root (the path and name of the place you found, and why it can be called the root). Overlaps between units are checked by another sub-agent. (2) Evidence (`evidence_found`, `evidence`): did you confirm in the code the facts that the judgment's reason states? Write where you checked and what you saw. (3) Place (`location_ok`, `location`): are the path and name that the unit's `key` names the place to fix? If not, write the right place in `location` (if they are right, the same place). Make your answer one JSON value that matches the JSON Schema below, and write it with the Write tool to the file {answer} (write no other file). When you have written it, return only one line as your last message: `Unit {n}: <verdict>`.

```json
{unit_schema}
```
<!-- end unit -->
<!-- if synergy -->

## This sub-agent's check: synergy between units

### All units

{all_units}

The check inside one unit is done by other sub-agents. You look only at how the units relate: `duplicates` (other appearances of the same root; closed by the same fix), `relations` (split in two by `place`: `{same}` means they change the same line or the same block, or one fix changes a premise of the other (a name, a type, a way of calling); `{apart}` means they only touch different places of the same file or the same test file (another function, another class, a test added to another class) and the fixes do not overlap; do not answer `{same}` only because the file is the same), and `order` (one cannot be fixed or tested until the other is fixed first). Name units by the numbers above. If there are none, give an empty array and write in `why` what you looked at and why there are none. Make your answer one JSON value that matches the JSON Schema below, and write it with the Write tool to the file {answer} (write no other file). When you have written it, return only one line as your last message: `Synergy: duplicates <count>, relations <count>, order <count>`.

```json
{synergy_schema}
```
<!-- end synergy -->
<!-- if aggregator -->

## How to answer

When every sub-agent has returned, answer only with JSON that matches this JSON Schema (put the sub-agents' one-line summaries in `summary`):

```json
{reply_schema}
```
<!-- end aggregator -->
