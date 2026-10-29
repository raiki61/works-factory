"""構造の目の block を、script を子のプロセスで回して確かめる（docs/design/structure.md の 7 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、survey → prep → 台本の返答 → take → finish と回す。
YAML と筋書きの揃いも見る。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import pathlib
import shutil
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "structure"
MEAN, CLAMP, LOOSE = "stats.py mean: 分母を直す", "stats.py clamp: 上限を直す", "書き方の全体"
FILES = {"stats.py": "def mean(xs):\n    return sum(xs) / 2\n\n\ndef clamp(x, hi):\n    return min(x, hi)\n", "README.md": "# stats\n"}
UNITS = [{"id": MEAN, "paths": ["stats.py"], "summary": "mean の分母"}, {"id": CLAMP, "paths": ["stats.py"], "summary": "clamp の上限"}]
CONCEPT_MAP = ("# 地図\n\n### `outcome` run の結末\n\n- 状態: 住処あり\n- 住処: `src/report.py`\n\n"
               "### `halt` 止め札\n\n- 状態: 住処あり\n- 住処: `src/halt.py`\n")
CONCEPT_TABLE = {"exclude": ["docs/**"], "concepts": {
    "outcome": {"status": "住処あり", "fences": [{"what": "結末の語", "pattern": "\"round_limit\"", "allowed": ["src/report.py"], "known": {}}]},
    "halt": {"status": "住処あり", "fences": [{"what": "止め札", "pattern": "\"STOP\"", "allowed": ["src/halt.py"], "known": {}}]}}}


def clean(unit_id, evidence="/units/0/id") -> dict:
    return {"unit_id": unit_id, "verdict": "汚れない", "faces": [], "evidence": [evidence], "reason": "知る場所が増えない"}


def dirty(unit_id, **more) -> dict:
    return {"unit_id": unit_id, "verdict": "汚れる", "faces": [2], "evidence": ["/units/0/measure"], "reason": "責務を割る",
            "chosen": "1 か所に固める", "chosen_reason": "読み直しを割らない", **more}


UP = {"route": "人に上げる", "rejected": [{"option": "2 か所に置く", "cost": "読み直しが割れる"}],
      "undecided_because": "人の前の決定が 2 つの置き場を別々に推していて、どちらにも決まらない"}


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "structure")
        self.target(FILES)

    def target(self, files: dict) -> None:
        """files を書いて commit する"""
        for rel, text in files.items():
            (self.run.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.run.repo / rel).write_text(text, encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "target")

    def survey(self, units=UNITS, include="", **inputs):
        return self.run.script("survey", include, **{"units": json.dumps(units, ensure_ascii=False), "policy": "", **inputs})

    def take(self, reply, include=""):
        return self.run.script("take", include, reply=json.dumps(reply, ensure_ascii=False))

    def place(self, rel=""):
        return self.run.artifacts / rel

    def read(self, rel):
        return json.loads(self.place(rel).read_text(encoding="utf-8"))

    def finish(self, include=""):
        return self.run.script("finish", include)

    def walk(self, replies, units=UNITS, **inputs):
        out = {"survey": self.survey(units, **inputs)}
        for reply in replies:
            out["prep"] = self.run.script("prep")
            out["take"] = self.take(reply)
            if out["take"]["done"]:
                break
        out["finish"] = self.finish()
        return out


class FlowCase(_RepoCase):
    def test_port_values_alone_reach_the_state(self):
        got = self.walk([{"rows": [clean(MEAN), clean(CLAMP, "/units/1/id")]}])
        self.assertEqual(got["survey"], {"eye": True, "sketch": True, "reason": ""})
        self.assertEqual((got["prep"]["attempt"], got["take"]["ok"], got["take"]["done"]), (1, True, True))
        fin = got["finish"]
        self.assertEqual((fin["ok"], fin["status"], fin["dirty"], fin["escalate"]), (True, "ok", 0, 0))
        self.assertEqual(fin["structure"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "structure-state.json"})
        state = self.read("structure-state.json")
        self.assertEqual((state["status"], state["skipped"]), ("ok", []))
        self.assertEqual(len([line for line in self.place("design.jsonl").read_text(encoding="utf-8").splitlines() if line]), 2)
        self.assertTrue(self.place("structure-eye-prompt-1.md").is_file())
        self.assertEqual(fin["optional"][0], {"node": "measure", "bare": False})
        self.assertTrue(any("構造の実測と目で増えた時間" in line for line in fin["report"]), fin["report"])

    def test_dirty_rows_are_counted_and_route_up_reaches_the_state(self):
        """人に上げる行は設計の行に残り（承認ノードの問いになる）、出口が数を返す"""
        got = self.walk([{"rows": [dirty(MEAN, **UP), clean(CLAMP, "/units/1/id")]}])
        fin = got["finish"]
        self.assertEqual((fin["ok"], fin["dirty"], fin["escalate"]), (True, 1, 1))
        rows = [json.loads(line) for line in self.place("design.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual((rows[0]["route"], rows[0]["route_reason"]), ("人に上げる", UP["undecided_because"]))

    def test_own_decision_gets_the_default_route(self):
        self.walk([{"rows": [dirty(MEAN), clean(CLAMP, "/units/1/id")]}])
        row = json.loads(self.place("design.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((row["route"], row["route_reason"]), ("自分で決める", "目が決め手から 1 つに決めた（決めきれない訳を書かなかった）"))

    def test_third_rejection_gives_up_and_the_state_names_the_last_reason(self):
        self.survey()
        got = []
        for n in range(3):
            prep = self.run.script("prep")
            self.assertEqual(prep["attempt"], n + 1)
            if got:   # どの回の目も前の回までの拒否の全部を読む
                self.assertTrue(prep["prompt"].startswith("## Why your previous answer was rejected"), prep["prompt"][:80])
                self.assertIn(got[-1]["reason"], prep["prompt"])
            got.append(self.take({"rows": []}))
        self.assertEqual([(g["ok"], g["done"], g["give_up"]) for g in got], [(False, False, False)] * 2 + [(False, True, True)])
        self.assertEqual(self.read("eye.json")["status"], "gave_up")
        self.assertEqual(self.place("design.jsonl").stat().st_size, 0)
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertEqual(fin["reason"], f"構造の目の返答が 3 回とも受け付けで拒まれた: {got[-1]['reason']}")

    def test_lang_reaches_the_prompt(self):
        self.survey()
        self.assertIn("in the language of the request", self.run.script("prep", lang="")["prompt"], "lang が空なら共通の既定の言語の文")
        self.assertIn("in Japanese", self.run.script("prep", lang="Japanese")["prompt"])

    def test_unreadable_reply_is_a_rejection_not_a_crash(self):
        self.survey()
        self.run.script("prep")
        got = self.run.script("take", reply="{壊れた")
        self.assertEqual((got["ok"], got["done"]), (False, False))

    def test_included_block_writes_in_its_own_place(self):
        self.survey(include="structure__measure")
        prep = self.run.script("prep", "structure__structure-eye-loop.structure-eye-prep")
        self.assertEqual(prep["attempt"], 1)
        self.assertTrue((self.place("structure") / "structure-eye-prompt-1.md").is_file())
        self.assertFalse(self.place("structure.json").exists())
        fin = self.finish("structure__finish")
        self.assertEqual(fin["structure"]["path"], "structure/structure-state.json")
        self.assertEqual(fin["status"], "failed", "目の受け付けが済んでいない")

    def test_measure_failure_and_unreadable_units_do_not_stop(self):
        shutil.rmtree(self.run.repo / ".git")   # git の無い対象では実測が落ちる
        got = self.survey()
        self.assertFalse(got["eye"])
        self.assertEqual(self.read("structure.json")["status"], "failed")
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("実測が落ちた", fin["reason"])
        run = kit.Run(self, "structure")
        broken = run.script("survey", units="{壊れた", policy="")
        self.assertFalse(broken["eye"])
        self.assertIn("入力 units", broken["reason"])
        fin = run.script("finish")
        self.assertEqual((fin["status"], fin["structure"]["path"]), ("failed", "structure-state.json"))

    def test_unit_without_paths_is_skipped_and_named(self):
        got = self.survey([{"id": MEAN, "paths": ["stats.py"], "summary": "mean の分母"}, {"id": LOOSE, "paths": [], "summary": "書き方の全体"}])
        self.assertTrue(got["eye"])
        self.assertEqual([u["id"] for u in self.read("structure.json")["units"]], [MEAN])
        self.assertEqual(self.read("skipped-units.json"), [LOOSE])
        self.run.script("prep")
        self.take({"rows": [clean(MEAN)]})
        self.finish()
        self.assertEqual(self.read("structure-state.json")["skipped"], [LOOSE])

    def test_no_measured_unit_skips_the_eye_but_still_returns_ok(self):
        got = self.survey([{"id": LOOSE, "paths": [], "summary": "書き方の全体"}])
        self.assertEqual(got, {"eye": False, "sketch": False, "reason": "測れた単位が無い"})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["dirty"]), (True, "ok", 0))
        self.assertEqual(self.read("structure-state.json")["skipped"], [LOOSE])

    def test_fresh_measure_drops_old_eye_state_and_only_its_own_files(self):
        self.place("eye.json").write_text('{"status": "gave_up"}', encoding="utf-8")
        self.place("design.jsonl").write_text('{"unit_id": "前の行"}\n', encoding="utf-8")
        self.place("rejects-structure-eye.json").write_text('["前の拒否"]', encoding="utf-8")
        self.place("structure-eye-prompt-2.md").write_text("前の指示", encoding="utf-8")
        self.place("other.json").write_text("{}", encoding="utf-8")
        self.place("rejects-other.json").write_text("[]", encoding="utf-8")
        self.survey()
        self.assertFalse(self.place("eye.json").exists())
        self.assertFalse(self.place("structure-eye-prompt-2.md").exists())
        self.assertEqual(self.place("design.jsonl").read_bytes(), b"")
        self.assertEqual(self.run.script("prep")["attempt"], 1, "測り直しは 1 回目から数える")
        self.assertTrue(self.place("other.json").is_file() and self.place("rejects-other.json").is_file(), "ほかの物は消さない")

    def test_measure_records_timing(self):
        self.survey()
        timing = self.read("structure.json")["timing"]
        self.assertIsInstance(timing["wall_s"], float)
        for key in ("started_at", "finished_at"):
            self.assertRegex(timing[key], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$", key)

    def test_unwritable_state_returns_null_in_the_place(self):
        """控えを place に書けない run も出口は落ちず、structure: null と理由を返す（place の外には書かない）"""
        self.survey()
        self.place("structure-state.json").mkdir()
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["structure"]), (False, "failed", None))
        self.assertIn("構造の目の控えを書けない", fin["reason"])
        self.assertEqual(fin["report"], [fin["reason"]])

    def test_return_survives_a_lib_that_does_not_load(self):
        broken = self.run.artifacts.parent / "no-lib"
        broken.mkdir()
        environ = self.run.environ
        self.run.environ = lambda include="", **inputs: {**environ(include, **inputs), "WORKS_FACTORY_ROOT": str(broken)}
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIsNone(fin["structure"], "形を照らせない出口は照らさずに指さない")
        self.assertIn("ModuleNotFoundError", fin["reason"])
        self.assertEqual(self.place("design.jsonl").read_bytes(), b"")
        self.assertIn("ModuleNotFoundError", self.read("structure-state.json")["reason"])
        files = kit.load("structure", "files")
        self.assertEqual(fin["optional"], files.OPTIONAL)

    def test_prep_without_measure_fails_the_node(self):
        """指示が組めない prep は空の指示を返さず node が落ちる（AI に生の型が届かない）"""
        self.assertIn("view.json", self.run.failing("prep"))


AGENTS = "# 対象の決まり\n\n層は下へだけ依存する。結末の語は src/report.py だけが持つ。\n"
PKG_AGENTS = "# pkg の決まり\n\npkg の中の語は pkg/names.py だけが持つ。ほかの所に写さない。\n"
QUOTE = "pkg の中の語は pkg/names.py だけが持つ。"


def cites(unit_id, path="pkg/AGENTS.md", quote=QUOTE, **more) -> dict:
    return dirty(unit_id, intent=[{"path": path, "quote": quote}], **more)


SYSTEM = "値を用意する側（stats.py）が値を作り、読む側が受け取る"
KIND = "数の並びから代表の値を出す小さな計算の部品で、分母の決め方を 1 か所に揃えたい"
GENERAL = {"structure": "分母の決め方は計算の部品の中の 1 か所が持ち、呼び手は値を渡すだけ", "why": "分母を呼び手が持つと呼び手ごとに割れる"}


def sketched(kinds=(KIND, KIND)) -> dict:
    return {"rows": [{"unit_id": MEAN, "system": SYSTEM, "kind": kinds[0]}, {"unit_id": CLAMP, "system": SYSTEM, "kind": kinds[1]}]}


def drawn(*indexes) -> dict:
    return {"rows": [{"index": i, **GENERAL} for i in indexes or (1, 2)]}


class SketchCase(_RepoCase):
    """直す前の時に、構造を描く役と一般の構造を描く目を構造の目の前に回す（docs/design/structure.md の 2.7・2.8）"""

    def sketch(self, reply):
        return self.run.script("sketch_take", reply=json.dumps(reply, ensure_ascii=False))

    def general(self, reply):
        return self.run.script("general_take", reply=json.dumps(reply, ensure_ascii=False))

    def test_the_eye_sees_the_drawn_system_beside_the_general_structure(self):
        self.survey()
        self.assertEqual(self.run.script("sketched"), {"general": False, "reason": "構造を描く役の行が無い（役が走らなかったか、3 回とも拒まれた）"})
        prep = self.run.script("sketch_prep")
        self.assertIn("You are the system sketcher", prep["prompt"])
        self.assertIn('"paths":["stats.py"]', prep["prompt"])
        self.assertEqual(self.sketch(sketched())["ok"], True)
        self.assertEqual(self.run.script("sketched")["general"], True)
        prep = self.run.script("general_prep")
        self.assertIn(f"1. {KIND}\n2. {KIND}", prep["prompt"])
        for leak in (MEAN, CLAMP, "stats.py", SYSTEM, "mean の分母"):   # 種類の 1 文のほかは、頼みも単位も対象の名も渡さない
            self.assertNotIn(leak, prep["prompt"] + prep["system"])
        self.assertIn("You are the blind judge", prep["system"])
        self.assertTrue(self.general(drawn())["ok"])
        prompt = self.run.script("prep")["prompt"]
        self.assertIn("## The system and its general structure", prompt)
        self.assertIn(GENERAL["structure"], prompt)
        self.assertIn("## Grounds for departing from the general structure", prompt)
        got = self.take({"rows": [dirty(MEAN, evidence=["/units/0/system", "/units/0/general/structure"]), clean(CLAMP, "/units/1/kind")]})
        self.assertTrue(got["ok"], got)

    def test_without_the_general_structure_the_eye_still_reads_the_grounds(self):
        self.survey()
        prompt = self.run.script("prep")["prompt"]
        self.assertNotIn("## The system and its general structure", prompt)
        self.assertIn("## Grounds for departing from the general structure", prompt)
        got = self.take({"rows": [clean(MEAN, "/units/0/general"), clean(CLAMP, "/units/1/id")]})
        self.assertFalse(got["ok"])
        self.assertIn("/units/0/general", got["reason"])

    def test_a_kind_that_names_the_target_is_rejected(self):
        self.survey()
        self.run.script("sketch_prep")
        got = self.sketch(sketched((KIND, "stats.py の上限を揃えたい")))
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("kind が対象の名を持つ（'stats.py'", got["reason"])
        self.assertFalse(self.place("sketches.json").exists())
        got = self.sketch({"rows": [sketched()["rows"][0]]})
        self.assertIn("行の無い単位", got["reason"])

    def test_a_kind_that_names_a_coined_stem_or_folder_of_the_paths_is_rejected(self):
        self.target({"deploy/chart_v2/values-local.yaml": "a: 1\n"})
        self.survey([{"id": "u1", "paths": ["deploy/chart_v2/values-local.yaml"], "summary": "設定の値"}])
        self.run.script("sketch_prep")
        for leak in ("values-local", "chart_v2"):   # 識別子らしい、拡張子を外したファイルの名とパスの段
            got = self.sketch({"rows": [{"unit_id": "u1", "system": SYSTEM, "kind": f"配備の設定で {leak} の値を揃えたい"}]})
            self.assertIn(f"kind が対象の名を持つ（{leak!r}", got["reason"])
        got = self.sketch({"rows": [{"unit_id": "u1", "system": SYSTEM, "kind": "Deploy の設定の値を環境ごとに揃えたい部品の一覧"}]})
        self.assertTrue(got["ok"], got)

    def test_a_kind_with_plain_words_that_are_also_stems_or_folders_passes(self):
        paths = ["src/server/config.py", "charts/app/values.yaml", "docs/api/README.md"]
        self.target({p: "a: 1\n" for p in paths})
        self.survey([{"id": "u1", "paths": paths, "summary": "設定の値"}])
        self.run.script("sketch_prep")
        kind = "A web app whose server reads its config, where the api docs and the chart values must agree"
        got = self.sketch({"rows": [{"unit_id": "u1", "system": SYSTEM, "kind": kind}]})
        self.assertTrue(got["ok"], got)

    def test_general_rows_answer_every_number_once(self):
        self.survey()
        self.sketch(sketched())
        self.run.script("general_prep")
        got = self.general(drawn(1, 1))
        self.assertFalse(got["ok"])
        self.assertIn("index 1 の 2 行目", got["reason"])
        self.assertIn("行の無い番号: [2]", got["reason"])
        self.assertTrue(self.general(drawn(2, 1))["ok"])
        self.assertEqual([r["unit_id"] for r in self.read("general.json")], [MEAN, CLAMP])

    def test_third_rejection_gives_up_and_the_eye_runs_without_it(self):
        self.survey()
        got = [self.sketch({"rows": []}) for _ in range(3)]
        self.assertEqual([(g["done"], g["give_up"]) for g in got], [(False, False)] * 2 + [(True, True)])
        self.assertFalse(self.run.script("sketched")["general"])
        self.assertNotIn("## The system and its general structure", self.run.script("prep")["prompt"])

    def test_fresh_measure_drops_the_drawn_rows(self):
        self.survey()
        self.sketch(sketched())
        self.run.script("general_prep")
        self.general(drawn())
        self.survey()
        for name in ("sketches.json", "general.json", "rejects-system-sketch.json", "general-structure-prompt-1.md", "general-structure-system-1.md"):
            self.assertFalse(self.place(name).exists(), name)


class IntentCase(_RepoCase):
    """書いた意図: 決まった名の文書を根と単位の上のフォルダから探し、汚れる行の抜き書きを見せた本文に照らす"""

    def setUp(self):
        super().setUp()
        self.target({"AGENTS.md": AGENTS, "pkg/AGENTS.md": PKG_AGENTS, "pkg/a.py": "x = 1\n", "other/AGENTS.md": "# 関係ない\n"})
        self.unit = [{"id": "u1", "paths": ["pkg/a.py"], "summary": "pkg の語を直す"}]

    def reply(self, *rows):
        return {"rows": list(rows)}

    def test_found_by_the_fixed_names_shallow_first(self):
        self.survey(self.unit)
        head = git(self.run.repo, "rev-parse", "HEAD")
        self.assertEqual([(d["path"], d["rev"]) for d in self.read("intent.json") if "pointed_by" not in d],
                         [("AGENTS.md", head), ("pkg/AGENTS.md", head)])

    def test_prompt_carries_the_documents_and_the_dirty_row_is_checked_against_them(self):
        self.survey(self.unit)
        prompt = self.run.script("prep")["prompt"]
        self.assertIn("## Written intent", prompt)
        self.assertLess(prompt.index("### AGENTS.md ("), prompt.index("### pkg/AGENTS.md ("))
        self.assertNotIn("other/AGENTS.md", prompt)
        self.assertIn("lines 1-3", prompt)
        got = self.take(self.reply(cites("u1", chosen="語を pkg/names.py に置く")))
        self.assertTrue(got["ok"], got)
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["dirty"], fin["escalate"], fin["after"]), (True, 1, 0, None))
        self.assertEqual(self.read("structure-state.json")["status"], "ok")
        self.assertTrue(any("u1: 汚れる" in line for line in fin["report"]), fin["report"])

    def test_quote_missing_from_the_shown_text_is_rejected_naming_the_document(self):
        self.survey(self.unit)
        self.run.script("prep")
        got = self.take(self.reply(cites("u1", quote="この文は pkg の AGENTS.md に書いていない文である")))
        self.assertFalse(got["ok"])
        self.assertIn("pkg/AGENTS.md の抜き書きが、見せた本文に字のまま無い", got["reason"])

    def test_dirty_row_without_intent_and_unknown_document_are_rejected(self):
        self.survey(self.unit)
        self.run.script("prep")
        self.assertIn("intent", self.take(self.reply(dirty("u1")))["reason"])
        self.assertIn("見せた文書に無い", self.take(self.reply(cites("u1", path="other/AGENTS.md")))["reason"])
        self.assertIn("20 字未満", self.take(self.reply(cites("u1", quote="pkg の中の語")))["reason"])

    def test_whitespace_runs_are_squeezed_when_comparing(self):
        self.survey(self.unit)
        self.run.script("prep")
        self.assertTrue(self.take(self.reply(cites("u1", quote="pkg の中の語は  pkg/names.py\nだけが持つ。", chosen="a")))["ok"])

    def test_clean_row_may_name_the_rules_it_checked(self):
        self.survey(self.unit)
        self.run.script("prep")
        self.assertTrue(self.take(self.reply({**clean("u1"), "intent": [{"path": "AGENTS.md", "quote": "層は下へだけ依存する。結末の語は src/report.py だけが持つ。"}]}))["ok"])

    def test_no_written_intent_means_no_section_and_no_quotes(self):
        run = kit.Run(self, "structure")
        for rel, text in {"a.py": "x = 1\n"}.items():
            (run.repo / rel).write_text(text, encoding="utf-8")
        git(run.repo, "add", "-A")
        git(run.repo, "commit", "-q", "-m", "t")
        run.script("survey", units=json.dumps([{"id": "u1", "paths": ["a.py"], "summary": "s"}]))
        prompt = run.script("prep")["prompt"]
        self.assertNotIn("## Written intent", prompt)
        self.assertIn("No written intent document of the target could be read", prompt)
        got = run.script("take", reply=json.dumps({"rows": [{**clean("u1"), "intent": [{"path": "x", "quote": "y" * 30}]}]}))
        self.assertIn("書いた意図の文書は見せていない", got["reason"])
        self.assertTrue(run.script("take", reply=json.dumps({"rows": [clean("u1")]}))["ok"])

    def test_clean_row_whose_quote_is_not_in_the_shown_text_is_rejected(self):
        """決め 19: 汚れない行の intent にも、見せた本文に字のまま在るかの照らしを当てる"""
        self.survey(self.unit)
        self.run.script("prep")
        got = self.take(self.reply({**clean("u1"), "intent": [{"path": "AGENTS.md", "quote": "この文は AGENTS.md に書いていない文である"}]}))
        self.assertFalse(got["ok"])
        self.assertIn("AGENTS.md の抜き書きが、見せた本文に字のまま無い", got["reason"])

    def test_git_failure_while_finding_intent_is_a_failed_state_without_an_eye(self):
        """HEAD が無い（commit が 1 つも無い）対象では書いた意図を探せず、status failed で目を起こさない"""
        run = kit.Run(self, "structure")
        (run.repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        got = run.script("survey", units=json.dumps([{"id": "u1", "paths": ["a.py"], "summary": "s"}]))
        self.assertFalse(got["eye"])
        doc = json.loads((run.artifacts / "structure.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "failed")
        self.assertIn("書いた意図を探せない", doc["reason"])

    def test_given_intent_replaces_the_fixed_names(self):
        self.survey(self.unit, intent=json.dumps(["other/AGENTS.md"]))
        self.assertEqual([d["path"] for d in self.read("intent.json")], ["other/AGENTS.md"])

    def test_unreadable_given_document_is_named_without_text(self):
        self.survey(self.unit, intent=json.dumps(["NO-SUCH.md", "pkg/AGENTS.md"]))
        doc = self.read("intent.json")[0]
        self.assertEqual(doc["text"], "")
        self.assertTrue(doc["reason"])
        self.assertIn("### NO-SUCH.md (could not be read:", self.run.script("prep")["prompt"])

    def test_before_reads_the_committed_version_not_the_working_tree(self):
        (self.run.repo / "pkg" / "AGENTS.md").write_text("# 書き換えた\n\n全然違う本文である。\n", encoding="utf-8")
        self.survey(self.unit)
        self.assertIn("pkg/names.py だけが持つ", self.read("intent.json")[1]["text"])


class PointedCase(_RepoCase):
    """指示ファイルが名指した文書が読む版に無い時（guided-resolver #2177 の run: AGENTS.md が「デプロイの設定は <パス> の正典に従う」と
    書き、正典はまだ取り込まれていない PR の枝にだけ在った。目は気づかなかった）。ほかの版で見つけた物は本文を書いた意図に足し、
    どの版にも無い物は読めないと名指し、どちらも報告の行に出す"""

    CANON = "docs/explanations/deploy-config.adoc"
    RULES = f"# 決まり\n\nデプロイの設定は `{CANON}` の正典に従う。試験の書き方は `pkg/a.py` を見る。古い手順は `docs/gone.md` に在った。\n"

    def setUp(self):
        super().setUp()
        self.target({"AGENTS.md": self.RULES, "pkg/a.py": "x = 1\n"})
        git(self.run.repo, "checkout", "-q", "-b", "canon")
        self.target({self.CANON: "名前は chart に持たせず、Terraform から受け渡す。\n"})
        self.canon = git(self.run.repo, "rev-parse", "HEAD")
        git(self.run.repo, "checkout", "-q", "-")
        self.unit = [{"id": "u1", "paths": ["pkg/a.py"], "summary": "設定の名を足す"}]

    def test_a_document_only_on_another_branch_is_read_as_written_intent(self):
        self.survey(self.unit)
        docs = {d["path"]: d for d in self.read("intent.json")}
        self.assertEqual((docs[self.CANON]["rev"], docs[self.CANON]["pointed_by"]), (self.canon, "AGENTS.md"))
        self.assertIn("Terraform から受け渡す", docs[self.CANON]["text"])
        self.assertNotIn("pkg/a.py", docs, "版に在る名指しは足さない")
        prompt = self.run.script("prep")["prompt"]
        self.assertIn(f"### {self.CANON} ({self.canon[:12]}, lines 1-1; pointed to by AGENTS.md, not in the version under review", prompt)
        self.take(self.reply_clean())
        out = self.finish()
        self.assertTrue(any(self.CANON in line and "読む版に無い" in line for line in out["report"]), out["report"])
        state = self.read(out["structure"]["path"])
        self.assertEqual(state["pointed"], [{"path": self.CANON, "by": "AGENTS.md", "found": True, "at": "canon"},
                                            {"path": "docs/gone.md", "by": "AGENTS.md", "found": False, "at": ""}],
                         "控えは版に無い名指しを行で持つ（line が修正前の承認ノードで人に問う。持ち主の決め pointed-ask）")

    def test_a_document_in_no_version_is_named_without_text(self):
        self.survey(self.unit)
        gone = next(d for d in self.read("intent.json") if d["path"] == "docs/gone.md")
        self.assertEqual((gone["text"], gone["pointed_by"]), ("", "AGENTS.md"))
        self.assertIn("ほかのどの版にも無い", gone["reason"])
        self.assertIn("### docs/gone.md (could not be read:", self.run.script("prep")["prompt"])
        self.take(self.reply_clean())
        self.assertTrue(any("docs/gone.md" in line and "どの版にも無く" in line for line in self.finish()["report"]))

    def test_an_empty_document_on_another_branch_is_found(self):
        """ほかの版で見つけたかは在るかで決める（本文が空のファイルを「どの版にも無い」側に入れない）"""
        git(self.run.repo, "checkout", "-q", "-b", "blank")
        self.target({"docs/gone.md": ""})
        git(self.run.repo, "checkout", "-q", "-")
        self.survey(self.unit)
        self.take(self.reply_clean())
        out = self.finish()
        row = next(r for r in self.read(out["structure"]["path"])["pointed"] if r["path"] == "docs/gone.md")
        self.assertEqual((row["found"], row["at"]), (True, "blank"))
        self.assertFalse(any("docs/gone.md" in line and "どの版にも無く" in line for line in out["report"]), out["report"])

    def reply_clean(self):
        return {"rows": [clean("u1")]}


class AfterCase(_RepoCase):
    """mode: after。base から今の作業ツリーまでの差分を測り、同じ目が差分を書いた意図（base の版）と比べる"""

    def setUp(self):
        super().setUp()
        self.target({"AGENTS.md": AGENTS, "pkg/AGENTS.md": PKG_AGENTS, "pkg/a.py": "x = 1\n"})
        self.base = git(self.run.repo, "rev-parse", "HEAD")
        (self.run.repo / "pkg" / "a.py").write_text("x = 2\ny = 3\n", encoding="utf-8")
        (self.run.repo / "pkg" / "AGENTS.md").write_text("# 書き換えた\n\n全然違う本文である。\n", encoding="utf-8")

    def after(self, units=(), **more):
        return self.survey(list(units), mode="after", base=self.base, **more)

    def test_diff_is_measured_and_shown_as_one_unit(self):
        self.assertEqual(self.after(), {"eye": True, "sketch": False, "reason": ""}, "直した後の時は構造を描く役を起こさない")
        doc = self.read("structure-after.json")
        self.assertEqual(doc["status"], "ok")
        self.assertIn("pkg/a.py", doc["after"]["changed"])
        self.assertIn("wall_s", doc["after"]["timing"])
        self.assertIn("+y = 3", self.place("after.diff").read_text(encoding="utf-8"))
        prompt = self.run.script("prep", mode="after")["prompt"]
        self.assertIn("## Diff", prompt)
        self.assertIn("The change is already made.", prompt)
        self.assertIn('"id":"diff"', prompt)
        self.assertIn("pkg の中の語は pkg/names.py だけが持つ", prompt, "意図は base の版")
        self.assertNotIn("全然違う本文", prompt.split("## Diff")[0])

    def test_flow_to_the_after_pointer(self):
        self.after()
        self.run.script("prep", mode="after")
        self.assertTrue(self.take({"rows": [cites("diff", chosen="a", evidence=["/units/0/paths"])]})["ok"])
        fin = self.run.script("finish", mode="after")
        self.assertEqual((fin["ok"], fin["status"], fin["dirty"]), (True, "ok", 1))
        self.assertEqual(fin["after"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "structure-after.json"})
        self.assertEqual(fin["structure"]["path"], "structure-state.json")
        structmark = kit.load("structure", "state").structmark
        self.assertEqual(structmark.read_after(self.place())["status"], "ok")

    def test_given_units_are_kept_and_empty_paths_are_skipped(self):
        self.after([{"id": "u1", "paths": ["pkg/a.py"], "summary": "a を直す"}, {"id": "u2", "paths": [], "summary": "全体"}])
        prompt = self.run.script("prep", mode="after")["prompt"]
        self.assertIn('"id":"u1"', prompt)
        self.assertNotIn('"id":"diff"', prompt)
        self.assertEqual(self.read("skipped-units.json"), ["u2"])

    def test_plan_deviations_reach_the_eye(self):
        plan = self.run.repo / "plan-fields.json"
        plan.write_text(json.dumps({"round": 1, "fields": [{"structure": [{"prescription": "p1", "deviation": "従わない訳である"}], "allowed_paths": ["a.py"], "out_of_scope": []}]}),
                        encoding="utf-8")   # 修正案の盤面の控えの形（shared:plan-fields.schema.json）
        self.after(plan=str(plan))
        self.assertEqual(self.read("structure-after.json")["deviations"][0]["deviation"], "従わない訳である")
        self.assertIn("従わない訳である", self.run.script("prep", mode="after")["prompt"])

    def test_empty_base_is_a_failed_state(self):
        got = self.survey([], mode="after", base="")
        self.assertEqual(got["eye"], False)
        fin = self.run.script("finish", mode="after")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("base_rev", fin["reason"])
        self.assertEqual(fin["after"]["path"], "structure-after.json")

    def test_no_diff_returns_ok_without_the_eye(self):
        git(self.run.repo, "checkout", "--", ".")
        got = self.after()
        self.assertEqual((got["eye"], got["reason"]), (False, "差分が無い"))
        self.assertEqual(self.run.script("finish", mode="after")["status"], "ok")

    def test_long_diff_is_cut_with_a_mark_and_kept_whole(self):
        (self.run.repo / "pkg" / "big.txt").write_text("あ" * 30000 + "\n", encoding="utf-8")
        self.after()
        prompt = self.run.script("prep", mode="after")["prompt"]
        self.assertIn("(cut: the first 40000 bytes are shown;", prompt)
        self.assertGreater(self.place("after.diff").stat().st_size, 40000)


class ConceptsCase(_RepoCase):
    """考えの地図の行・柵の表・方針の文書・根の地図の文書が目に見せる JSON に載る（元 tests/workflows/test_structure.py の StageACase）"""

    def edge(self, files):
        self.target(files)
        return self.survey([{"id": MEAN, "paths": ["src/edge.py"], "summary": "境の節が結末の語を書く"}])

    def test_eye_sees_concept_rows_and_policy(self):
        self.target({"src/report.py": 'OUT = "round_limit"\n', "src/edge.py": 'x = "round_limit"\n',
                     "POLICY.md": "決まり: 結末の語は report.py だけが持つ\n", "docs/concepts.md": CONCEPT_MAP,
                     "docs/concepts.json": json.dumps(CONCEPT_TABLE, ensure_ascii=False)})
        self.survey([{"id": MEAN, "paths": ["src/edge.py"], "summary": "境の節が結末の語を書く"}], policy="POLICY.md")
        prompt = self.run.script("prep")["prompt"]
        self.assertIn("### `outcome` run の結末", prompt)
        self.assertIn("known_places", prompt)
        self.assertIn("結末の語は report.py だけが持つ", prompt)
        self.assertNotIn("### `halt`", prompt, "単位のパスに当たる行だけ")
        unit = self.read("structure.json")["units"][0]
        self.assertEqual([(x["concept"], x["path"], x["home"], x["known_places"]) for x in unit["concepts"]["places"]],
                         [("outcome", "src/edge.py", False, 2)])

    def test_no_map_no_table_measures_only(self):
        self.edge({"src/edge.py": 'x = "round_limit"\n'})
        self.assertEqual(self.read("structure.json")["units"][0]["concepts"], {"rows": [], "places": []})
        self.assertFalse((self.run.repo / "docs").exists())

    def test_cut_policy_is_the_last_written_intent(self):
        """長い方針の文書は切りの印つきで、書いた意図の最後の 1 本として載る"""
        text = "決まり: 結末の語は report.py だけが持つ\n" + "あ" * 6100
        self.target({"src/edge.py": 'x = 1\n', "POLICY.md": text, "AGENTS.md": "# 対象の決まり\n\n層は下へだけ依存する\n"})
        self.survey([{"id": MEAN, "paths": ["src/edge.py"], "summary": "境"}], policy="POLICY.md")
        prompt = self.run.script("prep")["prompt"]
        self.assertIn("層は下へだけ依存する", prompt)
        self.assertIn("結末の語は report.py だけが持つ", prompt)
        self.assertIn(f"(cut: the first 6000 characters are shown; {len(text) - 6000} more were left out)", prompt)
        self.assertLess(prompt.index("### AGENTS.md"), prompt.index("### POLICY.md (policy,"))

    def test_unreadable_policy_stops_the_eye_and_names_the_port(self):
        got = self.survey(policy="NO-SUCH.md")
        self.assertFalse(got["eye"])
        self.assertIn("入力 policy", self.read("structure.json")["reason"])


class ShapeCase(unittest.TestCase):
    """YAML と筋書きの揃い（block の形の検査は tests/layers/test_block_shape.py。ここは structure だけの揃い）"""

    def setUp(self):
        self.doc = yaml.safe_load((BLOCK / "works-factory-structure.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in self.doc["nodes"]}
        self.body = {n["id"]: n for node in self.doc["nodes"] if "loop_group" in node for n in node["loop_group"]["nodes"]}

    def test_contract(self):
        self.assertEqual((self.doc["name"], self.doc["returns"], self.doc["outcome_field"]), ("works-factory-structure", "finish", "ok"))
        fmt = self.nodes["finish"]["output_format"]
        self.assertEqual(sorted(fmt["required"]), sorted(["ok", "status", "reason", "structure", "after", "dirty", "escalate", "optional", "report"]))
        self.assertEqual(fmt["properties"]["structure"]["type"], ["object", "null"])
        self.assertEqual(fmt["properties"]["after"]["type"], ["object", "null"])
        self.assertEqual(self.nodes["finish"]["trigger_rule"], "all_done")

    def test_loop_gives_up_in_the_body_before_max_iterations(self):
        rolekit = kit.load("structure", "eye").rolekit
        loop = self.nodes["structure-eye-loop"]["loop_group"]
        self.assertEqual(loop["max_iterations"], rolekit.GIVE_UP_AFTER)
        self.assertIs(loop["fresh_context"], False)
        self.assertEqual(loop["until_bash"], 'done=$structure-eye-accept.output.done; test "$done" = true')

    def test_eye_is_a_toolless_isolated_role(self):
        eye = self.body["structure-eye"]
        self.assertEqual(eye["allowed_tools"], [])
        self.assertIs(eye["mutates_checkout"], False)
        self.assertEqual(eye["settingSources"], ["user"])
        self.assertEqual(eye["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False})
        self.assertEqual(eye["model"], "@wf-plan-structure")
        self.assertEqual(eye["prompt"], "$structure-eye-prep.output.prompt")

    def test_sketcher_reads_and_the_general_eye_is_blind(self):
        """構造を描く役は読むだけの道具を持ち、一般の構造を描く目は道具も既定の system prompt（作業ツリーの cwd と git status）も持たない"""
        sketcher, general = self.body["system-sketch"], self.body["general-structure"]
        self.assertEqual(sketcher["allowed_tools"], ["Read", "Grep", "Glob"])
        self.assertEqual(general["allowed_tools"], [])
        self.assertEqual(general["systemPrompt"], "$general-structure-prep.output.system")
        for role in (sketcher, general):
            self.assertIs(role["mutates_checkout"], False)
            self.assertEqual(role["model"], "@wf-plan-structure")
        self.assertEqual(self.nodes["system-sketch-loop"]["when"], "$measure.output.sketch == true")
        self.assertEqual(self.nodes["general-structure-loop"]["when"], "$sketched.output.general == true")
        self.assertEqual(self.nodes["structure-eye-loop"]["trigger_rule"], "all_done", "描く役が飛んでも落ちても構造の目は回る")

    def test_scripts_are_read_only_uv_scripts(self):
        for node in [*self.nodes.values(), *self.body.values()]:
            if "script" in node:
                self.assertIs(node.get("mutates_checkout"), False, node["id"])

    def test_script_names_differ_from_lib_modules(self):
        lib = {p.stem for p in (kit.ROOT / "lib").glob("*.py")}
        mine = {p.stem for p in (BLOCK / "scripts").glob("*.py")}
        self.assertEqual(mine & lib, set())
        self.assertEqual(mine, {n["script"] for n in [*self.nodes.values(), *self.body.values()] if "script" in n})

    def test_declared_optional_matches_the_nodes(self):
        files = kit.load("structure", "files")
        ids = set(self.nodes) | set(self.body)
        for row in files.OPTIONAL:
            node = row["node"]
            self.assertTrue(node in ids or any(i.startswith(node) for i in ids), node)

    def test_own_file_names_match_the_rejection_ledger(self):
        files = kit.load("structure", "files")
        eye = kit.load("structure", "eye")
        self.assertIn(eye.rolekit.rejects_path(pathlib.Path(), files.NAME).name, files.OWN_FILES)

    def test_fixtures_are_the_expected_set(self):
        names = sorted(p.name.removesuffix(".stubs.yaml") for p in (BLOCK / "fixtures").glob("*.stubs.yaml"))
        self.assertEqual(names, ["after", "eye-gave-up", "eye-skipped", "standalone"])


if __name__ == "__main__":
    unittest.main()
