"""block r1 を、script を子のプロセスで回して確かめる（docs/design/r1.md の 8 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → comments_prep → 台本の返答 → save →
minimality_prep → 台本の返答 → save → finish と回す。元の tests/workflows の test_eyes.py の ScriptCase と test_eyeverdict.py
の R1 の場面を、port の値で作り直した（各試験の docstring に元の試験の名を書く）。筋書きを Archon の workflow test で回すのは
tests/layers/test_block_shape.py。keep-essence の 9（独立設計と R1〜R4）の R1 の守りは、役が別の会話・読むだけ（test_r1_shape.py）と、
材料が修正の会話を持たないこと（test_inputs_carry_no_fix_conversation）が縛る。
"""
import json
import pathlib
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "r1"
DOC = yaml.safe_load((BLOCK / "works-factory-r1.yaml").read_text(encoding="utf-8"))
PORTS = ["base", "purpose", "units", "judgment", "fixes", "x_scalars", "green", "checks", "after", "review", "policy", "lang"]
COMMENTS = {"candidates": [{"where": "a.txt:1", "comment": "# 入口", "same_content_at": "README.md:1", "reason": "見出しの言い直し"}],
            "kept": [{"where": "a.txt:3", "fact": "既定の値を選んだ訳"}]}
PASS = {"status": "pass", "reason": "最小", "deletions": [], "ledger_audit": [], "increments": []}
AFTER = {"changed": ["a.txt"], "tables": [], "new_names": [{"name": "x", "sites": 2}], "dup_blocks_added": 2}
DEVIATION = {"item": 2, "row": "u2", "deviation": "入口を 2 つ残す（呼び手が別のリポジトリに在る）"}


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "r1")
        self.repo = self.run.repo
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.place = self.run.artifacts
        self.eyekit = kit.load("r1", "steps").eyekit

    def intake(self, **inputs):
        return self.run.script("intake", **{"base": self.base, **inputs})

    def comments(self):
        return self.run.script("comments_prep")["prompt"]

    def minimality(self):
        return self.run.script("minimality_prep")["prompt"]

    def save(self, name, reply):
        # 欄 name は Run.script の引数の名と重なるので、大文字の鍵で渡す（INPUTS_NAME になる）
        return self.run.script("save", NAME=name, reply=reply if isinstance(reply, str) else dump(reply))

    def finish(self):
        return self.run.script("finish")

    def write(self, name, text) -> pathlib.Path:
        path = self.run.artifacts.parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def intake_json(self) -> dict:
        return json.loads((self.place / "intake.json").read_text(encoding="utf-8"))


class ShapeCase(unittest.TestCase):
    def test_inputs_carry_no_fix_conversation(self):
        """keep-essence の 9 の R1: 入力は差分の根・目的・単位・台帳・結末・規模・証拠・実測・審査の結論・方針・言語だけで、修正の会話を
        運ぶ port が無い（目は材料だけで判じる）"""
        self.assertEqual(list(DOC["inputs"]), PORTS)


class PortCase(_RepoCase):
    def test_malformed_x_scalars_are_refused_at_the_port(self):
        """規模の数値の形は名 x_<小文字> と数の値を宣言する（#861。持ち主の答え「型は決まるでしょ」）。object でない値・形の外の欄・
        数でない値は入口 ports.json が落とし、R1 の目は回らない（due: false と訳）。形で照らさずに読んでも、ほかの試験は赤にならない"""
        for raw in ("[1]", dump({"endpoints": 2, "x_ok": 1}), dump({"x_ok": "2"})):
            with self.subTest(raw):
                got = self.intake(x_scalars=raw)
                self.assertFalse(got["due"])
                self.assertIn("入力 x_scalars", got["reason"])
        self.assertTrue(self.intake(x_scalars=dump({"x_ok": 1}))["due"])


