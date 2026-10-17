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
        """(軸ごとの {ok, note}, gatemarks.axes の訳)。2 か所が食い違えば赤。決め手の欄が揃う行では、axes の訳が
        axis_reasons（軸の決まりの持ち主）を軸の順に並べた物と同じ"""
        b = self.view(**view)
        got = {axis: gate_axes._note(notes) for axis, notes in gatemarks.axis_reasons(b, mark, list(units)).items()}
        old = gatemarks.axes(b, mark, list(units))
        self.assertEqual(set(got), set(gate_axes.AXES))
        self.assertEqual(all(a["ok"] for a in got.values()), not old, (got, old))
        if gatemarks.decided(mark):
            reasons = gatemarks.axis_reasons(b, mark, list(units))
            self.assertEqual(old, [w for a in gatemarks.AXES for w in reasons[a]])
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
        self.assertIn(gatemarks.NOT_DECIDED, got["obvious"]["note"])

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
        self.assertEqual(got["world"]["note"], gatemarks.NO_WORLD)

    def test_world_rows_take_the_axis_off_the_row(self):
        """世界の解の段の行の在る run は、行の world が空でもこの軸で見ない（外れは world_items が聞く）"""
        wf = self.tmp / "world.jsonl"
        wf.write_text(json.dumps(TP.WORLD_ROW, ensure_ascii=False) + "\n", encoding="utf-8")
        worldmark.write(self.tmp, status="ok", reason="", world_file=str(wf), classes=1, dropped=0, name=worldmark.COPY_STATE)
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


class RunRootCase(AxesBase):
    """決め手の出どころに引いてよい作業ツリーの外の根は、依頼のファイルと run の置き場の根（盤面 plan-review/ の親）。
    場面は run f3a32503: 計画の役が定石から外れる訳に、run の置き場の plan/r1/brief-2.md:62（判定の処方の行）を挙げた"""

    def setUp(self):
        super().setUp()
        self.run_dir = self.tmp / "run"
        self.board = self.run_dir / boardview.FOLDER
        self.board.mkdir(parents=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.brief = self.run_dir / "plan" / "r1" / "brief-2.md"
        self.brief.parent.mkdir(parents=True)
        self.brief.write_text("前置き\n" * 61 + "判定の処方: 空の列は 0 を返す\n", encoding="utf-8")
        self.judgment = self.run_dir / "judge" / "judgment.json"
        self.judgment.parent.mkdir(parents=True)
        self.judgment.write_text("{\n \"units\": []\n}\n", encoding="utf-8")

    def view(self, narrows=(), faces=()):
        inputs = {"plan": {"plan": [{"unit_keys": ["u"], "narrows": list(narrows)}]}, "cwd": str(self.repo)}
        return boardview.view(self.board, inputs, {"faces": list(faces)})

    def deviate(self, deviation: str) -> list:
        """世界の解の外れ 1 行の揃わない訳（揃えば []）"""
        wf = self.board / "world.jsonl"
        wf.write_text(json.dumps(TP.WORLD_ROW, ensure_ascii=False) + "\n", encoding="utf-8")
        worldmark.write(self.board, status="ok", reason="", world_file=str(wf), classes=1, dropped=0, name=worldmark.COPY_STATE)
        planmarks.save(self.board, 1, [{"structure": [{"world": "w-mean", "deviation": deviation}]}])
        [(_, _, why)] = gatemarks.world_items(self.view())
        return why

    def test_absolute_run_file_is_a_source(self):
        self.assertEqual(self.deviate(f"判定の処方 {self.brief}:62 が 0 を返すと決めている"), [])
        got, _ = self.check({**TP.DECIDED, "decided_by": f"判定の処方 {self.judgment}:2 の単位の並び"})
        self.assertEqual(self.bad(got), [])

    def test_bare_name_is_still_asked(self):
        """相対の素の名は作業ツリーの根から引く（run の置き場で探し直さない）"""
        why = self.deviate("brief-2.md:62 の処方が 0 を返すと決めている")
        self.assertEqual(len(why), 1)
        self.assertIn("ファイルが無い", why[0])

    def test_outside_the_run_is_still_asked(self):
        other = self.tmp / "other.md"
        other.write_text("判定の処方\n", encoding="utf-8")
        got, _ = self.check({**TP.DECIDED, "decided_by": f"{other}:1 の処方"})
        self.assertEqual(self.bad(got), ["obvious"])
        self.assertIn("の外", got["obvious"]["note"])

    def test_request_file_is_a_source_but_not_its_folder(self):
        req = self.tmp / "request.json"
        req.write_text("[{\"where\": \"stats.py\", \"text\": \"空の列\"}]\n", encoding="utf-8")
        startrec.path(self.board).parent.mkdir(parents=True, exist_ok=True)
        startrec.path(self.board).write_text(json.dumps({"request_file": str(req)}), encoding="utf-8")
        got, _ = self.check({**TP.DECIDED, "decided_by": f"{req}:1 の依頼の行"})
        self.assertEqual(self.bad(got), [])
        (self.tmp / "other.md").write_text("依頼の横の文書\n", encoding="utf-8")
        got, _ = self.check({**TP.DECIDED, "decided_by": f"{self.tmp / 'other.md'}:1 の処方"})
        self.assertEqual(self.bad(got), ["obvious"])


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
        worldmark.write(self.tmp, status="ok", reason="", world_file=str(wf), classes=1, dropped=0, name=worldmark.COPY_STATE)
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
