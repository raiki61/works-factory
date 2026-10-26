"""workflows/.shared/writerblock.py（書き手の型の block 6 つの 2 本の script の本体。docs/plans/2026-10-24-fix-weapons.md の 11.10 の 1・
11.6 の D1 の縛る試験の 1 の (v) と本体の照らし）: 型が足す値と段落・表の定数の欠け・注文の型の食い違い・返答の書き出し。

block の組の試験（筋書きで指示が組める・返答の pointer・下請けの段落の真偽。tests/blocks/kit.py の WriterBlockCase）は block ごとの薄い試験が
継ぐ。ここは 1 度だけ照らす本体の事を見る。型の block は一時の pack の block `weapon-demo` で、md は slots の全部の鍵を差し込む。
"""
import contextlib
import io
import json
import os
import pathlib
import sys
import types
import unittest
from unittest import mock

from tests.bin import hermetic
from tests.blocks import kit
from tests.workflows.test_returns_never_fail import load, misfits, return_node

sys.dont_write_bytecode = True
sys.path.insert(0, str(kit.SHARED))
import ports  # noqa: E402
import prompt  # noqa: E402
import writerblock  # noqa: E402

SLOTS_SHAPE = json.loads((kit.SHARED / "schemas" / "writer-slots.schema.json").read_text(encoding="utf-8"))
VALUES = sorted(SLOTS_SHAPE["properties"]["values"]["properties"])
WHEN = sorted(SLOTS_SHAPE["properties"]["when"]["properties"])
OWNED_VALUES = ("first_prompt", "unattended", "overlay_file", "g1_items")
OWNED_WHEN = ("spawns", "g1", "ask_variant")
ORDER = {"weapon": "static", "group": "g1", "stage": 1, "since": "abc", "base": "", "units": [{"key": "u", "removes": [], "tests": []}],
         "scope": {"allowed_paths": ["a.py"], "out_of_scope": []}, "permits": []}


def table(**kw) -> types.SimpleNamespace:
    return types.SimpleNamespace(**{"ORDER_WEAPON": "static", "SPAWNS": False, "SUMMARY": False, **kw})


