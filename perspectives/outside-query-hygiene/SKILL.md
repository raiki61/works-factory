---
name: outside-query-hygiene
description: Keeps every query sent to an outside service (web search, web fetch, a package registry, any command that reaches a service that does not hold the target) free of the target's names and text, restates the lookup as the general problem, and goes to primary sources first. Use whenever you look something up outside while working on a repository or document that may be private, or when asked "search the web for this", "look up how others do it", "is it safe to send this query".
---

# Keep outside queries free of the target's names

**Core rule: a query you send to a service that does not hold the target stays in that service's records. Never put the target's names or text in it.**

Treat the target (the repository, documents, and diff you were given) as possibly private even when it looks public. Do not decide for yourself whether it is public.

## Pitfalls (read first)

- **The tool does not matter.** Web search, web fetch, a command-line request from a shell, a query to a package registry: all of them leave the query (search words, URLs, command arguments) outside.
- **A name you cannot place is the owner's name.** When in doubt, leave it out.
- **A sub-agent does not inherit this rule.** If you start a sub-agent, put this rule into its instructions word for word; otherwise it does not reach it.

## How to write a query

- Write it as the general problem you want to look up, restated in a few words. Look up the general name of the mechanism, not the name of an internal module.
- Leave out the target owner's names: company names, product names, internal code names, repository names, branch names, paths, the target's own identifiers.
- Leave out the target's text: code fragments, diffs, sentences from its documents.
- Third-party names may go in: things made and published outside the target, such as the open-source software, standards, and vendor products the target uses, and the general form of public error messages. Primary sources need them.
- To check the meaning of a word used only inside the target (in-house jargon), look up its definition restated in general words and the candidate standard terms, not the word itself.

## When a lookup cannot be done without the owner's names

Do not run it. Name it in your answer as "a lookup not run because it needs the target's names" and leave it for a person to check. If the answer has a place for "missing", "cannot verify", or "not found (what was searched)", write it there.

## What is not an outside query

A query to a place that already holds the target — the repository's own version control, the host that holds the repository, reading that host's pages — is not an outside query, and this rule does not cover it.

## Which sources to use

- Go to primary sources first: standards documents, official documentation and guides, original texts, official repositories, and practitioner documents that are widely cited.
- Prefer them over blog posts and other secondary sources.
- Check that a source is not about an old version.
- If you find only secondary sources, say so.
