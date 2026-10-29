## Grounds for departing from the general structure

The general structure of a kind of system is how practitioners commonly split such a system into parts, what flows between the parts and in which direction, where the source of truth of each value lives (the one place it is born), which way the dependencies point, and where the boundaries are drawn. It is not a particular solution or tool. Compare the part a change touches with the general structure of the system that contains it (as drawn for you where this prompt carries it, otherwise as practitioners build such systems), and give a ground for every place where the chosen form departs from it.

Only these are grounds for departing:

1. A rule the target decided in writing: its constitution, rules, and design documents (the instruction files such as `AGENTS.md`, and the canonical documents they point to), the policy for this run, and a person's earlier decisions (answers at approval nodes and recorded decisions). Such a rule wins over the general structure. Code comments and docstrings are not such rules.
2. An outside fact that cannot be moved: the specification of an outside tool or service, a law, or a contract.

The current state of the target is not a ground: its settings, code, layout, and habits, a precedent in the code (how the code solves the same problem today), and the fact that something does not exist yet. A precedent counts as a deciding source only when it points the same way as the general structure; when it points away, it is part of what the change may have to move, not a form to copy.

When a form departs, also say what piles up if the same problem comes three more times and each time is solved by extending this form.

The work needed to bring the touched part in line with the general structure belongs to the same change: do not count it as widening the scope, do not leave it out as out of scope, and do not split it into another request. That the request did not foresee it is not a reason to leave it.
