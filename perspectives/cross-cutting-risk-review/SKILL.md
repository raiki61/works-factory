---
name: cross-cutting-risk-review
description: "Looks around a finished change, not inside its diff, for cross-cutting risks it left untouched: rate limits, personal data sent out, coupling to outside services, wrong-environment blast radius, and capabilities lost in a migration. Use when asked \"what could go wrong in production\" or about security or data handling of a change. Not for line-level bugs in the diff."
---

# Review the cross-cutting risks around a change

**Core rule: look not only inside the diff but in the area the change touches and is trying to solve, for the cross-cutting risks the change did not touch. Treat a risk by whether this change introduced or exposed it: introduced or exposed is collected in this scope; purely existing and unrelated is surfaced as a suggestion or below.**

## Pitfalls (read first)

- **You did not write the change.** Read only; base the judgment on what you were given and what you read yourself.
- **For a migration, compare with the base, not with an ideal.** "It could be better" is out of scope; pick up only "what existed has disappeared".
- **Experience lost in the replacement shows only when the migration is finished.** When the diff touches procedures, development flow, or user experience, always do the inventory.
- **A silent omission is forbidden.** When the inventory of capabilities is triggered, say explicitly whether a capability is gone — "none" is said, not implied.
- **Do not decide for a person.** Whether to accept a lost capability, and whether to let a conflict with a person's policy through, is a person's decision. List them; do not count them toward your own verdict on whether the change needs a redesign (doing so would decide before the person does).
- **Pre-existing and unrelated risks do not stop the change.** Tell them; do not stop the change on them.
- **Do not reword what a person already passed.** If you see the same lost capability or the same policy conflict that a person already let through, write it in the same words, so it is not asked again. A loss that goes beyond the conditions the person passed, or a different capability, is new: write it in your own words, not in the passed words.

## Steps

### Risks to check

Look through operations and reliability, security, and data governance. The items below are representative, not a closed list: treat a cross-cutting risk specific to the touched area the same way.

- **Rate limits and abuse resistance**: do outside I/O and public endpoints have rate limiting or throttling?
- **Personal data sent outside**: if personal data goes to an outside service, are data classification, the right to deletion, and a retention policy in place?
- **Availability coupled to outside dependencies**: does a failure or delay of an outside dependency drag down the system's own availability?
- **Blast radius of the wrong environment**: when a procedure or script runs in an environment other than the assumed one (the cluster tool's current context, the cloud subscription, production mistaken for local), what is the range of damage, and is there a guard (a confirming command before running, an explicit context)?
- **Inventory of migration regressions**: see below.

If you have them, also read: the list of places the change affects, the findings on how practitioners usually solve the requested kind of work, and the marks showing where fixes were made.

### The inventory of lost capabilities (base capability inventory)

When the change is part of a migration that replaces an existing means, or touches a procedure, a development flow, or a user experience, take the inventory: first list the capabilities the replaced means (the base, the version before the change) provided — not only functions but experience: the speed of the iterative development loop, debugging means, observation, safe defaults — then check one by one whether each survives in the replacement, and ask whether a loss is acceptable. Always return explicitly either "lost capabilities: list" or "no capability lost (base checked: name)". One entry is one capability, written with a short plain title of what the person is asked. For the same capability as before, use the same words.

### Conflicts with a person's policy

A person's policy is the set of rules a person recorded as decided: a policy document of the project, the answers given with the request, and a person's answers during the work. Each rule there is one row. A conflict with the policy is only one with such a recorded row; name the row exactly as it is written there. Comments, docstrings, and test descriptions in the code are statements about the target, not policy: if one disagrees with the change, that is a lack of coherence (the change does not line up with what exists), not a policy conflict, and it is not listed among the conflicts. One entry is one conflict, with a short plain title.

### Split by origin

- **Introduced or exposed by this change**: the change needs a redesign.
- **Purely pre-existing and unrelated**: only tell a person. Of the review labels (heaviest first: [block], [suggest], [nit], [info]), use [suggest] or lighter, never [block]. One entry per risk: where it is and what is risky, and when known, how it happens, a measurement, and the condition under which it would be a false positive.

### Holes left unfixed on purpose

If the fix plan was reviewed before the change was written, and you have the holes that review raised (defects the change would make if built as planned) that whoever wrote the change answered they would leave unfixed, check whether each one still exists after the change. One that still exists and is a harm this change introduced or exposed needs a redesign; one where telling a person is enough is told as a suggestion; one that has disappeared is not raised.

## Done when

- When the inventory is triggered, "lost capabilities: list" or "no capability lost (base checked: name)" is returned explicitly.
- Every policy conflict names a recorded row exactly as written; comments, docstrings, and test descriptions are not among them.
- Lost capabilities and policy conflicts are listed for a person and not counted toward your own verdict.
- Every risk is split by origin, and pre-existing unrelated ones are at [suggest] or lighter.
- Anything a person already passed is written in the same words.

## How to report

Return the verdict on whether the change needs a redesign, then four lists: lost capabilities (or "no capability lost (base checked: name)"), policy conflicts, risks only told to a person, and holes left unfixed that still exist. Write each lost capability and each conflict for a reader who knows neither the work nor its tooling: the title in plain words, and enough facts to decide from the entry alone.

## Example

Input: a change replaces a local start script that reloaded the app on every file save with a container setup that rebuilds the image on each change.

Reply: The inventory is triggered (development flow). Lost capabilities: "reload on save" — title: "Accept losing reload on save during local development?"; the base reloaded within a second, the replacement rebuilds the image. Policy conflicts: none. Risks only told to a person: none. Verdict: no redesign from this alone; a person decides the loss.

## Works well with

- A view on coherence across the files a change touched (naming, conventions, documents kept in step).
- A way of writing a question to a person so that a first-time reader can decide it from the text alone.