def slots(**when) -> dict:
    return {"values": {k: f"<{k}>" for k in VALUES}, "when": {**{k: False for k in WHEN}, **when}, "subagents": {}, "summary_file": ""}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = hermetic.tmpdir(self)
        self.block, self.art = tmp / "weapon-demo", tmp / "art"
        (self.block / "prompts").mkdir(parents=True)
        self.art.mkdir()
        self.write_md()
        self.enterContext(mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": "r1"}))
        self.enterContext(mock.patch.object(ports, "caller_block", return_value=self.block))

    def write_md(self, owned_values=OWNED_VALUES, extra=()):
        """slots の全部の鍵と型が足す名を差し込む md（値は {名}、段落は <!-- if 名 --> の 1 行）"""
        names = [*VALUES, *owned_values, *extra]
        body = "\n".join(f"{{{k}}}" for k in names) + "\n" + "\n".join(f"<!-- if {k} -->\n{k}\n<!-- end {k} -->" for k in [*WHEN, *OWNED_WHEN])
        (self.block / "prompts" / "demo.md").write_text(body + "\n", encoding="utf-8")

    def prep(self, tbl, given=None, order=None):
        env = {"INPUTS_ORDER": json.dumps(order or ORDER), "INPUTS_SLOTS": json.dumps(given or slots())}
        seen = {}
        real = prompt.emit

        def wrapped(node, values, when, n):
            seen.update(node=node, values=values, when=when, n=n)
            return real(node, values, when, n)
        with mock.patch.dict(os.environ, env), mock.patch.object(prompt, "emit", wraps=wrapped), contextlib.redirect_stdout(io.StringIO()) as out:
            got = writerblock.prep(tbl)
        self.assertEqual(json.loads(out.getvalue()), got, "返りを標準出力にも書く")
        return got, seen


class PrepCase(Base):
    def test_prep_adds_the_values_and_the_paragraphs_the_type_owns(self):
        got, seen = self.prep(table())
        self.assertEqual((seen["node"], seen["n"]), ("demo", 1))
        self.assertEqual(sorted(seen["values"]), sorted([*VALUES, *OWNED_VALUES]))
        self.assertEqual(sorted(seen["when"]), sorted([*WHEN, *OWNED_WHEN]))
        v = seen["values"]
        self.assertEqual(v["first_prompt"], str(self.art / "demo-prompt-1.md"))
        self.assertTrue(v["unattended"] and not v["unattended"].endswith("\n"))
        self.assertTrue(v["overlay_file"].endswith("lib/borrow/unattended.md"), v["overlay_file"])
        self.assertEqual(v["g1_items"], "")
        self.assertEqual({k: seen["when"][k] for k in OWNED_WHEN}, {"spawns": False, "g1": False, "ask_variant": False})
        self.assertEqual(got["prompt"], (self.art / "demo-prompt-1.md").read_text(encoding="utf-8"))
        self.assertNotIn("summary_file", v, "SUMMARY が偽の型は輪の要約の値を足さない")

    def test_the_paragraphs_of_a_type_that_starts_subagents_follow_the_table(self):
        self.assertEqual(writerblock.paragraphs(table(SPAWNS=True)), {"spawns": True, "g1": True, "ask_variant": True})
        self.assertEqual(writerblock.paragraphs(table(SPAWNS=False)), {"spawns": False, "g1": False, "ask_variant": False})
        _, seen = self.prep(table(SPAWNS=True), slots(ask=True))
        self.assertEqual({k: seen["when"][k] for k in OWNED_WHEN}, {"spawns": True, "g1": False, "ask_variant": True},
                         "D1 は下請けの項目が無いので g1 は偽。ask_variant は相談の節が入る周だけ")
        _, seen = self.prep(table(SPAWNS=True), slots(ask=False))
        self.assertFalse(seen["when"]["ask_variant"])
        self.assertTrue(seen["when"]["spawns"])

    def test_a_continuing_round_leaves_the_borrowed_values_empty(self):
        """範囲の相談の答えの後・はみ出しを相談に積んだ周は続きの段落だけ（今の writer_values の早い返りと同じく、座の値は空で、写しの固定も照らさない）"""
        for name in writerblock.CONTINUING:
            with self.subTest(name=name), mock.patch.object(writerblock.seat, "pinned", side_effect=AssertionError("照らさない")):
                _, seen = self.prep(table(), slots(**{name: True}))
                self.assertEqual((seen["values"]["unattended"], seen["values"]["overlay_file"]), ("", ""))
                self.assertTrue(seen["values"]["first_prompt"])

    def test_a_borrowed_copy_that_does_not_match_the_pin_stops_the_prep(self):
        with mock.patch.object(writerblock.seat, "pinned", side_effect=ValueError("写しが固定と合わない")):
            with self.assertRaisesRegex(ValueError, "修正役の座を組めない: 写しが固定と合わない"):
                self.prep(table())

    def test_the_summary_file_is_added_only_for_a_type_that_takes_the_summary(self):
        self.write_md(OWNED_VALUES, ("summary_file",))
        _, seen = self.prep(table(SUMMARY=True))
        self.assertEqual(seen["values"]["summary_file"], "(empty)")
        given = slots()
        given["summary_file"] = "/p/summary.json"
        _, seen = self.prep(table(SUMMARY=True), given)
        self.assertEqual(seen["values"]["summary_file"], "/p/summary.json")

    def test_a_continuing_round_leaves_the_summary_file_empty(self):
        """続きの周（範囲の相談の答えの後・はみ出しを相談に積んだ周）は輪の要約も組まない（今の writer_values の早い返りは summary_file を
        組まず空のまま。割る前と割った後を比べる test_writer_prompts_kept の (d) が見つけた違い）"""
        self.write_md(OWNED_VALUES, ("summary_file",))
        for name in writerblock.CONTINUING:
            with self.subTest(name=name):
                given = slots(**{name: True})
                given["summary_file"] = "/p/summary.json"
                _, seen = self.prep(table(SUMMARY=True), given)
                self.assertEqual(seen["values"]["summary_file"], "")

    def test_the_second_round_numbers_the_prompt_after_the_first(self):
        self.prep(table())
        got, seen = self.prep(table())
        self.assertEqual(seen["n"], 2)
        self.assertTrue((self.art / "demo-prompt-2.md").is_file())
        self.assertEqual(seen["values"]["first_prompt"], str(self.art / "demo-prompt-1.md"), "続きの周は 1 回目の指示を指す")

    def test_the_order_of_another_type_stops_the_prep(self):
        """(ii) order.weapon が表の ORDER_WEAPON と違えば落ちる"""
        with self.assertRaisesRegex(ValueError, "注文の型は 'static'.*'pin'"):
            self.prep(table(), order={**ORDER, "weapon": "pin"})

    def test_a_slots_value_that_leaves_out_a_key_stops_the_prep(self):
        given = slots()
        del given["values"]["rejection"]
        with self.assertRaisesRegex(ValueError, "rejection"):
            self.prep(table(), given)

    def test_the_folder_of_the_block_names_the_type(self):
        with mock.patch.object(ports, "caller_block", return_value=self.block.parent / "demo"):
            with self.assertRaisesRegex(ValueError, "weapon-<型>"):
                self.prep(table())


class TableCase(Base):
    """(v) 型が足す名が slots の名と重なれば落ちる・表の定数が欠ければ落ちる（本体で 1 度だけ照らす）"""

    def test_a_name_the_type_adds_must_not_be_in_slots(self):
        for kind, key, name in (("値", "values", "first_prompt"), ("値", "values", "g1_items"), ("段落", "when", "spawns"),
                                ("段落", "when", "g1"), ("段落", "when", "ask_variant")):
            with self.subTest(name=name):
                given = slots()
                given[key][name] = "x" if key == "values" else True
                with self.assertRaisesRegex(ValueError, f"足す{kind} \\['{name}'\\] が slots の{kind}の名と重なる"):
                    writerblock._added(table(), "demo", given, self.art)

    def test_the_summary_file_of_the_slots_values_would_clash_for_a_type_that_takes_it(self):
        given = slots()
        given["values"]["summary_file"] = "x"
        with self.assertRaisesRegex(ValueError, r"足す値 \['summary_file'\]"):
            writerblock._added(table(SUMMARY=True), "demo", given, self.art)

    def test_every_constant_of_the_table_is_required(self):
        for name in ("ORDER_WEAPON", "SPAWNS", "SUMMARY"):
            with self.subTest(name=name):
                tbl = table()
                delattr(tbl, name)
                with self.assertRaisesRegex(ValueError, f"表の定数 {name} が無い"):
                    self.prep(tbl)
        with self.assertRaisesRegex(ValueError, "表の定数 SPAWNS が無い"):
            writerblock.paragraphs(types.SimpleNamespace())

    def test_a_constant_of_the_wrong_kind_stops(self):
        for name, value in (("ORDER_WEAPON", True), ("SPAWNS", "yes"), ("SUMMARY", 1)):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, f"表の定数 {name} は"):
                self.prep(table(**{name: value}))


