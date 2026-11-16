---
name: check-against-practice
description: Restates each line of a change request as the general kind of work it is, with the target's names and the request's proposed means removed, finds in primary sources how practitioners routinely solve that kind of work, and judges whether the means the request proposes matches that practice or departs from it. Use before building what a request asks for, when the request names a specific mechanism, or when asked "how does the world solve this", "is this the standard way", "check this against practice".
---

# Check a request against how practitioners solve it

**Core rule: do not ask about the parts of the mechanism the request names, or about the output format of a tool. Ask how practitioners do this kind of work.**

A request usually arrives already shaped as a means ("add X so that Y is judged"). Taken as given, the means hides the question of whether the work should be done that way at all. This perspective steps up from the named mechanism to the kind of work, finds the established practice for that kind of work, and only then compares the request's means with it.

## Pitfalls (read first)

- **The means is a proposal to doubt, not a given.** Whether it is good is decided against the practice that is found, never before.
- **Restate before you look at the target.** Reading the target's code first pulls the restatement down into its mechanism. Do the restatement from the request text alone (or have an eye that cannot see the target do it).
- **Never paraphrase an excerpt.** An excerpt is copied word for word from a page you actually opened. A paraphrase or a summary presented as a quote is not evidence.
- **Never cite a page you did not open.** A URL that only appeared in a search result list is not a source.
- **Never put the target's names into an outside query** (see "Queries to outside services").

## 1. Restate each request line as a problem class

For every line of the request:

- **Problem**: one sentence that states the line as a problem class, in the words of the work practitioners do. Step up one level to the kind of work: even if the request says "add X so that Y is judged", the class is neither how to build X nor how to read Y. Shape of an example: "in test-first development, how to make a test that calls a not-yet-existing function fail for a target that must be compiled".
- **Activity**: a short name for the kind of work.
- **Proposed means**: the means the request proposes, set apart from the problem, in words of the means. Empty if the request proposes none. Keep it out of the problem and out of the queries.
- **Queries**: one or a few search queries that ask how practitioners solve this class: practice, convention, standards.
- If one line spans two kinds of work, restate it as the one kind above both.
- Remove the target's names (paths, files, functions, fields, environment variables, component names, run ids) from the problem, the activity, the proposed means, and the queries.

## 2. Find the practice

- Search with the queries; you may add queries, without the target's names.
- Go to primary sources first: standards documents, official documentation and guides, original texts, official repositories, and widely cited practitioner documents. Prefer them over blog posts and other secondary sources. Check that a source is not about an old version. If you find only secondary sources, say so.
- Check that a source fits the situation of this request, not just its keywords.
- Bring back excerpts copied word for word from the pages you opened, long enough to carry the point.
- State the practice in one to three sentences, from the excerpts, without the target's names.
- When you find no source for a class, state the practice from your own knowledge and mark it plainly as not confirmed by a source.

## 3. Judge how the practice applies

For each class:

- **Applies**: how the practice applies to this request.
- **Does not apply**: where it does not. If it does not apply to this request at all, say so instead of forcing it.
- **Verdict on the means**: the same as the practice, different from it, or no means proposed.
- **When it differs**, name the difference and recommend the practice, in this form: "The request does X; the practice is Y. Choose Y unless …". The "unless" names what would have to be true for the request's means to win.

## Queries to outside services

A query you send to a service that does not hold the target (search words, URLs, command arguments) stays in that service's records. Treat the target as possibly private even when it looks public; do not decide for yourself that it is public.

- Write a query as the general problem, restated in a few words: the general name of the mechanism, not the name of an internal module.
- Leave out the owner's names (company, product, internal code names, repository and branch names, paths, the target's own identifiers) and the target's text (code fragments, diffs, sentences from its documents).
- Third-party names (open-source software, standards, and vendor products the target uses, and the general form of public error messages) may be included; primary sources need them. Treat a name you cannot place as the owner's name.
- To check a word used only inside the target (in-house jargon), look up its definition restated in general words and the candidate standard terms, not the word itself.
- Do not run a lookup that cannot be done without the owner's names. Say that it was not run because it needs the target's names, and leave it for a person.
- A query to a place that already holds the target (its own repository host) is not an outside query.
- If you start a sub-agent, put these rules, word for word, into its instructions. They do not reach it otherwise.
