<!-- if policy_example -->
An example of how to write a hole of kind policy (made from the first row of this run's list that can be named; put one name from the list in `decided_by`, word for word):

{policy_example}
<!-- end policy_example -->
<!-- if not policy_example -->
No row can be named: do not raise holes of kind policy.
<!-- end policy_example -->
<!-- if doc_row -->
This run has a row of the policy document: raise `{policy_doc_fence}` in `fences` only when the hole rewrites a line of the policy document.
<!-- end doc_row -->