class FlowCase(_RepoCase):
    def test_flow_reaches_the_verdict_and_the_report(self):
        """筋: 2 つの役が返り、pass の判定の行と、削るとした所・残したコメントの事実の行を報告に出す"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        self.assertEqual(self.intake(purpose="古い入口を消す"), {"due": True, "reason": ""})
        self.assertIn("You are a meticulous code comment analyzer", self.comments())
        self.assertEqual(self.save("r1-comments", COMMENTS), {"saved": True})
        text = self.minimality()
        self.assertIn(f"Read `{self.place / 'r1-comments.json'}`", text)
        reply = {**PASS, "status": "fix-needed", "reason": "写しが在る", "deletions": [{"where": "a.txt:2", "why": "b.py:9 に同じ\n内容"}]}
        self.save("r1-minimality", reply)
        done = self.finish()
        self.assertEqual(done, {"ok": True, "status": "ran", "reason": "", "verdict": {"status": "fix-needed", "reason": "写しが在る"},
                                "questions": [], "findings": [{"where": "a.txt:2", "text": "b.py:9 に同じ 内容"}], "report": ["R1: fix-needed（写しが在る）", "  - 削るとした所: a.txt:2（b.py:9 に同じ 内容）",
                                                            "  - 残したコメントが運ぶ事実: a.txt:3: 既定の値を選んだ訳"]})
        self.assertEqual(json.loads((self.place / "finish.json").read_text(encoding="utf-8")), done)

    def test_save_reply_writes_the_reply(self):
        """test_save_reply_writes_the_reply"""
        self.assertEqual(self.save("r1-comments", COMMENTS), {"saved": True})
        self.assertEqual(json.loads((self.place / "r1-comments.json").read_text(encoding="utf-8")), COMMENTS)

    def test_save_refuses_an_unknown_name(self):
        err = self.run.failing("save", NAME="r2-compare", reply=dump(PASS))
        self.assertIn("r2-compare", err)
        self.assertFalse((self.place / "r2-compare.json").exists())

    def test_minimality_runs_without_the_comment_candidates(self):
        """test_r1_minimality_runs_without_the_comment_candidates: 前段の返答が無い道は「取れなかった」の段落を持ち、報告にもそう書く"""
        self.intake()
        text = self.minimality()
        self.assertIn("could not be taken. Write why in the string field `candidates_note`", text)
        self.assertNotIn("Read `", text.split("could not be taken")[0].splitlines()[-1])
        self.assertIn("do not set `status` to unverifiable only because the earlier step is missing", text)
        self.save("r1-minimality", {**PASS, "candidates_note": "前段が無い"})
        done = self.finish()
        self.assertEqual(done["report"], ["R1: pass（最小）", "  - コメントの削除候補は取れなかった（出力のファイルが無い）"])

    def plant_old_files(self) -> dict:
        """この block が名を持つファイルの全部（と前の回の指示）を「前の run の物」の字で置く"""
        files = kit.load("r1", "files")
        old = {name: self.place / name for name in files.OWN_FILES}
        old.update({p.replace("*", "1"): self.place / p.replace("*", "1") for p in files.OWN_PROMPTS})
        for path in old.values():
            path.write_text("old", encoding="utf-8")
        return old

    def test_intake_clears_only_its_own_files(self):
        """入口は src/files.py が名を持つファイルの全部と前の回の指示を消し（書き直す物は新しい字）、ほかのファイルは残す"""
        old = self.plant_old_files()
        other = self.place / "rejects-other.json"
        other.write_text("[]", encoding="utf-8")
        self.intake()
        for name, path in old.items():
            with self.subTest(name):
                self.assertFalse(path.is_file() and path.read_text(encoding="utf-8") == "old", name)
        self.assertTrue(other.exists())

    def test_intake_that_cannot_read_lib_still_clears_its_files(self):
        """lib を読めずに落ちた入口も、この block のファイルを名で消して落ちた訳を返す"""
        import subprocess
        import sys
        from tests.bin import hermetic
        old = self.plant_old_files()
        env = hermetic.child_env(**{**self.run.environ(), "WORKS_FACTORY_ROOT": str(self.run.artifacts.parent / "no-lib")})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / "intake.py")], cwd=self.repo, env=env, capture_output=True,
                              text=True, encoding="utf-8")
        got = json.loads(done.stdout)
        self.assertFalse(got["due"])
        self.assertIn("R1 の入口が落ちた", got["reason"])
        self.assertEqual([n for n, p in old.items() if p.exists()], [])
        self.assertEqual(self.finish()["status"], "failed")


class DiffCase(_RepoCase):
    def test_no_fix_round_sees_the_requested_change(self):
        """test_no_fix_round_sees_the_requested_change・test_prep_takes_the_diff_from_the_entry_base: 目は port base からの累積差分を読む"""
        (self.repo / "a.txt").write_text("頼まれた変更\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "requested")
        self.intake()
        diff = self.intake_json()["diff"]
        self.assertEqual((diff["base"], diff["changed"]), (self.base, ["a.txt"]))
        self.assertEqual(pathlib.Path(diff["file"]), self.place / "run.diff")
        self.assertIn("+頼まれた変更", (self.place / "run.diff").read_text(encoding="utf-8"))
        self.assertGreater(diff["lines"], 0)
        text = self.comments()
        self.assertIn(f"Cumulative diff: `{self.place / 'run.diff'}` (Read it. It is the difference from the base `{self.base}`", text)
        self.assertIn("Changed files: a.txt  Repository: ", text)

    def test_empty_diff_points_at_the_reason(self):
        """test_empty_diff_points_at_the_reason"""
        self.intake()
        doc = self.intake_json()
        self.assertEqual(doc["diff"]["lines"], 0)
        self.assertIn(self.base, pathlib.Path(doc["diff"]["file"]).read_text(encoding="utf-8"))
        self.assertIn("変わったファイル 0 本", self.minimality())

    def test_untaken_diff_is_unmeasured_not_zero(self):
        """test_untaken_diff_is_unmeasured_not_zero: 引けない base は訳のファイルを指し、規模と変更ファイルを 0 にせず測れないと書く"""
        self.assertTrue(self.intake(base="no-such-rev")["due"])
        doc = self.intake_json()
        self.assertIn("累積差分が取れない", pathlib.Path(doc["diff"]["file"]).read_text(encoding="utf-8"))
        text = self.minimality()
        self.assertNotIn("変わったファイル 0 本", text)
        self.assertIn("測れなかった: 累積差分が取れない", text)
        self.assertIn("Changed files: 累積差分が取れない", text)

    def test_diff_leaves_out_the_runtime_copy(self):
        """test_prep_diff_leaves_out_the_archon_copy"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        ports = kit.load("r1", "steps").ports
        copy = self.repo / ports.RUNTIME_COPY / "workflows"
        copy.mkdir(parents=True)
        (copy / "x.yaml").write_text("name: x\n", encoding="utf-8")
        self.intake()
        self.assertEqual(self.intake_json()["diff"]["changed"], ["a.txt"])
        self.assertNotIn(ports.RUNTIME_COPY, (self.place / "run.diff").read_text(encoding="utf-8"))


