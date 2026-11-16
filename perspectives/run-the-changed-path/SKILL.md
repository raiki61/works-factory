---
name: run-the-changed-path
description: Runs, once, a user-visible or outside-facing path a change touches and records the real values that pass through it, instead of trusting a green test. Use when such a path has changed, or when asked "did anyone actually try it". Not for walking setup procedures or documentation steps.
---

# Run the changed path once and observe what flows through it

**Core rule: do not treat a path you did not run as verified. Run it once, the same way it runs in production, and write down the values you saw.**

Every other way of reviewing reads the diff. Defects that only appear when the code runs — behaviour specific to the runtime environment, values altered by a middle layer, rendering — do not appear however many times the diff is read. What you observe is the real thing that flowed through the same path as in production, not a test turning green.

## Pitfalls (read first)

- **Applies when the change touches a path users can see, or a seam with the outside.**
- **A green test is not an observation.** Record the value that actually passed through the path.
- **"Observed" needs at least one observation.** Do not report "found something" or "all clean" without at least one path you ran and the value you saw on it.
- **Do not break the real working tree.** Do not change the working tree, the checked-out commit (HEAD), the branch, or the files version control ignores. Make any copy you need for running in a fresh temporary directory outside it.
- **When you cannot run it, do not pretend.** If there is no environment, no permission, or it needs real hardware, say so: why it cannot be run, and what a person has to run and look at. A person decides whether there is really no way.

## Steps

1. Find the paths the change touches that users can see or that cross a seam with the outside.
2. Run each such path once, the same way it runs in production, from a copy in a fresh temporary directory.
3. Write down the value that actually passed through each path you ran.
4. For a path you cannot run, write why, and what a person has to run and look at.

## Done when

- Every path you report as observed has the value you saw on it, and no "found something" or "all clean" stands without one.
- Every path you could not run has the reason and what a person has to run and look at.
- The real working tree is as it was.

## How to report

For each path you ran: the path, and the value you observed on it. Or, if you could not run it: why, and what a person must run and look at.

When you name a place in a file, give the line number in the current file, not a line in the diff: lines of a diff are not lines of the file, and a person cannot open that place. Open the file and confirm the line before writing it; if you cannot, give the path with a function name or similar instead of a line number.

## Example

Input: a change makes the order confirmation page show the delivery date in the reader's local format.

Reply: Ran the confirmation page for a test order from a temporary copy. Value seen: "Delivery: 11/18/2026" for a reader whose locale shows day first — the template layer formats the date again after the change has formatted it.

## Works well with

- A set of rules that keeps the reviewed repository's own names and text out of queries sent to outside services (web searches, fetched URLs).
