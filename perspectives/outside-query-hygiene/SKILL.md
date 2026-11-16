---
name: outside-query-hygiene
description: Keeps every query sent to an outside service free of the target's names and text, restating the lookup as the general problem and going to primary sources first. Use whenever searching the web or a registry while working on possibly private material, or when asked "is it safe to send this query". Not for judging the results that come back.
---

# Keep outside queries free of the target's names

**Core rule: a query you send to a service that does not hold the target stays in that service's records. Never put the target's names or text in it.**

Treat the target (the repository, documents, and diff you were given) as possibly private even when it looks public. Do not decide for yourself whether it is public.

## Pitfalls (read first)

- **The tool does not matter.** Web search, web fetch, a command-line request from a shell, a query to a package registry: all of them leave the query (search words, URLs, command arguments) outside.
- **A name you cannot place is the owner's name.** When in doubt, leave it out.
- **A sub-agent does not inherit this rule.** If you start a sub-agent, put this rule into its instructions word for word; otherwise it does not reach it.

## Steps

### How to write a query

- Write it as the general problem you want to look up, restated in a few words. Look up the general name of the mechanism, not the name of an internal module.
- Leave out the target owner's names: company names, product names, internal code names, repository names, branch names, paths, the target's own identifiers.
- Leave out the target's text: code fragments, diffs, sentences from its documents.
- Third-party names may go in: things made and published outside the target, such as the open-source software, standards, and vendor products the target uses, and the general form of public error messages. Primary sources need them.
- To check the meaning of a word used only inside the target (in-house jargon), look up its definition restated in general words and the candidate standard terms, not the word itself.

### When a lookup cannot be done without the owner's names

Do not run it. Leave it for a person to check.

### What is not an outside query

A query to a place that already holds the target — the repository's own version control, the host that holds the repository, reading that host's pages — is not an outside query, and this rule does not cover it.

### Which sources to use

- Go to primary sources first: standards documents, official documentation and guides, original texts, official repositories, and practitioner documents that are widely cited.
- Prefer them over blog posts and other secondary sources.
- Check that a source is not about an old version.

## Done when

- No query you sent holds the target owner's names or the target's text.
- Every lookup that needed the owner's names was not run, and is named in your answer.
- The sources you rely on are primary where you found primary ones, and none is about an old version.
- Any sub-agent you started got this rule word for word in its instructions.

## How to report

- Name each lookup you did not run as "a lookup not run because it needs the target's names". If the answer has a place for "missing", "cannot verify", or "not found (what was searched)", write it there.
- If you found only secondary sources, say so.

## Example

Input: while reviewing a private repository, you want to know how others make retries of a payment call safe. The call sits in an internal module named "ledger-bridge", and you also want to know what that name means.

Reply:
- Query sent: "idempotency key retry payment API" (the general problem, no internal names). Source: the payment provider's official documentation on idempotent requests (primary).
- A lookup not run because it needs the target's names: what "ledger-bridge" means. Left for a person to check.

## Works well with

- Any work that compares a request or a change with how practitioners solve the same problem, which needs outside lookups.
- A stance for looking things up and bringing them back for someone else to judge.
