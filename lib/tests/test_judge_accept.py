"""判定のブロックの受け付けと支度の芯（lib/judge_accept）の試験。

今の works の試験（test_blk_judge・test_blk_premises・test_blk_purpose・test_blk_material・test_blk_spec・test_rejudge・
test_judge_verify・test_structure_units・test_accept の TestJudge・TestIntake）が盤面の上で確かめていた場面を、値を渡す形に写した。
各試験の docstring に元の試験の名を書く。
"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import judge_accept as ja  # noqa: E402


class TablesCase(unittest.TestCase):
    def test_is_open_follows_label_and_disposition(self):
        """元 test_judge_verify の開いた単位の数え（検証器の is_open）"""
        self.assertTrue(ja.is_open({"label": "block"}))
        self.assertTrue(ja.is_open({"label": "suggest", "disposition": "do-now"}))
        self.assertFalse(ja.is_open({"label": "suggest", "disposition": "defer"}))
        self.assertFalse(ja.is_open({"label": "nit"}))


# ================================================================ 依頼と判定（A）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 依頼と判定（A）の終わり


# ================================================================ 材料・前提・目的・素材（B）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 材料・前提・目的・素材（B）の終わり


# ================================================================ 再審と仕様（C）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
import hashlib as _c_hashlib  # noqa: E402
import json as _c_json  # noqa: E402
import shutil as _c_shutil  # noqa: E402
import tempfile as _c_tempfile  # noqa: E402

from engine.util import Reject as _CReject  # noqa: E402
import rolekit as _c_rolekit  # noqa: E402
import specblk as _c_specblk  # noqa: E402
import stopby as _c_stopby  # noqa: E402
from tests.bin import gitkit as _c_gitkit  # noqa: E402

# 元 works/tests/test_blk_spec.py の ACCEPT_TEST・write_reply・review_reply・revise_reply の写し（走らせるのは exit 1 の字面）
_C_ACCEPT_TEST = ("def test_mean_is_middle():\n"
                  "    # Given 1, 2, 3 の 3 つの数\n"
                  "    # When mean を呼ぶ\n"
                  "    # Then 2 を返す\n"
                  "    assert False\n")
_C_ACCEPT_RUN = "exit 1"
_C_FACE = {"key": "F1", "kind": "missing", "where": "R1",
           "why": "空の列の平均をどう扱うかが要件にも受け入れ条件にも無い（例外か 0 か）"}


def _c_write_reply(file="test_spec_accept.txt"):
    return {"requirements": [{"key": "R1", "text": "mean は 3 つの数の平均を返す"}],
            "acceptance": [{"key": "A1", "requirement": "R1", "file": file, "name": "test_mean_is_middle",
                            "run": _C_ACCEPT_RUN}],
            "out_of_scope": []}


def _c_review_reply(faces=True):
    if faces:
        return {"faces": [_C_FACE], "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}
    return {"faces": [], "faces_none": "要件 R1 と A1 の Then は依頼の 2 つ目と同じ値を見ている。範囲の外も無い",
            "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}


def _c_revise_reply():
    spec = _c_write_reply()
    spec["out_of_scope"] = ["空の列の平均（依頼に無い。今の実装のまま）"]
    return {"spec": spec, "handled": [{"key": "F1", "handled": "declared",
                                       "how": "空の列は依頼の範囲の外と決め、out_of_scope に理由つきで足した"}]}


class _CCase(unittest.TestCase):
    """使い捨ての対象のリポジトリ（git。1 commit）と、run の置き場の judge/・rejudge/"""

    def setUp(self):
        self.tmp = pathlib.Path(_c_tempfile.mkdtemp())
        self.addCleanup(_c_shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        _c_gitkit.git(self.repo, "init", "-q")
        _c_gitkit.git(self.repo, "add", "-A")
        _c_gitkit.git(self.repo, "commit", "-q", "-m", "seed")
        self.jdir = self.tmp / "art" / ja.JUDGE_DIR
        self.rdir = self.tmp / "art" / ja.REJUDGE_DIR
        self.jdir.mkdir(parents=True)

    def write_tests(self, text=_C_ACCEPT_TEST, name="test_spec_accept.txt"):
        (self.repo / name).write_text(text, encoding="utf-8")

    def written(self):
        self.write_tests()
        got = ja.spec_take(self.jdir, "write", _c_write_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        return got


class SpecErrorsCase(_CCase):
    def test_acceptance_without_gwt_rejected(self):
        """元 test_blk_spec の書く役の拒否（写しの rules の _spec_errors: テストの中に Given/When/Then が要る）"""
        self.write_tests("def test_mean_is_middle():\n    assert False\n")
        with self.assertRaises(_CReject) as cm:
            ja.spec_write_output(_c_write_reply(), self.repo)
        self.assertIn("Given/When/Then", str(cm.exception))
        self.assertTrue(str(cm.exception).startswith("spec.write: "))

    def test_missing_test_file_and_name_rejected(self):
        """元 test_blk_spec の test_give_up_after_three（テストのファイルが無い）と、名前の無いファイル"""
        with self.assertRaises(_CReject) as cm:
            ja.spec_write_output(_c_write_reply(file="missing_test.txt"), self.repo)
        self.assertIn("missing_test.txt", str(cm.exception))
        self.write_tests(_C_ACCEPT_TEST.replace("test_mean_is_middle", "test_other"))
        with self.assertRaises(_CReject) as cm:
            ja.spec_write_output(_c_write_reply(), self.repo)
        self.assertIn("name 'test_mean_is_middle'", str(cm.exception))

    def test_keys_unique_and_point_to_requirements(self):
        """元 写しの rules の _spec_errors（鍵が一意・受け入れ条件が要件を指す・要件は受け入れ条件を持つ）"""
        self.write_tests()
        spec = _c_write_reply()
        spec["requirements"].append({"key": "R1", "text": "同じ鍵の要件"})
        spec["requirements"].append({"key": "R2", "text": "受け入れ条件の無い要件"})
        spec["acceptance"].append({**spec["acceptance"][0], "key": "A2", "requirement": "R9"})
        errs = ja._spec_errors(spec, self.repo)
        self.assertTrue(any("requirements[1] の key が重複" in e for e in errs), errs)
        self.assertTrue(any("'R9' が requirements に無い" in e for e in errs), errs)
        self.assertTrue(any("要件 'R2' に受け入れ条件が無い" in e for e in errs), errs)
        self.write_tests()
        self.assertEqual(ja._spec_errors(_c_write_reply(), self.repo), [])

    def test_review_needs_faces_none(self):
        """元 写しの rules の spec_review_output（穴を挙げないなら faces_none が要る）"""
        ja.spec_review_output(_c_review_reply())
        ja.spec_review_output(_c_review_reply(faces=False))
        with self.assertRaises(_CReject) as cm:
            ja.spec_review_output({"faces": [], "faces_none": "無い", "reason": "x" * 20})
        self.assertIn("faces_none", str(cm.exception))

    def test_revise_answers_each_face_once(self):
        """元 写しの rules の spec_revise_output（審査の穴に key ごとに 1 度だけ答える）"""
        self.write_tests()
        ja.spec_revise_output(_c_revise_reply(), _c_review_reply(), self.repo)
        bad = _c_revise_reply()
        bad["handled"] = [{"key": "F9", "handled": "absorbed", "how": "x" * 20}]
        with self.assertRaises(_CReject) as cm:
            ja.spec_revise_output(bad, _c_review_reply(), self.repo)
        self.assertIn("'F9' は仕様の審査に無い", str(cm.exception))
        self.assertIn("'F1' に応答が無い", str(cm.exception))

    def test_revise_due_only_with_faces(self):
        """元 test_blk_spec の test_no_faces_skips_revise（写しの条件 spec_revise_due）"""
        self.assertEqual(ja.spec_revise_due(ja.spec_view(_c_review_reply()))[0], True)
        self.assertEqual(ja.spec_revise_due(ja.spec_view(_c_review_reply(faces=False)))[0], False)


class SpecTakeCase(_CCase):
    def test_review_is_read_only(self):
        """元 test_blk_spec の test_review_is_read_only（審査の役が作業ツリーを変えたら拒む。元に戻せば通る）"""
        self.written()
        (self.repo / "note.txt").write_text("x\n", encoding="utf-8")
        got = ja.spec_take(self.jdir, "review", _c_review_reply(), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("読むだけの役が作業ツリーを変えた", got["reason"])
        (self.repo / "note.txt").unlink()
        got = ja.spec_take(self.jdir, "review", _c_review_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        self.assertIs(got["revise"], True, "穴が開いた審査は直す輪を回す")
        self.assertEqual(ja.read_json(self.jdir / "spec-review.json"), _c_review_reply())

    def test_review_without_faces_skips_revise(self):
        """元 test_blk_spec の test_no_faces_skips_revise"""
        self.written()
        got = ja.spec_take(self.jdir, "review", _c_review_reply(faces=False), self.repo)
        self.assertEqual((got["ok"], got["revise"]), (True, False), got)

    def test_bad_shape_is_a_reject_not_a_crash(self):
        """元 test_blk_spec の test_unreadable_reply_is_counted（読めない・形の違う返答は拒否として返す）"""
        got = ja.spec_take(self.jdir, "write", {"requirements": "x"}, self.repo)
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"])
        got = ja.spec_take(self.jdir, "nope", {}, self.repo)
        self.assertFalse(got["ok"])

    def test_revise_replaces_the_spec(self):
        """元 写しの rules の _spec_now（直した版が在ればそれが今の仕様）"""
        self.written()
        ja.spec_take(self.jdir, "review", _c_review_reply(), self.repo)
        got = ja.spec_take(self.jdir, "revise", _c_revise_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        self.assertEqual(ja.spec_now(self.jdir), _c_revise_reply()["spec"])


class SpecGateCase(_CCase):
    def asked(self, faces=True):
        self.written()
        self.assertTrue(ja.spec_take(self.jdir, "review", _c_review_reply(faces), self.repo)["ok"])
        if faces:
            self.assertTrue(ja.spec_take(self.jdir, "revise", _c_revise_reply(), self.repo)["ok"])
        got = ja.spec_ask(self.jdir, self.repo, "run-spec")
        self.assertIs(got["ask"], True, got)
        return got

    def test_ask_message(self):
        """元 test_blk_spec の test_pass_path の関所の文（run の字面・審査の穴と答え・答えの行）と test_blk_spec_gate"""
        got = self.asked()
        for part in (_C_ACCEPT_RUN, "spec.approve", "F1", "declared", "process.spec.approval",
                     _c_specblk.gatemarks.answer.line("run-spec", "continue", "<通す範囲と条件>", env={}),
                     _c_specblk.gatemarks.answer.line("run-spec", "stop", "<理由>", env={})):
            self.assertIn(part, got["message"])
        self.assertFalse((self.jdir / _c_specblk.SPEC_FILE).exists(), "承認の前に仕様を固めない")

    def test_ask_without_faces_has_no_face_lines(self):
        """元 test_blk_spec の test_no_faces_skips_revise（審査の穴の行が無い）"""
        self.assertNotIn("審査の穴", self.asked(faces=False)["message"])

    def test_ask_after_give_up_stops(self):
        """元 test_blk_spec の test_give_up_after_three（3 回とも拒まれたら関所を開かず works:spec で止める）"""
        for _ in range(3):
            _c_rolekit.with_done(self.jdir, "spec-write", {"ok": False, "reason": "テストのファイルが無い"})
        got = ja.spec_ask(self.jdir, self.repo, "run-spec")
        self.assertEqual(got, {"ask": False, "message": ""})
        stop = ja.read_stop(self.jdir)
        self.assertEqual(stop["stop_reason"], ja.SPEC_STOP)
        self.assertIn("3 回とも", stop["reason"])

    def test_freeze_records_sha_and_exit(self):
        """元 test_blk_spec の test_pass_path（承認の後に run を走らせ、sha256 と exit_at_approval を固め、依頼の行を積む）"""
        self.asked()
        ja.write_json(self.jdir / "request.json", [{"where": "x.txt", "text": "人の依頼"}])
        got = ja.spec_answer(self.jdir, self.repo, _c_json.dumps({"decision": "approve", "text": "A1 で進めてよい"}))
        self.assertEqual(got, {"go": True, "reason": ""})
        spec = ja.read_json(self.jdir / "spec.json")
        a = spec["acceptance"][0]
        want = _c_hashlib.sha256((self.repo / "test_spec_accept.txt").read_bytes()).hexdigest()
        self.assertEqual((a["sha256"], a["exit_at_approval"]), (want, 1))
        self.assertEqual((spec["approval"]["answer"], spec["approval"]["note"]), ("continue", "A1 で進めてよい"))
        self.assertEqual(spec["out_of_scope"], _c_revise_reply()["spec"]["out_of_scope"], "直した版を固めた")
        rows = ja.read_json(self.jdir / "request.json")
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1]["text"].startswith(ja.SPEC_PROVENANCE), rows[1])
        self.assertIn("exit 1", rows[1]["measured"])
        again = ja.spec_answer(self.jdir, self.repo, _c_json.dumps({"decision": "continue", "text": "二度目"}))
        self.assertTrue(again["go"])
        self.assertEqual(ja.read_json(self.jdir / "spec.json")["approval"]["note"], "A1 で進めてよい", "1 度だけ固める")
        self.assertEqual(len(ja.read_json(self.jdir / "request.json")), 2)

    def test_gate_stop_words(self):
        """元 test_blk_spec の test_gate_stop と report.py の REQUEST_BY・HUMAN_BY（人の止めと止め札を分ける）"""
        for decision, text, want in (("stop", "受け入れ条件が弱い", "human:spec-gate"),
                                     ("reject", "", "human:spec-gate"),
                                     ("reject", "request: 札", "request:spec-gate"),
                                     ("stop", "request:札", "request:spec-gate")):
            with self.subTest(decision=decision, text=text):
                self.setUp()
                self.asked(faces=False)
                got = ja.spec_answer(self.jdir, self.repo, _c_json.dumps({"decision": decision, "text": text}))
                self.assertIs(got["go"], False)
                stop = ja.read_stop(self.jdir)
                self.assertEqual(stop["stop_reason"], want)
                self.assertIn(text or _c_specblk.GATE_STOP_NOTE, stop["reason"])
                self.assertFalse((self.jdir / "spec.json").exists())

    def test_gate_skipped(self):
        """元 test_blk_spec の test_give_up_after_three の answer gate=null（関所が開かなかった）"""
        for _ in range(3):
            _c_rolekit.with_done(self.jdir, "spec-write", {"ok": False, "reason": "テストのファイルが無い"})
        ja.spec_ask(self.jdir, self.repo, "run-spec")
        got = ja.spec_answer(self.jdir, self.repo, "null")
        self.assertIs(got["go"], False)
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], ja.SPEC_STOP)

    def test_gate_unknown_word(self):
        """元 test_blk_spec の test_answer_rejects_unknown_word"""
        with self.assertRaises(_c_rolekit.BoardGap):
            _c_specblk.parse_gate(_c_json.dumps({"decision": "maybe", "text": ""}))
        self.asked(faces=False)
        got = ja.spec_answer(self.jdir, self.repo, _c_json.dumps({"decision": "maybe", "text": ""}))
        self.assertIs(got["go"], False)
        self.assertIn("maybe", got["reason"])


_C_UNIT_A = "src/a.py:f — 上限を超えた入力を黙って切る"
_C_UNIT_B = "src/b.py:g — 名前の誤り"


def _c_judgment():
    return {"units": [{"key": _C_UNIT_A, "label": "block", "reason": "切ると呼び手が気づけない", "why_chain": ["a", "b"]},
                      {"key": _C_UNIT_B, "label": "suggest", "disposition": "do-now", "reason": "読み手が迷う"}],
            "questions": [], "framing": "上限の扱い", "one_shot": "切らずに拒む", "materials_missing": [],
            "carried_r1": [], "one_shot_closes": [], "precedents": []}


def _c_rejudge_reply(verdict="一部採る", **over):
    units = [{"key": _C_UNIT_A, "label": "block", "reason": "異議の通り、切る前に拒む形に直す"},
             {"key": _C_UNIT_B, "label": "nit", "reason": "読み手は迷わない"}]
    return {"verdict": verdict, "new_facts": "src/a.py の 12 行を読み、上限の超過で黙って切ることを確かめた", "units": units,
            "reason": "上限の単位は採り、名前の単位は下げた", **over}


class RejudgeCase(_CCase):
    def prepared(self, objection=f"{_C_UNIT_A} の処方が誤り。12 行は切らずに拒んでいる"):
        ja.write_json(self.jdir / "judgment.json", _c_judgment())
        got = ja.rejudge_prep(self.jdir, self.rdir, objection, self.repo)
        self.assertTrue(got["go"], got)
        return got

    def test_no_first_judgment_stops_session(self):
        """元 test_blk_rejudge の test_block_no_session_path（1 回目の判定が無ければ再審せずに rejudge-session で止める）"""
        got = ja.rejudge_prep(self.jdir, self.rdir, "異議", self.repo)
        self.assertEqual((got["go"], got["brief_file"]), (False, ""))
        self.assertEqual(ja.read_stop(self.rdir)["stop_reason"], _c_stopby.REJUDGE_SESSION)
        self.assertIsNone(ja.read_stop(self.jdir))

    def test_prep_writes_brief_and_before(self):
        """元 test_rejudge の test_prep_marks_once（1 回目の前だけ単位の写しを置く）と描いた指示書の値"""
        got = self.prepared()
        brief = pathlib.Path(got["brief_file"]).read_text(encoding="utf-8")
        for part in ("12 行は切らずに拒んでいる", _C_UNIT_B, "上限の扱い", str(self.jdir / "judgment.json")):
            self.assertIn(part, brief)
        before = ja.read_json(self.rdir / "units-before.json")
        self.assertEqual([u["key"] for u in before["units"]], [_C_UNIT_A, _C_UNIT_B])
        self.assertEqual(before["numbered_keys"], [_C_UNIT_A, _C_UNIT_B])
        ja.rejudge_prep(self.jdir, self.rdir, "別の異議", self.repo)
        self.assertEqual(ja.read_json(self.rdir / "units-before.json"), before, "写しは 1 回目の前だけ")

    def test_verdict_word_outside_three_rejected(self):
        """元 test_rejudge の test_type_rejected（写しの型: verdict は 採る・退ける・一部採る）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(verdict="保留"), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("型に合わない", got["reason"])
        got = ja.rejudge_take(self.jdir, self.rdir, {"verdict": "採る"}, self.repo)
        self.assertFalse(got["ok"])
        self.assertFalse((self.rdir / "judgment.json").exists())

    def test_empty_facts_rejected(self):
        """元 test_rejudge の test_empty_facts_rejected（写しの rules の rejudge_output）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(new_facts="確かめた"), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("new_facts", got["reason"])
        self.assertFalse((self.rdir / "rejudge-diff.json").exists())

    def test_tree_changed_rejected(self):
        """元 test_rejudge の test_tree_changed_rejected"""
        self.prepared()
        (self.repo / "a.txt").write_text("x\n", encoding="utf-8")
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])

    def test_accept_writes_judgment_and_diff(self):
        """元 test_rejudge の test_unnamed_change_recorded（下げた単位と名指されていない変化を前後の差に残す）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(), self.repo)
        self.assertEqual((got["ok"], got["verdict"]), (True, "一部採る"), got)
        self.assertEqual(ja.read_json(self.jdir / "judgment.json"), _c_judgment(), "1 回目の判定は上書きしない")
        now = ja.read_json(self.rdir / "judgment.json")
        self.assertEqual(set(now), set(_c_judgment()))
        self.assertEqual(now["units"][1], {"key": _C_UNIT_B, "label": "nit", "reason": "読み手は迷わない"})
        rows = ja.read_json(self.rdir / "rejudge-diff.json")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["pass"], row["node"], row["verdict"]), ("rejudge", "p2.rejudge", "一部採る"))
        self.assertEqual(row["unnamed_changed"], [_C_UNIT_B])
        named = {(c["key"], c["field"]): c["named"] for c in row["changed"] if c["kind"] == "changed"}
        self.assertEqual(named[(_C_UNIT_B, "label")], False)
        self.assertEqual(named[(_C_UNIT_A, "reason")], True)

    def test_lowered_block_named_in_diff_and_exit(self):
        """元 test_rejudge の test_collect_exit_has_lowered_and_objection（block から下げた単位）"""
        self.prepared()
        reply = _c_rejudge_reply(verdict="採る")
        reply["units"][0] = {**reply["units"][0], "label": "suggest", "disposition": "do-now"}
        self.assertTrue(ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)["ok"])
        self.assertEqual(ja.read_json(self.rdir / "rejudge-diff.json")[0]["lowered"], [_C_UNIT_A])
        got = ja.rejudge_collect(self.rdir)
        self.assertTrue(got["ok"], got)
        self.assertEqual((got["passes"], got["verdicts"], got["lowered"]), (1, ["採る"], [_C_UNIT_A]))
        self.assertIn(_C_UNIT_A, got["objection"])
        self.assertEqual(got["unsettled"], {"text": "", "settled": True})
        self.assertEqual(ja.read_json(self.rdir / "rejudge-exit.json"), got)
        self.assertEqual(ja.rejudge_verdict(self.rdir), "採る")

    def test_new_open_units(self):
        """元 test_rejudge の test_new_open_units"""
        self.prepared()
        reply = _c_rejudge_reply()
        reply["units"].append({"key": "src/c.py:h — 上限の抜け道がもう 1 つ", "label": "block"})
        self.assertTrue(ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)["ok"])
        got = ja.rejudge_collect(self.rdir)
        self.assertEqual(got["new_open_units"], ["src/c.py:h — 上限の抜け道がもう 1 つ"])
        self.assertFalse(got["unsettled"]["settled"], "一部採るは異議を降ろさない")

    def test_collect_after_give_up_stops(self):
        """元 test_rejudge の test_collect_names_last_rejection（3 回とも拒まれたら works:rejudge で止める）"""
        self.prepared()
        for _ in range(3):
            out = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(new_facts="確かめた"), self.repo)
            _c_rolekit.with_done(self.rdir, "rejudge", out)
        got = ja.rejudge_collect(self.rdir)
        self.assertFalse(got["ok"])
        self.assertIn("3 回", got["reason"])
        self.assertEqual(ja.read_stop(self.rdir)["stop_reason"], _c_stopby.REJUDGE)
        self.assertIsNone(ja.rejudge_verdict(self.rdir))

    def test_class_query_examples_tried(self):
        """元 test_blk_rejudge の test_rejudge_defects_query_matching_fixed_form_is_rejected（例が問いと合わなければ拒む）"""
        self.prepared()
        reply = _c_rejudge_reply()
        reply["units"][0]["class_query"] = {
            "how": {"patterns": ["truncate("], "fixed": True, "paths": ["src"], "count": "lines"},
            "counts": "defects", "total": 1, "hits": ["x = truncate(v)"], "misses": ["x = reject_over(truncate(v))"]}
        got = ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("class_query", got["reason"])
        reply["units"][0]["class_query"]["misses"] = ["x = reject_over(v)"]
        got = ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)
        self.assertTrue(got["ok"], got)
        self.assertIn(_C_UNIT_A, ja.read_json(self.rdir / "query-examples.json"))


