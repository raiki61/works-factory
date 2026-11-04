## Test measurements and the origin of the cumulative diff (measured by the machine)

What follows is fact the machine measured, and it does not appear in the cumulative diff file. The base-to-final outcome of each test shows the tests that exist even where the diff changes no test. Base is the code before the fix and the end (final) is the code after it. Red to green (赤→緑) is a test that fails on the code before the fix and passes after it: a test that prevents a regression already exists. Green to green (緑→緑) is a test that kept passing before and after the fix: if the fix does not change behaviour, it is evidence that the existing tests kept confirming that behaviour. Green to red (緑→赤) is a test the fix broke. Red to red (赤→赤) is a test that fails both before and after the fix. Skipped to skipped (飛ばし→飛ばし) is a test that was skipped both before and after the fix. The origin is the commit the cumulative diff starts from (shown under "Origin of the cumulative diff" below). If the origin is the PR's base and the cumulative diff has no lines, it does not mean the code was left unfixed: the fix may have undone the PR's changes.

### Each test's outcome at base and at the end (what the test gate measured for each test at base and at the end, grouped by transition)

Every test whose outcome changed and every red-to-red test is named. For tests whose outcome did not change and is not red (green to green, skipped to skipped), only these are named: tests in the test files the change reaches, and tests named in the TDD loop records. To find the test files the change reaches, the machine starts from the files the cumulative diff changed and follows the files that import or mention them, at any depth; this is the map of the change. The rest are given only as a count ("ほかに N 件は名を貼っていない"). When the map could not decide which tests the change touches, every test is named. Below, each transition comes as one line with its count, followed by the names of its tests (a red side comes with its outcome and failure message).

{outcomes}

### TDD loop records (per fix stage; units whose red-to-green was confirmed come with the names of their tests)

{tdd_records}

### Origin of the cumulative diff

{origin}
