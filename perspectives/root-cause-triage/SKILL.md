---
name: root-cause-triage
description: Judges a fix request and a pile of review findings as a read-only judge above the fixing side — tries to refute every finding, traces each survivor to its origin and up to three levels of "why could this exist", cuts root-cause units by the shape of the defect, picks the one root countermeasure and names what it closes, labels each unit, gives a search that counts every occurrence of the same shape, and settles each prescription from the zero prescription through earlier decisions, policy, the target's own precedent, and the world's practice, asking a person only what none of them settle. Use before fixing a set of findings, or when asked "triage these findings", "what is the root cause here", "which of these must we fix", "bundle these review comments".
---

# Triage a fix request into root-cause units

**Core rule: treat every finding — including the request itself — as something to refute; cut units by the shape of the defect in the code, not by a shared upper-level cause; and decide every prescription yourself unless one of three narrow cases sends it to a person.**

Why: the label and the way to fix bind the fixing side, which cannot overrule them, so the one who gives them must rank above it, read only, and not be anchored on the request's own idea of how to fix it.

## Pitfalls (read first)

- **Read only.** Do not change a single character of the working tree while you judge.
- **A silent skip is not "none".** Before you judge, every input you rely on (the request, the findings, the diff, the frozen purpose — the one-sentence purpose of the work, written before the first fix and not rewritten afterwards — and the records of earlier decisions) must have an explicit answer (present, absent, or not applicable). If one lacks it, or a file you need cannot be read, say which one and stop; do not judge on a gap.
- **The request is an object of refutation too.** Its rows come from a person, not from an observation, but try to kill the way it was asked for as well. A row of acceptance conditions whose test already passes means the failing state was never seen: doubt that the test really checks the requirement.
- **Do not take a hypothesis as given.** When the request's number and a re-measured value differ, take the re-measured value and write the difference down.
- **Do not widen beyond the frozen purpose.** An existing defect outside the purpose that the fix exposes is, by default, picked up in this fix. Only when you think it should go to another pull request instead, raise it separately for a person to decide; moving it out (to another pull request or a separate issue) is an exception the person grants. A finding that survives refutation but is outside the purpose is named one by one with why it is outside — not dropped, and not left as a vague mention.
- **If the purpose looks narrower than the request**, do not trust its boundary between inside and outside as it stands.
- **When there is no request row**, the thing judged is the findings and the diff; do not rewrite them into the shape of a request (where they came from — a person or an observation — would disappear).
- **Comments, docstrings, and test descriptions are the target's text, not policy.** Only recorded decisions count as earlier decisions or policy. When the target's text disagrees with the clean shape, the prescription rewrites that text; it is not a policy conflict.
- **Practice taken from knowledge alone is not verified.** Do not treat a practice row that was never checked against a source as checked.

## The tree for each finding

Root a tree at each finding, with four branches: (1) refutation, (2) origin, (3) upward expansion, (4) candidate prescriptions. Build all the trees first, then line the branches up against one another: bundle trees from the same root, check whether the measurement of one tree refutes the finding of another, and decide whether a finding is sound only after this cross-check.

When to stop deepening:

- Refutation: until the finding dies, or until it does not die even after reading the neighbourhood and the conditional clauses of the rule. Do this every time. Drop what you kill.
- Origin: as far as the label.
- Upward expansion: three levels.
- Prescription: until the deciding factors settle it on one, or it hits one of the three cases that go to a person.

## 1. The grain of a unit

- One unit is **one shape of defect in the code (which line is wrong in what way) that one way of fixing closes.**
- Bundle only another appearance of the same shape (one fix closes all, one search counts all), or what one fix to the defective line itself closes.
- Defects with different places to fix, different shapes, and where fixing one does not close the other are **separate units**, even if their upward expansion meets at the same upper cause (tests do not try the boundary, no mechanism makes a promise hold, the same discipline is missing). A cause that meets above is written in the framing, in each unit's chain of whys, and in the one shot — it is not a reason to bundle. Do not cut the depth of the root to make it fit.
- That two findings share a kind of origin (both a hygiene violation, both a dead route) is not a reason to bundle either.

## 2. Origin, in a fixed order

1. Is the logic correct?
2. Is the origin poor readability or naming, a dead route, a bypass of a standard mechanism, a reinvention of an external standard, a hygiene violation (leftover cleanup, a home-made bypass of an official mechanism, unguarded external I/O, a verification mechanism that fails open), a procedure that does not hold or misfires, or circular grounds?
3. The label.

A dead route, a bypass, a hygiene violation, or a reinvention is not a matter of taste: it causes concrete harm. Reconcile every row of the request without leaving one out.

## 3. Upward expansion

For each candidate that must be fixed, ask "why could this defect exist" up to three levels — no further, so that you do not land on "the culture is bad".

## 4. The one shot

- From the causes where the upper levels of several trees meet, choose the one whose fix makes the most findings vanish in a chain.
- Look at combinations too, not only single branches: two prescriptions that make each other unnecessary, one that contains the other, two that close only together.
- **Name the units you expect it to close.** A one shot with no names cannot be refuted, and the next round just picks the same root again.
- If nothing meets above (including a single finding), the one shot is the fix of the unit that closes the most. Only when there is nothing to fix is there no one shot.

