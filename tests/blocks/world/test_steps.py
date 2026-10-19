"""世界の解の block の中身（blocks/world/src/steps.py。lib/tests/test_blk_world.py の Classes・Plan・Verify・Judge・Intake を、
port の値で受ける形に写した物。docs/design/world.md の 8 節。写さない試験は同じ節に名指してある）。

- 言い直す役の受け付け（依頼の全部の行に 1 つ・対象の識別子を、web の役に渡る proposed も含めて拒む・全部の行に検索語）・取る類を
  決める（類の上限）・web の役の受け付け（differs の challenge・sources が返答の excerpts を指す・依頼の解き方の無い行の verdict・
  抜き書きを取り直した本文で照らし、字のまま無い抜き書きを指す根拠を外して、印 basis を機械が付ける・web が off の run は取り直さない）・
  出口（行を書く）。出し直しの輪の拒否は lib/rolekit の控えに積む
- 一時の置き場のファイルだけ（網・子のプロセスなし。取り直しの口は偽の get を渡す）
"""
import json
import unittest

from tests.blocks import kit

steps = kit.load("world", "steps")
rolekit, worldmark = steps.rolekit, steps.worldmark

URL = "https://example.org/guide/tdd"
PAGE = ("<html><body><p>Write a failing test first. A compile error is not a red test: add the smallest stub so the test runs"
        " and fails on the expected assertion.</p></body></html>").encode()
GOOD = "A compile error is not a red test: add the smallest stub so the test runs and fails on the expected assertion."
FINDINGS = [
    {"where": "src/red_check.py:40", "text": "赤の判定がコンパイルの要る対象で読み込みの失敗を赤に数える。読むだけの役を足して生のログから判じさせる"},
    {"where": "docs/guide.md", "text": "手引きの誤字（赤を緑と書いている）"},
]
PROBLEM = "テストを先に書く開発で、まだ無い機能を呼ぶテストを、コンパイルの要る対象でどう赤にするか"
DOC_PROBLEM = "文書の誤字を直す"


def klass(finding=1, **kw):
    row = {"finding": finding, "problem": PROBLEM, "activity": "テストを先に書く開発",
           "proposed": "読むだけの役を足して生のログから判じさせる", "queries": ["test-first red phase compile error stub"]}
    row.update(kw)
    return row


def doc_class(finding=2, **kw):
    row = {"finding": finding, "problem": DOC_PROBLEM, "activity": "文書の校正", "proposed": "",
           "queries": ["proofreading documentation typos practice"]}
    row.update(kw)
    return row


def judged(finding=1, **kw):
    row = {"finding": finding, "practice": "読み込みの失敗は赤に数えず、最小の仮の実装で走らせてから期待違いの失敗を赤とする",
           "sources": [], "applies": "赤の判定の直し", "not_applies": "", "verdict": "differs",
           "challenge": "依頼は読む役を足す、定石は仮の実装で走らせる。読み込みの失敗が赤でない訳が無い限り定石を選ぶ"}
    row.update(kw)
    return row


class Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "world")
        self.out = self.run.artifacts
        self.enterContext(self.run.env())

    def intake(self, web="on", findings=None, purpose="", means=()):
        request = json.dumps(FINDINGS if findings is None else findings, ensure_ascii=False)
        return steps.intake(self.out, request=request, purpose=purpose, means=json.dumps(list(means), ensure_ascii=False), web=web,
                            lang="")

    def classes(self, reply):
        steps.classes_prompt(self.out)
        return steps.accept(self.out, steps.CLASSES_ROLE, json.dumps(reply, ensure_ascii=False))

    def plan(self):
        return steps.pick(self.out)

    def judge(self, rows, excerpts=(), get=lambda u: (200, PAGE)):
        """web の役の返答（rows と excerpts）を受け付けの中身に渡す。抜き書きは get が返す本文で取り直して照らす"""
        return steps._take_judge(self.out, {"rows": list(rows), "excerpts": list(excerpts)}, get)

    def finish(self):
        return steps.finish(self.out)

    def final_rows(self, got=None):
        got = got or self.finish()
        return worldmark.rows(self.out / got["rows"]["path"]) if got["rows"] else []

    def read(self, name):
        return json.loads((self.out / name).read_text(encoding="utf-8"))


