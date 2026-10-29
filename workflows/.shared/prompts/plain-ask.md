<!-- required-for-fields: undecided_because asks questions ask_why stuck_recommend -->
Follow these rules when you write the fields of your output that ask a person to decide something (a question, why it is not settled, the options and their costs, the recommendation, what is handed to a person). The factory (the automated pipeline that is fixing the repository for this request) shows this text as you wrote it to the owner (the person who decides for the repository): at an approval node, where this run (this one execution of the factory) stops until the owner answers, and in the section on what a person decides of the report the factory writes at the end of the run.

- **Write for a first-time reader.** The reader is the owner coming back from other work. They know neither this run nor the factory's internal words. Each item must let them decide from its own text alone, without opening the run's records, the plan, or the code.
- **Give every fact the decision needs, even if the text gets longer.** Having the facts complete comes before keeping it short. Say what a thing is and why it matters before you name it.
- **Do not point into the run's internals in this text**: no `<path>:<line>` references, no positions in the run's JSON such as `plan[0]` or `faces[2]`, no unit keys, item numbers, or ids of rows and answers, and no names of the run's record files. Say in plain words what the thing is (for example "the function that computes the average", not a file and a line). References a machine checks (the deciding source, grounds, evidence, or a field this prompt tells you to fill with a `<path>:<line>`) belong in those fields, not here. The acceptance check rejects `<path>:<line>` and `<name>[<number>]` in this text and returns it to you.
- **Give each item this shape**, in this order, each part as its own sentence:
  1. Title: what is to be decided, said so that a person can answer it.
  2. Now: the current state, with the fact that makes it a question.
  3. Proposal: what the factory would do.
  4. Cost: what that costs, and whether and how it can be undone.
  5. Recommendation: which answer you recommend, and why.
  When the output schema (the shape of the JSON you return) splits an item over several fields (for example a question's reason and options, or a row's reason for not being settled and its recommendation), put each part in the field that holds it and keep the parts in this order across the fields.
- **One point, one item.** When the same point comes up from several angles (a capability that is narrowed, the policy, the world's solutions), raise it once and mention the other angles inside that one item.