class AfterCase(_RepoCase):
    def test_r1_head_carries_after_counts(self):
        """test_r1_head_carries_after_counts"""
        self.intake()
        self.assertIn(self.eyekit.NO_AFTER, self.minimality())
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[], after=AFTER)
        self.intake(after=str(path))
        text = self.minimality()
        self.assertIn(structmark.after_counts(folder) + "\n", text)
        self.assertIn("増えた写しの塊 2 個", text)
        self.assertNotIn(self.eyekit.NO_AFTER, text)

    def test_r1_head_carries_plan_deviations_and_the_plan_review_verdict(self):
        """test_r1_head_carries_plan_deviations_and_the_plan_review_verdict（port review で）"""
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[DEVIATION], after=AFTER)
        line = "  - 修正案の項目 2・設計の行 u2から外れる——入口を 2 つ残す（呼び手が別のリポジトリに在る）"
        self.intake(after=str(path), review=dump({"round": 2, "verdict": "accepted", "blocks": [], "why": ""}))
        text = self.minimality()
        self.assertIn(f"{structmark.after_counts(folder)}\n{line}\n{self.eyekit.REVIEW_ACCEPTED.format(k=2)}\n", text)
        self.intake(after=str(path), review=dump({"round": 3, "verdict": "blocked", "blocks": [{"key": "f1", "why": "入口は 1 つで足りる"}]}))
        self.assertIn(self.eyekit.REVIEW_BLOCKED.format(k=3, n=1, faces="f1: 入口は 1 つで足りる"), self.minimality())

    def test_empty_review_port_says_it_was_not_given(self):
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[DEVIATION], after=AFTER)
        self.intake(after=str(path))
        self.assertIn(self.eyekit.REVIEW_UNREAD.format(why=self.eyekit.REVIEW_NOT_GIVEN), self.minimality())


