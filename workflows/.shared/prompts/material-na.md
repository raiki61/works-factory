<!-- if na_never -->
This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. Write what you saw as `found` or `clean`; if you could not check, write `not_run` with the reason.
<!-- end na_never -->
<!-- if na_cond_true -->
The condition of this viewpoint holds for this run ({na_why}), so the acceptance step rejects `not_applicable`. Write what you saw as `found` or `clean`; if you could not check, write `not_run` with the reason.
<!-- end na_cond_true -->
<!-- if na_cond_false -->
The condition of this viewpoint does not hold for this run ({na_why}). You may write `not_applicable`, with the reason in `reason`.
<!-- end na_cond_false -->
<!-- if na_judged -->
The condition of this viewpoint holds for this run ({na_why}), but none of the facts the machine holds raise it, so the acceptance step takes your judgment. If you read the diff and judge that the viewpoint does not apply, you may write `not_applicable`, with the reason in `reason`.
<!-- end na_judged -->
