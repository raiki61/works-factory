"""仕様の block を、script を子のプロセスで回して確かめる（docs/design/spec.md の 10.2）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → prep → 台本の返答（テストのファイルも
試験が書く）→ take（write）→ prep → take（review）→ prep → take（revise）→ ask → 答え → freeze → finish と回す。受け付け・承認ノード・
固め・照らしの決まりは src の関数をこの過程で呼んで確かめる。YAML と筋書きの揃いも見る。筋書きを Archon の workflow test で回すのは
tests/layers/test_block_shape.py。
"""
import hashlib
import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "spec"
TEST_FILE = "test_spec_accept.txt"
TEST_TEXT = ("def test_mean_is_middle():\n"
             "    # Given 1, 2, 3 の 3 つの数\n"
             "    # When mean を呼ぶ\n"
             "    # Then 2 を返す\n"
             "    assert False\n")
RUN = "exit 1"
ROWS = [{"where": "stats.py:4", "text": "mean は 2 でなく 3 を返す。分母を len(xs) にする"}]
REQUEST = json.dumps(ROWS, ensure_ascii=False)
FACE = {"key": "F1", "kind": "missing", "where": "R1", "why": "空の列の平均をどう扱うかが要件にも受け入れ条件にも無い（例外か 0 か）"}


def write_reply(file=TEST_FILE):
    return {"requirements": [{"key": "R1", "text": "mean は 3 つの数の平均を返す"}],
            "acceptance": [{"key": "A1", "requirement": "R1", "file": file, "name": "test_mean_is_middle", "run": RUN}],
            "out_of_scope": []}