class VerdictCase(_RepoCase):
    def ran(self, reply) -> dict:
        self.intake()
        self.save("r1-comments", COMMENTS)
        self.save("r1-minimality", reply)
        return self.finish()

    def test_r1_redesign_without_points_falls_to_fix_needed(self):
        """CollectCase.test_r1_redesign_without_points_falls_to_fix_needed"""
        done = self.ran({**PASS, "status": "redesign-needed", "reason": "冗長な写しが在る"})
        self.assertEqual(done["verdict"], {"status": "fix-needed", "reason": kit.load("r1", "steps").UNNAMED_REDESIGN + "冗長な写しが在る"})
        self.assertEqual((done["ok"], done["status"]), (True, "ran"))

    def test_r1_malformed_points_are_unverifiable_not_unnamed(self):
        """CollectCase.test_r1_malformed_points_are_unverifiable_not_unnamed"""
        done = self.ran({**PASS, "status": "redesign-needed", "reason": "冗長", "redesign_points": "設計の点"})
        self.assertEqual(done["verdict"], {"status": "unverifiable", "reason": kit.load("r1", "steps").BROKEN_POINTS + "冗長"})

    def test_r1_points_make_redesign_whatever_the_eye_wrote(self):
        """CollectCase.test_r1_points_make_redesign_whatever_the_eye_wrote"""
        done = self.ran({**PASS, "reason": "冗長", "redesign_points": ["返りの型を作り替える"]})
        self.assertEqual(done["verdict"], {"status": "redesign-needed",
                                           "reason": kit.load("r1", "steps").RAISED_BY_POINTS + "冗長（組み直す設計の点: 返りの型を作り替える）"})

    def test_findings_are_the_deletions_in_one_line(self):
        """fix-needed の時、finish は deletions を {where, text} の並びとして findings に載せ、改行を含む why を 1 行にする。pass の時は空"""
        deletions = [{"where": "b.py:9", "why": "a.txt:1 に同じ\n内容"}, {"where": "c.py:2", "why": "使い手が無い"}]
        done = self.ran({**PASS, "status": "fix-needed", "reason": "写しが在る", "deletions": deletions})
        self.assertEqual(done["findings"], [{"where": "b.py:9", "text": "a.txt:1 に同じ 内容"}, {"where": "c.py:2", "text": "使い手が無い"}])
        self.assertEqual(self.ran({**PASS, "deletions": deletions})["findings"], [], "pass の時は返す項目を作らない")

    def test_fix_needed_without_deletions_names_the_reason(self):
        """deletions が空で increments だけの fix-needed では、名指しの無い項目を作らず判定の reason の 1 行を載せる"""
        done = self.ran({**PASS, "status": "fix-needed", "reason": "増分が正当化されていない\nコメントも", "increments": ["a.txt: 理由が無い"]})
        self.assertEqual(done["findings"], [{"where": "", "text": "増分が正当化されていない コメントも"}])

    def test_fallback_has_every_field(self):
        """出口が落ちた形（fallback）も、入口が落ちた形も、finish の output_format の必須の欄を全部持つ"""
        required = next(n for n in DOC["nodes"] if n["id"] == "finish")["output_format"]["required"]
        self.intake()
        (self.place / "finish.json").mkdir()   # 写しを書けない
        self.assertEqual(sorted(self.finish()), sorted(required))
        self.assertEqual(self.finish()["findings"], [])
        (self.place / "intake.json").unlink()
        (self.place / "finish.json").rmdir()
        self.assertEqual(sorted(self.finish()), sorted(required))

    def test_missing_eye_file_is_unverifiable_and_named(self):
        """CollectCase.test_missing_eye_file_is_unverifiable_and_named（R4 を回した尾は eyes のまとめが足す）"""
        self.intake()
        done = self.finish()
        reason = "R1 の筋が落ちた（r1: 出力のファイルが無い。ノードが落ちた）"
        self.assertEqual(done, {"ok": False, "status": "failed", "reason": reason, "verdict": {"status": "unverifiable", "reason": reason},
                                "questions": [], "findings": [], "report": [f"R1: unverifiable（{reason}）",
                                                            "  - コメントの削除候補は取れなかった（出力のファイルが無い）"]})

    def test_off_contract_status_is_named(self):
        """CollectCase.test_off_contract_status_is_named"""
        done = self.ran({**PASS, "status": "ok"})
        self.assertEqual((done["ok"], done["status"], done["verdict"]["status"]), (False, "failed", "unverifiable"))
        self.assertIn("約束の外", done["verdict"]["reason"])

    def test_a_port_that_cannot_be_read_fails_with_its_name(self):
        for name, raw in (("units", '{"rows": 1}'), ("judgment", self.run.pointer("absent.json")), ("policy", "/no/such/file.md"),
                          ("green", "yes"), ("review", dump({"verdict": "maybe"}))):
            with self.subTest(name):
                got = self.intake(**{name: raw})
                self.assertFalse(got["due"])
                self.assertTrue(got["reason"].startswith(f"入力 {name}: "), got["reason"])
                done = self.finish()
                self.assertEqual((done["ok"], done["status"], done["reason"]), (False, "failed", got["reason"]))
                self.assertEqual(done["verdict"], {"status": "unverifiable", "reason": f"入力が読めない: {got['reason']}"})
                self.assertEqual(len(done["report"]), 1)

    def test_output_that_json_cannot_hold_is_refused_before_the_copy(self):
        """NaN・Infinity は finish.json を書く前に落とす（script の出口はこれを落ちた形にする）"""
        from unittest import mock
        steps = kit.load("r1", "steps")
        self.intake()
        self.save("r1-minimality", PASS)
        with self.run.env(), mock.patch.object(steps.eyekit, "verdict_row", return_value=({"status": "pass", "reason": float("nan")}, True)):
            with self.assertRaisesRegex(ValueError, "JSON に書けない"):
                steps.finish(self.place)
        self.assertFalse((self.place / "finish.json").exists())

    def test_finish_never_fails(self):
        """test_verdict_never_fails の r1 の半分: 中の誤りでも落ちず、出口が落ちた形を返す"""
        self.intake()
        (self.place / "finish.json").mkdir()   # 写しを書けない
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["questions"]), (False, "failed", []))
        self.assertTrue(done["verdict"]["reason"].startswith("出口が落ちた: "), done["verdict"])
        self.assertEqual(done["verdict"]["status"], "unverifiable")
        self.assertEqual(len(done["report"]), 1)


