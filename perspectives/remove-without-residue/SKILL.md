---
name: remove-without-residue
description: Removes what a plan names to remove (names and files) together with the tests that bind it, fixes the remaining code that used it without turning it into a different behavior, and confirms the removal by searching that the name is gone from every caller, test, and document — instead of writing a test that only checks the name is gone. Use when a plan or review says "remove this", "delete this feature/option/module", or when asked to "remove it cleanly", "make sure nothing still refers to it".
---

# Remove without leaving residue

**Core rule: remove the thing and everything that binds it, fix what used it, and prove the removal by its absence from the tree — not by a test about the absence.**

## Pitfalls (read first)

- **Remove; do not rewrite into a different behavior.** The remaining code that used the removed thing is fixed so it no longer needs it, not given a new behavior in its place.
- **Do not write a test that only checks a removed name is gone.** The search of the tree is the check.
- **A name still mentioned has not gone.** If any caller, test, or document still mentions it, the removal is not finished: remove the rest of the mentions, or, if a behavior really changed, name a test that shows that change.
- **Stay inside what is named.** Remove what the plan names; a removal that widens beyond it is a new decision.

## How to remove

1. Remove the named names and files.
2. Remove the tests that bind only what was removed. Do not loosen or delete tests that bind anything else.
3. Fix the remaining code that used it.
4. Scan your own diff for what lost its last caller or reference because of the removal (parameters, variables, functions, exports, imports, types) and remove it too. This does not reach the public API: no caller left in the repository does not show no caller left outside it.
5. **Confirm the absence.** Search for each removed name in the version before the change and in the tree after it. Every mention — code, tests, notes, documents, settings — is gone, or is shown to be a different thing with the same spelling.
6. Rewrite every sentence that still describes the removed behavior.
