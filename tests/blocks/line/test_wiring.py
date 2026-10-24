"""line の YAML の配線（docs/design/line.md の 11 節の test_wiring.py）: 受け皿・返し・一度だけの include・include した block の入力の
全部が渡るか名指した訳に在るか（L-W67）・when: が名に depth を含む欄を読まない・差分の審査の 3 つの when:・報告がいつも走ること。

元は今の tests/workflows/test_line.py の LineWiringCase・FixWiringCase・NoFixWiringCase・SharedPlacesWiringCase・StructureOnceCase・
HandoffCase（docs/design/README.md の 9.5）。include した block の中は各 block の試験が見る。include した block の YAML が workflows/ に
無い間（組み込みの前に別の枝に在る block）は、その block の照らしだけを見送らずに赤にする（組み込みの後はどれも在る）。
"""
import contextlib
import io
import json
import os
import re
import runpy
import tempfile
import unittest
from unittest import mock

import yaml

from tests.blocks import kit

BLOCK = "line"
PATH = kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml"
TEXT = PATH.read_text(encoding="utf-8")
DOC = yaml.safe_load(TEXT)
TOP = {n["id"]: n for n in DOC["nodes"]}
LOOP = {n["id"]: n for n in TOP["plan-rounds"]["loop_group"]["nodes"]}
NODES = {**TOP, **LOOP}
INCLUDES = {k: n for k, n in NODES.items() if "include" in n}
ONCE = ("replan", "replan-review", "refix-run", "rejudge-run", "parallel-pr-after")
STAGES = (("lens", "delta-review", "fix"), ("lens-2", "delta-review-2", "refix-run"))

# include した block の入力のうち、line が渡さない物と訳（各設計書の 1.2・1.6）
NOT_PASSED = {
    ("test-gate-base", "baseline"): "final の時だけ読む（base は直す前の結末を作る側）",
    ("structure", "base"): "after の時だけ読む（line は before で回す。after は eyes の graph の中）",
    ("structure", "plan"): "after の時だけ読む",
    **{(fix, name): "group の時だけ読む（whole の親が自分を子に起こす時に渡す）"
       for fix in ("fix", "refix-run") for name in ("group", "from_tree", "out_dir")},
    ("fix", "notes"): "案の直しの後の 2 回目の修正の段だけ",
    ("fix", "only_items"): "2 回目の修正の段だけ（1 回目は直す義務の単位の全部）",
    ("fix", "prior"): "2 回目の修正の段だけ（1 回目の段の申し送り）",
    ("lens", "lenses"): "block の既定の表（docs/design/line.md の 4.5）",
    ("lens-2", "lenses"): "block の既定の表",
    ("plan", "conflicts"): "形 replan だけが読む（往復の中は形 plan）",
    # 仕様駆動の道の include（docs/design/spec-driven.md の 6.2）。block works-factory-spec-driven は形ごとに読む入力が違う
    **{("spec-entry", name): "形 check の入力（形 entry は表だけを読む）" for name in
       ("base", "tdd", "out_of_scope", "ready", "plan", "plan_ok", "out_of_purpose")},
    ("spec-check", "table"): "形 entry の入力（形 check は表を読み直さず、形 entry の返りの写しを受ける）",
    **{("spec-diagnose", name): "仕様駆動の run の中で回らない段の値か、再審の道の入力（素材・世界の解・頭の深さ・仕様の段は会話の中か回さない）"
       for name in ("constraints", "materials", "pr_material", "world_rows", "row_asks", "depth_why", "spec_rows", "spec_origin", "answers",
                    "prior_failures", "pr_text", "objection", "prior", "prior_brief", "prior_inputs", "spec", "verify", "excluded")},
    **{("spec-plan", name): "仕様駆動の run の中で回らない段の値（裏取り・並行 PR・頭の深さ・前の決め・世界の解・構造の目・前の周・申し出）"
       for name in ("verify", "excluded", "depth_record", "decisions", "world_rows", "structure", "prior_failures", "prior", "conflicts")},
    ("plan", "routes"): "計画の往復は依頼の文の run だけで回る（既定の auto）。仕様駆動の run は spec-plan が spec を渡す",
    ("replan", "routes"): "案の直しは仕様駆動の run では回らない（既定の auto）",
    ("rejudge-run", "request_files"): "再審の道は読まない（判定の道だけの入力）",
    **{(review, name): "方針の文と方針の文のファイル。仕様を固める会話から単独で回す時だけ使う（line は修正案を plan で渡す）"
       for review in ("plan-review-run", "replan-review") for name in ("proposal", "proposal_file")},
    **{(plan, "spec_doc"): "仕様駆動の run だけが渡す人と固めた仕様の本文（依頼の文の run の固めた仕様は spec）" for plan in ("plan", "replan")},
    ("spec-plan", "spec"): "仕様駆動の run は仕様の段の spec.json を作らない（固めた本文は spec_doc）",
    ("plan-review-run", "ruling"): "形 replan だけが読む",
    ("plan-review-run", "conflicts"): "形 replan だけが読む",
    **{("rejudge-run", name): "判定の道だけが読む（再審の道は prior と objection で考え直す。docs/design/diagnose.md の 1.2）"
       for name in ("answers", "base", "baseline", "constraints", "depth_why", "materials", "pr_material", "pr_text", "prior_failures",
                    "request_origin", "row_asks", "spec_origin", "spec_rows")},
    ("spec-check-run", "request"): "write の時だけ読む", ("spec-check-run", "pr_text"): "write の時だけ読む",
    **{("merge-seal", name): "apply と check の時だけ読む"
       for name in ("answer", "deliver", "items", "r2", "request", "sealed_hash", "user_env_dir")},
}


