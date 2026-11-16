---
name: design-from-set-premises
description: Reads the premises a person set before designing — answers given during the work, the design-document sections the request names, and the map documents of the target — takes a withdrawn or changed requirement as changed, and starts the design from what the system already has (its roots of trust, its paths of outside communication, the things being protected). Use when designing from a purpose, when comparing a design with a person's answers, or when asked "design this from scratch", "what are the premises here", "did the answers change the requirement".
---

# Design from the premises a person set

**Core rule: a person's answer during the work outranks the earlier wording of the purpose. Design against the purpose as the answers changed it.**

Words used here:

- **The target**: the system (repository) the design is for.
- **The request**: the person's request for the change, the text the design starts from.
- **Approval points**: moments during the work where it stops until a person answers a question.
- **Map documents**: the documents at the target's root that describe its overall structure (an architecture overview, a list of components and how they connect).

## Pitfalls (read first)

- **Read the answers first**, before any other material.
- **A withdrawn requirement is not a fixed contract.** If an answer withdraws or changes the purpose or an earlier requirement, take the changed requirement as the premise.
- **Do not count a kept withdrawn requirement alone as a broken premise.** If a design still keeps a withdrawn requirement, that alone is neither a difference nor a broken premise; compare against the purpose as the answers changed it.
- **A missing document is not an empty one.** If the request's text could not be read, the design-document sections it names were not given to you: do not take their absence as the request naming none.

## What to read as premises

1. **Answers a person gave during the work** (at approval points).
2. **The design-document sections the request names**, at the version the request was fixed at. Read them as part of the request, like the purpose.
3. **The map documents at the target's root.** Even where the request does not name them, start the design from what already exists in the system: the roots of trust (where credentials and trust start), the paths of outside communication (where the system talks to the outside), the things being protected.
