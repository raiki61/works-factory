"""裁定の文のファイル（src/rulings.py。修正役が Read する）: 約束の文は prompts/parts/ruling-promise.md が持ち、約束は裁定と案の直しの
状態で選ばれる。lib/conflict は裁定の行の読み書きだけを持ち、指示の文を持たない。

- 約束の選び: 裁定ごとの約束・案を直した行・諦めた行・2 回目の修正の段で待つ行・組どうしの合わせの申し出
- 申し出の回の返答の段落（prompts/parts/ruling-previous-reply.md）
- 作り直した後にまた止まった単位の積み（park）: 裁定に回さず ask_human で積み、裁定の文のファイルを書き直す（それ以外は書き直さない）
"""
import json
import pathlib
import shutil
import tempfile
import unittest

from tests.blocks import kit

rulings = kit.load("fix", "rulings")
import conflict  # noqa: E402  （lib。kit.load の後に届く）
import stopby  # noqa: E402

MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"


def place_with_rows(rows):
    """申し出の行 rows を置いた置き場（一時。モジュールの終わりに消す）"""
    root = pathlib.Path(tempfile.mkdtemp())
    unittest.addModuleCleanup(shutil.rmtree, root, ignore_errors=True)
    (root / conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")
    return root


def row(rid, key, decision, *, state=None, text="受け入れのテストの赤の種類を exception に直す", plan_units=(), source="fix"):
    """申し出の行 1 つ（state は欄 replan の値で、None なら欄を置かない）"""
    out = {"id": rid, "round": 1, "source": source, "unit_key": key, "between": ["stats.py:3", "test_stats.py:2"],
           "why_both_cannot_hold": "テストは上限 hi を期待し、今のコードは lo を返す——両方は成り立たない",
           "which_is_right": "request", "kind": "brief_vs_judgment", "status": "ruled",
           "ruling": {"decision": decision, "text": text, "limits": [], "by": "t",
                      **({"plan_items": [1], "plan_units": list(plan_units)} if plan_units else {})}}
    if state is not None:
        out["replan"] = state
    return out


def written(b) -> str:
    return rulings.write(b).read_text(encoding="utf-8")


def section(text, rid):
    return text.split(f"## {rid}:", 1)[1].split("\n## ", 1)[0]


def claim(key, source):
    """TDD の輪の状態の未送の行 {source, item}（item は申し出の中身）"""
    return {"source": source, "item": {"unit_key": key, "between": ["stats.py:3", "test_stats.py:2"],
                                        "why_both_cannot_hold": "直した案でも確認が上限まで落ちた", "which_is_right": "unknown",
                                        "kind": "needs_context"}}


class ParkCase(unittest.TestCase):
    """rulings.park（輪の状態の未送の行を積み、裁定の文のファイルを書き直すかを決める 1 か所）。案を直して直す義務に戻った単位の
    諦めの行（機械が諦めた申し出）だけが、裁定に回らず ask_human で積まれ、裁定の文のファイルが書き直される"""
    SENTINEL = "前に書いた裁定の文\n"

    def place(self, *rows):
        b = place_with_rows(list(rows))
        (b / conflict.RULINGS_FILE).write_text(self.SENTINEL, encoding="utf-8")
        return b

    def amended(self):
        return row("c1-1", MEAN, "fix_plan_item", state="amended", plan_units=[MEAN])

    def test_repeat_gave_up_is_asked_to_human_and_rewrites_the_rulings_file(self):
        b = self.place(self.amended())
        rulings.park(b, [claim(MEAN, conflict.GAVE_UP_SOURCE)])
        new = [r for r in conflict.items(b) if r["id"] != "c1-1"]
        self.assertEqual([(r["ruling"]["decision"], r["ruling"]["by"]) for r in new], [(conflict.ASK, stopby.TDD_REPEAT)])
        text = (b / conflict.RULINGS_FILE).read_text(encoding="utf-8")
        self.assertNotEqual(text, self.SENTINEL)
        self.assertIn(f"## {new[0]['id']}: {MEAN}", text)

    def test_first_gave_up_is_parked_without_ruling_and_leaves_the_file(self):
        b = self.place()
        rulings.park(b, [claim(MEAN, conflict.GAVE_UP_SOURCE)])
        self.assertEqual([r.get("ruling") for r in conflict.items(b)], [None])
        self.assertEqual((b / conflict.RULINGS_FILE).read_text(encoding="utf-8"), self.SENTINEL)

    def test_other_source_of_an_amended_unit_leaves_the_file(self):
        b = self.place(self.amended())
        rulings.park(b, [claim(MEAN, conflict.FIX_SOURCE)])
        self.assertEqual((b / conflict.RULINGS_FILE).read_text(encoding="utf-8"), self.SENTINEL)

    def test_gave_up_of_another_unit_leaves_the_file(self):
        b = self.place(self.amended())
        rulings.park(b, [claim(CLAMP, conflict.GAVE_UP_SOURCE)])
        self.assertEqual((b / conflict.RULINGS_FILE).read_text(encoding="utf-8"), self.SENTINEL)


class PromiseCase(unittest.TestCase):
    def test_kind_of_a_row_without_kind_reads_as_none(self):
        legacy = row("c1-1", MEAN, "ask_human")
        legacy.pop("kind")
        self.assertIn("申し出の種類: （無し）", written(place_with_rows([legacy])))

    def test_only_ruled_paths_widen(self):
        rows = [row(f"c1-{i}", MEAN, d) for i, d in enumerate(("fix_code_as", conflict.REPLACE), 1)]
        text = written(place_with_rows(rows))
        self.assertEqual(text.count("you may change only the paths listed under"), 2, text)

    def test_replan_promise_says_same_run(self):
        text = written(place_with_rows([row("c1-1", MEAN, "fix_plan_item", state="waiting", plan_units=[MEAN, CLAMP])]))
        self.assertIn("In this run the plan writer fixes only this item", text)
        self.assertIn("the second fix stage fixes it", text)

    def test_amended_row_returns_to_duty(self):
        text = written(place_with_rows([row("c1-1", MEAN, "fix_plan_item", state="amended", plan_units=[MEAN])]))
        self.assertIn("the plan was fixed in this same run and the unit owes a fix again", text)
        self.assertNotIn("the second fix stage fixes it", text)

    def test_gave_up_rows_promise_the_last_gate(self):
        """諦めた行は案の直しを約束しない。ask_human と同じく最後の人の関所で人が決め、諦めた理由を添える"""
        b = place_with_rows([row("c1-1", MEAN, "fix_plan_item", state="waiting", plan_units=[MEAN, CLAMP])])
        conflict.set_replan(b, ["c1-1"], conflict.GAVE_UP, why="修正案の役の直しが 3 回とも拒まれた: 数が違う")
        text = written(b)
        self.assertNotIn("the second fix stage fixes it", text)
        self.assertIn("a person decides at the last approval node", text)
        self.assertIn("修正案の役の直しが 3 回とも拒まれた: 数が違う", text)

    def test_second_pass_new_replan_rows_promise_the_last_gate(self):
        """2 回目の修正の段（案を直した行が在る）で新しく fix_plan_item と裁いた行（待つ行）は、修正の段を抜ける時に諦めた行になり
        最後の人の関所へ行くと言う。1 回目の段の待つ行は今どおり"""
        waiting = row("c2-1", MEAN, "fix_plan_item", state="waiting", plan_units=[MEAN])
        mine = section(written(place_with_rows([row("c1-1", CLAMP, "fix_plan_item", state="amended", plan_units=[CLAMP]), waiting])), "c2-1")
        self.assertNotIn("the second fix stage fixes it", mine)
        self.assertIn("this run's plan fix is already done", mine)
        first = section(written(place_with_rows([waiting])), "c2-1")
        self.assertIn("the second fix stage fixes it", first)

    def test_ask_human_promise_keeps_held_work_conditionally(self):
        """ask_human の約束は、直しが作業ツリーに在ればそのまま残す（戻すな・触るな。機械が戻した時は当て直すな）と条件の形で言う"""
        mine = section(written(place_with_rows([row("c1-1", MEAN, "ask_human")])), "c1-1")
        self.assertIn("If a fix for this unit is in the working tree, leave it as it is", mine)
        self.assertIn("do not apply it again", mine)
        self.assertIn("Do not write it in `changes`", mine)

    def test_clash_rows_are_fixed_by_the_joiner(self):
        text = written(place_with_rows([row("c1-1", MEAN, "fix_code_as", source=conflict.JOIN_SOURCE)]))
        self.assertIn("A ruling to fix, on a claim from the join between groups", text)

    def test_parked_note_excludes_every_unit_outside_duty(self):
        b = place_with_rows([row("c1-1", MEAN, "ask_human")])
        (b / conflict.PARKED_REPLY).write_text("{}", encoding="utf-8")
        text = written(b)
        self.assertIn(f"The reply from the round that raised the claim is at {b / conflict.PARKED_REPLY}", text)
        self.assertIn("Exclude every unit outside the units you owe a fix", text)
        self.assertIn("units accepted in the first fix stage", text)


if __name__ == "__main__":
    unittest.main()