def review_reply(faces=True):
    if faces:
        return {"faces": [FACE], "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}
    return {"faces": [], "faces_none": "要件 R1 と A1 の Then は依頼の 2 つ目と同じ値を見ている。範囲の外も無い",
            "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}


def revise_reply():
    spec = write_reply()
    spec["out_of_scope"] = ["空の列の平均（依頼に無い。今の実装のまま）"]
    return {"spec": spec, "handled": [{"key": "F1", "handled": "declared", "how": "空の列は依頼の範囲の外と決め、out_of_scope に理由つきで足した"}]}


def doc() -> dict:
    return yaml.safe_load((BLOCK / "works-factory-spec.yaml").read_text(encoding="utf-8"))


def nodes(d=None) -> dict:
    out = {}
    for node in (d or doc())["nodes"]:
        out[node["id"]] = node
        for inner in (node.get("loop_group") or {}).get("nodes") or []:
            out[inner["id"]] = inner
    return out


class _Case(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "spec")
        (self.run.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.steps = kit.load("spec", "steps")
        self.place = self.run.artifacts

    def read(self, name):
        return json.loads((self.place / name).read_text(encoding="utf-8"))

    def write_tests(self, text=TEST_TEXT, name=TEST_FILE):
        (self.run.repo / name).write_text(text, encoding="utf-8")

    def intake(self, **inputs):
        return self.run.script("intake", **{"mode": "write", "request": REQUEST, "pr_text": "", "lang": "", **inputs})

    def prep(self, role, prev=""):
        return self.run.script("prep", role=role, prev=prev)

    def fix_prep(self, role):
        return self.run.script("fix_prep", role=role)

    def take(self, role, reply, fix=None, guarded=None):
        guarded = role == "review" if guarded is None else guarded
        return self.run.script("take", role=role, status_guarded="true" if guarded else "false", reply=json.dumps(reply, ensure_ascii=False),
                               fix_reply="null" if fix is None else json.dumps(fix, ensure_ascii=False))

    def written(self):
        """intake と書く役の受け付けまで済ませる"""
        self.assertEqual(self.intake()["go"], True)
        self.write_tests()
        got = self.take("write", write_reply())
        self.assertTrue(got["ok"], got)

    def reviewed(self, faces=True):
        self.written()
        got = self.take("review", review_reply(faces))
        self.assertTrue(got["ok"], got)
        if faces:
            got = self.take("revise", revise_reply())
            self.assertTrue(got["ok"], got)

    def asked(self, faces=True):
        self.reviewed(faces)
        got = self.run.script("ask")
        self.assertIs(got["ask"], True, got)
        return got

    def freeze(self, decision="approve", text="", **inputs):
        return self.run.script("freeze", answer=json.dumps({"decision": decision, "text": text}, ensure_ascii=False), **inputs)

    def finish(self, checked="null"):
        return self.run.script("finish", checked=checked)


class FlowCase(_Case):
    def test_write_to_approval_end_to_end(self):
        """port の値だけで、書く→審査→直す→承認ノード→固めまで回り、出口が approved と pointer・報告の行・足した行を返す"""
        self.assertEqual(self.intake(), {"mode": "write", "go": True, "reason": ""})
        first = self.prep("write")
        self.assertEqual(first["resubmit"], False)
        self.assertIn(str(self.place / "request.json"), first["prompt"])
        self.write_tests()
        self.assertEqual(self.take("write", write_reply()), {"ok": True, "done": True, "reason": "", "revise": False})
        self.assertIn(str(self.place / "spec-write.json"), self.prep("review")["prompt"])
        got = self.take("review", review_reply())
        self.assertEqual((got["ok"], got["revise"]), (True, True))
        self.assertIn(str(self.place / "spec-review.json"), self.prep("revise")["prompt"])
        self.assertTrue(self.take("revise", revise_reply())["ok"])
        asked = self.run.script("ask")
        self.assertTrue(asked["ask"])
        self.assertFalse((self.place / "spec.json").exists(), "承認の前に仕様を固めない")
        self.assertEqual(self.freeze(text="A1 で進めてよい"), {"go": True, "reason": ""})
        spec = self.read("spec.json")
        row = spec["acceptance"][0]
        self.assertEqual((row["sha256"], row["exit_at_approval"]), (hashlib.sha256(TEST_TEXT.encode()).hexdigest(), 1))
        self.assertEqual((spec["approval"]["answer"], spec["approval"]["note"]), ("continue", "A1 で進めてよい"))
        self.assertEqual(spec["out_of_scope"], revise_reply()["spec"]["out_of_scope"], "直した版を固めた")
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["stop_reason"], out["reason"]), (True, "approved", "", ""))
        self.assertEqual(out["spec"], json.loads(self.run.pointer("spec.json")))
        self.assertEqual(out["added_rows"], json.loads(self.run.pointer("added-rows.json")))
        self.assertEqual((out["questions"], out["unchecked"]), ([], False))
        rows = self.read("added-rows.json")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["text"].startswith(self.steps.gate.freeze.PROVENANCE), rows[0])
        self.assertIn("exit 1", rows[0]["measured"])
        self.assertEqual(out["added_origin"], self.steps.gate.freeze.ORIGIN)
        self.assertEqual(out["report"][0], "仕様: 要件 1 件・受け入れ条件 1 件を人が承認した（一言: A1 で進めてよい）")
        self.assertEqual(out["report"][1], f"- A1（要件 R1）: {TEST_FILE} の test_mean_is_middle——承認の時 exit 1")
        self.assertEqual(self.run.script("ask")["ask"], True, "もう一度組んでも同じ")
        self.assertEqual(self.freeze(text="二度目")["go"], True)
        self.assertEqual(self.read("spec.json")["approval"]["note"], "A1 で進めてよい", "1 度だけ固める")

    def test_no_faces_skips_revise_and_the_ask_has_no_face_lines(self):
        message = self.asked(faces=False)["message"]
        self.assertNotIn("審査の穴", message)
        self.assertFalse((self.place / "spec-revise.json").exists())
        self.assertTrue(self.freeze()["go"])
        self.assertEqual(self.finish()["status"], "approved")

    def test_ask_message(self):
        message = self.asked()["message"]
        gatemarks = self.steps.gate.gatemarks
        for part in (RUN, "F1", "declared", "process.spec.approval", gatemarks.answer.line("run-test", "continue", "<通す範囲と条件>"),
                     gatemarks.answer.line("run-test", "stop", "<理由>")):
            self.assertIn(part, message)

    def test_request_container_and_pointer(self):
        (self.place / "req.json").write_text(json.dumps({"findings": ROWS, "pr": [], "issue": []}), encoding="utf-8")
        self.assertTrue(self.intake(request=self.run.pointer("req.json"))["go"])
        self.assertEqual(self.read("request.json"), ROWS)

    def test_empty_request_is_not_refused(self):
        self.assertTrue(self.intake(request="[]")["go"])
        self.assertEqual(self.read("request.json"), [])

    def test_approval_in_users_env_leaves_the_marker(self):
        """起動の殻を通った run（隔離の前の HOME・XDG の控えが在る）では、受け入れ条件のコマンドを利用者の HOME・XDG に戻して走らせ、
        印の置き場に印を残す。user_env_dir が空なら place に置く（置き場を立てずに戻すと、戻さずに止まって仕様を固められない）"""
        import userenv   # lib/（steps を読んだ時に ports が足した）
        home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        for given in ("", str(home)):
            with self.subTest(user_env_dir=given):
                self.setUp()
                where = pathlib.Path(given) if given else self.place
                self.asked()
                with self.run.env(), mock.patch.dict(os.environ, {userenv.RECORD: userenv.record({"HOME": str(home)})}):
                    got = self.steps.freeze_answer(self.place, self.run.repo, {"decision": "approve", "text": ""}, given)
                self.assertTrue(got["go"], got)
                self.assertEqual(self.read("spec.json")["acceptance"][0]["exit_at_approval"], 1)
                self.assertTrue(userenv.ran(where))