class SaveCase(Base):
    """<w>-save: 返答を本物の形 writer-reply に照らして place の reply-<n>.json に書き、{saved: true} を返す。形に合わなければ落ちる
    （その周の終わりに内の輪が落ちる。docs/plans/2026-10-24-fix-weapons.md の 11.3 の「落ちた周の守り」）"""
    REPLY = kit.fixture("weapon-static", "standalone")["static"]

    def save(self, reply):
        with mock.patch.dict(os.environ, {"INPUTS_REPLY": json.dumps(reply)}), contextlib.redirect_stdout(io.StringIO()) as stdout:
            got = writerblock.save()
        self.assertEqual(json.loads(stdout.getvalue()), got)
        return got

    def test_save_writes_the_reply_with_the_number_of_the_prompt_it_answers(self):
        (self.art / "demo-prompt-1.md").write_text("p1", encoding="utf-8")
        self.assertEqual(self.save(self.REPLY), {"saved": True})
        self.assertEqual(json.loads((self.art / "reply-1.json").read_text(encoding="utf-8")), self.REPLY)
        (self.art / "demo-prompt-2.md").write_text("p2", encoding="utf-8")
        self.save(self.REPLY)
        self.assertTrue((self.art / "reply-2.json").is_file())

    def test_a_round_whose_reply_is_missing_does_not_shift_the_next_pair(self):
        """AI の node が落ちて save が走らなかった周は reply- が欠けるだけで、次の周の対（prompt-2 と reply-2）はずれない"""
        for n in (1, 2):
            (self.art / f"demo-prompt-{n}.md").write_text("p", encoding="utf-8")
        self.save(self.REPLY)
        self.assertTrue((self.art / "reply-2.json").is_file())
        self.assertFalse((self.art / "reply-1.json").exists())

    def test_a_reply_that_does_not_hold_the_shape_stops_the_node(self):
        (self.art / "demo-prompt-1.md").write_text("p1", encoding="utf-8")
        for name, bad in (("空", {}), ("必須の欄が欠ける", {k: v for k, v in self.REPLY.items() if k != "fix_closure"}),
                          ("知らない欄", {**self.REPLY, "extra": 1}), ("precedent の条件に外れる",
                           {**self.REPLY, "changes": [{"unit_key": "u"}]})):
            with self.subTest(name), self.assertRaises(ValueError):
                self.save(bad)
        self.assertFalse((self.art / "reply-1.json").exists(), "形に合わない返答は書かない")


