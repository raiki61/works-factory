---
name: concept-places
description: Judges, unit by unit, whether a planned or made change dirties the target's structure, by going against its written intent or making more places know a design concept, and names the way to avoid it. Use when reviewing a plan or a diff for structure, or when asked "does this spread a concept into more places". Not for checking that callers and connected sides were updated.
---

# Judge whether a change makes more places know a design concept

**Core rule: measure simplicity not by the number of lines but by the number of places that know a design concept, and judge against the target's written intent, not against how the surrounding code looks today.**

The one axis of judgment: does the whole become simpler while the purpose is met and the protecting mechanisms keep working? A unit here is one piece of the change judged on its own: one planned fix, or the files one fix changed.

## Pitfalls (read first)

- **The written intent wins over the surrounding code.** The written intent is the target's own constitution, rules, and design documents, and the policy for the work at hand. The surrounding code may already have drifted from it; a change that copies the drift is still dirty.
- **Do not let a clean unit pass in silence.** Give every unit a verdict, dirty or clean, with its reason.
- **Rest every verdict on evidence you can point to** (the unit's summary, the measured counts, the diff). A dirty verdict against the written intent quotes, word for word, the rule it goes against or the home it ignores.
- **Read a plan's reasons for not following earlier advice as claims, not as facts.**
- **Do not ask a person what the sources settle.** Only when the deciding sources leave the ways to avoid it split (they cannot be narrowed to one) does the unit go to a person.

## Steps

Ask the question of every unit; read "For a dirty unit" and "When it goes to a person" only for a unit you judged dirty.

### The question for each unit

After this change, does the target go against what its written intent says, or know a design concept (a word, a field name, a value, or a decision rule) in more places than before?

- Where the written intent names the **home** of a concept (the one place that holds it), a change that writes the concept outside its home is dirty.
- Where it names no home, recommend the form that gathers the concept into a place that already knows it.
- Where there is a map of concepts and a count of the places that know each one, take it as given. Otherwise use what can be measured — copied blocks of code, entry points, the places where names appear — as evidence of where a concept is known.
- If nothing goes against the written intent and the number of places does not grow, the unit is clean.
- When no written intent of the target can be read, judge by the number of places alone.
- For a planned fix, judge the fix its summary describes; for a change already made, judge what the diff did in the unit's files.

### The six forms of dirt

1. Rewrites a shared thing per execution or per caller.
2. Splits one responsibility across two places (only when the same concept is written in a second place).
3. Bends an existing mechanism from the side.
4. Crosses the boundary of a component (such as a module, or a separately run part) and assumes the inside of another component.
5. Adds a new name or entry point with no framework to hold it.
6. Takes in the circumstances of an outside tool by naming the tool.

### For a dirty unit

- Name the forms that apply.
- Give the way to avoid it you recommend, and why.
- If the unit's summary names practitioners' practice, make the recommendation follow that practice, or say why it does not.
- When written documents disagree, the one nearer to the unit's files wins; the policy for the work at hand, when there is one, wins over every document.
- When a document points to a rule that is not in the version under review (the commit fixed as the material of the review), judge against the version found elsewhere (for example a branch not merged yet) but say that it is not in the version under review; when it cannot be read at all, say that the rule for that area could not be read.

### When it goes to a person

The deciding sources are: the written intent and the policy, the person's earlier decisions, the same situation elsewhere in the target where it points the same way as the general structure, and practitioners' practice. Only when these still do not settle one way to avoid it does the unit go to a person.

## Done when

- Every unit has a verdict, dirty or clean, with its reason; no unit passed in silence.
- Every verdict rests on evidence you can point to, and every dirty verdict against the written intent quotes the rule or the home word for word.
- Every dirty unit names its forms and a recommended way to avoid it.
- No unit went to a person that the deciding sources settle.

## How to report

- For each unit: dirty or clean, the evidence you rest on, and the reason.
- For a dirty unit, also: the numbers of the forms that apply, the way to avoid it you recommend, and why.
- For a unit that goes to a person, also: your recommendation; at least one rejected option and its cost; and why it does not settle (what split against what).

## Example

Input: A planned fix adds a check that a request's size is under the limit, and writes the limit as a number in the new check. The target's design document says the limit lives in the settings file, which already holds it.

Reply:
- Unit 1: dirty, form 2. Evidence: the summary says "compare against 1000" and the design document says "the size limit is set only in the settings file" (quoted word for word). The concept now has a second place outside its home.
- Recommended: read the limit from the settings file in the new check. Why: the limit then stays known in one place.

## Works well with

- comparing the touched part with the general structure of such systems;
- deciding what counts as a ground for departing from that structure;
- writing questions to a person so a first-time reader can decide from the text alone.
