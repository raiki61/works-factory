"""直す義務の集合を、同じ見本の値で、それぞれ消費する所の入口から作って突き合わせる（盤面・子のプロセスなし）。

集合: 修正役への約束（fixrules.owed_values が指示書に埋める値）・受け付けが通す単位（fixboard.fix_duty。元は受け付けの script の
fix_unit_keys）・TDD の振り分けの義務（tddloop.start が作る st を _owed で読む）・片付け後の確かめの免除
（fixboard.nothing_owed_but_excused。元は assert_changed.nothing_owed）・事後の関門が見る項目（fixgates.problems が義務の外の
項目を OUT_OF_DUTY で飛ばす）。正本は fixboard.fix_duty で、この試験は各入口が返した物だけを比べる（入口が自前の式に替われば赤）。

見本は test_fix_duty の物（開いた単位・答え待ちの fork の出どころ・escalate の出どころ・ask_human の単位・関所で答えて戻した単位）を
値で渡す。元 works/tests/test_duty_sets.py の報告の側（report.head3・gatemarks.held_lines と KNOWN_DIFF）は盤面の部品なので外した。
"""
import json
import pathlib
import sys
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from lib.tests import test_fix_duty as fd  # noqa: E402
from lib.tests.test_fix_duty import ASKED_UNIT, BACK_UNIT, ESC_UNIT, FORK_UNIT, OTHER_UNIT  # noqa: E402
import fixboard  # noqa: E402
import fixgates  # noqa: E402
import fixrules  # noqa: E402
import planmarks  # noqa: E402
import tddloop  # noqa: E402

IS_OPEN = [FORK_UNIT, OTHER_UNIT, ESC_UNIT, ASKED_UNIT]   # 判定の出口の is_open の並び（関所で諮った BACK_UNIT は無い）


class DutySets(fd.DutyCase):
    def kw(self):
        return {"withheld_by": fd.WITHHELD_BY, "returned": fd.RETURNED}

    # ---- 集合を、消費する所の入口から作る
    def promised(self) -> set:
        got = fixrules.owed_values(self.tmp, {"open_units": json.dumps(IS_OPEN, ensure_ascii=False)}, owed=fd.OWED, **self.kw())
        return set(json.loads(got["open_units"]))

    def accepted(self) -> tuple:
        owed, excused = fixboard.fix_duty(self.tmp, fd.OWED, **self.kw())
        return set(owed), dict(excused)

    def tdd_owed(self) -> tuple:
        suite = self.tmp / "suite.py"
        suite.write_text("", encoding="utf-8")
        with mock.patch.object(tddloop, "run_suite", return_value=([], 0, [])), \
                mock.patch.object(tddloop, "snapshot", return_value=""):
            got = tddloop.start(self.tmp, self.tmp, str(suite), json.dumps(IS_OPEN, ensure_ascii=False), owed=fd.OWED,
                                **self.kw())
        self.assertTrue(got["go"], got)
        st = json.loads(pathlib.Path(got["state_file"]).read_text(encoding="utf-8"))
        return set(tddloop._owed(st)), set(st["excused"])

    def gated_items(self) -> set:
        """事後の関門が見る項目の単位: 単位ごとに 1 項目の tdd の欄を置き、OUT_OF_DUTY で飛ばさなかった項目の単位"""
        fields = [{"unit_keys": [k], "route": "tdd", "route_why": "", "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
                   "tests": [{"id": f"test_x.py::T::test_{n}", "behavior": "b", "path": "p", "red_kind": "assertion", "red_why": "w"}]}
                  for n, k in enumerate(fd.ALL_UNITS)]
        planmarks.save(self.tmp, 1, fields)
        tests, _ = fixgates._accept_tests(self.tmp, fields, None, owed=fd.OWED, withheld=set(fd.WITHHELD_BY),
                                          returned=fd.RETURNED)
        return {k for t in tests for k in t["unit_keys"]}

    # ---- 関係
    def test_promise_and_acceptance_and_tdd_read_one_owed(self):
        owed, excused = self.accepted()
        self.assertEqual(owed, {OTHER_UNIT, BACK_UNIT}, "答えを返した単位は義務に残り、答え待ち・ask_human は外れる")
        self.assertEqual(self.promised(), owed, "約束の一覧 = 受け付けの義務（関所で答えて戻った単位を含み、外れた単位を含まない）")
        tdd_owed, tdd_excused = self.tdd_owed()
        self.assertEqual(tdd_owed, owed, "TDD の義務 = 受け付けの義務 − 食い違いで止めた単位（無し）")
        self.assertEqual(tdd_excused, set(excused), "TDD が外す単位 = 受け付けの外れた単位")
        self.assertEqual(owed & set(excused), set())

    def test_post_gates_check_the_owed_items(self):
        owed, _ = self.accepted()
        self.assertEqual(self.gated_items(), owed, "事後の関門が見る項目の単位 = 受け付けの義務")

    def test_nothing_owed_only_when_owed_is_empty_and_excused_is_not(self):
        self.assertEqual(fixboard.nothing_owed_but_excused(self.tmp, fd.OWED, **self.kw()), {}, "義務が残る置き場は空の申告を通さない")
        shrunk = fd.OWED - {OTHER_UNIT}
        owed, excused = fixboard.fix_duty(self.tmp, shrunk, withheld_by=fd.WITHHELD_BY, returned=())
        self.assertEqual((owed, bool(excused)), (set(), True))
        self.assertEqual(fixboard.nothing_owed_but_excused(self.tmp, shrunk, withheld_by=fd.WITHHELD_BY, returned=()), excused,
                         "義務が空で外れた単位が在る時だけ通し、外れた単位を並べる")


if __name__ == "__main__":
    unittest.main()
