---
name: change-structure-review
description: "Reviews a change's implementation and design: conventions, code and abstractions with no reason to exist, fit with existing patterns, boundaries, and root cause versus patch. Use when asked for a design-level code review, such as \"is this over-engineered\". Not for purpose-free hygiene checks of a diff, nor for consistency across the whole repository."
---

# Review a change's implementation and design

**Core rule: judge by what reading the code settles. Translate a design principle into a question the imports answer before you raise it.**

## Pitfalls (read first)

- **Where a mechanism already enforces a convention (a lint rule, a CI job), only confirm it is green.** Doing an already-red-on-violation check again by hand or by a model finds nothing more.
- **Before raising a boundary violation, check whether it already existed at the base**: separate what this change brought in from what was already there.
- **If no dependency table is found, infer it from the actual imports nearby and say it is inferred.**

## Steps

### Implementation

- Fit with the conventions of the language, framework, and lint (as far as the package manifest and lint settings tell).
- Code and abstractions that lost their reason to exist in this diff but were not deleted.
- Whether less code and fewer abstractions could reach the same purpose.
- Fit with existing patterns and names; no new pattern brought in.
- Whether a first-time developer can follow the intent and flow without getting lost.

### Design

- **Architecture boundaries**: violations of layer dependencies and module boundaries. Look for a dependency table in the README, documents, and lint settings, and compare.
- **Ownership of abstractions**: for each interface, abstract base, or port the diff adds, who defines it — the side that uses it or the side that implements it? If the implementing side defines it, the dependency is not inverted. Also name what the abstraction **fails to constrain** (it returns an untyped value, it does not fix the shape of the return): an abstraction that constrains the name but not the shape lets the places that actually break pass straight through.
- **Details leaking inward**: how far outer details (protocol vocabulary, wire formats, display formats, constraints of a downstream runtime) have entered the types and models of inner layers. Is something that should be converted at the boundary sitting inside?
- Is it a root-cause solution rather than an ad-hoc patch?
- Does the same problem exist elsewhere, to be solved together?
- Name **only one** highest-leverage improvement this change prompts (existing code included, outside the change's scope allowed).

## Done when

- Conventions a lint rule or CI job already enforces were only confirmed green, not checked again.
- Every boundary violation raised says whether this change brought it in or it existed at the base, and an inferred dependency table is marked as inferred.
- Exactly one highest-leverage improvement is named.

## How to report

Findings under implementation and under design, each with where and what is wrong. For a boundary violation, add whether this change brought it in or it was already at the base, and whether the dependency table was found or inferred. End with the one highest-leverage improvement.

## Example

Input: a diff adds an interface for a storage backend inside the module that implements it; its read method returns an untyped value.

Reply: Design, ownership of abstractions: the interface is defined by the implementing side, so the dependency is not inverted; define it on the side that uses it. It also fails to constrain the shape of the read result: it returns an untyped value. Brought in by this change (not at the base).

## Works well with

- A view that learns the target's own conventions from its primary sources before review points are applied.
- A view that sets the bar a review finding must clear before it is raised.