class Classes(Base):
    def test_every_finding_needs_a_class(self):
        self.intake()
        got = self.classes({"classes": [klass(1)]})
        self.assertFalse(got["ok"])
        self.assertIn("行の無い依頼の行: [2]", got["reason"])
        self.assertFalse(got["done"])

    def test_class_text_with_target_identifier_is_refused(self):
        self.intake()
        got = self.classes({"classes": [klass(1, queries=["red_check.py compile error"]), doc_class()]})
        self.assertFalse(got["ok"])
        self.assertIn("red_check.py", got["reason"])

    def test_every_row_needs_queries(self):
        """文書だけの依頼の行でも、言い直しの行に検索語が無ければ拒む（語の直しだけの行の例外は無い）"""
        self.intake()
        got = self.classes({"classes": [klass(1), {**doc_class(2), "queries": []}]})
        self.assertFalse(got["ok"], got)
        self.assertIn("queries が無い", got["reason"])

    def test_queries_needed_on_every_row_and_capped(self):
        self.intake()
        got = self.classes({"classes": [klass(1, queries=[]), {**doc_class(2), "queries": []}]})
        self.assertIn("classes[0]", got["reason"])
        self.assertIn("classes[1]", got["reason"], "文書だけの行も例外にしない")
        self.assertIn("queries が無い", got["reason"])
        got = self.classes({"classes": [klass(1, queries=["a b", "c d", "e f", "g h"]), doc_class()]})
        self.assertIn(f"{steps.MAX_QUERIES} 本まで", got["reason"])

    def test_rejections_counted_by_rolekit(self):
        """拒否は rolekit の控えに積まれ、3 回目で done。次の回の指示は、それまでの却下の全部を共通の断片の段落で頭に持つ"""
        self.intake()
        reasons = []
        for n in range(1, rolekit.GIVE_UP_AFTER + 1):
            got = self.classes({"classes": []})
            self.assertEqual(got["done"], n == rolekit.GIVE_UP_AFTER, n)
            reasons.append(got["reason"])
        self.assertTrue(rolekit.given_up_reason(self.out, steps.CLASSES_ROLE), "諦めた理由を rolekit が返す")
        self.assertEqual(rolekit.rejected(self.out, steps.CLASSES_ROLE), reasons)
        first = (self.out / "world-classes-prompt-1.md").read_text(encoding="utf-8")
        self.assertTrue(first.startswith("You are the restater"), "1 回目は却下の段落を持たない")
        second = (self.out / "world-classes-prompt-2.md").read_text(encoding="utf-8")
        self.assertTrue(second.startswith("## Why your previous answer was rejected"))
        self.assertIn(rolekit.rejects_text(reasons[:1]), second)
        third = (self.out / "world-classes-prompt-3.md").read_text(encoding="utf-8")
        self.assertIn(rolekit.rejects_text(reasons[:2]), third, "3 回目には 1 回目の拒否も貼る")

    def test_class_ids_are_stable_by_text(self):
        self.intake()
        self.assertTrue(self.classes({"classes": [klass(1, problem=f" {PROBLEM} "), doc_class()]})["ok"])
        rows = self.read(steps.CLASSES)
        self.assertEqual(rows[0]["class_id"], steps.class_id(PROBLEM), "前後の空白違いの同じ字の問題は同じ id")
        self.assertEqual(rows[1]["class_id"], steps.class_id(DOC_PROBLEM))

    def test_purpose_means_are_shown(self):
        self.intake(purpose="赤を言語に依らず判じる", means=["読むだけの役を足す"])
        prompt = steps.classes_prompt(self.out)["prompt"]
        self.assertIn("赤を言語に依らず判じる", prompt)
        self.assertIn("- 読むだけの役を足す", prompt)
        self.intake()
        prompt = steps.classes_prompt(self.out)["prompt"]
        self.assertIn(steps.NOT_GIVEN, prompt)
        self.assertNotIn("Means the request proposed", prompt, "解き方が無ければ段落ごと入れない")


