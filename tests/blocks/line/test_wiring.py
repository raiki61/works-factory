"""line の YAML の配線（docs/design/line.md の 11 節の test_wiring.py）: 受け皿・返し・一度だけの include・when: が名に depth を含む欄を読まない・差分の審査の 3 つの when:・報告がいつも走ること。

元は test_line.py の LineWiringCase・FixWiringCase・NoFixWiringCase・SharedPlacesWiringCase・StructureOnceCase・
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
EYESBACK = kit.BLOCKS / "line" / "src" / "eyesback.py"
LIMIT = kit.load("line", "eyesback").LIMIT if EYESBACK.exists() else 0   # 独立の目から修正の段へ返す周の数（src/eyesback.py が無い木では 0）
PATH = kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml"
TEXT = PATH.read_text(encoding="utf-8")
DOC = yaml.safe_load(TEXT)
TOP = {n["id"]: n for n in DOC["nodes"]}
LOOP = {n["id"]: n for n in TOP["plan-rounds"]["loop_group"]["nodes"]}
THEME_LOOP = {n["id"]: n for n in TOP["theme-rounds"]["loop_group"]["nodes"]}   # 設計の段の往復（docs/design/line.md の 3.3 節）
BODIES = {**LOOP, **THEME_LOOP}   # 輪の本体の節（受け皿は輪の外の返りを受ける。輪の中の include は受け皿を持たない）
NODES = {**TOP, **BODIES}
INCLUDES = {k: n for k, n in NODES.items() if "include" in n}
ONCE = ("replan", "replan-review", "refix-run", "rejudge-run", "parallel-pr-after")
STAGES = (("lens", "delta-review", "fix"), ("lens-2", "delta-review-2", "refix-run"))



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


def would_run(node: dict, states: dict) -> bool:
    """node が待つ節（depends_on）の状態 states から、trigger_rule の決まりで走るか。状態は completed・failed・skipped（when などで飛んだ）・
    skipped_after_failure（前が落ちたので飛んだ）。決まりは Archon の待ち方（all_success・one_success・none_failed_min_one_success・all_done）と同じ"""
    upstream = [states[dep] for dep in node["depends_on"]]
    failed = [s for s in upstream if s in ("failed", "skipped_after_failure")]
    done = [s for s in upstream if s == "completed"]
    rule = node.get("trigger_rule") or "all_success"
    if rule == "all_success":
        return len(done) == len(upstream)
    if rule == "one_success":
        return bool(done)
    if rule == "none_failed_min_one_success":
        return not failed and bool(done)
    if rule == "all_done":
        return True
    raise AssertionError(f"知らない待ち方 {rule}")


class ReceiverCase(unittest.TestCase):
    """受け皿（埋め P8）と返し（埋め P2）"""

    def test_bodies_are_written_once(self):
        for script, count in (("returned", 1), ("relay", 1), ("gate_answer", 1)):
            with self.subTest(script=script):
                self.assertEqual(len(re.findall(rf"^\s*script: {script}\s*$", TEXT, re.M)), count)
        self.assertEqual(sorted(k for k, n in TOP.items() if n.get("script") == "relay"),
                         ["design-in", "lens-2-in", "lens-in", "structure-in", "theme-design-in", "theme-world-in"])
        self.assertEqual(sorted(k for k, n in TOP.items() if n.get("script") == "gate_answer"), ["answer-final", "answer-start"])

    def test_every_top_include_has_a_receiver_with_every_field(self):
        """受け皿は include の返りをまるごと受け、運ぶ欄の名は block の返す node の output_format の欄と同じ（optional はいつも無くてよい欄
        なので名指さない）。report は報告そのもので、受け皿を持たない（result が直に読む）"""
        for key, node in INCLUDES.items():
            if key in BODIES or key == "report":
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
        includes = [k for k in INCLUDES if k not in BODIES]
        for reader in ("collect", "fixed", "fix-in", "judged", "ask-final"):
            with self.subTest(reader=reader):
                reads = refs({k: v for k, v in TOP[reader].get("with", {}).items() if isinstance(v, dict)})
                self.assertFalse([k for k in includes if f'"${k}.output' in reads], f"{reader} が include を from: で直に読む")
        heads = [f"back-{k}" for k in range(1, LIMIT + 2)] + ["eyes-back"]   # 返す輪の周の頭と集めは、with: の値の全部で include の返りを直に読まない
        for reader in heads:
            with self.subTest(reader=reader):
                reads = refs(TOP[reader].get("with", {}))
                self.assertFalse([k for k in includes if f'"${k}.output' in reads or f"${k}.output" in reads], f"{reader} が include の返りを直に読む")
        self.assertEqual(TOP["collect"]["trigger_rule"], "all_done")
        for key in includes:
            if key != "report":
                self.assertIn(f"{key}-out", TOP["collect"]["depends_on"], key)
        self.assertIn("eyes-back", TOP["collect"]["depends_on"])

    def test_merge_seal_waits_for_the_eyes_receiver(self):
        """封じは最後の周の目と試験を読むので、返す輪の集めを待つ（eyes の graph の返す node が落ちても merge-seal の with: が落ちた node を
        読まない。docs/design/line.md の 1.3）"""
        self.assertEqual(TOP["merge-seal"]["depends_on"], ["eyes-back", "eyes-back-restore"])

    def test_merge_apply_reads_the_seal_through_ask_final(self):
        """受け皿の got の中の欄は with: で読めない（Archon は output_format の宣言の外の道を誤りにする）ので、封じの値は最後の承認ノードが
        受け皿から読んで返す。封じが落ちた run は sealed_hash が空で、merge の apply が拒む（閉じた側に倒れる）"""
        with_ = TOP["merge-apply"]["with"]
        for name in ("sealed_hash", "fingerprint", "green_ok", "eyes_ok", "r2"):
            self.assertEqual(with_[name], f"$ask-final.output.{name}", name)
        self.assertNotIn("$merge-seal.output", refs(with_))


class EyesBackCase(unittest.TestCase):
    """独立の目から修正の段へ返す輪（docs/design/line.md の 1.3 の 21.5）の周の節と、後ろのつなぎ替え"""

    def same_shape(self, suffix: str):
        """周の節の同じ種類（suffix）を、周の番号を K にしてそろえた JSON の字の並び"""
        return {k: re.sub(rf"back-{k}\b", "back-K", json.dumps(TOP[f"back-{k}{suffix}"], sort_keys=True)) for k in range(1, LIMIT + 1)}

    def test_rounds_are_three_and_alike(self):
        """返す周の数が eyesback.LIMIT と同じで（計画の往復の上限 rounds.LIMIT とは別）、どの周の節も周の番号を替えただけの同じ形（when・
        depends_on・with: の上書きの鍵・trigger_rule）で、最後に上限の訳を記録するだけの周の頭 back-(LIMIT+1) と集め eyes-back が在り、
        eyes-out とどの周の目の受け皿の names も同じ字で findings・route・route_why を持つ"""
        self.assertEqual(LIMIT, 3, "返す周の数は 3 周（src/eyesback.py の LIMIT の 1 か所）")
        heads = sorted(k for k in TOP if re.fullmatch(r"back-\d+", k))
        self.assertEqual(heads, [f"back-{k}" for k in range(1, LIMIT + 2)])
        self.assertEqual(sorted(k for k in TOP if re.fullmatch(r"back-\d+-fix", k)), [f"back-{k}-fix" for k in range(1, LIMIT + 1)])
        for suffix in ("-fix", "-fix-out", "-fixed", "-gate", "-gate-out", "-eyes", "-eyes-out"):
            with self.subTest(suffix=suffix):
                self.assertEqual(len(set(self.same_shape(suffix).values())), 1, "周の節の形がそろわない")
        for k in range(1, LIMIT + 2):
            head = TOP[f"back-{k}"]
            with self.subTest(head=k):
                # 1 周目は最初の目の受け皿だけを待つ（飛べば頭も飛ぶ。止まった run で最後の承認ノードを走らせない）。2 周目以降は前の周の頭が走れば
                # 走る（one_success。前の周の修正の段の中の節が落ちて周の節が飛んでも走る）
                self.assertEqual((head["script"], head.get("trigger_rule")), ("eyes_back", None if k == 1 else "one_success"))
                self.assertEqual(head["depends_on"], ["eyes-out"] if k == 1 else [f"back-{k - 1}", *(f"back-{k - 1}-{x}" for x in ("fixed", "fix-out", "gate-out", "eyes-out"))])
                self.assertEqual(head["with"]["round"], str(k))
                self.assertEqual(sorted(head["with"]), sorted(TOP["back-1"]["with"]))
                self.assertIsNone(head.get("when"), "頭は毎周走る（飛んだ node の出力を when: が読むと Archon が誤りにする）")
                if k > 1:
                    self.assertEqual(head["with"]["prev"], f"$back-{k - 1}.output")
                    self.assertEqual(head["with"]["fixed"], {"from": f"$back-{k - 1}-fixed.output", "if_skipped": None})
        self.assertEqual(TOP["back-1-fix"]["include"], "works-factory-fix")
        self.assertEqual(TOP["back-1-fix"]["with"].keys(), TOP["refix-run"]["with"].keys(), "返しの修正の入力は 2 度目の修正と同じ鍵")
        self.assertEqual(TOP["back-2-fix"]["with"]["only_items"], "$back-2.output.only_items")
        self.assertEqual(TOP["back-1-fixed"]["with"]["more"], "$back-1.output.more")
        self.assertEqual(TOP["back-1-fixed"]["with"]["add"], {"from": "$back-1-fix-out.output.got", "if_skipped": None})
        self.assertEqual(TOP["back-1-fixed"]["with"].keys(), TOP["fixed"]["with"].keys())
        self.assertEqual({k for k, v in TOP["back-1-fixed"]["with"].items() if TOP["fixed"]["with"][k] != v}, {"add", "more"})
        self.assertEqual(TOP["back-1-gate"]["with"], TOP["test-gate-final"]["with"])
        names = TOP["eyes-out"]["with"]["names"]
        self.assertTrue({"findings", "route", "route_why"} <= set(names.split()))
        for k in range(1, LIMIT + 1):
            self.assertEqual(TOP[f"back-{k}-eyes-out"]["with"]["names"], names)
        final = TOP["eyes-back"]
        self.assertEqual((final["script"], final["trigger_rule"], final.get("when")), ("eyes_back_end", "none_failed_min_one_success", None))
        self.assertEqual(final["depends_on"], heads)
        self.assertEqual(final["with"], {f"back_{k}": {"from": f"$back-{k}.output", "if_skipped": None} for k in range(1, LIMIT + 2)})
        props = final["output_format"]["properties"]
        self.assertTrue(props["eyes"]["description"].startswith("json(returns:works-factory-eyes):"))
        self.assertTrue(props["tests"]["description"].startswith("json(returns:works-factory-test-gate):"))

    def test_seal_and_final_read_the_last_round(self):
        """merge-seal が eyes-back を待ち、when に sealable を持ち、指紋・緑・目の値を eyes-back から読む。ask-final は eyes-back を
        if_skipped: null で読み、merge-apply の items と result の eyes は eyes-back から読み、eyes-back は when を持たず、周の頭が 1 つも走らない run では飛ぶ（all_done にすると、計画や修正で止まった run でも集めが済み、最後の承認ノードが走る）。
        返した周の中の節が落ちた run では、次の周の頭が one_success で走るので、eyes-back・merge-seal・ask-final まで届く"""
        seal = TOP["merge-seal"]
        self.assertEqual(seal["depends_on"], ["eyes-back", "eyes-back-restore"])
        self.assertIn("$eyes-back.output.sealable == true", seal["when"])
        self.assertEqual({k: seal["with"][k] for k in ("fingerprint", "green_ok", "eyes_ok")},
                         {"fingerprint": "$eyes-back.output.fingerprint", "green_ok": "$eyes-back.output.green_ok", "eyes_ok": "$eyes-back.output.eyes_ok"})
        ask = TOP["ask-final"]
        self.assertIn("eyes-back", ask["depends_on"])
        self.assertEqual(ask["with"]["eyes_back"], {"from": "$eyes-back.output", "if_skipped": None})
        self.assertEqual(ask["with"]["tests"], {"from": "$test-gate-final-out.output.got", "if_skipped": None}, "最初の試験と目は今の受け皿のまま")
        self.assertEqual(ask["with"]["eyes"], {"from": "$eyes-out.output.got", "if_skipped": None})
        self.assertEqual(TOP["merge-apply"]["with"]["items"], "$eyes-back.output.item_claims")
        self.assertEqual(TOP["result"]["with"]["eyes"], {"from": "$eyes-back.output.eyes", "if_skipped": None})
        self.assertEqual(TOP["collect"]["with"]["eyes_back"], {"from": "$eyes-back.output", "if_skipped": None})
        self.assertEqual((TOP["eyes-back"]["trigger_rule"], TOP["eyes-back"].get("when")), ("none_failed_min_one_success", None))
        self.assertIn("eyes-back", TOP["result"].get("depends_on", []) + TOP["collect"]["depends_on"])

    def test_round_waits_reach_the_next_head_after_an_internal_error(self):
        """周 k の修正の段の中の節が誤りで落ちると、Archon はその後ろの周の節（受け皿・試験・目）を「前が落ちたので飛んだ」節にする。それでも次の周の
        頭と集めが走るように、周の合わせの節 back-k-fixed と 2 周目以降の頭は one_success で待つ（周 k の頭が走れば走る。合わせの節は落ちた段を null で
        受けて『進めなかった』を返し、頭はその周の試験と目を null で受けて返す前の状態を持ち越す）。周の頭が 1 つも走らない run では、1 周目の頭が
        eyes-out を既定の待ち方で待って飛び、後ろの頭も合わせの節も飛ぶので、集めも封じも最後の承認ノードも飛ぶまま。落ちた段を読む受け皿・試験・目の節は
        既定の待ち方のままで、落ちた節の出力を直に読まない"""
        for k in range(1, LIMIT + 1):
            with self.subTest(round=k):
                fixed = TOP[f"back-{k}-fixed"]
                self.assertEqual((fixed.get("trigger_rule"), fixed.get("depends_on")), ("one_success", [f"back-{k}", f"back-{k}-fix-out"]))
                self.assertEqual(fixed["with"]["add"], {"from": f"$back-{k}-fix-out.output.got", "if_skipped": None})
                for suffix in ("-fix", "-fix-out", "-gate", "-gate-out", "-eyes-out"):
                    self.assertIsNone(TOP[f"back-{k}{suffix}"].get("trigger_rule"), f"back-{k}{suffix} は落ちた節の後ろで飛ぶ既定の待ち方のまま")
        for k in range(2, LIMIT + 2):
            with self.subTest(head=k):
                self.assertEqual(TOP[f"back-{k}"].get("trigger_rule"), "one_success")
                self.assertIn(f"back-{k - 1}", TOP[f"back-{k}"]["depends_on"])
                for name in ("fixed", "tests", "eyes"):
                    self.assertEqual(TOP[f"back-{k}"]["with"][name]["if_skipped"], None, f"{name} は飛んだ節を null で受ける")
        first = TOP["back-1"]
        self.assertEqual((first["depends_on"], first.get("trigger_rule")), (["eyes-out"], None))
        self.assertEqual((TOP["eyes-back"].get("depends_on"), TOP["eyes-back"].get("trigger_rule")),
                         ([f"back-{k}" for k in range(1, LIMIT + 2)], "none_failed_min_one_success"))

    def test_restore_sits_between_the_collect_and_the_seal(self):
        """作業ツリーを返す前の木へ戻す節 eyes-back-restore が、集め eyes-back の後・封じ merge-seal の前に在り、script は eyes_back_restore、
        mutates_checkout の鍵を持たず、封じと同じ when を持ち、指紋と戻す先 checkpoint を eyes-back から読む"""
        self.assertIn("eyes-back-restore", TOP)
        node = TOP["eyes-back-restore"]
        self.assertEqual(node["script"], "eyes_back_restore")
        self.assertNotIn("mutates_checkout", node)
        self.assertEqual(node["depends_on"], ["eyes-back"])
        self.assertEqual(node["when"], TOP["merge-seal"]["when"])
        self.assertEqual(node["with"], {"fingerprint": "$eyes-back.output.fingerprint", "checkpoint": "$eyes-back.output.checkpoint"})
        self.assertEqual(set(node["output_format"]["properties"]), {"restored", "kept", "reason"})
        self.assertEqual(TOP["merge-seal"]["depends_on"], ["eyes-back", "eyes-back-restore"])

    def test_final_and_collect_read_the_restore_outcome(self):
        """最後の承認ノード ask-final と報告の集め collect が、戻す節 eyes-back-restore の出力を back_restore として（飛んだ run では null で）読み、
        どちらも eyes-back-restore を待つ"""
        for key in ("ask-final", "collect"):
            with self.subTest(key):
                self.assertEqual(TOP[key]["with"].get("back_restore"), {"from": "$eyes-back-restore.output", "if_skipped": None})
                self.assertIn("eyes-back-restore", TOP[key]["depends_on"])

    def test_later_heads_still_run_when_a_node_inside_the_returned_round_falls(self):
        """返した周の中の節（修正・最後の試験・独立の目）が落ちると、その後ろの受け皿・合わせは「前が落ちたので飛んだ節」になる。次の周の頭は
        前の周の頭が成功していればそれでも走り（受け皿の got が欠けた周として記録を運ぶ）、集め eyes-back まで届く"""
        after_fix = {"fix-out": "skipped_after_failure", "fixed": "skipped_after_failure", "gate-out": "skipped_after_failure", "eyes-out": "skipped_after_failure"}
        after_gate = {"fix-out": "completed", "fixed": "completed", "gate-out": "skipped_after_failure", "eyes-out": "skipped_after_failure"}
        after_eyes = {"fix-out": "completed", "fixed": "completed", "gate-out": "completed", "eyes-out": "skipped_after_failure"}
        for fell, inside in (("fix", after_fix), ("gate", after_gate), ("eyes", after_eyes)):
            for k in range(2, LIMIT + 2):
                with self.subTest(fell=fell, head=k):
                    states = {f"back-{k - 1}": "completed", **{f"back-{k - 1}-{x}": s for x, s in inside.items()}}
                    self.assertTrue(would_run(TOP[f"back-{k}"], states), f"back-{k} が前の周の中の節の落ちで飛ぶ")
        heads = {f"back-{k}": "completed" for k in range(1, LIMIT + 2)}
        self.assertTrue(would_run(TOP["eyes-back"], heads))

    def test_heads_stay_skipped_when_the_first_head_did_not_run(self):
        """計画や修正で止まった run は 1 周目の頭が飛び、後ろの周の頭・集め eyes-back も飛んだまま（最後の承認ノードと封じが走らない）。
        前の周の頭が落ちて飛んだ時も同じ"""
        self.assertFalse(would_run(TOP["back-1"], {"eyes-out": "skipped"}))
        self.assertFalse(would_run(TOP["back-1"], {"eyes-out": "skipped_after_failure"}))
        for previous in ("skipped", "skipped_after_failure"):
            for k in range(2, LIMIT + 2):
                with self.subTest(previous=previous, head=k):
                    states = {f"back-{k - 1}": previous, **{f"back-{k - 1}-{x}": previous for x in ("fixed", "fix-out", "gate-out", "eyes-out")}}
                    self.assertFalse(would_run(TOP[f"back-{k}"], states))
            self.assertFalse(would_run(TOP["eyes-back"], {f"back-{k}": previous for k in range(1, LIMIT + 2)}))


class IncludeInputsCase(unittest.TestCase):
    """include した block の入力が全部渡るか訳の表に在るか（L-W67）は、全部の graph に効く tests/layers/test_include_inputs.py が見る"""

    def test_once_only_includes(self):
        """一度だけの include は line に 1 つずつ（案の直し・その事前審査・2 度目の修正・再審・修正の後の並行 PR）"""
        named = [n["include"] for n in INCLUDES.values()]
        for key in ONCE:
            with self.subTest(include=key):
                self.assertIn(key, TOP)
                self.assertNotIn("loop_group", TOP[key])
        self.assertEqual(named.count("works-factory-fix"), 2 + LIMIT, "1 回目・2 度目と、返す周ごとに 1 つ")
        self.assertEqual(named.count("works-factory-plan"), 3, "往復の中・案の直し・仕様駆動の run の spec-plan")
        self.assertEqual(named.count("works-factory-plan-review"), 3, "往復の中・案の直し・設計の段の往復の theme-review（形 theme）")
        self.assertEqual(named.count("works-factory-diagnose"), 2, "再審と、仕様駆動の run の spec-diagnose")
        self.assertEqual(named.count("works-factory-parallel-pr"), 1)
        self.assertEqual(named.count("works-factory-judge"), 1, "再審は判定のまとめを 2 度 include せず diagnose を直に include する")
        self.assertEqual(named.count("works-factory-eyes"), 1 + LIMIT, "最初の目と、返す周ごとに 1 つ")
        self.assertEqual(named.count("works-factory-test-gate"), 2 + LIMIT, "直す前・最後の試験と、返す周ごとに 1 つ")
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
        """8.1: 判定から入る run で、直した差分が在る時だけ、修正の後に 1 度だけ並行 PR を確かめ直す。始めで止まった run は request-in が
        飛ぶので、fixed を先に読んで打ち切る（筋書き start-refused）"""
        node = TOP["parallel-pr-after"]
        self.assertEqual(node["when"], "$fixed.output.diffed == true && $request-in.output.entry != ''")
        self.assertEqual((node["with"]["base"], node["with"]["changed"]), ("$start.output.ports.base_rev", "[]"))
        self.assertIn("parallel-pr-after-out", TOP["test-gate-final"]["depends_on"])
        # 修正の後は封じた差分から hunk を外さず、残っていると申し送る段（parallel-pr の設計書の 1.2 の stage）
        self.assertEqual(node["with"]["stage"], "after")

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
        # spec- は仕様駆動の run の修正前、fixture- は直す前で止まった写しの run の修正前
        self.assertEqual(gates, ["gate-start", "gate-before-fix", "spec-gate-before-fix", "fixture-gate-before-fix", "gate-replan", "gate-final"])
        for key in gates:
            self.assertEqual([o["id"] for o in TOP[key]["wait"]["options"]], ["approve", "continue", "stop", "reject"], key)
        # 往復の本体の関所は設計の相談の gate-design 1 つだけ（本体の唯一の終わり。E16・3.1 節）。選び肢は 4 つの語と revise
        # 設計の段の往復の本体の関所は gate-theme 1 つ（3.3 節）。選び肢は 4 つの語と revise。設計の相談はそれに設計へ戻す redesign を足す
        for body, gate, options in ((LOOP, "gate-design", ["approve", "continue", "stop", "reject", "revise", "redesign"]),
                                    (THEME_LOOP, "gate-theme", ["approve", "continue", "stop", "reject", "revise"])):
            with self.subTest(gate=gate):
                self.assertEqual([k for k in body if "wait" in body[k]], [gate])
                self.assertEqual([o["id"] for o in body[gate]["wait"]["options"]], options)
                self.assertFalse([k for k, n in body.items() if gate in (n.get("depends_on") or [])], "関所の後ろに本体の節を置かない")

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

    def test_line_inputs_are_the_current_seventeen(self):
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
        打ち切るので、依頼の文の run は飛ばされた spec-entry の出力を読まない）。どの節も answer-start を request-in より先に読む読み順
        は、ここで縛らず筋書き start-refused の dry-run が照らす（始めで止まった run は request-in が飛ぶ）"""
        self.assertEqual(TOP["judge"]["when"], "$test-gate-base.output.ok == true && $start.output.from_spec == false")
        when = TOP["test-gate-base"]["when"]
        head, tail = when.split(" || ")
        self.assertEqual(head, "$answer-start.output.go == true && $request-in.output.go == true && $start.output.from_fixture == false"
                               " && $start.output.from_spec == false")
        self.assertIn("$spec-entry.output.ok == true", tail)
        self.assertNotIn("$spec-entry", head)

    def test_fix_gets_the_routes(self):
        for name in ("fix", "refix-run"):
            with self.subTest(name):
                self.assertEqual(TOP[name]["with"]["routes"], "$start.output.ports.routes")
        self.assertEqual(TOP["spec-plan"]["with"]["routes"], "spec")

    def test_before_fix_gate_is_shared(self):
        """6.5 の 8: spec- の付いた 3 つ（と直す前で止まった写しの run の fixture- の付いた 3 つ。4.1）は今の 3 つと同じ script・
        output_format・wait: の form と options（錨で本体が 1 つ）を持ち、<頭>-gate-before-fix の attention だけが <頭>-ask-before-fix を読む"""
        for head in ("spec", "fixture"):
            for old in ("ask-before-fix", "answer-before-fix"):
                new = f"{head}-{old}"
                with self.subTest(new):
                    self.assertEqual((TOP[new]["script"], TOP[new]["output_format"]), (TOP[old]["script"], TOP[old]["output_format"]))
            old, new = TOP["gate-before-fix"]["wait"], TOP[f"{head}-gate-before-fix"]["wait"]
            self.assertEqual((new["form"], new["options"]), (old["form"], old["options"]))
            self.assertEqual(new["attention"], f"${head}-ask-before-fix.output.text")
        self.assertEqual(TOP["fixture-ask-before-fix"]["with"]["fixture"], "$start.output.fixture")
        self.assertIn("&before_fix_wait", TEXT)

    def test_only_spec_and_fixture_answers_wire_the_direction(self):
        """一言の向きの判定（block answer-direction）の配線: spec-answer-before-fix と fixture-answer-before-fix だけが with: に direction
        （同じ道の受け皿の got。飛ばされたら null）と direction_due 'true' を持ち、本線の answer-before-fix は持たない（今の振る舞いのまま）。
        spec-direction・fixture-direction の when: はそれぞれ from_spec・fixture_gate の句で始まり、with: の plan は同じ道の ask の出力 plan を読む。
        三つの答えは同じ output_format（止めた訳 reason の欄を持つ）"""
        self.assertLessEqual({"spec-direction", "spec-direction-out", "fixture-direction", "fixture-direction-out"}, set(TOP),
                             "一言の向きの判定の node と受け皿が、仕様駆動の道と写しの道に在る")
        for head, gate in (("spec", "from_spec"), ("fixture", "fixture_gate")):
            direction, answer = TOP[f"{head}-direction"], TOP[f"{head}-answer-before-fix"]
            with self.subTest(head):
                self.assertEqual(direction["include"], "works-factory-answer-direction")
                self.assertTrue(direction["when"].startswith(f"$start.output.{gate} == true && "), direction["when"])
                self.assertTrue(direction["when"].endswith(f"${head}-ask-before-fix.output.open == true"), direction["when"])
                self.assertEqual(direction["with"]["plan"], {"from": f"${head}-ask-before-fix.output.plan", "if_skipped": None})
                self.assertEqual(direction["with"]["answer"], f"${head}-gate-before-fix.output")
                self.assertEqual(direction["with"]["asked"], f"${head}-ask-before-fix.output.asked")
                self.assertEqual(direction["with"]["lang"], "$start.output.ports.lang")
                self.assertEqual(TOP[f"{head}-direction-out"]["with"]["got"], f"${head}-direction.output")
                self.assertEqual(answer["with"]["direction"], {"from": f"${head}-direction-out.output.got", "if_skipped": None})
                self.assertEqual(answer["with"]["direction_due"], "true")
                self.assertIn(f"{head}-direction-out", answer["depends_on"])
        self.assertEqual({n for n, node in TOP.items() if "direction_due" in (node.get("with") or {})},
                         {"spec-answer-before-fix", "fixture-answer-before-fix"})
        self.assertEqual({n for n, node in TOP.items() if "direction" in (node.get("with") or {})},
                         {"spec-answer-before-fix", "fixture-answer-before-fix"})
        self.assertNotIn("direction", TOP["answer-before-fix"]["with"])
        self.assertNotIn("direction_due", TOP["answer-before-fix"]["with"])
        self.assertIn("reason", TOP["answer-before-fix"]["output_format"]["properties"])
        self.assertNotIn("reason", TOP["answer-before-fix"]["output_format"]["required"], "reason は任意の欄（3 道で同じ形のまま）")
        self.assertIn("plan", TOP["ask-before-fix"]["output_format"]["properties"])
        self.assertNotIn("plan", TOP["ask-before-fix"]["output_format"]["required"])


if __name__ == "__main__":
    unittest.main()
