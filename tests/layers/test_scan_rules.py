"""走査器の決まりの組と許可の一覧が、試験と計画と木に合う。"""
import pathlib
import re
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HERE = pathlib.Path(__file__).resolve().parent
# 土台の計画 docs/plans/2026-10-11-foundation.md の Task 2 の Produces が名指す決まりと、根の AGENTS.md の E18 の機械の行。
REQUIRED = {"E2", "E3", "E4", "E8", "E9", "E12", "E13", "E14", "E18"}
CALL = re.compile(r'scan\.problems\("(E\d+)"')


class ScanRulesTest(unittest.TestCase):
    def test_rules_scanned_tested_and_required_agree(self):
        tested = {rule for path in HERE.glob("test_*.py") for rule in CALL.findall(path.read_text(encoding="utf-8"))}
        self.assertEqual(set(scan.RULES), REQUIRED)
        self.assertEqual(tested, REQUIRED)

    def test_every_allowance_hits_the_real_tree(self):
        self.assertEqual(scan.stale_allowances(ROOT), [])

    def test_allowance_hitting_nothing_is_red(self):
        with tree({"lib/x.py": ""}) as root:
            got = scan.stale_allowances(root)
        self.assertEqual(len(got), sum(len(entries) for entries in scan.ALLOWED.values()), got)


if __name__ == "__main__":
    unittest.main()
