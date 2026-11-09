"""line の YAML の配線（docs/design/line.md の 11 節の test_wiring.py）: 返りの直の結びと返し・独立の目から修正の段へ返す輪の待ち方と、
封じと最後の承認ノードが最後の周を読むこと（書き込みの順の守り）。

元は test_line.py の LineWiringCase・HandoffCase（docs/design/README.md の 9.5）。include した block の中は各 block の試験が見る。
一度だけの include・when: の句・承認ノードの選択肢・with: の鍵と script の読みの一致のような YAML の形は、全部の graph に効く
tests/layers/ の試験（test_include_inputs.py・test_gates.py・test_block_returns.py・test_depth_skip.py）と、残す筋書きの結末
（tests/blocks/line/test_scenarios.py の NoApplyTest・test_scenarios_gates.py の NoApplyCase）が見る。
"""
import json
import re
import unittest

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
BODIES = {**LOOP, **THEME_LOOP}   # 輪の本体の節
NODES = {**TOP, **BODIES}
INCLUDES = {k: n for k, n in NODES.items() if "include" in n}
LENIENT = ("all_done", "one_success")   # 落ちた節の後にも走る待ち方（tests/workflows/test_returns_never_fail.py の LENIENT と同じ）
BOUND = re.compile(r"\$([A-Za-z][\w-]*)\.output\b")


def bound_ids(node: dict) -> set[str]:
    """節が with:・when: で結ぶ $<id>.output の <id>（loop_group の本体と output_format は見ない）"""
    return set(BOUND.findall(json.dumps({k: v for k, v in node.items() if k not in ("output_format", "loop_group")}, ensure_ascii=False)))


def lenient(node: dict) -> bool:
    return node.get("trigger_rule") in LENIENT or node.get("always_run") is True


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


def settled(fell: str) -> dict:
    """一番上の節 fell が落ちた run の、一番上の節の結末（would_run の状態の語）。when: は読まず、走りうる節は走ったと見る"""
    state: dict = {}
    todo = list(TOP)
    while todo:
        ready = [k for k in todo if all(d in state for d in TOP[k].get("depends_on") or [])]
        if not ready:
            raise AssertionError(f"待つ先の結末が決まらない節: {todo}")
        for key in ready:
            todo.remove(key)
            deps = TOP[key].get("depends_on") or []
            if key == fell:
                state[key] = "failed"
            elif not deps or would_run({**TOP[key], "depends_on": deps}, state):
                state[key] = "completed"
            else:
                state[key] = "skipped_after_failure" if any(state[d] in ("failed", "skipped_after_failure") for d in deps) else "skipped"
    return state


class ReturnsCase(unittest.TestCase):
    """block と輪の返りの直の結び（docs/design/line.md の 13 節）と返し（埋め P2）"""

    def test_bodies_are_written_once(self):
        for script, count in (("relay", 1), ("gate_answer", 1)):
            with self.subTest(script=script):
                self.assertEqual(len(re.findall(rf"^\s*script: {script}\s*$", TEXT, re.M)), count)
        self.assertEqual(sorted(k for k, n in TOP.items() if n.get("script") == "relay"),
                         ["design-in", "lens-2-in", "lens-in", "structure-in", "theme-design-in", "theme-world-in"])
        self.assertEqual(sorted(k for k, n in TOP.items() if n.get("script") == "gate_answer"), ["answer-final", "answer-start"])

    def test_plan_rounds_wait_on_every_stage_that_can_stop(self):
        """計画の往復の when は、前の段のうち止める理由（stop_reason）を返す node（owed・structure-in・tiers）の全部を見る"""
        guard = TOP["plan-rounds"]["when"]
        for stage in ("owed", "structure-in", "tiers"):
            with self.subTest(stage=stage):
                self.assertIn(f"${stage}.output.stop_reason == ''", guard)

    def test_a_strict_reader_is_skipped_when_what_it_reads_falls(self):
        """緩い読み手（落ちた節の後にも走る節）でない読み手は、結ぶ include（返す節）か輪が落ちた run では、待ち方だけで飛ぶ（Archon は
        落ちた節への with: を if_skipped に落とさず、読んだ節を落とす。docs/design/line.md の 13 節）。緩い読み手が直に結ぶ include の
        返す節と輪は tests/workflows/test_returns_never_fail.py が落ちない節として照らす（輪は script の節でないので赤）"""
        readers = {k: bound_ids(n) for k, n in TOP.items() if not lenient(n)}
        for fell in (k for k, n in TOP.items() if "include" in n or "loop_group" in n):
            state = settled(fell)
            with self.subTest(fell=fell):
                self.assertEqual(sorted(k for k, ids in readers.items() if fell in ids and state[k] == "completed"), [],
                                 f"{fell} が落ちても走り、落ちた {fell} を結ぶ節")

    def test_loop_returns_reach_the_collect_through_the_node_after_the_loop(self):
        """報告を組む collect（緩い読み手）は輪を結ばず、輪を既定の待ち方で結ぶ直後の script が欄 rounds で運ぶ返りを読む"""
        for loop, carrier, key in (("plan-rounds", "ask-before-fix", "rounds"), ("theme-rounds", "theme-descend", "theme_rounds")):
            with self.subTest(loop=loop):
                self.assertEqual(TOP["collect"]["with"][key], {"from": f"${carrier}.output.rounds", "if_skipped": None})
                self.assertEqual((TOP[carrier]["with"]["rounds"], TOP[carrier].get("trigger_rule")), (f"${loop}.output", None))
                self.assertIn(loop, TOP[carrier]["depends_on"])
                self.assertIn("rounds", TOP[carrier]["output_format"]["properties"])

    def test_merge_seal_waits_for_the_eyes_back_collector(self):
        """封じは最後の周の目と試験を読むので、返す輪の集めを待つ（docs/design/line.md の 1.3）"""
        self.assertEqual(TOP["merge-seal"]["depends_on"], ["eyes-back", "eyes-back-restore"])

    def test_merge_apply_reads_the_seal_through_ask_final(self):
        """封じの値は最後の承認ノードが封じの返りから読んで返し、当ての段はそれだけを読む（出どころを 1 つにする）。封じが飛んだ run は
        sealed_hash が空で、merge の apply が拒む（閉じた側に倒れる）"""
        with_ = TOP["merge-apply"]["with"]
        for name in ("sealed_hash", "fingerprint", "green_ok", "eyes_ok", "r2"):
            self.assertEqual(with_[name], f"$ask-final.output.{name}", name)
        self.assertNotIn("merge-seal", bound_ids(TOP["merge-apply"]))


