"""案内の道の目の block を、script を子のプロセスで回して確かめる（docs/design/guidance-path.md の試験の節）。

使い捨ての作業ツリーに入口のファイルを置き、頼み 2 つを読み手の台本の返答で辿らせ、1 つは閉じるべき所に置き（当たり）、1 つは
外に置く（外れ）。外れだけが案内を見直す役に回り、出口は頼みごとの道と案内の直しを返す。
"""
import json
import unittest

from tests.bin import hermetic
from tests.blocks import kit

REQUESTS = [
    {"id": "add-check", "request": "Add one more check that an AI role answer must pass.", "closes": ["blocks/world/"]},
    {"id": "new-eye", "request": "Add a new review viewpoint as its own block.", "closes": ["blocks/new-eye/", "docs/design/new-eye.md"]},
]


def walk(placed, steps=("AGENTS.md",)):
    return {"steps": [{"file": f, "why": "the entry"} for f in steps], "placed": [{"path": p, "change": "edit"} for p in placed],
            "copied": [{"path": "blocks/world/", "why": "the model block"}], "stuck": [], "guessed": []}


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "guidance-path")
        (self.run.repo / "AGENTS.md").write_text("# entry\n", encoding="utf-8")
        (self.run.repo / "README.md").write_text("# readme\n", encoding="utf-8")

    def walks(self, *replies):
        self.assertEqual(self.run.script("intake", requests=json.dumps(REQUESTS), entry="", lang=""),
                         {"due": True, "requests": 2, "reason": ""})
        outs = []
        for reply in replies:
            prep = self.run.script("walk_prep", "walk-loop.walk-prep")
            outs.append((prep, self.run.script("walk_accept", "walk-loop.walk-accept", reply=json.dumps(reply))))
        return outs

    def test_hit_and_miss_lead_to_fixes_for_the_miss_only(self):
        (first, a1), (second, a2) = self.walks(walk(["blocks/world/src/steps.py"]), walk(["lib/neweye.py"]))
        self.assertIn(REQUESTS[0]["request"], first["prompt"])
        for close in [c for r in REQUESTS for c in r["closes"]] + ["closes", "Should close in"]:
            self.assertNotIn(close, first["prompt"], "読み手に閉じるべき所を見せない（指示の全部で）")
            self.assertNotIn(close, second["prompt"])
        self.assertIn("- README.md\n- AGENTS.md", first["prompt"], "入口が空なら README.md と AGENTS.md")
        self.assertIn(REQUESTS[1]["request"], second["prompt"])
        self.assertEqual((a1["done"], a2["done"]), (False, True))
        self.assertEqual(self.run.script("compare", "compare"), {"due": True, "misses": 1, "reason": ""})
        fix_prep = self.run.script("fix_prep", "fix-loop.fix-prep")
        self.assertIn("### Request new-eye", fix_prep["prompt"])
        self.assertNotIn("### Request add-check", fix_prep["prompt"])
        self.assertIn("- Should close in: blocks/new-eye/, docs/design/new-eye.md", fix_prep["prompt"])
        fixes = {"fixes": [{"request": "new-eye", "kind": "guide", "where": "blocks/AGENTS.md",
                            "change": "Say a new viewpoint is a new folder copied from blocks/world/.", "why": "step 1"}]}
        self.assertEqual(self.run.script("fix_accept", "fix-loop.fix-accept", reply=json.dumps(fixes))["ok"], True)
        fin = self.run.script("finish", "finish")
        self.assertEqual((fin["ok"], fin["hits"], fin["misses"]), (True, 1, 1))
        self.assertEqual(fin["fixes"], fixes["fixes"])
        paths = json.loads((self.run.artifacts / fin["paths"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual([(p["id"], p["hit"]) for p in paths], [("add-check", True), ("new-eye", False)])
        self.assertIn("- 頼み new-eye: 外れ", "\n".join(fin["report"]))

    def test_walk_reply_is_checked(self):
        """開いたファイルは作業ツリーに在る物だけ・パスは根からの相対・置く所が空でない。3 回拒めば諦めて次の頼みへ進む"""
        self.run.script("intake", requests=json.dumps(REQUESTS[:1]), entry="AGENTS.md", lang="")
        bad = walk([], steps=("nothing.md",))
        bad["copied"] = [{"path": "/abs/x", "why": "x"}]
        reasons = []
        for _ in range(3):
            self.run.script("walk_prep", "walk-loop.walk-prep")
            reasons.append(self.run.script("walk_accept", "walk-loop.walk-accept", reply=json.dumps(bad)))
        self.assertIn("nothing.md", reasons[0]["reason"])
        self.assertIn("placed が空", reasons[0]["reason"])
        self.assertIn("/abs/x", reasons[0]["reason"])
        self.assertEqual([r["done"] for r in reasons], [False, False, True])
        second = (self.run.artifacts / "guidance-walk-prompt-2.md").read_text(encoding="utf-8")
        self.assertTrue(second.startswith("## Why your previous answer was rejected"))
        self.assertEqual(self.run.script("compare", "compare")["due"], False)
        fin = self.run.script("finish", "finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("諦めた", fin["reason"])

    def test_fix_reply_must_cover_every_miss(self):
        self.walks(walk(["lib/x.py"]), walk(["lib/y.py"]))
        self.run.script("compare", "compare")
        self.run.script("fix_prep", "fix-loop.fix-prep")
        partial = {"fixes": [{"request": "add-check", "kind": "rewrite", "where": "AGENTS.md", "change": "c", "why": "w"}]}
        got = self.run.script("fix_accept", "fix-loop.fix-accept", reply=json.dumps(partial))
        self.assertFalse(got["ok"])
        self.assertIn("new-eye", got["reason"])
        self.assertIn("kind は guide・model・block", got["reason"])

    def test_unreadable_records_fail_the_finish(self):
        """比べの控え・直しの控えが無い・壊れている時、出口は当たりとも直しが通ったとも読まない（E23）"""
        self.walks(walk(["blocks/world/x.py"]), walk(["lib/y.py"]))
        for broken in (None, "{"):
            with self.subTest(compare=broken):
                (self.run.artifacts / "compare.json").unlink(missing_ok=True)
                if broken is not None:
                    (self.run.artifacts / "compare.json").write_text(broken, encoding="utf-8")
                fin = self.run.script("finish", "finish")
                self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
                self.assertIn("compare.json", fin["reason"])
        self.run.script("compare", "compare")
        (self.run.artifacts / "fixes.json").write_text("{", encoding="utf-8")
        fin = self.run.script("finish", "finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("fixes.json", fin["reason"])

    def test_bad_entry_is_named(self):
        got = self.run.script("intake", requests=json.dumps(REQUESTS), entry="NOPE.md", lang="")
        self.assertFalse(got["due"])
        self.assertIn("NOPE.md", got["reason"])
        fin = self.run.script("finish", "finish")
        self.assertEqual((fin["ok"], fin["paths"]), (False, None))


class IsolationCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "guidance-path")
        (self.run.repo / "AGENTS.md").write_text("# entry\n", encoding="utf-8")

    def test_requests_are_not_taken_by_path(self):
        (self.run.repo / "reqs.json").write_text(json.dumps(REQUESTS), encoding="utf-8")
        got = self.run.script("intake", requests="reqs.json", entry="AGENTS.md", lang="")
        self.assertFalse(got["due"])
        self.assertIn("パスで受けない", got["reason"])
        (self.run.artifacts / "reqs.json").write_text(json.dumps(REQUESTS), encoding="utf-8")
        got = self.run.script("intake", requests=self.run.pointer("reqs.json"), entry="AGENTS.md", lang="")
        self.assertEqual((got["due"], got["requests"]), (True, 2), "pointer では受ける")

    def test_hidden_places_match_the_yaml_and_are_refused(self):
        import yaml
        steps = kit.load("guidance-path", "steps")
        doc = yaml.safe_load((kit.BLOCKS / "guidance-path" / "works-factory-guidance-path.yaml").read_text(encoding="utf-8"))
        walker = next(n for node in doc["nodes"] for n in (node.get("loop_group") or {}).get("nodes", []) if n["id"] == "guidance-walk")
        want = [f"Read(./{h}/**)" if not h.endswith(".md") else f"Read(./{h})" for h in steps.HIDDEN]
        self.assertEqual(walker["denied_tools"], want)
        self.assertNotIn("Bash", walker["allowed_tools"], "読み手は shell を持たない（Read の規則を抜けない）")
        (self.run.repo / "docs/design").mkdir(parents=True)
        (self.run.repo / "docs/design/guidance-path.md").write_text("x", encoding="utf-8")
        self.run.script("intake", requests=json.dumps(REQUESTS[:1]), entry="AGENTS.md", lang="")
        self.run.script("walk_prep", "walk-loop.walk-prep")
        got = self.run.script("walk_accept", "walk-loop.walk-accept",
                              reply=json.dumps(walk(["blocks/world/x.py"], steps=("AGENTS.md", "docs/design/guidance-path.md"))))
        self.assertIn("見せない所", got["reason"])
        got = self.run.script("intake", requests=json.dumps(REQUESTS[:1]), entry="docs/design/guidance-path.md", lang="")
        self.assertIn("見せない所", got["reason"])

    def test_intake_clears_only_its_own_files(self):
        (self.run.artifacts / "rejects-classes.json").write_text("[]", encoding="utf-8")
        self.run.script("intake", requests=json.dumps(REQUESTS[:1]), entry="AGENTS.md", lang="")
        self.run.script("walk_prep", "walk-loop.walk-prep")
        self.run.script("walk_accept", "walk-loop.walk-accept", reply=json.dumps(walk([])))
        self.assertTrue((self.run.artifacts / "rejects-walk-add-check.json").is_file())
        self.run.script("intake", requests=json.dumps(REQUESTS[1:]), entry="AGENTS.md", lang="")
        self.assertFalse((self.run.artifacts / "rejects-walk-add-check.json").exists(), "前の intake の頼みの控えは名で消す")
        self.assertTrue((self.run.artifacts / "rejects-classes.json").is_file(), "ほかの block の控えは消さない")


class CompareCase(unittest.TestCase):
    def test_new_block_placeholder(self):
        """{new} と {new_} は全部の置いた所で同じ 1 つの名に結ばれ、その所が作業ツリーにまだ無い時だけ当たる"""
        steps = kit.load("guidance-path", "steps")
        root = hermetic.tmpdir(self)
        closes = ["blocks/{new}/", "tests/blocks/{new_}/", "docs/design/{new}.md"]
        new = ["blocks/docs-sync/works-factory-docs-sync.yaml", "tests/blocks/docs_sync/test_docs_sync.py", "docs/design/docs-sync.md"]
        self.assertEqual(steps.judge_placed(new, closes, root), (True, ""))
        got = steps.judge_placed(["blocks/docs-sync/x.yaml", "docs/design/other.md"], closes, root)
        self.assertEqual(got[0], False)
        self.assertIn("1 つに結ばれない", got[1])
        self.assertIn("閉じるべき所の外", steps.judge_placed(["blocks/docs-sync/x", "lib/x.py"], closes, root)[1])
        (root / "blocks" / "world").mkdir(parents=True)
        got = steps.judge_placed(["blocks/world/src/x.py"], closes, root)
        self.assertEqual(got, (False, "新しい所のはずの blocks/world が作業ツリーに既に在る"))

    def test_under(self):
        steps = kit.load("guidance-path", "steps")
        self.assertTrue(steps.under("./blocks/world/src/x.py", ["blocks/world/"]))
        self.assertTrue(steps.under("docs/design/new-eye.md", ["docs/design/new-eye.md"]))
        self.assertFalse(steps.under("blocks/worldly/x.py", ["blocks/world"]))
        self.assertFalse(steps.under("lib/x.py", ["blocks/world/"]))


if __name__ == "__main__":
    unittest.main()