class IntakeCase(_Case):
    def test_write_clears_only_its_own_files(self):
        """前の回の控え（返答・却下・指示・止め）は入口が名で消す。ほかの物の名のファイルは消さない"""
        self.written()
        self.assertFalse(self.take("write", write_reply("none.txt"))["ok"])
        self.prep("write")
        (self.place / "other.json").write_text("{}", encoding="utf-8")
        (self.place / "rejects-other.json").write_text("[]", encoding="utf-8")
        self.steps.files.write_stop(self.place, "works:spec", "古い止め")
        self.assertTrue(self.intake()["go"])
        for name in ("spec-write.json", "rejects-spec-write.json", "candidate-spec-write.json", "stop.json", "spec-write-prompt-1.md",
                     "spec-snapshot-spec.review.json"):
            self.assertFalse((self.place / name).exists(), name)
        for name in ("other.json", "rejects-other.json"):
            self.assertTrue((self.place / name).is_file(), name)
        self.assertFalse(self.prep("write")["prompt"].startswith("## "), "古い却下は次の指示に届かない")
        self.assertTrue((self.place / "spec-write-prompt-1.md").is_file())

    def test_unreadable_request_still_clears_the_old_files(self):
        """依頼が読めなくても、前の回の自分のファイルは先に消える（古い答えが残らない）"""
        self.place.mkdir(parents=True, exist_ok=True)
        for name in ("spec-write.json", "spec.json", "stop.json"):
            (self.place / name).write_text('{"stale": true}', encoding="utf-8")
        got = self.intake(request="not json")
        self.assertIs(got["go"], False)
        self.assertFalse((self.place / "spec-write.json").exists())
        self.assertFalse((self.place / "spec.json").exists())
        self.assertNotIn("stale", self.read("stop.json"))

    def test_check_does_not_clear_the_place(self):
        self.written()
        self.assertEqual(self.intake(mode="check"), {"mode": "check", "go": True, "reason": ""})
        self.assertTrue((self.place / "spec-write.json").is_file())

    def test_unreadable_port_stops_with_works_spec(self):
        for raw in (self.run.pointer("absent.json"), '{"rows": 1}', "", '[{"where": "x"}]'):
            with self.subTest(raw=raw):
                got = self.intake(request=raw)
                self.assertFalse(got["go"])
                self.assertIn("仕様の段の支度が落ちた", got["reason"])
                self.assertIn("入力 request", got["reason"])
                self.assertEqual(self.read("stop.json")["stop_reason"], "works:spec")
                out = self.finish()
                self.assertEqual((out["ok"], out["status"], out["stop_reason"]), (False, "failed", "works:spec"))
                self.assertEqual((out["spec"], out["added_rows"]), (None, None))
                self.assertIn(got["reason"], out["reason"])
                self.setUp()

    def test_unknown_mode_stops(self):
        got = self.intake(mode="nope")
        self.assertEqual((got["go"], got["mode"]), (False, ""))
        self.assertIn("入力 mode", got["reason"])
        self.assertEqual(self.finish()["status"], "failed")


class ErrorsCase(_Case):
    def errors(self, spec):
        return self.steps.take.spec_errors(spec, self.run.repo)

    def test_acceptance_without_gwt_rejected(self):
        self.write_tests("def test_mean_is_middle():\n    assert False\n")
        with self.assertRaises(self.steps.take.Reject) as cm:
            self.steps.take.write_output(write_reply(), self.run.repo)
        self.assertIn("Given/When/Then", str(cm.exception))
        self.assertTrue(str(cm.exception).startswith("spec.write: "))

    def test_missing_test_file_and_name_rejected(self):
        with self.assertRaises(self.steps.take.Reject) as cm:
            self.steps.take.write_output(write_reply(file="missing_test.txt"), self.run.repo)
        self.assertIn("missing_test.txt", str(cm.exception))
        self.write_tests(TEST_TEXT.replace("test_mean_is_middle", "test_other"))
        with self.assertRaises(self.steps.take.Reject) as cm:
            self.steps.take.write_output(write_reply(), self.run.repo)
        self.assertIn("name 'test_mean_is_middle'", str(cm.exception))

    def test_keys_unique_and_point_to_requirements(self):
        self.write_tests()
        spec = write_reply()
        spec["requirements"] += [{"key": "R1", "text": "同じ鍵の要件"}, {"key": "R2", "text": "受け入れ条件の無い要件"}]
        spec["acceptance"].append({**spec["acceptance"][0], "key": "A2", "requirement": "R9"})
        errs = self.errors(spec)
        self.assertTrue(any("requirements[1] の key が重複" in e for e in errs), errs)
        self.assertTrue(any("'R9' が requirements に無い" in e for e in errs), errs)
        self.assertTrue(any("要件 'R2' に受け入れ条件が無い" in e for e in errs), errs)
        self.assertEqual(self.errors(write_reply()), [])

    def test_review_needs_faces_none(self):
        take = self.steps.take
        take.review_output(review_reply())
        take.review_output(review_reply(faces=False))
        with self.assertRaises(take.Reject) as cm:
            take.review_output({"faces": [], "faces_none": "無い", "reason": "x" * 20})
        self.assertIn("faces_none", str(cm.exception))

    def test_revise_answers_each_face_once(self):
        take = self.steps.take
        self.write_tests()
        take.revise_output(revise_reply(), review_reply(), self.run.repo)
        bad = revise_reply()
        bad["handled"] = [{"key": "F9", "handled": "absorbed", "how": "x" * 20}]
        with self.assertRaises(take.Reject) as cm:
            take.revise_output(bad, review_reply(), self.run.repo)
        self.assertIn("'F9' は仕様の審査に無い", str(cm.exception))
        self.assertIn("'F1' に応答が無い", str(cm.exception))

    def test_revise_checks_the_revised_spec_too(self):
        """直した仕様のテストのファイルが読めなければ拒む（直す役も書く役と同じ照らし）"""
        take = self.steps.take
        self.write_tests()
        bad = revise_reply()
        bad["spec"] = write_reply(file="gone_test.txt")
        with self.assertRaises(take.Reject) as cm:
            take.revise_output(bad, review_reply(), self.run.repo)
        self.assertIn("gone_test.txt", str(cm.exception))

    def test_review_faces_keys_unique(self):
        take = self.steps.take
        bad = review_reply()
        bad["faces"] = [FACE, {**FACE, "why": "同じ鍵の 2 つ目の穴。空の列の平均をどう扱うかが決まっていない"}]
        with self.assertRaises(take.Reject) as cm:
            take.review_output(bad)
        self.assertIn("faces[1] の key が重複", str(cm.exception))

    def test_revise_handled_keys_unique(self):
        take = self.steps.take
        self.write_tests()
        bad = revise_reply()
        bad["handled"] = bad["handled"] * 2
        with self.assertRaises(take.Reject) as cm:
            take.revise_output(bad, review_reply(), self.run.repo)
        self.assertIn("handled[1] の key が重複", str(cm.exception))

    def test_revise_due_only_with_faces(self):
        self.assertTrue(self.steps.take.revise_due(review_reply()))
        self.assertFalse(self.steps.take.revise_due(review_reply(faces=False)))


