---
name: change-structure-review
description: Reviews the implementation and design of a change — conventions of its language, framework, and lint settings, code left without a reason to exist, less code and fewer abstractions for the same purpose, fit with existing patterns and names, followability for a newcomer, architecture boundaries, who owns each added abstraction and what it fails to constrain, outer details leaking inward, root cause versus patch, the same problem elsewhere, and the one highest-leverage improvement. Use when reviewing a diff's code and design, or when asked "is this well designed", "does this cross a layer", "is there a simpler way".
---

# Review a change's implementation and design

**Core rule: judge by what reading the code settles. Translate a design principle into a question the imports answer before you raise it.**

## Pitfalls (read first)

- **Where a mechanism already enforces a convention (a lint rule, a CI job), only confirm it is green.** Doing an already-red-on-violation check again by hand or by a model finds nothing more.
- **Before raising a boundary violation, check whether it already existed at the base**: separate what this change brought in from what was already there.
- **If no dependency table is found, infer it from the actual imports nearby and say it is inferred.**

## Implementation

- Fit with the conventions of the language, framework, and lint (as far as the package manifest and lint settings tell).
- Code and abstractions that lost their reason to exist in this diff but were not deleted.
- Whether less code and fewer abstractions could reach the same purpose.
- Fit with existing patterns and names; no new pattern brought in.
- Whether a first-time developer can follow the intent and flow without getting lost.

## Design

- **Architecture boundaries**: violations of layer dependencies and module boundaries. Look for a dependency table in the README, documents, and lint settings, and compare.
- **Ownership of abstractions**: for each interface, abstract base, or port the diff adds, who defines it — the side that uses it or the side that implements it? If the implementing side defines it, the dependency is not inverted. Also name what the abstraction **fails to constrain** (it returns an untyped value, it does not fix the shape of the return): an abstraction that constrains the name but not the shape lets the places that actually break pass straight through.
- **Details leaking inward**: how far outer details (protocol vocabulary, wire formats, display formats, constraints of a downstream runtime) have entered the types and models of inner layers. Is something that should be converted at the boundary sitting inside?
- Is it a root-cause solution rather than an ad-hoc patch?
- Does the same problem exist elsewhere, to be solved together?
- Name **only one** highest-leverage improvement this change prompts (existing code included, outside the change's scope allowed).