class EyesBackCase(unittest.TestCase):
    """独立の目から修正の段へ返す輪（docs/design/line.md の 1.3 の 21.5）の周の節と、後ろのつなぎ替え"""

    def test_seal_and_final_read_the_last_round(self):
        """merge-seal が eyes-back を待ち、when に sealable を持ち、指紋・緑・目の値を eyes-back から読む。ask-final は eyes-back を
        if_skipped: null で読み、merge-apply の items と result の eyes は eyes-back から読み、eyes-back は when を持たず、周の頭が 1 つも走らない run では飛ぶ（all_done にすると、計画や修正で止まった run でも集めが済み、最後の承認ノードが走る）"""
        seal = TOP["merge-seal"]
        self.assertEqual(seal["depends_on"], ["eyes-back", "eyes-back-restore"])
        self.assertIn("$eyes-back.output.sealable == true", seal["when"])
        self.assertEqual({k: seal["with"][k] for k in ("fingerprint", "green_ok", "eyes_ok")},
                         {"fingerprint": "$eyes-back.output.fingerprint", "green_ok": "$eyes-back.output.green_ok", "eyes_ok": "$eyes-back.output.eyes_ok"})
        ask = TOP["ask-final"]
        self.assertIn("eyes-back", ask["depends_on"])
        self.assertEqual(ask["with"]["eyes_back"], {"from": "$eyes-back.output", "if_skipped": None})
        self.assertEqual(ask["with"]["tests"], {"from": "$test-gate-final.output", "if_skipped": None}, "最初の試験と目は最初の周の返り")
        self.assertEqual(ask["with"]["eyes"], {"from": "$eyes.output", "if_skipped": None})
        self.assertEqual(TOP["merge-apply"]["with"]["items"], "$eyes-back.output.item_claims")
        self.assertEqual(TOP["result"]["with"]["eyes"], {"from": "$eyes-back.output.eyes", "if_skipped": None})
        self.assertEqual(TOP["collect"]["with"]["eyes_back"], {"from": "$eyes-back.output", "if_skipped": None})
        self.assertEqual((TOP["eyes-back"]["trigger_rule"], TOP["eyes-back"].get("when")), ("none_failed_min_one_success", None))
        self.assertIn("eyes-back", TOP["result"].get("depends_on", []) + TOP["collect"]["depends_on"])

    def test_round_waits_reach_the_next_head_after_an_internal_error(self):
        """周 k の修正の段の中の節が誤りで落ちると、Archon はその後ろの周の節（試験・目）を「前が落ちたので飛んだ」節にする（修正の block の
        nodes-ok が中の落ちを block の外へ伝える）。それでも次の周の頭と集めが走るように、周の合わせの節 back-k-fixed と 2 周目以降の頭は
        one_success で待つ（周 k の頭が走れば走る。合わせの節は修正の block の返す節が返した止めを受けて『進めなかった』を返し、頭はその周の
        試験と目を null で受けて返す前の状態を持ち越す）。周の頭が 1 つも走らない run では、1 周目の頭が eyes を既定の待ち方で待って飛び、
        後ろの頭も合わせの節も飛ぶので、集めも封じも最後の承認ノードも飛ぶまま。試験と目の節は既定の待ち方のまま"""
        for k in range(1, LIMIT + 1):
            with self.subTest(round=k):
                fixed = TOP[f"back-{k}-fixed"]
                self.assertEqual((fixed.get("trigger_rule"), fixed.get("depends_on")), ("one_success", [f"back-{k}", f"back-{k}-fix"]))
                self.assertEqual(fixed["with"]["add"], {"from": f"$back-{k}-fix.output", "if_skipped": None})
                for suffix in ("-fix", "-gate"):
                    self.assertIsNone(TOP[f"back-{k}{suffix}"].get("trigger_rule"), f"back-{k}{suffix} は落ちた節の後ろで飛ぶ既定の待ち方のまま")
        for k in range(2, LIMIT + 2):
            with self.subTest(head=k):
                self.assertEqual(TOP[f"back-{k}"].get("trigger_rule"), "one_success")
                self.assertIn(f"back-{k - 1}", TOP[f"back-{k}"]["depends_on"])
                for name in ("fixed", "tests", "eyes"):
                    self.assertEqual(TOP[f"back-{k}"]["with"][name]["if_skipped"], None, f"{name} は飛んだ節を null で受ける")
        first = TOP["back-1"]
        self.assertEqual((first["depends_on"], first.get("trigger_rule")), (["eyes"], None))
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
        """返した周の中の節（修正・最後の試験・独立の目）が落ちると、その後ろの節は「前が落ちたので飛んだ節」になる。次の周の頭は前の周の頭が
        成功していればそれでも走り（返りが欠けた周として記録を運ぶ）、集め eyes-back まで届く"""
        after_fix = {"fix": "failed", "fixed": "completed", "gate": "skipped", "eyes": "skipped"}
        after_gate = {"fix": "completed", "fixed": "completed", "gate": "failed", "eyes": "skipped_after_failure"}
        after_eyes = {"fix": "completed", "fixed": "completed", "gate": "completed", "eyes": "failed"}
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
        self.assertFalse(would_run(TOP["back-1"], {"eyes": "skipped"}))
        self.assertFalse(would_run(TOP["back-1"], {"eyes": "skipped_after_failure"}))
        for previous in ("skipped", "skipped_after_failure"):
            for k in range(2, LIMIT + 2):
                with self.subTest(previous=previous, head=k):
                    states = {f"back-{k - 1}": previous, **{f"back-{k - 1}-{x}": previous for x in ("fixed", "fix", "gate", "eyes")}}
                    self.assertFalse(would_run(TOP[f"back-{k}"], states))
            self.assertFalse(would_run(TOP["eyes-back"], {f"back-{k}": previous for k in range(1, LIMIT + 2)}))


