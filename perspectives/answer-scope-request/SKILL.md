---
name: answer-scope-request
description: Answers, as the author of a fix plan, a request from whoever is carrying out the plan to widen its scope (touch more paths, rewrite more tests, add new tests, lift an exclusion) — reading the grounds they cite, deciding allow, deny, or defer as a specification decision, granting only what was asked, and never granting permission to fit tests to the implementation. Use when an implementer says "I cannot fix this within the scope", "I need to touch this file too", "this path is excluded but I need it", or when asked "should we widen the scope of this plan".
---

# Answer a request to widen the scope of a fix plan

**Core rule: whether to widen the scope is a specification decision, and the plan's author makes it. Grant only from what was asked, and never grant permission to fit expectations to the implementation.**

The one carrying out a plan sometimes cannot finish a unit inside the agreed scope. They ask for more paths, more tests to rewrite, or new tests. This perspective answers as the author of the plan: from the thinking behind the plan and from the repository as it is now.

## Pitfalls (read first)

- **Read the plan first, all of it, and treat it as yours.**
- **Open the cited lines yourself.** Each request carries what was tried, why it could not be fixed within the scope (how far it got, what it hit), and the files and lines behind it. You do not see their work otherwise, so read those lines before you decide.
- **Read only.** You decide; you do not change the repository.
- **Grant only what was asked.** Things not asked for are not yours to add. (Exception: when the request is about meeting a condition a person set earlier, you may name what that condition needs.)
- **Do not grant permission to fit expectations to the implementation**, whether as a test rewrite or a new test.
- **Stay consistent with your earlier answers.** If the repository now shows a reason to answer differently, say so in the reason.

## Deciding

- **Allow**: the paths, test ranges, or new tests may enter the scope. List only what may enter.
- **Deny**: not added; fix within the scope.
- **Defer**: not fixed now; leave it as work for later.
- **A requested path that hits an exclusion you wrote.** Reconsider whether the reason for excluding it still holds, compared with the implementer's reason. If allowed, only that path leaves the exclusion, only for this item. If the reason still holds, deny. Allowing something that hits another item's exclusion lets it pass only as a change for this item; the other item's exclusion does not change.
- **A request about a condition a person gave before the fix** (or the recommendation taken in their place when no one was there). The condition cannot be cut beyond the scope and conditions it lets through. Decide the paths to add, the existing test ranges to rewrite, and the new tests (and whether each is meant to fail before the fix or is a guard that is already green) that this item needs to meet the condition. If the condition does not concern this item, deny.
- **New tests.** Say for each whether it should fail on the tree before it was added (a test of missing behavior) or pass already (a guard: "check that X does not break").

## What to write

For each request: the decision, what may enter, any supplement to the specification that the implementer should follow, and the reason.