class OutCase(Base):
    """<w>-out（落ちない。縛る試験の 10）: 入力を持たず、place の <w>-prompt-<n>.md・reply-<n>.json・out-<n>.json を見て返す。どの場合も
    終了せずに返り、返りが型の block の返す節の output_format に合う（test_returns_never_fail.misfits で照らす）"""
    REPLY = SaveCase.REPLY
    SHAPE = return_node(load("weapon-static"))["output_format"]   # 返す節の形（6 つの YAML で同じ字。縛る試験の 2 の (b)）

    def out(self) -> dict:
        os.environ.pop("INPUTS_REPLY", None)
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            writerblock.out()
        got = json.loads(stdout.getvalue())
        self.assertEqual(misfits(got, self.SHAPE), [])
        return got

    def put(self, *names):
        for name in names:
            (self.art / name).write_text(json.dumps(self.REPLY) if name.startswith("reply-") else "p", encoding="utf-8")

    def assert_failed(self, got: dict, said: str):
        self.assertEqual((got["ok"], got["reply"]), (False, None))
        self.assertIn(said, got["reason"])
        self.assertEqual(got["report"], [got["reason"]])

    def test_a_saved_reply_is_returned_by_pointer(self):
        """(a) save の後は ok: true で、pointer の先が在って空でない。返りは out-<n>.json にも書く"""
        self.put("demo-prompt-1.md", "reply-1.json")
        got = self.out()
        self.assertEqual(got, {"ok": True, "reason": "", "report": [],
                               "reply": {"type": "archon_artifact", "run_id": "r1", "path": "reply-1.json"}})
        self.assertGreater((self.art / got["reply"]["path"]).stat().st_size, 0, "pointer の先が在って空でない")
        self.assertEqual(json.loads((self.art / "out-1.json").read_text(encoding="utf-8")), got)

    def test_a_round_without_a_reply_returns_not_ok(self):
        """(b) reply-<n>.json が無い（AI の node か save が落ちた周）と ok: false・reply: null"""
        self.put("demo-prompt-1.md")
        self.assert_failed(self.out(), "書き手の返答が無い")

    def test_a_round_whose_prep_failed_does_not_return_the_reply_of_the_round_before(self):
        """(c) 前の周の reply-<n>.json と out-<n>.json が在り、この周の <w>-prompt-<n+1>.md が無い（prep が落ちた周）と ok: false。
        前の周の out-<n>.json の中身を変えない（prep が落ちた周の <n> は前の周の番号）"""
        self.put("demo-prompt-1.md", "reply-1.json")
        self.assertTrue(self.out()["ok"])
        kept = (self.art / "out-1.json").read_text(encoding="utf-8")
        self.assert_failed(self.out(), "demo-prep が落ちた")
        self.assertEqual((self.art / "out-1.json").read_text(encoding="utf-8"), kept)

    def test_a_first_round_whose_prep_failed_returns_not_ok(self):
        """(d) 1 周目に prep が落ちた（<w>-prompt-1.md も無い）と ok: false"""
        self.assert_failed(self.out(), "demo-prep が落ちた")

    def test_a_failure_inside_the_node_falls_back_to_not_ok(self):
        """(e) compute の中で落ちる（out-<n>.json の書き出し）と fallback で ok: false。out-<n>.json は書かない"""
        self.put("demo-prompt-1.md", "reply-1.json")
        with mock.patch.object(pathlib.Path, "write_text", side_effect=OSError("書けない")):
            got = self.out()
        self.assert_failed(got, "書けない")
        self.assertFalse((self.art / "out-1.json").exists())


if __name__ == "__main__":
    unittest.main()
