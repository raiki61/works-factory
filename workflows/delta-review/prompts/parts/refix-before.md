<!-- if policy -->
Human policy document: `{policy_path}` (read it all first).
<!-- end policy -->
<!-- if not policy -->
Human policy document: none.
<!-- end policy -->

<!-- if request -->
Request file: `{request_file}` (read it all first).
<!-- end request -->
<!-- if not request -->
Request file: none.
<!-- end request -->

<!-- if scope -->
## Paths you may change and things you must not touch (the acceptance checks against these values)

The acceptance check compares the paths you change with these values and rejects what falls outside. `out_of_scope` is stronger than the scope and beats a permitted path too. The `out_of_scope` of every item applies to every path you change (only a path lifted from an item's `out_of_scope` by a scope consultation does not apply under that item). The paths a scope consultation allowed and the permits for tests are included here too.

{scope_items}
- Permits for every item (test-change permits and paths added by fix rulings; they do not beat out_of_scope): {scope_permits}
<!-- end scope -->
