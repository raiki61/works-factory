## Test measurements and the origin of the cumulative diff (measured by the machine)

What follows is fact the machine measured, and it does not appear in the cumulative diff file. The base-to-final outcome of each test shows the tests that exist even where the diff changes no test. Red to green (赤→緑) is a test that fails on the code before the fix and passes after it: a test that prevents a regression already exists. Green to green (緑→緑) is a test that kept passing before and after the fix: if the fix does not change behaviour, it is evidence that the existing tests kept confirming that behaviour. Green to red (緑→赤) is a test the fix broke. If the origin is the PR's base and the cumulative diff is empty, it does not mean the body was left unfixed: the fix may have undone the PR's changes.

### Each test's outcome at base and at the end (what the test gate measured for each test at base and at the end, grouped by transition)

Every test whose outcome changed and every red-to-red test is named. For tests whose outcome did not change and is not red (green to green, skipped to skipped), only these are named: tests in the test files that the machine's map of the change reaches from the files the cumulative diff changed, and tests the TDD loop records name. The rest are given only as a count ("ほかに N 件は名を貼っていない"). When the map could not decide which tests the change touches, every test is named.

{outcomes}

### TDD loop records (per fix stage; units whose red-to-green was confirmed come with the names of their tests)

{tdd_records}

### Origin of the cumulative diff

{origin}