class RejudgeDiffCase(unittest.TestCase):
    """元 test_rejudge の DiffCase（diff_units）"""
    BEFORE = [{"key": "k1", "label": "block"}, {"key": "k2", "label": "suggest", "disposition": "do-now"},
              {"key": "k3", "label": "info"}]

    def test_named_by_number(self):
        after = [{"key": "k1", "label": "block"}, {"key": "k2", "label": "nit"}, {"key": "k3", "label": "info"}]
        for text in ("#2 の判定を見直せ", "no 2 は誤り", "No.2 は誤り", "2 番の単位", "２番の単位"):
            with self.subTest(text):
                got = ja.diff_units(self.BEFORE, after, text, ["k1", "k2", "k3"])
                self.assertEqual(got["unnamed_changed"], [], got)
                self.assertTrue(all(c["named"] for c in got["changed"]))
        got = ja.diff_units(self.BEFORE, after, "#12 と #1 を見直せ", ["k1", "k2", "k3"])
        self.assertEqual(got["unnamed_changed"], ["k2"])

    def test_no_names_all_unnamed(self):
        after = [{"key": "k1", "label": "suggest", "disposition": "do-now"}, {"key": "k2", "label": "nit"},
                 {"key": "k3", "label": "info", "reason": "足した"}]
        got = ja.diff_units(self.BEFORE, after, "判定がおかしい", ["k1", "k2", "k3"])
        self.assertEqual(got["unnamed_changed"], ["k1", "k2", "k3"])
        self.assertEqual(got["lowered"], ["k1"])

    def test_removed_and_lowered(self):
        after = [{"key": "k1", "label": "suggest", "disposition": "do-now"}, {"key": "k4", "label": "block"}]
        got = ja.diff_units(self.BEFORE, after, "k1 は block でない", [])
        kinds = {(c["key"], c["kind"]) for c in got["changed"]}
        self.assertTrue({("k2", "removed"), ("k3", "removed"), ("k4", "added"), ("k1", "changed")} <= kinds)
        self.assertEqual(got["lowered"], ["k1"])
        self.assertEqual(got["unnamed_changed"], ["k2", "k3", "k4"])

    def test_fields_are_the_writes_pick(self):
        after = [dict(self.BEFORE[0], origin_analysis="書き足した"), self.BEFORE[1], self.BEFORE[2]]
        self.assertEqual(ja.diff_units(self.BEFORE, after, "", [])["changed"], [])
        self.assertEqual(list(ja.REJUDGE_UNIT_FIELDS), ["key", "label", "disposition", "reason", "reopen_evidence"])