def block_doc(name: str) -> dict:
    block = name.removeprefix("works-factory-")
    path = kit.BLOCKS / block / f"works-factory-{block}.yaml"
    if not path.is_file():
        raise AssertionError(f"include した block {block} が workflows/ に無い（組み込みで別の枝から入る）")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def returns_of(doc: dict) -> dict:
    return next(n for n in doc["nodes"] if n["id"] == doc["returns"])


def refs(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class ReceiverCase(unittest.TestCase):
    """受け皿（埋め P8）と返し（埋め P2）"""

    def test_bodies_are_written_once(self):
        for script, count in (("returned", 1), ("relay", 1), ("gate_answer", 1)):
            with self.subTest(script=script):
                self.assertEqual(len(re.findall(rf"^\s*script: {script}\s*$", TEXT, re.M)), count)
        self.assertEqual(sorted(k for k, n in TOP.items() if n.get("script") == "relay"),
                         ["design-in", "lens-2-in", "lens-in", "structure-in"])
        self.assertEqual(sorted(k for k, n in TOP.items() if n.get("script") == "gate_answer"), ["answer-final", "answer-start"])

    def test_every_top_include_has_a_receiver_with_every_field(self):
        """受け皿は include の返りをまるごと受け、運ぶ欄の名は block の返す node の output_format の欄と同じ（optional はいつも無くてよい欄
        なので名指さない）。report は報告そのもので、受け皿を持たない（result が直に読む）"""
        for key, node in INCLUDES.items():
            if key in LOOP or key == "report":
                continue
            with self.subTest(include=key):
                receiver = TOP.get(f"{key}-out")
                self.assertIsNotNone(receiver, "受け皿が無い")
                self.assertEqual((receiver["script"], receiver["depends_on"], receiver.get("trigger_rule")), ("returned", [key], None))
                self.assertEqual(receiver["with"]["got"], f"${key}.output")
                props = set(returns_of(block_doc(node["include"]))["output_format"]["properties"]) - {"optional"}
                self.assertEqual(sorted(receiver["with"]["names"].split()), sorted(props))

    def test_plan_rounds_have_one_receiver_with_the_plan_out_fields(self):
        """今の 2 つの受け皿（plan-rounds-out・plan-rounds-review-out）を 1 つにした（docs/design/line.md の 9 節）。往復の返りは本体の唯一の
        終わりの関所が依る design-talk の返りで、plan-out の欄の全部と設計の相談の欄（3.1 節）を持つ"""
        receiver = TOP["plan-rounds-out"]
        self.assertEqual(receiver["with"]["got"], "$plan-rounds.output")
        talk = LOOP["design-talk"]["output_format"]["properties"]
        self.assertEqual(sorted(receiver["with"]["names"].split()), sorted(talk))
        self.assertLessEqual(set(LOOP["plan-out"]["output_format"]["properties"]), set(talk))
        self.assertEqual(LOOP["gate-design"]["depends_on"], ["design-talk"])
        self.assertNotIn("plan-rounds-review-out", TOP)

    def test_plan_rounds_wait_on_every_stage_that_can_stop(self):
        """計画の往復の when は、前の段のうち止める理由（stop_reason）を返す node（owed・structure-in・tiers）の全部を見る"""
        guard = TOP["plan-rounds"]["when"]
        for stage in ("owed", "structure-in", "tiers"):
            with self.subTest(stage=stage):
                self.assertIn(f"${stage}.output.stop_reason == ''", guard)

    def test_all_done_readers_read_receivers_only(self):
        """all_done で集める collect と、落ちうる include の後ろの集め役は、include の返りを直に読まない（落ちた node への with: は
        Archon が誤りにする）"""
        includes = [k for k in INCLUDES if k not in LOOP]
        for reader in ("collect", "fixed", "fix-in", "judged", "ask-final"):
            with self.subTest(reader=reader):
                reads = refs({k: v for k, v in TOP[reader].get("with", {}).items() if isinstance(v, dict)})
                self.assertFalse([k for k in includes if f'"${k}.output' in reads], f"{reader} が include を from: で直に読む")
        self.assertEqual(TOP["collect"]["trigger_rule"], "all_done")
        for key in includes:
            if key != "report":
                self.assertIn(f"{key}-out", TOP["collect"]["depends_on"], key)

    def test_merge_seal_waits_for_the_eyes_receiver(self):
        """eyes の graph の返す node が落ちても merge-seal の with: が落ちた node を読まない（docs/design/line.md の 1.3）"""
        self.assertEqual(TOP["merge-seal"]["depends_on"], ["eyes-out"])

    def test_merge_apply_reads_the_seal_through_ask_final(self):
        """受け皿の got の中の欄は with: で読めない（Archon は output_format の宣言の外の道を誤りにする）ので、封じの値は最後の承認ノードが
        受け皿から読んで返す。封じが落ちた run は sealed_hash が空で、merge の apply が拒む（閉じた側に倒れる）"""
        with_ = TOP["merge-apply"]["with"]
        for name in ("sealed_hash", "fingerprint", "green_ok", "eyes_ok", "r2"):
            self.assertEqual(with_[name], f"$ask-final.output.{name}", name)
        self.assertNotIn("$merge-seal.output", refs(with_))


class IncludeInputsCase(unittest.TestCase):
    def test_include_inputs_are_passed_or_named(self):
        """L-W67: include した block の inputs: の全部が with: で渡るか、渡さない訳の一覧に在る。block の inputs: に無い鍵は渡さない"""
        for key, node in INCLUDES.items():
            with self.subTest(include=key):
                inputs = set(block_doc(node["include"]).get("inputs") or {})
                given = set(node.get("with") or {})
                self.assertEqual(sorted(given - inputs), [], "block の inputs: に無い鍵を渡している")
                self.assertEqual(sorted(i for i in inputs - given if (key, i) not in NOT_PASSED), [])

    def test_not_passed_names_real_inputs(self):
        for (key, name) in NOT_PASSED:
            with self.subTest(include=key, name=name):
                self.assertIn(name, block_doc(INCLUDES[key]["include"]).get("inputs") or {})
                self.assertNotIn(name, INCLUDES[key].get("with") or {})

    def test_once_only_includes(self):
        """一度だけの include は line に 1 つずつ（案の直し・その事前審査・2 度目の修正・再審・修正の後の並行 PR）"""
        named = [n["include"] for n in INCLUDES.values()]
        for key in ONCE:
            with self.subTest(include=key):
                self.assertIn(key, TOP)
                self.assertNotIn("loop_group", TOP[key])
        self.assertEqual(named.count("works-factory-fix"), 2)
        self.assertEqual(named.count("works-factory-plan"), 3, "往復の中・案の直し・仕様駆動の run の spec-plan")
        self.assertEqual(named.count("works-factory-plan-review"), 2)
        self.assertEqual(named.count("works-factory-diagnose"), 2, "再審と、仕様駆動の run の spec-diagnose")
        self.assertEqual(named.count("works-factory-parallel-pr"), 1)
        self.assertEqual(named.count("works-factory-judge"), 1, "再審は判定のまとめを 2 度 include せず diagnose を直に include する")
        self.assertEqual(named.count("works-factory-eyes"), 1)
        self.assertNotIn("works-factory-gate-efficacy", named, "重い検算は run の中で回さない（持ち主の決め 2026-10-19）")
        self.assertNotIn("gates", DOC["inputs"])

    def test_include_ids_are_not_loop_body_ids(self):
        """展開した後の node の id が重ならない（Archon は include した block の頭の段の node にだけ `<include の id>__` を付け、loop の
        中の node の id はそのまま残す。今の LineWiringCase の同じ名の試験）"""
        def body_ids(nodes, inside=False):
            got = set()
            for node in nodes:
                if "include" in node:
                    got |= body_ids(block_doc(node["include"])["nodes"])
                elif inside:
                    got.add(node["id"])
                if "loop_group" in node:
                    got |= body_ids(node["loop_group"]["nodes"], inside=True)
            return got
        self.assertEqual(set(INCLUDES) & body_ids(DOC["nodes"]), set())


class WhenCase(unittest.TestCase):
    def test_when_does_not_read_depth_fields(self):
        """when: が読むのは真偽の欄で、深さの語や名に depth を含む欄を読まない（表を引くのは line の src。docs/design/line.md の 5.3）"""
        for key, node in NODES.items():
            when = node.get("when") or ""
            with self.subTest(node=key):
                self.assertFalse(re.search(r"\.[a-z_]*depth[a-z_]*\b", when), when)
                self.assertNotIn("軽量", when)

    def test_delta_review_stages_share_the_three_moved_conditions(self):
        """delta-review と lens の設計書の 1.6 が今の delta-cut から line へ移した 3 つ: 深さで省かない・変更の確かめが通った・戻せず
        当たったままの組が無い（fix の stop_reason が空）。段ごとに lens と delta-review が同じ when: を持つ"""
        for lens, review, fix in STAGES:
            with self.subTest(stage=fix):
                want = (f"$raise.output.checks == true && ${fix}.output.ok == true && ${fix}.output.checked.ok == true"
                        f" && ${fix}.output.stop_reason == ''")
                self.assertEqual(TOP[lens]["when"], want)
                self.assertEqual(TOP[review]["when"], want)
                self.assertEqual(TOP[lens]["with"]["base"], f"${fix}.output.start_tree")
                self.assertEqual(TOP[review]["with"]["base"], f"${fix}.output.start_tree")
                self.assertEqual(TOP[review]["with"]["plan"], f"${fix}.output.scope")
                self.assertEqual(TOP[review]["with"]["fix_reply"], f"${fix}.output.reply")
                self.assertEqual(TOP[review]["with"]["permits"], f"${fix}.output.allowed_tests")
        self.assertEqual(TOP["delta-review"]["with"]["plan_review"], TOP["fix"]["with"]["plan_review"])
        self.assertEqual(TOP["delta-review-2"]["with"]["plan_review"], TOP["refix-run"]["with"]["plan_review"])

    def test_raise_is_once_before_the_first_review(self):
        """上げ直しは run に 1 回、1 回目の修正の段の後・1 回目の差分の審査の前（2 度目の段の前では上げ直さない。5.3）"""
        self.assertEqual([k for k, n in TOP.items() if n.get("script") == "raise_depth"], ["raise"])
        self.assertEqual(TOP["raise"]["depends_on"], ["fix-in", "fix", "after-fix"])
        self.assertEqual(TOP["lens"]["depends_on"], ["raise"])

    def test_parallel_pr_after_runs_for_judged_entries_with_a_diff(self):
        """8.1: 判定から入る run で、直した差分が在る時だけ、修正の後に 1 度だけ並行 PR を確かめ直す"""
        node = TOP["parallel-pr-after"]
        self.assertEqual(node["when"], "$start.output.ports.entry != '' && $fixed.output.diffed == true")
        self.assertEqual((node["with"]["base"], node["with"]["changed"]), ("$start.output.ports.base_rev", "[]"))
        self.assertIn("parallel-pr-after-out", TOP["test-gate-final"]["depends_on"])

    def test_excluded_reaches_both_fix_stages(self):
        """8.2・integration.md 4.1-5: 並行 PR が外した hunk を fix の 1 回目と 2 度目に渡す"""
        self.assertEqual(TOP["fix"]["with"]["excluded"], "$fix-in.output.excluded")
        self.assertEqual(TOP["refix-run"]["with"]["excluded"], "$fix-in.output.excluded")
        self.assertNotIn("excluded", TOP["parallel-pr-after"]["with"])

    def test_after_fix_nodes_read_the_judgment_through_fix_in(self):
        """修正から後ろの node は判定・構造の目・独立設計・計画の値を fix-in から読む（固定材料の run は判定と計画が飛ぶ）"""
        after = ("fix", "replan", "replan-review", "refix-run", "lens", "delta-review", "lens-2", "delta-review-2", "rejudge-run",
                 "spec-check-run", "eyes")
        early = ("$judge.output", "$judge-out", "$plan-rounds", "$structure-in", "$design-in", "$tiers", "$owed",
                 "$answer-before-fix")
        for key in after:
            with self.subTest(node=key):
                text = refs(TOP[key].get("with"))
                self.assertFalse([e for e in early if e in text], text)


class FlowCase(unittest.TestCase):
    def test_report_reruns_on_resume(self):
        """L-W60: 報告はいつも走る。collect・report・result は all_done で、collect と result は always_run（include の always_run は
        Archon が捨てるので report には書かない）"""
        for key in ("collect", "report", "result"):
            self.assertEqual(TOP[key]["trigger_rule"], "all_done", key)
        for key in ("collect", "result"):
            self.assertIs(TOP[key].get("always_run"), True, key)
        self.assertNotIn("always_run", TOP["report"])
        self.assertEqual(TOP["report"]["depends_on"], ["collect"])

    def test_start_is_not_always_run(self):
        """L-E34: 呼び直しで機能・test_cmd・入口の形・base_rev を替えない"""
        self.assertNotIn("always_run", TOP["start"])

    def test_four_gates_have_the_same_options(self):
        gates = [k for k, n in TOP.items() if "wait" in n]
        self.assertEqual(gates, ["gate-start", "gate-before-fix", "spec-gate-before-fix", "gate-replan", "gate-final"])   # spec- は仕様駆動の run の修正前
        for key in gates:
            self.assertEqual([o["id"] for o in TOP[key]["wait"]["options"]], ["approve", "continue", "stop", "reject"], key)
        # 往復の本体の関所は設計の相談の gate-design 1 つだけ（本体の唯一の終わり。E16・3.1 節）。選び肢は 4 つの語と revise
        self.assertEqual([k for k in LOOP if "wait" in LOOP[k]], ["gate-design"])
        self.assertEqual([o["id"] for o in LOOP["gate-design"]["wait"]["options"]], ["approve", "continue", "stop", "reject", "revise"])
        self.assertFalse([k for k, n in LOOP.items() if "gate-design" in (n.get("depends_on") or [])], "関所の後ろに本体の節を置かない")

    def test_plan_rounds_carry_two_priors(self):
        """3 節: plan の prior は plan の形、plan-review の prior は往復の記録の形で、1 周目はどちらも空。どちらも周の頭の design-turn が
        前の周の design-talk の返りから運ぶ（修正要望の周は人の block を差し込んだ写し。3.1 節）。plan-out も同じ記録を受ける"""
        self.assertEqual(LOOP["plan"]["with"]["prior"], "$design-turn.output.plan_prior")
        self.assertEqual(LOOP["plan-review-run"]["with"]["prior"], "$design-turn.output.record")
        self.assertEqual(LOOP["plan-out"]["with"]["prior"], "$design-turn.output.record")
        self.assertEqual(LOOP["design-turn"]["with"]["previous"], "$LOOP_PREV.design-talk.output")
        self.assertEqual(LOOP["design-turn"]["with"]["answer"], "$LOOP_PREV.gate-design.output")
        self.assertEqual(TOP["plan-rounds"]["loop_group"]["until_bash"], 'done=$design-talk.output.done; [ "$done" = "true" ]')
        self.assertEqual(LOOP["plan-review-run"]["with"]["tree"], "$tiers.output.tree")
        self.assertNotIn("round_limit", LOOP["plan-review-run"]["with"])
        self.assertEqual(TOP["plan-rounds"]["loop_group"]["max_iterations"], 22)   # 往復の上限 20 と空の revise の聞き直し 2（test_rounds が和を照らす）
        self.assertNotIn("fresh_context", TOP["plan-rounds"]["loop_group"])

    def test_line_has_no_ai_node(self):
        self.assertFalse([k for k, n in NODES.items() if "prompt" in n or "command" in n])

    def test_line_inputs_are_the_current_sixteen(self):
        self.assertEqual(sorted(DOC["inputs"]), sorted(
            ("request", "base", "pr", "spec", "test_cmd", "tdd_suite", "final_gate", "unattended", "design_talk", "thickness",
             "features_off", "features_on", "policy_md", "fix_fixture", "lang", "deliver", "spec_table")))
        self.assertEqual((DOC["returns"], DOC["outcome_field"]), ("result", "fixed"))


class ScriptReadsCase(unittest.TestCase):
    """with: を持つ line の script の node の全部を、with: の鍵の全部を "null" にして走らせ、読んだ INPUTS_<名> が with: の鍵と同じ
    （片方だけ欄を足すと、欄が黙って報告から落ちる。今の LineWiringCase の同じ名の試験）。script は落ちない（fallback）ので null でも回る"""

    class Recorded(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.read = set()

        def get(self, key, default=None):
            self.read.add(key)
            return super().get(key, default)

        def __getitem__(self, key):
            self.read.add(key)
            return super().__getitem__(key)

    def test_with_keys_are_what_the_script_reads(self):
        scripts = kit.BLOCKS / BLOCK / "scripts"
        for key, node in NODES.items():
            if "script" not in node or not node.get("with"):
                continue
            path = scripts / f"{node['script']}.py"
            with self.subTest(node=key):
                self.assertTrue(path.is_file(), f"{path.name} が無い")
                with tempfile.TemporaryDirectory() as tmp:
                    env = self.Recorded(WORKFLOW_ID=kit.RUN_ID, ARTIFACTS_DIR=tmp, WORKS_FACTORY_ROOT=str(kit.ROOT),
                                        **{f"INPUTS_{name.upper()}": "null" for name in node["with"]})
                    with mock.patch.object(os, "environ", env), contextlib.redirect_stdout(io.StringIO()), \
                            contextlib.redirect_stderr(io.StringIO()):
                        runpy.run_path(str(path), run_name="__main__")
                    read = {name for name in env.read if isinstance(name, str) and name.startswith("INPUTS_")}
                    self.assertTrue({f"INPUTS_{name.upper()}" for name in node["with"]} <= read,
                                    f"with: の鍵を読まない: {sorted({f'INPUTS_{n.upper()}' for n in node['with']} - read)}")


if __name__ == "__main__":
    unittest.main()


class SpecDrivenWiringCase(unittest.TestCase):
    """仕様駆動の道の配線（docs/design/spec-driven.md の 6.2・6.5 の 5 と 8）。足す node は id の並び SPEC_DRIVEN_NODES で名指す
    （前からの spec-check-run を頭の字で巻き込まない）"""

    def setUp(self):
        from tests.blocks.line.test_scenarios import SPEC_DRIVEN_NODES
        self.names = SPEC_DRIVEN_NODES

    def test_every_named_node_is_in_the_yaml(self):
        """名がずれた時に、筋書きの試験が何も照らさないまま通らない"""
        self.assertEqual([n for n in self.names if n not in TOP], [])

    def test_spec_nodes_run_only_in_a_spec_run(self):
        """when: を持つ足す node はどれも from_spec == true か spec-entry の出力を読む句を持つ。受け皿と答えの node は when: を持たず、
        依る node（足す node）が飛ぶと飛ぶ"""
        for name in self.names:
            node = TOP[name]
            with self.subTest(name):
                if "when" in node:
                    self.assertTrue("$start.output.from_spec == true" in node["when"] or "$spec-" in node["when"], node["when"])
                else:
                    self.assertTrue(any(d in self.names for d in node["depends_on"]), node["depends_on"])

    def test_request_run_gates(self):
        """依頼の文の run の判定は from_spec == false の時だけ回り、直す前の結末は spec-entry を読む節を || の後ろに置く（前の節で
        打ち切るので、依頼の文の run は飛ばされた spec-entry の出力を読まない）"""
        self.assertEqual(TOP["judge"]["when"], "$test-gate-base.output.ok == true && $start.output.from_spec == false")
        when = TOP["test-gate-base"]["when"]
        head, tail = when.split(" || ")
        self.assertEqual(head, "$answer-start.output.go == true && $start.output.from_fixture == false && $start.output.from_spec == false")
        self.assertIn("$spec-entry.output.ok == true", tail)
        self.assertNotIn("$spec-entry", head)

    def test_fix_gets_the_routes(self):
        for name in ("fix", "refix-run"):
            with self.subTest(name):
                self.assertEqual(TOP[name]["with"]["routes"], "$start.output.ports.routes")
        self.assertEqual(TOP["spec-plan"]["with"]["routes"], "spec")

    def test_before_fix_gate_is_shared(self):
        """6.5 の 8: spec- の付いた 3 つは今の 3 つと同じ script・output_format・wait: の form と options（錨で本体が 1 つ）を持ち、
        spec-gate-before-fix の attention だけが spec-ask-before-fix を読む"""
        for old, new in (("ask-before-fix", "spec-ask-before-fix"), ("answer-before-fix", "spec-answer-before-fix")):
            with self.subTest(new):
                self.assertEqual((TOP[new]["script"], TOP[new]["output_format"]), (TOP[old]["script"], TOP[old]["output_format"]))
        old, new = TOP["gate-before-fix"]["wait"], TOP["spec-gate-before-fix"]["wait"]
        self.assertEqual((new["form"], new["options"]), (old["form"], old["options"]))
        self.assertEqual(new["attention"], "$spec-ask-before-fix.output.text")
        self.assertIn("&before_fix_wait", TEXT)
