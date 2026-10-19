"""局所レビューの block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/local-review.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。プラグインの有無は
環境変数 CLAUDE_CONFIG_DIR を読む受け付けを、この過程の中で一時の設定に向けて回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import os
import unittest
from unittest import mock

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "local-review"
NAME = "local-review"
LOOP = f"{NAME}-loop"
LENSES = ["/code-review", "pr-review-toolkit:code-reviewer", "/simplify", "/security-review",
          "pr-review-toolkit:silent-failure-hunter", "pr-review-toolkit:type-design-analyzer",
          "pr-review-toolkit:pr-test-analyzer"]
UNSEEN = "【works: 所見を受け取れていない——このレンズは見ていないのと同じに扱え】"
WHY = "差分が認証・データの取り扱い・外部との入出力に触れる"


def rows(invoked=lambda skill: True, code_review=()):
    """宣言の 7 本に 1 行ずつ。/code-review の行は code_review の所見を持つ（空なら見ていない印が付く形）"""
    out = [{"skill": s, "items": [], "invoked": invoked(s), "failed": "起こしたが所見なし（差分を見た）"} for s in LENSES]
    out[0]["items"] = list(code_review)
    return out


def reply(findings=None, **material):
    return {"material": {"status": "clean", "checked": "差分を見た", **material}, "simplify_carried": False,
            "findings": rows() if findings is None else findings}


def refused_na():
    """not_applicable は名乗れないので拒まれる返答"""
    return {**reply(), "material": {"status": "not_applicable", "reason": "無い"}}


FOUND = {"where": "app.txt:1", "text": "一行目の見本", "mechanism": "因果", "measured": "未実測", "false_positive_if": "見本なら誤り"}


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "app.txt").write_text("一行目\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def intake(self, **inputs):
        return self.run.script("intake", "intake", **{"base": "", "entry": "", "lang": "", **inputs})

    def prep(self):
        return self.run.script("role_prep", f"{LOOP}.{NAME}-prep")

    def accept(self, got):
        return self.run.script("role_accept", f"{LOOP}.{NAME}-accept", reply=json.dumps(got, ensure_ascii=False))

    def accept_in_process(self, got, plugins=None):
        """CLAUDE_CONFIG_DIR を一時の設定に向けて受け付ける（plugins が None なら環境変数を外す）"""
        vp = kit.load(NAME, "viewpoint")
        cfg = {} if plugins is None else {"CLAUDE_CONFIG_DIR": str(self.config(plugins))}
        with self.run.env(), mock.patch.dict(os.environ, cfg):
            if plugins is None:
                os.environ.pop("CLAUDE_CONFIG_DIR", None)
            return vp.materialkit.accept(vp, self.run.artifacts, self.run.repo, json.dumps(got, ensure_ascii=False))

    def config(self, plugins):
        cfg = self.run.artifacts.parent / "claude-config" / "plugins"
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "installed_plugins.json").write_text(json.dumps({"plugins": {f"{n}@market": [] for n in plugins}}), encoding="utf-8")
        return cfg.parent

    def finish(self):
        return self.run.script("finish", "finish")

    def material(self):
        return json.loads((self.run.artifacts / "material.json").read_text(encoding="utf-8"))

    def test_port_values_alone_reach_the_material(self):
        """写す元 MaterialCase のレンズの場面: 通常の run は宣言の 7 本を指示に入れ、見たレンズの行を素材に写して受ける。
        not_applicable は名乗れない"""
        self.assertEqual(self.intake()["due"], True)
        got = self.prep()["prompt"]
        self.assertIn("You are the local-review role.", got)
        self.assertNotIn("Why your previous answer was rejected", got)
        refused = self.accept(refused_na())
        self.assertEqual((refused["ok"], refused["done"]), (False, False))
        self.assertIn("『条件に当たらない』を名乗れない", refused["reason"])
        self.assertTrue(self.prep()["prompt"].startswith("## Why your previous answer was rejected"))
        self.assertEqual(self.accept(reply(rows(code_review=[FOUND]))), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        self.assertEqual(fin["report"], ["素材 local_review: clean（見た所: 差分を見た）"])
        doc = self.material()
        self.assertEqual((doc["role"], doc["status"]), (NAME, "ran"))
        self.assertEqual(doc["materials"], {"local_review": {"status": "clean", "checked": "差分を見た"}})
        self.assertEqual(json.loads((self.run.artifacts / "lenses.json").read_text(encoding="utf-8")), {"round": 1, "unseen": []})

    def test_local_review_rows_cover_the_declared_lenses(self):
        """写す元 test_local_review_rows_cover_the_declared_lenses: 行の欠け・宣言の外の名・同じレンズの 2 行・items も failed も
        無い行をそれぞれ拒む"""
        self.intake()
        full = rows(code_review=[FOUND])
        hunter = "pr-review-toolkit:silent-failure-hunter"
        cases = ((full, ""),
                 ([r for r in full if r["skill"] != "/security-review"], "宣言した '/security-review' の行が findings に無い"),
                 ([*full, {**full[1], "skill": "my:lens"}], "findings[7] の skill 'my:lens' は宣言に無い——正本は宣言のレンズ"),
                 ([*full, full[1]], "findings に同じ skill の行が 2 本: pr-review-toolkit:code-reviewer"),
                 ([*[r for r in full if r["skill"] != hunter], {"skill": hunter, "items": [], "invoked": True, "failed": ""}],
                  f"'{hunter}' の行が items も failed も持たない"))
        for found, why in cases:
            with self.subTest(why=why):
                self.setUp()
                self.intake()
                got = self.accept_in_process(reply(found))
                self.assertEqual(got["ok"], not why, got)
                if why:
                    self.assertIn(why, got["reason"])
                    self.assertNotIn("graph", got["reason"], "block は graph を名指さない")

    def test_condition_lens_must_be_invoked_unless_awaiting_human(self):
        """条件が真の /security-review は invoked が真でなければ拒む。material が awaiting_human の時は免じる"""
        self.intake()
        skipped = rows(code_review=[FOUND])
        skipped[3]["invoked"] = False
        got = self.accept_in_process(reply(skipped))
        self.assertFalse(got["ok"])
        self.assertIn("'/security-review' は条件 security_surface_touched が真の周（" + WHY + "）", got["reason"])
        got = self.accept_in_process(reply(skipped, status="awaiting_human", reason="呼び出しが落ちた"))
        self.assertTrue(got["ok"], got)

    def test_missing_required_lens_is_refused(self):
        """写す元 test_missing_required_lens_is_refused: 必須のレンズを起こしていない返答と、それを awaiting_human にした返答を拒む。
        プラグインが入っていれば出し直させる（done が偽）"""
        self.intake()
        miss = rows(lambda s: s != "pr-review-toolkit:code-reviewer")
        for status in ("clean", "awaiting_human"):
            with self.subTest(status):
                got = self.accept_in_process(reply(miss, status=status, reason="待つ"), plugins=["pr-review-toolkit"])
                self.assertFalse(got["ok"])
                self.assertFalse(got["done"], "プラグインが在れば出し直させる")
                self.assertIn("'pr-review-toolkit:code-reviewer' は必須のレンズ", got["reason"])
                self.assertEqual("awaiting_human にできない" in got["reason"], status == "awaiting_human")
        vp = kit.load(NAME, "viewpoint")
        self.assertEqual(vp.materialkit.rolekit.given_up_reason(self.run.artifacts, NAME), "")

    def test_simplify_carry_is_not_accepted(self):
        """1 run は 1 周: /simplify を起こしていない返答は simplify_carried が真でも拒み、尾にその訳を言う"""
        self.intake()
        miss = rows(lambda s: s != "/simplify")
        got = self.accept_in_process({**reply(miss), "simplify_carried": True})
        self.assertFalse(got["ok"])
        self.assertIn("'/simplify' は必須のレンズなのに invoked が true でない", got["reason"])
        self.assertIn("simplify_carried: true の持ち越しはこの run では受けない", got["reason"])

    def test_absent_plugin_gives_up_at_once(self):
        """写す元 test_absent_plugin_gives_up_at_once: レンズのプラグインが隔離した設定に無ければ、1 回目の拒みで done にして人に渡し、
        出口が gave_up と素材 local_review の理由にプラグインの名を書く"""
        self.intake()
        miss = rows(lambda s: not s.startswith("pr-review-toolkit:"))
        got = self.accept_in_process(reply(miss), plugins=["other-plugin"])
        self.assertFalse(got["ok"])
        self.assertTrue(got["done"], "1 回目から諦める")
        self.assertIn("プラグイン pr-review-toolkit が入っていない", got["reason"])
        self.assertIn("bin/_lib/toolset.py install", got["reason"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("pr-review-toolkit", fin["reason"])
        mat = self.material()["materials"]["local_review"]
        self.assertEqual(mat["status"], "not_run")
        self.assertIn("pr-review-toolkit", mat["reason"])

    def test_local_review_unseen_lens_is_marked(self):
        """写す元 test_local_review_unseen_lens_is_marked: /code-review の行が items 空で受けられ、行の failed に印が付き、
        控え lenses.json と出口の report の行に見ていないレンズが出る"""
        self.intake()
        given = reply(rows())
        given["findings"][0]["failed"] = "本文が届かなかった"
        self.assertEqual(self.accept(given), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        doc = self.material()
        self.assertTrue(doc["reply"]["findings"][0]["failed"].startswith(UNSEEN))
        self.assertIn(UNSEEN, doc["reply"]["material"]["checked"])
        self.assertEqual(json.loads((self.run.artifacts / "lenses.json").read_text(encoding="utf-8")),
                         {"round": 1, "unseen": ["/code-review"]})
        self.assertEqual(fin["report"][1:], ["  - 局所レビューの /code-review: 所見を受け取れていない（fork の返答が届かなかった）——見ていないのと同じ"])

    def test_rejected_round_writes_no_lens_file(self):
        self.intake()
        self.accept(refused_na())
        self.assertFalse((self.run.artifacts / "lenses.json").exists())

    def test_location_beyond_the_file_is_sent_back(self):
        """所見の場所の行がファイルに無ければ拒む（例の run の 1 回目の拒み）"""
        self.intake()
        far = {**FOUND, "where": "app.txt:99"}
        got = self.accept(reply(rows(code_review=[far])))
        self.assertFalse(got["ok"])
        self.assertIn("所見の場所の行がファイルに無い", got["reason"])

    def test_tree_change_is_refused(self):
        self.intake()
        (self.run.repo / "app.txt").write_text("役が書き換えた\n", encoding="utf-8")
        got = self.accept(reply(rows(code_review=[FOUND])))
        self.assertFalse(got["ok"])
        self.assertIn("読むだけの役が作業ツリーを変えた", got["reason"])

    def test_three_rejections_give_up(self):
        self.intake()
        bad = refused_na()
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        self.assertEqual(self.material()["materials"]["local_review"]["status"], "not_run")

    def test_entry_run_does_not_start_the_role(self):
        """判定から入る run（entry が空でない）は役を起こさず、出口が skipped と fill_entry の字で素材を埋める"""
        got = self.intake(entry="人の依頼（/path/req.json）")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (True, "skipped"))
        mk = kit.load(NAME, "viewpoint").materialkit
        self.assertEqual(fin["reason"], mk.entry_skip("P1 の役").why)
        mat = self.material()
        self.assertEqual(mat["materials"], {"local_review": mk.fill_entry("人の依頼（/path/req.json）", None)})
        self.assertIn("件数は渡されていない", mat["materials"]["local_review"]["reason"])
        self.assertIsNone(mat["reply"])

    def test_prompt_declares_the_lenses_without_notes(self):
        """prep が組んだ指示の {skills} の値: /security-review は applies: true と理由を持ち、どの要素も note を持たない。
        対象の根に REVIEW.md が無ければ repo_review の段落が入らず、在れば入る"""
        self.intake()
        got = self.prep()["prompt"]
        start = got.index("[\n {\n  \"skill\": \"/code-review\"")
        declared = json.JSONDecoder().raw_decode(got[start:])[0]
        self.assertEqual([e["skill"] for e in declared], LENSES)
        self.assertEqual(declared[3], {"skill": "/security-review", "required": False, "applies_cond": "security_surface_touched",
                                       "applies": True, "applies_why": WHY})
        self.assertFalse(any("note" in e for e in declared))
        self.assertNotIn("The target repository's own review viewpoints", got)
        self.assertIn("reading rules below", got)
        self.assertIn("# 借りた superpowers のスキルを無人の役で読むときの読み替え", got)
        self.setUp()
        (self.run.repo / "REVIEW.md").write_text("# 観点\n", encoding="utf-8")
        self.intake()
        self.assertIn("The target repository's own review viewpoints:", self.prep()["prompt"])

    def test_lang_reaches_the_prompt(self):
        self.intake(lang="Japanese")
        self.assertIn("in Japanese.", self.prep()["prompt"])

    def test_unreadable_base_fails_with_the_port_name(self):
        got = self.intake(base="no-such-commit")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertEqual(self.material()["materials"]["local_review"]["status"], "not_run")

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__local-review__intake", base="", entry="", lang="")
        self.run.script("role_prep", f"judge__local-review__{LOOP}.{NAME}-prep")
        self.assertTrue((self.run.artifacts / "judge" / "local-review" / f"{NAME}-prompt-1.md").is_file())
        fin = self.run.script("finish", "judge__local-review__finish")
        self.assertEqual(fin["material"]["path"], "judge/local-review/material.json")


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    # 今の判定の local-review の役の起こし方（tests/workflows/test_judge.py の ROLES["local-review"] の行と、
    # workflows/judge/works-factory-judge.yaml の錨 net_closed_launch に node が足す 3 つの鍵を、作り直しの時に字で写した物）。
    # 組み込みで workflows/ が入れ替わっても、この期待は block の起こし方の正本として残る
    LAUNCH = {"model": "@wf-judge-materials", "settingSources": ["user"],
              "allowed_tools": ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch", "Skill", "Agent"],
              "skills": ["code-review", "simplify", "security-review"], "plugins": ["pr-review-toolkit@works-local"],
              "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                          "excludedCommands": ["works-gh:*"], "network": {"allowedDomains": []},
                          "filesystem": {"denyWrite": ["~/../archon-home"]}},
              "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}}

    def test_launch_matches_the_judge_role(self):
        """起こし方は今の判定の local-review の役と同じ（群の既定は sonnet・medium。役の node は mutates_checkout を持たない）"""
        import launchgroups
        role = self.body[NAME]
        self.assertEqual({k: role.get(k) for k in self.LAUNCH}, self.LAUNCH)
        self.assertEqual(launchgroups.default_of(role["model"]), ("sonnet", "medium"))
        self.assertNotIn("mutates_checkout", role)
        self.assertEqual(role["output_format"]["required"], ["material", "findings", "simplify_carried"])


if __name__ == "__main__":
    unittest.main()
