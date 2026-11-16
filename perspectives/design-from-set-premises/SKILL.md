---
name: design-from-set-premises
description: Reads the premises a person already set (answers given during the work, design sections the request names, map documents) and treats a withdrawn or changed requirement as changed before designing. Use when designing after a person has answered questions, or when asked "did my answers change the requirement". Not for designing blind from the purpose alone.
---

# Design from the premises a person set

**Core rule: a person's answer during the work outranks the earlier wording of the purpose. Design against the purpose as the answers changed it.**

Words used here:

- **The target**: the system (repository) the design is for.
- **The request**: the person's request for the change, the text the design starts from.
- **Map documents**: the documents at the target's root that describe its overall structure (an architecture overview, a list of components and how they connect).

## Pitfalls (read first)

- **Read the answers first**, before any other material.
- **A withdrawn requirement is not a fixed contract.** If an answer withdraws or changes the purpose or an earlier requirement, take the requirement as withdrawn or changed as the premise.
- **Do not count a kept withdrawn requirement alone as a broken premise.** If a design still keeps a withdrawn requirement, that alone is neither a difference nor a broken premise; compare against the purpose as the answers changed it.
- **A missing document is not an empty one.** If the request's text could not be read, the design-document sections it names were not given to you: do not take their absence as the request naming none.

## Steps

### What to read as premises

1. **Answers a person gave during the work** (when the work stopped until a person answered a question).
2. **The design-document sections the request names**, at the version the request was fixed at. Read them as part of the request, like the purpose.
3. **The map documents at the target's root.** Even where the request does not name them, start the design from what already exists in the system: the roots of trust (where credentials and trust start), the paths of outside communication (where the system talks to the outside), the things being protected.

## Done when

- You read the answers before the other material.
- Every requirement an answer withdrew or changed is taken as withdrawn or changed.
- The design starts from the roots of trust, the paths of outside communication, and the things being protected that the system already has.
- If the request's text could not be read, you did not take the named sections as none.

## How to report

Give the design against the purpose as the answers changed it. When you compare a design with the answers, judge it against that changed purpose, and do not count a kept withdrawn requirement alone as a difference.

## Example

Input: the request asked for "export reports as files and email them". During the work a person answered "drop the email part; files are enough". A draft design still has an email step.

Reply:
- Premise: the purpose is now "export reports as files"; the email requirement is withdrawn.
- The draft's email step alone is not a broken premise. Compared with the changed purpose, the file export meets it.
- The design starts from what exists: the export writes into the storage the system already protects, and adds no new path to the outside.

## Works well with

- Designing from the purpose alone before looking at a plan or the code.
- Comparing the touched system with the general structure of the same kind of system.
