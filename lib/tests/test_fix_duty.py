"""直す義務と、そこから外れた単位の正本（fixboard.fix_duty。元 conflict.fix_duty）と、最後の回の拒否の行の結び（parking.settle）。

- fix_duty: 答え待ちの fork・escalate の出どころ・ask_human の単位・関所で答えて戻した単位を混ぜた見本で、owed と excused は
  互いに素で、合わせて修正役が書いてよい単位（開いた単位と関所で答えて戻した単位）を覆い、excused は問いの key・裁定の id を理由に持つ。
  元は盤面（test_plan_gate の GateBase）の写しの規則と問いの台帳を読んだ。ここでは同じ見本を値（owed・withheld_by・returned）と
  置き場の conflicts.json で渡す（元 works/tests/test_fix_duty.py の TestFixDuty の場合を写した）
- parking.settle の declared: 文照合を使わず declared の単位に結ぶ（元 TestAcceptReadsDuty の場合。受け付けの script を通さず
  lib の parking を直に呼ぶ）
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import conflict  # noqa: E402
import fixboard  # noqa: E402
import parking  # noqa: E402

# 元 works/tests/test_plan_gate.py の見本の単位と問い（盤面の GateBase は使わない）
FORK_UNIT = "stats.py mean: 空の列の扱いが決まらない"
OTHER_UNIT = "stats.py clamp: 上限を超えた値に lo を返す"
FORK = {"key": "q-empty-mean", "kind": "fork", "status": "held", "origin": FORK_UNIT, "options": ["例外", "0 を返す"],
        "reason": "推し: 例外"}
ESC_UNIT = "stats.py median: 偶数の長さの中央値が決まらない"
ASKED_UNIT = "stats.py clamp: 下限と上限が逆の時の扱い"
BACK_UNIT = "stats.py mode: 同数の時の選び方"
ESC = {"key": "q-median", "kind": "stuck", "status": "escalate", "origin": ESC_UNIT, "reason": "推し: 平均を返す"}
BACK = {**FORK, "key": "q-mode", "origin": BACK_UNIT}
ALL_UNITS = [FORK_UNIT, OTHER_UNIT, ESC_UNIT, ASKED_UNIT, BACK_UNIT]
# 元の盤面の値: 写しの規則の直す義務（開いた単位から、人に諮っている fork の出どころ BACK_UNIT を除く）、答えていない問い
# （fork と escalate の出どころ）、関所で人が答えた問いの出どころ
OWED = {FORK_UNIT, OTHER_UNIT, ESC_UNIT, ASKED_UNIT}
WITHHELD_BY = {FORK_UNIT: FORK, ESC_UNIT: ESC}
RETURNED = {BACK_UNIT}


def put_rulings(place: pathlib.Path) -> None:
    """ASKED_UNIT に ask_human の裁定の行を置く（置き場の conflicts.json）"""
    (place / conflict.FILE).write_text(json.dumps({"items": [
        {"id": "c1-1", "unit_key": ASKED_UNIT, "ruling": {"decision": conflict.ASK}}]}), encoding="utf-8")


class DutyCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-duty-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        put_rulings(self.tmp)

    def duty(self, withheld_by=None):
        return fixboard.fix_duty(self.tmp, OWED, withheld_by=WITHHELD_BY if withheld_by is None else withheld_by,
                                 returned=RETURNED)


class TestFixDuty(DutyCase):
    def test_owed_and_excused_split_fixable_with_reasons(self):
        owed, excused = self.duty()
        self.assertEqual(owed, {OTHER_UNIT, BACK_UNIT}, "関所で答えて戻した単位は義務に残る")
        self.assertEqual(owed & set(excused), set())
        self.assertLessEqual(set(ALL_UNITS), owed | set(excused), "開いた単位と戻した単位を覆う")
        self.assertIn(FORK["key"], excused[FORK_UNIT])
        self.assertIn(ESC["key"], excused[ESC_UNIT])
        self.assertIn("ask_human の裁定 c1-1", excused[ASKED_UNIT])
        self.assertEqual(fixboard.nothing_owed_but_excused(self.tmp, OWED, withheld_by=WITHHELD_BY, returned=RETURNED), {},
                         "義務が残る置き場は空の changes を通さない")

    def test_excused_reason_reads_withheld_by_not_a_copy(self):
        _, excused = self.duty(withheld_by={FORK_UNIT: ESC})
        self.assertIn(ESC["key"], excused[FORK_UNIT])
        self.assertNotIn(ESC_UNIT, excused)

    def test_unreadable_conflicts_keep_asked_unit_owed(self):
        (self.tmp / conflict.FILE).write_text("{", encoding="utf-8")
        owed, excused = self.duty()
        self.assertIn(ASKED_UNIT, owed, "控えが読めなければ ask_human を義務から外さない")
        self.assertNotIn(ASKED_UNIT, excused)


class TestDeclaredBinding(unittest.TestCase):
    def test_declared_keys_bind_without_text_matching(self):
        """declared の文は文照合を使わず declared の単位に結ぶ（別の単位の足跡のパスを名指しても）。declared に無い文は今の bind"""
        import inspect
        self.assertIn("declared", inspect.signature(parking.settle).parameters)
        A, B = "a.py f: 直す", "b.py g: 直す"
        feet = {A: {"a.py"}, B: {"b.py"}}
        base = dict(keys={A, B}, feet=feet, reached={}, owed={A, B}, out_of_duty=set(), changed=set())
        declared_text = "食い違い[0]: 名指し 'b.py:99' の行がファイルに無い"
        by_path = "b.py を直した行の拒否"
        nothing = "どの単位も名指さない行"
        got = parking.settle([declared_text], declared={declared_text: {A}}, **base)
        self.assertEqual(sorted(got.park), [A], got)
        self.assertEqual(got.unbound, {})
        self.assertEqual(got.how, {declared_text: "declared"})
        got = parking.settle([declared_text, by_path], declared={declared_text: {A}}, **base)
        self.assertEqual(sorted(got.park), [A, B], got)
        self.assertEqual(got.how, {declared_text: "declared", by_path: "text"})
        got = parking.settle([nothing], declared={declared_text: {A}}, **base)
        self.assertEqual(sorted(got.park), [A, B], "declared に無い文は結べず義務の全部")
        self.assertEqual(got.how, {nothing: "unbound"})
        self.assertEqual(list(got.unbound), [nothing])


if __name__ == "__main__":
    unittest.main()
