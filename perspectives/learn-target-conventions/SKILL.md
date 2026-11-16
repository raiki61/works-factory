---
name: learn-target-conventions
description: Before applying general review points, learns the target repository's own conventions from its primary sources (README, contribution guide, documents, lint/formatter/type-check settings, package manifest, CI definition, and the code near the diff), never copies those conventions into the review rules, says explicitly what could not be found or was inferred, and carries the learned facts forward only as references — re-read when the sources change, and never handed to a role that must doubt from zero. Use at the start of reviewing a repository you do not know, or when asked "what are this project's conventions", "how does this repo usually do it".
---

# Learn the target's own conventions from its primary sources

**Core rule: do not copy the target's conventions into the review rules. The moment you write them there, they become a copy of the canonical source and stay stale while the repository changes. Learn them from the target's primary sources before you apply the review points.**

## Pitfalls (read first)

- **Silence reads as "none".** Say explicitly what you could not pin down ("could not identify; looked in: ...") and mark what you filled in by inference as inferred.
- **What the code near the diff actually uses is the standard,** not the ideal written in a document. If the two disagree, that itself is a finding.
- **Where a lint, formatter, or type check already fails (goes red) whenever the convention is broken, only confirm that the check currently passes (is green).** Do not check that convention again by hand or by a model: it finds nothing more.
- **Carried facts are references only.** The way this kind of hand-over breaks is that a carried fact puts on the face of an established fact.
  - Do not freeze it as a constraint. "I read it that way in the last round" is not a ground. Re-read when the settings, manifest, or CI definition changed.
  - Do not hand it to a role that doubts from zero. Giving the learned facts to a context-blind grader or to a role that derives the ideal solution from the purpose alone breaks the isolation and lowers the judgment to one that takes "this repository's way" as given. Do not mix facts from earlier rounds into a doubting role's input.

## Where to read (use what exists; treat what does not as absent)

- **README, contribution guide, documents**: architecture boundaries, dependency policy, development flow.
- **Lint, formatter, and type-check settings**: conventions enforced by machine.
- **Package manifest**: the language, framework, and test defaults (what need not be written).
- **CI definition**: what is gated.
- **The code near the diff**: the actual standard mechanisms (internationalisation, settings loading, error classification, dependency injection, logging).

You may carry the facts you learned to later rounds (no need to re-read every round; in a round where the primary-source files did not change, carry the earlier learning over).
