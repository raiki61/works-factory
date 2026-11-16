---
name: ground-every-departure
description: Compares the part a change touches with the general structure of that kind of system (how practitioners split it into parts, what flows which way, where each value's source of truth lives, which way dependencies point, where boundaries are drawn) and requires a ground for every departure — only a rule the target decided in writing or an outside fact that cannot be moved counts, never the target's current state. Use when judging, planning, or reviewing a change whose form differs from the usual structure, or when asked "why is it built this way", "is this departure justified", "should this follow the usual layout".
---

# Require a ground for every departure from the general structure

**Core rule: compare the touched part with the general structure of the system that contains it, and give a ground for every place where the chosen form departs from it.**

The general structure of a kind of system is how practitioners commonly split such a system into parts, what flows between the parts and in which direction, where the source of truth of each value lives (the one place it is born), which way the dependencies point, and where the boundaries are drawn. It is not a particular solution or tool. Use the drawing of it you were given; otherwise, the way practitioners build such systems.

## Pitfalls (read first)

- **The current state is not a ground.** Its settings, code, layout, and habits, a precedent in the code (how the code solves the same problem today), and the fact that something does not exist yet.
- **A precedent counts only when it points the same way as the general structure.** When it points away, it is part of what the change may have to move, not a form to copy.
- **Aligning is not scope creep.** The work needed to bring the touched part in line with the general structure belongs to the same change: do not count it as widening the scope, do not leave it out as out of scope, and do not split it into another request. That the request did not foresee it is not a reason to leave it.

## The only two grounds

1. **A rule the target decided in writing**: its constitution, rules, and design documents (its instruction files and the canonical documents they point to), the policy for this piece of work, and a person's earlier decisions (answers at approval points and recorded decisions). Such a rule wins over the general structure. Code comments and docstrings are not such rules.
2. **An outside fact that cannot be moved**: the specification of an outside tool or service, a law, or a contract.

## What else to write for a departure

Say what piles up if the same problem comes three more times and each time is solved by extending this form.