class TakeCase(_Case):
    def test_review_is_read_only(self):
        """審査の役が作業ツリーを変えたら拒む。元に戻せば通る"""
        self.written()
        (self.run.repo / "note.txt").write_text("x\n", encoding="utf-8")
        got = self.take("review", review_reply())
        self.assertFalse(got["ok"])
        self.assertIn("読むだけの役が作業ツリーを変えた", got["reason"])
        (self.run.repo / "note.txt").unlink()
        got = self.take("review", review_reply())
        self.assertEqual((got["ok"], got["revise"]), (True, True), "穴が開いた審査は直す輪を回す")
        self.assertEqual(self.read("spec-review.json"), review_reply())

    def test_review_without_a_snapshot_is_rejected(self):
        self.intake()
        got = self.take("review", review_reply())
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーの写し", got["reason"])

    def test_review_without_faces_skips_revise(self):
        self.written()
        got = self.take("review", review_reply(faces=False))
        self.assertEqual((got["ok"], got["revise"]), (True, False))

    def test_bad_shape_is_a_reject_not_a_crash(self):
        self.intake()
        for reply in ({"requirements": "x"}, [], "x", {}):
            with self.subTest(reply=reply):
                got = self.take("write", reply)
                self.assertFalse(got["ok"])
                self.assertTrue(got["reason"])
        got = self.steps.take.take(self.place, "nope", {}, self.run.repo)
        self.assertFalse(got["ok"])

    def test_revise_replaces_the_spec(self):
        self.reviewed()
        self.assertEqual(self.steps.take.current(self.place), revise_reply()["spec"])

    def test_unparsable_reply_is_a_reject(self):
        self.intake()
        out = self.run.script("take", role="write", status_guarded="false", reply="not json", fix_reply="null")
        self.assertFalse(out["ok"])
        self.assertIn("JSON として読めない", out["reason"])

    def test_three_rejects_give_up_and_the_ask_stays_closed(self):
        self.intake()
        for i in range(3):
            got = self.take("write", write_reply("missing.txt"))
            self.assertEqual((got["ok"], got["done"]), (False, i == 2))
        self.assertEqual(self.run.script("ask"), {"ask": False, "message": ""})
        stop = self.read("stop.json")
        self.assertEqual(stop["stop_reason"], "works:spec")
        self.assertIn("3 回とも", stop["reason"])
        self.assertEqual(self.run.script("freeze", answer="null"), {"go": False, "reason": stop["reason"]}, "承認ノードは開かなかった")
        out = self.finish()
        self.assertEqual((out["status"], out["stop_reason"], out["spec"]), ("failed", "works:spec", None))
        self.assertEqual(out["report"], [f"仕様: 固まらなかった（{stop['reason']}）"])