class SpecblkCase(unittest.TestCase):
    """元 test_blk_spec_gate の GateTextCase と test_blk_spec の parse_gate の場面（lib/specblk に残した口）"""

    def test_gate_text_answer_lines(self):
        asking = {"node": "spec.approve", "kinds": ["declared"], "question": "承認するか", "items": ["A1"]}
        text = _c_specblk.gate_text(asking, run_id="run-x")
        for verb, note in (("continue", "<通す範囲と条件>"), ("stop", "<理由>")):
            self.assertIn(_c_specblk.gatemarks.answer.line("run-x", verb, note), text)

    def test_parse_gate(self):
        self.assertIsNone(_c_specblk.parse_gate("null"))
        self.assertIsNone(_c_specblk.parse_gate(""))
        self.assertEqual(_c_specblk.parse_gate('{"decision": "reject"}'), {"decision": "reject", "text": ""})
        with self.assertRaises(_c_rolekit.BoardGap):
            _c_specblk.parse_gate("[1]")
        self.assertEqual(_c_specblk.snapshot_name("spec.review"), "spec-snapshot-spec.review.json")
# ================================================================ 再審と仕様（C）の終わり


# ================================================================ 並行 PR と世界の解（W）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
import hashlib as _w_hashlib  # noqa: E402
import json as _w_json  # noqa: E402
import shutil as _w_shutil  # noqa: E402
import subprocess as _w_subprocess  # noqa: E402
import tempfile as _w_tempfile  # noqa: E402

