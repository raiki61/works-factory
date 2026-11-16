---
name: open-pr-collision
description: Checks, read-only, whether open pull requests in the target repository touch the same files as this change, names the colliding hunks, hands each to the pull request that leads it, and drafts (without posting) a note to that pull request's owner asking which should go in first — refusing to say "no collision" from a wrong repository, a cut list, an empty or unmeasured change set, or an unchecked result. Use before or after making a change in a repository where others have open pull requests, or when asked to "check for parallel PRs", "does any open PR touch the same files", "draft a note to the PR that collides".
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
- **Do not decide yourself whether the host holds pull requests.** That is decided before you start.

## Steps

1. Resolve owner/repo from the upstream remote.
2. List the open pull requests and remove your own by head commit.
3. Check whether the list was cut.
4. Take the set of changed files; check that it is not empty and not a stand-in.
5. For each remaining pull request, read its changed files. One whose files intersect the set touches the same file.
6. Read the hunks of each intersecting pull request. If a pull request touches the same file but none of its hunks collide, nothing is taken out for it.

## Handing over a collision

For each place where a collision or overlap is found, treat that change as belonging to the other pull request, which already holds it ahead of this change.

- **Before this change is fixed and verified**: report the colliding hunk as taken out of this change's scope (you list it; you do not edit files — whoever makes the change leaves it alone), one hunk at a time, with its line range in the current working tree and what it collides with.
- **After this change is fixed and verified**: do not take it out — removing a hunk now would void the verification. Keep it in, and say in the note that it is still in this change.
- **The note to the other pull request's owner** (a draft, not posted): which pull request, which file, which hunk, which change of this one it collides with, and a question asking which should go in first. A pull request that has a hunk taken out needs a note.

Works well with (for reference only; nothing here needs them): rules that keep the target's names out of queries sent to outside services (web searches, fetched URLs), and rules for when a check may honestly be reported as "not run", "needs a person", or "not applicable".