class ResubmitCase(_Case):
    def rejected_once(self):
        self.intake()
        got = self.take("write", write_reply("missing.txt"))
        self.assertFalse(got["ok"])
        return got

    def test_prep_resubmits_only_after_a_reject_with_a_candidate(self):
        self.intake()
        self.assertFalse(self.prep("write", prev="false")["resubmit"], "控えが無ければ 1 回目の役")
        self.rejected_once()
        self.assertEqual(self.prep("write", prev="false"), {"prompt": "", "resubmit": True})
        for prev in ("", "true", "null"):
            with self.subTest(prev=prev):
                self.assertFalse(self.prep("write", prev=prev)["resubmit"], "resume で輪が 1 周目から回し直した時は新しい会話")

    def test_fix_prompt_carries_the_last_reject_and_the_candidate(self):
        self.rejected_once()
        text = self.fix_prep("write")["prompt"]
        reason = self.read("rejects-spec-write.json")[-1]["reason"]
        self.assertIn(reason, text)
        self.assertIn(str(self.place / "candidate-spec-write.json"), text)
        self.assertNotRegex(text, r"\{[a-z0-9_]+\}")
        self.assertTrue((self.place / "spec-write-fix-prompt-1.md").is_file())

    def test_fix_reply_is_merged_with_the_candidate(self):
        """出し直しの返答は直す欄だけ。前の答えの控えと合わせて照らす（返さない欄は前のまま）"""
        self.rejected_once()
        self.write_tests()
        fixed = {"acceptance": write_reply()["acceptance"]}
        got = self.run.script("take", role="write", status_guarded="false", reply="null", fix_reply=json.dumps(fixed))
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.read("spec-write.json"), write_reply())

    def test_fix_reply_after_fixing_only_the_file_returns_nothing(self):
        """テストのファイルだけを直した出し直しは欄を返さない（{}）。前の答えのまま照らし直して通る"""
        self.intake()
        self.assertFalse(self.take("write", write_reply())["ok"], "テストのファイルがまだ無い")
        self.write_tests()
        got = self.run.script("take", role="write", status_guarded="false", reply="null", fix_reply="{}")
        self.assertTrue(got["ok"], got)

    def test_third_fresh_role_reads_every_reject_of_the_loop(self):
        self.intake()
        for i in range(2):
            self.take("write", write_reply(f"missing{i}.txt"))
        text = self.prep("write")["prompt"]
        self.assertIn("missing0.txt", text)
        self.assertIn("missing1.txt", text)

    def test_unreadable_fix_reply_without_a_candidate_is_a_reject(self):
        self.intake()
        got = self.run.script("take", role="write", status_guarded="false", reply="null", fix_reply="{}")
        self.assertFalse(got["ok"])


class StopCase(_Case):
    def test_stop_words_are_human_stops(self):
        for decision, text, want in (("stop", "受け入れ条件が弱い", "human:spec-gate"), ("reject", "", "human:spec-gate"),
                                     ("reject", "request: 札", "request:spec-gate"), ("stop", "request:札", "request:spec-gate")):
            with self.subTest(decision=decision, text=text):
                self.setUp()
                self.asked(faces=False)
                got = self.freeze(decision, text)
                self.assertIs(got["go"], False)
                stop = self.read("stop.json")
                self.assertEqual(stop["stop_reason"], want)
                self.assertIn(text or self.steps.files.GATE_STOP_NOTE, stop["reason"])
                self.assertFalse((self.place / "spec.json").exists())
                out = self.finish()
                self.assertEqual((out["ok"], out["status"], out["stop_reason"]), (False, "stopped", want))
                self.assertEqual((out["spec"], out["added_rows"], out["added_origin"]), (None, None, ""))
                self.assertEqual(out["report"], [f"仕様: 人が承認ノードで止めた: {text or self.steps.files.GATE_STOP_NOTE}"])

    def test_gate_skipped_stops_with_works_spec(self):
        self.intake()
        for _ in range(3):
            self.take("write", write_reply("missing.txt"))
        self.run.script("ask")
        got = self.run.script("freeze", answer="null")
        self.assertIs(got["go"], False)
        self.assertEqual(self.read("stop.json")["stop_reason"], "works:spec")

    def test_gate_skipped_without_a_stop_record_writes_one(self):
        self.intake()
        got = self.run.script("freeze", answer="")
        self.assertIs(got["go"], False)
        self.assertEqual(self.read("stop.json"), {"stop_reason": "works:spec", "reason": "仕様の承認ノードが開かなかった（仕様が固まっていない）"})

    def test_unknown_word_and_unreadable_answer(self):
        self.asked(faces=False)
        for answer in ('{"decision": "maybe", "text": ""}', "not json", "[1]"):
            with self.subTest(answer=answer):
                got = self.run.script("freeze", answer=answer)
                self.assertIs(got["go"], False)
                self.assertTrue(got["reason"])
                self.assertEqual(self.read("stop.json")["stop_reason"], "works:spec")
                (self.place / "stop.json").unlink()
        self.assertIn("maybe", self.run.script("freeze", answer='{"decision": "maybe", "text": ""}')["reason"])

    def test_ask_before_the_spec_is_ready_stops(self):
        self.written()
        got = self.run.script("ask")
        self.assertEqual(got, {"ask": False, "message": ""})
        self.assertIn("spec.review", self.read("stop.json")["reason"])

    def test_ask_with_faces_but_no_revise_reply_stops_without_opening(self):
        self.written()
        self.take("review", review_reply())
        got = self.run.script("ask")
        self.assertEqual(got, {"ask": False, "message": ""})
        self.assertIn("spec.revise", self.read("stop.json")["reason"])
        self.assertFalse((self.place / "spec-ask.json").exists())

    def test_answer_without_the_ask_record_stops_with_works_spec(self):
        self.asked(faces=False)
        (self.place / "spec-ask.json").unlink()
        got = self.freeze("approve")
        self.assertIs(got["go"], False)
        self.assertEqual(self.read("stop.json")["stop_reason"], "works:spec")
        self.assertIn("spec-ask.json", self.read("stop.json")["reason"])
        self.assertFalse((self.place / "spec.json").exists())

    def test_ask_that_cannot_build_the_text_is_a_works_spec_stop(self):
        self.reviewed()
        spec = self.read("spec-revise.json")
        spec["spec"]["acceptance"][0].pop("run")
        (self.place / "spec-revise.json").write_text(json.dumps(spec), encoding="utf-8")
        self.assertEqual(self.run.script("ask"), {"ask": False, "message": ""})
        self.assertIn("仕様の承認ノードの文を組めない", self.read("stop.json")["reason"])
        self.assertEqual(self.finish()["status"], "failed")

    def test_finish_without_the_run_reaching_anything_says_so(self):
        self.intake()
        out = self.finish()
        self.assertEqual((out["status"], out["stop_reason"], out["reason"]), ("failed", "works:spec", "仕様の段が最後まで回らなかった"))

    def test_finish_without_intake_still_returns(self):
        out = self.finish()
        self.assertEqual((out["ok"], out["status"]), (False, "failed"))
        self.assertIn("入口", out["reason"])

    def test_freeze_that_cannot_run_is_a_works_spec_stop(self):
        self.asked(faces=False)
        spec = self.read("spec-ask.json")
        spec["pending"]["acceptance"][0]["requirement"] = "R404"
        (self.place / "spec-ask.json").write_text(json.dumps(spec), encoding="utf-8")
        got = self.freeze()
        self.assertFalse(got["go"])
        self.assertIn("仕様を固められない", got["reason"])
        self.assertEqual(self.read("stop.json")["stop_reason"], "works:spec")
        self.assertFalse((self.place / "spec.json").exists())