import rolekit as _w_rolekit  # noqa: E402
import stopby as _w_stopby  # noqa: E402
import webget as _w_webget  # noqa: E402
import worldblk as _w_worldblk  # noqa: E402
import worldmark as _w_worldmark  # noqa: E402
from accept import tree_state as _w_tree_state  # noqa: E402

_W_GITHUB = "git@github.com:o/r.git"
_W_SEED = "def mean(xs):\n    return sum(xs)\n"
# 元 works/tests/replies/pr_ok.json・pr_no_conflicts.json・pr_handed_over.json
_W_PR_OK = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている（gh pr diff 7 -R o/r の hunk @@ -1,3 +1,4 @@）。申し送りの下書きを conflicts[0].note に書いた（投稿していない）"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": False,
                   "note": "PR #7 の担当へ: この run（判定から入る run）も stats.py の mean を直します。#7 の hunk @@ -1,3 +1,4 @@ と同じ行です。どちらを先に入れるか決めてください。"}],
    "excluded": [{"pr": "7", "file": "stats.py", "start": 1, "end": 2,
                  "why": "PR #7 の hunk @@ -1,3 +1,4 @@ が mean の同じ行を書き換える（この run の依頼 1 件目と同じ所）"}],
}
_W_PR_NO_CONFLICTS = {
    "material": {"status": "clean", "checked": "gh -R o/r で open な PR 2 件を引き、自分の PR（headRefOid が HEAD）を除いて、変更ファイルの集合と交差した PR #7 の差分を読んだ。同じファイルの hunk はこの run の変更とぶつからない（衝突 0 件・打ち切りなし）"},
    "repo": "o/r", "listed": 2, "truncated": False, "conflicts": [], "excluded": [],
}
_W_PR_HANDED_OVER = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている。担当の PR に申し送った"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": True, "note": "gh pr comment 7 -R o/r で申し送った"}],
    "excluded": [],
}