## 5. Label and disposition

- Labels: block, suggest, nit, question, info. **Never make a raw finding alone a block.**
- A suggest is do-now (the default) or defer. Defer only for a structural reason; a sense of cost is not a reason.
- Write in the reason the facts and the refutation you applied.

## 6. Count every occurrence of the same shape

For every unit that must be fixed, do not stop at naming one place. Give a plain text search (patterns and paths) that pulls out all of "the same shape", so that coverage has a denominator.

- **Do not tie it to a version** (a commit or other fixed snapshot). It is counted before the fix and again after it on the working tree; a search pinned to a version keeps counting the old content and hides the fix.
- **Count every line that becomes a site to fix**, not only the root line, or the other sites go uncounted.
- Say which way you count: **the defect itself** (goes down when fixed) or **the population the fix applies to** (does not go down). Every hit of a population search must be something the fix changes; do not mix in things already correct. For a thing that is missing (a missing docstring or test), count what should carry it (the definition line, say).
- **When a defective line and a correct line read the same**, a defect count never reaches zero. Count instead a line that tells the defect apart (the condition of the branch to fix, say) as a population.
- **Make it testable on examples**: one line it must hit (copied from the present version), and one line it must not hit — for a defect count, at least one line as it reads after a correct fix (a partial match would otherwise keep counting it). If you cannot give an example, say why.
- If one search lists patterns for defects that are fixed in different ways, you bundled different shapes: go back and split the unit. Variants in how the same shape is written, or the several sites of one defect, are not different shapes.
- **Do not count the request itself.** A search whose paths are only the request's own files counts its text, not the sites to fix. For a unit that only adds something new, say there is no earlier shape to count.

## 7. Prescriptions: from the zero prescription, then the deciding factors

1. First list the zero prescriptions: withdraw, or settle it with one existing mechanism.
2. After the zero prescription and before anything that builds a new mechanism, apply the deciding factors in order: (a) a person's earlier decision as recorded; (b) the person's policy; (c) the same scene in the target — how its code already solves the same problem (stated intent in comments counts for neither a nor b); (d) the world's solution — standard specifications, well-known open-source software, official documents.
3. **The way of solving that the request and the purpose showed is not an earlier decision.** It is a proposal to doubt against practice. If practice differs from it, adopt the practice or write a reason, from outside the request, for departing.
4. If any factor settles it on one, decide it yourself, in the form "Chosen option: …, because …", with the source (name, document and section, or URL). **Do not send to a person what those factors settle.**
5. A person is asked in only three cases: (1) the deciding sources split; (2) the answer changes with how a person ranks priorities and practice does not settle the ranking; (3) it conflicts with a recorded decision (name that decision as recorded). A conflict with the target's text is not case 3.
6. A fork in the design — a prescription that reaches a new mechanism or widens a shared surface, and falls in one of the three cases — gets at least two options with consequence and cost, one sentence on why the zero prescription falls short (if you cannot write it, it is not a fork: take the zero prescription), and always your own recommendation.
7. **If a prescription reduces or narrows a capability that existed before, write the capability that is lost.** You do not decide whether to accept it as a cost.

## 8. Precedents

For every unit to fix and every question to a person, give one row: the generalized problem, the primary source, the verdict (adopt, adapt, does not apply, not found), and the reason. If the practice for this kind of problem was already gathered (for example by an earlier comparison with how the world solves it), use it first; look up yourself only what it does not cover. **If not found, say what you searched for and how.** For a question to a person, say which of the three cases it is and which sources applied; if you cannot, it is obvious — take it as a prescription.

## 9. Stable keys

Name a defect as "file path + symbol name + a one-sentence summary", where the path and symbol are where the defect shows (not where the fix would write) and the summary is in the shape of the symptom. Use the same string for the same defect every time.

## What else goes to a person

- **A question does not remove an obstacle**: the unit concerned stays a block.
- **An exposed defect outside the purpose** (above) is a request for an exception, not a way to drop a duty: it cannot take a block or a do-now unit with it — make that unit defer with a structural reason first.
- **A viewpoint misfire**: the same finding flares up again with no new evidence and the cause is not the code but the viewpoint — name which viewpoint.
- **Stuck**: whether the prescription was wrong or it is a design problem.
- **Not converging**: new blocks keep appearing round after round (seen from the trend of counts, tied to no one unit).
- **Needs the field**: it is decided only when a person checks real machines, outside environments, or operations that need permission. If a read-only command settles it when a person types it, give that command (never one that writes, sends outside, or cannot be undone).
- **An input awaiting a person** (unobserved, a list cut off, a record that could not be read, a CI that cannot run): always raise it.
- An answer a person already gave to a question: reuse that question's exact wording so it matches, or tie the answer to the question or unit it answers; if it matches nothing, say why.

## Later rounds

- What the check rejected last time is a caution so you do not fail at the same place, **not a hole to fix**: do not make a unit from it.
- What an independent eye said needs a redesign last round **is a hole to fix**: refute each one; make each survivor a block or do-now unit (never defer), and for each one killed or outside the purpose, say why.

Works well with: a perspective that compares the fix the request proposes with practitioners' practice, and one that keeps web searches and other outside queries free of the target repository's names and text.
