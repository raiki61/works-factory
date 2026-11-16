---
name: open-pr-collision
description: Checks, read-only, whether open pull requests touch the same files as this change, names the colliding hunks, and drafts an unposted note asking which should go first. Use when others have open pull requests in the same repository, or when asked "does anyone else's PR touch this". Not for repairing a merge that already broke.
---

# Check whether open pull requests collide with this change

**Core rule: never write "no collision" from a list or a set you cannot trust — say that it could not be checked instead.**

## Pitfalls (read first)

- **Read only.** Do not write or delete files, and do not move the version-control state (no checkout, switch, stash, or reset). Do not post to pull requests; a person reads the drafts and passes them on.
- **Resolve the repository from the upstream remote, not from the current directory's default.** Take owner/repo from the remote the branch tracks (or the main remote if there is none), and pass it explicitly to every later query. A tool's own "current repository" resolves from the directory and makes the check always pass. If you cannot derive it, the rest could not be checked.
- **Leave out your own pull request by its head commit, not by branch name.** Otherwise the change under review goes out of its own scope, a self-referential misjudgment. On a detached head the branch name is empty.
- **A cut list is not a clean list.** If the number of pull requests returned equals the maximum count you passed when listing them, the list may have been cut: say so, and do not write "no collision".
- **An empty change set checks nothing.** Do not write "no collision"; say what was empty.
- **A stand-in set is not the change.** When the set of changed files stands in for a diff that could not be measured (for example it was taken from the places a request names), an empty intersection says nothing about the real change: hand it to a person with the reasons.
- **An unchecked result is never clean.** If the network or the tool refused and you could not check, say so with the refused command and its output.
- **Check whether the host holds pull requests before anything else, from the remote alone.** When there is no remote, the remote is a local path, or the host has no pull requests, the check does not apply: say that it does not apply and why (what the remote was). Do not guess it from a failed query; a query refused by the network is unchecked, not "does not apply".

## Steps

The steps are the same before and after this change is fixed and verified (the one who asks for the check says which case it is); under "Handing over a collision", read the item for the case you are in. A hunk is one block of consecutive changed lines in a diff.

### Finding the collisions

1. Resolve owner/repo from the upstream remote.
2. List the open pull requests and remove your own by head commit.
3. Check whether the list was cut.
4. Take the set of changed files; check that it is not empty and not a stand-in (a set taken from somewhere other than a measured diff, such as the places a request names).
5. For each remaining pull request, read its changed files. One whose files intersect the set touches the same file.
6. Read the hunks of each intersecting pull request. If a pull request touches the same file but none of its hunks collide, nothing is taken out for it.

### Handing over a collision

For each place where a collision or overlap is found, treat that change as belonging to the other pull request, which already holds it ahead of this change.

- **Before this change is fixed and verified**: report the colliding hunk as taken out of this change's scope (you list it; you do not edit files — whoever makes the change leaves it alone), one hunk at a time, with its line range in the current working tree and what it collides with.
- **After this change is fixed and verified**: do not take it out — removing a hunk now would void the verification. Keep it in, and say in the note that it is still in this change.
- **The note to the other pull request's owner** (a draft, not posted): which pull request, which file, which hunk, which change of this one it collides with, and a question asking which should go in first. A pull request that has a hunk taken out needs a note.

## Done when

- The repository came from the upstream remote, and every query named it explicitly.
- Your own pull request was left out by its head commit.
- You know whether the list was cut, and whether the change set was empty or a stand-in.
- Every intersecting pull request has its hunks read, and every colliding hunk has a note drafted (and, before the change is fixed and verified, is listed as taken out).
- Nothing was written, posted, or moved in version control.

## How to report

- **The repository** you resolved, **how many pull requests were listed** (before removing your own), and **whether the list may have been cut**.
- **Each intersecting pull request**: its number, the intersecting files, and the drafted note.
- **Each hunk taken out** (only before the change is fixed and verified): the pull request, the file, the line range in the current working tree, and what it collides with.
- **The outcome**, one of:
  - **Collision found**: how many, with the details above.
  - **No collision**: only from a trusted list and a real, non-empty change set; say what you looked at.
  - **Does not apply**: the host holds no pull requests; say what the remote was.
  - **Waits for a person**: the repository could not be derived, the list may have been cut, or the change set is a stand-in; say why.
  - **Not run**: the change set was empty, or the network or the tool refused; say what was empty, or the refused command and its output.

## Example

Input: before this change is fixed and verified. The branch tracks a remote on a host with pull requests. Listing with a maximum of 50 returns 12 open pull requests. One of them, #41, also changes the configuration loader, and one of its hunks overlaps this change's edit of the same function.

Reply:
- Repository: the owner/repo of the tracked remote. Listed: 12, not cut.
- #41 — intersecting file: the configuration loader. Hunk taken out: lines 40–52 of that file in the current working tree; it collides with this change's edit of the loading function.
- Note to the owner of #41 (draft, not posted): both pull requests change the loading function in that file at lines 40–52; which should go in first?
- Outcome: collision found, 1.

## Works well with

- Rules that keep the target's names out of queries sent to outside services (web searches, fetched URLs).
- Rules for when a check may honestly be reported as "not run", "needs a person", or "not applicable".
