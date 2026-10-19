"""黙った失敗のレンズの block を、script を子のプロセスで回して確かめる（docs/design/lens.md の 8.2）。

使い捨ての run directory と git のリポジトリ（README.md・docs/a.md・.archon/x.md を commit し、作業ツリーで変える）で、port の値だけを渡し、
intake → lens_prep → 台本の返答を渡す lens_take → finish と回す。YAML と筋書きの揃いも見る。筋書きを Archon の workflow test で回すのは
tests/layers/test_block_shape.py。
"""
import ast
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "lens"
LENS = "silent-failure-hunter"
KEY = "silent_failure_hunter"
BODY = "You look for errors that are swallowed {without} a trace."
LENSES = json.dumps([{"lens": LENS, "body": BODY}])
GOOD_FINDING = {"where": "README.md", "cite": "except: pass", "why": "例外を握りつぶすので、呼び元は失敗に気づけない"}


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "lens")
        repo = self.run.repo
        (repo / "docs").mkdir()
        (repo / ".archon").mkdir()
        (repo / "README.md").write_text("# demo\n", encoding="utf-8")
        (repo / "docs" / "a.md").write_text("a\n", encoding="utf-8")
        (repo / ".archon" / "x.md").write_text("x\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "seed")
        self.base = git(repo, "rev-parse", "HEAD")
        self.steps = kit.load("lens", "steps")

    def change(self, name="README.md", text="# demo\nchanged\n"):
        (self.run.repo / name).write_text(text, encoding="utf-8")

    def intake(self, **inputs):
        ports = {"base": self.base, "lenses": LENSES, "lang": "", **inputs}
        return self.run.script("intake", **ports)

    def read(self, name):
        return json.loads((self.run.artifacts / name).read_text(encoding="utf-8"))

    def take(self, reply):
        return self.run.script("lens_take", lens=LENS, reply=json.dumps(reply, ensure_ascii=False))

    def finish(self):
        return self.run.script("finish")


class IntakeCase(_RepoCase):
    def test_changed_files_start_the_lens_and_the_diff_is_cut(self):
        self.change()
        self.assertEqual(self.intake(), {"due": True, "reason": "", f"{KEY}_go": True})
        doc = self.read("intake.json")
        self.assertEqual((doc["files"], doc["failed"], doc["base"]), (["README.md"], False, self.base))
        self.assertEqual(doc["routes"][LENS], {"go": True, "reason": "", "agent": "pr-review-toolkit:silent-failure-hunter", "body": BODY})
        self.assertIn("+changed", (self.run.artifacts / "lens.diff").read_text(encoding="utf-8"))
        self.assertEqual([r["state"] for r in self.read("lens.json")["rows"]], ["pending"])

    def test_untracked_file_is_in_the_diff_and_the_runtime_copy_is_not(self):
        self.change("new.md", "n\n")
        self.change(".archon/x.md", "changed\n")
        self.intake()
        self.assertEqual(self.read("intake.json")["files"], ["new.md"])

    def test_non_ascii_names_are_kept(self):
        self.change("日本語.md", "n\n")
        self.intake()
        self.assertEqual(self.read("intake.json")["files"], ["日本語.md"])

    def test_no_changed_file_is_not_routed(self):
        self.assertEqual(self.intake(), {"due": False, "reason": "", f"{KEY}_go": False})
        row = self.read("lens.json")["rows"][0]
        self.assertEqual((row["state"], row["reason"]), ("not_routed", "修正の差分に変わったファイルが無い"))

    def test_lens_not_named_is_not_routed(self):
        self.change()
        self.assertEqual(self.intake(lenses="[]")[f"{KEY}_go"], False)
        self.assertEqual(self.read("lens.json")["rows"][0]["reason"], "入力 lenses が名指していない")

    def test_bad_ports_fail_with_the_port_name(self):
        self.change()
        cases = [({"lenses": "{"}, "入力 lenses"), ({"lenses": ""}, "入力 lenses"),
                 ({"lenses": json.dumps([{"lens": "nope"}])}, "入力 lenses: 知らないレンズ nope（この block のレンズは silent-failure-hunter）"),
                 ({"lenses": json.dumps([{"lens": LENS}, {"lens": LENS}])}, f"入力 lenses: レンズ {LENS} が 2 つ在る"),
                 ({"lenses": json.dumps([{"lens": LENS, "extra": 1}])}, "入力 lenses"),
                 ({"base": "not-a-version"}, "入力 base")]
        for inputs, head in cases:
            with self.subTest(inputs=inputs):
                got = self.intake(**inputs)
                self.assertEqual((got["due"], got[f"{KEY}_go"]), (False, False))
                self.assertIn(head, got["reason"])
                self.assertTrue(self.read("intake.json")["failed"])
                self.assertEqual(self.read("errors.json")[0]["node"], "intake")

    def test_body_given_does_not_look_the_definition_up(self):
        self.change()
        with self.run.env(), mock.patch.object(self.steps.lenses.validator, "agent_def", side_effect=AssertionError("引くな")):
            got = self.steps.intake(self.run.artifacts, self.run.repo, base=self.base, lenses_raw=LENSES, lang="")
        self.assertTrue(got[f"{KEY}_go"])

    def test_definition_that_cannot_be_found_is_not_routed(self):
        self.change()
        cases = [(None, "pr-review-toolkit:silent-failure-hunter の定義が役の設定に無い（pr-review-toolkit が入っていない）"),
                 ({"body": ""}, "の定義が役の設定に無い"), (RuntimeError("boom"), "の定義を引けない（RuntimeError: boom）"),
                 (SystemExit("曖昧"), "の定義を引けない（SystemExit: 曖昧）")]
        for what, why in cases:
            with self.subTest(what=repr(what)):
                patch = mock.patch.object(self.steps.lenses.validator, "agent_def",
                                          **({"side_effect": what} if isinstance(what, BaseException) else {"return_value": what}))
                with self.run.env(), patch:
                    got = self.steps.intake(self.run.artifacts, self.run.repo, base=self.base,
                                            lenses_raw=json.dumps([{"lens": LENS}]), lang="")
                self.assertEqual(got[f"{KEY}_go"], False)
                self.assertIn(why, self.read("lens.json")["rows"][0]["reason"])

    def test_definition_found_goes_into_the_route(self):
        self.change()
        with self.run.env(), mock.patch.object(self.steps.lenses.validator, "agent_def", return_value={"body": "DEF"}) as call:
            got = self.steps.intake(self.run.artifacts, self.run.repo, base=self.base, lenses_raw=json.dumps([{"lens": LENS, "agent": "p:r"}]),
                                    lang="")
        call.assert_called_once_with("p:r")
        self.assertTrue(got[f"{KEY}_go"])
        self.assertEqual(self.read("intake.json")["routes"][LENS]["body"], "DEF")

    def test_own_files_are_removed_and_others_kept(self):
        self.change()
        mine = ["lens.json", "errors.json", "lens.diff", f"reply-{KEY}.json", f"{LENS}-prompt-1.md"]
        for name in [*mine, "other.json", "rejects-x.json"]:
            (self.run.artifacts / name).write_text("[]", encoding="utf-8")
        self.intake()
        for name in ("errors.json", f"reply-{KEY}.json", f"{LENS}-prompt-1.md"):
            self.assertFalse((self.run.artifacts / name).exists(), name)
        self.assertTrue((self.run.artifacts / "other.json").is_file())
        self.assertTrue((self.run.artifacts / "rejects-x.json").is_file())

    def test_include_path_splits_the_place(self):
        self.change()
        self.run.script("intake", include="lens__lens-intake", base=self.base, lenses=LENSES, lang="")
        self.assertTrue((self.run.artifacts / "lens" / "intake.json").is_file())


class PromptCase(_RepoCase):
    def prep(self, lang=""):
        self.change()
        self.intake(lang=lang)
        return self.run.script("lens_prep", lens=LENS)["prompt"]

    def test_prompt_holds_the_definition_name_diff_files_limits_and_language(self):
        text = self.prep(lang="Japanese")
        self.assertIn("## Role definition (pr-review-toolkit:silent-failure-hunter)", text)
        self.assertIn(BODY, text, "定義の本文の中の {…} は字のまま")
        self.assertIn(f"Your lens name is `{LENS}`", text)
        self.assertIn(str(self.run.artifacts / "lens.diff"), text)
        self.assertIn('["README.md"]', text)
        self.assertIn("at least 4 characters", text)
        self.assertIn("at least 20 characters", text)
        self.assertIn("Write `why` and `findings_none` in Japanese.", text)
        self.assertTrue((self.run.artifacts / f"{LENS}-prompt-1.md").is_file())

    def test_empty_language_uses_the_shared_default(self):
        self.assertIn("in the language of the request (the user's language).", self.prep())

    def test_no_slot_is_left_unfilled(self):
        import re
        self.assertEqual([m for m in re.findall(r"\{[a-z0-9_]+\}", self.prep()) if m != "{without}"], [])

    def test_prep_without_a_route_writes_the_error_and_fails(self):
        self.intake(base="nope")   # 入口が壊れて振り分けが無い
        err = self.run.failing("lens_prep", lens=LENS)
        self.assertIn("lens-prep silent-failure-hunter", err)
        self.assertEqual(self.read("errors.json")[-1]["node"], LENS)


class FinishCase(_RepoCase):
    def routed(self):
        self.change()
        self.intake()

    def test_reply_findings_get_the_lens_name_and_bad_ones_are_dropped(self):
        self.routed()
        self.take({"findings": [GOOD_FINDING, {"where": "README.md", "cite": "x", "why": ""}]})
        got = self.finish()
        self.assertEqual((got["ok"], got["status"], got["reason"], got["ran"], got["failed"], got["not_routed"]),
                         (True, "ok", "", 1, 0, 0))
        self.assertEqual(got["rows"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "lens.json"})
        row = self.read("lens.json")["rows"][0]
        self.assertEqual((row["state"], row["dropped"], row["findings"]), ("ran", 1, [{"lens": LENS, **GOOD_FINDING}]))
        self.assertEqual(got["report"], ["なし（振り分けたレンズは全部走った）", f"{LENS}: 出した発見 1 件・形の誤りで捨てた 1 件"])
        self.assertEqual(got["carry"], [])
        self.assertEqual(got["optional"], [{"node": LENS, "bare": False}, {"node": f"{LENS}-take", "bare": False}])

    def test_lens_without_a_reply_fails_the_row_but_not_the_block(self):
        self.routed()
        got = self.finish()
        self.assertEqual((got["ok"], got["status"], got["ran"], got["failed"]), (True, "ok", 0, 1))
        self.assertEqual(self.read("lens.json")["rows"][0]["reason"], "レンズのノードの出口が無い（落ちたか走らなかった）")
        self.assertEqual(got["report"], [f"{LENS}: 落ちた（レンズのノードの出口が無い（落ちたか走らなかった））"])
        self.assertEqual(got["carry"], [{"where": f"レンズ {LENS}", "text": f"{LENS}（再実行の要あり: 落ちて観点を誰も見ていない。理由: "
                                         "レンズのノードの出口が無い（落ちたか走らなかった））"}])

    def test_reply_without_findings_array_fails_the_row(self):
        self.routed()
        self.take({"findings": "x"})
        got = self.finish()
        self.assertEqual((got["ok"], got["failed"]), (True, 1))
        self.assertIn("findings の形が違う", self.read("lens.json")["rows"][0]["reason"])

    def test_not_routed_row_is_counted_and_reported(self):
        self.intake()
        got = self.finish()
        self.assertEqual((got["ok"], got["ran"], got["failed"], got["not_routed"]), (True, 0, 0, 1))
        self.assertEqual(got["report"], [f"{LENS}: 起こさなかった（修正の差分に変わったファイルが無い）"])
        self.assertEqual(got["carry"], [])

    def test_failed_intake_is_failed(self):
        self.intake(base="nope")
        got = self.finish()
        self.assertEqual((got["ok"], got["status"], got["rows"], got["ran"]), (False, "failed", None, 0))
        self.assertTrue(got["report"][0].startswith("レンズ: 落ちた（"))

    def test_no_intake_file_is_failed(self):
        got = self.finish()
        self.assertEqual((got["ok"], got["status"], got["reason"]), (False, "failed", "入口の控えが無い（入口の node が落ちた）"))

    def test_missing_route_file_is_failed(self):
        self.routed()
        (self.run.artifacts / "lens.json").unlink()
        got = self.finish()
        self.assertEqual((got["ok"], got["status"]), (False, "failed"))
        self.assertIn("レンズの集め役が終わらなかった", got["reason"])

    def test_unwritable_file_is_failed(self):
        self.routed()
        self.take({"findings": []})
        with self.run.env(), mock.patch.object(self.steps.lens, "_write", side_effect=OSError("disk")):
            got = self.steps.finish(self.run.artifacts)
        self.assertEqual((got["ok"], got["status"]), (False, "failed"))
        self.assertIn("レンズの集め役が終わらなかった: disk", got["reason"])

    def test_prep_error_makes_the_status_failed_and_keeps_the_row(self):
        self.routed()
        self.run.failing("lens_prep", lens="nope")
        got = self.finish()
        self.assertEqual((got["ok"], got["status"], got["failed"]), (False, "failed", 1))
        self.assertIn("レンズの指示が組めなかった", got["reason"])
        self.assertIsNotNone(got["rows"])

    def test_include_path_splits_the_place(self):
        self.change()
        self.run.script("intake", include="lens__lens-intake", base=self.base, lenses=LENSES, lang="")
        self.run.script("lens_take", include="lens__x", lens=LENS, reply=json.dumps({"findings": []}))
        got = self.run.script("finish", include="lens__x")
        self.assertEqual((got["ok"], got["ran"], got["rows"]["path"]), (True, 1, "lens/lens.json"))


    def test_prep_whose_import_breaks_still_writes_the_error(self):
        self.change()
        self.intake()
        env = hermetic.child_env(**{**self.run.environ(lens=LENS), "WORKS_FACTORY_ROOT": str(self.run.artifacts / "no-lib")})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / "lens_prep.py")], cwd=self.run.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.read("errors.json")[-1]["node"], LENS)
        got = self.finish()
        self.assertEqual((got["ok"], got["status"]), (False, "failed"))


