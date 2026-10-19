How to write `material`: `status` is one of the following.
- `found`: you found something. Give `count` (an integer) and `detail`.
- `clean`: you looked in this run and found nothing. Say in `checked` what you looked at.
- `not_applicable`: the viewpoint does not apply. Give `reason`. Whether you may write it is in the section on `not_applicable`.
- `awaiting_human`: it waits for a person to start something. Give `reason`.
- `not_run`: it should have been done, but you skipped it. Give `reason`.

`carried_over` (reusing an earlier round) is written by the machine for viewpoints that did not run. You ran, so write what you found in this run; an answer that says `carried_over` is rejected.
