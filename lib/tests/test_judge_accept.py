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
