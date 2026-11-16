---
name: answer-scope-request
description: Decides, as the author of a fix plan, whether to allow, deny, or defer a request from the implementer to widen the plan's scope. Use when an implementer asks for more room, saying "I need to touch this file too" or "this path is excluded but the fix needs it". Not for deciding which side gives way when a test and the request contradict each other.
---

# Answer a request to widen the scope of a fix plan

**Core rule: whether to widen the scope is a specification decision, and the plan's author makes it. Grant only from what was asked, and never grant permission to fit expectations to the implementation.**

The one carrying out a plan sometimes cannot finish a fix inside the agreed scope. They ask for more paths, more tests to rewrite, or new tests. This perspective answers as the author of the plan: from the thinking behind the plan and from the repository as it is now.

## Pitfalls (read first)

- **Read the plan first, all of it, and treat it as yours.**
- **Open the cited lines yourself.** Each request carries what was tried, why it could not be fixed within the scope (how far it got, what it hit), and the files and lines behind it. You do not see their work otherwise, so read those lines before you decide.
- **Read only.** You decide; you do not change the repository.
- **Grant only what was asked.** Things not asked for are not yours to add. (Exception: when the request is about meeting a condition a person set earlier, you may name what that condition needs.)
- **Do not grant permission to fit expectations to the implementation**, whether as a test rewrite or a new test.
- **Stay consistent with the answers you gave to earlier requests on the same plan.** If the repository now shows a reason to answer differently, say so in the reason.

## Steps

"Deciding" covers every request; its last three bullets add rules for a requested path that hits an exclusion, a request about a condition a person set, and new tests.

### Deciding

- **Allow**: the paths, test ranges, or new tests may enter the scope. List only what may enter.
- **Deny**: not added; fix within the scope.
- **Defer**: not fixed now; leave it as work for later.
- **A requested path that hits an exclusion you wrote.** Reconsider whether the reason for excluding it still holds, compared with the implementer's reason. If allowed, only that path leaves the exclusion, only for this item. If the reason still holds, deny. Allowing something that hits another item's exclusion lets it pass only as a change for this item; the other item's exclusion does not change.
- **A request about a condition a person gave before the fix** (or the recommendation taken in their place when no one was there). The condition reaches only as far as the scope and conditions it lets through; do not stretch it further. Decide the paths to add, the existing test ranges to rewrite, and the new tests (and whether each is meant to fail before the fix or is a guard that is already green) that this item needs to meet the condition. If the condition does not concern this item, deny.
- **New tests.** Say for each whether it should fail on the tree before it was added (a test of missing behavior) or pass already (a guard: "check that X does not break").

## Done when

- You read the whole plan and opened the lines each request cites.
- Every request has one decision: allow, deny, or defer.
- What you allow comes only from what was asked (or, for a person's condition, what that condition needs), and nothing you allow fits expectations to the implementation.
- Every new test you allow is marked as one that fails before it is added or as a guard.
- Your answers agree with the ones you gave to earlier requests on the same plan, or the reason says what in the repository now makes them differ.

## How to report

For each request: the decision, what may enter, any supplement to the specification that the implementer should follow, and the reason.

## Example

Input: the implementer asks to touch `src/config` as well, citing `src/config:8`: the fix reads a default that lives there, outside the plan's paths. The plan does not exclude it.

Reply:

- Decision: allow.
- May enter: `src/config`.
- Supplement to the specification: none.
- Reason: the default the fix needs is at `src/config:8`; touching it changes no test's expectation.

## Works well with

- A view for writing a fix plan with its scope and acceptance tests before the code is touched.
- A read-only ruling on a fix that cannot go green without bending the test, the request, or the code.