class CheckCase(_Case):
    """修正の後の承認し直すかの問い"""

    def frozen(self):
        self.asked(faces=False)
        self.assertTrue(self.freeze()["go"])
        return self.place / "spec.json"

    def check(self, path=None):
        spec = str(path) if path else ""
        self.intake(mode="check")
        return self.run.script("check", spec=spec)

    def test_unchanged_is_no_question(self):
        out = self.check(self.frozen())
        self.assertEqual(out, {"questions": [], "unchecked": False})
        done = self.finish(json.dumps(out))
        self.assertEqual((done["ok"], done["status"], done["questions"], done["unchecked"]), (True, "checked", [], False))
        self.assertEqual(done["report"], ["仕様: 承認した受け入れ条件のテストは承認の版のまま"])

    def test_changed_acceptance_file_is_a_question(self):
        path = self.frozen()
        was = self.read("spec.json")["acceptance"][0]["sha256"]
        self.write_tests(TEST_TEXT + "\n# 弱めた\n")
        out = self.check(path)
        self.assertIs(out["unchecked"], False)
        self.assertEqual(len(out["questions"]), 1, out)
        for part in (TEST_FILE, was[:12], "spec_changed", "承認し直すか"):
            self.assertIn(part, out["questions"][0])
        done = self.finish(json.dumps(out))
        self.assertEqual((done["ok"], done["status"], done["stop_reason"]), (True, "checked", ""), "止めるかは graph が決める")
        self.assertEqual(done["questions"], out["questions"])
        self.assertEqual(done["report"][0], "仕様: 承認し直すかの問い 1 件")

    def test_pointer_is_accepted(self):
        self.frozen()
        self.assertEqual(self.check(self.run.pointer("spec.json")), {"questions": [], "unchecked": False})

    def test_deleted_file_says_gone(self):
        path = self.frozen()
        (self.run.repo / TEST_FILE).unlink()
        got = self.check(path)["questions"]
        self.assertEqual(len(got), 1, got)
        self.assertIn("消えた", got[0])

    def test_unmeasurable_file_says_why_not_gone(self):
        path = self.frozen()
        (self.run.repo / TEST_FILE).unlink()
        (self.run.repo / TEST_FILE).mkdir()
        got = self.check(path)["questions"]
        self.assertEqual(len(got), 1, got)
        self.assertIn("通常のファイルでない", got[0])
        self.assertNotIn("消えた", got[0])

    def test_same_file_counted_once(self):
        path = self.frozen()
        spec = self.read("spec.json")
        spec["acceptance"].append({**spec["acceptance"][0], "key": "A2", "name": "test_other"})
        path.write_text(json.dumps(spec), encoding="utf-8")
        self.write_tests(TEST_TEXT + "\n# 弱めた\n")
        self.assertEqual(len(self.check(path)["questions"]), 1)

    def test_unreadable_spec_is_a_question_not_silence(self):
        path = self.place / "spec.json"
        for text in ("{壊れた", json.dumps({"requirements": []}), json.dumps([1])):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                out = self.check(path)
                self.assertIs(out["unchecked"], True)
                self.assertEqual(len(out["questions"]), 1, out)
                self.assertIn("読めない", out["questions"][0])
        path.unlink()
        out = self.check(path)
        self.assertIs(out["unchecked"], True)
        self.assertIn("照らしが落ちた", out["questions"][0], "無いファイルは入力の口が名指して落ちる")

    def test_no_spec_given_is_a_question(self):
        out = self.check()
        self.assertEqual(out, {"questions": [self.steps.check.NO_SPEC], "unchecked": True})
        done = self.finish(json.dumps(out))
        self.assertEqual((done["ok"], done["status"], done["unchecked"]), (False, "unchecked", True))
        self.assertEqual(done["report"][0], "仕様: 受け入れ条件のテストが変わったかを照らせなかった")
        self.assertEqual(done["stop_reason"], "")

    def test_check_without_a_result_is_unchecked(self):
        self.intake(mode="check")
        done = self.finish("null")
        self.assertEqual((done["ok"], done["status"], done["unchecked"]), (False, "unchecked", True))
        self.assertIn("照らしが落ちた", done["questions"][0])