def _w_git(repo, *args):
    return _w_subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                             check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _w_fake_gh(prs, files):
    """lib/ghreads._gh の代わりの読む口（本物の gh・GitHub に触らない）。prs は pr list の返り、files は番号 → 変更ファイル"""
    calls = []

    def gh(*args):
        calls.append(args)
        if args[:2] == ("pr", "list"):
            return prs, None, False
        if args[:2] == ("pr", "view"):
            return {"files": [{"path": p} for p in files.get(args[2], [])]}, None, False
        return None, f"知らない語 {args}", False
    gh.calls = calls
    return gh


def _w_never(*args):
    raise AssertionError(f"gh を呼んではいけない: {args}")


class _WPrBase(unittest.TestCase):
    """並行 PR の場面（元 test_blk_pr の PrCase）: 判定から入る run の対象（stats.py を持つ git の木）と judge/ の置き場"""

    def setUp(self):
        self.tmp = pathlib.Path(_w_tempfile.mkdtemp(prefix="judge-w-"))
        self.addCleanup(_w_shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo, self.jdir = self.tmp / "repo", self.tmp / "art" / ja.JUDGE_DIR
        self.repo.mkdir()
        self.jdir.mkdir(parents=True)
        _w_git(self.repo, "init", "-q")
        (self.repo / "stats.py").write_text(_W_SEED, encoding="utf-8")
        _w_git(self.repo, "add", "-A")
        _w_git(self.repo, "commit", "-q", "-m", "seed")
        _w_git(self.repo, "remote", "add", "origin", _W_GITHUB)
        self.head = _w_git(self.repo, "rev-parse", "HEAD").strip()
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({"base_rev": self.head, "input": {"base": {"rev": self.head}}}))
        ja.write_json(self.jdir / ja.REQUEST_FILE, [{"where": "stats.py:2", "text": "mean が数で割っていない"}])

    def scan(self, gh=None, which=lambda name: "/bin/gh"):
        return ja.pr_scan(self.jdir, self.repo, gh=gh or _w_never, which=which)

    def material(self):
        return _w_json.loads((self.jdir / ja.MATERIAL_PR_FILE).read_text(encoding="utf-8"))

    def snap(self):
        """入口が置く作業ツリーの写し（judge/judge-tree.json。元 prcheck.snapshot の pr-snapshot.json）"""
        ja.write_json(self.jdir / ja.TREE_FILE, _w_tree_state(self.repo))


class WPrScanCase(_WPrBase):
    def test_no_crossing_is_decided_by_machine(self):
        """元 test_blk_pr の test_helper_by_engine_when_no_crossing: 交差 0 → 機械で済む（役は要らない）。素材は clean、
        自分の PR（headRefOid が HEAD）は外す。外す hunk の一覧は空で置く"""
        gh = _w_fake_gh([{"number": 3, "headRefName": "me", "headRefOid": self.head},
                         {"number": 7, "headRefName": "x", "headRefOid": "f" * 40}], {"7": ["other.py"], "3": ["stats.py"]})
        got = self.scan(gh)
        self.assertEqual((got["go"], got["go_role"]), (True, False), got)
        self.assertEqual(self.material()["materials"]["parallel_pr"]["status"], "clean")
        self.assertEqual(self.material()["role"], "pr-check")
        self.assertNotIn(("pr", "view", "3", "-R", "o/r", "--json", "files"), gh.calls, "自分の PR は見ない")
        doc = _w_json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["excluded"]), ("p0.parallel_pr", []))
        self.assertTrue(all("-R" in c for c in gh.calls), "gh は必ず -R で呼ぶ")

    def test_crossing_falls_back_to_role(self):
        """元 test_blk_pr の test_fallback_on_crossing_sets_role_needed: 交差 1 件 → 役へ（go_role）。渡し物に理由と
        交差を取る集合（差分が空なので依頼の where が名指す追跡中のパス）。素材は役が返すまで書かない"""
        got = self.scan(_w_fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
        self.assertEqual((got["go"], got["go_role"]), (True, True))
        self.assertIn("交差", got["reason"])
        brief = _w_json.loads((self.jdir / "pr-brief.json").read_text(encoding="utf-8"))
        self.assertEqual((brief["node"], brief["changed_files"], brief["fallback"]), ("p0.parallel_pr", ["stats.py"], got["reason"]))
        self.assertEqual(brief["request_wheres"], ["stats.py:2"])
        self.assertFalse((self.jdir / ja.MATERIAL_PR_FILE).exists())

    def test_diff_files_win_over_request_wheres(self):
        """元 review-loop.py の _pr_files: 差分の根から変わったファイルが在れば、それが交差を取る集合（依頼の where は使わない）"""
        (self.repo / "new.py").write_text("x = 1\n", encoding="utf-8")
        got = self.scan(_w_fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
        self.assertEqual(got["go_role"], False, got)
        self.assertEqual(self.material()["materials"]["parallel_pr"]["status"], "clean")

    def test_gh_missing_falls_back(self):
        """元 test_blk_pr の test_fallback_when_gh_missing: gh が無い → 何も走らせずに役へ"""
        got = self.scan(which=lambda name: None)
        self.assertTrue(got["go_role"])
        self.assertIn("gh", got["reason"])

    def test_no_forge_is_not_applicable(self):
        """元 test_forge の forge の無い run（entry の parallel_pr_due・fill_materials の組み手）: remote が GitHub でない
        （ローカルのパス）→ 役を起こさず、素材は not_applicable（no_forge: …）"""
        _w_git(self.repo, "remote", "set-url", "origin", str(self.tmp / "elsewhere"))
        got = self.scan()
        self.assertEqual((got["go"], got["go_role"]), (True, False))
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "not_applicable")
        self.assertTrue(m["reason"].startswith("no_forge: local_path"), m)

    def test_empty_set_is_not_run(self):
        """元 test_blk_pr の test_blocked_is_engine_with_reason: 交差を取る集合が空 → 機械が not_run で済ませ、理由に「空」"""
        ja.write_json(self.jdir / ja.REQUEST_FILE, [{"where": "nowhere.py", "text": "x"}])
        got = self.scan()
        self.assertFalse(got["go_role"])
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "not_run")
        self.assertIn("空", m["reason"])

    def test_truncated_and_unreadable_wait_for_human(self):
        """元 review-loop.py の parallel_pr_reply: 一覧が上限で打ち切られた・gh が読めない → awaiting_human（衝突なしと書かない）"""
        many = [{"number": n, "headRefOid": "f" * 40} for n in range(ja.PR_LIMIT)]
        self.scan(_w_fake_gh(many, {}))
        self.assertIn("打ち切られた", self.material()["materials"]["parallel_pr"]["reason"])
        self.scan(lambda *a: (None, "gh pr が exit 1: HTTP 401", False))
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "awaiting_human")
        self.assertIn("HTTP 401", m["reason"])

    def test_stopped_run_does_not_go(self):
        """仕様の段が止めた run は先へ進めない（go 偽）"""
        ja.write_stop(self.jdir, "human:spec-gate", "要らない")
        got = self.scan()
        self.assertEqual((got["go"], got["go_role"]), (False, False))

    def test_github_repo_redacts_token(self):
        """元 entry.py の github_repo_redacted: GitHub でない remote の理由の文に URL の userinfo（トークン）を載せない"""
        _w_git(self.repo, "remote", "set-url", "origin", "https://user:SECRET@git.example.com/o/r.git")
        slug, why = ja._github_repo(self.repo)
        self.assertIsNone(slug)
        self.assertNotIn("SECRET", why)
        _w_git(self.repo, "remote", "set-url", "origin", "https://github.com/o/r.git")
        self.assertEqual(ja._github_repo(self.repo), ("o/r", None))


