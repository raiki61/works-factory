"""世界の解の block を、script を子のプロセスで回して確かめる（docs/design/README.md の 11.2・docs/design/world.md の 8 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → restate_prep → 台本の返答 →
restate_accept → pick → web_prep → 台本の返答 → web_accept → finish と回す（web は off。網に出ない）。YAML と筋書きの揃いも見る。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest

import yaml

from tests.blocks import kit

BLOCK = kit.BLOCKS / "world"
REQUEST = json.dumps([{"where": "README", "text": "The cache folder should follow the user settings"}])
CLASSES = {"classes": [{"finding": 1, "problem": "where a command line tool keeps its cache files",
                        "activity": "choosing the cache location of a tool", "proposed": "read one environment variable",
                        "queries": ["cache directory convention for command line tools"]}]}
JUDGED = {"rows": [{"finding": 1, "practice": "Follow the platform base directory convention for cache files.", "sources": [],
                    "applies": "Put the cache under the platform cache home.", "not_applies": "", "verdict": "differs",
                    "challenge": "The request reads one variable; the practice is the full base directory lookup. Choose it."}],
          "excerpts": []}


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "world")

    def walk(self, include="", classes=CLASSES, judged=JUDGED, **inputs):
        ports = {"request": REQUEST, "purpose": "Cached files go where the user expects them", "means": '["read one environment variable"]',
                 "web": "off", "lang": "", **inputs}
        node = (lambda name: f"{include}__{name}") if include else (lambda name: name)
        loop = (lambda group, name: f"{include}__{group}.{name}") if include else (lambda group, name: f"{group}.{name}")
        out = {"intake": self.run.script("intake", node("intake"), **ports)}
        out["restate_prep"] = self.run.script("restate_prep", loop("world-classes-loop", "world-classes-prep"))
        out["restate_accept"] = self.run.script("restate_accept", loop("world-classes-loop", "world-classes-accept"),
                                                reply=json.dumps(classes))
        out["pick"] = self.run.script("pick", node("pick"))
        if out["pick"]["due"]:
            group, prep = ("world-judge-loop", "web_prep") if out["pick"]["web"] else ("world-judge-offline-loop", "offline_prep")
            out["web_prep"] = self.run.script(prep, loop(group, f"{group.removesuffix('-loop')}-prep"))
            out["web_accept"] = self.run.script("web_accept", loop(group, f"{group.removesuffix('-loop')}-accept"),
                                                reply=json.dumps(judged))
        out["finish"] = self.run.script("finish", node("finish"))
        return out

    def test_port_values_alone_reach_the_rows(self):
        got = self.walk()
        self.assertEqual(got["intake"], {"due": True, "findings": 1, "reason": ""})
        self.assertIn("1. where: README", got["restate_prep"]["prompt"])
        self.assertIn("- read one environment variable", got["restate_prep"]["prompt"])
        self.assertIn("in the language of the request", got["restate_prep"]["prompt"], "lang が空なら既定の言語の文")
        self.assertEqual(got["restate_accept"], {"ok": True, "done": True, "reason": ""})
        self.assertIn("The web is off for this run", got["web_prep"]["prompt"])
        self.assertNotIn("README", got["web_prep"]["prompt"], "web の役に依頼の行は渡らない")
        fin = got["finish"]
        self.assertEqual((fin["ok"], fin["status"]), (True, "ok"))
        self.assertEqual(fin["rows"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "world.jsonl"})
        rows = [json.loads(line) for line in (self.run.artifacts / "world.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["finding"], r["where"], r["basis"], r["versus"]["verdict"]) for r in rows],
                         [(1, "README", "knowledge", "differs")])
        self.assertIn("web が off", fin["reason"])
        self.assertTrue(fin["report"][0].startswith("- 類 w-"), fin["report"])

    def test_included_block_writes_in_its_own_place(self):
        """include された時は place が include の道に分かれ（loop の本体も同じ所）、出力の pointer もそこを指す"""
        got = self.walk(include="world")
        self.assertEqual(got["finish"]["rows"]["path"], "world/world.jsonl")
        self.assertTrue((self.run.artifacts / "world" / "world-classes-prompt-1.md").is_file())
        self.assertTrue((self.run.artifacts / "world" / "world-judge-offline-prompt-1.md").is_file(), "web が off なら道具の無い役の指示")
        self.assertFalse((self.run.artifacts / "world.jsonl").exists())

    def test_lang_reaches_the_prompt(self):
        got = self.walk(lang="Japanese")
        self.assertIn("in Japanese", got["restate_prep"]["prompt"])
        self.assertIn("in Japanese", got["web_prep"]["prompt"])

    def test_rejected_reply_brings_the_reason_to_the_next_prompt(self):
        """拒んだ返答の理由は、次の回の指示の頭に共通の断片の段落で入る。出口は落ちずに status: failed と理由を返す"""
        bad = {"classes": [{**CLASSES["classes"][0], "queries": []}]}
        got = self.walk(classes=bad)
        self.assertEqual(got["restate_accept"]["done"], False)
        self.assertIn("queries が無い", got["restate_accept"]["reason"])
        again = self.run.script("restate_prep", "world-classes-loop.world-classes-prep")
        self.assertTrue(again["prompt"].startswith("## Why your previous answer was rejected"))
        self.assertIn("queries が無い", again["prompt"])
        self.assertTrue((self.run.artifacts / "world-classes-prompt-2.md").is_file())
        fin = self.run.script("finish", "finish")
        self.assertEqual((fin["ok"], fin["status"], fin["rows"]), (False, "failed", None))
        self.assertIn("queries が無い", fin["reason"])

    def test_unreadable_port_does_not_stop_the_run(self):
        got = self.run.script("intake", request=self.run.pointer("absent.json"), purpose="", means="[]", web="on", lang="")
        self.assertFalse(got["due"])
        self.assertIn("入力 request", got["reason"])
        self.assertEqual(self.run.script("pick")["due"], False)
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("absent.json", fin["reason"])

    def test_prep_without_intake_fails_the_node(self):
        """指示が組めない prep は空の指示を返さず node が落ちる（AI に生の型が届かない）"""
        self.assertIn("intake.json", self.run.failing("restate_prep"))


class ShapeCase(unittest.TestCase):
    """YAML と筋書きの揃い（block の形の検査は tests/layers/test_block_shape.py。ここは world だけの揃い）"""

    def setUp(self):
        self.doc = yaml.safe_load((BLOCK / "works-factory-world.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in self.doc["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        rolekit = kit.load("world", "steps").rolekit
        for loop in ("world-classes-loop", "world-judge-loop", "world-judge-offline-loop"):
            self.assertEqual(self.nodes[loop]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_roles_have_only_their_tools(self):
        """言い直す役は道具を持たず、web の役は web の検索と取得だけ（keep-essence の 12。対象を読まずに上の類に上がる）"""
        loops = ("world-classes-loop", "world-judge-loop", "world-judge-offline-loop")
        body = {n["id"]: n for loop in loops for n in self.nodes[loop]["loop_group"]["nodes"]}
        self.assertEqual(body["world-classes"]["allowed_tools"], [])
        self.assertEqual(body["world-judge"]["allowed_tools"], ["WebSearch", "WebFetch"])
        self.assertEqual(body["world-judge-offline"]["allowed_tools"], [], "web が off の run は道具で web を断つ")
        self.assertEqual(body["world-judge-offline"]["output_format"], body["world-judge"]["output_format"])

    def test_web_switch_picks_exactly_one_judge_loop(self):
        whens = {self.nodes[n]["when"] for n in ("world-judge-loop", "world-judge-offline-loop")}
        self.assertEqual(whens, {"$pick.output.due == true && $pick.output.web == true",
                                 "$pick.output.due == true && $pick.output.web == false"})
        for node in ("world-judge", "world-judge-offline"):
            self.assertTrue((BLOCK / "prompts" / f"{node}.md").read_text(encoding="utf-8").endswith("{part:world-judge}\n"), "同じ部品の md から組む")
        self.assertIn("{shared:query-rule}", (BLOCK / "prompts" / "world-judge.md").read_text(encoding="utf-8"))
        self.assertNotIn("{shared:query-rule}", (BLOCK / "prompts" / "world-judge-offline.md").read_text(encoding="utf-8"),
                         "道具を持たない役に外への検索の決まりを渡さない")

    def test_web_off_fixture_needs_no_network(self):
        fixture = kit.fixture("world", "standalone")
        self.assertEqual(fixture["fixture"]["inputs"]["web"], "off")
        self.assertEqual(fixture["world-judge-offline"]["excerpts"], [])


if __name__ == "__main__":
    unittest.main()