class PromptCase(_Case):
    """prep が md から組む指示（決まった文は md が持ち、prep は材料と値だけを渡す）"""

    RULE = "Rules for queries to outside services"

    def text(self, role, **intake):
        self.intake(**intake)
        if role != "write":
            self.write_tests()
            self.assertTrue(self.take("write", write_reply())["ok"])
        if role == "revise":
            self.assertTrue(self.take("review", review_reply())["ok"])
        return self.prep(role)["prompt"]

    def test_first_round_prompts_have_no_rejection_and_no_open_slot(self):
        heads = {"write": "You are the spec writer.", "review": "You are the spec reviewer.", "revise": "You are the spec reviser."}
        for role, head in heads.items():
            with self.subTest(role=role):
                self.setUp()
                text = self.text(role)
                self.assertIn(head, text)
                self.assertNotIn("## Why your previous answer was rejected", text)
                self.assertNotIn("If the rejection says", text)
                self.assertNotIn("sub-agent", text, "この block の役は下請けを起こさない（段落 spawns は入れない）")
                self.assertEqual(text.count(self.RULE), 1, "検索の決まりは 1 度だけ")
                self.assertNotRegex(text, r"\{[a-z0-9_]+\}")
                self.assertIn("the language of the request (the user's language)", text, "lang が空なら既定の言語の文")
                self.assertIn(str(self.place / "request.json"), text)

    def test_language_is_the_port_value(self):
        self.assertIn("in Japanese", self.text("write", lang="Japanese"))

    def test_rejections_come_first_and_the_file_hint_is_the_writers_only(self):
        for role in ("write", "revise"):
            with self.subTest(role=role):
                self.setUp()
                self.text(role)
                bad = write_reply("missing.txt") if role == "write" else {**revise_reply(), "handled": []}
                self.assertFalse(self.take(role, bad)["ok"])
                again = self.prep(role)["prompt"]
                self.assertTrue(again.startswith("## Why your previous answer was rejected"), again[:80])
                self.assertIn(self.read(f"rejects-spec-{role}.json")[0]["reason"], again)
                self.assertEqual("fix the test file in the target repository first" in again, role == "write")

    def test_pr_text_reaches_the_three_roles_and_only_when_given(self):
        """PR の題と本文だけで仕様の段を選んだ run でも、役は PR の文を読める（無ければ節ごと入らない）"""
        pr = "#7 題 T\n\n本文X {not_a_slot} $LOOP"
        for role in ("write", "review", "revise"):
            with self.subTest(role=role):
                self.setUp()
                text = self.text(role, pr_text=pr)
                self.assertIn("## Pull request", text)
                self.assertIn(pr, text, "入れた値の中の字は読み直さない")
                self.setUp()
                self.assertNotIn("## Pull request", self.text(role))
                self.assertNotIn("## Pull request", self.text(role, pr_text="  \n"), "空白だけは PR が無い")

    def test_revise_prompt_tells_the_minimum_length_of_how(self):
        self.assertIn(f"`how` is at least {self.steps.files.MIN_HOW} characters", self.text("revise"))

    def test_review_prompt_takes_the_words_the_answer_form_checks(self):
        text = self.text("review")
        for word in self.steps.files.FACE_KINDS:
            self.assertIn(f"`{word}`", text)
        self.assertIn(f"at least {self.steps.files.MIN_WHY} characters", text)
        self.assertIn(f"at least {self.steps.files.MIN_REASON} characters", text)
        self.assertIn(str(self.place / "spec-write.json"), text)
        self.assertIn("You are the judge", text, "役の定義の断片")

    def test_revise_prompt_takes_the_answer_words_and_both_files(self):
        text = self.text("revise")
        for word in self.steps.files.HANDLED:
            self.assertIn(f"`{word}`", text)
        self.assertIn(str(self.place / "spec-write.json"), text)
        self.assertIn(str(self.place / "spec-review.json"), text)

    def test_fix_prompt_is_the_shared_paragraph(self):
        self.intake()
        self.take("write", write_reply("missing.txt"))
        text = self.fix_prep("write")["prompt"]
        self.assertTrue(text.startswith("Your previous answer was rejected by the machine's check."), text[:60])
        self.assertIn("return `{}`", text, "二重の波括弧は字の {} になる")
        for role in ("review", "revise"):
            self.assertEqual((BLOCK / "prompts" / f"spec-{role}-fix.md").read_text(encoding="utf-8"), "{shared:resubmit}\n")


