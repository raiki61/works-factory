## Test measurements and the origin of the cumulative diff (measured by the machine)

What follows is fact the machine measured, and it does not appear in the cumulative diff file. The base-to-final outcome of each test shows the tests that exist even where the diff changes no test. Red to green (赤→緑) is a test that fails on the code before the fix and passes after it: a test that prevents a regression already exists. Green to green (緑→緑) is a test that kept passing before and after the fix: if the fix does not change behaviour, it is evidence that the existing tests kept confirming that behaviour. Green to red (緑→赤) is a test the fix broke. If the origin is the PR's base and the cumulative diff is empty, it does not mean the body was left unfixed: the fix may have undone the PR's changes.

### Machine summary of all base-to-final test outcomes and the complete result file

The machine-generated lines immediately below give the counts and, when available, a line labelled `全件の結果ファイル` (complete result file) followed by an absolute path. That is the file to Read for individual test names and full failure messages; it contains all comparison rows in their original order. The counts include every compared test, without truncation. Read only the details needed to evaluate whether a regression test is missing, whether existing tests confirmed unchanged behaviour, or whether the fix introduced a failure. Do not load or repeat the entire listing by default. If no file path is listed, or the lines say the comparison was not measured, do not infer individual test outcomes. A skipped test, a test absent on one side, and an unmeasured comparison are different facts. An absent base result under a narrowed baseline does not establish a newly introduced failure. Unclassified failures and unreadable evidence are not passing results.

{outcomes}

### TDD loop records (per fix stage; units whose red-to-green was confirmed come with the names of their tests)

{tdd_records}

### Origin of the cumulative diff

{origin}