def _literals(script: str, key: str) -> list:
    """script の中の辞書の字面 {key: 値} の値（ast.literal_eval できる物）を全部返す"""
    tree = ast.parse((BLOCK / "scripts" / script).read_text(encoding="utf-8"))
    return [ast.literal_eval(v) for d in ast.walk(tree) if isinstance(d, ast.Dict)
            for k, v in zip(d.keys, d.values) if isinstance(k, ast.Constant) and k.value == key]


class ShapeCase(unittest.TestCase):
    def setUp(self):
        self.doc = yaml.safe_load((BLOCK / "works-factory-lens.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in self.doc["nodes"]}
        self.table = kit.load("lens", "lenses").LENSES

    def test_every_lens_row_has_its_three_nodes(self):
        finish = self.nodes["finish"]
        optional = kit.load("lens", "steps").OPTIONAL
        for row in self.table:
            name, key = row["lens"], row["lens"].replace("-", "_")
            with self.subTest(lens=name):
                for node in (f"{name}-prep", name, f"{name}-take"):
                    self.assertIn(node, self.nodes)
                    self.assertIn(node, finish["depends_on"])
                self.assertIn(f"{key}_go", self.nodes["intake"]["output_format"]["required"])
                self.assertEqual(self.nodes[f"{name}-prep"]["when"], f"$intake.output.{key}_go == true")
                self.assertIn({"node": name, "bare": False}, optional)
                self.assertIn({"node": f"{name}-take", "bare": False}, optional)
                self.assertEqual((BLOCK / "prompts" / f"{name}.md").read_text(encoding="utf-8").strip(), "{part:lens}")
        self.assertEqual(finish["trigger_rule"], "all_done")
        self.assertIn("intake", finish["depends_on"])

    def test_ai_node_keys(self):
        for row in self.table:
            node = self.nodes[row["lens"]]
            self.assertEqual((node["model"], node["settingSources"], node["allowed_tools"], node["context"], node["mutates_checkout"]),
                             ("@wf-fix-review", ["user"], ["Read", "Grep", "Glob"], "fresh", False))
            self.assertEqual(node["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False})
            self.assertEqual(node["retry"], {"max_attempts": 2, "on_error": "all"})
            self.assertEqual(node["idle_timeout"], 1728000000)
            self.assertEqual(node["depends_on"], [f"{row['lens']}-prep"], "輪の外の役の直前の層は 1 つ")
            props = node["output_format"]["properties"]["findings"]["items"]["properties"]
            lenses = kit.load("lens", "lenses")
            self.assertEqual((props["cite"]["minLength"], props["why"]["minLength"]), (lenses.MIN_CITE, lenses.MIN_WHY))

    def test_fallbacks_that_hand_copy_the_table_match_it(self):
        steps = kit.load("lens", "steps")
        want = [{"node": n, "bare": False} for r in self.table for n in (r["lens"], f"{r['lens']}-take")]
        self.assertEqual(steps.OPTIONAL, want)
        self.assertEqual(_literals("finish.py", "optional"), [want])
        keys = {f"{r['lens'].replace('-', '_')}_go" for r in self.table}
        source = (BLOCK / "scripts" / "intake.py").read_text(encoding="utf-8")
        self.assertEqual({w for w in __import__("re").findall(r"[a-z0-9_]+_go", source)}, keys)
        self.assertEqual(set(self.nodes["intake"]["output_format"]["properties"]) - {"due", "reason"}, keys)

    def test_prep_error_file_name_is_the_one_in_files(self):
        self.assertIn(f'/ "{kit.load("lens", "files").ERRORS}"', (BLOCK / "scripts" / "lens_prep.py").read_text(encoding="utf-8"))

    def test_intake_output_lists_exactly_the_table_keys(self):
        keys = {f"{r['lens'].replace('-', '_')}_go" for r in self.table}
        shape = self.nodes["intake"]["output_format"]
        self.assertEqual(set(shape["properties"]) - {"due", "reason"}, keys)
        self.assertEqual(set(shape["required"]) - {"due", "reason"}, keys)


if __name__ == "__main__":
    unittest.main()