class WPrAcceptCase(_WPrBase):
    def setUp(self):
        super().setUp()
        self.snap()

    def accept(self, reply):
        return ja.pr_accept(self.jdir, _w_json.dumps(reply, ensure_ascii=False), self.repo)

    def test_check_no_post(self):
        """元 test_blk_pr の test_check_no_post"""
        self.assertEqual(ja.check_no_post(_W_PR_HANDED_OVER), ["7"])
        self.assertEqual(ja.check_no_post(_W_PR_OK), [])
        self.assertEqual(ja.check_no_post(_W_PR_NO_CONFLICTS), [])
        two = _w_json.loads(_w_json.dumps(_W_PR_OK))
        two["conflicts"] += [{"pr": "9", "files": ["a"], "handed_over": True}, {"pr": "11", "files": ["b"], "handed_over": True}]
        self.assertEqual(ja.check_no_post(two), ["9", "11"])
        self.assertEqual(ja.check_no_post({"conflicts": "x"}), [])

    def test_handed_over_true_rejected(self):
        """元 test_blk_pr の test_handed_over_true_rejected: handed_over true が 1 件 → ok false、文に pr と「投稿しない」。何も書かない"""
        got = self.accept(_W_PR_HANDED_OVER)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("投稿しない", got["reason"])
        self.assertTrue(got["reason"].endswith(": 7"), got["reason"])
        self.assertFalse((self.jdir / "pr-excluded.json").exists())

    def test_handover_draft_accepted_with_anchor(self):
        """元 test_blk_pr の test_handover_draft_accepted・test_excluded_hunks_leave_scope・test_excluded_carries_content_anchor:
        通れば外す hunk が中身と sha256 と写しの HEAD つきで pr-excluded.json に、申し送りの下書きが pr-downgrades.json に、
        素材（excluded を外した返答）が material-pr-check.json に置かれる"""
        got = self.accept(_W_PR_OK)
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        doc = _w_json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["head"]), ("p0.parallel_pr", self.head))
        h = doc["excluded"][0]
        self.assertEqual({k: h[k] for k in ("pr", "file", "start", "end", "why")}, _W_PR_OK["excluded"][0])
        self.assertEqual(h["text"], _W_SEED)
        self.assertEqual(h["sha256"], _w_hashlib.sha256(_W_SEED.encode("utf-8")).hexdigest())
        drafts = _w_json.loads((self.jdir / ja.PR_DOWNGRADES_FILE).read_text(encoding="utf-8"))
        self.assertEqual(drafts, [{"pr": "7", "files": ["stats.py"], "note": _W_PR_OK["conflicts"][0]["note"]}])
        mat = self.material()
        self.assertEqual(mat["materials"]["parallel_pr"]["status"], "found")
        self.assertNotIn("excluded", mat["reply"])

    def test_no_conflicts_reply_accepted(self):
        """元 test_blk_pr の test_no_conflicts_reply_accepted"""
        self.assertTrue(self.accept(_W_PR_NO_CONFLICTS)["ok"])
        doc = _w_json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["excluded"], [])

    def test_excluded_checked(self):
        """元 test_blk_pr の test_excluded_checked: 外す hunk の誤り → ok false。何も書かない"""
        hunk = _W_PR_OK["excluded"][0]
        cases = {"excluded が無い": {k: v for k, v in _W_PR_OK.items() if k != "excluded"},
                 "conflicts に無い": dict(_W_PR_OK, excluded=[dict(hunk, pr="99")]),
                 "交差したファイル": dict(_W_PR_OK, excluded=[dict(hunk, file="other.py")]),
                 "より大きい": dict(_W_PR_OK, excluded=[dict(hunk, start=2, end=1)]),
                 "行の数 2 を超える": dict(_W_PR_OK, excluded=[dict(hunk, end=3)]),
                 "note": dict(_W_PR_OK, conflicts=[{k: v for k, v in _W_PR_OK["conflicts"][0].items() if k != "note"}]),
                 "型": dict(_W_PR_OK, excluded=[dict(hunk, start=0)])}
        for word, bad in cases.items():
            got = ja.prcheck_take(self.jdir, bad, self.repo)
            self.assertFalse(got["ok"], word)
            self.assertIn(word, got["reason"], word)
            self.assertFalse((self.jdir / "pr-excluded.json").exists(), word)

    def test_fallback_role_reads_only(self):
        """元 test_blk_pr の test_fallback_role_reads_only・test_head_move_rejected: 入口の写しの後に作業ツリーや HEAD を
        変えて受け付け → ok false、文に「作業ツリーを変えた」"""
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        got = ja.prcheck_take(self.jdir, _W_PR_OK, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])
        (self.repo / "stats.py").write_text(_W_SEED, encoding="utf-8")
        _w_git(self.repo, "checkout", "-q", "-b", "other")
        self.assertIn("ref", ja.prcheck_take(self.jdir, _W_PR_OK, self.repo)["reason"])

    def test_malformed_reply_bounced_not_crashed(self):
        """元 test_blk_pr の test_malformed_reply_bounced_not_crashed・test_accept_script_unreadable_reply: JSON でない・
        素材の形が違う返答 → 例外でなく ok false"""
        got = ja.pr_accept(self.jdir, "not json", self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("JSON", got["reason"])
        self.assertIn("型", ja.prcheck_take(self.jdir, dict(_W_PR_OK, material={"status": "maybe"}), self.repo)["reason"])

    def test_third_rejection_gives_up_and_stops(self):
        """元 blk-pr/scripts/collect.py の gave_up（rolekit.gave_up。by は stopby.PR）: 3 回目の拒否で done、止めの控えを置く"""
        for n in range(1, _w_rolekit.GIVE_UP_AFTER + 1):
            got = self.accept(_W_PR_HANDED_OVER)
            self.assertEqual(got["done"], n == _w_rolekit.GIVE_UP_AFTER, n)
        self.assertEqual(len(_w_json.loads((self.jdir / "rejects-pr-check.json").read_text(encoding="utf-8"))), 3)
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], _w_stopby.PR)