class ShapeCase(unittest.TestCase):
    """YAML と block の揃い"""

    def test_gate_is_an_approval_with_the_four_words(self):
        gate = nodes()["spec-gate"]
        self.assertEqual([o["id"] for o in gate["wait"]["options"]], ["approve", "continue", "stop", "reject"])
        self.assertEqual(gate["wait"]["form"], "select")

    def test_freeze_may_change_the_checkout(self):
        """受け入れ条件のコマンドを走らせる node は作業ツリーを変えうる。mutates_checkout: false を書かない"""
        self.assertNotIn("mutates_checkout", nodes()["spec-freeze"])

    def test_loops_give_up_where_the_accept_does(self):
        rolekit = kit.load("spec", "steps").rolekit
        for role in ("write", "review", "revise"):
            loop = nodes()[f"spec-{role}-loop"]["loop_group"]
            self.assertEqual(loop["max_iterations"], rolekit.GIVE_UP_AFTER)
            self.assertEqual(loop["until_bash"], f'done=$spec-{role}-accept.output.done; test "$done" = true')

    def test_read_only_roles_cannot_write(self):
        ns = nodes()
        for name in ("spec-review", "spec-review-fix"):
            self.assertEqual(ns[name]["mutates_checkout"], False)
            self.assertFalse({"Edit", "Write", "Bash"} & set(ns[name]["allowed_tools"]), name)
            self.assertEqual(ns[name]["model"], "@wf-judge-core")
        for name in ("spec-write", "spec-write-fix", "spec-revise", "spec-revise-fix"):
            self.assertLessEqual({"Edit", "Write", "Bash"}, set(ns[name]["allowed_tools"]), name)
            self.assertNotIn("mutates_checkout", ns[name], "Edit・Write・Bash を持つ役は印を書かない")
            self.assertEqual(ns[name]["model"], "@wf-judge-spec")

    def test_accept_settings(self):
        ns = nodes()
        want = {"write": "false", "review": "true", "revise": "false"}
        for role, guarded in want.items():
            with_ = ns[f"spec-{role}-accept"]["with"]
            self.assertEqual((with_["role"], str(with_["status_guarded"]).lower()), (role, guarded))
            self.assertEqual(ns[f"spec-{role}-prep"]["with"]["role"], role)
            self.assertEqual(ns[f"spec-{role}-fix-prep"]["with"]["role"], role)

    def test_output_enums_match_the_words_the_md_takes(self):
        files = kit.load("spec", "files")
        props = nodes()["spec-review"]["output_format"]["properties"]["faces"]["items"]["properties"]
        self.assertEqual(tuple(props["kind"]["enum"]), files.FACE_KINDS)
        self.assertEqual(props["why"]["minLength"], files.MIN_WHY)
        self.assertEqual(nodes()["spec-review"]["output_format"]["properties"]["reason"]["minLength"], files.MIN_REASON)
        handled = nodes()["spec-revise"]["output_format"]["properties"]["handled"]["items"]["properties"]
        self.assertEqual(tuple(handled["handled"]["enum"]), files.HANDLED)
        self.assertEqual(handled["how"]["minLength"], files.MIN_HOW)

    def test_fix_roles_return_only_what_they_fix(self):
        ns = nodes()
        for role in ("write", "review", "revise"):
            self.assertEqual(ns[f"spec-{role}-fix"]["output_format"]["required"], [])
            self.assertTrue(ns[f"spec-{role}"]["output_format"]["required"])

    def test_no_parallel_layer_before_a_conversation_continuing_role(self):
        """出し直しの役の前に並んだ層が在ると会話が切れる（#571）"""
        from tests.workflows.test_loop_sessions import layers, parallel_before_role
        for role in ("write", "review", "revise"):
            group = nodes()[f"spec-{role}-loop"]
            with self.subTest(role=role):
                self.assertEqual(parallel_before_role(group), [])
                self.assertEqual([len(x) for x in layers(group["loop_group"]["nodes"])], [1] * 5)

    def test_md_per_ai_node(self):
        ai = {n for n, node in nodes().items() if "prompt" in node}
        self.assertEqual(ai, {f"spec-{r}{fix}" for r in ("write", "review", "revise") for fix in ("", "-fix")})
        self.assertEqual({p.stem for p in (BLOCK / "prompts").glob("*.md")}, ai)

    def test_inputs_are_the_ports_of_the_sheet(self):
        self.assertEqual(list(doc()["inputs"]), ["mode", "request", "pr_text", "spec", "user_env_dir", "lang"])
        self.assertEqual(doc()["outcome_field"], "ok")


class ReportCase(unittest.TestCase):
    def test_lines(self):
        report = kit.load("spec", "report")
        spec = {"requirements": [{"key": "R1"}], "acceptance": [
            {"key": "A1", "requirement": "R1", "file": "t.py", "name": "n1", "exit_at_approval": 0},
            {"key": "A2", "requirement": "R1", "file": "t.py", "name": "n2", "exit_at_approval": None, "run_error": "OSError: x"},
            {"key": "A3", "requirement": "R1", "file": "t.py", "name": "n3", "exit_at_approval": 2}], "approval": {"note": ""}}
        self.assertEqual(report.approved(spec), [
            "仕様: 要件 1 件・受け入れ条件 3 件を人が承認した",
            "- A1（要件 R1）: t.py の n1——承認の時 既に緑（赤を見ていない）",
            "- A2（要件 R1）: t.py の n2——承認の時 走らない（OSError: x）",
            "- A3（要件 R1）: t.py の n3——承認の時 exit 2"])
        self.assertEqual(report.stopped("要らない"), ["仕様: 人が承認ノードで止めた: 要らない"])


if __name__ == "__main__":
    unittest.main()
