---
name: cross-cutting-risk-review
description: Looks, after a change is written, not inside the diff but in the area the change touches and is trying to solve, for the cross-cutting risks it left untouched — through operations and reliability, security, and data governance: rate limits and abuse resistance, personal data sent outside, availability coupled to outside dependencies, the blast radius of running in the wrong environment, and, for a migration, every capability the replaced means provided (including development-loop speed, debugging, observation, and safe defaults) checked one by one for survival — splitting what this change introduced or exposed from what was already there, and handing lost capabilities and policy conflicts to a person instead of deciding them. Use before accepting a change, when reviewing changes to outside I/O, endpoints, procedures, or migrations, or when asked "what else could this break", "what does this change not see", "is anything lost in this migration", "did we lose any capability", "what are the operational risks".
---

# Review the cross-cutting risks around a change

**Core rule: look not only inside the diff but in the area the change touches and is trying to solve, for the cross-cutting risks the change did not touch. Treat a risk by whether this change introduced or exposed it: introduced or exposed is collected in this scope; purely existing and unrelated is surfaced as a suggestion or below.**

## Pitfalls (read first)

- **You did not write the change.** Read only; base the judgment on what you were given and what you read yourself.
- **For a migration, compare with the base, not with an ideal.** "It could be better" is out of scope; pick up only "what existed has disappeared".
- **Experience lost in the replacement shows only when the migration is finished.** When the diff touches procedures, development flow, or user experience, always do the inventory.
- **A silent omission is forbidden.** When the inventory of capabilities is triggered, say explicitly whether a capability is gone — "none" is said, not implied.
- **Do not decide for a person.** Whether to accept a lost capability, and whether to let a conflict with a person's policy through, is a person's decision. List them; do not count them toward your own verdict on whether the change needs a redesign (doing so would decide before the person does).
- **Pre-existing and unrelated risks do not stop the change.** Tell them; do not block on them.
- **Do not reword what a person already passed.** If you see the same lost capability or the same policy conflict that a person already let through, write it in the same words, so it is not asked again. A loss that goes beyond the conditions the person passed, or a different capability, is new: write it in your own words, not in the passed words.

## Risks to check

Look through operations and reliability, security, and data governance. The items below are representative, not a closed list: treat a cross-cutting risk specific to the touched area the same way.

- **Rate limits and abuse resistance**: do outside I/O and public endpoints have rate limiting or throttling?
- **Personal data sent outside**: if personal data goes to an outside service, are data classification, the right to deletion, and a retention policy in place?
- **Availability coupled to outside dependencies**: does a failure or delay of an outside dependency drag down the system's own availability?
- **Blast radius of the wrong environment**: when a procedure or script runs in an environment other than the assumed one (the cluster tool's current context, the cloud subscription, production mistaken for local), what is the range of damage, and is there a guard (a confirming command before running, an explicit context)?
- **Inventory of migration regressions**: see below.

If you have them, also read: the list of places the change affects, the findings on how practitioners usually solve the requested kind of work, and the marks showing where fixes were made.

## The inventory of lost capabilities (base capability inventory)

When the change is part of a migration that replaces an existing means, or touches a procedure, a development flow, or a user experience, take the inventory: first list the capabilities the replaced means (the base, the version before the change) provided — not only functions but experience: the speed of the iterative development loop, debugging means, observation, safe defaults — then check one by one whether each survives in the replacement, and ask whether a loss is acceptable. Always return explicitly either "lost capabilities: list" or "no capability lost (base checked: name)". One entry is one capability, written with a short plain title of what the person is asked. For the same capability as before, use the same words.

## Conflicts with a person's policy

A person's policy is the set of rules a person recorded as decided: a policy document of the project, the answers given with the request, and a person's answers during the work. Each rule there is one row. A conflict with the policy is only one with such a recorded row; name the row exactly as it is written there. Comments, docstrings, and test descriptions in the code are statements about the target, not policy: if one disagrees with the change, that is a lack of coherence (the change does not line up with what exists), not a policy conflict, and it is not listed among the conflicts. If you are also judging the coherence of the whole change, put it in the reason you give for that coherence verdict; otherwise list it as something only told to a person. One entry is one conflict, with a short plain title.

## Split by origin

- **Introduced or exposed by this change**: the change needs a redesign.
- **Purely pre-existing and unrelated**: only tell a person. Of the finding weights (heaviest first: block, suggest, nit, info), use suggest or lighter, never block. One entry per risk: where it is and what is risky, and when known, how it happens, a measurement, and the condition under which it would be a false positive.

## Holes left unfixed on purpose

If the fix plan was reviewed before the change was written, and you have the holes that review raised (defects the change would make if built as planned) that whoever wrote the change answered they would leave unfixed, check whether each one still exists after the change. One that still exists and is a harm this change introduced or exposed needs a redesign; one where telling a person is enough is told as a suggestion; one that has disappeared is not raised.

## When your answer is sent back

This applies when whoever checks your answer returns it to you because some of its policy conflicts were not written correctly.

- If a policy conflict names no recorded policy row, rewrite it so that it copies the row's name character for character — or, if what it names is a comment, a docstring, or a test description rather than a policy, take it out of the conflicts. Fix every entry named, and return the whole list of conflicts, including the ones you do not change.
- When you copy an entry that was already passed, do not change its text.

## Writing what a person is asked

Write each lost capability and each conflict for a reader who knows neither the work nor its tooling: the title in plain words, and enough facts to decide from the entry alone.

Works well with (optional; this file is complete without them): perspectives on coherence across the files a change touched (naming, conventions, documents kept in step), and on writing a question to a person so that a first-time reader can decide it from the text alone.
