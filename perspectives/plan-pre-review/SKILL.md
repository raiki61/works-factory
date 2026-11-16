---
name: plan-pre-review
description: Reviews a fix plan or a design draft before any code is written, as a different eye from whoever wrote it, and predicts the holes the change will make once built — copies, unclosed entrances, readers left behind, dead paths, scope creep, regressions, policy conflicts, unchecked precedents — grading each by the concrete harm, offering the smaller alternative, and separating what a person must decide from what the rules and standard practice already decide. Use before approving a plan or a design, or when asked to "pre-review this plan", "what will this change break", "check this design before we build it".
---

# Pre-review a plan before the change is written

**Core rule: predict, before the change is written, the holes the change will make once it is written — and try to refute the plan, not confirm it.**

Why: when every stage that judges a change comes after the change, the holes a change makes are first found by the next whole round of review (measured once: 8 of the findings of one round were products of the previous round's fix). A pre-review moves that finding to before the change.

## Pitfalls (read first)

- **You are a different eye.** You did not write the plan, and you are not the one who judged the request. Either may be partial to its own idea; neither one's conclusion is a reason for you to agree.
- **Try to refute.** Reading to confirm collects only the evidence that agrees.
- **Base the judgment on what you were given, what you read yourself in the repository, and primary sources.** Take your evidence from the version under review, not from a working tree that may be in the middle of a change.
- **When the input is not enough, say so.** Do not write "no holes" when a file you needed could not be read: name what could not be read and what could not be checked. Do not fill the gap with a guess.
- **Leave nothing out silently.** Every hole carries its reason. When you find none, say what you checked that lets you say there is none.
- **Do not decide for a person.** Whether a regression or a policy conflict is accepted as a cost is never decided by you, the plan's author, or the one who writes the fix: list it.

## The one axis of judgment

Does the whole get simpler, while the purpose is met and the mechanisms that protect keep working? Measure simplicity not by the number of lines but by **the number of places that know a design concept**.

## The eight checks

1. **Copy**: does what is added copy, into another place, a rule, a type, a vocabulary, or a procedure that already has a canonical home? Read the repository to check.
2. **Entrance**: besides the route that an added fence watches, is there another route into the same set? **Count every route into the set first**, then judge: a fence that closes one entrance leaves the next one as the next round's finding. **Always give the form that closes it without adding a fence or an entrance** (delete, merge, or leave it to the world's tool), or say why there is none. A finding that only says "add an entrance" plants the next finding in the entrance it adds (seen once: an entrance added on a pre-review's advice was raised in the next round as "it keeps adding entrances").
3. **Contract drift**: does a side that reads or writes what changes (instructions, rejection texts, documents, tests, other callers) stay behind?
4. **Dead path**: is what is added left in a form that nothing uses or reaches?
5. **Scope creep and minimality**: does it add a mechanism that the purpose does not need (scope creep), or a prescription larger than needed within the purpose (minimality)? Raise it only when you can name the smaller prescription concretely, and name it.
6. **Regression**: does it remove or narrow a capability that existed before this change started? Compare with the state before the change, not with an ideal. List what it narrows explicitly.
7. **Policy**: does it conflict with recorded policy — the written rules, the request's own answers, a person's earlier decisions? Code comments, docstrings, and test descriptions are not policy: if the plan leaves such text disagreeing, raise it as contract drift and have the plan rewrite the text.
8. **Precedent source**: open the sources of the precedents the plan adopts or aligns with, and check that each exists and fits the problem. A machine can check that a source is named; only you check what it says.

In addition, when there is **an alternative that closes everything together, smaller** (delete, merge, adopt the world's solution), give it.

## Weigh what already exists

- When the plan creates a new mechanism (a script, a subcommand, a helper, a test fixture such as a fake tool or a bundle of tests), check that it names the existing things it considered and why it did not take them (or how it searched, if it found nothing). Missing that is a copy hole.
- Even when it is written, search the files the plan touches and their siblings yourself. If an existing helper does the same job, give the form that uses it.
- Before you ask for a new mechanism to close a hole, search the same places. If an existing helper closes it, name that helper.
- **Homes of concepts**: for each concept the plan touches, check whether the repository already has one place that holds it. A plan that makes another place know that concept (copies a word, a field name, a value, or a decision rule) instead of using the home is a copy hole: name the concept, the home's path and line, and the new place. Not using an existing home is serious; adding a second place for a concept that has no home yet is a suggestion. Do not raise one whose home you cannot point to.

## Grade each hole by its harm

- **Severity**: a hole that, once written, will block the next round is blocking; anything else is a suggestion.
- **Reach**: the harm met if the change goes ahead without fixing the hole. Central harms: the change breaks; a behaviour that exists now is lost; it goes against recorded policy; it forces a redesign (including a fence that misses a whole class of entrances). Anything else is peripheral: stale explanatory text, an omission in a list of rewrites, test material — still answered during the change and checked again after it.
- Write the concrete harm in the first sentence of the reason.
- **A detail one test can guard is peripheral**: when the lost behaviour stays inside one function's detail (an ordering rule, the arithmetic of a limit, a tie-break) and one test can pin it, give that test (what goes in, what it asserts). **Never move down a hole about a design choice** (which component, boundary, or route the plan uses).
- **The form that does not narrow**: on a regression, when you can, show a form that keeps the earlier behaviour, applies the new behaviour only where it is wanted, and names out loud the cases where it cannot apply.

## Ask a person only what nothing else settles

- Before you send anything to a person, look up how the world solves the same problem: standards, the established practice of well-known open-source software, official documents. A means the request proposes decides nothing; it is a proposal to doubt against that practice. The request's text does settle the cost it accepts and the scope it asks for.
- If the standard practice or the request's own text settles the answer on one, decide it yourself and name that source.
- A person is asked in only three cases: (1) the deciding sources disagree (earlier decisions, policy, how the code already solves the same problem, the standard practice); (2) the answer changes with how a person ranks priorities, and the standard practice does not settle the ranking; (3) following the sources would overturn a recorded decision. That an item narrows today's behaviour or touches policy is not by itself a reason to ask.
- Turning a behaviour on, where, and how strongly is not case (2) when the standard practice makes it a setting whose default keeps today's behaviour. A loss caused by a limit outside the change is not case (2) when the request already accepts it.
- When nothing settles it and none of the three cases fits, go ahead with your own recommendation and say where you searched and found nothing.
- **Regardless**, these always go to a person: a write to the outside, an operation that cannot be undone, a change to the policy document, widening a protection (credentials, sandbox), a web result that raised a new doubt, or a touch on a protected path.
- When an item goes to a person, give one recommended answer (let it through, with its scope and conditions; or stop, with why), written so it can be copied as the answer.
- When part of the fix for a hole is a person's decision (it would overturn recorded policy), raise that part as its own policy item; do not bury "goes to a person" inside another hole's reason.
- When the plan departs from a means the requester named, or from a prescription given earlier for the problem, it never passes quietly, however well it explains itself: it goes to a person with your recommendation.
- When the plan says it follows a means the requester named, check that it really does; a false "follows" is a hole. When it really follows the means but an independent design (below) disagrees with that part, a person answers which side wins, with your recommendation — do not raise it as a defect of the plan.

## Departing from the general structure

The general structure of a kind of system is how practitioners commonly split it into parts, what flows between them and which way, where each value's source of truth lives, which way dependencies point, and where boundaries are drawn. Compare the part the change touches with it, and require a ground for every departure. Only two things are grounds:

1. A rule the target decided in writing (its rules and design documents, the policy for this run, a person's recorded decisions). Code comments and docstrings are not such rules.
2. An outside fact that cannot be moved (an outside tool's specification, a law, a contract).

The current state of the target is not a ground: its settings, code, layout, habits, and precedents in its code. A precedent counts only when it points the same way as the general structure. For a departure, also say what piles up if the same problem comes three more times and is solved each time by extending this form. Bringing the touched part in line with the general structure belongs to the same change: it is not scope creep and not a separate request.

## Compare with an independent design (when one exists)

An independent design is one made from the purpose alone, without seeing the plan. Compare structure: what each holds fixed and what it derives, where it puts the seams, and whether the routine flow the stakeholders run day to day closes. Judge each mechanism the plan adds, and the size of what it writes, against the design.

- Show a disagreement with quotes from both sides, word for word. A point you cannot quote from the design is not a disagreement (the design knows nothing of the implementation's circumstances).
- A mechanism with no pair in the design, and a gap in size, are disagreements; for a gap in size, give the smaller alternative.
- The independent design does not win on its own either: it is one more input to refute.

## Reading a plan

- For each change, check that the smaller prescriptions were listed in order and that one sentence holds for why each smaller one falls.
- Check that the plan does not widen beyond the way of fixing the earlier judgment named.
- Look for what disappears or narrows but is not in the plan's list of what it narrows: that is a blocking hole, and it must be written back into the list.
- Every place the change ripples to (callers to align, tests that assert a literal value) must be either covered by the plan, shown to have no effect, or raised as a hole.
- Check that the plan's acceptance tests go through the real route, do not assert the return value of a mock, and do not lean on comparing wording; that the failure each test should show before the fix really happens with the current code; and that rewritten tests change only behaviour the request changes, not expected values bent to fit the implementation.
- Check that what the plan may write is enough for the fix and not too wide, and that what it says it does not touch covers what the request does not touch.

## Reading a design draft

A design draft is reviewed before anyone approves it. Besides the eight checks, look at:

1. **Asking and deciding**: a question put to the person that the rules already decide, and a decision the draft makes alone that needs the person.
2. **Missing options and costs**: a question with no option that builds on what exists, or no option that does nothing; an option whose cost or gain is missing.
3. **New parts where existing ones are enough**: read the existing parts it names, and those it should have named.
4. **Content the rework drops**: something the rework drops without listing it as narrowed, or sends somewhere nothing receives it.
5. **Changes that cannot go down to the fix**: a change not concrete enough to hand on (a place and what changes there).
6. **Difference from the independent design**, if one is given.
7. **The person's answers left out**: an answer said to be applied whose content is not in the draft.
8. **Unasked premises**: an assumed premise that would change the design if it fell, but that the draft does not ask about.

In a design draft, "the change" means building the design: a hole that forces the design to be redone is a redesign harm; a fine adjustment that can be handed on to planning is peripheral.

## Later passes of the same plan

- First settle every earlier hole that needs an answer: gone, or raised again under the same name.
- Keep the same severity and the same reach. If you move a central hole down to peripheral, say in the first sentence why it no longer meets the central definition.
- Look only at what changed since the earlier pass and where it ripples; do not search the unchanged parts again for new holes.
- For each new blocking hole, say where it came from: missed by the earlier review, introduced by the revision, a restatement of an earlier hole, or the flip side of closing an earlier hole (two things that cannot both hold). A flip side goes to a person with a recommendation of which side to put first.
- When the back-and-forth stops, recommend continuing only when you can say every open block and every held item can be settled inside the fix; otherwise recommend stopping.

## Looking across several items of one plan

Look only at how the items relate: conflicting changes to the same line or hunk, order dependencies, duplicated work, and one root split into different items. Items that only touch different places of the same file are not a hole.
