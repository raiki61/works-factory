## Where concepts live (a viewpoint the factory adds)

{shared:axis}

For each concept the diff touches, check its home (the one place that holds it) inside the target repository. If the section "Map of where concepts live" (the machine pasted it after this viewpoint) has a map, take its lines as the truth; if not, find the home from the repository's own structure (the README, module boundaries, places that hold the same word as a constant). If the diff writes a concept outside its home, or holds the same concept again in a form different from its home, and you can name the home's path and line, set `status` to {st_redesign} and start `reason` with "考えの住処: ", writing the concept's name, its home, and the place outside. What you cannot name stays {st_pass}; write it in `reason`. Put the maps you read (without a map, the homes you found from the structure) in `seen`, and the concepts whose home you could not find in `unseen`. Also check the places the machine measurement below says grew.

{after_section}

---

As the inspector: R3 overall coherence. Look at the coherence across files in the whole change (naming, conventions, interfaces, documents kept in step).

The canonical sources: `{review_md}` (on the target repository's side: {repo_review_md})

R3 looks at the coherence of the range the diff touched (whether what changed lines up with what already exists). This includes agreement between documents on defaults and recommendations (whether the documents the change touches converge on one recommended tool, procedure, and layout for the reader). Cross-cutting risks the diff did not touch are R4's to look at.
{shared:eye-seen}
