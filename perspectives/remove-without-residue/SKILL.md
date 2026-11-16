---
name: remove-without-residue
description: Removes what a plan names to remove (names and files) together with the tests that bind it, fixes remaining users without changing behaviour, and confirms by searching that the name is gone everywhere. Use when asked to "delete this feature cleanly". Not for general tidying where nothing is named for removal.
---

# Remove without leaving residue

**Core rule: remove the thing and everything that binds it, fix what used it, and prove the removal by its absence from the tree — not by a test about the absence.**

## Pitfalls (read first)

- **Remove; do not rewrite into a different behavior.** The remaining code that used the removed thing is fixed so it no longer needs it, not given a new behavior in its place.
- **Do not write a test that only checks a removed name is gone.** The search of the tree is the check.
- **A name still mentioned has not gone.** If any caller, test, or document still mentions it, the removal is not finished: remove the rest of the mentions, or, if a behavior really changed, name a test that shows that change.

## Steps

### How to remove

1. Remove the named names and files.
2. Remove the tests that bind what is removed, together with it.
3. Fix the remaining code that used it.
4. Scan your own diff for what lost its last caller or reference because of the removal (parameters, variables, functions, exports, imports, types) and remove it too. This does not reach the public API: no caller left in the repository does not show no caller left outside it.
5. **Confirm the absence.** Search for each removed name in the version before the change and in the tree after it. No caller, test, or document mentions it any more.
6. Rewrite every sentence that still describes the removed behavior.

## Done when

- Every named name and file is removed, with the tests that bind it.
- The code that used it is fixed without being given a new behavior.
- A search for each removed name finds no caller, test, or document that still mentions it — or, where a behavior really changed, a test that shows the change is named.
- What lost its last caller because of the removal is removed too, short of the public API.

## How to report

For each removed name: the searches you ran before and after the change and what they found, the tests you removed with it, and the remaining code you fixed. If a behavior really changed, name the test that shows it.

## Example

Input: a plan says to remove an old export-to-spreadsheet option.

Reply:

- Removed the option, its handler, and the two tests that bind the handler.
- The menu that listed the option now lists the rest without it.
- Searched for the option's name before (7 hits) and after (0 hits): no caller, test, or document mentions it.
- The handler's helper lost its last caller and was removed. Rewrote the user guide's paragraph that described the option.

## Works well with

- A way of tidying what a change leaves unneeded without changing behavior.
