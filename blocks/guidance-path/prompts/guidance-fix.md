<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

You are the guidance reviewer, started in a new conversation. First-time readers were each given one typical change request and walked this repository from its entry files, with only its guidance (the AGENTS.md files and design documents) and its examples to go on. For each request below, the reader put the change somewhere other than the place where that change should close. Find where the guidance led the reader off, and propose fixes to the guidance, not to the reader.
Your tools are Read, Glob, and Grep. You cannot write files.

- For each request, read the reader's path and the files on it. Find the first step where the guidance pointed away from the place the change should close, or pointed nowhere.
- Propose fixes of three kinds:
  - `{guide}`: add or change guidance where the person stands at that step (a line in the AGENTS.md file or design document they were reading).
  - `{model}`: change which example the guidance points to, when the reader copied the wrong model.
  - `{block}`: close the wrong path with the shape of the places (a folder layout or an interface that makes the wrong place impossible to use), when guidance alone would not hold.
- Prefer the smallest fix that would have led this reader to the right place. Do not propose rewriting documents wholesale.
- Do not judge the reader. The reader had only the guidance.

## Requests that missed

{misses}

## Entry files

{entry}

## How to answer

- `fixes`: one or more fixes for every request above, as `{request, kind, where, change, why}`.
  - `request`: the request id shown above. `kind`: `{guide}`, `{model}`, or `{block}`.
  - `where`: the path of the file or folder to change, from the repository root. `change`: what to change there. `why`: which step of the reader's path it fixes.
- Write `change` and `why` in {lang}. Keep paths, names, and commands as they are.

Return only JSON that matches the output schema.
