<!-- if first -->
Look only at the three points below and at the quality points in the verdict section further down. Read what the diff of the {change} added, and find these holes:
<!-- end first -->
<!-- if not first -->
Look only at the same three points as the first review. Read what the diff of the {change} added, and find these holes:
<!-- end first -->

1. **Copy** (`{copy}`): what the {change} added copies a rule, type, vocabulary, or procedure that already has an authoritative home to another place.
2. **Entrance** (`{entrance}`): a guard the {change} added does not see another route into the same set, and that route remains open.
3. **Drift between declaration and implementation** (`{contract_drift}`): the readers of what the {change} changed (prompt guidance, rejection messages, documents, tests, docstrings) are left stale.

`{regression}`, `{policy_kind}`, and `{precedent}` are words of the review before the fix only, and this acceptance check does not accept them here (a regression after the fix is raised to a person by a later step).

The diff is a starting point, not a boundary: read the readers and callers as well.

Files in the list of changed files that are protected files (tests, fences, acceptance entrances; the `protected_files` field of the material has them, with `path`, `id`, and `why`): if there are any, read whether the change loosens a check (deleting or weakening a test, rewriting an expectation, removing a fence or an acceptance check). If it does, make it a hole (`kind` is one of the five words `{copy}`, `{entrance}`, `{contract_drift}`, `{dead_path}`, `{scope_creep}`). A protected file also always appears at the last approval node.

One hole is one row of `faces`, written like this:

- `key`: a name that calls the hole uniquely, at least {min_key} characters.
- `kind`: one of the three words above, or one of these two: `{dead_path}` (a path the {change} added that nothing reaches) or `{scope_creep}` (a change widened beyond what was asked).
- `where`: **only the path of a changed file**, exactly as in the list of changed files. Put line numbers, function names, and "several places" in `why`: the acceptance check compares the path for an exact match. Do not raise a hole in a file that did not change.
- `cite`: a string **that exists, as it is, in the current state of that file**, at least {min_cite} characters. Do not paraphrase, summarize, or abbreviate.
- `why`: at least {min_why} characters.
<!-- if first -->
- `lens`: add it only to a hole you took from a lens finding, and write the name of the lens it came from. Omit it for a hole that did not come from a lens.
<!-- end first -->

If there is no hole, leave `faces` empty and write in `faces_none` what you read to be able to say there is none (at least {min_none} characters; name the files you read, the readers, and the callers).