# 元 works/tests/test_blk_world.py の見本
_W_URL = "https://example.org/guide/tdd"
_W_PAGE = ("<html><body><p>Write a failing test first. A compile error is not a red test: add the smallest stub so the test runs"
           " and fails on the expected assertion.</p></body></html>").encode()
_W_GOOD = "A compile error is not a red test: add the smallest stub so the test runs and fails on the expected assertion."
_W_FINDINGS = [
    {"where": "src/red_check.py:40", "text": "赤の判定がコンパイルの要る対象で読み込みの失敗を赤に数える。読むだけの役を足して生のログから判じさせる"},
    {"where": "docs/guide.md", "text": "手引きの誤字（赤を緑と書いている）"},
]
_W_PROBLEM = "テストを先に書く開発で、まだ無い機能を呼ぶテストを、コンパイルの要る対象でどう赤にするか"
_W_CLASSES = {"classes": [
    {"finding": 1, "problem": _W_PROBLEM, "activity": "テストを先に書く開発", "proposed": "読むだけの役を足して生のログから判じさせる",
     "queries": ["test-first red phase compile error stub"]},
    {"finding": 2, "problem": "文書の誤字を直す", "activity": "文書の校正", "proposed": "", "queries": ["proofreading documentation typos practice"]},
]}


def _w_judged(finding=1, **kw):
    row = {"finding": finding, "practice": "読み込みの失敗は赤に数えず、最小の仮の実装で走らせてから期待違いの失敗を赤とする",
           "sources": [], "applies": "赤の判定の直し", "not_applies": "", "verdict": "differs",
           "challenge": "依頼は読む役を足す、定石は仮の実装で走らせる。読み込みの失敗が赤でない訳が無い限り定石を選ぶ"}
    row.update(kw)
    return row


