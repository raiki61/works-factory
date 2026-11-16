---
name: citation-provenance
description: Extracts the factual claims a change makes about its own grounds — "the source of truth is X", "the convention is X", "this was agreed" — from the diff, the pull request description, and the docstrings, and checks for each that X existed before the change, so that a change citing as its ground something it adds itself (a circle) is caught, and an agreement with an outside party that leaves no trace is treated as an unconfirmed premise. Use when a change justifies itself by a convention, a canonical source, or an agreement, or when asked "where does this rule come from", "was this agreed before or invented here", "check the grounds this PR cites".
---

# Check where the grounds a change cites come from

**Core rule: a ground the change adds itself is no ground. For every claim of the form "the source of truth / the convention / the agreement is X", check that X existed before the change.**

## Pitfalls (read first)

- **Look for the claims in all three places**: the body of the diff, the pull request description, and the docstrings.
- **Check against the version before the change**, not the current one — for example by searching the history of the base for the string that defines X.
- **A circle is material, not a verdict.** When the diff cites as grounds something the diff itself adds, write the proof: the place in the diff that adds X, and the result of the command you ran.
- **An agreement with an outside party** (another team, another system, an upstream source) that leaves no trace before the change is an unconfirmed premise, not a fact.
- **Do not break the real working tree.** Make any copy in a fresh temporary directory outside it.

## How to report

One row per extracted claim: the sentence of the claim, whether X existed before the change (yes or no), and how you checked it and what you found. Say whether any circle was found, and how many.

Works well with (optional; this file does not need it): a set of rules that keeps the reviewed repository's own names and text out of queries sent to outside services (web searches, fetched URLs).