class Plan(Base):
    def test_plan_holds_only_taken_and_over(self):
        self.intake()
        self.assertTrue(self.classes({"classes": [klass(1), doc_class()]})["ok"])
        self.assertEqual(self.plan(), {"due": True, "reason": ""})
        self.assertEqual(set(self.read(steps.PLAN)), {"over", "taken"})

    def test_doc_only_rows_still_go_to_judge(self):
        self.intake(findings=[FINDINGS[1]])
        self.assertTrue(self.classes({"classes": [doc_class(1)]})["ok"])
        self.assertTrue(self.plan()["due"])

    def test_web_off_collects_nothing_and_still_judges(self):
        """web が off の run も web の役に回り、指示は道具を使うなと言う（on の指示は抜き書きの返し方を言う）"""
        prompts = {}
        for web in ("on", "off"):
            self.intake(web=web)
            self.classes({"classes": [klass(1), doc_class()]})
            self.assertTrue(self.plan()["due"])
            prompts[web] = steps.judge_prompt(self.out)["prompt"]
        self.assertFalse(self.read(steps.INTAKE)["web"])
        self.assertIn("The web is off for this run", prompts["off"])
        self.assertNotIn("List `excerpts`", prompts["off"])
        self.assertNotIn("The web is off", prompts["on"])
        self.assertIn("List `excerpts`", prompts["on"])
        self.assertIn(f"At most {steps.MAX_EXCERPTS * 2} excerpts", prompts["on"], "上限は取った類の数を掛ける")

    def test_web_off_never_refetches(self):
        self.intake(web="off")
        self.classes({"classes": [klass(1), doc_class()]})
        self.plan()
        steps.judge_prompt(self.out)

        def never(url):
            raise AssertionError(f"web が off なのに取り直した: {url}")
        self.assertTrue(self.judge([judged(), judged(2, verdict="none", challenge="")], get=never)["ok"])
        doc = self.read(steps.VERIFIED)
        self.assertEqual((doc["kept"], doc["dropped"], doc["offline"]), ([], [], False))
        self.assertNotIn("網に届かなかった", self.finish()["reason"])

    def test_class_cap_counts_over(self):
        many = [{"where": f"src/m{i}.py", "text": f"直し {i}"} for i in range(steps.MAX_CLASSES + 2)]
        self.intake(findings=many)
        reply = {"classes": [klass(i + 1, problem=f"類の文 その{i}", queries=[f"問い {i}"]) for i in range(len(many))]}
        self.assertTrue(self.classes(reply)["ok"])
        self.plan()
        pl = self.read(steps.PLAN)
        self.assertEqual(len(pl["taken"]), steps.MAX_CLASSES)
        self.assertEqual(pl["over"], [steps.MAX_CLASSES + 1, steps.MAX_CLASSES + 2])

    def test_missing_plan_reports_failed(self):
        self.intake()
        self.classes({"classes": [klass(1), doc_class()]})
        got = self.finish()
        self.assertEqual(got["status"], "failed")
        self.assertIn("類を決める node", got["reason"])

    def test_classes_given_up_skips_everything(self):
        self.intake()
        for _ in range(rolekit.GIVE_UP_AFTER):
            self.classes({"classes": []})
        self.assertFalse(self.plan()["due"])
        got = self.finish()
        self.assertEqual((got["ok"], got["status"]), (False, "failed"))
        self.assertIn("言い直す役", got["reason"])
        self.assertIn("3 回とも", got["reason"])

    def test_failed_loop_keeps_last_reject_reason(self):
        self.intake()
        rejected = self.classes({"classes": []})
        self.assertFalse(rejected["done"])
        got = self.finish()
        self.assertEqual(got["status"], "failed")
        self.assertIn(rejected["reason"], got["reason"])