class PointsCase(unittest.TestCase):
    """by_points（R1 の名指しの決まり。eyekit.verdict_row の settle）を、返答の dict で直に呼ぶ"""
    REASON = "冗長な写しが在る"

    def setUp(self):
        self.steps = kit.load("r1", "steps")

    def r1(self, status, **extra):
        return {**PASS, "status": status, "reason": self.REASON, **extra}

    def test_unnamed_redesign_falls_to_fix_needed(self):
        for label, points in (("欄が無い", {}), ("空の配列", {"redesign_points": []})):
            with self.subTest(label):
                self.assertEqual(self.steps.by_points(self.r1("redesign-needed", **points)),
                                 {"status": "fix-needed", "reason": self.steps.UNNAMED_REDESIGN + self.REASON})

    def test_malformed_points_are_unverifiable(self):
        for status in ("redesign-needed", "fix-needed", "pass"):
            for label, points in (("空白だけ", ["", "  "]), ("配列でない", "設計の点"), ("項が文字列でない", [3, None]), ("オブジェクト", {"a": 1})):
                with self.subTest(status=status, label=label):
                    self.assertEqual(self.steps.by_points(self.r1(status, redesign_points=points)),
                                     {"status": "unverifiable", "reason": self.steps.BROKEN_POINTS + self.REASON})
        self.assertEqual(self.steps.by_points(self.r1("redesign-needed", redesign_points=["  ", "返りの型を作り替える", 3])),
                         {"status": "redesign-needed", "reason": self.REASON + "（組み直す設計の点: 返りの型を作り替える）"})

    def test_points_make_redesign(self):
        points = ["返りの型を作り替える", "他の消費者が読む契約を替える"]
        tail = "（組み直す設計の点: 返りの型を作り替える／他の消費者が読む契約を替える）"
        for status in ("fix-needed", "pass"):
            with self.subTest(status):
                self.assertEqual(self.steps.by_points(self.r1(status, redesign_points=[*points, ""])),
                                 {"status": "redesign-needed", "reason": self.steps.RAISED_BY_POINTS + self.REASON + tail})
        self.assertEqual(self.steps.by_points(self.r1("redesign-needed", redesign_points=points)),
                         {"status": "redesign-needed", "reason": self.REASON + tail})
        self.assertEqual(self.steps.by_points(self.r1("unverifiable", redesign_points=points)),
                         {"status": "unverifiable", "reason": self.REASON})
        self.assertEqual(self.steps.by_points(self.r1("fix-needed")), {"status": "fix-needed", "reason": self.REASON})
        self.assertEqual(self.steps.by_points(self.r1("pass")), {"status": "pass", "reason": self.REASON})