class DirectionWiringCase(unittest.TestCase):
    """一言の向きの止め（承認の判断）の配線: 仕様駆動の道と写しの道の答えの node は本線と同じ script で、同じ道の向きの判定の返りを読む。
    筋書きで回すのは仕様駆動の道（spec-direction）だけなので、写しの道が同じ判断に届くことをここで見る"""

    def test_spec_and_fixture_answers_read_their_own_direction(self):
        for head in ("spec", "fixture"):
            answer = TOP[f"{head}-answer-before-fix"]
            with self.subTest(head):
                self.assertEqual(answer["script"], TOP["answer-before-fix"]["script"])
                self.assertEqual(answer["with"]["direction"], {"from": f"${head}-direction.output", "if_skipped": None})
                self.assertEqual(answer["with"]["direction_due"], "true")
                self.assertEqual(TOP[f"{head}-direction"]["with"]["answer"], f"${head}-gate-before-fix.output")


class ExcludedWiringCase(unittest.TestCase):
    """8.2（対象への書き込みの守り）: 並行 PR が外した hunk（判定のまとめの excluded を fix-in が運ぶ）を、修正の段の全部（1 回目・2 度目・
    独立の目から返す周）が受ける。外した hunk に触れた修正を拒むのは fix の受け付けで、fix-in が運ぶことは test_fix_in.py が見る"""

    def test_every_fix_stage_reads_the_exclusion_through_fix_in(self):
        stages = [k for k, n in TOP.items() if n.get("include") == "works-factory-fix"]
        self.assertEqual(len(stages), 2 + LIMIT, stages)
        for key in stages:
            with self.subTest(key):
                self.assertEqual(TOP[key]["with"]["excluded"], "$fix-in.output.excluded")


if __name__ == "__main__":
    unittest.main()