class Verify(Base):
    """web の役の受け付けが、返答の抜き書きを機械が取り直した本文で照らす（役の取得の記録は引かない）"""

    def setUp(self):
        super().setUp()
        self.intake(findings=FINDINGS[:1])
        self.classes({"classes": [klass(1)]})
        self.plan()
        steps.judge_prompt(self.out)

    def test_verify_keeps_fetched_excerpt_and_caps_total(self):
        ex = {"id": "x1", "url": URL, "excerpt": GOOD}
        made_up = {"id": "x2", "url": URL, "excerpt": "Nothing like this sentence is on that page at all."}
        with self.subTest("残る"):
            self.assertTrue(self.judge([judged(sources=["x1"])], [ex])["ok"])
            self.assertEqual([k["id"] for k in self.read(steps.VERIFIED)["kept"]], ["x1"])
            row = self.final_rows()[0]
            self.assertEqual((row["basis"], row["sources"]), ("web", [ex]))
        with self.subTest("上限"):
            many = [{"id": f"x{i}", "url": URL, "excerpt": GOOD} for i in range(1, steps.MAX_EXCERPTS + 3)]
            self.assertTrue(self.judge([judged(sources=["x1"])], many)["ok"])
            doc = self.read(steps.VERIFIED)
            self.assertEqual((len(doc["kept"]), doc["over_excerpts"]), (steps.MAX_EXCERPTS, 2))
            self.assertEqual(self.finish()["dropped"], 2)
        with self.subTest("落ちた根拠だけ"):
            self.assertTrue(self.judge([judged(sources=["x2"])], [made_up])["ok"])
            row = self.final_rows()[0]
            self.assertEqual((row["basis"], row["sources"]), ("knowledge", []))
            self.assertEqual(self.finish()["dropped"], 1)
        with self.subTest("落ちた根拠と残る根拠"):
            self.assertTrue(self.judge([judged(sources=["x1", "x2"])], [ex, made_up])["ok"])
            row = self.final_rows()[0]
            self.assertEqual(([s["id"] for s in row["sources"]], row["basis"]), (["x1"], "web"))

    def test_verified_fields_offline_and_web_off(self):
        ex = {"id": "x1", "url": URL, "excerpt": GOOD}
        with self.subTest("控えの欄"):
            self.assertTrue(self.judge([judged(sources=["x1"])], [ex])["ok"])
            self.assertEqual(set(self.read(steps.VERIFIED)), {"kept", "dropped", "offline", "over_excerpts"})

        def down(url):
            raise steps.webget.FetchError("網に届かない")
        with self.subTest("網に届かない"):
            self.assertTrue(self.judge([judged(sources=["x1"])], [ex], get=down)["ok"])
            self.assertTrue(self.read(steps.VERIFIED)["offline"])
            self.assertEqual(self.final_rows()[0]["basis"], "knowledge")
            self.assertIn(worldmark.NOT_WEB, self.finish()["reason"])
        with self.subTest("web が off"):
            self.intake(findings=FINDINGS[:1], web="off")
            self.classes({"classes": [klass(1)]})
            self.plan()
            steps.judge_prompt(self.out)
            calls = []
            got = self.judge([judged(sources=["x1"])], [ex], get=lambda u: calls.append(u) or (200, PAGE))
            self.assertTrue(got["ok"], got)
            self.assertEqual(calls, [])
            row = self.final_rows()[0]
            self.assertEqual((row["basis"], row["sources"]), ("knowledge", []))

    def test_malformed_reply_is_named(self):
        ex = {"id": "x1", "url": URL, "excerpt": GOOD}
        self.assertIn("rows", steps._take_judge(self.out, None, None)["reason"])
        self.assertIn("オブジェクトでない", steps.accept(self.out, steps.JUDGE_ROLE, "null")["reason"])
        self.assertIn("excerpts は", steps._take_judge(self.out, {"rows": [judged()], "excerpts": "x"}, None)["reason"])
        self.assertIn("excerpts[0]", self.judge([judged()], [{"id": "x1"}])["reason"])
        self.assertIn("重なる", self.judge([judged()], [ex, ex])["reason"])
        self.assertIn("excerpts の id でない", self.judge([judged(sources=["x9"])], [ex])["reason"])


