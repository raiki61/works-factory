---
name: prior-decisions-check
description: Searches the decision records of the area a change or a request touches (ADRs, the ledger of deliberate deferrals, rejected issues and pull requests, closed issues) and lists the settled points — topic, decision, reason, condition for revisiting, and where it is written — then names every request line that would overturn one of them. Use before changing an area that has history, before accepting a request, or when asked "was this already decided", "did we reject this before", "check this against earlier decisions".
---

# Check a change or a request against earlier decisions

**Core rule: list what was already settled in the area, each with where it is written, and name every request line that would overturn a settled point.**

## Pitfalls (read first)

- **Comments, docstrings, and test descriptions are not decision records.** If one of them names an issue or a decision record, read what it names and list that, pointing to where it is written.
- **A settled point without a place cannot be named.** Every settled point carries where it is written, so that later readers can cite it.
- **When there is no diff yet, search where the request points.** When the request aims at existing code, an empty diff is normal, and what is about to change is the place the request names.
- **Read the area the change touches first.** This is advice on order, not a boundary.
- **Judge a conflict by what a line asks, not by where it points.** Two lines that point to the same place may ask for opposite things.
- **If you could not search the records, do not write "no settled points".** Say that the search could not be done, why, and what you did read. An unchecked area is not a clean one.
- **Say what you searched and what you did not.**
- **Read only.**

## How to report

- **Settled points**: one per point — topic, decision, reason, condition for revisiting, and where it is written.
- **Conflicts**: one per pair — the settled decision, the place the request line points to (copied exactly), and how the line goes against the decision. Empty if none.
- **Searched**: the range you looked at and the range you did not.

Works well with (optional; this file does not need it): a perspective that sets the stance of a read-only investigator who goes to primary sources.