class WWorldCase(unittest.TestCase):
    """世界の解の段を judge/ の置き場で回す（元 test_blk_world の Scripts.test_web_off_run_reaches_exit と Verify・Judge の場面を、
    節の中身の関数で。網に出ない: 取り直しの口 get を差し替える）"""

    def setUp(self):
        self.tmp = pathlib.Path(_w_tempfile.mkdtemp(prefix="judge-w-world-"))
        self.addCleanup(_w_shutil.rmtree, self.tmp, ignore_errors=True)
        self.jdir = self.tmp / ja.JUDGE_DIR
        self.jdir.mkdir()
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({}))
        ja.write_json(self.jdir / ja.REQUEST_FILE, _W_FINDINGS)
        ja.write_json(self.jdir / "purpose.json", {"purpose_text": "赤を言語に依らず判じる", "source": "request",
                                                   "known_weaknesses": [], "source_files": []})
        ja.write_json(self.jdir / "purpose-means.json", {"means": ["読むだけの役を足す"]})

    def intake(self):
        return ja.world_intake(self.jdir, self.tmp)

    def through_classes(self):
        self.assertTrue(self.intake()["due"])
        self.assertTrue(ja.world_accept(self.jdir, "world-classes", _w_json.dumps(_W_CLASSES, ensure_ascii=False))["ok"])

    def test_intake_shows_request_purpose_and_means(self):
        """元 test_blk_world の test_purpose_means_are_shown: 言い直す役の指示書の本文に依頼の行・目的の文・依頼の解き方が載る。
        段の入力の目的の文は judge/world-purpose.json（元 line_edge._world_due）、worldblk の控えは judge/world/ の下"""
        got = self.intake()
        self.assertEqual((got["due"], got["reason"]), (True, ""))
        for want in ("赤を言語に依らず判じる", "読むだけの役を足す", _W_FINDINGS[0]["where"]):
            self.assertIn(want, got["prompt"])
        doc = _w_json.loads((self.jdir / ja.WORLD_PURPOSE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(doc, {"purpose_text": "赤を言語に依らず判じる", "means": ["読むだけの役を足す"]})
        self.assertTrue((self.jdir / "world" / _w_worldblk.INTAKE).is_file())
        self.assertTrue(_w_json.loads((self.jdir / "world" / _w_worldblk.INTAKE).read_text(encoding="utf-8"))["web"])

    def test_world_cut_turns_web_off(self):
        """始めの記録の features_cut に world が在れば web は off（元 entry.py の WORLD_FEATURE）"""
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({"features_cut": ["world"]}))
        self.intake()
        self.assertFalse(_w_json.loads((self.jdir / "world" / _w_worldblk.INTAKE).read_text(encoding="utf-8"))["web"])

    def test_missing_purpose_is_not_due_and_finish_says_why(self):
        """元 line_edge._world_due: 目的の文が読めなければ回さない。出口は status failed で理由に目的の文のファイル"""
        (self.jdir / "purpose.json").unlink()
        got = self.intake()
        self.assertFalse(got["due"])
        fin = ja.world_finish(self.jdir)
        self.assertEqual((fin["ok"], fin["status"]), (True, "failed"))
        self.assertIn(ja.WORLD_PURPOSE_FILE, fin["reason"])

    def test_stopped_run_is_not_due(self):
        ja.write_stop(self.jdir, _w_stopby.PURPOSE, "目的が決まらない")
        self.assertEqual(self.intake()["due"], False)
        self.assertEqual(ja.world_plan(self.jdir)["due"], False)

    def test_full_stage_writes_world_rows_and_state(self):
        """元 test_blk_world の test_web_row_carries_kept_sources・test_verify_keeps_fetched_excerpt_and_caps_total: 言い直し →
        類を決める → web の役（指示書の本文に excerpts の返し方）→ 抜き書きを取り直した本文で照らす（字のまま無い抜き書きは落ち、
        それを指す根拠も外れる）→ judge/world.jsonl と judge/world-state.json（worldmark.stage_rows が読む）"""
        self.through_classes()
        plan = ja.world_plan(self.jdir)
        self.assertTrue(plan["due"], plan)
        self.assertIn("excerpts に", plan["prompt"])
        self.assertNotIn(_W_FINDINGS[0]["text"], plan["prompt"])
        made_up = {"id": "x2", "url": _W_URL, "excerpt": "Nothing like this sentence is on that page at all."}
        reply = {"rows": [_w_judged(sources=["x1", "x2"]), _w_judged(2, verdict="none", challenge="")],
                 "excerpts": [{"id": "x1", "url": _W_URL, "excerpt": _W_GOOD}, made_up]}
        got = ja.world_accept(self.jdir, "world-judge", _w_json.dumps(reply, ensure_ascii=False), get=lambda u: (200, _W_PAGE))
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        fin = ja.world_finish(self.jdir)
        self.assertEqual((fin["ok"], fin["status"]), (True, "ok"), fin)
        rows = _w_worldmark.rows(self.jdir / _w_worldmark.WORLD_FILE)
        self.assertEqual([(r["basis"], [s["id"] for s in r["sources"]]) for r in rows], [("web", ["x1"]), ("knowledge", [])])
        self.assertEqual(rows[0]["where"], _W_FINDINGS[0]["where"])
        state = _w_worldmark.read(self.jdir)
        self.assertEqual((state["status"], state["classes"], state["dropped"]), ("ok", 2, 1))
        self.assertEqual(_w_worldmark.stage_rows(self.jdir), rows)

    def test_offline_run_still_finishes(self):
        """元 test_blk_world の test_verified_fields_offline_and_web_off: 網に届かない run は止めず、行は知識だけ（NOT_WEB）"""
        self.through_classes()
        ja.world_plan(self.jdir)

        def down(url):
            raise _w_webget.FetchError("網に届かない")
        reply = {"rows": [_w_judged(sources=["x1"]), _w_judged(2, verdict="none", challenge="")],
                 "excerpts": [{"id": "x1", "url": _W_URL, "excerpt": _W_GOOD}]}
        self.assertTrue(ja.world_accept(self.jdir, "world-judge", _w_json.dumps(reply), get=down)["ok"])
        fin = ja.world_finish(self.jdir)
        self.assertEqual(fin["status"], "ok")
        self.assertIn(_w_worldmark.NOT_WEB, fin["reason"])
        self.assertEqual({r["basis"] for r in _w_worldmark.rows(self.jdir / _w_worldmark.WORLD_FILE)}, {"knowledge"})

    def test_rejections_counted_and_give_up_does_not_stop(self):
        """元 test_blk_world の test_rejections_counted_by_rolekit・test_classes_given_up_skips_everything: JSON でない返答も
        拒否として数え、3 回目で done。web の役は起こさず、出口は status failed（言い直す役）で、run は止めない"""
        self.intake()
        for n in range(1, _w_rolekit.GIVE_UP_AFTER + 1):
            got = ja.world_accept(self.jdir, "world-classes", "not json" if n == 1 else '{"classes": []}')
            self.assertEqual((got["ok"], got["done"]), (False, n == _w_rolekit.GIVE_UP_AFTER), n)
        self.assertEqual(len(_w_rolekit.rejected(self.jdir, "world-classes")), 3)
        self.assertEqual(len(_w_rolekit.rejected(self.jdir / "world", _w_worldblk.CLASSES_ROLE)), 3)
        plan = ja.world_plan(self.jdir)
        self.assertFalse(plan["due"])
        self.assertIn("3 回とも", plan["reason"])
        fin = ja.world_finish(self.jdir)
        self.assertEqual((fin["ok"], fin["status"]), (True, "failed"))
        self.assertIn("言い直す役", fin["reason"])
        self.assertIsNone(ja.read_stop(self.jdir))
        self.assertEqual(_w_worldmark.read(self.jdir)["status"], "failed")
        self.assertIsNone(_w_worldmark.stage_rows(self.jdir))

    def test_judge_reject_names_the_problem(self):
        """元 test_blk_world の Judge.test_differs_needs_challenge・test_practice_with_target_identifier_is_refused"""
        self.through_classes()
        ja.world_plan(self.jdir)
        bad = {"rows": [_w_judged(challenge="短い"), _w_judged(2, verdict="none", challenge="")], "excerpts": []}
        self.assertIn("challenge", ja.world_accept(self.jdir, "world-judge", _w_json.dumps(bad))["reason"])
        bad = {"rows": [_w_judged(practice="src/red_check.py を直す"), _w_judged(2, verdict="none", challenge="")], "excerpts": []}
        self.assertIn("src/red_check.py", ja.world_accept(self.jdir, "world-judge", _w_json.dumps(bad))["reason"])
# ================================================================ 並行 PR と世界の解（W）の終わり


# ================================================================ 入口と返り（F）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
class StartViewCase(unittest.TestCase):
    def test_missing_fields_take_the_contract_defaults(self):
        """元 test_accept.TestIntake（始めの記録の欄が無い時の読み）。既定は docs/design.md の「judge の返り」の入力 start の決め"""
        view = ja.start_view({"input": {"request_file": "/r.json", "base": {"rev": "a" * 40}}})
        self.assertEqual(view["request_file"], "/r.json")
        self.assertEqual((view["policy_md"], view["features_cut"], view["spec"], view["answers"], view["gates"]),
                         ("", ["judge_verify"], False, [], ""))
        self.assertEqual(view["diff_base"], "a" * 40)
        self.assertEqual(ja.start_view(None)["request_file"], "")

    def test_explicit_fields_win(self):
        view = ja.start_view({"request_file": "/top.json", "features_cut": [], "input": {"spec": True, "request_file": "/r.json"}})
        self.assertEqual((view["request_file"], view["features_cut"], view["spec"]), ("/top.json", [], True))


class StopFileCase(unittest.TestCase):
    def test_first_stop_wins(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ja.read_stop(tmp))
            ja.write_stop(tmp, ja.SPEC_STOP, "一つ目")
            ja.write_stop(tmp, ja.JUDGE_STOP, "二つ目")
            self.assertEqual(ja.read_stop(tmp), {"stop_reason": ja.SPEC_STOP, "reason": "一つ目"})

    def test_block_words_carry_the_machine_head(self):
        for word in (ja.JUDGE_STOP, ja.VERIFY_STOP, ja.SPEC_STOP, ja.MATERIAL_STOP, ja.REQUEST_STOP):
            self.assertTrue(word.startswith("works:"), word)
# ================================================================ 入口と返り（F）の終わり


if __name__ == "__main__":
    unittest.main()