class Judge(Base):
    def setUp(self):
        super().setUp()
        self.intake(findings=FINDINGS[:1])
        self.classes({"classes": [klass(1)]})
        self.plan()
        self.prompt = steps.judge_prompt(self.out)["prompt"]

    def accept(self, *rows):
        return steps.accept(self.out, steps.JUDGE_ROLE, json.dumps({"rows": list(rows), "excerpts": []}, ensure_ascii=False))

    def test_prompt_asks_for_excerpts_without_target_text(self):
        """web の役に渡る文は名を外す: 依頼の行の本文も where も載らない。外への検索の決まりは共通の断片から 1 回だけ入る"""
        self.assertIn(PROBLEM, self.prompt)
        self.assertIn("List `excerpts`", self.prompt)
        self.assertNotIn(GOOD, self.prompt)
        self.assertNotIn(FINDINGS[0]["text"], self.prompt)
        self.assertNotIn(FINDINGS[0]["where"], self.prompt)
        self.assertEqual(self.prompt.count("Rules for queries to outside services"), 1)
        self.assertNotIn("sub-agent", self.prompt, "この役は下請けを起こさない")

    def test_differs_needs_challenge(self):
        got = self.accept(judged(challenge="短い"))
        self.assertFalse(got["ok"])
        self.assertIn("challenge", got["reason"])

    def test_basis_is_set_by_machine_only(self):
        self.assertNotIn("basis", self.prompt)
        self.assertIn("excerpts の id でない", self.accept(judged(sources=["x9"]))["reason"])
        self.assertTrue(self.accept(judged(basis="web"))["ok"], "返答の basis は受け付けが見ない")
        self.assertEqual(self.final_rows()[0]["basis"], "knowledge")
        self.assertTrue(self.judge([judged(basis="knowledge", sources=["x1"])], [{"id": "x1", "url": URL, "excerpt": GOOD}])["ok"])
        self.assertEqual(self.final_rows()[0]["basis"], "web")

    def test_verdict_none_only_without_proposed(self):
        self.assertIn("verdict none", self.accept(judged(verdict="none", challenge=""))["reason"])

    def test_practice_with_target_identifier_is_refused(self):
        self.assertIn("src/red_check.py", self.accept(judged(practice="src/red_check.py を直す"))["reason"])

    def test_every_judged_row_needed(self):
        self.assertIn("行の無い依頼の行: [1]", self.accept()["reason"])

    def test_knowledge_row_is_written(self):
        self.assertTrue(self.accept(judged())["ok"])
        got = self.finish()
        self.assertEqual((got["ok"], got["status"]), (True, "ok"))
        self.assertEqual([(r["basis"], r["versus"]["verdict"]) for r in self.final_rows(got)], [("knowledge", "differs")])

    def test_web_row_carries_kept_sources(self):
        self.assertTrue(self.judge([judged(sources=["x1"])], [{"id": "x1", "url": URL, "excerpt": GOOD}])["ok"])
        got = self.finish()
        rows = self.final_rows(got)
        self.assertEqual(rows[0]["sources"], [{"id": "x1", "url": URL, "excerpt": GOOD}])
        self.assertEqual(rows[0]["where"], FINDINGS[0]["where"])
        self.assertEqual(rows[0]["versus"]["proposed"], klass()["proposed"], "依頼の解き方は言い直しの行から機械が写す")
        self.assertEqual((got["classes"], got["dropped"]), (1, 0))

    def test_exit_is_the_block_output(self):
        """出口は block の返りの欄だけ。行は lib/worldmark の行の形で、報告の行は値から組む"""
        self.assertTrue(self.judge([judged(sources=["x1"])], [{"id": "x1", "url": URL, "excerpt": GOOD}])["ok"])
        got = self.finish()
        self.assertEqual(set(got), {"ok", "status", "reason", "rows", "classes", "dropped", "report"})
        self.assertEqual(got["rows"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": steps.WORLD_FILE})
        for r in self.final_rows(got):
            self.assertEqual(set(r), set(worldmark.FIELDS))
        self.assertEqual(got["report"][-1], "- 類 1・落とした抜き書き 0")
        self.assertIn("定石と違う", got["report"][0])
        self.assertEqual(self.read(steps.STATE)["status"], "ok")

    def test_judge_given_up_reports_failed(self):
        for _ in range(rolekit.GIVE_UP_AFTER):
            steps.judge_prompt(self.out)
            self.accept()
        got = self.finish()
        self.assertEqual(got["status"], "failed")
        self.assertIn("判断する役", got["reason"])
        self.assertIsNone(got["rows"], "行の無い出口は pointer を持たない（Archon は空のファイルの pointer を拒む）")
        self.assertEqual(got["report"], [f"- 世界の解の段が落ちた（行なしで進んだ）: {got['reason']}"])


class Intake(Base):
    def test_unreadable_request_reports_failed_without_stopping(self):
        got = steps.intake(self.out, request="none.json", purpose="", means="[]", web="on", lang="")
        self.assertFalse(got["due"])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("none.json", fin["reason"])

    def test_empty_request_is_not_due_and_ok(self):
        self.assertFalse(self.intake(findings=[])["due"])
        got = self.finish()
        self.assertEqual((got["status"], got["rows"]), ("ok", None))

    def test_bad_web_word_is_reported(self):
        self.assertIn("web", self.intake(web="maybe")["reason"])

    def test_request_shape_is_checked_by_its_schema(self):
        """依頼は行の配列か、それを findings に持つ工場の依頼のファイルの形。形に合わなければ形のファイルを名指す"""
        container = {"findings": FINDINGS[:1], "pr": [1]}
        got = steps.intake(self.out, request=json.dumps(container, ensure_ascii=False), purpose="", means="[]", web="on", lang="")
        self.assertEqual((got["due"], got["findings"]), (True, 1))
        got = steps.intake(self.out, request='[{"text": "no where"}]', purpose="", means="[]", web="on", lang="")
        self.assertIn("request.schema.json", got["reason"])
        self.assertIn("where", got["reason"])

    def test_request_by_pointer_and_by_path(self):
        (self.out / "req.json").write_text(json.dumps(FINDINGS, ensure_ascii=False), encoding="utf-8")
        got = steps.intake(self.out, request=self.run.pointer("req.json"), purpose="", means="[]", web="on", lang="")
        self.assertEqual(got["findings"], 2)
        (self.run.repo / "mine.json").write_text(json.dumps(FINDINGS[:1], ensure_ascii=False), encoding="utf-8")
        got = steps.intake(self.out, request="mine.json", purpose="", means="[]", web="on", lang="")
        self.assertEqual(got["findings"], 1, "作業ツリーからの相対のパス")

    def test_intake_clears_only_its_own_files(self):
        (self.out / "someone-else.json").write_text("{}", encoding="utf-8")
        self.intake()
        self.classes({"classes": []})
        self.assertTrue((self.out / "rejects-classes.json").is_file())
        self.intake()
        self.assertFalse((self.out / "rejects-classes.json").exists(), "前の run の却下を数えない")
        self.assertFalse((self.out / "world-classes-prompt-1.md").exists())
        self.assertTrue((self.out / "someone-else.json").is_file(), "place の中のほかの物は消さない")


if __name__ == "__main__":
    unittest.main()