class ScalarsCase(unittest.TestCase):
    """test_eyeverdict.py の ScalarsCase の全部（src/scalars.py に）"""
    DIFF = ("diff --git a/a.py b/a.py\nindex 1..2 100644\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,3 @@\n keep\n-old\n+new\n+more\n"
            "diff --git a/docs/x.md b/docs/x.md\nnew file mode 100644\n--- /dev/null\n+++ b/docs/x.md\n@@ -0,0 +1 @@\n+doc line\n")

    def setUp(self):
        self.s = kit.load("r1", "scalars")

    def test_counts_lines_and_files_from_the_diff(self):
        self.assertEqual(self.s.scalars(self.DIFF), {"added_lines": 3, "deleted_lines": 1, "doc_lines": 1, "files": ["a.py", "docs/x.md"]})

    def test_empty_diff_counts_zero(self):
        self.assertEqual(self.s.scalars(""), {"added_lines": 0, "deleted_lines": 0, "doc_lines": 0, "files": []})

    def test_hunk_lines_that_look_like_file_heads_are_counted(self):
        diff = "diff --git a/doc.md b/doc.md\n--- a/doc.md\n+++ b/doc.md\n@@ -1,2 +1,2 @@\n title\n----\n+++i;\n"
        self.assertEqual(self.s.scalars(diff), {"added_lines": 1, "deleted_lines": 1, "doc_lines": 1, "files": ["doc.md"]})

    def test_quoted_non_ascii_path_is_read(self):
        diff = ('diff --git "a/\\346\\226\\207.md" "b/\\346\\226\\207.md"\n--- "a/\\346\\226\\207.md"\n'
                '+++ "b/\\346\\226\\207.md"\n@@ -1 +1 @@\n-古い\n+新しい\n')
        self.assertEqual(self.s.scalars(diff), {"added_lines": 1, "deleted_lines": 1, "doc_lines": 1, "files": ["文.md"]})

    def test_unreadable_diff_is_named_not_zero(self):
        got = self.s.scalars("これは差分でない")
        self.assertNotIn("added_lines", got)
        self.assertIn("測れなかった", self.s.scalars_text(got))

    def test_untaken_diff_is_named_not_zero(self):
        self.assertEqual(self.s.scalars("", {"x_endpoints": 2}, "累積差分が取れない（git が落ちた）"),
                         {"x_endpoints": 2, "unmeasured": ["累積差分が取れない（git が落ちた）"]})

    def test_fix_x_scalars_are_added(self):
        got = self.s.scalars(self.DIFF, {"x_endpoints": 2})
        self.assertEqual((got["x_endpoints"], got["added_lines"]), (2, 3))
        self.assertIn("x_endpoints 2", self.s.scalars_text(got))

    def test_part_measured_returns_the_measured_part(self):
        got = self.s.scalars("これは差分でない", {"x_endpoints": 2})
        self.assertEqual((got["x_endpoints"], got["unmeasured"]), (2, ["累積差分が git の差分の形でない"]))
        self.assertIn("測れなかった: 累積差分が git の差分の形でない", self.s.scalars_text(got))

    def test_x_scalars_outside_the_graph_shape_are_named(self):
        got = self.s.scalars(self.DIFF, {"x_ok": 1, "endpoints": 2, "x_flag": True})
        self.assertEqual(got["x_ok"], 1)
        self.assertNotIn("endpoints", got)
        self.assertNotIn("x_flag", got)
        self.assertIn("endpoints・x_flag", got["unmeasured"][0])
        self.assertIn("object でない", self.s.scalars(self.DIFF, [1])["unmeasured"][0])


if __name__ == "__main__":
    unittest.main()
