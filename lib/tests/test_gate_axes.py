"""修正前の関所の 4 つの軸を軸ごとに分ける（gate_axes）。軸ごとの訳が今の works の gatemarks.axes と同じ部品から出て、全部の軸が
ok の時だけ gatemarks.axes が空になる（2 か所が食い違えば赤）。場面は今の works の tests/test_plan_gate.py の FourAxesCase と、
軸ごとの欄（undecided_because・fences・汚れる行への答えの欠け）。見え方は boardview.view（盤面・git・子のプロセスなし）"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
from lib.tests import test_plan_gate as TP  # noqa: E402
import boardview  # noqa: E402
import gate_axes  # noqa: E402
import gatemarks  # noqa: E402
import planmarks  # noqa: E402
import startrec  # noqa: E402
import structmark  # noqa: E402
import worldmark  # noqa: E402


class AxesBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name).resolve()

    def view(self, narrows=(), faces=()):
        inputs = {"plan": {"plan": [{"unit_keys": ["u"], "narrows": list(narrows)}]}, "cwd": str(self.tmp)}
        return boardview.view(self.tmp, inputs, {"faces": list(faces)})

    def put_rows(self, *rows):
        """構造の目の行（元 FourAxesCase.put_rows）"""
        design = self.tmp / "design.jsonl"
        design.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        structmark.write(self.tmp, status="ok", reason="", design_file=str(design), wall_s=0)

    def check(self, mark, units=("u",), **view):
        """(軸ごとの {ok, note}, gatemarks.axes の訳)。2 か所が食い違えば赤"""
        b = self.view(**view)
        got = gate_axes.split(b, mark, list(units))
        old = gatemarks.axes(b, mark, list(units))
        self.assertEqual(set(got), set(gate_axes.AXES))
        self.assertEqual(all(a["ok"] for a in got.values()), not old, (got, old))
        return got, old

    def bad(self, got) -> list:
        return sorted(a for a, v in got.items() if not v["ok"])


class SplitCase(AxesBase):
    def test_decided_url_is_all_ok(self):
        """元 FourAxesCase.test_decided_by_url_passes"""
        got, old = self.check(TP.DECIDED)
        self.assertEqual(old, [])
        self.assertEqual(got, {a: {"ok": True, "note": ""} for a in gate_axes.AXES})

    def test_no_decided_by_is_not_obvious(self):
        got, _ = self.check({**TP.DECIDED, "decided_by": ""})
        self.assertEqual(self.bad(got), ["obvious"])
        self.assertIn(gate_axes.NOT_DECIDED, got["obvious"]["note"])

    def test_undecided_because_is_not_obvious(self):
        got, _ = self.check({**TP.DECIDED, "undecided_because": "世界の解が 2 つに割れる"})
        self.assertEqual(self.bad(got), ["obvious"])

    def test_decided_by_must_exist(self):
        """元 FourAxesCase.test_decided_by_must_exist: 現物に無い出どころは自明でない"""
        got, old = self.check({**TP.DECIDED, "decided_by": "docs/adr/0099-nope.md:3 の決め"})
        self.assertIn("obvious", self.bad(got))
        self.assertIn("決め手の出どころが現物に無い", got["obvious"]["note"])
        self.assertTrue(old)

    def test_decided_by_file_line_passes(self):
        """元 FourAxesCase.test_decided_by_file_line_passes"""
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0002-keep.md").write_text("# 決め\n\n空の列は例外のまま\n", encoding="utf-8")
        got, old = self.check({**TP.DECIDED, "decided_by": "docs/0002-keep.md:3（人の前の決定）"})
        self.assertEqual((self.bad(got), old), ([], []))

    def test_request_quote_must_be_in_request(self):
        """元 FourAxesCase.test_request_quote_must_be_in_request"""
        req = self.tmp / "request.json"
        req.write_text(json.dumps({"findings": [{"where": "stats.py", "text": "空の列の mean は今までどおり例外でよい"}]},
                                  ensure_ascii=False), encoding="utf-8")
        startrec.path(self.tmp).parent.mkdir(parents=True, exist_ok=True)
        startrec.path(self.tmp).write_text(json.dumps({"request_file": str(req)}), encoding="utf-8")
        got, _ = self.check({**TP.DECIDED, "decided_by": "依頼の本文「空の列の mean は今までどおり例外でよい」"})
        self.assertEqual(self.bad(got), [])
        got, _ = self.check({**TP.DECIDED, "decided_by": "依頼の本文「空の列は 0 を返す」"})
        self.assertEqual(self.bad(got), ["obvious"])
        self.assertIn("依頼の文に無い", got["obvious"]["note"])

    def test_no_world_is_not_world(self):
        """元 FourAxesCase.test_no_world_asks: 世界の解の行の無い run で world も URL の決め手も無い"""
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        got, _ = self.check({**TP.DECIDED, "decided_by": "keep.md:1", "world": ""})
        self.assertEqual(self.bad(got), ["world"])
        self.assertEqual(got["world"]["note"], gate_axes.NO_WORLD)

    def test_world_rows_take_the_axis_off_the_row(self):
        """世界の解の段の行の在る run は、行の world が空でもこの軸で見ない（外れは world_items が聞く）"""
        wf = self.tmp / "world.jsonl"
        wf.write_text(json.dumps(TP.WORLD_ROW, ensure_ascii=False) + "\n", encoding="utf-8")
        worldmark.write(self.tmp, status="ok", reason="", world_file=str(wf), classes=1, dropped=0)
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        got, _ = self.check({**TP.DECIDED, "decided_by": "keep.md:1", "world": ""})
        self.assertEqual(self.bad(got), [])

    def test_route_up_unit_is_not_clean(self):
        """元 FourAxesCase.test_eye_route_up_becomes_gate_item の軸の側: 構造の目が人に上げた単位の行は汚くないが揃わない"""
        self.put_rows(TP.ROUTE_UP)
        got, _ = self.check(TP.DECIDED)
        self.assertEqual(self.bad(got), ["clean"])
        self.assertIn("構造の目が人に上げた単位（u）", got["clean"]["note"])

    def test_clean_route_rows_do_not_block(self):
        """元 FourAxesCase.test_clean_route_rows_do_not_block"""
        self.put_rows({**TP.ROUTE_UP, "route": "自分で決める", "route_reason": "決め手で決まる", "undecided_because": ""})
        got, old = self.check(TP.DECIDED)
        self.assertEqual((self.bad(got), old), ([], []))

    def test_dirty_unit_without_answer_is_not_clean(self):
        """汚れると見た単位に修正案の欄 structure の答えが無い行は汚くないが揃わない。答えが在れば揃う"""
        self.put_rows({**TP.ROUTE_UP, "route": "自分で決める", "route_reason": "決め手で決まる", "undecided_because": ""})
        planmarks.save(self.tmp, 1, [{"structure": []}])
        got, _ = self.check(TP.DECIDED)
        self.assertEqual(self.bad(got), ["clean"])
        self.assertIn("修正案の答えが無い", got["clean"]["note"])
        planmarks.save(self.tmp, 1, [{"structure": [{"row": "u", "follows": True}]}])
        got, _ = self.check(TP.DECIDED)
        self.assertEqual(self.bad(got), [])

    def test_fences_are_overkill(self):
        """柵の印が在る行はやりすぎでないが揃わない（決め手が在っても聞く）"""
        got, _ = self.check({**TP.DECIDED, "fences": ["external_write"]})
        self.assertEqual(self.bad(got), ["not_overkill"])
        self.assertIn("external_write", got["not_overkill"]["note"])

    def test_face_outside_plan_units_is_overkill(self):
        """元 FourAxesCase.test_face_outside_plan_units_asks"""
        got, _ = self.check(TP.DECIDED, units=("別の単位",))
        self.assertEqual(self.bad(got), ["not_overkill"])
        self.assertIn("修正案の単位の外を名指す（別の単位）", got["not_overkill"]["note"])


class GatherCase(AxesBase):
    def test_no_rows_is_all_ok(self):
        b = self.view()
        self.assertEqual(gate_axes.gather(b), {a: {"ok": True, "note": ""} for a in gate_axes.AXES})

    def test_rows_name_their_text(self):
        """関所の全部の行（修正案の narrows と事前審査の人に回す穴）を軸ごとに集め、訳に行の頭を添える"""
        b = self.view(narrows=[{**TP.NARROW, **TP.DECIDED, "fences": ["irreversible"]}],
                      faces=[{**TP.FACE, **TP.DECIDED, "unit_keys": ["別の単位"]}])
        got = gate_axes.gather(b)
        self.assertEqual(sorted(a for a, v in got.items() if not v["ok"]), ["not_overkill"])
        self.assertIn(TP.NARROW["what"], got["not_overkill"]["note"])
        self.assertIn(TP.FACE["key"], got["not_overkill"]["note"])

    def test_world_deviation_and_route_up_rows(self):
        """世界の解の外れ（world_items の揃わない行）は world、構造の目が人に上げた設計の問い（design_items）は clean に載る"""
        wf = self.tmp / "world.jsonl"
        wf.write_text(json.dumps(TP.WORLD_ROW, ensure_ascii=False) + "\n", encoding="utf-8")
        worldmark.write(self.tmp, status="ok", reason="", world_file=str(wf), classes=1, dropped=0)
        planmarks.save(self.tmp, 1, [{"structure": [{"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"}]}])
        self.put_rows(TP.ROUTE_UP)
        got = gate_axes.gather(self.view())
        self.assertFalse(got["world"]["ok"])
        self.assertIn("w-mean", got["world"]["note"])
        self.assertFalse(got["clean"]["ok"])
        self.assertIn(gatemarks.DESIGN_HEAD, got["clean"]["note"])

    def test_gather_agrees_with_the_gate(self):
        """全部の軸が ok の時だけ、関所の決め手の濾しに掛ける行が全部聞かずに通る"""
        for narrows in ([{**TP.NARROW, **TP.DECIDED}], [{**TP.NARROW, **TP.DECIDED, "undecided_because": "割れる"}],
                        [dict(TP.NARROW)]):
            with self.subTest(narrows=narrows):
                b = self.view(narrows=narrows)
                got = gate_axes.gather(b)
                self.assertEqual(all(a["ok"] for a in got.values()), not gatemarks.plan_gate_items(b))


if __name__ == "__main__":
    unittest.main()
