"""修正のブロック（workflows/fix/）の形と script の振る舞いの試験。

YAML は PyYAML で読み、script は subprocess で起こす（Archon は起こさない）。筋書き（fixtures/）だけは tests/archon.py の
使い捨ての木で止めた Archon の `archon workflow test` を回す（源が無ければ見送る）。
返りの約束は docs/design.md の「サブグラフの出力の約束」の fix の返り、節の並びは docs/plans/2026-10-12-blocks/fix.md の「作る物」。
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

from tests import archon
from tests.bin import hermetic, trimmed
from tests.bin.gitkit import git
from tests.layers import scan
from tests.workflows.copied import REWRITES, assert_text_is_original

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "fix"
YAML_PATH = BLOCK / "works-factory-fix.yaml"
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

if str(LIB / "graphloops") not in sys.path:
    sys.path.append(str(LIB / "graphloops"))

from engine.schema import validate_schema  # noqa: E402  （output_format の照らし。jsonschema に頼らない lib の小道具）
import conflict  # noqa: E402
import fixboard  # noqa: E402
import rolekit  # noqa: E402
import ruling  # noqa: E402
import runreport  # noqa: E402

CONTRACT_FIELDS = {"done", "units", "groups", "conflicts", "replan_items", "objection", "diff", "allowed_test_changes",
                   "changed", "x_scalars", "delta_review", "handoffs", "mismatched", "stop_reason"}
CONTRACT_INPUTS = {"start", "baseline", "units", "judgment", "plan", "ripple", "depth", "answers", "prior_conflicts",
                   "plan_review", "notes"}
EXTRA_INPUTS = {"only_items", "mode", "group", "from_tree", "out_dir"}
CHANGED_MARKS = {"mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
                 "path_changed"}
INCLUDED_HEAD_KEYS = ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout")
READ_ONLY_ROLES = ("ruler", "delta-review", "review2", "lens", "consult-answer", "ruled-consult-answer")


def moved_policy(tmp: pathlib.Path) -> tuple:
    """run の始めに固めた方針の文書の版を持つ始めの記録の欄と、その後に書き換えた生の文書: ({policy_md, policy}, 生の文書のパス)。
    役の指示書が名指すのは固めた版の写しで、生の文書ではない（policy.frozen_copy）"""
    import policy
    doc = tmp / "policy.md"
    doc.write_text("- 始めの版\n", encoding="utf-8")
    fields = {"policy_md": str(doc), "policy": policy.freeze(tmp / "frozen", tmp, str(doc))}
    doc.write_text("- 書き換えた版\n", encoding="utf-8")
    return fields, str(doc)
# 作業ツリーを変えない script の節（E7）。置き場（run の成果物の置き場）にだけ書く
READ_ONLY_SCRIPTS = ("route", "prep", "tdd-unit", "conflict-check", "rule-prep", "rule-accept", "fix-ruled-prep",
                     "ruled-consult-check", "ruled-consult-accept", "assert-changed", "delta-cut", "lens-prep",
                     "lens-reply", "lens-collect", "delta-accept", "refix-prep", "cut2", "review2-accept", "refix2-prep", "tdd-prep",
                     "fix-prep", "consult-check", "consult-accept", "group-end", "fix-reads", "fix", "nodes-ok")

# 今の works（2aa7c66c）の同じ役の節の値: (model, effort, context, settingSources, sandbox)。
# 元 works/blk-fix/blk-fix.yaml の tdd・fix・fix-ruled・rule・plan-answer、blk-delta.yaml の review、blk-lens.yaml の
# lens-silent-failure-hunter、blk-refix.yaml の refix・review2・refix2
SANDBOX = {"enabled": True, "allowUnsandboxedCommands": False}
ORIGINAL_ROLES = {
    "tdd": ("sonnet", "high", None, ["user"], SANDBOX),
    "fixer": ("sonnet", "high", None, ["user"], SANDBOX),
    "fix-ruled": ("sonnet", "high", None, ["user"], SANDBOX),
    "ruler": ("opus", "high", None, ["user"], SANDBOX),
    "consult-answer": ("opus", "medium", None, ["user"], SANDBOX),
    "ruled-consult-answer": ("opus", "medium", None, ["user"], SANDBOX),
    "delta-review": ("sonnet", "medium", None, ["user"], SANDBOX),
    "lens": ("sonnet", "medium", "fresh", ["user"], SANDBOX),
    "refix": ("sonnet", "high", None, ["user"], SANDBOX),
    "review2": ("sonnet", "medium", None, ["user"], SANDBOX),
    "refix2": ("sonnet", "high", None, ["user"], SANDBOX),
}
# 今の works の輪の max_iterations（同じ元の YAML）
ORIGINAL_LOOPS = {"tdd-loop": 40, "fix-loop": 12, "fix-ruled-loop": 12, "rule-loop": 3, "delta-loop": 3, "refix-loop": 3,
                  "review2-loop": 3, "refix2-loop": 3}
# 元の修正役の output_format の欄（raiki61/claude-plugins @ 2aa7c66c の works/.shared/core/recount.py:85 FIX_OUTPUT_FORMAT
# = fix_output_format()。:69 が写しの p3.fix の schema に conflicts・consult・bash_writes を足した物）を、元のモジュールを読んで
# 写した値（CI に元が無いので定数に持つ）
FIX_REPLY_ORIGINAL = {
    "required": {"changes", "fix_closure", "gates_changed", "interactions", "mechanism_changed", "not_done", "path_changed",
                 "plan_faces", "premise_drift", "seams_changed", "security_surface_changed", "wrote_refs"},
    "properties": {"bash_writes", "changes", "conflicts", "consult", "decision_records_changed", "fix_closure", "gates_changed",
                   "interactions", "mechanism_changed", "not_done", "path_changed", "plan_faces", "premise_drift",
                   "premise_drift_note", "rejudge_requested", "seams_changed", "security_surface_changed", "wrote_refs",
                   "x_scalars"},
    "changes.required": {"breaks", "bypass_tried", "closure", "files", "precedent", "root_or_symptom", "unit_key", "what"},
    "changes.properties": {"breaks", "bypass_tried", "closure", "coverage", "files", "precedent", "root_or_symptom", "unit_key",
                           "what"},
}
FIX_RULES = ("common", "brief", "direct", "principles", "ruler", "tdd", "refix", "clash")
COMMANDS = ("delta-review", "review2", "lens-silent-failure-hunter")
NO_QUEUE = re.compile(r"\b(queue|lock)\b|\btake\(")
# 網に出ようとした子をすぐ落とす宛先（控えを読めなかった時に本物の網へ出ない）
NO_NET = {"https_proxy": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}


def load():
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


def all_nodes(doc):
    """工程の節を loop_group の中まで（id → 節）"""
    out = {}
    for node in doc["nodes"]:
        out[node["id"]] = node
        for inner in (node.get("loop_group") or {}).get("nodes") or []:
            out[inner["id"]] = inner
    return out


def refs(text: str) -> set:
    return set(re.findall(r"\$([a-z0-9-]+)\.output", str(text)))


class ContractCase(unittest.TestCase):
    """返す節 fix の output_format が約束の 12 欄をちょうど持つ（10 欄と、最後の関所を開ける理由の 2 欄 handoffs・mismatched）"""

    def setUp(self):
        self.doc = load()
        self.nodes = all_nodes(self.doc)
        self.fmt = self.nodes["fix"]["output_format"]

    def test_returns_fix_with_outcome_done(self):
        self.assertEqual(self.doc["name"], "works-factory-fix")
        self.assertEqual(self.doc["returns"], "fix")
        self.assertEqual(self.doc["outcome_field"], "done")

    def test_exact_fields_all_required_and_closed(self):
        self.assertEqual(set(self.fmt["properties"]), CONTRACT_FIELDS)
        self.assertEqual(set(self.fmt["required"]), CONTRACT_FIELDS)
        self.assertIs(self.fmt["additionalProperties"], False)
        self.assertEqual(self.fmt["properties"]["done"], {"type": "boolean"})

    def test_unit_status_enum_matches_unit_statuses(self):
        """単位の状態の enum（型の正本は YAML）は、lib の論理が読む語彙 fixboard.UNIT_STATUSES と同じ"""
        unit = self.fmt["properties"]["units"]["items"]
        self.assertEqual(unit["properties"]["status"]["enum"], list(fixboard.UNIT_STATUSES))

    def test_nested_shapes(self):
        props = self.fmt["properties"]
        unit = props["units"]["items"]
        self.assertEqual(set(unit["required"]), {"unit_id", "group_id", "status", "reason"})
        self.assertIs(unit["additionalProperties"], False)
        group = props["groups"]["items"]
        self.assertEqual(set(group["required"]), {"group_id", "unit_ids", "returned", "reason"})
        self.assertEqual(group["properties"]["returned"], {"type": "boolean"})
        self.assertEqual(set(props["changed"]["required"]), CHANGED_MARKS | {"premise_drift_note"})
        self.assertTrue(all(v == {"type": "boolean"} for k, v in props["changed"]["properties"].items() if k in CHANGED_MARKS))
        self.assertEqual(props["changed"]["properties"]["premise_drift_note"], {"type": "string"})
        self.assertEqual(props["x_scalars"], {"type": "object"})
        self.assertEqual(set(props["delta_review"]["required"]), {"rounds", "pass"})
        for name in ("replan_items", "allowed_test_changes", "handoffs", "mismatched"):
            self.assertEqual(props[name]["items"], {"type": "string"})
        self.assertEqual(props["objection"], {"type": "string"})
        pointer = props["diff"]
        self.assertEqual(set(pointer["required"]), {"type", "run_id", "path"})
        self.assertEqual(pointer["properties"]["type"]["enum"], ["archon_artifact"])
        self.assertEqual(props["conflicts"]["type"], ["object", "null"])
        self.assertEqual({k: v for k, v in props["conflicts"].items() if k != "type"},
                         {k: v for k, v in pointer.items() if k != "type"})


class RulerTypeCase(unittest.TestCase):
    """裁定役の返答の型の正本は節 ruler の output_format だけ（受け付けの ruling.problems は裁きの意味だけを見る）"""

    def fmt(self) -> dict:
        return all_nodes(load())["ruler"]["output_format"]

    def test_trimmed_min_length_kept_by_pattern(self):
        self.assertEqual(trimmed.missing_patterns(self.fmt()), [])

    def test_decision_vocabulary_matches_output_format(self):
        """受け付けが裁きを分ける語（conflict.DECISIONS）は、節 ruler の output_format の decision の enum と同じ"""
        row = self.fmt()["properties"]["rulings"]["items"]["properties"]
        self.assertEqual(row["decision"]["enum"], list(conflict.DECISIONS))

    def test_ruling_outside_the_type_is_rejected(self):
        good = {"id": "c-1", "decision": conflict.ASK, "text": "材料から決められないので人に回す", "limits": []}
        self.assertEqual(validate_schema({"rulings": [good]}, self.fmt()), [])
        for name, reply in (("裁きが無い", {"rulings": []}), ("知らない語", {"rulings": [{**good, "decision": "later"}]}),
                            ("知らない欄", {"rulings": [{**good, "note": "x"}]}),
                            ("範囲が無い", {"rulings": [{k: v for k, v in good.items() if k != "limits"}]})):
            with self.subTest(name):
                self.assertTrue(validate_schema(reply, self.fmt()))


class InputsCase(unittest.TestCase):
    def test_contract_inputs_and_extra_inputs_default_empty(self):
        doc = load()
        inputs = doc["inputs"]
        self.assertEqual(set(inputs), CONTRACT_INPUTS | EXTRA_INPUTS)
        for name in EXTRA_INPUTS:
            self.assertEqual(inputs[name].get("default"), "", name)

    def test_plan_review_is_an_input(self):
        """L-W19・F130: fix は事前審査の返り（plan_review）を入力に受け、線は 1 回目に計画の往復の review、2 度目に案の直しの review を
        渡す。1 回目の申し出と裁定（prior_conflicts）と機械の申し送り（notes）は 2 度目にだけ渡る。どれも既定値を持つ（K11）"""
        inputs = load()["inputs"]
        self.assertEqual({k: inputs[k]["default"] for k in ("prior_conflicts", "plan_review", "notes")},
                         {"prior_conflicts": "null", "plan_review": "null", "notes": ""})
        line = {n["id"]: n for n in yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))["nodes"]}
        self.assertEqual(line["fix"]["with"]["plan_review"], "$fix-in.output.review")
        self.assertEqual({k: line["refix-run"]["with"][k] for k in ("prior_conflicts", "plan_review", "notes")},
                         {"prior_conflicts": "$fix.output.conflicts", "plan_review": "$replan-review.output.review",
                          "notes": "$answer-replan.output.fix_notes"})
        self.assertNotIn("prior_conflicts", line["fix"]["with"])

    def test_no_head_keys_that_include_drops(self):
        doc = load()
        self.assertEqual([k for k in INCLUDED_HEAD_KEYS if k in doc], [])


class GroupsCase(unittest.TestCase):
    """組は fan_out: で並べ、幅は run の時に $prep.output.groups から決まる。固定の枝の数・待ちの列・錠は持たない（no-queue）"""

    def setUp(self):
        self.doc = load()
        self.nodes = all_nodes(self.doc)

    def test_exactly_two_self_launching_fanouts(self):
        launchers = {nid: n for nid, n in self.nodes.items() if "workflow" in n}
        self.assertEqual(set(launchers), {"groups-par", "groups-seq"})
        for node in launchers.values():
            self.assertEqual(node["workflow"], "works-factory-fix")
            self.assertEqual(node["fan_out"]["items"], "$prep.output.groups")
            self.assertEqual(node["with"]["mode"], "group")
        self.assertEqual(launchers["groups-par"]["isolation"], "worktree")
        self.assertNotIn("isolation", launchers["groups-seq"])
        self.assertEqual(launchers["groups-seq"]["fan_out"]["max_parallel"], 1)

    def test_a_failed_node_halts_the_block_for_resume(self):
        """#576・#594: 子が 1 つでも落ちれば組の節が落ち（resume が落ちた子を続きから回すのは、組の節が済んでいない時だけ）、join は
        走らない。サブグラフのどの節が落ちても、返す節 fix と落ちても止めない段のほかの全部の節に結ぶブロックの sink の柵
        nodes-ok が飛ぶ。止めない段は線が報告で受け止めると宣言した節（レンズとその中継）とちょうど同じ"""
        for nid in ("groups-par", "groups-seq"):
            self.assertEqual(self.nodes[nid]["fan_out"]["join"], "all_success", nid)
        self.assertEqual(self.nodes["join"]["trigger_rule"], "none_failed_min_one_success")
        top = [n["id"] for n in self.doc["nodes"]]
        guard = self.nodes["nodes-ok"]
        self.assertEqual(guard["bash"], "true")
        line = {n["id"]: n for n in yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(
            encoding="utf-8"))["nodes"]}
        declared = json.loads(line["collect"]["with"]["optional"])
        for include in ("fix", "refix-run"):
            with self.subTest(include=include):
                absorbed = {nid for nid in top if runreport._declared(f"{include}__{nid}", declared)}
                self.assertEqual(absorbed, {"lens", "lens-reply"})
                self.assertEqual(set(guard["depends_on"]), set(top) - {"fix", "nodes-ok"} - absorbed)
        self.assertEqual(guard["trigger_rule"], "none_failed_min_one_success")
        self.assertNotIn("when", guard, "柵が飛ぶのはどれかの節が落ちた時だけ（when で飛ぶ節は落ちと数えない）")
        self.assertEqual([nid for nid, n in self.nodes.items() if "nodes-ok" in (n.get("depends_on") or [])], [])

    def test_only_the_returning_node_and_reads_run_after_a_failure(self):
        """#594: 落ちた節の後ろの節は飛ぶ（済んだ控えを残さず、resume で作り直される）。all_done で走るのは返す節と、
        フックの記録を読むだけの fix-reads だけ"""
        self.assertEqual({n["id"] for n in self.doc["nodes"] if n.get("trigger_rule") == "all_done"}, {"fix", "fix-reads"})

    def test_fanouts_hang_off_block_mode_only(self):
        prep = self.nodes["prep"]
        self.assertEqual(prep["when"], "$route.output.group == false")
        for nid in ("groups-par", "groups-seq"):
            self.assertIn("prep", self.nodes[nid]["depends_on"])
            self.assertEqual(refs(self.nodes[nid]["when"]), {"prep"})

    def test_no_fixed_lanes_and_no_queue_in_scripts(self):
        self.assertEqual([nid for nid in self.nodes if re.search(r"-lane-\d", nid)], [])
        hits = [f"{p.name}:{i}" for p in sorted((BLOCK / "scripts").glob("*.py"))
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if NO_QUEUE.search(line)]
        self.assertEqual(hits, [])
        self.assertNotIn("flock", (LIB / "consult.py").read_text(encoding="utf-8"))   # 子の run ごとに置き場が分かれ、錠は効かない

    def test_one_tdd_unit_artifact_on_block_path(self):
        typed = [nid for nid, n in self.nodes.items() if n.get("output_type") == "tdd-unit"]
        self.assertEqual(typed, ["tdd-unit"])
        self.assertEqual(self.nodes["tdd-unit"]["depends_on"], ["join"])
        self.assertEqual(self.nodes["join"]["when"], "$route.output.group == false")

    def test_no_node_adds_permits_between_fix_accept_and_group_end(self):
        """#245: group-end は子の置き場の許しの訳を受け付けの後に引き直す。受け付けの通った周で輪が抜け、輪の体で
        fix-accept の後に走る節（範囲の相談の合意を書く consult-accept を含む）が無く、輪の後は group-end だけが走る間だけ、
        引き直した値が受け付けの時の値と同じになる"""
        loop = self.nodes["fix-loop"]["loop_group"]
        self.assertEqual(refs(loop["until_bash"]), {"fix-accept"})
        self.assertIn("$fix-accept.output.done", loop["until_bash"])
        body = {n["id"]: n for n in loop["nodes"]}

        def ancestors(nid):
            out, todo = set(), list(body[nid].get("depends_on") or [])
            while todo:
                dep = todo.pop()
                if dep in body and dep not in out:
                    out.add(dep)
                    todo.extend(body[dep].get("depends_on") or [])
            return out
        self.assertEqual(ancestors("fix-accept"), set(body) - {"fix-accept"})
        self.assertEqual(self.nodes["group-end"]["depends_on"], ["group-start", "tdd-loop", "fix-loop"])


class RolesCase(unittest.TestCase):
    def setUp(self):
        self.nodes = all_nodes(load())

    def test_read_only_roles_declare_it(self):
        for nid in READ_ONLY_ROLES:
            self.assertIs(self.nodes[nid].get("mutates_checkout"), False, nid)

    def test_read_only_scripts_declare_it_and_no_other_node_does(self):
        """E7: 読むだけの script の節は mutates_checkout: false。作業ツリーを変える節（戻し・後始末・当て直し）は書かない"""
        marked = {nid for nid, n in self.nodes.items() if n.get("mutates_checkout") is False}
        self.assertEqual(marked, set(READ_ONLY_ROLES) | set(READ_ONLY_SCRIPTS))

    def test_lens_nodes_match_the_lens_table(self):
        """レンズの表の行と工程のレンズの節は 1 対 1 で、中継の節がその節の出口を受け、集め役は中継の出口を受ける。ずれると
        起こしたレンズの行が毎回「落ちた」になる（lens_prep・lens_collect の名は表から引く）"""
        import lenses
        by_lens = {n["command"].removeprefix("lens-"): nid for nid, n in self.nodes.items()
                   if str(n.get("command", "")).startswith("lens-")}
        self.assertEqual(set(by_lens), {row["lens"] for row in lenses.LENSES})
        self.assertEqual(refs(self.nodes["lens-reply"]["with"]["reply"]), set(by_lens.values()))
        self.assertEqual(refs(self.nodes["lens-collect"]["with"]["reply"]["from"]), {"lens-reply"})

    def test_a_failed_lens_is_recorded_and_the_block_goes_on(self):
        """F327（元 works/darkfactory/darkfactory.yaml:946 の [optional]）: レンズが落ちても集め役は走り（支度が済んでいれば
        one_success）、レンズの行を理由つきの failed で残し、差分の審査へ進む。Archon は落ちた節の出口を if_skipped の結びでも
        読ませないので、集め役は飛ぶ中継の節の出口を if_skipped: null で受ける。支度が落ちた・飛んだ run では集め役も飛ぶ（F328）"""
        reply, collector = self.nodes["lens-reply"], self.nodes["lens-collect"]
        self.assertEqual((reply["depends_on"], reply.get("trigger_rule", "all_success")), (["lens"], "all_success"))
        self.assertEqual(reply["output_format"], self.nodes["lens"]["output_format"])
        self.assertEqual((collector["depends_on"], collector["trigger_rule"]), (["lens-prep", "lens-reply"], "one_success"))
        self.assertEqual(collector["with"]["reply"], {"from": "$lens-reply.output", "if_skipped": None})
        self.assertIn("lens-collect", self.nodes["delta-loop"]["depends_on"])

    def test_roles_keep_the_original_model_and_session_settings(self):
        for nid, (model, effort, context, sources, sandbox) in ORIGINAL_ROLES.items():
            node = self.nodes[nid]
            self.assertEqual((node.get("model"), node.get("effort"), node.get("context"), node.get("settingSources"),
                              node.get("sandbox")), (model, effort, context, sources, sandbox), nid)

    def test_borrowed_skills_sit_on_the_seat_roles(self):
        """借りた superpowers の技: TDD の役に test-driven-development、手直しの役に receiving-code-review（元 blk-fix.yaml:188・
        blk-refix.yaml:64,332。seat.SKILL_NODES と同じ役）。下請けを起こす修正役は Agent を持つ"""
        import seat
        got = {nid: n["skills"] for nid, n in self.nodes.items() if "skills" in n}
        want = {nid: [seat.skill_of(seat.load_seams()[seat.SEATS[nid]])] for nid in seat.SKILL_NODES}
        self.assertEqual(got, want)
        for nid in got:
            self.assertIn("Skill", self.nodes[nid]["allowed_tools"], nid)
        for nid in ("fixer", "fix-ruled"):
            self.assertIn("Agent", self.nodes[nid]["allowed_tools"], nid)

    def test_loops_keep_the_original_bounds(self):
        for nid, bound in ORIGINAL_LOOPS.items():
            self.assertEqual(self.nodes[nid]["loop_group"]["max_iterations"], bound, nid)

    def test_verdicts_only_on_the_first_review(self):
        """準拠（compliance）と品質（quality）の 2 判定は 1 回目の審査役 delta-review の型だけが要り、2 回目の review2 の型には
        欄が無い（元 works/tests/test_delta_marks.py の DeltaMarksCase.test_role_schema_carries_verdicts_on_first_review_only）"""
        import deltamarks
        first, second = self.nodes["delta-review"]["output_format"], self.nodes["review2"]["output_format"]
        for k in ("compliance", "quality"):
            self.assertIn(k, first["required"], k)
            self.assertIn(k, first["properties"], k)
            self.assertNotIn(k, second.get("required") or [], k)
            self.assertNotIn(k, second["properties"], k)
        self.assertEqual(first["properties"]["compliance"]["properties"]["verdict"]["enum"], list(deltamarks.COMPLIANCE))
        self.assertEqual(first["properties"]["quality"]["properties"]["verdict"]["enum"], ["pass", "fail"])

    def test_tdd_loop_bound_is_the_lib_budget(self):
        """TDD の輪の max_iterations は lib の回数の上限 tddloop.MAX_ITERATIONS と同じ値で、輪は tdd-step の done で抜ける
        （上限に届く周で tddloop.step が残りを direct（gave_up budget）にして done を立てるので、max_iterations に当てて run を
        落とさない。元 works/blk-fix/lib/tddloop.py:131・works/blk-fix/blk-fix.yaml:157、旧試験 TestYaml.test_node_order）"""
        import tddloop
        loop = self.nodes["tdd-loop"]["loop_group"]
        self.assertEqual(loop["max_iterations"], tddloop.MAX_ITERATIONS)
        self.assertEqual(refs(loop["until_bash"]), {"tdd-step"})
        self.assertIn("$tdd-step.output.done", loop["until_bash"])
        self.assertIn("done", self.nodes["tdd-step"]["output_format"]["required"])

    def test_tdd_role_continues_within_a_unit(self):
        """同じ単位の段（test → fix → refactor）は同じ会話で続け、単位が替わる周だけ新しい会話にする（元 works/blk-fix/blk-fix.yaml:142・
        :157 の fresh_context: false と、包みが単位の鍵で会話を切る works/blk-fix/lib/tddloop.py:880 write_key）。止めた Archon は
        fresh_context: false の loop_group で前の周の最後の会話を次の周の体の AI の節へ渡し（dag-executor.ts の
        lastSequentialSession）、節の context: fresh だけがそれを切る。並んだ層（2 つ以上の節の層）では会話を渡さないので、2 つの役は
        別の層に置く。周をまたぐ会話は筋書きで渡らない（K6）ので、ここは形だけを縛る"""
        loop = self.nodes["tdd-loop"]["loop_group"]
        self.assertIs(loop["fresh_context"], False)
        body = {n["id"]: n for n in loop["nodes"]}
        roles = sorted(nid for nid, n in body.items() if any(k in n for k in scan.ROLE_KINDS))
        self.assertEqual(roles, ["tdd", "tdd-new"])
        same, new = body["tdd"], body["tdd-new"]
        self.assertNotIn("context", same, "同じ単位の続きの役は前の周の会話を継ぐ")
        self.assertEqual(new.get("context"), "fresh", "新しい単位の役は新しい会話")
        wiring = ("id", "description", "context", "when", "depends_on", "trigger_rule")
        self.assertEqual({k: v for k, v in same.items() if k not in wiring}, {k: v for k, v in new.items() if k not in wiring},
                         "2 つの役は同じ指示書の字・道具・skills・印")
        for node in (same, new):
            self.assertNotIn("with", node, "輪の中の役の節に with: を足さない（K5）")
            self.assertNotIn("mutates_checkout", node)
        prep = body["tdd-prep"]["output_format"]
        self.assertIn("new_unit", prep["required"])
        self.assertEqual(prep["properties"]["new_unit"], {"type": "boolean"})
        self.assertEqual(same["when"], "$tdd-prep.output.go == true && $tdd-prep.output.new_unit == false")
        self.assertEqual(new["when"], "$tdd-prep.output.go == true && $tdd-prep.output.new_unit == true")
        self.assertEqual((same["depends_on"], new["depends_on"]), (["tdd-prep"], ["tdd-prep", "tdd"]),
                         "2 つの役を同じ層に置くと Archon は並んだ層として会話を切る")
        self.assertEqual(new.get("trigger_rule"), "none_failed_min_one_success", "続きの役が飛ばされた周も新しい単位の役は起きる")
        step = body["tdd-step"]
        self.assertEqual(step["depends_on"], ["tdd-prep", "tdd", "tdd-new"])
        self.assertEqual(step["with"], {"reply": {"from": "$tdd.output", "if_skipped": None},
                                        "reply_new": {"from": "$tdd-new.output", "if_skipped": None}})

    def test_fix_reply_shape_matches_the_original(self):
        """修正役の返答の型（&fix_reply。fixer と fix-ruled が共有）が、元の修正役の output_format の欄を 1 つも落とさない:
        required・欄の全部、changes[] の required・欄の全部が元の物を含む（FIX_REPLY_ORIGINAL）"""
        for nid in ("fixer", "fix-ruled"):
            fmt = self.nodes[nid]["output_format"]
            row = fmt["properties"]["changes"]["items"]
            got = {"required": set(fmt["required"]), "properties": set(fmt["properties"]),
                   "changes.required": set(row["required"]), "changes.properties": set(row["properties"])}
            for part, want in FIX_REPLY_ORIGINAL.items():
                self.assertEqual(want - got[part], set(), (nid, part))

    def test_give_up_counts_match_the_loop_bounds(self):
        """受け付けが諦める拒否の回は、輪の max_iterations と同じ（ずれれば諦めの前に輪の上限で節が落ちる）"""
        self.assertEqual(self.nodes["rule-loop"]["loop_group"]["max_iterations"], ruling.GIVE_UP_AFTER)
        for nid in ("delta-loop", "refix-loop", "review2-loop", "refix2-loop"):
            self.assertEqual(self.nodes[nid]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER, nid)

    def test_clash_loops_sit_between_join_and_the_ruled_fix(self):
        """#382: 合わせのループは join の後・申し出の照らしの前、裁定の後の合わせのループは裁定の輪の後・裁定の後の修正の輪の前（作業ツリーを
        変える 2 つの輪を順に）。上限の周は with: limit が持ち、輪の max_iterations と同じ（ずれれば片付けの前に輪の上限で節が落ちる）。
        支度・受け付けは 2 つの段で同じ script を pass で使い分ける。周ごとに組が替わりうるので、2 つの輪は毎周新しい会話
        （fresh_context: true。false だと合わせ役が前の組の会話を持ったまま次の組を直す）。確かめ直しの赤は並べた run だけが控えるので、
        合わせのループは並べた run だけで回り、申し出の照らしは飛ばしたループを待たずに回る"""
        self.assertEqual(self.nodes["clash-loop"]["depends_on"], ["join"])
        self.assertEqual(self.nodes["clash-loop"]["when"], "$prep.output.par == true")
        self.assertIn("clash-loop", self.nodes["conflict-check"]["depends_on"])
        self.assertEqual(self.nodes["conflict-check"]["trigger_rule"], "none_failed_min_one_success")
        self.assertEqual(self.nodes["clash-ruled-loop"]["depends_on"], ["conflict-check", "rule-loop"])
        self.assertIn("clash-ruled-loop", self.nodes["fix-ruled-loop"]["depends_on"])
        for loop, prep, accept, pass_ in (("clash-loop", "clash-prep", "clash-accept", "first"),
                                          ("clash-ruled-loop", "clash-ruled-prep", "clash-ruled-accept", "ruled")):
            self.assertEqual(self.nodes[accept]["with"]["limit"], self.nodes[loop]["loop_group"]["max_iterations"], loop)
            self.assertIs(self.nodes[loop]["loop_group"]["fresh_context"], True, loop)
            self.assertEqual(refs(self.nodes[loop]["loop_group"]["until_bash"]), {accept})
            self.assertEqual((self.nodes[prep]["script"], self.nodes[prep]["with"]["pass"]), ("clash_prep", pass_))
            self.assertEqual((self.nodes[accept]["script"], self.nodes[accept]["with"]["pass"]), ("clash_accept", pass_))
        for nid in ("clean", "fix"):
            self.assertTrue({"clash-loop", "clash-ruled-loop"} <= set(self.nodes[nid]["depends_on"]), nid)

    def test_answer_nodes_are_keyed_by_passes_and_name_nodes_here(self):
        """#385: 段 → 範囲の相談に答える役の節は fixrules.PASSES を鍵にした表 1 つ。値はどれもこの YAML の節で、
        段ごとの組みは YAML の配線（consult_accept の pass: と answer.from、答える役が待つ同じ段の consult_check）と一致する。
        表に無い段は例外"""
        import fixrules
        self.assertEqual(tuple(fixrules.ANSWER_NODES), fixrules.PASSES)
        for pass_, nid in fixrules.ANSWER_NODES.items():
            self.assertIn(nid, self.nodes, pass_)
            self.assertEqual(fixrules.answer_node(pass_), nid)
        checks = {n["with"]["pass"]: nid for nid, n in self.nodes.items() if n.get("script") == "consult_check"}
        accepts = {n["with"]["pass"]: n for n in self.nodes.values() if n.get("script") == "consult_accept"}
        self.assertEqual(set(accepts), set(fixrules.PASSES))
        for pass_, accept in accepts.items():
            answer = accept["with"]["answer"]["from"].removeprefix("$").removesuffix(".output")
            self.assertEqual(fixrules.answer_node(pass_), answer, pass_)
            self.assertEqual(self.nodes[answer]["depends_on"], [checks[pass_]], pass_)
        with self.assertRaises(ValueError):
            fixrules.answer_node("refix")


class FilesCase(unittest.TestCase):
    def setUp(self):
        self.nodes = all_nodes(load())

    def test_collectors_read_files_not_bindings(self):
        """落ちうる前の節の返りを with: で束ねない（落ちた節への束ねは if_skipped が在っても投げる）"""
        for nid in ("join", "tdd-unit", "fix"):
            self.assertNotIn("with", self.nodes[nid], nid)

    def test_named_scripts_and_commands_exist(self):
        scripts = {n["script"] for n in self.nodes.values() if "script" in n}
        self.assertEqual(sorted(s for s in scripts if not (BLOCK / "scripts" / f"{s}.py").is_file()), [])
        commands = {n["command"] for n in self.nodes.values() if "command" in n}
        self.assertEqual(commands, set(COMMANDS))
        for name in COMMANDS:
            self.assertTrue((BLOCK / "commands" / f"{name}.md").is_file(), name)
        for name in FIX_RULES:
            self.assertTrue((BLOCK / "commands" / "fix-rules" / f"{name}.md").is_file(), name)


    def test_delta_review_reads_the_seat_file(self):
        """1 回目の審査役は材料の seat_file（delta-cut が brief と must に名指す座。refix.cut）を読み、その型で審査する
        （元 works/blk-delta/commands/delta-review.md:15）"""
        lines = (BLOCK / "commands" / "delta-review.md").read_text(encoding="utf-8").splitlines()
        self.assertTrue(any(ln.startswith("  - `seat_file`: 空でなければ Read で全部読み、その型の手順で審査せよ。") for ln in lines))

class ScenarioCase(unittest.TestCase):
    """筋書き（fixtures/）を止めた Archon の workflow test で回す。道のつながりだけを確かめる"""

    def test_fixtures_reach_their_expected_ends(self):
        with archon.tree(["fix"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-fix", "--json", "--cwd", str(tree))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        got = {pathlib.Path(r["fixture"]).name: (r["outcome"], r["pass"]) for r in json.loads(done.stdout)["results"]}
        self.assertEqual(got, {"group-tdd.stubs.yaml": ("completed", True), "group-no-suite.stubs.yaml": ("completed", True),
                               "group-consult.stubs.yaml": ("completed", True),
                               "block-stops-at-fanout.stubs.yaml": ("failed", True)})


# ---------------------------------------------------------------- 差分の審査・レンズ・手直しの scripts（delta・lens・refix の節）
_RV_KEY = "stats.py mean: 分母が len(xs) - 1 になっている"
_RV_FACE = "stats.py mean: docstring が無い"
_RV_REVIEW = {"faces": [{"key": _RV_FACE, "kind": "contract_drift", "where": "stats.py", "cite": "return sum(xs)",
                         "why": "分母を直したが docstring が平均の定義を書かず、読む側が古い式を想定する"}],
              "checks": [],
              "compliance": {"verdict": "pass", "items": [], "read": "修正案の項目 1 と差分の stats.py を読み、項目と差分を照らした"},
              "quality": {"verdict": "fail", "why": "faces に挙げた穴は修正案の項目への準拠の外の品質の穴で、準拠の行には結ばない"}}
_RV_HANDLED = {"handled": [{"key": _RV_FACE, "handled": "fixed", "how": "mean に docstring を足して平均の定義を書いた",
                            "files": ["stats.py"]}]}


def _rv_node(nid):
    return all_nodes(load())[nid]


class DeltaScriptsCase(unittest.TestCase):
    """差分の審査・レンズ・手直しの scripts を一時の対象のリポジトリ（tests/e2e/target-seed/ の写し）と一時の置き場で起こし、
    標準出力の返りを節の output_format で照らす。置き場は $ARTIFACTS_DIR/fix/fix/（include の名 fix）"""

    def setUp(self):
        from tests.bin.gitkit import committed_copy
        import leftovers
        import planmarks
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-delta-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, ROOT / "tests" / "e2e" / "target-seed")
        self.art = self.tmp / "art"
        self.place = self.art / "fix" / "fix"
        (self.place / "r1").mkdir(parents=True)
        (self.place / "r1" / "start.json").write_text("{}\n", encoding="utf-8")
        start = leftovers.snapshot(self.repo)
        self._json("groups.json", {"groups": [{"group_id": "g1", "unit_ids": [_RV_KEY], "items": [1]}], "count": 1,
                                   "par": False, "start_tree": start, "out_dir": str(self.place / "groups")})
        self._json("assert-changed.json", {"ok": True, "reason": ""})
        self._json("depth.json", [{"unit_id": _RV_KEY, "depth": "標準", "why": "触るファイルが 4 個"}])
        self._json("p2.fix_plan.json", {"plan": [{"unit_keys": [_RV_KEY], "approach": "分母を len(xs) にする"}]})
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "refactor": "",
                                        "allowed_paths": ["stats.py"],
                                        "out_of_scope": [{"glob": "vendored/**", "why": "外の写し"}]}])
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        self.cfg = self.tmp / "claude-config"
        self.cfg.mkdir()

    def _json(self, name, doc):
        path = self.place / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def _run(self, script, nid, **inputs):
        env = {k: v for k, v in hermetic.child_env().items() if not k.startswith("PR_REVIEW_TOOLKIT")}
        env.update({"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": "run-delta",
                    "ARCHON_NODE_EXECUTION": json.dumps({"path": f"fix__{nid}"}), "WORKS_FACTORY_ROOT": str(ROOT),
                    "CLAUDE_CONFIG_DIR": str(self.cfg), "PYTHONDONTWRITEBYTECODE": "1"})
        env.update({f"INPUTS_{k.upper()}": v for k, v in inputs.items() if k != "env"})
        env.update(inputs.get("env") or {})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{script}.py")], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        node = _rv_node(nid)
        self.assertEqual(validate_schema(out, node["output_format"]), [], (nid, out))
        return out

    def _cut(self):
        out = self._run("delta_cut", "delta-cut")
        self.assertTrue(out["go"], out)
        return out

    def test_delta_cut_passes_the_plan_review_to_the_brief(self):
        """F302: 差分の審査役の材料 out.p2.plan_review は置き場の事前審査の返答の写し（prep が入力 plan_review から写す）。無い run は null"""
        out = self._cut()
        brief = json.loads(pathlib.Path(out["brief_file"]).read_text(encoding="utf-8"))
        self.assertIsNone(brief["reads"]["out.p2.plan_review"])
        review = {"faces": [{"key": "穴-分母が空の列で 0 になる", "kind": "contract_drift", "unit_keys": [_RV_KEY]}], "shrink": []}
        self._json("p2.plan_review.json", review)
        out = self._cut()
        brief = json.loads(pathlib.Path(out["brief_file"]).read_text(encoding="utf-8"))
        self.assertEqual(brief["reads"]["out.p2.plan_review"]["faces"], review["faces"])

    def test_refix_preps_tie_holes_through_the_plan_review(self):
        """F302: 1 回目と 2 回目の手直しの支度も、置き場の事前審査の返答の写し（p2.plan_review.json）を穴の名札の材料に渡す。修正役が
        塞いだと言った事前審査の穴（plan_faces の absorbed）の検算が開いたままなら、その穴の unit_keys の項目の枝に結ぶ（via check）。
        2 回目はその名札を前の往復の結びとして引き継ぐ（via earlier）。支度が plan_review を渡さないと、どちらも枝の無い名札になる"""
        face = "pf-1 平均の分母が空の列で割れる"
        self._json("p2.plan_review.json", {"faces": [{"key": face, "kind": "contract_drift", "unit_keys": [_RV_KEY]}], "shrink": []})
        reply = self.place / "g1-reply.json"
        reply.write_text(json.dumps({"changes": [], "not_done": [], "plan_faces": [{"key": face, "handled": "absorbed", "how": "分けた"}]},
                                    ensure_ascii=False), encoding="utf-8")
        self._json("groups/g1/result.json", {"group_id": "g1", "reply_file": str(reply)})
        self._cut()
        review = {**_RV_REVIEW, "faces": [], "faces_none": "差分の stats.py の mean を全部読み、新しい穴は無かった（検算の 1 件だけが開いている）",
                  "checks": [{"key": face, "closed": False, "why": "空の列で 0 割りのまま"}],
                  "quality": {"verdict": "pass", "why": "新しい品質の穴は無く、開いているのは事前審査の穴の検算の 1 件だけ"}}
        got = self._run("delta_accept", "delta-accept", reply=json.dumps(review, ensure_ascii=False))
        self.assertTrue(got["ok"], got)
        self.assertTrue(self._run("refix_prep", "refix-prep", n="1")["go"])
        ties = json.loads((self.place / "refix1-brief.json").read_text(encoding="utf-8"))["ties"]
        self.assertEqual([(t["key"], t["via"]) for t in ties], [(face, ["check"])])
        self.assertTrue(ties[0]["branches"], ties)
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", "def mean(xs):\n    if not xs:\n        return 0\n"),
                     encoding="utf-8")
        fixed = {"handled": [{"key": face, "handled": "fixed", "how": "空の列は 0 を返す", "files": ["stats.py"]}]}
        self.assertTrue(self._run("refix_accept", "refix-accept", reply=json.dumps(fixed, ensure_ascii=False), iteration="1", n="1")["ok"])
        self.assertTrue(self._run("cut2", "cut2")["go"])
        review2 = {**review, "checks": [{"key": face, "closed": False, "why": "負の数で割れる"}]}
        self.assertTrue(self._run("review2_accept", "review2-accept", reply=json.dumps(review2, ensure_ascii=False))["ok"])
        self.assertTrue(self._run("refix_prep", "refix2-prep", n="2")["go"])
        ties2 = json.loads((self.place / "refix2-brief.json").read_text(encoding="utf-8"))["ties"]
        self.assertEqual([t["key"] for t in ties2], [face])
        self.assertIn("earlier", ties2[0]["via"])
        self.assertEqual(ties2[0]["branches"], ties[0]["branches"])

    def test_delta_cut_skips_an_all_light_run(self):
        """全部の単位が軽量の run は delta/skipped.json に理由を書いて go: false（持ち主の決め dynamic-depth）"""
        import depth
        self._json("depth.json", [{"unit_id": _RV_KEY, "depth": depth.LIGHT, "why": "触るファイル 1 個"}])
        out = self._run("delta_cut", "delta-cut")
        self.assertEqual(out, {"go": False, "files": [], "diff_file": "", "brief_file": ""})
        got = json.loads((self.place / "delta" / "skipped.json").read_text(encoding="utf-8"))
        self.assertEqual(list(got), ["reason"])
        self.assertTrue(got["reason"].startswith("軽量で省いた"), got)
        self.assertFalse((self.place / "loop-fix_delta.json").exists())

    def test_delta_cut_raises_the_depth_before_skipping(self):
        """全部が軽量の run でも、修正の後の信号（修正役の異議）で標準へ上げてから決め、審査を回す（fixboard.redepth。元の h-redepth）"""
        import depth
        self._json("depth.json", [{"unit_id": _RV_KEY, "depth": depth.LIGHT, "why": "触るファイル 1 個"}])
        self._json("fix-ruled-reply.json", {"rejudge_requested": "単位の見立てが違う"})
        self.assertTrue(self._cut()["go"])
        raised = json.loads((self.place / "depth-raised.json").read_text(encoding="utf-8"))
        self.assertEqual(raised["units"][_RV_KEY]["depth"], depth.STANDARD)
        self.assertFalse((self.place / "delta" / "skipped.json").exists())

    def test_delta_cut_does_not_mark_a_failed_change_check_as_light(self):
        """変更の確かめが通らない run は審査を回さないが、全部が軽量の印 skipped.json は書かない（審査が通ったと読まれる）"""
        self._json("delta/skipped.json", {"reason": "前の回の印"})
        self._json("assert-changed.json", {"ok": False, "reason": "申告したファイルが変わっていない"})
        out = self._run("delta_cut", "delta-cut")
        self.assertFalse(out["go"])
        self.assertFalse((self.place / "delta" / "skipped.json").exists())

    def test_empty_diff_without_claims_does_not_launch_the_review(self):
        """作業ツリーが run の始めの版と同じ（.archon/ の下の変更は数えない）で、修正役が塞いだと言う事前審査の穴（plan_faces の
        absorbed）も無い run は、delta/skipped.json に訳を書いて go: false で審査役を起こさない。返す節はこれを審査を省いた run と
        読む（{rounds: 0, pass: true}）。塞いだと言う穴が在れば、差分が空でも検算のために審査を回す
        （元 works/.shared/core/graphloops/rules/review-loop.py:604 fix_delta_nonempty・:617 delta_review_due）"""
        import fixboard
        git(self.repo, "checkout", "-q", "--", "stats.py")
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "copied.txt").write_text("Archon が写した工程\n", encoding="utf-8")
        out = self._run("delta_cut", "delta-cut")
        self.assertEqual(out, {"go": False, "files": [], "diff_file": "", "brief_file": ""})
        got = json.loads((self.place / "delta" / "skipped.json").read_text(encoding="utf-8"))
        self.assertEqual(list(got), ["reason"])
        self.assertIn("差分が空", got["reason"])
        self.assertIn("塞いだと言われた穴も無い", got["reason"])
        self.assertFalse((self.place / "loop-fix_delta.json").exists())
        self.assertFalse((self.place / "review1-brief.json").exists())
        self.assertEqual(fixboard.delta_review(self.place), ({"rounds": 0, "pass": True}, True))
        with self.subTest("塞いだと言う穴が在る"):
            reply = self.place / "g1-reply.json"
            reply.write_text(json.dumps({"changes": [], "not_done": [], "plan_faces": [
                {"key": "pf-1", "handled": "absorbed", "how": "既に塞がっていた"}]}, ensure_ascii=False), encoding="utf-8")
            self._json("groups/g1/result.json", {"group_id": "g1", "reply_file": str(reply)})
            out = self._run("delta_cut", "delta-cut")
            self.assertTrue(out["go"], out)
            self.assertNotIn("stats.py", out["files"])
            self.assertFalse((self.place / "delta" / "skipped.json").exists())

    def test_cut_review_refix_rejects_outside_the_range_then_accepts(self):
        """標準の run: 差分を切って材料を書き、審査を受けて delta/review-1.json に pass: false、手直しの支度が指示書を書き、
        範囲の外（other.py）を変えた手直しは拒んで理由のファイルを置き、外を戻せば受ける"""
        out = self._cut()
        self.assertEqual(out["files"], ["stats.py"])
        brief = json.loads(pathlib.Path(out["brief_file"]).read_text(encoding="utf-8"))
        self.assertEqual([it["item"] for it in brief["plan_items"]], [1])
        self.assertFalse((self.place / "delta" / "skipped.json").exists())
        acc = self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))
        self.assertEqual((acc["ok"], acc["done"]), (True, True), acc)
        rec = json.loads((self.place / "delta" / "review-1.json").read_text(encoding="utf-8"))
        self.assertEqual((rec["pass"], rec["owed"]), (False, 1))
        prep = self._run("refix_prep", "refix-prep", n="1")
        self.assertEqual((prep["go"], prep["iteration"]), (True, 1))
        text = pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(str(self.place / "refix1-brief.json"), text)
        self.assertIn("`receiving-code-review`", text, "手直しの役に借りたスキルの座")
        seat_file = json.loads((self.place / "review1-brief.json").read_text(encoding="utf-8"))["seat_file"]
        self.assertIn("task-reviewer-prompt.md", pathlib.Path(seat_file).read_text(encoding="utf-8"), "1 回目の審査役の座")
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        (self.repo / "other.py").write_text("X = 1\n", encoding="utf-8")
        bad = self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False), iteration="1")
        self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
        self.assertIn("other.py", pathlib.Path(bad["reason_file"]).read_text(encoding="utf-8"))
        again = self._run("refix_prep", "refix-prep", n="1")
        self.assertEqual(again["iteration"], 2)
        self.assertIn(bad["reason_file"], pathlib.Path(again["prompt_file"]).read_text(encoding="utf-8"))
        (self.repo / "other.py").unlink()
        ok = self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False), iteration="2")
        self.assertEqual((ok["ok"], ok["done"]), (True, True), ok)
        cut2 = self._run("cut2", "cut2")
        self.assertEqual((cut2["go"], cut2["files"]), (True, ["stats.py"]), cut2)

    def test_third_refix_prompt_names_every_reject_of_the_loop(self):
        """どの回の役も輪の拒否の全部を読む。2 回続けて拒まれた輪の 3 回目の指示書が名指すファイルに、1 回目の拒否の理由も届く（#345）"""
        self._cut()
        self.assertTrue(self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))["ok"])
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        reasons = []
        for k, stray in ((1, "other.py"), (2, "another.py")):
            self.assertEqual(self._run("refix_prep", "refix-prep", n="1")["iteration"], k)
            for name in ("other.py", "another.py"):
                (self.repo / name).unlink(missing_ok=True)
            (self.repo / stray).write_text("X = 1\n", encoding="utf-8")
            bad = self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                            iteration=str(k))
            self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
            reasons.append(bad["reason"])
        self.assertNotIn("another.py", reasons[0])
        third = self._run("refix_prep", "refix-prep", n="1")
        self.assertEqual(third["iteration"], 3)
        head = pathlib.Path(third["prompt_file"]).read_text(encoding="utf-8").split("\n")[1]
        named = re.findall(re.escape(str(self.place)) + r"/\S+?\.md", head)
        self.assertEqual(len(named), 1, head)
        text = pathlib.Path(named[0]).read_text(encoding="utf-8")
        self.assertLess(text.index(reasons[0]), text.index(reasons[1]), "1 回目の拒否も古い順に届く")

    def test_refix_prompts_name_the_frozen_policy_copy(self):
        """1 回目と 2 回目の手直しの指示書が名指す方針の文書は、始めの記録の固めた版の写し（run の途中で書き換えた生の文書ではない）"""
        fields, raw_doc = moved_policy(self.tmp)
        self._json("r1/start.json", fields)
        self._cut()
        self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))
        prep = self._run("refix_prep", "refix-prep", n="1")
        text = pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(fields["policy"]["copy"], text)
        self.assertNotIn(raw_doc, text)
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        self.assertTrue(self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                                  iteration="1")["ok"])
        self.assertTrue(self._run("cut2", "cut2")["go"])
        review2 = {**_RV_REVIEW, "checks": [{"key": _RV_FACE, "closed": False, "why": "docstring は足したが平均の定義を書いていない"}]}
        self.assertTrue(self._run("review2_accept", "review2-accept", reply=json.dumps(review2, ensure_ascii=False))["ok"])
        prep = self._run("refix_prep", "refix2-prep", n="2")
        self.assertTrue(prep["go"], prep)
        text = pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(fields["policy"]["copy"], text)
        self.assertNotIn(raw_doc, text)

    def test_refix_prompts_paste_the_item_scope(self):
        """#570: 1 回目と 2 回目の手直しの指示書に、項目の変えてよいパスと out_of_scope が字のまま在り、受け付けは貼った glob の字で拒む"""
        import planrange
        self._cut()
        self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))
        text = pathlib.Path(self._run("refix_prep", "refix-prep", n="1")["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(planrange.SCOPE_HEAD, text)
        for path in ("stats.py", "vendored/**"):
            self.assertIn(f"`{path}`", text)
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        stray = self.repo / "vendored" / "x.py"
        stray.parent.mkdir()
        stray.write_text("X = 1\n", encoding="utf-8")
        declared = {"handled": [{**_RV_HANDLED["handled"][0], "files": ["stats.py", "vendored/x.py"]}]}
        bad = self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(declared, ensure_ascii=False), iteration="1")
        self.assertFalse(bad["ok"], bad)
        self.assertIn("vendored/x.py は項目 1 の out_of_scope（vendored/**）に当たる", bad["reason"])
        stray.unlink()
        self._run("refix_prep", "refix-prep", n="1")
        self.assertTrue(self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                                  iteration="2")["ok"])
        self.assertTrue(self._run("cut2", "cut2")["go"])
        review2 = {**_RV_REVIEW, "checks": [{"key": _RV_FACE, "closed": False, "why": "docstring は足したが平均の定義を書いていない"}]}
        self.assertTrue(self._run("review2_accept", "review2-accept", reply=json.dumps(review2, ensure_ascii=False))["ok"])
        text = pathlib.Path(self._run("refix_prep", "refix2-prep", n="2")["prompt_file"]).read_text(encoding="utf-8")
        for path in ("stats.py", "vendored/**"):
            self.assertIn(f"`{path}`", text, "2 回目の brief に plan_items が無くても指示書に貼る")

    def test_refix_undeclared_write_is_rejected(self):
        """記録の無い run の書き込みの出どころ（U6 の狭め）: 手直しの段の頭の木からの変更が handled[].files にも bash_writes にも無ければ拒む"""
        self._cut()
        self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))
        self.assertTrue(self._run("refix_prep", "refix-prep", n="1")["go"])
        self.assertTrue((self.place / "refix1-head.json").is_file())
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        undeclared = {"handled": [{"key": _RV_FACE, "handled": "declared",
                                   "how": "直さずに残す訳を述べた（stats.py の変更は申告しない）"}]}
        bad = self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(undeclared, ensure_ascii=False), iteration="1")
        self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
        self.assertIn("stats.py", bad["reason"])
        ok = self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False), iteration="2")
        self.assertEqual((ok["ok"], ok["done"]), (True, True), ok)

    def test_refix_accepts_read_the_recorder_log(self):
        """記録の根が在る run の 1 回目・2 回目の手直しの受け付けは、作業ツリーの記録を読み、記録の無い変更を拒む"""
        import writelog
        import writes
        log = writelog.log_path(writelog.root(self.cfg), self.repo)
        log.parent.mkdir(parents=True)
        log.write_text("", encoding="utf-8")
        p = self.repo / "stats.py"
        for n, (prep, accept) in enumerate((("refix-prep", "refix-accept"), ("refix2-prep", "refix2-accept")), 1):
            with self.subTest(accept=accept):
                if n == 1:
                    self._cut()
                else:
                    self.assertTrue(self._run("cut2", "cut2")["go"])
                nid, review = ("delta-accept", _RV_REVIEW) if n == 1 else ("review2-accept", {**_RV_REVIEW, "checks": [
                    {"key": _RV_FACE, "closed": False, "why": "docstring は足したが平均の定義を書いておらず、穴が残る"}]})
                self.assertTrue(self._run(nid.replace("-", "_"), nid, reply=json.dumps(review, ensure_ascii=False))["ok"])
                self.assertTrue(self._run("refix_prep", prep, n=str(n))["go"])
                p.write_text(p.read_text(encoding="utf-8") + f"\n# 手直し {n}\n", encoding="utf-8")
                bad = self._run("refix_accept", accept, n=str(n), reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                                iteration="1")
                self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
                self.assertIn(writes.REJECT + "stats.py", bad["reason"])
                _record(log, p)
                ok = self._run("refix_accept", accept, n=str(n), reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                               iteration="2")
                self.assertEqual((ok["ok"], ok["done"]), (True, True), ok)

    def test_third_rejection_gives_up_and_unknown_keys_are_rejected(self):
        self._cut()
        stray = {**_RV_REVIEW, "faces": [{**_RV_REVIEW["faces"][0], "where": "nowhere.py"}]}
        for k in (1, 2, 3):
            out = self._run("delta_accept", "delta-accept", reply=json.dumps(stray, ensure_ascii=False))
            self.assertEqual((out["ok"], out["done"]), (False, k == 3), out)
            self.assertIn("nowhere.py", out["reason"])
        rec = json.loads((self.place / "delta" / "review-1.json").read_text(encoding="utf-8"))
        self.assertEqual((rec["pass"], rec["gave_up"]), (False, True))
        self.assertFalse(self._run("refix_prep", "refix-prep", n="1")["go"])

    def test_not_launched_roles_are_done(self):
        """支度が go: false で役を起こさなかった時（with: reply が null）は、受け付けが done: true で輪を抜ける"""
        self._cut()
        self.assertEqual(self._run("refix_prep", "refix-prep", n="1")["go"], False)
        for script, nid, extra in (("refix_accept", "refix-accept", {"iteration": "1", "n": "1"}),
                                   ("review2_accept", "review2-accept", {}),
                                   ("refix_accept", "refix2-accept", {"iteration": "1", "n": "2"})):
            out = self._run(script, nid, reply="null", **extra)
            self.assertEqual((out["ok"], out["done"]), (True, True), (nid, out))
        self.assertFalse(self._run("cut2", "cut2")["go"])
        self.assertFalse(self._run("refix_prep", "refix2-prep", n="2")["go"])
        self.assertFalse((self.place / "delta" / "review-2.json").exists())

    def test_declared_only_refix_skips_review2(self):
        """1 回目の手直しが全部の穴を declared で答えて受けられたら、fixed が無いので cut2 は go: false で 2 回目の審査を回さない
        （元 review-loop.py:628 delta_review2_due。元の試験 works/tests/test_blk_refix.py:397）"""
        self._cut()
        self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))
        self.assertTrue(self._run("refix_prep", "refix-prep", n="1")["go"])
        declared = {"handled": [{"key": _RV_FACE, "handled": "declared",
                                 "how": "docstring の定義は呼び手の文書が持つので、ここでは足さずに残す"}]}
        ok = self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(declared, ensure_ascii=False), iteration="1")
        self.assertEqual((ok["ok"], ok["done"]), (True, True), ok)
        self.assertEqual(self._run("cut2", "cut2"), {"go": False, "files": [], "diff_file": "", "brief_file": ""})
        self.assertFalse((self.place / "loop-fix_delta2.json").exists())
        self.assertFalse((self.place / "review2-brief.json").exists())

    def test_both_cuts_leave_out_the_runtime_copy(self):
        """1 回目（delta-cut）と 2 回目（cut2）の差分の審査の支度は、実行基盤の写しの置き場（.archon/ の下）を差分に載せない。
        scripts が除くパスの頭（boundary.SKIP）を渡さないと、写した工程のファイルが審査役の差分に載る"""
        copy = self.repo / ".archon" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("name: copied\n", encoding="utf-8")
        p = self.repo / "stats.py"
        first = self._cut()
        self.assertEqual(first["files"], ["stats.py"], first)
        self.assertNotIn(".archon", pathlib.Path(first["diff_file"]).read_text(encoding="utf-8"))
        self.assertTrue(self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))["ok"])
        self.assertTrue(self._run("refix_prep", "refix-prep", n="1")["go"])
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        copy.unlink()   # 手直しの受け付けは run の始めの版から見た範囲の外の変更を拒むので、写しは受け付けの後に置き直す
        self.assertTrue(self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                                  iteration="1")["ok"])
        copy.write_text("name: copied again\n", encoding="utf-8")
        second = self._run("cut2", "cut2")
        self.assertEqual((second["go"], second["files"]), (True, ["stats.py"]), second)
        self.assertNotIn(".archon", pathlib.Path(second["diff_file"]).read_text(encoding="utf-8"))

    def test_second_refix_takes_a_real_reply_on_the_second_round(self):
        """2 回目の手直し（p3.delta_fix2）を本物の 2 周目で回す: 1 回目の審査・手直し（fixed）・2 回目の審査（塞がっていない検算と
        新しい穴）を受けた置き場で、refix2-prep が 2 回目の義務の指示書を書き、役の本物の返答を refix2-accept が照らす。義務の key に
        答えない返答は拒み、答えた返答を受けて置き場に 2 回目の手直しの返答を控える"""
        p = self.repo / "stats.py"
        self._cut()
        self.assertTrue(self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))["ok"])
        self.assertTrue(self._run("refix_prep", "refix-prep", n="1")["go"])
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        self.assertTrue(self._run("refix_accept", "refix-accept", n="1", reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                                  iteration="1")["ok"])
        cut2 = self._run("cut2", "cut2")
        self.assertEqual((cut2["go"], cut2["files"]), (True, ["stats.py"]), cut2)
        face2 = "stats.py mean: docstring が空の並びの扱いを書いていない"
        review2 = {"faces": [{"key": face2, "kind": "contract_drift", "where": "stats.py", "cite": '"""算術平均"""',
                              "why": "空の並びで 0 で割るのに docstring が平均の定義しか書かず、呼び手が空を渡してよいと読む"}],
                   "checks": [{"key": _RV_FACE, "closed": False, "why": "docstring は足したが平均の定義を書いておらず、穴が残る"}]}
        acc2 = self._run("review2_accept", "review2-accept", reply=json.dumps(review2, ensure_ascii=False))
        self.assertEqual((acc2["ok"], acc2["done"]), (True, True), acc2)
        self.assertEqual(json.loads((self.place / "delta" / "review-2.json").read_text(encoding="utf-8"))["pass"], False)
        prep = self._run("refix_prep", "refix2-prep", n="2")
        self.assertEqual((prep["go"], prep["iteration"]), (True, 1), prep)
        self.assertIn(str(self.place / "refix2-brief.json"), pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8"))
        owed = json.loads((self.place / "refix2-brief.json").read_text(encoding="utf-8"))["owed"]
        self.assertEqual(sorted(r["key"] for r in owed), sorted([face2, _RV_FACE]))
        p.write_text(p.read_text(encoding="utf-8").replace('"""算術平均"""', '"""算術平均（空の並びは渡さない）"""'),
                     encoding="utf-8")
        handled = {"handled": [{"key": face2, "handled": "fixed", "how": "docstring に空の並びを渡さない約束を書いた",
                                "files": ["stats.py"]},
                               {"key": _RV_FACE, "handled": "fixed", "how": "docstring に算術平均の定義を書いた",
                                "files": ["stats.py"]}]}
        half = {"handled": handled["handled"][:1]}
        bad = self._run("refix_accept", "refix2-accept", n="2", reply=json.dumps(half, ensure_ascii=False), iteration="1")
        self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
        self.assertIn("応答が無い", pathlib.Path(bad["reason_file"]).read_text(encoding="utf-8"))
        again = self._run("refix_prep", "refix2-prep", n="2")
        self.assertEqual(again["iteration"], 2)
        self.assertIn(bad["reason_file"], pathlib.Path(again["prompt_file"]).read_text(encoding="utf-8"))
        ok = self._run("refix_accept", "refix2-accept", n="2", reply=json.dumps(handled, ensure_ascii=False), iteration="2")
        self.assertEqual((ok["ok"], ok["done"]), (True, True), ok)
        import fixboard
        import refix
        got = fixboard.output(self.place, refix.passes()[2]["fix"])
        self.assertEqual([r["key"] for r in got["handled"]], [face2, _RV_FACE])
    def test_refix_rounds_share_one_script(self):
        """1 回目と 2 回目の手直しの支度と受け付けは、同じ script を with: {n: 1|2} で呼ぶ（節の id は変えない）"""
        for nid, script, n in (("refix-prep", "refix_prep", 1), ("refix2-prep", "refix_prep", 2),
                               ("refix-accept", "refix_accept", 1), ("refix2-accept", "refix_accept", 2)):
            with self.subTest(nid):
                node = _rv_node(nid)
                self.assertEqual((node["script"], node["with"]["n"]), (script, n))
        self.assertEqual(sorted(p.name for p in (BLOCK / "scripts").glob("refix*")), ["refix_accept.py", "refix_prep.py"])

    def test_refix_texts_are_unchanged_for_both_rounds(self):
        """n から組む字（起こさなかった時の理由・止まりの文の頭・拒否の控えの名）が、2 つの script だった時の字と同じ"""
        for n, prep, accept in ((1, "refix-prep", "refix-accept"), (2, "refix2-prep", "refix2-accept")):
            with self.subTest(n=n):
                out = self._run("refix_accept", accept, n=str(n), reply="null", iteration="1")
                self.assertEqual(out["reason"], f"手直しの役を起こさなかった（{n} 回目の審査が直す義務を出していない・審査を受けていない）")
                self._json(f"rejects-{accept}.json", [{"at": "2026-10-12T00:00:00+00:00", "reason": "前の拒否"}])
                self.assertEqual(self._run("refix_prep", prep, n=str(n))["iteration"], 2)
                env = hermetic.child_env()
                for script, name, extra in (("refix_prep", prep, {}), ("refix_accept", accept, {"INPUTS_REPLY": "{}",
                                                                                                "INPUTS_ITERATION": "1"})):
                    done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{script}.py")], cwd=self.repo,
                                          env={**env, "INPUTS_N": str(n), **extra}, capture_output=True, text=True,
                                          encoding="utf-8")
                    self.assertNotEqual(done.returncode, 0)
                    self.assertTrue(done.stderr.startswith(f"{name}: KeyError: "), done.stderr)
        bad = subprocess.run([sys.executable, str(BLOCK / "scripts" / "refix_prep.py")], cwd=self.repo,
                             env=hermetic.child_env(INPUTS_N="3"), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual((bad.returncode, bad.stderr), (1, "refix_prep: 入力 n は 1 か 2: '3'\n"))

    def test_lens_prep_without_the_role_definition_is_go_false(self):
        """利用者が silent-failure-hunter の役の定義を入れていなければ go: false で、理由を lens.json の行に残す。集めは
        起こさなかった行を残し、審査役の材料の lens の欄に載せる"""
        out = self._cut()
        got = self._run("lens_prep", "lens-prep")
        self.assertEqual(got, {"go": False, "prompt_file": ""})
        rows = json.loads((self.place / "lens.json").read_text(encoding="utf-8"))["rows"]
        self.assertEqual(rows[0]["state"], "not_routed")
        self.assertIn("定義が役の設定に無い", rows[0]["reason"])
        col = self._run("lens_collect", "lens-collect", reply="null")
        self.assertEqual(col, {"state": "not_routed", "count": 0})
        brief = json.loads(pathlib.Path(out["brief_file"]).read_text(encoding="utf-8"))
        self.assertEqual(brief["lens"][0]["state"], "not_routed")

    def test_lens_prep_with_the_role_definition_and_collect(self):
        self._cut()
        agents = self.tmp / "toolkit" / "agents"
        agents.mkdir(parents=True)
        (agents / "silent-failure-hunter.md").write_text("---\nname: x\n---\n黙って失敗する所を探す役。\n", encoding="utf-8")
        got = self._run("lens_prep", "lens-prep", env={"PR_REVIEW_TOOLKIT_ROOT": str(self.tmp / "toolkit")})
        self.assertTrue(got["go"], got)
        self.assertIn("黙って失敗する所を探す役。", pathlib.Path(got["prompt_file"]).read_text(encoding="utf-8"))
        reply = {"findings": [{"where": "stats.py", "cite": "return sum(xs)", "why": "空の並びで 0 で割って落ちるが呼び手は気づけない"}]}
        col = self._run("lens_collect", "lens-collect", reply=json.dumps(reply, ensure_ascii=False))
        self.assertEqual(col, {"state": "ran", "count": 1})
        brief = json.loads((self.place / "review1-brief.json").read_text(encoding="utf-8"))
        self.assertEqual(brief["lens"][0]["findings"][0]["where"], "stats.py")

    def test_a_failed_lens_leaves_a_failed_row_and_the_collector_goes_on(self):
        """F327: 中継の節はレンズの返りをそのまま返す。レンズが落ちて中継が飛んだ run（返り null）でも、集め役は起こしたレンズを
        理由つきの failed の行に残し、審査役の材料に載せ、集め役の事実は ok: true で済む"""
        out = self._cut()
        agents = self.tmp / "toolkit" / "agents"
        agents.mkdir(parents=True)
        (agents / "silent-failure-hunter.md").write_text("---\nname: x\n---\n黙って失敗する所を探す役。\n", encoding="utf-8")
        self.assertTrue(self._run("lens_prep", "lens-prep", env={"PR_REVIEW_TOOLKIT_ROOT": str(self.tmp / "toolkit")})["go"])
        reply = {"findings": [], "findings_none": "差分を読んだ"}
        self.assertEqual(self._run("lens_reply", "lens-reply", reply=json.dumps(reply, ensure_ascii=False)), reply)
        self.assertEqual(self._run("lens_collect", "lens-collect", reply="null"), {"state": "failed", "count": 0})
        row = json.loads((self.place / "lens.json").read_text(encoding="utf-8"))["rows"][0]
        self.assertIn("出口が無い", row["reason"])
        brief = json.loads(pathlib.Path(out["brief_file"]).read_text(encoding="utf-8"))
        self.assertEqual(brief["lens"][0]["state"], "failed")
        self.assertEqual(json.loads((self.place / "lenses.json").read_text(encoding="utf-8"))["collector"], {"ok": True, "reason": ""})

    def test_lens_collect_failure_is_reported_not_silent(self):
        """レンズの集め役（lens-collect）が落ちた・ok でない事実を、止まった run の報告に知らせる: diff の隣の lenses.json に
        {collector: {ok: false, reason}} で載せる。集め役が自分の誤りで落ちれば集め役が書き、何も書かずに落ちた・走らなかった時は
        返す節が書く（lib が読めない道でも）。集めが済めば ok: true、審査を回さない run も ok: true と訳。書けなければ名指す
        （集め役は非 0 で落ち、run を止める。元 works/blk-lens/scripts/exit.py の lenses.exit_ も盤面を止めた）"""
        lenses = self.place / "lenses.json"

        def collector():
            return json.loads(lenses.read_text(encoding="utf-8"))["collector"]

        def raw(script, nid, cwd_script=None, **inputs):
            env = {k: v for k, v in hermetic.child_env().items() if not k.startswith("PR_REVIEW_TOOLKIT")}
            env.update({"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": "run-delta", "PYTHONDONTWRITEBYTECODE": "1",
                        "ARCHON_NODE_EXECUTION": json.dumps({"path": f"fix__{nid}"}), "WORKS_FACTORY_ROOT": str(ROOT),
                        "CLAUDE_CONFIG_DIR": str(self.cfg)})
            env.update({f"INPUTS_{k.upper()}": v for k, v in inputs.items()})
            return subprocess.run([sys.executable, str(cwd_script or BLOCK / "scripts" / f"{script}.py")], cwd=self.repo,
                                  env=env, capture_output=True, text=True, encoding="utf-8")

        self._json("lenses.json", {"collector": {"ok": True, "reason": "前の試みの行"}})
        self._cut()
        self.assertFalse(lenses.exists(), "delta-cut が前の試みの印を消す")
        self._run("lens_prep", "lens-prep")
        (self.place / "lens.json").write_text("{壊れた", encoding="utf-8")
        done = raw("lens_collect", "lens-collect", reply="null")
        self.assertNotEqual(done.returncode, 0, done.stdout)
        got = collector()
        self.assertIs(got["ok"], False)
        self.assertIn("レンズの集め役が終わらなかった", got["reason"])
        self.assertIn("読めない", got["reason"])
        self._run("collect", "fix")
        self.assertEqual(collector(), got, "返す節は集め役が書いた事実をそのまま残す")
        with self.subTest("集め役が何も書かずに落ちた・走らなかった"):
            lenses.unlink()
            self._run("collect", "fix")
            got = collector()
            self.assertIs(got["ok"], False)
            self.assertIn("集め役の出口が無い", got["reason"])
        with self.subTest("lib も境の口も読めない返す節"):
            lenses.unlink()
            lone = self.tmp / "lone" / "fix" / "scripts" / "collect.py"
            lone.parent.mkdir(parents=True)
            lone.write_bytes((BLOCK / "scripts" / "collect.py").read_bytes())
            done = raw("collect", "fix", cwd_script=lone)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIs(collector()["ok"], False)
        with self.subTest("書けない"):
            lenses.unlink()
            lenses.mkdir()
            done = raw("collect", "fix")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn(f"lenses.json を書けない（{lenses}", done.stderr)
            lenses.rmdir()
        with self.subTest("集めが済んだ"):
            self._run("lens_prep", "lens-prep")
            self.assertEqual(self._run("lens_collect", "lens-collect", reply="null")["state"], "not_routed")
            self.assertEqual(collector(), {"ok": True, "reason": ""})
            self._run("collect", "fix")
            self.assertEqual(collector(), {"ok": True, "reason": ""})
        with self.subTest("審査を回さない run"):
            self._json("assert-changed.json", {"ok": False, "reason": "申告したファイルが変わっていない"})
            self.assertFalse(self._run("delta_cut", "delta-cut")["go"])
            self._run("collect", "fix")
            got = collector()
            self.assertIs(got["ok"], True)
            self.assertIn("レンズは起こさない", got["reason"])

    def test_collect_stdlib_copies_match_the_lib(self):
        """返す節 collect が lib を読めない道のために写して持つ名と文と置き場のパスは、lib の正本と同じ（one-source。写しのずれは赤）"""
        import importlib.util
        import fixboard

        def load(path, name):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        collect = load(BLOCK / "scripts" / "collect.py", "fix_collect")
        with mock.patch.object(sys, "path", [str(ROOT / "workflows" / ".shared"), *sys.path]):   # boundary は頭で skip_value を読む（単独で回しても落ちない）
            boundary = load(ROOT / "workflows" / ".shared" / "boundary.py", "boundary")
        self.assertEqual((collect.LENSES_FILE, collect.ALLOWED_TESTS, collect.ACCEPT_TRACE),
                         (fixboard.LENSES_FILE, fixboard.ALLOWED_TESTS_FILE, fixboard.ACCEPT_TRACE_FILE))
        self.assertEqual(collect.NO_COLLECTOR, fixboard.LENS_NOT_DONE.format(why=collect.NO_COLLECTOR.partition(": ")[2]))
        collect.boundary = boundary
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.art),
                                          "ARCHON_NODE_EXECUTION": json.dumps({"path": "refix__fix"})}):
            self.assertEqual(self.art / collect.place_rel(), boundary.place("fix"))

    def test_scripts_do_not_name_queues_or_take(self):
        for name in ("delta_cut", "delta_accept", "lens_prep", "lens_collect", "refix_prep", "refix_accept", "cut2",
                     "review2_accept"):
            text = (BLOCK / "scripts" / f"{name}.py").read_text(encoding="utf-8")
            self.assertIsNone(NO_QUEUE.search(text), name)
            self.assertNotIn("../", text, name)


# ---------------------------------------------------------------- script の振る舞い（prep・join・tdd_unit・collect・clean・assert_changed）

_BLK_RUN = "wf-blk"
_BLK_MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
              "path_changed")


def _blk_run(script, repo, art, inputs=None, node_path="fix__x", env_extra=None):
    """scripts/<script>.py を一時の対象のリポジトリ repo で起こす。(終了の値, 標準出力の JSON か None, 標準エラー)。
    env_extra は子の環境に足す"""
    env = hermetic.child_env()
    env.update({"ARTIFACTS_DIR": str(art), "WORKFLOW_ID": _BLK_RUN, "WORKS_FACTORY_ROOT": str(ROOT),
                "ARCHON_NODE_EXECUTION": json.dumps({"path": node_path}), "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(env_extra or {})
    env.update({f"INPUTS_{k.upper()}": v for k, v in (inputs or {}).items()})
    done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{script}.py")], cwd=repo, env=env,
                          capture_output=True, text=True, encoding="utf-8")
    try:
        out = json.loads(done.stdout)
    except ValueError:
        out = None
    return done.returncode, out, done.stderr


def _blk_write(path, doc):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def _blk_ptr(rel):
    return json.dumps({"type": "archon_artifact", "run_id": _BLK_RUN, "path": rel})


def _recorder_root(tmp):
    """記録の根を持つ隔離した設定の置き場（toolset.install が作る形）。(子の環境に足す物, 記録の根)"""
    import writelog
    cfg = pathlib.Path(tmp) / "claude-config"
    root = writelog.root(cfg)
    root.mkdir(parents=True)
    return {"CLAUDE_CONFIG_DIR": str(cfg)}, root


def _record(log, path, tool="Edit"):
    """記録のフックが書く形の 1 行を log に足す"""
    import hashlib
    log.parent.mkdir(parents=True, exist_ok=True)
    real = os.path.realpath(str(path))
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"tool_name": tool, "path": real,
                            "file_sha": hashlib.sha256(pathlib.Path(real).read_bytes()).hexdigest()}) + "\n")


def _blk_result(gid, units, end_tree, start_tree, **extra):
    doc = {"group_id": gid, "unit_ids": units, "end_tree": end_tree, "start_tree": start_tree,
           "units": [{"unit_id": k, "status": "fixed", "reason": ""} for k in units],
           "tdd": {"ran": False, "reason": "実行器が無い", "suite": "", "units": []}, "conflicts": [], "objection": "",
           "changed": {k: False for k in _BLK_MARKS}, "allowed_tests": [], "verified": []}
    doc.update(extra)
    return doc


class BlockScriptsCase(unittest.TestCase):
    """script を一時の対象のリポジトリと一時の置き場で起こし、標準出力の JSON を読む（fix.md の試験の script の振る舞い）"""

    @classmethod
    def setUpClass(cls):
        import leftovers
        cls.snapshot = staticmethod(leftovers.snapshot)
        cls.fmt = all_nodes(load())["fix"]["output_format"]

    def setUp(self):
        from tests.bin.gitkit import committed_copy
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-fix-scripts-"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, ROOT / "tests" / "e2e" / "target-seed")
        self.art = self.tmp / "art"
        self.place = self.art / "fix" / "fix"
        self.place.mkdir(parents=True)

    # ---- 助け
    def prep_inputs(self, *, cut=(), only=""):
        _blk_write(self.art / "in" / "start.json", {"tdd_suite": "", "features_cut": list(cut)})
        _blk_write(self.art / "in" / "judgment.json", {"units": [
            {"key": "A", "label": "block"}, {"key": "B", "label": "block"},
            {"key": "C", "label": "suggest", "disposition": "do-now"}, {"key": "D", "label": "suggest"}],
            "questions": []})
        _blk_write(self.art / "plan" / "r1" / "plan-fields.json", {"round": 1, "fields": [{}, {}]})
        _blk_write(self.art / "plan" / "r1" / "p2.fix_plan.json", {"plan": [{"unit_keys": ["A", "B"]}, {"unit_keys": ["C"]}]})
        return {"start": _blk_ptr("in/start.json"), "judgment": _blk_ptr("in/judgment.json"),
                "plan": _blk_ptr("plan/r1/plan-fields.json"), "units": "[]", "depth": "[]", "only_items": only,
                "baseline": "", "ripple": "", "answers": "null"}

    def restore(self):
        git(self.repo, "checkout", "-q", "--", ".")
        git(self.repo, "clean", "-qfd")

    def tree_with(self, files):
        """files を書いた作業ツリーの姿の木を取り、作業ツリーを元に戻す"""
        for name, text in files.items():
            (self.repo / name).write_text(text, encoding="utf-8")
        tree = self.snapshot(self.repo)
        self.restore()
        return tree

    def groups_file(self, groups, start_tree, par=True):
        out_dir = self.place / "groups"
        _blk_write(self.place / "groups.json", {"groups": groups, "count": len(groups), "par": par,
                                                "start_tree": start_tree, "out_dir": str(out_dir)})
        return out_dir

    def assert_contract(self, out):
        self.assertEqual(validate_schema(out, self.fmt), [], out)
        self.assertEqual(set(out), CONTRACT_FIELDS, "返す節は required に無い欄も全部返す")

    # ---- fix_reads.py
    def read_hook(self, cfg, path, session="s-1"):
        """隔離した設定の読んだ証拠のフック（bin/_lib/record-read.py を実物で起こす）に、役が path を Read した出来事を渡す"""
        import reads
        event = {"session_id": session, "tool_name": "Read", "tool_input": {"file_path": str(path)}, "tool_use_id": "toolu_read",
                 "cwd": str(self.repo), "hook_event_name": "PostToolUse"}
        done = subprocess.run([sys.executable, str(ROOT / "bin" / "_lib" / "record-read.py"), str(cfg / reads.ROOT)],
                              input=json.dumps(event), text=True, encoding="utf-8", capture_output=True, cwd=str(self.repo),
                              env=hermetic.child_env(PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_fix_reads_names_what_the_fixer_did_not_read(self):
        """F147: 修正役が指示書を読み、判定の写しを読まなかった置き場は、reads-fix.json で指示書が read・判定の写しが missing。
        記録は段の頭の印 fix-head.json を置いた時刻から後で切る。役を起こしていない段（裁定の後の修正役）は索引に null と訳。
        受け付けの条件にしない（ok: true）"""
        import reads
        cfg = self.tmp / "claude-config"
        (cfg / reads.ROOT).mkdir(parents=True)
        judgment = _blk_write(self.place / "judgment.json", {"units": [], "questions": []})
        head = _blk_write(self.place / "fix-head.json", {"tree": "t"})
        os.utime(head, (head.stat().st_mtime - 60,) * 2)
        prompt = self.place / "prompt-p3.fix.md"
        prompt.write_text("指示書\n", encoding="utf-8")
        self.read_hook(cfg, prompt)
        code, out, err = _blk_run("fix_reads", self.repo, self.art, {}, "fix__fix-reads", env_extra={"CLAUDE_CONFIG_DIR": str(cfg)})
        self.assertEqual(code, 0, err)
        self.assertEqual((out["ok"], out["missing"], out["reason"]), (True, [str(judgment)], ""), out)
        index = json.loads(pathlib.Path(out["index_file"]).read_text(encoding="utf-8"))
        self.assertIsNone(index["fix-ruled"])
        self.assertIn("fix-ruled", index["why"])
        doc = json.loads(pathlib.Path(index["fix"]).read_text(encoding="utf-8"))
        self.assertEqual([(r["path"], r["hook"] in reads.HOOK_SEEN) for r in doc["rows"]], [(str(prompt), True), (str(judgment), False)])

        os.utime(head, (head.stat().st_mtime + 120,) * 2)
        code, out, err = _blk_run("fix_reads", self.repo, self.art, {}, "fix__fix-reads", env_extra={"CLAUDE_CONFIG_DIR": str(cfg)})
        self.assertIn(str(prompt), out["missing"], "段の頭より前の読みは数えない")

    def test_fix_reads_without_the_record_says_why_and_does_not_fail(self):
        """記録の根が無い起動は、読んだかを測れない訳を残して ok: true（missing は空。読んでいないと取り違えない）"""
        import reads
        _blk_write(self.place / "judgment.json", {"units": [], "questions": []})
        _blk_write(self.place / "fix-head.json", {"tree": "t"})
        (self.place / "prompt-p3.fix.md").write_text("指示書\n", encoding="utf-8")
        code, out, err = _blk_run("fix_reads", self.repo, self.art, {}, "fix__fix-reads",
                                  env_extra={"CLAUDE_CONFIG_DIR": str(self.tmp / "no-config")})
        self.assertEqual((code, out["ok"], out["missing"]), (0, True, []), err)
        doc = json.loads(pathlib.Path(json.loads(pathlib.Path(out["index_file"]).read_text(encoding="utf-8"))["fix"])
                         .read_text(encoding="utf-8"))
        self.assertEqual(doc["sources"], {"hook": "none", "why": reads.NO_ROOT})

    # ---- route.py
    def test_route_returns_the_shape_of_the_mode(self):
        """route は入力 mode の語を fixboard.MODES で引いて形を返す"""
        fmt = all_nodes(load())["route"]["output_format"]
        for mode, group in (("", False), ("group", True)):
            code, out, err = _blk_run("route", self.repo, self.art, {"mode": mode}, "fix__route")
            self.assertEqual(code, 0, err)
            self.assertEqual(out, {"group": group})
            self.assertEqual(validate_schema(out, fmt), [], out)

    # ---- prep.py
    def test_prep_two_groups_run_side_by_side(self):
        subprocess.run(["git", "remote", "add", "origin", str(self.tmp / "origin.git")], cwd=self.repo, check=True, env=hermetic.child_env())
        code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(), "fix__prep")
        self.assertEqual(code, 0, err)
        self.assertEqual([(g["unit_ids"], g["items"]) for g in out["groups"]], [(["A", "B"], [1]), (["C"], [2])])
        self.assertTrue(out["par"])
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["out_dir"], str(self.place / "groups"))
        self.assertEqual(out["start_tree"], self.snapshot(self.repo))
        for name in ("r1/start.json", "judgment.json", "plan-fields.json", "p2.fix_plan.json", "fix-ignored-before.json",
                     "groups.json", "units.json", "only-items.json", "base-rev.json"):
            self.assertTrue((self.place / name).is_file(), name)
        self.assertEqual(json.loads((self.place / "groups.json").read_text(encoding="utf-8")), out)
        self.assertEqual((self.place / "r1" / "start.json").read_bytes(), (self.art / "in" / "start.json").read_bytes(),
                         "始めの記録は字のまま写す（欄を既定で埋めない。L-E24 の startrec.adopt）")

    def test_prep_writes_only_copies_the_children_adopt(self):
        """prep が置き場に書く入力の写しは、組の子が親から写す一覧 fixboard.ADOPTED に全部載る（載らない写しは子で黙って空になる）"""
        import fixboard
        import gatemarks
        import planmarks
        _blk_write(self.art / "in" / "ripple.json", [{"path": "stats.py"}])
        _blk_write(self.art / "in" / "baseline.json", {"cases": [], "exit": 0, "suite": "", "test_cmd": "", "rev": "HEAD"})
        inputs = self.prep_inputs()
        judgment_dir = self.art / json.loads(inputs["judgment"])["path"].rsplit("/", 1)[0]
        _blk_write(judgment_dir / gatemarks.BESIDE[0], {"rounds": {"1": []}})   # 判定の隣の結びと素材の状態
        _blk_write(judgment_dir / gatemarks.BESIDE[1], {"ci": {"status": "not_run"}})
        inputs = {**inputs, "ripple": _blk_ptr("in/ripple.json"), "baseline": _blk_ptr("in/baseline.json"),
                  "depth": '[{"unit_id": "A", "depth": "標準", "why": "x"}]',
                  "answers": '{"decision": "approve", "text": "stats.py の外は触らない"}', "units": '["A"]',
                  "only_items": '["1"]', "plan_review": _blk_ptr("in/review.json"), "notes": "## 直した項目 1 の事前審査の穴"}
        _blk_write(self.art / "in" / "review.json", {"faces": [], "shrink": []})
        code, out, err = _blk_run("prep", self.repo, self.art, inputs, "fix__prep")
        self.assertEqual(code, 0, err)
        written = {p.relative_to(self.place).as_posix() for p in self.place.rglob("*") if p.is_file()}
        own = {fixboard.GROUPS_FILE, "fix-ignored-before.json", fixboard.marks_path(self.place).name,
               fixboard.TRACE_FILE, planmarks.FIELDS_FILE}
        self.assertEqual(written - own, set(fixboard.ADOPTED))

    def test_prep_takes_the_gate_answers_into_the_duty(self):
        """修正前の関所で答えた問いの単位は直す義務に戻り、答えていない問いの単位は外れる（gatemarks.returned・withheld_by）。
        関所の一言と戻った単位の行は修正役と TDD の役が読む human-notes.md に載る"""
        import gatemarks
        fork = {"key": "q-fork", "kind": "fork", "status": "held", "origin": "B", "reason": "分母はどちらか"}
        held = {"key": "q-esc", "kind": "decision", "status": "escalate", "origin": "C", "reason": "人に上げる"}
        inputs = self.prep_inputs()
        _blk_write(self.art / "in" / "judgment.json", {"units": [
            {"key": "A", "label": "block"}, {"key": "B", "label": "block"},
            {"key": "C", "label": "suggest", "disposition": "do-now"}, {"key": "D", "label": "suggest"}],
            "questions": [fork, held]})
        answer = {"decision": "continue", "text": "分母は len(xs)", "asked": [gatemarks.ask_text(fork)]}
        code, out, err = _blk_run("prep", self.repo, self.art, {**inputs, "answers": json.dumps(answer, ensure_ascii=False)},
                                  "fix__prep")
        self.assertEqual(code, 0, err)
        self.assertEqual([g["unit_ids"] for g in out["groups"]], [["A", "B"]])
        notes = (self.place / "human-notes.md").read_text(encoding="utf-8")
        self.assertIn("分母は len(xs)", notes)
        self.assertIn("q-fork", notes)

    def test_prep_without_remote_runs_in_order(self):
        """子ごとの作業ツリーは remote の既定の枝から切られる（U8 の実測: remote の無いリポジトリでは子を 1 つも起こせない）"""
        code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(), "fix__prep")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["count"], 2)
        self.assertFalse(out["par"])

    def test_prep_lane_switch_off_runs_in_order(self):
        code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(cut=["fix_lanes"]), "fix__prep")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["count"], 2)
        self.assertFalse(out["par"])

    def test_prep_only_items_keeps_their_units(self):
        code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(only='["2"]'), "fix__prep")
        self.assertEqual(code, 0, err)
        self.assertEqual([g["unit_ids"] for g in out["groups"]], [["C"]])
        self.assertFalse(out["par"])

    def test_prep_under_refix_writes_its_own_place(self):
        _blk_write(self.place / "groups.json", {"mark": "first"})
        code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(only='["1"]'), "refix__prep")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["out_dir"], str(self.art / "fix" / "refix" / "groups"))
        self.assertTrue((self.art / "fix" / "refix" / "groups.json").is_file())
        self.assertEqual(json.loads((self.place / "groups.json").read_text(encoding="utf-8")), {"mark": "first"})

    def test_group_children_find_the_line_place_from_preps_out_dir(self):
        """#504: 組の子の run は prep が返す out_dir から、メイングラフの run の置き場（boundary.line_place。利用者の HOME・XDG の印と
        試験の使い回しの置き場）を辿る。prep の書く形と辿る形が離れれば、ここで落ちる"""
        import importlib.util
        with mock.patch.object(sys, "path", [str(ROOT / "workflows" / ".shared"), *sys.path]):
            spec = importlib.util.spec_from_file_location("boundary", ROOT / "workflows" / ".shared" / "boundary.py")
            boundary = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(boundary)
        for execution in ("fix__prep", "refix__prep"):
            with self.subTest(execution):
                code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(only='["1"]'), execution)
                self.assertEqual(code, 0, err)
                with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.tmp / "child-run"), "INPUTS_OUT_DIR": out["out_dir"]}):
                    self.assertEqual(boundary.line_place(), self.art)

    def test_refix_place_reads_the_first_pass_rulings(self):
        """F216・L-W18・L-W48: 2 度目の修正（include refix-run）の prep は入力 prior_conflicts の先（1 回目の置き場）の申し出と裁定を
        写し、直す項目の待つ行を案を直した行にする（conflict.second_pass が真。裁定 fix_test_scope の範囲と直した項目の単位の許しが
        立つ）。この段で新しく fix_plan_item と裁いた行には「最後の人の関所で決める」の約束が出て、段を抜ける返す節 collect が諦めた
        行にする（CLOSE_WHY。案の段に戻るのは 1 run に 1 回）。replan_items はこの段の項目だけ。1 回目の置き場は書き換えない"""
        import conflict
        import replan
        body = {"between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "テストと依頼が食い違う",
                "which_is_right": "request", "kind": "unnamed_test_broke", "round": 1, "source": "fix", "status": "ruled"}
        scope = {**body, "id": "c1-1", "unit_key": "A",
                 "ruling": {"decision": "fix_test_scope", "text": "テストを直してよい", "limits": ["test_stats.py"], "by": "ruler"}}
        waiting = {**body, "id": "c1-2", "unit_key": "B", "replan": "waiting",
                   "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "by": "ruler",
                              "plan_items": [1], "plan_units": ["A", "B"]}}
        _blk_write(self.place / "conflicts.json", {"items": [scope, waiting]})
        inputs = {**self.prep_inputs(only='["1"]'), "prior_conflicts": _blk_ptr("fix/fix/conflicts.json")}
        code, out, err = _blk_run("prep", self.repo, self.art, inputs, "refix-run__prep")
        self.assertEqual(code, 0, err)
        second = self.art / "fix" / "refix-run"
        rows = conflict.items(second)
        self.assertEqual([(r["id"], r.get(conflict.PRIOR)) for r in rows], [("c1-1", True), ("c1-2", True)])
        self.assertEqual(conflict.replan_state(rows[1]), conflict.AMENDED)
        self.assertTrue(conflict.second_pass(second))
        self.assertFalse(conflict.second_pass(self.place), "1 回目の置き場は書き換えない")
        permits = {p["id"] for p in conflict.test_permits(second)}
        self.assertLessEqual({f"{conflict.RULED_TEST_ID}-c1-1", f"{conflict.AMENDED_TEST_ID}-c1-2"}, permits)
        new = conflict.park(second, [{"unit_key": "C", "between": ["stats.py:9", "test_stats.py:8"],
                                      "why_both_cannot_hold": "直した案の項目 2 も判定と食い違う", "which_is_right": "request",
                                      "kind": "brief_vs_judgment"}], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(second, {new[0]: {"decision": "fix_plan_item", "text": "項目 2 も誤り", "limits": [],
                                                 "plan_items": [2], "plan_units": ["C"]}}, by="ruler")
        self.assertIn(conflict.LATE_REPLAN_PROMISE, (second / conflict.RULINGS_FILE).read_text(encoding="utf-8"))
        _blk_write(second / "join.json", {"par": False, "groups": [
            {"group_id": g["group_id"], "unit_ids": g["unit_ids"], "returned": True, "reason": ""} for g in out["groups"]],
            "units": [{"unit_id": k, "group_id": g["group_id"], "status": "fixed", "reason": ""} for g in out["groups"] for k in g["unit_ids"]]})
        _blk_write(second / "assert-changed.json", {"ok": True, "reason": ""})
        _blk_write(second / "delta" / "skipped.json", {"reason": "全部の単位が軽量"})
        code, got, err = _blk_run("collect", self.repo, self.art, node_path="refix-run__fix")
        self.assertEqual(code, 0, err)
        self.assert_contract(got)
        self.assertEqual((got["replan_items"], got["conflicts"]["path"]), (["2"], "fix/refix-run/conflicts.json"))
        last = conflict.items(second)[-1]
        self.assertEqual((conflict.replan_state(last), last[conflict.REPLAN_WHY]), (conflict.GAVE_UP, replan.CLOSE_WHY))
        self.assertEqual([r["id"] for r in conflict.asked(second)], [last["id"]])

    def test_prep_pastes_the_machine_notes(self):
        """P144・L-D35: 入力 notes（2 度目の修正に線が渡す機械の申し送り）は修正役と TDD の役の notes_file（human-notes.md）に載る"""
        notes = "## 直した項目 1（単位 A）の事前審査の穴\n\n- [contract_drift] 穴-分母（stats.py）: 空の列"
        code, out, err = _blk_run("prep", self.repo, self.art, {**self.prep_inputs(), "notes": notes}, "fix__prep")
        self.assertEqual(code, 0, err)
        self.assertIn(notes, (self.place / "human-notes.md").read_text(encoding="utf-8"))

    def test_prep_starts_an_empty_log_when_recorder_root_exists(self):
        import shutil

        import writelog
        env, root = _recorder_root(self.tmp)
        log = writelog.log_path(root, self.repo)
        code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(), "fix__prep", env_extra=env)
        self.assertEqual(code, 0, err)
        self.assertEqual(log.read_text(encoding="utf-8"), "")
        _record(log, self.repo / "stats.py")
        code, out, err = _blk_run("prep", self.repo, self.art, self.prep_inputs(), "fix__prep", env_extra=env)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(log.read_text(encoding="utf-8").splitlines()), 1, "在る記録は空にしない")
        self.assertEqual((log.parent / writelog.WHERE).read_text(encoding="utf-8"), os.path.realpath(self.repo),
                         "作業の場の控えが無いと、作業の場が消えても起動の片付け（writelog.sweep）が残す")
        shutil.rmtree(self.repo)
        self.assertEqual(writelog.sweep(root), ([log.parent], []))

    def test_join_carries_child_records_to_parent(self):
        """並べた子の記録（子の作業ツリーのパス）を、子の差分を当てた親の作業ツリーの記録へ写す。記録の無い子の変更は写さない"""
        import writelog
        import writes
        env, root = _recorder_root(self.tmp)
        parent_log = writelog.log_path(root, self.repo)
        parent_log.parent.mkdir()
        parent_log.write_text("", encoding="utf-8")
        start = self.snapshot(self.repo)
        fixed = (self.repo / "stats.py").read_text(encoding="utf-8").replace("len(xs) - 1", "len(xs)")
        t1 = self.tree_with({"stats.py": fixed})
        t2 = self.tree_with({"extra.py": "X = 1\n"})
        child = self.tmp / "child-g1"
        child.mkdir()
        (child / "stats.py").write_text(fixed, encoding="utf-8")
        child_log = writelog.log_path(root, child)
        _record(child_log, child / "stats.py")
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start, worktree=str(child)))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start, worktree=""))
        code, out, err = _blk_run("join", self.repo, self.art, env_extra=env)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 2})
        rows = [json.loads(ln) for ln in parent_log.read_text(encoding="utf-8").splitlines()]
        carried = [r for r in rows if r["tool_name"] == writes.CARRY_TOOL]
        self.assertEqual([(r["path"], r["from"]) for r in carried],
                         [(os.path.realpath(self.repo / "stats.py"), os.path.realpath(child / "stats.py"))])
        self.assertEqual(writes.unrecorded(self.repo, ["stats.py", "extra.py"], parent_log), ["extra.py"])

    # ---- join.py
    def test_join_applies_both_groups_in_order(self):
        start = self.snapshot(self.repo)
        t1 = self.tree_with({"stats.py": (self.repo / "stats.py").read_text(encoding="utf-8").replace("len(xs) - 1", "len(xs)")})
        t2 = self.tree_with({"extra.py": "X = 1\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 2})
        self.assertIn("/ (len(xs))\n", (self.repo / "stats.py").read_text(encoding="utf-8"))
        self.assertTrue((self.repo / "extra.py").is_file())
        joined = json.loads((self.place / "join.json").read_text(encoding="utf-8"))
        self.assertEqual([u["status"] for u in joined["units"]], ["fixed", "fixed"])

    def test_join_keeps_first_when_second_clashes(self):
        start = self.snapshot(self.repo)
        src = (self.repo / "stats.py").read_text(encoding="utf-8")
        t1 = self.tree_with({"stats.py": src.replace("len(xs) - 1", "len(xs)")})
        t2 = self.tree_with({"stats.py": src.replace("len(xs) - 1", "max(len(xs), 1)")})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        self.assertIn("/ (len(xs))\n", (self.repo / "stats.py").read_text(encoding="utf-8"))
        joined = json.loads((self.place / "join.json").read_text(encoding="utf-8"))
        g2 = joined["groups"][1]
        self.assertFalse(g2["returned"])
        self.assertIn("当たらない", g2["reason"])
        self.assertEqual(joined["units"][1], {"unit_id": "B", "group_id": "g2", "status": "not_done", "reason": g2["reason"]})
        row, = json.loads((self.place / "clash.json").read_text(encoding="utf-8"))["clashes"]
        self.assertEqual((row["group_id"], row["kind"], row["state"], row["names"]), ("g2", "text", "pending", ["stats.py"]),
                         "字で当たらない組も合わせのループの直し待ちに控える")

    def test_join_stops_on_a_group_without_a_readable_result(self):
        """#576: 結果のファイルが無いか読めない組が在れば、並べない run でも並べた run でも作業ツリーを変えず join.json も書かずに
        1 で止まる（済んだ子の変更を戻して持ち越しにしない）"""
        start = self.snapshot(self.repo)
        src = (self.repo / "stats.py").read_text(encoding="utf-8")
        (self.repo / "stats.py").write_text(src.replace("len(xs) - 1", "len(xs)"), encoding="utf-8")
        t1 = self.snapshot(self.repo)
        for par, broken in ((False, None), (False, {"group_id": "g2"}), (True, None)):
            with self.subTest(par=par, broken=broken):
                out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []},
                                            {"group_id": "g2", "unit_ids": ["B"], "items": []}], start, par=par)
                _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
                _blk_write(out_dir / "g2" / "group-start.json", {"start_tree": t1})
                (out_dir / "g2" / "result.json").unlink(missing_ok=True)
                if broken is not None:
                    _blk_write(out_dir / "g2" / "result.json", broken)
                code, out, err = _blk_run("join", self.repo, self.art)
                self.assertEqual(code, 1, err)
                self.assertIn("g2", err)
                self.assertNotIn("g1", err)
                self.assertEqual(self.snapshot(self.repo), t1)
                self.assertFalse((self.place / "join.json").exists())

    def rerun_seed(self, files, *, test_cmd=""):
        """走らせ直しの種: files を commit し、実行器（lib/tests/test_blk_fix_tdd.py の SUITE）を指す始めの記録と、その実行器で
        取った直す前の結末を置き場に置く。返りは始めの木"""
        import baseline_red
        from lib.tests.test_blk_fix_tdd import SUITE
        for name, text in files.items():
            (self.repo / name).write_text(text, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "走らせ直しの種")
        suite = self.tmp / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        _blk_write(self.place / "r1" / "start.json", {"tdd_suite": str(suite), "test_cmd": test_cmd, "features_cut": []})
        cases, code, why = baseline_red.run_suite(str(suite), self.repo, self.tmp, "base")
        self.assertIsNotNone(cases, why)
        _blk_write(self.place / "baseline.json", {"cases": cases, "exit": code})
        return self.snapshot(self.repo)

    def test_join_reruns_fixer_only_group_against_the_earlier_group(self):
        """F411: TDD の名指しの無い組（修正役だけが直した組 g2）も親の木で走らせ直す。前に戻した組 g1 が赤 → 緑を確かめた名指しを
        g2 が赤にすれば、g2 だけを戻して returned: false（元 works/blk-fix/lib/tddlanes.py:688 _green_after は当てた全部の単位の
        名指しを走らせた）"""
        start = self.rerun_seed({
            "e.py": "LIMIT = 10\n",
            "a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT + 1)\n",
            "test_a.py": "import unittest\n\nfrom a import cap\n\n\nclass TestA(unittest.TestCase):\n"
                         "    def test_cap(self):\n        self.assertEqual(cap(15), 10)\n"})
        t1 = self.tree_with({"a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT)\n"})
        t2 = self.tree_with({"e.py": "LIMIT = 20\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start, verified=["test_a.py::TestA::test_cap"]))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        g1, g2 = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"]
        self.assertTrue(g1["returned"], g1)
        self.assertFalse(g2["returned"])
        self.assertIn("test_cap", g2["reason"])
        self.assertEqual((self.repo / "e.py").read_text(encoding="utf-8"), "LIMIT = 10\n", "後の組の直しは戻す")
        self.assertIn("min(x, LIMIT)\n", (self.repo / "a.py").read_text(encoding="utf-8"), "前の組の直しは残す")

    def test_join_does_not_carry_a_backed_out_groups_named_tests(self):
        """F411 (1): 戻した組（g2）が赤 → 緑を確かめた名指しは、後の組（g3）の走らせ直しに持ち越さない（g2 の直しは親の木に無いので
        その名指しは赤のまま。持ち越すと関わりの無い g3 まで戻る）"""
        start = self.rerun_seed({
            "e.py": "LIMIT = 10\n",
            "a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT + 1)\n",
            "test_a.py": "import unittest\n\nfrom a import cap\n\n\nclass TestA(unittest.TestCase):\n"
                         "    def test_cap(self):\n        self.assertEqual(cap(15), 10)\n",
            "b.py": "def double(x):\n    return x * 2 + 1\n",
            "test_b.py": "import unittest\n\nfrom b import double\n\n\nclass TestB(unittest.TestCase):\n"
                         "    def test_double(self):\n        self.assertEqual(double(2), 4)\n",
            "c.py": "C = 1\n"})
        t1 = self.tree_with({"a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT)\n"})
        t2 = self.tree_with({"e.py": "LIMIT = 20\n", "b.py": "def double(x):\n    return x * 2\n"})
        t3 = self.tree_with({"c.py": "C = 2\n"})
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": [n]}
                                    for n, (g, k) in enumerate((("g1", "A"), ("g2", "B"), ("g3", "C")), 1)], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start, verified=["test_a.py::TestA::test_cap"]))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start,
                                                               verified=["test_b.py::TestB::test_double"]))
        _blk_write(out_dir / "g3" / "result.json", _blk_result("g3", ["C"], t3, start))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        rows = {g["group_id"]: g for g in json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"]}
        self.assertEqual({k: g["returned"] for k, g in rows.items()}, {"g1": True, "g2": False, "g3": True}, rows)
        self.assertIn("test_cap", rows["g2"]["reason"])
        self.assertEqual((self.repo / "c.py").read_text(encoding="utf-8"), "C = 2\n", "関わりの無い後の組の直しは親の木に残る")

    def test_join_backs_out_the_later_group_on_a_semantic_clash(self):
        """F412: 2 つの組が同じファイル e.py を違う行で変え、字では合うが、後の組 g2 の直しが前の組 g1 の変えた定数を当てにして
        いて親の木で g2 の名指しが赤: 後の組だけを意味の食い違いとして戻す（元 works/tests/test_tdd_lanes.py:828
        test_semantic_clash_backs_out_only_the_later_lane の写し）"""
        filler = "".join(f"# {i}\n" for i in range(10))
        start = self.rerun_seed({
            "e.py": f"E1 = 1\n{filler}E8 = 8\n",
            "b.py": "def triple(x):\n    return x * 3 + 1\n",
            "test_b.py": "import unittest\n\nfrom b import triple\n\n\nclass TestB(unittest.TestCase):\n"
                         "    def test_triple(self):\n        self.assertEqual(triple(2), 6)\n"})
        t1 = self.tree_with({"e.py": f"E1 = 10\n{filler}E8 = 8\n"})
        t2 = self.tree_with({"e.py": f"E1 = 1\n{filler}E8 = 80\n",
                             "b.py": "from e import E1\n\n\ndef triple(x):\n    return x * 3 + E1 - 1\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start, verified=["test_b.py::TestB::test_triple"]))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        g1, g2 = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"]
        self.assertTrue(g1["returned"], g1)
        self.assertFalse(g2["returned"])
        self.assertIn("意味の食い違い", g2["reason"])
        self.assertIn("e.py", g2["reason"])
        self.assertIn("test_triple", g2["reason"])
        self.assertNotIn("backed_out", g1, "当てたままの組は印を持たない")
        self.assertEqual(sorted(g2["backed_out"]), ["b.py", "e.py"], "#383 の 8: 当ててから赤で戻した組は戻したパスを名指す")
        e = (self.repo / "e.py").read_text(encoding="utf-8")
        self.assertIn("E1 = 10\n", e, "前の組は残す")
        self.assertIn("E8 = 8\n", e, "後の組の直しは戻す")
        self.assertEqual((self.repo / "b.py").read_text(encoding="utf-8"), "def triple(x):\n    return x * 3 + 1\n")
        import clash
        [row] = clash.load(self.place)
        self.assertEqual((row["group_id"], row["unit_ids"], row["state"]), ("g2", ["B"], clash.PENDING),
                         "#382: 赤で戻した組は合わせのループの直し待ちに控える")
        self.assertEqual((sorted(row["names"]), row["shared"], row["why"]), (["b.py", "e.py"], ["e.py"], g2["reason"]))
        self.assertEqual(pathlib.Path(row["patch"]), self.place / "join" / "g2.diff")

    def test_join_does_not_record_a_group_whose_recheck_raised(self):
        """#382: 確かめ直しそのものが落ちた組（fixboard.CHECK_RAISED）は戻すが、合わせのループの直し待ちには控えない（組を当てて赤では
        ない）"""
        filler = "".join(f"# {i}\n" for i in range(10))
        start = self.rerun_seed({"e.py": f"E1 = 1\n{filler}E8 = 8\n"})
        t1 = self.tree_with({"e.py": f"E1 = 10\n{filler}E8 = 8\n"})
        t2 = self.tree_with({"e.py": f"E1 = 1\n{filler}E8 = 80\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start, tdd={
            "ran": True, "units": [{"tests": 5, "test_files": ["e.py"]}]}))   # 名指しの並びが壊れていて照らしが落ちる
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        g2 = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"][1]
        self.assertIn("当てた後の確かめ直しが落ちた", g2["reason"])
        self.assertFalse((self.place / "clash.json").exists())

    @unittest.skipIf(os.geteuid() == 0, "root は書けないフォルダの中も書ける")
    def test_join_keeps_a_group_it_could_not_restore_and_stops_applying(self):
        """#403: 確かめ直しが赤の組 g1 の差分を戻せない（走らせ直しの試験が pkg/ を書けなくする）と、g1 を当てていないと言わず、
        当たったままのパスを unrestored に名指して止めの文を置き、作業ツリーが信用できないので後の組 g2 は当てない"""
        (self.repo / "pkg").mkdir()
        self.addCleanup(os.chmod, self.repo / "pkg", 0o755)
        start = self.rerun_seed({
            "pkg/__init__.py": "",
            "pkg/m.py": "V = 1\n",
            "c.py": "C = 1\n",
            "test_m.py": "import os\nimport unittest\n\nfrom pkg.m import V\n\n\nclass TestM(unittest.TestCase):\n"
                         "    def test_v(self):\n        if V == 2:\n            os.chmod('pkg', 0o555)\n        self.assertEqual(V, 3)\n"})
        t1 = self.tree_with({"pkg/m.py": "V = 2\n"})
        t2 = self.tree_with({"c.py": "C = 2\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start, verified=["test_m.py::TestM::test_v"]))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start))
        code, out, err = _blk_run("join", self.repo, self.art)
        os.chmod(self.repo / "pkg", 0o755)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 0})
        g1, g2 = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"]
        self.assertEqual(g1["unrestored"], ["pkg/m.py"], g1)
        self.assertNotIn("backed_out", g1)
        self.assertIn(fixboard.UNRESTORED_HEAD, g1["reason"])
        self.assertNotIn("当てられない", g1["reason"])
        self.assertEqual((self.repo / "pkg" / "m.py").read_text(encoding="utf-8"), "V = 2\n", "差分は当たったまま")
        self.assertFalse(g2["returned"])
        self.assertEqual(g2["reason"], fixboard.AFTER_UNRESTORED.format(group="g1"))
        self.assertEqual((self.repo / "c.py").read_text(encoding="utf-8"), "C = 1\n", "後の組は当てない")
        self.assertEqual(fixboard.held(self.place), fixboard.HELD.format(groups="g1"))

    @unittest.skipIf(os.geteuid() == 0, "root は書けないフォルダの中も書ける")
    def test_join_that_fails_after_an_unrestored_group_still_leaves_it_held(self):
        """#403: 戻せない組 g1 の後で join 自身が落ちても（戻せた組 g0 の TDD の輪の状態を写せない）、当たったままの組を join.json に
        先に書いてあるので、後の節は held と読み、返す節は止めの語 stopby.UNRESTORED で人に回す"""
        import stopby
        (self.repo / "pkg").mkdir()
        self.addCleanup(os.chmod, self.repo / "pkg", 0o755)
        start = self.rerun_seed({
            "pkg/__init__.py": "",
            "pkg/m.py": "V = 1\n",
            "c.py": "C = 1\n",
            "test_m.py": "import os\nimport unittest\n\nfrom pkg.m import V\n\n\nclass TestM(unittest.TestCase):\n"
                         "    def test_v(self):\n        if V == 2:\n            os.chmod('pkg', 0o555)\n        self.assertEqual(V, 3)\n"})
        t0 = self.tree_with({"c.py": "C = 2\n"})
        t1 = self.tree_with({"pkg/m.py": "V = 2\n"})
        out_dir = self.groups_file([{"group_id": "g0", "unit_ids": ["B"], "items": [2]},
                                    {"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start)
        broken = self.tmp / "g0-state.json"
        broken.write_text("{broken", encoding="utf-8")
        _blk_write(out_dir / "g0" / "result.json", _blk_result("g0", ["B"], t0, start, tdd_state=str(broken)))
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start, verified=["test_m.py::TestM::test_v"]))
        code, _, err = _blk_run("join", self.repo, self.art)
        os.chmod(self.repo / "pkg", 0o755)
        self.assertEqual(code, 1, err)
        g0, g1 = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"]
        self.assertTrue(g0["returned"], g0)
        self.assertEqual(g1["unrestored"], ["pkg/m.py"], g1)
        self.assertEqual(fixboard.held(self.place), fixboard.HELD.format(groups="g1"))
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual((code, out["done"], out["stop_reason"]), (0, False, stopby.UNRESTORED), err)

    # ---- conflict_check.py
    def test_conflict_check_gathers_child_claims_and_goes(self):
        """F208: 組を戻した後、戻せた組の子の申し出（結果の conflicts）を親の置き場の conflicts.json に集める。名指した行が親の作業
        ツリーに無くなった申し出は積まずに conflicts-dropped.json に名指し、戻せなかった組の申し出は裁かない。裁く申し出が在る時だけ
        go: true（裁定の輪を回す）"""
        claim = {"unit_key": "A", "between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "期待と判定が食い違う",
                 "which_is_right": "request", "kind": "test_vs_request", "source": "tdd"}
        gone = {**claim, "unit_key": "B", "between": ["stats.py:900", "test_stats.py:8"]}
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": []} for g, k in (("g1", "A"), ("g2", "B"), ("g3", "C"))],
                                   start, par=False)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], start, start, conflicts=[claim]))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], start, start, conflicts=[gone]))
        _blk_write(out_dir / "g3" / "result.json", _blk_result("g3", ["C"], start, start, conflicts=[{**claim, "unit_key": "C"}]))
        _blk_write(self.place / "join.json", {"par": False, "units": [], "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""},
            {"group_id": "g2", "unit_ids": ["B"], "returned": True, "reason": ""},
            {"group_id": "g3", "unit_ids": ["C"], "returned": False, "reason": "当たらない"}]})
        code, out, err = _blk_run("conflict_check", self.repo, self.art, node_path="fix__conflict-check")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"go": True, "count": 1})
        items = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([(r["unit_key"], r["source"], r["status"]) for r in items], [("A", "tdd", "parked")])
        dropped = json.loads((self.place / "conflicts-dropped.json").read_text(encoding="utf-8"))["dropped"]
        self.assertEqual(len(dropped), 1)
        self.assertIn("B", dropped[0])
        with self.subTest("申し出の無い run は裁定の輪を回さない"):
            __import__("shutil").rmtree(self.place)
            self.place.mkdir(parents=True)
            out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []}], start, par=False)
            _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], start, start))
            _blk_write(self.place / "join.json", {"par": False, "units": [], "groups": [
                {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}]})
            code, out, err = _blk_run("conflict_check", self.repo, self.art, node_path="fix__conflict-check")
            self.assertEqual(code, 0, err)
            self.assertEqual(out, {"go": False, "count": 0})
            self.assertFalse((self.place / "conflicts-dropped.json").exists())
        with self.subTest("当たったままの組が在る run も、先に戻せた組の申し出は積んで名を残し、裁定の輪だけを回さない"):
            __import__("shutil").rmtree(self.place)
            self.place.mkdir(parents=True)
            out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": []} for g, k in (("g1", "A"), ("g2", "B"))],
                                       start, par=True)
            _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], start, start, conflicts=[claim, {**gone, "unit_key": "A"}]))
            _blk_write(self.place / "join.json", {"par": True, "units": [], "groups": [
                {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""},
                {"group_id": "g2", "unit_ids": ["B"], "returned": False, "reason": fixboard.UNRESTORED_HEAD, "unrestored": ["x.py"]}]})
            code, out, err = _blk_run("conflict_check", self.repo, self.art, node_path="fix__conflict-check")
            self.assertEqual(code, 0, err)
            self.assertEqual(out, {"go": False, "count": 1})
            items = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
            self.assertEqual([(r["unit_key"], r["status"]) for r in items], [("A", "parked")])
            self.assertEqual(len(json.loads((self.place / "conflicts-dropped.json").read_text(encoding="utf-8"))["dropped"]), 1)

    def test_conflict_check_keeps_claims_citing_their_own_child_place(self):
        """依頼 290: 子の申し出が名指す子の置き場（結果の place）の brief は、その組の名指しの根に許す（元 works の共有の盤面。
        子の受け付けが許した根と同じ）。ほかの組の置き場は許さない。brief の無い run の機械の諦め（between が空）は照らさずに積み、
        役の申し出の空の between は落とす"""
        child = self.tmp / "child-g1"
        child.mkdir()
        (child / "brief-1.md").write_text("# brief\n", encoding="utf-8")
        other = self.tmp / "child-g2"
        other.mkdir()
        giveup = {"unit_key": "A", "between": [f"{child}/brief-1.md:1"], "why_both_cannot_hold": "赤の確かめが 3 回とも通らなかった",
                  "which_is_right": "unknown", "kind": "needs_context", "source": "tdd-gave-up"}
        bare = {**giveup, "unit_key": "C", "between": []}
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": []} for g, k in (("g1", "A"), ("g2", "B"), ("g3", "C"))],
                                   start, par=False)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], start, start, conflicts=[giveup], place=str(child)))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], start, start, conflicts=[{**giveup, "unit_key": "B"}],
                                                               place=str(other)))
        _blk_write(out_dir / "g3" / "result.json", _blk_result("g3", ["C"], start, start, conflicts=[
            bare, {**bare, "unit_key": "D", "source": "tdd"}], place=""))
        _blk_write(self.place / "join.json", {"par": False, "units": [], "groups": [
            {"group_id": g, "unit_ids": [k], "returned": True, "reason": ""} for g, k in (("g1", "A"), ("g2", "B"), ("g3", "C"))]})
        code, out, err = _blk_run("conflict_check", self.repo, self.art, node_path="fix__conflict-check")
        self.assertEqual(code, 0, err)
        items = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([(r["unit_key"], r["source"]) for r in items], [("A", "tdd-gave-up"), ("C", "tdd-gave-up")])
        dropped = json.loads((self.place / "conflicts-dropped.json").read_text(encoding="utf-8"))["dropped"]
        self.assertEqual([d.split(":", 1)[0] for d in dropped], ["g2", "g3"])
        self.assertIn("（B）", dropped[0])
        self.assertIn("（D）", dropped[1])

    # ---- tdd_unit.py
    def test_tdd_unit_writes_one_body_for_all_groups(self):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": []}], start)
        row = {"unit_key": "A", "route": "tdd", "why": "", "tests": ["test_stats.py::test_mean"], "test_files": [],
               "red": "ok", "green": "ok", "refactor": "none", "gave_up": "", "problems": [], "red_quotes": {},
               "quote_unchecked": [], "stub_files": [], "test_cmd": "", "refactor_why": ""}
        _blk_write(out_dir / "g1" / "result.json", _blk_result(
            "g1", ["A"], start, start, tdd={"ran": True, "reason": "", "suite": "run.sh", "reused": {}, "units": [row]}))
        code, out, err = _blk_run("tdd_unit", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, [{"group_id": "g1", "ran": True, "reason": "", "suite": "run.sh", "reused": {}, "units": [row]},
                               {"group_id": "g2", "ran": False, "reason": out[1]["reason"], "suite": "", "reused": {},
                                "units": []}])
        self.assertTrue(out[1]["reason"])
        self.assertEqual(json.loads((self.place / "tdd-unit.json").read_text(encoding="utf-8")), out)

    # ---- collect.py
    def collect_place(self, *, ok=True, skipped=True, result_extra=None, conflicts=None):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start, par=False)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], start, start, **(result_extra or {})))
        _blk_write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}],
            "units": [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""}]})
        _blk_write(self.place / "assert-changed.json", {"ok": ok, "reason": "" if ok else "申告が無い"})
        if skipped:
            _blk_write(self.place / "delta" / "skipped.json", {"reason": "全部の単位が軽量"})
        if conflicts is not None:
            _blk_write(self.place / "conflicts.json", {"items": conflicts})
        (self.repo / "stats.py").write_text("X = 2\n", encoding="utf-8")

    def test_collect_light_run_skips_review(self):
        self.collect_place()
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["delta_review"], {"rounds": 0, "pass": True})
        self.assertTrue(out["done"])
        self.assertIsNone(out["conflicts"])
        diff = self.art / out["diff"]["path"]
        self.assertIn("stats.py", diff.read_text(encoding="utf-8"))
        self.assertEqual(out["diff"]["run_id"], _BLK_RUN)

    def test_collect_counts_review_rounds(self):
        self.collect_place(skipped=False)
        _blk_write(self.place / "delta" / "review-1.json", {"pass": False})
        _blk_write(self.place / "delta" / "review-2.json", {"pass": True})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out["delta_review"], {"rounds": 2, "pass": True})
        self.assertTrue(out["done"])

    def test_collect_failed_or_missing_review_is_not_done(self):
        self.collect_place(skipped=False)
        _blk_write(self.place / "delta" / "review-1.json", {"pass": False})
        _blk_write(self.place / "delta" / "review-2.json", {"pass": False})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual((out["delta_review"], out["done"]), ({"rounds": 2, "pass": False}, False))
        with self.subTest("審査の控えが無い"):
            __import__("shutil").rmtree(self.place / "delta")
            code, out, err = _blk_run("collect", self.repo, self.art)
            self.assertEqual(code, 0, err)
            self.assertEqual((out["delta_review"], out["done"]), ({"rounds": 0, "pass": False}, False))

    def test_collect_after_a_failed_change_check_reports_no_review(self):
        self.collect_place(ok=False, skipped=False)
        code, out, err = _blk_run("delta_cut", self.repo, self.art, node_path="fix__delta-cut")
        self.assertEqual((code, out["go"]), (0, False), err)
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual((out["delta_review"], out["done"]), ({"rounds": 0, "pass": False}, False))

    def test_unrestored_group_holds_the_tree_and_stops_for_a_human(self):
        """#403: 戻せず当たったままの組が在る run は、裁定・後始末・差分の審査が木を動かさず、返す節は done: false と人待ちの止めの語
        stopby.UNRESTORED で返す（組の行は当たったままのパスを持つ）"""
        import leftovers
        import stopby
        self.collect_place(skipped=False)
        leftovers.record_ignored(self.place, self.repo)
        (self.repo / "junk.pyc").write_bytes(b"x")
        row = {"group_id": "g1", "unit_ids": ["A"], "returned": False, "reason": fixboard.UNRESTORED_HEAD, "unrestored": ["stats.py"]}
        _blk_write(self.place / "join.json", {"par": True, "groups": [row],
                                              "units": [{"unit_id": "A", "group_id": "g1", "status": "not_done", "reason": "x"}]})
        code, out, err = _blk_run("conflict_check", self.repo, self.art, node_path="fix__conflict-check")
        self.assertEqual((code, out), (0, {"go": False, "count": 0}), err)
        code, out, err = _blk_run("clean", self.repo, self.art)
        self.assertEqual((code, out), (0, {"ok": True, "count": 0}), err)
        self.assertTrue((self.repo / "junk.pyc").is_file(), "人が確かめるまで木を動かさない")
        code, out, err = _blk_run("delta_cut", self.repo, self.art, node_path="fix__delta-cut")
        self.assertEqual((code, out["go"]), (0, False), err)
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual((out["done"], out["stop_reason"], out["groups"]), (False, stopby.UNRESTORED, [row]))
        self.assertIn(stopby.UNRESTORED, stopby.WAITING, "人待ちの語（結末は needs_human）")
        with self.subTest("返す節の中が落ちた道（fallback）も、当たったままの組を名指して人に回す"):
            (self.place / fixboard.FIX_UNITS_FILE).write_text("{broken", encoding="utf-8")
            code, out, err = _blk_run("collect", self.repo, self.art)
            self.assertEqual(code, 0, err)
            self.assert_contract(out)
            self.assertIn("fix の出力を組めない", out["groups"][0]["reason"])
            self.assertEqual((out["done"], out["stop_reason"], out["groups"][0]["unrestored"]), (False, stopby.UNRESTORED, ["stats.py"]))
            (self.place / fixboard.FIX_UNITS_FILE).unlink()
        with self.subTest("当たったままの組の無い run の止めの語は空"):
            self.collect_place()
            code, out, err = _blk_run("collect", self.repo, self.art)
            self.assertEqual((code, out["done"], out["stop_reason"]), (0, True, ""), err)

    def test_collect_returns_the_contract_when_the_boundary_cannot_be_read(self):
        """境の口（.shared）も lib も読めない写しから起こしても、返す節は落ちずに約束の形の done: false を返す（stdlib だけの最後の手）"""
        lone = self.tmp / "lone" / "fix" / "scripts"
        lone.mkdir(parents=True)
        (lone / "collect.py").write_bytes((BLOCK / "scripts" / "collect.py").read_bytes())
        env = hermetic.child_env(ARTIFACTS_DIR=str(self.art), WORKFLOW_ID=_BLK_RUN, PYTHONDONTWRITEBYTECODE="1")
        done = subprocess.run([sys.executable, str(lone / "collect.py")], cwd=self.repo, env=env, capture_output=True,
                              text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assert_contract(out)
        self.assertFalse(out["done"])
        self.assertEqual(out["diff"]["path"], "fix/fix/fix-collect-error.txt")
        self.assertIn("boundary", (self.place / "fix-collect-error.txt").read_text(encoding="utf-8"))

    def test_collect_refused_change_is_not_done(self):
        self.collect_place(ok=False)
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertFalse(out["done"])

    def test_collect_plan_item_ruling_and_objection(self):
        row = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": "A", "between": ["stats.py:9", "test_stats.py:1"],
               "why_both_cannot_hold": "案の項目が判定と食い違う", "which_is_right": "request", "kind": "brief_vs_judgment",
               "status": "ruled", "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "plan_items": [1]},
               "replan": "waiting"}
        self.collect_place(conflicts=[row], result_extra={"objection": "判定の単位 A は前提が違う",
                                                          "changed": {**{k: False for k in _BLK_MARKS}, "premise_drift": True}})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["replan_items"], ["1"])
        self.assertIn("前提が違う", out["objection"])
        self.assertTrue(out["changed"]["premise_drift"])
        self.assertEqual(out["conflicts"]["path"], "fix/fix/conflicts.json")

    def test_changed_carries_the_premise_drift_note_and_the_x_scalars(self):
        """E42・E17: 返りの changed は前提のずれの申告の文 premise_drift_note を組の順に改行でつなぎ、x_scalars は修正役が足した x_ の
        数値を名ごとに足す（独立の目の R2 の頭と規模の数値。元 review-loop.py:1848・:2175）"""
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [1]}], start, par=False)
        for gid, unit, note, xs in (("g1", "A", "上限を 10 に測り直した", {"x_moved": 2}),
                                    ("g2", "B", "", {"x_moved": 3, "x_new_files": 1})):
            _blk_write(out_dir / gid / "result.json", _blk_result(
                gid, [unit], start, start, changed={**{k: False for k in _BLK_MARKS}, "premise_drift": bool(note),
                                                    "premise_drift_note": note}, x_scalars=xs))
        _blk_write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": g, "unit_ids": [u], "returned": True, "reason": ""} for g, u in (("g1", "A"), ("g2", "B"))],
            "units": [{"unit_id": u, "group_id": g, "status": "fixed", "reason": ""} for g, u in (("g1", "A"), ("g2", "B"))]})
        _blk_write(self.place / "assert-changed.json", {"ok": True, "reason": ""})
        _blk_write(self.place / "delta" / "skipped.json", {"reason": "全部の単位が軽量"})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual((out["changed"]["premise_drift"], out["changed"]["premise_drift_note"]), (True, "上限を 10 に測り直した"))
        self.assertEqual(out["x_scalars"], {"x_moved": 5, "x_new_files": 1})

    def beside(self, out) -> pathlib.Path:
        return (self.art / out["diff"]["path"]).parent

    def test_collect_returns_accepted_breaks(self):
        """F427・L-W20・R23（S03）: 修正役が壊すと分かって通した理由（changes[].breaks.accepted。空白だけは除く）を、戻せた組の子の
        結果（handoffs。fixboard.group_result が返答から組む）と裁定の後の修正役の返答から、fix の出力の handoffs に 1 件 1 行で返す
        （読み手は線の fixed を通した最後の承認ノードと報告）"""
        import fixboard
        reply = {"changes": [{"unit_key": "A", "breaks": {"accepted": "古い呼び手の戻り値が変わる"}}]}
        child = fixboard.group_result({"group_id": "g1", "unit_ids": ["A"]}, start_tree="t", end_tree="t", tdd=None, reply=reply)
        self.collect_place(result_extra={"handoffs": child["handoffs"]})
        _blk_write(self.place / "fix-ruled-reply.json", {"changes": [
            {"unit_key": "B", "breaks": {"accepted": " 設定の既定が変わる\n（人が決める）"}},
            {"unit_key": "C", "breaks": {"accepted": "  "}}]})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["handoffs"], ["A: 壊すと分かって通した——古い呼び手の戻り値が変わる",
                                           "B: 壊すと分かって通した——設定の既定が変わる （人が決める）"])
        self.assertEqual(child["claimed"], ["A"])

    CLOSURE_A = {"unit_key": "A", "counts": "defects", "total": 3, "after": 3, "claimed": 1, "covered": 1, "bound": True,
                 "how_from": "判定", "closed": False, "discrepancies": ["申告の site 1 件・数え直しの当たり 3 件"], "out_of_query": []}
    CLOSURE_B = {"unit_key": "B", "counts": "defects", "total": 2, "after": 0, "claimed": 2, "covered": 2, "bound": True,
                 "how_from": "判定", "closed": True, "discrepancies": [], "out_of_query": []}

    def test_collect_writes_the_closure_beside_the_diff(self):
        """F428・R72（S28）: 修正の後に判定の問いで数え直した閉鎖の表（組の子の結果の closure と、裁定の後の段の親の置き場の
        fix-unit-rows.json）と申告の単位（claimed）を diff の隣の closure.json に置く。申告と合わない単位・減っていない単位を読み手が引ける"""
        import fixbeside
        self.collect_place(result_extra={"closure": [self.CLOSURE_A], "claimed": ["A"]})
        _blk_write(self.place / "fix-unit-rows.json", {"round": 1, "rows": [self.CLOSURE_B]})
        _blk_write(self.place / "fix-ruled-reply.json", {"changes": [{"unit_key": "B"}, {"unit_key": "C"}]})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        doc = json.loads((self.beside(out) / fixbeside.CLOSURE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(doc, {"rows": [self.CLOSURE_A, self.CLOSURE_B], "claimed": ["A", "B", "C"]})
        got = fixbeside.read([self.beside(out)])
        self.assertEqual([x.split("（")[0] for x in fixbeside.closure_lines(got, mismatched_only=True)], ["A: 閉じていない"])
        self.assertEqual([x.split("（")[0] for x in fixbeside.closure_lines(got, stuck_only=True)], ["A: 閉じていない"])
        self.assertEqual(fixbeside.closure_lines(got), ["C: 閉鎖の表に行が無い（修正役の申告だけで、機械の数え直しで閉じたと確かめていない）"])
        self.assertEqual(fixbeside.not_closed(got), ["A"])

    def test_collect_writes_the_accept_trace_beside_the_diff(self):
        """F013・F041・R37: 受け付けの行（回さなかった試験・赤緑を確かめずに受けた回・はみ出しの決着・範囲の相談）を、組の子の
        結果の accept_trace と親の置き場の trace.jsonl の受け付けの行（fixboard.traced_ops）から diff の隣の accept-trace.json に置く"""
        import fixbeside
        import fixboard
        child = {"op": fixbeside.TESTS_OP, "ci_left": ["tests/test_slow.py"], "final_left": ["tests/test_far.py"], "final_far": [],
                 "group_id": "g1"}
        self.collect_place(result_extra={"accept_trace": [child]})
        fixboard.trace(self.place, fixbeside.SKIPPED_OP, why=["実行器が無い"])
        fixboard.trace(self.place, "fix_accepted", node="fix-ruled-accept")
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        rows = json.loads((self.beside(out) / fixboard.ACCEPT_TRACE_FILE).read_text(encoding="utf-8"))
        self.assertEqual([r["op"] for r in rows], [fixbeside.TESTS_OP, fixbeside.SKIPPED_OP])
        got = fixbeside.read([self.beside(out)])
        text = "\n".join([*fixbeside.tests_left_lines(got), *fixbeside.gates_lines(got)])
        for want in ("  - tests/test_slow.py", "最後のテストの段に任せた試験（1 件", "  - tests/test_far.py",
                     "事後の関門の束: 受け付け 1 回が受け入れのテストの赤緑を確かめずに通した（理由: 実行器が無い）"):
            self.assertIn(want, text)

    def test_collect_writes_delta_holes_and_lenses_beside_the_diff(self):
        """F312・F329・R73・R38: 差分の審査の穴の名札（fixboard.hole_ties。組めなければ訳）と手直しの handled の行、レンズの集計と
        未確認のレンズの行を diff の隣に置く。手直しが declared で残した穴と 2 回目が fixed と言った穴、落ちたレンズは次の依頼の行になる"""
        import fixbeside
        import fixboard
        import lens
        self.collect_place(skipped=False)
        _blk_write(self.place / "delta" / "review-1.json", {"pass": False})
        _blk_write(self.place / "delta" / "review-2.json", {"pass": True})
        _blk_write(fixboard.out_file(self.place, "p3.delta_fix"), {"handled": [
            {"key": "穴1", "handled": "declared", "how": "仕様どおり", "files": ["stats.py"]}]})
        _blk_write(fixboard.out_file(self.place, "p3.delta_fix2"), {"handled": [
            {"key": "穴2", "handled": "fixed", "how": "分母を直した", "files": ["stats.py"]}]})
        lens.write_routes(self.place, [{"lens": "silent-failure-hunter", "agent": "a", "go": True}])
        lens.collect(self.place, {})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        holes = json.loads((self.beside(out) / fixbeside.DELTA_HOLES_FILE).read_text(encoding="utf-8"))
        self.assertEqual([h["key"] for h in holes["handled"]["1"]], ["穴1"])
        self.assertEqual(set(holes["ties"]), {"1", "2"})
        got = fixbeside.read([self.beside(out)])
        rows = fixbeside.branch_rows(got)
        self.assertIn("手直しの結果（1 件）:", rows)
        self.assertIn("  - 穴1: 直さずに残すと申告した（declared）——仕様どおり", rows)
        items = fixbeside.next_items(got)
        self.assertEqual([i["text"].split("（")[0] for i in items], ["穴1", "穴2", "silent-failure-hunter"])
        self.assertIn("再実行の要あり", items[-1]["text"])
        always = fixbeside.always_rows(got)
        self.assertIn("  - 落ちたレンズ silent-failure-hunter（再実行の要あり）: レンズのノードの出口が無い（落ちたか走らなかった）", always)
        self.assertEqual(always[-1], fixbeside.ANOMALY_LINE)
        self.assertIn("silent-failure-hunter: 落ちた", "\n".join(fixbeside.lens_lines(got)))

    def test_collect_names_the_beside_files_when_it_cannot_build_the_return(self):
        """K13・errors F1・F2: 出力を組めない（置き場に groups.json が無い）時、diff の隣に閉鎖の表と穴の名札は無く、読み手は無いと名指して
        0 件に見せない（閉鎖の表の訳は閉じたかを数えていない行。許したテストの変更と受け付けの行は collect が空の形で置く）"""
        import fixbeside
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertFalse(out["done"])
        got = fixbeside.read([self.beside(out)])
        self.assertEqual(sorted(x.split(" ")[1].rsplit("/", 1)[-1] for x in got["unread"]), sorted(fixbeside.FILES), got["unread"])
        self.assertTrue(all(x.endswith(fixbeside.CLOSURE_UNREAD) for x in got["closure_unread"]) and got["closure_unread"])

    def test_collect_takes_units_fixed_after_ruling(self):
        """裁定の後の修正の段が直した単位（親の置き場の fix-units.json）は fixed で返る。fixed の行は替えない"""
        self.collect_place()
        _blk_write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}],
            "units": [{"unit_id": "A", "group_id": "g1", "status": "not_done", "reason": "申し出で止めた"}]})
        _blk_write(self.place / "fix-units.json", {"A": {"status": "fixed", "reason": ""}})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["units"], [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""}])

    def test_collect_group_mode_returns_its_own_row(self):
        start = self.snapshot(self.repo)
        out_dir = self.tmp / "parent" / "groups"
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], start, start))
        group = json.dumps({"group_id": "g2", "unit_ids": ["B"], "items": []})
        code, out, err = _blk_run("collect", self.repo, self.art,
                                  {"mode": "group", "group": group, "out_dir": str(out_dir)}, "collect")
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["units"], [{"unit_id": "B", "group_id": "g2", "status": "fixed", "reason": ""}])
        self.assertTrue(out["done"])

    def test_collect_group_mode_takes_only_a_usable_result(self):
        """組の子の自分の結果も 1 つの決まり（fixboard.usable_result）で読む: end_tree の無い結果は返っていない組で、done: false"""
        start = self.snapshot(self.repo)
        out_dir = self.tmp / "parent" / "groups"
        broken = _blk_result("g2", ["B"], start, start)
        del broken["end_tree"]
        _blk_write(out_dir / "g2" / "result.json", broken)
        group = json.dumps({"group_id": "g2", "unit_ids": ["B"], "items": []})
        code, out, err = _blk_run("collect", self.repo, self.art,
                                  {"mode": "group", "group": group, "out_dir": str(out_dir)}, "collect")
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual([g["returned"] for g in out["groups"]], [False])
        self.assertFalse(out["done"])

    def test_collect_group_mode_returns_no_review(self):
        """組の子の run は差分の審査を回さず、返りの delta_review は {rounds: 0, pass: false}。子の置き場に審査を省いた印や審査の
        控えが在っても読まない（親は子の返りのこの欄を読まない）"""
        start = self.snapshot(self.repo)
        out_dir = self.tmp / "parent" / "groups"
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], start, start))
        group = json.dumps({"group_id": "g2", "unit_ids": ["B"], "items": []})
        for name, doc in (("delta/skipped.json", {"reason": "全部の単位が軽量"}), ("delta/review-1.json", {"pass": True})):
            with self.subTest(name):
                __import__("shutil").rmtree(self.place / "delta", ignore_errors=True)
                _blk_write(self.place / name, doc)
                code, out, err = _blk_run("collect", self.repo, self.art,
                                          {"mode": "group", "group": group, "out_dir": str(out_dir)}, "collect")
                self.assertEqual(code, 0, err)
                self.assert_contract(out)
                self.assertEqual(out["delta_review"], {"rounds": 0, "pass": False})
                self.assertTrue(out["done"], "組の子の done は審査に依らない")

    def test_group_permits_reach_join_and_collect_only_for_an_accepted_reply(self):
        """#286: 修正役の返答を受け付けていない組の子の許しは、join の和（同じテストのファイルへの挿しだけの食い違いを合わせる）にも
        親の collect の返りの allowed_test_changes・diff の隣の allowed-tests.json にも入らない。受け付けた組の許しは両方に入る。
        #304: 形の崩れた許しの行（path の無い行・ALLOWED_SOURCES に無い source）は join も collect も同じ決まりで捨て、join は落ちない"""
        import fixboard
        child = {"path": "test_stats.py", "permit": "plan-agreed-2", "source": "consult"}
        src = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        tail = 'if __name__ == "__main__":'

        def added(name):
            return src.replace(tail, f"class {name}(unittest.TestCase):\n    def test_{name.lower()}(self):\n"
                                     f"        self.assertTrue(True)\n\n\n{tail}")
        malformed = [{"permit": "plan-3", "source": "plan"}, {"path": "test_other.py", "permit": "x-1", "source": "guess"}]
        bad_source = [{"path": "test_stats.py", "permit": "x-1", "source": "guess"}]
        for reply, returned, given, rows, extra in ((None, 1, [child], [], []), ({"changes": []}, 2, [child], [child], []),
                                                    ({"changes": []}, 2, [child], [child], malformed),
                                                    ({"changes": []}, 1, [], [], bad_source)):
            with self.subTest(reply=reply, extra=extra):
                __import__("shutil").rmtree(self.art, ignore_errors=True)
                self.restore()
                self.place.mkdir(parents=True)
                permits = fixboard.group_result({"group_id": "g2", "unit_ids": ["B"]}, start_tree="", end_tree="", tdd=None,
                                                reply=reply, allowed_rows=given)["allowed_tests"] + extra
                start = self.snapshot(self.repo)
                t1, t2 = self.tree_with({"test_stats.py": added("TestG1")}), self.tree_with({"test_stats.py": added("TestG2")})
                out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                            {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
                _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
                _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start, allowed_tests=permits))
                code, out, err = _blk_run("join", self.repo, self.art)
                self.assertEqual((code, out), (0, {"groups": 2, "returned": returned}), err)
                self.collect_place(result_extra={"allowed_tests": permits})
                code, out, err = _blk_run("collect", self.repo, self.art)
                self.assertEqual(code, 0, err)
                self.assertEqual(out["allowed_test_changes"], [r["path"] for r in rows])
                beside = (self.art / out["diff"]["path"]).parent / fixboard.ALLOWED_TESTS_FILE
                self.assertEqual(json.loads(beside.read_text(encoding="utf-8")), rows)

    def test_join_drops_malformed_test_files_of_a_child_tdd_unit(self):
        """#319: 組の子の result.json の TDD の単位の test_files に文字列でない要素（null）が混じっても、test_files が並びでない（数）
        時も、join の和は落ちず、文字列の要素だけで組を戻す"""
        src = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        tail = 'if __name__ == "__main__":'

        def added(name):
            return src.replace(tail, f"class {name}(unittest.TestCase):\n    def test_{name.lower()}(self):\n"
                                     f"        self.assertTrue(True)\n\n\n{tail}")
        start = self.snapshot(self.repo)
        t1, t2 = self.tree_with({"test_stats.py": added("TestG1")}), self.tree_with({"test_stats.py": added("TestG2")})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        tdd = {"ran": True, "reason": "", "suite": "", "units": [{"unit_key": "B", "tests": [], "test_files": ["test_stats.py", None]},
                                                          {"unit_key": "B", "tests": [], "test_files": 5}]}
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start, tdd=tdd))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual((code, out), (0, {"groups": 2, "returned": 2}), err)

    def test_join_reads_a_malformed_child_tdd_as_empty(self):
        """#342: 組の子の result.json の tdd が dict でない（並び・文字列）時も、units が並びでない（数）時も、verified・
        allowed_tests が並びでない（数・文字列）時も、join は落ちず、TDD の単位・名指し・許しの無い組として戻す"""
        start = self.snapshot(self.repo)
        tdds = {"g1": ["x"], "g2": "x", "g3": {"ran": True, "reason": "", "suite": "", "units": 5,
                                              "test_cmd": ["x"]}}
        broken = {"g1": {"verified": 5, "allowed_tests": 5}, "g2": {"verified": "test_x", "allowed_tests": "x"}, "g3": {}}
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [g.upper()], "items": [i]} for i, g in enumerate(tdds, 1)],
                                   start)
        for g, tdd in tdds.items():
            end = self.tree_with({f"{g}.md": f"{g}\n"})
            _blk_write(out_dir / g / "result.json", _blk_result(g, [g.upper()], end, start, tdd=tdd, **broken[g]))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual((code, out), (0, {"groups": 3, "returned": 3}), err)

    def test_collect_allowed_test_changes_from_rulings_and_groups(self):
        """F429: 許したテストの変更（裁定 fix_test_scope の範囲・組の子が許した物）を返りの allowed_test_changes にパスで並べ、
        訳（許しの id と出どころ）を返りの diff の隣の allowed-tests.json に [{path, permit, source}] で置く（元
        works/.shared/core/conflict.py:983 ruled_test_doc が最後の関所に許しの id と理由つきで並べた）。止めの道（lib は読めるが
        返りを組めない）と lib の無い道でも、diff の隣に空の [] を置く"""
        import fixboard
        ruled = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": "A", "between": ["stats.py:9", "test_stats.py:8"],
                 "why_both_cannot_hold": "テストの期待が判定と食い違う", "which_is_right": "request", "kind": "test_vs_request",
                 "status": "ruled", "ruling": {"decision": "fix_test_scope", "text": "期待を直してよい",
                                               "limits": ["test_stats.py:8-9"]}}
        child = {"path": "test_extra.py", "permit": "plan-agreed-2", "source": "consult"}
        self.collect_place(conflicts=[ruled], result_extra={"allowed_tests": [child]})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["allowed_test_changes"], ["test_extra.py", "test_stats.py"])
        beside = (self.art / out["diff"]["path"]).parent / fixboard.ALLOWED_TESTS_FILE
        self.assertEqual(json.loads(beside.read_text(encoding="utf-8")),
                         [child, {"path": "test_stats.py", "permit": "conflict-ruling-c1-1", "source": "ruling"}])
        self.assertTrue({r["source"] for r in json.loads(beside.read_text(encoding="utf-8"))} <= set(fixboard.ALLOWED_SOURCES))
        with self.subTest("止めの道"):
            __import__("shutil").rmtree(self.art, ignore_errors=True)
            self.place.mkdir(parents=True)
            code, out, err = _blk_run("collect", self.repo, self.art)
            self.assertEqual((code, out["done"]), (0, False), err)
            beside = (self.art / out["diff"]["path"]).parent / fixboard.ALLOWED_TESTS_FILE
            self.assertEqual(json.loads(beside.read_text(encoding="utf-8")), [])
            self.assertEqual(json.loads((beside.parent / fixboard.ACCEPT_TRACE_FILE).read_text(encoding="utf-8")), [])
        with self.subTest("lib の無い道"):
            __import__("shutil").rmtree(self.art, ignore_errors=True)
            lone = self.tmp / "lone" / "fix" / "scripts"
            lone.mkdir(parents=True)
            (lone / "collect.py").write_bytes((BLOCK / "scripts" / "collect.py").read_bytes())
            env = hermetic.child_env(ARTIFACTS_DIR=str(self.art), WORKFLOW_ID=_BLK_RUN, PYTHONDONTWRITEBYTECODE="1")
            done = subprocess.run([sys.executable, str(lone / "collect.py")], cwd=self.repo, env=env, capture_output=True,
                                  text=True, encoding="utf-8")
            self.assertEqual(done.returncode, 0, done.stderr)
            beside = (self.art / json.loads(done.stdout)["diff"]["path"]).parent / fixboard.ALLOWED_TESTS_FILE
            self.assertEqual(json.loads(beside.read_text(encoding="utf-8")), [])
            self.assertEqual(json.loads((beside.parent / fixboard.ACCEPT_TRACE_FILE).read_text(encoding="utf-8")), [])

    def test_collect_returns_handoffs_and_mismatched_units(self):
        """最後の関所を開ける理由の 2 欄（元 works/darkfactory/lib/line_edge.py:800 _final_needs の handoffs・mismatched）:
        handoffs は修正役が人に回した物（受け付けた返答の changes[].breaks.accepted。元 works/.shared/core/report.py:304
        handoff_lines）、mismatched は直したという申告と機械の数え直しが合わない単位（閉鎖の表の discrepancies の在る行。元
        works/.shared/core/querytest.py:254 closure_lines の mismatched_only）。組の子の結果の行と、親の置き場の裁定の後の返答と
        閉鎖の表の行を重ねずに並べる。形 group は自分の結果の行だけ、返りを組めない道は空"""
        import fixboard
        import querytest
        child = {"handoffs": ["A: 壊すと分かって通した——古い呼び出しを捨てる"],
                 "mismatched": ["A: 閉じていない（defects・修正前 3・修正後 1・申告の site 3・問い 判定者）——合わない: 残り 1"]}
        self.collect_place(result_extra=child)
        _blk_write(self.place / fixboard.RULED_REPLY_FILE, {"changes": [
            {"unit_key": "B", "breaks": {"how": "h", "result": "r", "accepted": "  外の利用者の\n挙動が変わる  "}},
            {"unit_key": "C", "breaks": {"how": "h", "result": "r", "accepted": " "}},
            {"unit_key": "A", "breaks": {"how": "h", "result": "r"}}]})
        _blk_write(self.place / querytest.CLOSURE_FILE, {"round": 1, "rows": [
            {"unit_key": "B", "closed": True, "discrepancies": ["申告の数が問いの数と合わない"]},
            {"unit_key": "C", "closed": False, "discrepancies": []}]})
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["handoffs"], [*child["handoffs"], "B: 壊すと分かって通した——外の利用者の 挙動が変わる"])
        self.assertEqual(len(out["mismatched"]), 2, out["mismatched"])
        self.assertEqual(out["mismatched"][0], child["mismatched"][0])
        self.assertTrue(out["mismatched"][1].startswith("B: 閉じた（"), out["mismatched"])
        self.assertIn("合わない: 申告の数が問いの数と合わない", out["mismatched"][1])
        with self.subTest("形 group は自分の結果の行だけ"):
            start = self.snapshot(self.repo)
            out_dir = self.tmp / "parent" / "groups"
            _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], start, start, **child))
            group = json.dumps({"group_id": "g2", "unit_ids": ["B"], "items": []})
            code, out, err = _blk_run("collect", self.repo, self.art, {"mode": "group", "group": group, "out_dir": str(out_dir)},
                                      "collect")
            self.assertEqual(code, 0, err)
            self.assertEqual((out["handoffs"], out["mismatched"]), (child["handoffs"], child["mismatched"]))
        with self.subTest("返りを組めない道"):
            __import__("shutil").rmtree(self.art, ignore_errors=True)
            self.place.mkdir(parents=True)
            code, out, err = _blk_run("collect", self.repo, self.art)
            self.assertEqual(code, 0, err)
            self.assert_contract(out)
            self.assertEqual((out["done"], out["handoffs"], out["mismatched"]), (False, [], []))

    def test_collect_diff_holds_every_returned_group(self):
        """F424: 返りの diff は run の始めの版（prep が控えた base-rev.json）から今の作業ツリーへの累積差分の指し札で、戻せた組の
        全部の直し（未追跡の新しいファイルも）が載り、.archon/ の下は載らない。途中で HEAD が進んでも始めの版から取る。差分が無ければ
        空の差分の訳のファイルを指す（元 works/.shared/core/graphloops/rules/review-loop.py:1567 の fix_delta と線の差分）"""
        import fixboard
        fixboard.record_base_rev(self.place, self.repo)
        start = self.snapshot(self.repo)
        t1 = self.tree_with({"stats.py": (self.repo / "stats.py").read_text(encoding="utf-8").replace("len(xs) - 1", "len(xs)")})
        t2 = self.tree_with({"extra.py": "X = 1\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual((code, out), (0, {"groups": 2, "returned": 2}), err)
        git(self.repo, "commit", "-qam", "途中で HEAD が進む")
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "run.json").write_text("{}\n", encoding="utf-8")
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["diff"]["path"], "fix/fix/fix.diff")
        diff = (self.art / out["diff"]["path"]).read_text(encoding="utf-8")
        self.assertIn("b/stats.py", diff)
        self.assertIn("/ (len(xs))", diff)
        self.assertIn("b/extra.py", diff)
        self.assertNotIn(".archon", diff)
        with self.subTest("差分が無い"):
            (self.place / "fix.diff").unlink()
            git(self.repo, "reset", "-q", "--hard", fixboard.base_rev_of(self.place))
            git(self.repo, "clean", "-qfd", "-e", ".archon")
            code, out, err = _blk_run("collect", self.repo, self.art)
            self.assertEqual(code, 0, err)
            self.assertEqual(out["diff"]["path"], "fix/fix/fix-diff-none.txt")
            self.assertIn("空", (self.art / out["diff"]["path"]).read_text(encoding="utf-8"))

    def test_collect_conflicts_pointer_only_with_rows(self):
        """F425: 返りの conflicts は申し出と裁定の置き場 conflicts.json の指し札で、行が無ければ null（置き場のファイルが空の行でも
        null）。replan_items は裁定 fix_plan_item が誤りとした項目の番号（欄 plan_items、無ければその単位の組の項目）"""
        self.collect_place()
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual((out["conflicts"], out["replan_items"]), (None, []))
        self.collect_place(conflicts=[])
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertIsNone(out["conflicts"], "行の無い conflicts.json は指さない")
        row = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": "A", "between": ["stats.py:9", "test_stats.py:8"],
               "why_both_cannot_hold": "案の項目が判定と食い違う", "which_is_right": "request", "kind": "brief_vs_judgment",
               "status": "ruled", "ruling": {"decision": "fix_plan_item", "text": "項目が誤り", "limits": []}, "replan": "waiting"}
        self.collect_place(conflicts=[row, {**row, "id": "c1-2", "unit_key": "B",
                                             "ruling": {"decision": "ask_human", "text": "人に聞く", "limits": []}}])
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assert_contract(out)
        self.assertEqual(out["conflicts"], {"type": "archon_artifact", "run_id": _BLK_RUN, "path": "fix/fix/conflicts.json"})
        self.assertEqual(out["replan_items"], ["1"], "欄 plan_items の無い裁定はその単位の組の項目")

    def test_collect_never_fails(self):
        cases = {
            "start_not_json": lambda: {"start": "{not json"},
            "pointer_target_missing": lambda: {"start": _blk_ptr("in/none.json"), "judgment": _blk_ptr("in/none.json")},
            "empty_place": lambda: {},
            "broken_result": self.broken_result,
            "group_without_result": lambda: {"mode": "group", "group": '{"group_id": "g9", "unit_ids": ["Z"], "items": []}'},
            "unknown_mode": lambda: {"mode": "lane"},
        }
        for name, make in cases.items():
            with self.subTest(name):
                __import__("shutil").rmtree(self.art, ignore_errors=True)
                self.place.mkdir(parents=True)
                code, out, err = _blk_run("collect", self.repo, self.art, make())
                self.assertEqual(code, 0, err)
                self.assert_contract(out)
                self.assertFalse(out["done"])
                reasons = [g["reason"] for g in out["groups"]] + [u["reason"] for u in out["units"]]
                self.assertTrue(any(reasons), out)

    def broken_result(self):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []}], start, par=False)
        (out_dir / "g1").mkdir(parents=True)
        (out_dir / "g1" / "result.json").write_text("{broken", encoding="utf-8")
        _blk_write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}],
            "units": [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""}]})
        return {}

    # ---- clean.py・assert_changed.py
    def test_clean_keeps_archon_place(self):
        import leftovers
        leftovers.record_ignored(self.place, self.repo)
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "w.pyc").write_bytes(b"x")
        (self.repo / "junk.pyc").write_bytes(b"x")
        code, out, err = _blk_run("clean", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"ok": True, "count": 1})
        self.assertFalse((self.repo / "junk.pyc").exists())
        self.assertTrue((self.repo / ".archon" / "w.pyc").is_file())

    def assert_case(self, declared, touch):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []}], start, par=False)
        reply = _blk_write(self.tmp / "reply.json", {"changes": [{"files": declared}]})
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], start, start, reply_file=str(reply)))
        _blk_write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}], "units": []})
        for name in touch:
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("changed\n", encoding="utf-8")
        code, out, err = _blk_run("assert_changed", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads((self.place / "assert-changed.json").read_text(encoding="utf-8")), out)
        return out

    def test_assert_changed_passes_declared_change(self):
        out = self.assert_case(["stats.py"], ["stats.py", ".archon/run.json"])
        self.assertEqual(out, {"ok": True, "reason": ""})

    def test_assert_changed_does_not_count_archon_place(self):
        out = self.assert_case([".archon/run.json"], [".archon/run.json"])
        self.assertFalse(out["ok"])
        self.assertIn(".archon/run.json", out["reason"])

    def test_assert_changed_refuses_empty_declaration(self):
        out = self.assert_case([], ["stats.py"])
        self.assertFalse(out["ok"])

    def test_assert_changed_reads_japanese_and_untracked_names(self):
        """F419: 日本語の名前は git の引用（"\\346\\227\\245..."）でなくそのままの名で申告と突き合わせ、未追跡の新しいファイルも変わった
        物に数える。申告したのに変わっていないファイルと、テストを走らせただけ（無視される __pycache__ が出来ただけ）の木は通さず、
        落ちずに ok: false と理由を書く（元 works/tests/test_blk_fix.py:450 test_japanese_names_pass・:436
        test_untracked_file_passes・:428 test_declared_but_unchanged_file_fails・:413 test_running_tests_only_fails の写し）"""
        (self.repo / "日本.py").write_text("x = 1\n", encoding="utf-8")
        git(self.repo, "add", "日本.py")
        git(self.repo, "commit", "-qm", "日本")
        out = self.assert_case(["日本.py", "未追跡.py"], ["日本.py", "未追跡.py"])
        self.assertEqual(out, {"ok": True, "reason": ""})
        self.restore()
        with self.subTest("申告したのに変わっていない"):
            out = self.assert_case(["stats.py", "test_stats.py"], ["stats.py"])
            self.assertFalse(out["ok"])
            self.assertIn("test_stats.py", out["reason"])
        self.restore()
        with self.subTest("テストを走らせただけ"):
            run = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=self.repo, capture_output=True, text=True,
                                 env={"PATH": os.environ["PATH"]})
            self.assertTrue(list(self.repo.glob("__pycache__/*.pyc")), run.stderr)
            out = self.assert_case(["stats.py"], [])
            self.assertFalse(out["ok"])
            self.assertIn("stats.py", out["reason"])


class ClashScenarioCase(unittest.TestCase):
    """#382（持ち主の決め clash-goes-to-ruling）の筋書き: 2 つの組を並べて直し、親の木で合わせると後の組 g2 の名指しが赤になる
    （g1 が e.py の E1 を変え、g2 の b.py が前の E1 を当てにする。BlockScriptsCase の test_join_backs_out_the_later_group_on_a_semantic_clash
    の種）。join・合わせのループ・申し出の照らし・裁定の輪・裁定の後の合わせのループの script を順に起こし、役の手は試験がファイルを書いて模す"""

    setUpClass = BlockScriptsCase.__dict__["setUpClass"]
    setUp = BlockScriptsCase.setUp
    restore = BlockScriptsCase.restore
    tree_with = BlockScriptsCase.tree_with
    groups_file = BlockScriptsCase.groups_file
    rerun_seed = BlockScriptsCase.rerun_seed
    FILLER = "".join(f"# {i}\n" for i in range(10))
    FIXED_B = "from e import E1\n\n\ndef triple(x):\n    return x * 3 + E1 - 10\n"

    TEST_B = ("import unittest\n\nfrom b import triple\n\n\nclass TestB(unittest.TestCase):\n"
              "    def test_triple(self):\n        self.assertEqual(triple(2), 6)\n")

    def joined_with_clash(self, g2_extra=None):
        """種を組んで join を回し、g2 を赤で戻して直し待ちに控えた所まで進める。g2_extra は g2 が足して変えるファイル"""
        start = self.rerun_seed({
            "e.py": f"E1 = 1\n{self.FILLER}E8 = 8\n",
            "b.py": "def triple(x):\n    return x * 3 + 1\n",
            "test_b.py": self.TEST_B})
        _blk_write(self.place / "judgment.json", {"units": [{"key": "A", "label": "block"}, {"key": "B", "label": "block"}],
                                                  "questions": []})
        t1 = self.tree_with({"e.py": f"E1 = 10\n{self.FILLER}E8 = 8\n"})
        t2 = self.tree_with({"e.py": f"E1 = 1\n{self.FILLER}E8 = 80\n",
                             "b.py": "from e import E1\n\n\ndef triple(x):\n    return x * 3 + E1 - 1\n", **(g2_extra or {})})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start, verified=["test_b.py::TestB::test_triple"]))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual((code, out), (0, {"groups": 2, "returned": 1}), err)
        self.green_tree = self.snapshot(self.repo)

    def prep(self, pass_="first"):
        code, out, err = _blk_run("clash_prep", self.repo, self.art, {"pass": pass_})
        self.assertEqual(code, 0, err)
        return out

    def accept(self, reply, iteration, pass_="first"):
        raw = "null" if reply is None else json.dumps(reply, ensure_ascii=False)
        code, out, err = _blk_run("clash_accept", self.repo, self.art,
                                  {"reply": raw, "iteration": str(iteration), "pass": pass_, "limit": "9"})
        self.assertEqual(code, 0, err)
        return out

    def fixed_reply(self, files=("b.py",)):
        return {"handled": "fixed", "how": "b.py の triple が前の組の E1 = 10 でも 6 を返すように直し、test_triple を回して緑", "files": list(files)}

    def group_row(self, gid="g2"):
        return next(g for g in json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"] if g["group_id"] == gid)

    def to_ruling(self, decision="fix_code_as"):
        """1 回目の合わせ役が直せないと答え、申し出が裁定役に届いて decision で裁かれるまで進める。申し出の id を返す"""
        self.joined_with_clash()
        out = self.prep()
        self.assertTrue(out["go"], out)
        got = self.accept({"handled": "cannot", "how": "b.py だけでは前の組の E1 と両立させる直し方が決められない", "files": []},
                          out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, True), got)
        self.assertEqual(self.snapshot(self.repo), self.green_tree, "直せなかった組は当て直す前の緑の木へ戻す")
        rows = [r for r in conflict.items(self.place) if r["source"] == conflict.JOIN_SOURCE]
        self.assertEqual([r["unit_key"] for r in rows], ["B"], rows)
        self.assertEqual(self.group_row()["clash"]["outcome"], "parked")
        code, out, err = _blk_run("conflict_check", self.repo, self.art, node_path="fix__conflict-check")
        self.assertEqual((code, out), (0, {"go": True, "count": 1}), err)
        code, out, err = _blk_run("rule_prep", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertIn(rows[0]["id"], pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8"))
        ruled = {"rulings": [{"id": rows[0]["id"], "decision": decision, "limits": [],
                              "text": "b.py の triple を、前の組が変えた E1 = 10 の上でも triple(2) が 6 になるように直せ"}]}
        code, out, err = _blk_run("rule_accept", self.repo, self.art, {"reply": json.dumps(ruled, ensure_ascii=False), "iteration": "1"})
        self.assertEqual((code, out["ok"]), (0, True), (err, out))
        return rows[0]["id"]

    def test_join_clash_repaired_inside_the_groups_files(self):
        """閉じる条件 1: 組を当てて赤になった run で、合わせ役が影響したファイルだけを直し、緑で進む"""
        self.joined_with_clash()
        out = self.prep()
        self.assertTrue(out["go"], out)
        self.assertIn("E8 = 80", (self.repo / "e.py").read_text(encoding="utf-8"), "控えの差分を当て直した")
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertEqual((brief["files"], brief["named_tests"]), (["b.py", "e.py"], ["test_b.py::TestB::test_triple"]))
        (self.repo / "b.py").write_text(self.FIXED_B, encoding="utf-8")
        got = self.accept(self.fixed_reply(), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["reason"], g2["clash"]["outcome"]), (True, "", "repaired"), g2)
        units = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["units"]
        self.assertEqual({u["unit_id"]: u["status"] for u in units}, {"A": "fixed", "B": "fixed"})
        e = (self.repo / "e.py").read_text(encoding="utf-8")
        self.assertIn("E1 = 10\n", e, "前の組の直しは残る")
        self.assertIn("E8 = 80\n", e, "後の組の直しも残る")
        code, out, err = _blk_run("conflict_check", self.repo, self.art, node_path="fix__conflict-check")
        self.assertEqual((code, out), (0, {"go": False, "count": 0}), err)

    def joined_with_text_clash(self, seed=None, g1=None, g2=None):
        """種を組んで join を回し、g1 と同じ行（e.py の E1）を別の値に変えた g2 を字で当たらない組として控えた所まで進める。
        seed・g1・g2 は種・各組が足して変えるファイル"""
        start = self.rerun_seed({
            "e.py": f"E1 = 1\n{self.FILLER}E8 = 8\n",
            "b.py": "def triple(x):\n    return x * 3 + 1\n",
            "test_b.py": self.TEST_B, **(seed or {})})
        _blk_write(self.place / "judgment.json", {"units": [{"key": "A", "label": "block"}, {"key": "B", "label": "block"}],
                                                  "questions": []})
        t1 = self.tree_with({"e.py": f"E1 = 10\n{self.FILLER}E8 = 8\n", **(g1 or {})})
        t2 = self.tree_with({"e.py": f"E1 = 1  # B が読む\n{self.FILLER}E8 = 8\n",
                             "b.py": "def triple(x):\n    return x * 3\n", **(g2 or {})})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "result.json", _blk_result("g2", ["B"], t2, start, verified=["test_b.py::TestB::test_triple"]))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual((code, out), (0, {"groups": 2, "returned": 1}), err)
        self.green_tree = self.snapshot(self.repo)

    def test_join_text_clash_is_redone_on_the_current_tree(self):
        """#598: 2 つの組が同じ行を別の値に変えて後の組が字で当たらなくても、単位を落とさない。合わせのループが後の組を親の今の
        木へ食い違いの印つきで当て直し、印を残した返答は拒み、印を解いた返答で両方の組の直しが残る"""
        self.joined_with_text_clash()
        out = self.prep()
        self.assertTrue(out["go"], out)
        e = self.repo / "e.py"
        self.assertIn("<<<<<<< ", e.read_text(encoding="utf-8"))
        self.assertEqual((self.repo / "b.py").read_text(encoding="utf-8"), "def triple(x):\n    return x * 3\n")
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertEqual((brief["kind"], brief["conflicted"]), ("text", ["e.py"]))
        got = self.accept(self.fixed_reply(("e.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn("食い違いの印", got["reason"])
        out = self.prep()
        e.write_text(f"E1 = 10  # B が読む\n{self.FILLER}E8 = 8\n", encoding="utf-8")
        got = self.accept(self.fixed_reply(("e.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["clash"]["outcome"]), (True, "repaired"), g2)
        units = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["units"]
        self.assertEqual({u["unit_id"]: u["status"] for u in units}, {"A": "fixed", "B": "fixed"})
        self.assertIn("E1 = 10  # B が読む\n", e.read_text(encoding="utf-8"))
        self.assertEqual((self.repo / "b.py").read_text(encoding="utf-8"), "def triple(x):\n    return x * 3\n")

    def test_join_text_clash_the_role_cannot_fix_reaches_ruling_as_a_text_clash(self):
        """字で当たらない組を合わせ役が直せないと答えると、申し出は字の食い違いとして裁定役に届く（赤の文の申し出と言わない）"""
        self.joined_with_text_clash()
        out = self.prep()
        got = self.accept({"handled": "cannot", "how": "E1 をどちらの値にするか決められない", "files": []}, out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, True), got)
        self.assertEqual(self.snapshot(self.repo), self.green_tree, "直せなかった組は印つきで当て直す前の木へ戻す")
        rows = [r for r in conflict.items(self.place) if r["source"] == conflict.JOIN_SOURCE]
        self.assertEqual([r["unit_key"] for r in rows], ["B"], rows)
        said = rows[0][conflict.WHY_FIELD]
        self.assertIn("前の組の直しと同じ所を変え、字で当たらない", said)
        self.assertNotIn("試験が赤", said)

    def test_join_text_clash_marking_a_locked_test_file_goes_to_ruling_at_once(self):
        """字で当たらない所が許しの無いテストのファイルに在れば、合わせ役は印を残しても消しても通れない。合わせ役を起こさずに、
        そのファイルを名指して裁定役へ回す（裁定 fix_test_scope で許せる）"""
        test_e = "import unittest\n\n\nclass TestE(unittest.TestCase):\n    def test_e(self):\n        pass  # E\n"
        self.joined_with_text_clash(seed={"test_e.py": test_e}, g1={"test_e.py": test_e.replace("# E", "# g1")},
                                    g2={"test_e.py": test_e.replace("# E", "# g2")})
        out = self.prep()
        self.assertFalse(out["go"], out)
        self.assertEqual(self.snapshot(self.repo), self.green_tree)
        rows = [r for r in conflict.items(self.place) if r["source"] == conflict.JOIN_SOURCE]
        self.assertEqual([r["unit_key"] for r in rows], ["B"], rows)
        self.assertIn("許しの無いテストのファイルに在り", rows[0][conflict.WHY_FIELD])
        self.assertIn("test_e.py", rows[0][conflict.WHY_FIELD])
        self.assertEqual(self.group_row()["clash"]["outcome"], "parked")

    def test_join_clash_rejects_writes_outside_the_group_and_test_rewrites(self):
        """受け付けは修正役と同じ軸: 組が変えたファイルの外の変更と、許しの無いテストのファイルの書き換えを拒む（作業ツリーは
        合わせ役の手の中のまま、次の周に同じ組を続ける）"""
        self.joined_with_clash()
        out = self.prep()
        (self.repo / "x.py").write_text("X = 1\n", encoding="utf-8")
        got = self.accept(self.fixed_reply(("x.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn("組が変えたファイルの外", got["reason"])
        (self.repo / "x.py").unlink()
        test_b = self.repo / "test_b.py"
        test_b.write_text(test_b.read_text(encoding="utf-8").replace("6)", "15)"), encoding="utf-8")
        out = self.prep()
        self.assertEqual(out["iteration"], 2)
        self.assertIn("前の回までの返答は受け付けで拒まれた", pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8"))
        got = self.accept(self.fixed_reply(("test_b.py",)), out["iteration"])
        self.assertFalse(got["ok"], got)
        self.assertIn("許しの無いテストのファイル", got["reason"])
        self.assertIn("test_b.py", got["reason"])

    def test_join_clash_rejects_rewriting_the_groups_own_test(self):
        """組が自分で変えたテストのファイルも、許しが無ければ合わせ役は書き換えられない（組の変えたファイルの内でも拒む。
        組の外の拒否とは別の照らし）"""
        self.joined_with_clash({"test_b.py": self.TEST_B + "\n    def test_triple_zero(self):\n        triple(0)\n"})
        out = self.prep()
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertIn("test_b.py", brief["files"])
        test_b = self.repo / "test_b.py"
        test_b.write_text(test_b.read_text(encoding="utf-8").replace("6)", "15)"), encoding="utf-8")
        got = self.accept(self.fixed_reply(("test_b.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn("許しの無いテストのファイル", got["reason"])
        self.assertIn("test_b.py", got["reason"])
        self.assertNotIn("組が変えたファイルの外", got["reason"])

    def test_join_clash_goes_to_ruling_and_the_ruling_fixes_it(self):
        """閉じる条件 2: 直せない形では、申し出が裁定役に届き、裁定の答えで解ける"""
        rid = self.to_ruling()
        out = self.prep("ruled")
        self.assertTrue(out["go"], out)
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in brief["rulings"]], [rid])
        self.assertIn(conflict.CLASH_PROMISE, (self.place / conflict.RULINGS_FILE).read_text(encoding="utf-8"))
        (self.repo / "b.py").write_text(self.FIXED_B, encoding="utf-8")
        got = self.accept(self.fixed_reply(), out["iteration"], "ruled")
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["clash"]["outcome"], g2["clash"]["requests"]), (True, "repaired", [rid]), g2)
        code, out, err = _fx_run("fix_ruled_prep", self.repo, self.art)
        self.assertEqual((code, out["go"]), (0, False), "合わせの申し出への直す裁定は裁定の後の修正役を起こさない")
        self.assertEqual(conflict.human_lines(self.place), [])

    def test_join_clash_reaches_a_human_only_when_the_ruling_cannot_fix_it(self):
        """閉じる条件 3: 裁定でも解けない形だけ、人に回る（裁定の後の合わせ役が 3 回拒まれる）"""
        rid = self.to_ruling()
        for n in (1, 2, 3):
            out = self.prep("ruled")
            self.assertTrue(out["go"], out)
            got = self.accept(self.fixed_reply(), out["iteration"], "ruled")
            self.assertEqual((got["ok"], got["done"]), (False, n == 3), got)
        self.assertEqual(self.snapshot(self.repo), self.green_tree, "人に回す組は当て直す前の緑の木へ戻す")
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["clash"]["outcome"]), (False, "parked"), g2)
        self.assertIn("人に回した", g2["reason"])
        lines = conflict.human_lines(self.place)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("B: 裁定 " + rid), lines)
        self.assertIn("戻した直しの控え", lines[0])
        asked = [r for r in conflict.asked(self.place)]
        self.assertEqual([r["ruling"]["by"] for r in asked], [clash_by()])
        self.assertEqual(self.prep("ruled")["go"], False, "人に回した組はもう当て直さない")

    def test_join_clash_ruled_ask_human_goes_to_a_human_without_reapplying(self):
        """裁定役が ask_human と裁いた合わせの申し出は、裁定の後の合わせのループが当て直さずに人の行になる"""
        self.to_ruling("ask_human")
        self.assertEqual(self.prep("ruled")["go"], False)
        self.assertEqual(self.snapshot(self.repo), self.green_tree)
        lines = conflict.human_lines(self.place)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("B: "), lines)

    def test_join_clash_rejudge_ruling_becomes_the_fix_objection(self):
        """裁定 rejudge は単位を直す義務から外し、裁定の文を修正の出力の異議にする（メイングラフが再審を回す）"""
        self.to_ruling("rejudge")
        self.assertEqual(self.prep("ruled")["go"], False)
        self.assertEqual(conflict.human_lines(self.place), [], "rejudge は人の行にしない")
        self.assertIn("B", conflict.held_by_rulings(self.place))
        code, out, err = _blk_run("collect", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertIn("triple(2) が 6 になるように直せ", out["objection"])


def clash_by():
    import clash
    return clash.BY_RULED_GIVE_UP


_GRP_RUN = "wf-grp"
_GRP_GROUP = {"group_id": "g1", "unit_ids": ["stats.py mean: 分母が len(xs) - 1 になっている"], "items": []}
_GRP_MEAN = _GRP_GROUP["unit_ids"][0]
_GRP_NEW_TEST = '''
    def test_mean_of_two(self):
        self.assertEqual(mean([2, 4]), 3)
'''


def _grp_node(nid):
    return all_nodes(load())[nid]


class GroupChildScriptsCase(unittest.TestCase):
    """形 group の子の run の scripts（group-start・tdd-prep・tdd-step・group-end）を一時の対象のリポジトリ（tests/e2e/target-seed/
    の写し）と、親の置き場・子の置き場（どちらも一時の $ARTIFACTS_DIR/fix/fix/）で subprocess で起こし、返りを節の output_format で
    照らす。テストの実行器は lib/tests/test_blk_fix_tdd.py の SUITE（unittest を回し、断言の失敗を failure と書く JUnit を返す）"""

    def setUp(self):
        from tests.bin.gitkit import committed_copy
        from lib.tests.test_blk_fix_tdd import SUITE
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-grp-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, ROOT / "tests" / "e2e" / "target-seed")
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(SUITE, encoding="utf-8")
        self.parent = self.tmp / "parent-art" / "fix" / "fix"
        self.out_dir = self.parent / "groups"
        self.out_dir.mkdir(parents=True)
        self.art = self.tmp / "child-art"
        self.place = self.art / "fix" / "fix"
        self.grp_env = {}
        self._grp_parent_inputs("")

    def _grp_parent_inputs(self, suite, **start):
        """親の置き場に prep が書く写し（始めの記録・判定・直す前の結末）を置く"""
        (self.parent / "r1").mkdir(parents=True, exist_ok=True)
        (self.parent / "r1" / "start.json").write_text(json.dumps(
            {"tdd_suite": suite, "test_cmd": "", "policy_md": "", "request_file": "", "features_cut": [], **start}), encoding="utf-8")
        (self.parent / "judgment.json").write_text(json.dumps(
            {"units": [{"key": _GRP_MEAN, "label": "block"}], "questions": []}, ensure_ascii=False), encoding="utf-8")
        (self.parent / "baseline.json").write_text(json.dumps({"cases": [], "exit": 1}), encoding="utf-8")

    def _grp_run(self, script, nid, ok=True, cwd=None, **inputs):
        """self.grp_env は子の環境に足す（記録の根を試す試験はここに自分の根を置く）"""
        env = hermetic.child_env()
        env.update({"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": _GRP_RUN,
                    "ARCHON_NODE_EXECUTION": json.dumps({"path": nid}), "WORKS_FACTORY_ROOT": str(ROOT),
                    "PYTHONDONTWRITEBYTECODE": "1", "INPUTS_GROUP": json.dumps(_GRP_GROUP, ensure_ascii=False),
                    "INPUTS_OUT_DIR": str(self.out_dir), "INPUTS_FROM_TREE": "", "INPUTS_MODE": "group", **self.grp_env})
        env.update({f"INPUTS_{k.upper()}": v for k, v in inputs.items()})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{script}.py")], cwd=cwd or self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")
        if not ok:
            self.assertNotEqual(done.returncode, 0, done.stdout)
            return done.stderr
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(validate_schema(out, _grp_node(nid)["output_format"]), [], (nid, out))
        return out

    def _grp_step(self, reply):
        return self._grp_run("tdd_step", "tdd-step", reply=json.dumps(reply, ensure_ascii=False))

    def test_group_start_adopts_the_parent_tree_and_skips_tdd_without_runner(self):
        """from_tree の姿を作業ツリーに写し、親の置き場の写しを自分の置き場に写す。実行器の無い run は tdd: false"""
        import leftovers
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        tree = leftovers.snapshot(self.repo)
        git(self.repo, "checkout", "--", "stats.py")
        out = self._grp_run("group_start", "group-start", from_tree=tree)
        self.assertEqual((out["tdd"], out["units"]), (False, 1), out)
        self.assertIn("tdd_suite", out["reason"])
        self.assertIn("/ len(xs)", stats.read_text(encoding="utf-8"), "親の姿の木を写した")
        for name in ("r1/start.json", "judgment.json", "baseline.json", "fix-ignored-before.json", "tdd-start.json"):
            self.assertTrue((self.place / name).is_file(), name)
        grp = json.loads((self.place / "groups.json").read_text(encoding="utf-8"))
        self.assertEqual((grp["groups"], grp["par"], grp["out_dir"], grp["start_tree"]),
                         ([_GRP_GROUP], False, str(self.out_dir), tree))
        self.assertEqual(self._grp_run("tdd_prep", "tdd-prep"), {"prompt_file": "", "go": False, "new_unit": False})
        self.assertIn("入力 group", self._grp_run("group_start", "group-start", ok=False, group="{}"))

    def test_side_by_side_child_measures_from_the_parent_head(self):
        """並べた子の worktree は origin の枝から切られ、HEAD が親と違う。修正前の版は親の prep が控えた親の HEAD を写して使い、
        子の HEAD からは測らない（親の姿を写しただけの子の累積差分は空）"""
        import fixboard
        import leftovers
        parent_head = git(self.repo, "rev-parse", "HEAD")
        (self.parent / "base-rev.json").write_text(json.dumps({"rev": parent_head}), encoding="utf-8")
        tree = leftovers.snapshot(self.repo)
        (self.repo / "elsewhere.py").write_text("Z = 1\n", encoding="utf-8")
        git(self.repo, "add", "elsewhere.py")
        git(self.repo, "commit", "-qm", "origin の枝にだけ在る commit")
        self._grp_run("group_start", "group-start", from_tree=tree)
        self.assertFalse((self.repo / "elsewhere.py").exists(), "親の姿の木を写した")
        self.assertEqual(fixboard.base_rev_of(self.place), parent_head)
        out = self._grp_run("collect", "fix")
        self.assertEqual(out["diff"]["path"], "fix/fix/fix-diff-none.txt", out["diff"])

    def test_ruled_accept_runs_the_tests_of_the_tdd_state_the_join_copied(self):
        """子の TDD の輪の状態は組の結果の tdd_state に載り、join が親の置き場の tdd-<k>/ に写す（2 度回しても写し直さない）。
        親の裁定の後の修正の受け付けは、写した状態の実行器で変更に当たる試験を走らせ、元で緑だった試験を赤にする直しを拒む"""
        import fixboard
        import leftovers
        parent_art = self.tmp / "parent-art"
        self._grp_parent_inputs(str(self.suite))
        self._grp_run("group_start", "group-start")
        result = json.loads(pathlib.Path(self._grp_run("group_end", "group-end")["result_file"]).read_text(encoding="utf-8"))
        self.assertTrue(pathlib.Path(result["tdd_state"]).is_file(), result["tdd_state"])
        fixboard.write_json(self.parent / "groups.json", {"groups": [_GRP_GROUP], "count": 1, "par": False,
                                                          "start_tree": result["start_tree"], "out_dir": str(self.out_dir)})
        leftovers.record_ignored(self.parent, self.repo)
        for _ in range(2):
            code, _, err = _blk_run("join", self.repo, parent_art, node_path="fix__join")
            self.assertEqual(code, 0, err)
        copied = fixboard.ruled_states(self.parent)
        self.assertEqual(copied, (str(self.parent / "tdd-1" / "state.json"),) * 2)
        self.assertFalse((self.parent / "tdd-2").exists())
        self.assertEqual(json.loads((self.parent / "tdd-1" / "state.json").read_text(encoding="utf-8"))["work"],
                         str(self.parent / "tdd-1"))
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)")
                         .replace("    return x\n", "    return lo\n"), encoding="utf-8")
        reply = {"changes": [_fx_change(_GRP_MEAN, ["stats.py"])]}
        code, out, err = _blk_run("fix_ruled_accept", self.repo, parent_art,
                                  {"reply": json.dumps(reply, ensure_ascii=False), "consulted": "false", "iteration": "1"},
                                  node_path="fix__fix-ruled-accept")
        self.assertEqual(code, 0, err)
        self.assertFalse(out["ok"], out)
        self.assertIn("test_clamp_within_range", out["reason"])

    def test_join_resolves_a_relative_runner_in_the_parent_tree(self):
        """並べた子の worktree で回った輪の状態の実行器（相対パス。自分の置き場から根を引く）を、join は親の作業ツリーで解き直して
        写す。親の裁定の後の修正の受け付けは親の木で試験を走らせ、元で緑だった試験を赤にする直しを拒む"""
        import fixboard
        from lib.tests.test_blk_fix_tdd import SUITE
        (self.repo / "ci").mkdir()
        (self.repo / "ci" / "suite.py").write_text(
            "import os\nos.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))\n" + SUITE, encoding="utf-8")
        git(self.repo, "add", "ci/suite.py")
        git(self.repo, "commit", "-qm", "根を自分の置き場から引く実行器")
        child = self.tmp / "child-tree"
        git(self.repo, "worktree", "add", "--detach", "--quiet", str(child), "HEAD")
        self._grp_parent_inputs("ci/suite.py")
        self._grp_run("group_start", "group-start", cwd=child)
        result = json.loads(pathlib.Path(self._grp_run("group_end", "group-end", cwd=child)["result_file"])
                            .read_text(encoding="utf-8"))
        fixboard.write_json(self.parent / "groups.json", {"groups": [_GRP_GROUP], "count": 1, "par": False,
                                                          "start_tree": result["start_tree"], "out_dir": str(self.out_dir)})
        code, _, err = _blk_run("join", self.repo, self.tmp / "parent-art", node_path="fix__join")
        self.assertEqual(code, 0, err)
        state = json.loads((self.parent / "tdd-1" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(pathlib.Path(state["exe"]).resolve(), (self.repo / "ci" / "suite.py").resolve())
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("    return x\n", "    return lo\n"), encoding="utf-8")
        reply = {"changes": [_fx_change(_GRP_MEAN, ["stats.py"])]}
        code, out, err = _blk_run("fix_ruled_accept", self.repo, self.tmp / "parent-art",
                                  {"reply": json.dumps(reply, ensure_ascii=False), "consulted": "false", "iteration": "1"},
                                  node_path="fix__fix-ruled-accept")
        self.assertEqual(code, 0, err)
        self.assertFalse(out["ok"], out)
        self.assertIn("test_clamp_within_range", out["reason"])

    def _grp_notes(self):
        """親の置き場に修正前の関所の一言（prep が書く human-notes.md）を置き、子の置き場に写ったパスを返す"""
        (self.parent / "human-notes.md").write_text("平均の直しは分母だけに留める\n", encoding="utf-8")
        return str(self.place / "human-notes.md")

    def test_fix_prep_names_the_gate_notes(self):
        """修正役の指示書は、親から写した修正前の関所の一言のファイルを notes_file に名指す（fixboard.fix_values）"""
        notes = self._grp_notes()
        self._grp_run("group_start", "group-start")
        prep = self._grp_run("fix_prep", "fix-prep")
        self.assertTrue(prep["go"], prep)
        self.assertIn(notes, pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8"))

    def test_tdd_prep_names_the_gate_notes(self):
        """TDD の役の指示書は、親から写した修正前の関所の一言のファイルを notes_file に名指す"""
        notes = self._grp_notes()
        self._grp_parent_inputs(str(self.suite))
        self._grp_run("group_start", "group-start")
        self.assertIn(notes, self._grp_prompt())

    def test_tdd_prep_names_the_frozen_policy_copy(self):
        """TDD の役の指示書が名指す方針の文書は、始めの記録の固めた版の写し（run の途中で書き換えた生の文書ではない）"""
        fields, raw_doc = moved_policy(self.tmp)
        self._grp_parent_inputs(str(self.suite), **fields)
        self._grp_run("group_start", "group-start")
        text = self._grp_prompt()
        self.assertIn(fields["policy"]["copy"], text)
        self.assertNotIn(raw_doc, text)

    def test_group_start_in_order_stops_while_an_earlier_child_is_halted(self):
        """#576: 親の作業ツリーで 1 つずつ回る子は、前の組の子が使える結果を残さずに止まっていれば（結果が無いか壊れている）、
        その変更を戻さず何も書かずに 1 で止まる（親の resume が前の子を続きから回す）。前の組が結果を書いていれば今どおり始める"""
        import leftovers
        before = leftovers.snapshot(self.repo)
        (self.out_dir / "g0").mkdir()
        (self.out_dir / "g0" / "group-start.json").write_text(json.dumps({"start_tree": before}), encoding="utf-8")
        (self.repo / "half.py").write_text("Y = 1\n", encoding="utf-8")
        err = self._grp_run("group_start", "group-start", ok=False)
        self.assertIn("g0", err)
        self.assertEqual((self.repo / "half.py").read_text(encoding="utf-8"), "Y = 1\n")
        self.assertEqual(sorted(p.name for p in self.out_dir.iterdir()), ["g0"])
        self.assertEqual(sorted(p.name for p in (self.out_dir / "g0").iterdir()), ["group-start.json"])
        self.assertFalse(self.place.exists())
        (self.out_dir / "g0" / "result.json").write_text("{", encoding="utf-8")
        self.assertIn("g0", self._grp_run("group_start", "group-start", ok=False))
        self.assertEqual((self.repo / "half.py").read_text(encoding="utf-8"), "Y = 1\n")
        (self.out_dir / "g0" / "result.json").write_text(json.dumps({"end_tree": before}), encoding="utf-8")
        self._grp_run("group_start", "group-start")
        self.assertTrue((self.repo / "half.py").is_file(), "前の組の結果の在る変更は残す")

    def test_group_start_side_by_side_ignores_a_sibling_still_running(self):
        """並べた子は兄弟の組がまだ結果を書いていなくても止まらず、兄弟のフォルダに触らない（兄弟は同時に回っている）"""
        import leftovers
        tree = leftovers.snapshot(self.repo)
        (self.out_dir / "g0").mkdir()
        (self.out_dir / "g0" / "group-start.json").write_text(json.dumps({"start_tree": tree}), encoding="utf-8")
        self._grp_run("group_start", "group-start", from_tree=tree)
        self.assertEqual(sorted(p.name for p in (self.out_dir / "g0").iterdir()), ["group-start.json"])

    def test_group_start_in_order_drops_its_own_earlier_attempt(self):
        """自分の組の始めの記録が前の試みから残っていれば、前の試みの結果が無くても壊れていても、その木に戻してから始める
        （戻した控えは書かない）"""
        import leftovers
        before = leftovers.snapshot(self.repo)
        for left in (None, "{"):
            with self.subTest(result=left):
                (self.out_dir / "g1").mkdir(exist_ok=True)
                (self.out_dir / "g1" / "group-start.json").write_text(json.dumps({"start_tree": before}), encoding="utf-8")
                if left is not None:
                    (self.out_dir / "g1" / "result.json").write_text(left, encoding="utf-8")
                (self.repo / "half.py").write_text("Y = 1\n", encoding="utf-8")
                self._grp_run("group_start", "group-start")
                self.assertFalse((self.repo / "half.py").exists())
                self.assertFalse((self.out_dir / "g1" / "dropped.json").exists())
                began = json.loads((self.out_dir / "g1" / "group-start.json").read_text(encoding="utf-8"))
                self.assertEqual(began["start_tree"], before)

    def test_tdd_step_reads_the_recorder_log(self):
        """記録の根が在る run の TDD の輪の受け付けは、group-start が作った作業ツリーの記録を読み、記録の無い変更を拒む"""
        import writelog
        import writes
        env, root = _recorder_root(self.tmp)
        self._grp_parent_inputs(str(self.suite))
        self.grp_env = env
        self._grp_run("group_start", "group-start")
        got = self._grp_step({"phase": "route", "units": [{"unit_key": _GRP_MEAN, "route": "tdd"}]})
        self.assertEqual((got["ok"], got["phase"]), (True, "test"), got)
        test_file = self.repo / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace(
            "\n\nif __name__", _GRP_NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        reply = {"phase": "test", "unit_key": _GRP_MEAN, "test_files": ["test_stats.py"],
                 "tests": ["test_stats.py::TestStats::test_mean_of_two"]}
        got = self._grp_step(reply)
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn(writes.REJECT + "test_stats.py", got["reason"])
        _record(writelog.log_path(root, self.repo), test_file)
        got = self._grp_step(reply)
        self.assertEqual((got["ok"], got["phase"]), (True, "fix"), got)

    def test_tdd_head_reuses_the_test_gate_base_test_cmd(self):
        """test-gate の base が線の run の置き場に控えた test_cmd の緑を、fix の組の子の run の TDD の輪の頭が引く（同じ run の中で
        2 度走らせない）。置き場（boundary.line_place）・run の名（始めの記録の run_id）・落とす変数・2 つの起こし口の指紋が揃って当たる"""
        count = self.tmp / "test-cmd-count"
        test_cmd = f"{sys.executable} -c \"open({str(count)!r}, 'a').write('1\\n')\""
        line = self.tmp / "parent-art"
        self._grp_parent_inputs(str(self.suite), test_cmd=test_cmd, run_id="line-run")
        _blk_write(line / "start" / "record.json", {"run_id": "line-run", "test_cmd": test_cmd, "base_rev": "", "tdd_suite": ""})
        env = hermetic.child_env()
        env.update({"ARTIFACTS_DIR": str(line), "WORKFLOW_ID": "line-run", "ARCHON_NODE_EXECUTION": json.dumps({"path": "test-gate"}),
                    "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "INPUTS_MODE": "base",
                    "INPUTS_START": json.dumps({"type": "archon_artifact", "run_id": "line-run", "path": "start/record.json"})})
        gate = subprocess.run([sys.executable, str(ROOT / "workflows" / "test-gate" / "scripts" / "run.py")], cwd=self.repo,
                              env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(gate.returncode, 0, gate.stderr)
        self.assertEqual(json.loads(gate.stdout)["material"]["status"], "clean", gate.stdout)
        self.assertEqual(self._grp_run("group_start", "group-start")["tdd"], True)
        self.assertEqual(len(count.read_text(encoding="utf-8").split()), 1)

    def test_tdd_prep_and_step_route_the_unit_change_between_the_two_roles(self):
        """tdd-prep は 1 周目と単位が替わる周だけ new_unit: true（新しい会話の役 tdd-new）、同じ単位の出し直しは false（続きの役
        tdd）。tdd-step は飛ばされた方の束ね（null）を読まず、起きた方の返答で段を進める（F032）"""
        self._grp_parent_inputs(str(self.suite))
        self._grp_run("group_start", "group-start")
        self.assertIs(self._grp_run("tdd_prep", "tdd-prep")["new_unit"], True)
        route = json.dumps({"phase": "route", "units": [{"unit_key": _GRP_MEAN, "route": "tdd"}]}, ensure_ascii=False)
        got = self._grp_run("tdd_step", "tdd-step", reply="null", reply_new=route)
        self.assertEqual((got["ok"], got["phase"]), (True, "test"), got)
        self.assertIs(self._grp_run("tdd_prep", "tdd-prep")["new_unit"], True, "振り分けから単位の段へ")
        bad = json.dumps({"phase": "test", "unit_key": _GRP_MEAN, "test_files": [], "tests": []}, ensure_ascii=False)
        got = self._grp_run("tdd_step", "tdd-step", reply="null", reply_new=bad)
        self.assertEqual((got["ok"], got["phase"]), (False, "test"), got)
        self.assertIs(self._grp_run("tdd_prep", "tdd-prep")["new_unit"], False, "同じ単位の出し直しは続きの会話")
        got = self._grp_run("tdd_step", "tdd-step", reply=bad, reply_new="null")
        self.assertEqual((got["ok"], got["phase"]), (False, "test"), got)
        state = json.loads((self.place / "tdd-start.json").read_text(encoding="utf-8"))["state_file"]
        calls = json.loads(pathlib.Path(state).read_text(encoding="utf-8"))["calls"]
        self.assertEqual([c["ok"] for c in calls], [True, False, False], "どちらの束ねの返答も 1 周 1 回の確かめ")

    def test_tdd_step_rejects_a_query_claim_when_the_judgment_is_unreadable(self):
        """TDD の輪の query の申し出も、修正役の受け付けと同じ口（fixboard.judge_query）で試す: 置き場の判定の写しが読めなければ
        「読めない」と名指して拒み、黙って積まない（K15）"""
        import fixboard
        self._grp_parent_inputs(str(self.suite))
        self._grp_run("group_start", "group-start")
        self._grp_step({"phase": "route", "units": [{"unit_key": _GRP_MEAN, "route": "tdd"}]})
        (self.place / fixboard.JUDGMENT_FILE).unlink()
        got = self._grp_step({"phase": "conflict", "unit_key": _GRP_MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                              "why_both_cannot_hold": "テストは分母 len(xs) - 1 の値を期待しているが、依頼は算術平均を求めている",
                              "which_is_right": "query", "kind": "query_hits_fixed",
                              "correct_lines": ["    return sum(xs) / (len(xs) - 1)"]})
        self.assertFalse(got["ok"], got)
        self.assertIn(f"{fixboard.JUDGMENT_FILE} が読めない", got["reason"])
        self.assertFalse((self.place / "conflicts.json").exists(), "拒んだ申し出は積まない")

    def test_tdd_step_takes_the_red_and_gives_up_on_the_third_refusal(self):
        """実行器が在る run: 振り分け → 名指しが failure で落ちる赤を受け → 直しの段で 3 回拒まれた単位は、単位の頭の木に戻して
        機械の申し出を置き場の conflicts.json に積み、輪を抜ける"""
        self._grp_parent_inputs(str(self.suite))
        out = self._grp_run("group_start", "group-start")
        self.assertEqual((out["tdd"], out["units"], out["reason"]), (True, 1, ""), out)
        prep = self._grp_run("tdd_prep", "tdd-prep")
        self.assertTrue(prep["go"])
        text = pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(_GRP_MEAN, text)
        self.assertIn("前の単位の引き継ぎ", text, "周ごとに新しい会話なので引き継ぎの節が載る")
        got = self._grp_step({"phase": "route", "units": [{"unit_key": _GRP_MEAN, "route": "tdd"}]})
        self.assertEqual((got["ok"], got["done"], got["phase"]), (True, False, "test"), got)
        test_file = self.repo / "test_stats.py"
        head = test_file.read_text(encoding="utf-8")
        test_file.write_text(head.replace("\n\nif __name__", _GRP_NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        got = self._grp_step({"phase": "test", "unit_key": _GRP_MEAN, "test_files": ["test_stats.py"],
                              "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertEqual((got["ok"], got["phase"], got["reason_file"]), (True, "fix", ""), got)
        self.assertTrue(self._grp_run("tdd_prep", "tdd-prep")["go"])
        fix = {"phase": "fix", "unit_key": _GRP_MEAN, "files": ["stats.py"], "what": "分母を直したつもり"}
        for n in (1, 2):
            got = self._grp_step(fix)
            self.assertEqual((got["ok"], got["done"]), (False, False), got)
            self.assertTrue(pathlib.Path(got["reason_file"]).is_file())
            self.assertIn(got["reason"].splitlines()[0], self._grp_prompt())
        got = self._grp_step(fix)
        self.assertEqual((got["ok"], got["done"], got["phase"]), (False, True, "done"), got)
        self.assertEqual(test_file.read_text(encoding="utf-8"), head, "単位の頭の木に戻した")
        rows = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([r["unit_key"] for r in rows], [_GRP_MEAN])
        self.assertEqual(self._grp_run("tdd_prep", "tdd-prep"), {"prompt_file": "", "go": False, "new_unit": False})
        end = self._grp_run("group_end", "group-end")
        result = json.loads(pathlib.Path(end["result_file"]).read_text(encoding="utf-8"))
        self.assertTrue(result["tdd"]["ran"])
        self.assertEqual([(u["unit_key"], u["gave_up"]) for u in result["tdd"]["units"]], [(_GRP_MEAN, "green")])
        self.assertEqual([(u["unit_id"], u["status"]) for u in result["units"]], [(_GRP_MEAN, "given_up")])
        self.assertEqual([r["unit_key"] for r in result["conflicts"]], [_GRP_MEAN])

    def _grp_prompt(self):
        return pathlib.Path(self._grp_run("tdd_prep", "tdd-prep")["prompt_file"]).read_text(encoding="utf-8")

    def _grp_green_loop(self):
        """実行器の在る子の run で TDD の輪を mean の単位の緑まで回し（route → test の赤 → fix の緑）、修正の輪の頭（fix-prep）を
        回す。返りはテストのファイル"""
        self._grp_parent_inputs(str(self.suite))
        self._grp_run("group_start", "group-start")
        self.assertEqual(self._grp_step({"phase": "route", "units": [{"unit_key": _GRP_MEAN, "route": "tdd"}]})["phase"], "test")
        test_file = self.repo / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("\n\nif __name__", _GRP_NEW_TEST + "\n\nif __name__"),
                             encoding="utf-8")
        got = self._grp_step({"phase": "test", "unit_key": _GRP_MEAN, "test_files": ["test_stats.py"],
                              "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertEqual((got["ok"], got["phase"]), (True, "fix"), got)
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        got = self._grp_step({"phase": "fix", "unit_key": _GRP_MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"})
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        self.assertTrue(self._grp_run("fix_prep", "fix-prep")["go"])
        return test_file

    def _grp_accept(self, reply):
        return self._grp_run("fix_accept", "fix-accept", reply=json.dumps(reply, ensure_ascii=False), consulted="false",
                             iteration="1")

    def test_fix_accept_rejects_a_change_to_a_loop_frozen_test(self):
        """輪の後の修正役が、TDD の輪で緑にした単位のテストのファイルの既存の行を変えた返答を、fix-accept が凍ったテストの確かめで
        拒み、そのファイルを名指す（accept_reply から factchecks.check_frozen を外すと赤）。元 works/blk-fix/lib/tddloop.py:1662
        frozen_problems・works/blk-fix/scripts/accept.py の 1b check_frozen"""
        import fixboard
        test_file = self._grp_green_loop()
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("mean([2, 4]), 3)", "mean([2, 4]), 3.0)"),
                             encoding="utf-8")
        out = self._grp_accept({"changes": [_fx_change(_GRP_MEAN, ["stats.py", "test_stats.py"])]})
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        head = fixboard.FIX_CHECK_HEAD.format(head=fixboard.FIX_CHECKS["frozen"], cid="frozen", count=1)
        self.assertIn(head, out["reason"])
        frozen = out["reason"].split(head, 1)[1].split("\n## ", 1)[0]
        self.assertIn("test_stats.py", frozen)

    def test_fix_accept_rejects_a_change_under_the_skip_head(self):
        """fix-prep が修正の段の頭に .archon/ の下の姿を控え（fixboard.record_skipped。除くパスの頭は boundary.SKIP）、fix-accept が
        その下を変えた返答を拒む（元 works/blk-fix/scripts/accept.py:234 check_pack_copy・:663）"""
        import fixboard
        copy = self.repo / ".archon" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("a: 1\n", encoding="utf-8")
        self._grp_green_loop()
        self.assertEqual(fixboard.read_json(self.place / fixboard.SKIP_BEFORE_FILE),
                         {".archon/workflows/x.yaml": fixboard.skip_digests(self.repo, (".archon/",))[".archon/workflows/x.yaml"]})
        copy.write_text("a: 2\n", encoding="utf-8")
        out = self._grp_accept({"changes": [_fx_change(_GRP_MEAN, ["stats.py"])]})
        self.assertFalse(out["ok"], out)
        head = fixboard.FIX_CHECK_HEAD.format(head=fixboard.FIX_CHECKS["pack"], cid="pack", count=1)
        self.assertIn(head, out["reason"])
        self.assertIn(".archon/workflows/x.yaml", out["reason"].split(head, 1)[1])

    def test_group_end_writes_the_result(self):
        """組の結果を out_dir/<group_id>/result.json に約束の形で書く（修正の輪の結末・返答の写し・許したテストを読む）"""
        import leftovers
        self._grp_run("group_start", "group-start")
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        (self.place / "fix-units.json").write_text(json.dumps({_GRP_MEAN: {"status": "fixed", "reason": ""}},
                                                              ensure_ascii=False), encoding="utf-8")
        (self.place / "fix-reply.json").write_text(json.dumps({"changes": [
            {"unit_key": _GRP_MEAN, "breaks": {"accepted": "空の列の平均の値が変わる"}}], "gates_changed": True,
                                                               "rejudge_requested": "単位の見立てが違う",
                                                               "premise_drift_note": "上限を測り直した", "x_scalars": {"x_moved": 2}},
                                                              ensure_ascii=False), encoding="utf-8")
        import conflict
        agreed = {"op": conflict.ASKED_OP, "id": 1, "item": "1", "status": "answered", "decision": "allow",
                  "granted_paths": [], "granted_tests": ["test_stats.py"], "granted_new_tests": [], "reason": "許した"}
        (self.place / "trace.jsonl").write_text(json.dumps(agreed, ensure_ascii=False) + "\n", encoding="utf-8")
        closure = {"unit_key": _GRP_MEAN, "closed": True, "discrepancies": []}
        (self.place / "fix-unit-rows.json").write_text(json.dumps({"round": 1, "rows": [closure]}), encoding="utf-8")
        import fixbeside
        import fixboard
        notice = {"op": fixbeside.TESTS_OP, "ci_left": [], "final_left": ["test_far.py"], "final_far": []}
        fixboard.write_json(self.place / fixboard.ACCEPT_TRACE_FILE, [notice])
        out = self._grp_run("group_end", "group-end")
        self.assertEqual(out["result_file"], str(self.out_dir / "g1" / "result.json"))
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(set(result), {"group_id", "unit_ids", "end_tree", "start_tree", "units", "tdd", "conflicts",
                                       "objection", "changed", "x_scalars", "allowed_tests", "verified",
                                       "reply_file", "tdd_state", "worktree", "handoffs", "mismatched", "accept_trace", "closure",
                                       "claimed", "place"})
        # F427・F428・F013: 子の置き場の受け入れた壊れ・閉鎖の表・受け付けの知らせを、親の collect へ結果で運ぶ
        self.assertEqual((result["handoffs"], result["claimed"], result["closure"]),
                         ([f"{_GRP_MEAN}: 壊すと分かって通した——空の列の平均の値が変わる"], [_GRP_MEAN], [closure]))
        self.assertEqual(result["accept_trace"], [{**notice, "group_id": "g1"}, {**agreed, "group_id": "g1"}])
        self.assertEqual(result["tdd_state"], "", "輪の無い組")
        self.assertEqual(result["worktree"], os.path.realpath(self.repo))
        self.assertEqual(result["units"], [{"unit_id": _GRP_MEAN, "status": "fixed", "reason": ""}])
        self.assertEqual(result["end_tree"], leftovers.snapshot(self.repo))
        self.assertNotEqual(result["end_tree"], result["start_tree"])
        self.assertEqual((result["tdd"]["ran"], result["tdd"]["units"]), (False, []))
        self.assertEqual(result["changed"], {**{k: k == "gates_changed" for k in CHANGED_MARKS}, "premise_drift_note": "上限を測り直した"})
        self.assertEqual(result["x_scalars"], {"x_moved": 2})
        self.assertEqual((result["objection"], [t["path"] for t in result["allowed_tests"]], result["verified"], result["conflicts"]),
                         ("単位の見立てが違う", ["test_stats.py"], [], []))
        self.assertEqual(result["reply_file"], str(self.place / "fix-reply.json"))
        self.assertEqual(result["place"], str(self.place), "親の conflict-check がこの組の名指しに許す根")

    def test_group_end_lists_allowed_tests_only_for_an_accepted_reply(self):
        """受け付けが通らず fix-reply.json が無い組は、置き場に許しが在っても許しの訳 allowed_tests を
        空にする（#286。join の和と親の collect が同じ欄から読む）。相談の 1 問 1 答の行は accept_trace に残る"""
        import conflict
        self._grp_run("group_start", "group-start")
        agreed = {"op": conflict.ASKED_OP, "id": 1, "item": "1", "status": "answered", "decision": "allow",
                  "granted_paths": [], "granted_tests": ["test_stats.py"], "granted_new_tests": [], "reason": "許した"}
        (self.place / "trace.jsonl").write_text(json.dumps(agreed, ensure_ascii=False) + "\n", encoding="utf-8")
        out = self._grp_run("group_end", "group-end")
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual((result["allowed_tests"], result["reply_file"]), ([], ""))
        self.assertEqual(result["accept_trace"], [{**agreed, "group_id": "g1"}])

    def test_refix_child_sees_the_first_pass_and_returns_only_its_rows(self):
        """L-W18・F023: 2 度目の修正の段の組の子は、親の置き場が写した 1 回目の段の申し出と裁定（印 prior_pass）を写して読み
        （conflict.second_pass が真）、結果の conflicts にはこの段の行だけを載せる（親の conflict-check が 1 回目の行を積み直さない）"""
        import conflict
        first = self.tmp / "first"
        first.mkdir()
        row = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": _GRP_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
               "why_both_cannot_hold": "案の項目が判定と食い違う", "which_is_right": "request", "kind": "brief_vs_judgment",
               "status": "ruled", "replan": "waiting",
               "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "plan_items": [1], "by": "ruler"}}
        (first / "conflicts.json").write_text(json.dumps({"items": [row]}, ensure_ascii=False), encoding="utf-8")
        conflict.adopt_prior(self.parent, first, ["1"])
        self._grp_run("group_start", "group-start")
        self.assertTrue(conflict.second_pass(self.place))
        new = conflict.park(self.place, [{"unit_key": _GRP_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                          "why_both_cannot_hold": "直した後も分母が空の列で割れる", "which_is_right": "unknown",
                                          "kind": "needs_context"}], source=conflict.FIX_SOURCE)
        out = self._grp_run("group_end", "group-end")
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in result["conflicts"]], new)

    def test_group_end_carries_permits_mismatches_and_accept_notices_to_the_parent_collect(self):
        """修正役の返答を受け付けた組の子の置き場の許しの訳（F429）・申告と数え直しが合わない単位（追記 00:00）・受け付けが選んだ試験の知らせ（F014）は
        group-end が組の結果に載せ、親の collect が返りの diff の隣の allowed-tests.json・返りの mismatched・accept-trace.json に集める
        （組の子でだけ走る受け付けの知らせが親の diff の隣に届く）"""
        import conflict
        import fixboard
        import querytest
        self._grp_run("group_start", "group-start")
        conflict.park(self.place, [{"unit_key": _GRP_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_test_scope", "text": "期待を直してよい",
                                                          "limits": ["test_stats.py:8"]})
        (self.place / querytest.CLOSURE_FILE).write_text(json.dumps({"round": 1, "rows": [
            {"unit_key": _GRP_MEAN, "closed": True, "discrepancies": ["申告の数が問いの数と合わない"]}]}, ensure_ascii=False),
            encoding="utf-8")
        notice = {"op": "fix_tests_selected", "node": "fix-accept", "pass": "first", "attempt": 1,
                  "note": "選んだ試験が 0 件しか走らなかった", "ci_left": [], "final_left": [], "final_far": []}
        (self.place / fixboard.ACCEPT_TRACE_FILE).write_text(json.dumps([notice], ensure_ascii=False), encoding="utf-8")
        (self.place / fixboard.FIX_REPLY_FILE).write_text(json.dumps({"changes": []}), encoding="utf-8")
        result = json.loads(pathlib.Path(self._grp_run("group_end", "group-end")["result_file"]).read_text(encoding="utf-8"))
        permit = {"path": "test_stats.py", "permit": f"{conflict.RULED_TEST_ID}-c1-1", "source": "ruling"}
        self.assertEqual(result["allowed_tests"], [permit])
        self.assertEqual(len(result["mismatched"]), 1, result["mismatched"])
        self.assertIn("合わない: 申告の数が問いの数と合わない", result["mismatched"][0])
        child_notice = {**notice, "group_id": "g1"}
        self.assertEqual(result["accept_trace"], [child_notice])

        parent_art = self.parent.parent.parent
        start = result["start_tree"]
        _blk_write(self.parent / fixboard.GROUPS_FILE, {"groups": [_GRP_GROUP], "count": 1, "par": False, "start_tree": start,
                                                       "out_dir": str(self.out_dir)})
        _blk_write(self.parent / fixboard.JOIN_FILE, {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": [_GRP_MEAN], "returned": True, "reason": ""}],
            "units": [{"unit_id": _GRP_MEAN, "group_id": "g1", "status": "fixed", "reason": ""}]})
        own = {**notice, "pass": "ruled", "node": "fix-ruled-accept"}
        _blk_write(self.parent / fixboard.ACCEPT_TRACE_FILE, [own])
        for _ in range(2):   # 回し直しても行を重ねない
            code, out, err = _blk_run("collect", self.repo, parent_art)
            self.assertEqual(code, 0, err)
            beside = (parent_art / out["diff"]["path"]).parent
            self.assertEqual(json.loads((beside / fixboard.ACCEPT_TRACE_FILE).read_text(encoding="utf-8")), [child_notice, own])
            self.assertEqual(json.loads((beside / fixboard.ALLOWED_TESTS_FILE).read_text(encoding="utf-8")), [permit])
            self.assertEqual(out["allowed_test_changes"], ["test_stats.py"])
            self.assertEqual(out["mismatched"], result["mismatched"])

    def test_group_child_starts_its_log_and_reports_where_join_finds_it(self):
        """並べた子は自分の作業ツリーの記録を group-start で空で作り、group-end の結果の worktree から join が同じ記録を引く"""
        import writelog
        env, root = _recorder_root(self.tmp)
        self.grp_env = env
        self._grp_run("group_start", "group-start")
        log = writelog.log_path(root, self.repo)
        self.assertEqual(log.read_text(encoding="utf-8"), "")
        result = json.loads(pathlib.Path(self._grp_run("group_end", "group-end")["result_file"]).read_text(
            encoding="utf-8"))
        self.assertEqual(writelog.log_path(root, result["worktree"]), log)

    def test_group_end_alone_writes_into_its_own_place(self):
        """out_dir が空の単独の run は自分の置き場の groups/<group_id>/ に書く（collect も同じ所を読む）"""
        out = self._grp_run("group_end", "group-end", out_dir="")
        self.assertEqual(out["result_file"], str(self.place / "groups" / "g1" / "result.json"))
        self.assertFalse((self.place / "result.json").exists())
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(result["units"][0]["status"], "not_done")
        self.assertIn("group-start", result["tdd"]["reason"])

    def test_group_start_alone_places_the_inputs_it_points_to(self):
        """out_dir が空の単独の run は、自分の run の指し札の先の始めの記録と判定を自分の置き場に写す（節 prep と同じ写し）"""
        self.art.mkdir(parents=True, exist_ok=True)
        inputs = {"start": {"tdd_suite": "", "run_id": _GRP_RUN},
                  "judgment": {"units": [{"key": _GRP_MEAN, "label": "block"}], "questions": []}}
        pointers = {}
        for name, doc in inputs.items():
            (self.art / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            pointers[name] = json.dumps({"type": "archon_artifact", "run_id": _GRP_RUN, "path": f"{name}.json"})
        out = self._grp_run("group_start", "group-start", out_dir="", **pointers)
        self.assertEqual((out["tdd"], out["units"]), (False, 1), out)
        self.assertEqual(json.loads((self.place / "r1" / "start.json").read_text(encoding="utf-8"))["run_id"], _GRP_RUN)
        self.assertEqual(json.loads((self.place / "judgment.json").read_text(encoding="utf-8"))["units"][0]["key"], _GRP_MEAN)


# ---------------------------------------------------------------- 修正の輪と裁定の輪の script（fix_prep・fix_accept・fix_ruled_prep・
# fix_ruled_accept・consult_check・consult_accept・rule_prep・rule_accept）

_FX_RUN = "wf-fx"
_FX_MEAN = "u-mean"     # 判定者の問いの在る単位（stats.py の mean の分母）
_FX_BOUND = "u-bound"   # 判定者の問いの無い単位（coverage.how が無いと数え直しが名指して拒む）
_FX_JUDGMENT = {"units": [
    {"key": _FX_MEAN, "label": "block", "class_query": {
        "how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
        "counts": "defects", "total": 1}},
    {"key": _FX_BOUND, "label": "block"}], "questions": []}


def _fx_run(script, repo, art, *, env_extra=None, **inputs):
    """scripts/<script>.py を一時の対象のリポジトリ repo・一時の置き場 art で起こす。(終了の値, 標準出力の JSON か None, 標準エラー)。
    env_extra は子の環境に足す"""
    env = hermetic.child_env()
    env.update({"ARTIFACTS_DIR": str(art), "WORKFLOW_ID": _FX_RUN, "WORKS_FACTORY_ROOT": str(ROOT),
                "ARCHON_NODE_EXECUTION": json.dumps({"path": "x"}), "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(env_extra or {})
    env.update({f"INPUTS_{k.upper()}": v for k, v in inputs.items()})
    done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{script}.py")], cwd=repo, env=env,
                          capture_output=True, text=True, encoding="utf-8")
    try:
        out = json.loads(done.stdout)
    except ValueError:
        out = None
    return done.returncode, out, done.stderr


def _fx_change(unit, files, **extra):
    """修正役の返答の changes の 1 行（closure の site は 1 つ。自己申告の欄は lib/tests/test_fix_seams.py の SELF_REPORT）"""
    from lib.tests.test_fix_seams import SELF_REPORT
    return {"unit_key": unit, "files": files, "what": "直した", **SELF_REPORT, **extra,
            "closure": {"mechanism": "分母", "fix_mechanism": "len(xs)", "verified_how": "読んだ",
                        "sites": [{"site": f"{files[0]}:9", "red_seen": True}]}}


class FixLoopPlace(unittest.TestCase):
    """修正の輪の script を起こす一時の対象のリポジトリと置き場（$ARTIFACTS_DIR/fix/fix/。組の子の置き場の形）"""

    def setUp(self):
        from tests.bin.gitkit import committed_copy
        import leftovers
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-fix-loop-"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, ROOT / "tests" / "e2e" / "target-seed")
        self.art = self.tmp / "art"
        self.place = self.art / "fix" / "fix"
        self.place.mkdir(parents=True)
        self._fx_json("judgment.json", _FX_JUDGMENT)
        self._fx_json("r1/start.json", {"tdd_suite": "", "test_cmd": "", "policy_md": "", "request_file": "",
                                         "features_cut": []})
        leftovers.record_ignored(self.place, self.repo)   # 段の頭の木（group-start が取る物）

    def _fx_json(self, name, doc):
        path = self.place / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def _fx_fix_mean(self):
        path = self.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("sum(xs) / (len(xs) - 1)", "sum(xs) / len(xs)"),
                        encoding="utf-8")

    def _fx_accept(self, script, reply, iteration, **extra):
        code, out, err = _fx_run(script, self.repo, self.art, reply=json.dumps(reply, ensure_ascii=False),
                                 consulted="false", iteration=str(iteration), **extra)
        self.assertEqual(code, 0, err)
        return out

    def _fx_group(self, units):
        return json.dumps({"group_id": "g1", "unit_ids": units, "items": []})


class FixLoopScriptsCase(FixLoopPlace):
    """修正の輪・裁定の後の修正の輪・範囲の相談・裁定の輪の script を、一時の対象のリポジトリと一時の置き場で起こす"""

    def test_third_reject_gives_up_only_the_named_unit(self):
        """3 回目の拒否で、拒否が名指す単位だけを段の頭の木に戻して諦め、ほかの単位の直しを受けて輪を抜ける（fix.md 192 行）"""
        self._fx_fix_mean()
        (self.repo / "bounds.py").write_text("def bound(x):\n    return x\n", encoding="utf-8")
        reply = {"changes": [_fx_change(_FX_MEAN, ["stats.py"]), _fx_change(_FX_BOUND, ["bounds.py"])]}
        group = self._fx_group([_FX_MEAN, _FX_BOUND])
        for n in (1, 2):
            out = self._fx_accept("fix_accept", reply, n, group=group)
            self.assertEqual((out["ok"], out["done"]), (False, False), out)
            self.assertIn(_FX_BOUND, out["reason"])
            self.assertTrue(pathlib.Path(out["reason_file"]).is_file())
        out = self._fx_accept("fix_accept", reply, 3, group=group)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        units = json.loads((self.place / "fix-units.json").read_text(encoding="utf-8"))
        self.assertEqual({k: v["status"] for k, v in units.items()}, {_FX_MEAN: "fixed", _FX_BOUND: "given_up"})
        self.assertFalse((self.repo / "bounds.py").exists(), "諦めた単位の直しは段の頭の木に戻す")
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"), "ほかの単位の直しは残す")
        self.assertIn("bounds.py", (self.place / "fix-parked-1.patch").read_text(encoding="utf-8"))
        rows = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([(r["unit_key"], r["ruling"]["decision"]) for r in rows], [(_FX_BOUND, "ask_human")])
        kept = json.loads((self.place / "fix-reply.json").read_text(encoding="utf-8"))
        self.assertEqual([c["unit_key"] for c in kept["changes"]], [_FX_MEAN])
        self.assertEqual(set(kept["changed"]), set(CHANGED_MARKS) | {"premise_drift_note"})

    def test_accept_traces_tests_left_to_ci_and_final_stage(self):
        """F013: 受け付けの回ごとに accept-trace.json に impact.ACCEPT_TRACE_OP の行（手元で回さなかった試験 ci_left・最後のテストの段に
        任せた試験 final_left・final_far。元 works/blk-fix/scripts/accept.py:708）を積み、読み手（fixbeside）は組と段ごとに最後の回
        ＝受けた回の行を読む（元は受けた回だけを積んだ）。名は輪の状態から引く"""
        import fixbeside
        import fixboard
        import impact
        self._fx_fix_mean()
        self._fx_accept("fix_accept", {"changes": []}, 1, group=self._fx_group([_FX_MEAN]))
        out = self._fx_accept("fix_accept", {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}, 2, group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        rows = [r for r in fixboard.accept_trace_rows(self.place) if r["op"] == impact.ACCEPT_TRACE_OP]
        self.assertEqual([(r["pass"], r["attempt"]) for r in rows], [("first", 1), ("first", 2)])
        self.assertEqual([(r["attempt"], r["ci_left"], r["final_left"]) for r in fixbeside._accepted_tests(rows)], [(2, [], [])])
        state = self._fx_json("tdd-state.json", {"ci_left": ["tests/test_slow.py"], "final_left": ["tests/test_far.py"],
                                                 "final_far": ["lib/far.py"]})
        fixboard.tests_trace(self.place, str(state), "", pass_="ruled", attempt=1)
        last = [r for r in fixboard.accept_trace_rows(self.place) if r["op"] == impact.ACCEPT_TRACE_OP][-1]
        self.assertEqual((last["ci_left"], last["final_left"], last["final_far"]),
                         (["tests/test_slow.py"], ["tests/test_far.py"], ["lib/far.py"]))

    def test_accept_traces_skipped_gates(self):
        """F041: 事後の関門の束が受け入れのテストの赤緑を確かめずに受けた回（帳面の skipped。実行器の無い run の fixgates.NO_SUITE
        ほか）は、受けた回の置き場の trace に fixgates.SKIPPED_OP（fix_gates_skipped）の行と訳を積み（義務の外 OUT_OF_DUTY は除く。
        fixboard.gates_trace）、accept_trace_rows が diff の隣の accept-trace.json へ運び、報告と最後の承認ノードが「受け付け N 回・理由」で数える"""
        import fixbeside
        import fixboard
        import fixgates
        self._fx_fix_mean()
        out = self._fx_accept("fix_accept", {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}, 1, group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual([r for r in fixboard.accept_trace_rows(self.place) if r["op"] == fixgates.SKIPPED_OP], [],
                         "受け入れのテストの無い項目は確かめる物が無い")
        fixgates._record(self.place, {"pass": "first", "attempt": 2},
                         {"skipped": [{"why": fixgates.NO_SUITE}, {"why": fixgates.OUT_OF_DUTY}]})
        fixboard.gates_trace(self.place, pass_="first", attempt=2)
        rows = [r for r in fixboard.accept_trace_rows(self.place) if r["op"] == fixgates.SKIPPED_OP]
        self.assertEqual([r["why"] for r in rows], [[fixgates.NO_SUITE]])
        self.assertEqual(fixbeside.gates_lines({"trace": rows}),
                         [f"事後の関門の束: 受け付け 1 回が受け入れのテストの赤緑を確かめずに通した（理由: {fixgates.NO_SUITE}）"])

    def test_undeclared_change_is_rejected(self):
        """書き込みの記録が無い run は、段の頭の木からの変更が changes[].files にも bash_writes にも無ければ拒む（U6 の狭めの照らし）"""
        import fixboard
        self._fx_fix_mean()
        (self.repo / "scratch.txt").write_text("下書き\n", encoding="utf-8")
        out = self._fx_accept("fix_accept", {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}, 1,
                              group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertIn(fixboard.UNDECLARED + "scratch.txt", out["reason"])
        declared = {"changes": [_fx_change(_FX_MEAN, ["stats.py"])],
                    "bash_writes": [{"path": "scratch.txt", "why": "Bash で生成した下書きのファイル"}]}
        out = self._fx_accept("fix_accept", declared, 2, group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def _fx_accept_env(self, env, reply, iteration, script="fix_accept"):
        group = {"group": self._fx_group([_FX_MEAN])} if script == "fix_accept" else {}
        code, out, err = _fx_run(script, self.repo, self.art, env_extra=env, reply=json.dumps(reply, ensure_ascii=False),
                                 consulted="false", iteration=str(iteration), **group)
        self.assertEqual(code, 0, err)
        return out

    def test_accept_rejects_unrecorded_change_when_log_exists(self):
        """記録の根が在る run（記録の在る run）は、修正の受け付けも裁定の後の修正の受け付けも、記録も申告も無い変更を拒み、
        記録が在れば通す（keep-essence の 5）"""
        import writelog
        import writes
        env, root = _recorder_root(self.tmp)
        log = writelog.log_path(root, self.repo)
        log.parent.mkdir()
        reply = {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}
        for script in ("fix_accept", "fix_ruled_accept"):
            with self.subTest(script=script):
                git(self.repo, "checkout", "--", "stats.py")
                log.write_text("", encoding="utf-8")   # 始めの節（prep・group-start）が作る物
                if script == "fix_ruled_accept":   # 直す義務は戻せた組の fixed でない単位だけ
                    self._fx_json("join.json", {
                        "groups": [{"group_id": "g1", "unit_ids": [_FX_MEAN, _FX_BOUND], "returned": True, "reason": ""}],
                        "units": [{"unit_id": _FX_MEAN, "group_id": "g1", "status": "not_done", "reason": ""},
                                  {"unit_id": _FX_BOUND, "group_id": "g1", "status": "fixed", "reason": ""}]})
                self._fx_fix_mean()
                out = self._fx_accept_env(env, reply, 1, script)
                self.assertEqual((out["ok"], out["done"]), (False, False), out)
                self.assertIn(writes.REJECT + "stats.py", out["reason"])
                _record(log, self.repo / "stats.py")
                out = self._fx_accept_env(env, reply, 2, script)
                self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_no_recorder_root_keeps_no_record_path(self):
        """記録の根が無い起動は記録の無い run の道（記録を求めず、段の頭からの変更を申告に縛る）のまま"""
        cfg = self.tmp / "claude-config"
        cfg.mkdir()
        self._fx_fix_mean()
        out = self._fx_accept_env({"CLAUDE_CONFIG_DIR": str(cfg)}, {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}, 1)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual(list(cfg.iterdir()), [], "根も記録も作らない")

    def test_tdd_loop_writes_are_not_the_fixers(self):
        """修正の段の頭は TDD の輪の後の木（fix-prep が 1 回目に控える）。輪が書いた物を修正役の申告に求めない"""
        (self.repo / "tdd_note.txt").write_text("TDD の輪が書いた物\n", encoding="utf-8")
        code, out, err = _fx_run("fix_prep", self.repo, self.art, group=self._fx_group([_FX_MEAN]))
        self.assertEqual(code, 0, err)
        self.assertTrue((self.place / "fix-head.json").is_file())
        self._fx_fix_mean()
        out = self._fx_accept("fix_accept", {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}, 1,
                              group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertTrue((self.repo / "tdd_note.txt").is_file())

    def test_ruled_fixer_head_is_the_ruled_prep_tree(self):
        """#332: 裁定の後の修正の段の頭は fix-ruled-prep が控える木。1 回目の修正の段の頭（fix-head.json）の後に書かれた物を
        裁定の後の修正役の申告に求めない（事前の確かめと同じ木を受け付けも読む）"""
        import conflict
        code, _, err = _fx_run("fix_prep", self.repo, self.art, group=self._fx_group([_FX_MEAN]))
        self.assertEqual(code, 0, err)
        (self.repo / "tdd_note.txt").write_text("1 回目の修正・join が書いた物\n", encoding="utf-8")
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_test_scope", "text": "テストの期待を直してよい",
                                                          "limits": ["test_stats.py"]})
        code, _, err = _fx_run("fix_ruled_prep", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self._fx_json("join.json", {"groups": [{"group_id": "g1", "unit_ids": [_FX_MEAN], "returned": True, "reason": ""}],
                                    "units": [{"unit_id": _FX_MEAN, "group_id": "g1", "status": "not_done", "reason": ""}]})
        self._fx_fix_mean()
        out = self._fx_accept("fix_ruled_accept", {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}, 1)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_consulted_turn_and_skipped_fixer(self):
        out = self._fx_accept("fix_accept", {"changes": []}, 1, group=self._fx_group([_FX_MEAN]))
        self.assertFalse(out["ok"])
        code, out, err = _fx_run("fix_accept", self.repo, self.art, reply="{}", consulted="true", iteration="1",
                                 group=self._fx_group([_FX_MEAN]))
        self.assertEqual((code, out["ok"], out["done"]), (0, False, False), err)
        code, out, err = _fx_run("fix_accept", self.repo, self.art, reply="null", consulted="false", iteration="1",
                                 group=self._fx_group([_FX_MEAN]))
        self.assertEqual((code, out["ok"], out["done"]), (0, True, True), err)

    def test_ruled_pass_allows_ruled_test_scope_and_first_does_not(self):
        """裁定 fix_test_scope の limits のテストの変更を、親の置き場の裁定の後の受け付け（ruled）は通し、組の子の置き場の 1 回目
        （first）は通さない"""
        import conflict
        import leftovers
        child_art = self.tmp / "child-art"
        child = child_art / "fix" / "fix"
        child.mkdir(parents=True)
        for name in ("judgment.json", "r1/start.json"):
            (child / name).parent.mkdir(parents=True, exist_ok=True)
            (child / name).write_bytes((self.place / name).read_bytes())
        leftovers.record_ignored(child, self.repo)
        self._fx_fix_mean()
        path = self.repo / "test_stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("mean([1, 2, 3]), 2", "mean([2, 4]), 3"), encoding="utf-8")
        reply = {"changes": [_fx_change(_FX_MEAN, ["stats.py", "test_stats.py"])]}
        code, out, err = _fx_run("fix_accept", self.repo, child_art, reply=json.dumps(reply, ensure_ascii=False),
                                 consulted="false", iteration="1", group=self._fx_group([_FX_MEAN]))
        self.assertEqual((code, out["ok"]), (0, False), err or out)
        self.assertIn("test_stats.py", out["reason"])
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_test_scope", "text": "テストの期待を直してよい",
                                                          "limits": ["test_stats.py"]})
        self._fx_json("join.json", {"groups": [{"group_id": "g1", "unit_ids": [_FX_MEAN, _FX_BOUND], "returned": True,
                                                "reason": ""}],
                                    "units": [{"unit_id": _FX_MEAN, "group_id": "g1", "status": "not_done", "reason": ""},
                                              {"unit_id": _FX_BOUND, "group_id": "g1", "status": "fixed", "reason": ""}]})
        out = self._fx_accept("fix_ruled_accept", reply, 1)   # 直す義務は戻せた組の fixed でない単位だけ
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        kept = json.loads((self.place / "fix-ruled-reply.json").read_text(encoding="utf-8"))
        self.assertEqual(set(kept["changed"]), set(CHANGED_MARKS) | {"premise_drift_note"})

    @unittest.skipIf(os.geteuid() == 0, "root は読めない印のファイルも読める")
    def test_prep_snapshots_the_skip_head_before_marking_the_stage_head(self):
        """F107: 段の頭の印（fix-head.json・fix-ruled-head.json）は .archon/ の下の控え skip-before.json を書いた後に置く。控えを
        書けずに落ちた prep を回し直すと控えも書く（印だけが残ると check_pack_copy が申告だけを見る形に黙って弱まる）"""
        import conflict
        import fixboard
        copy = self.repo / ".archon" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("a: 1\n", encoding="utf-8")
        with open(self.repo / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write(".archon/\n")   # 木の姿（git add）は読まず、控え（skip_digests）だけが読んで落ちる
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_test_scope", "text": "テストの期待を直してよい",
                                                          "limits": ["test_stats.py"]})
        for script, head, extra in (("fix_prep", fixboard.FIX_HEAD_FILE, {"group": self._fx_group([_FX_MEAN])}),
                                    ("fix_ruled_prep", fixboard.RULED_HEAD_FILE, {})):
            with self.subTest(script=script):
                (self.place / fixboard.SKIP_BEFORE_FILE).unlink(missing_ok=True)
                copy.chmod(0)
                try:
                    code, _, err = _fx_run(script, self.repo, self.art, **extra)
                finally:
                    copy.chmod(0o644)
                self.assertNotEqual(code, 0, "控えが書けない prep は落ちる")
                self.assertIn("x.yaml", err)
                self.assertFalse((self.place / head).exists(), "控えの無いまま段の頭の印を置かない")
                code, _, err = _fx_run(script, self.repo, self.art, **extra)
                self.assertEqual(code, 0, err)
                self.assertIn(".archon/workflows/x.yaml", fixboard.read_json(self.place / fixboard.SKIP_BEFORE_FILE))
                self.assertTrue((self.place / head).is_file())

    def test_third_fix_prompt_names_every_reject_of_the_loop(self):
        """どの回の修正役も輪の拒否の全部を読む（#345）。修正の輪と裁定の後の修正の輪で 2 回続けて拒まれた後の 3 回目の指示書が名指す
        ファイルに、1 回目と 2 回目の拒否の理由が古い順に在る（#345）"""
        import conflict
        named = re.compile(re.escape(rolekit.REJECT_LINE.partition("{path}")[0]) + r"(\S+?) ")
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_test_scope", "text": "テストの期待を直してよい",
                                                          "limits": ["test_stats.py"]})
        self._fx_json("join.json", {"groups": [{"group_id": "g1", "unit_ids": [_FX_MEAN, _FX_BOUND], "returned": True,
                                                "reason": ""}],
                                    "units": [{"unit_id": _FX_MEAN, "group_id": "g1", "status": "not_done", "reason": ""},
                                              {"unit_id": _FX_BOUND, "group_id": "g1", "status": "fixed", "reason": ""}]})
        group = {"group": self._fx_group([_FX_MEAN])}
        for prep, accept, extra in (("fix_prep", "fix_accept", group), ("fix_ruled_prep", "fix_ruled_accept", {})):
            with self.subTest(prep=prep):
                reasons = []
                for k, reply in ((1, {"changes": []}), (2, {"changes": [_fx_change(_FX_BOUND, ["bounds.py"])]})):
                    code, out, err = _fx_run(prep, self.repo, self.art, **extra)
                    self.assertEqual((code, out["iteration"]), (0, k), err)
                    bad = self._fx_accept(accept, reply, k, **extra)
                    self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
                    reasons.append(bad["reason"])
                self.assertNotEqual(*reasons)
                code, out, err = _fx_run(prep, self.repo, self.art, **extra)
                self.assertEqual((code, out["iteration"]), (0, 3), err)
                files = named.findall(pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8"))
                self.assertEqual(len(files), 1, files)
                text = pathlib.Path(files[0]).read_text(encoding="utf-8")
                self.assertLess(text.index(reasons[0]), text.index(reasons[1]), "1 回目の拒否も古い順に届く")

    def test_fix_ruled_prep_without_fix_ruling_does_not_launch(self):
        import conflict
        code, out, err = _fx_run("fix_ruled_prep", self.repo, self.art)
        self.assertEqual((code, out), (0, {"prompt_file": "", "go": False, "iteration": 1}), err)
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "材料から決められない食い違いが在る",
                                    "which_is_right": "unknown", "kind": "needs_context"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "ask_human", "text": "人が決める", "limits": []})
        code, out, err = _fx_run("fix_ruled_prep", self.repo, self.art)
        self.assertEqual((code, out["go"]), (0, False), err)

    def test_fix_ruled_prep_names_the_saved_reply_and_rulings(self):
        """直す裁定が在れば、組の修正役の返答の控えと裁定の文のファイルを名指す新しい会話の指示書を組む"""
        import conflict
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_code_as", "text": "分母を len(xs) にせよ",
                                                          "limits": []})
        out_dir = self.place / "groups"
        child = self.tmp / "child-reply.json"
        child.write_text(json.dumps({"changes": [_fx_change(_FX_MEAN, ["stats.py"])], "not_done": []}), encoding="utf-8")
        self._fx_json("groups/g1/result.json", {"group_id": "g1", "reply_file": str(child)})
        self._fx_json("groups.json", {"groups": [{"group_id": "g1", "unit_ids": [_FX_MEAN], "items": []}], "count": 1,
                                      "par": False, "start_tree": "", "out_dir": str(out_dir)})
        code, out, err = _fx_run("fix_ruled_prep", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual((out["go"], out["iteration"]), (True, 1), out)
        text = pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(str(self.place / "fix-reply.json"), text)
        self.assertIn(conflict.RULINGS_FILE, text)
        self.assertTrue((self.place / "fix-ruled-head.json").is_file())

    def test_first_pass_conflict_leaves_the_loop_for_ruling(self):
        """1 回目の受け付けが裁かれていない申し出を積むと、輪を抜け（done: true）単位は not_done で裁定へ回る"""
        import conflict
        reply = {"changes": [], "conflicts": [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                               "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                               "which_is_right": "request", "kind": "unnamed_test_broke"}]}
        out = self._fx_accept("fix_accept", reply, 1, group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual([r["unit_key"] for r in conflict.unruled(self.place)], [_FX_MEAN])
        units = json.loads((self.place / "fix-units.json").read_text(encoding="utf-8"))
        self.assertEqual(units[_FX_MEAN]["status"], "not_done")

    def test_ruled_new_claim_is_parked_as_ask_human(self):
        """F207: 裁定の後の受け付け（fix-ruled-accept）の新しい申し出は、裁定の輪がもう無いので機械が ask_human に裁いて積み
        （by fix-accept）、返答がほかの確かめで拒まれても積んだまま残す（元 works/blk-fix/scripts/accept.py:18-24・:340-344）"""
        import conflict
        import fixboard
        self._fx_json("join.json", {"groups": [{"group_id": "g1", "unit_ids": [_FX_MEAN, _FX_BOUND], "returned": True,
                                                "reason": ""}],
                                    "units": [{"unit_id": _FX_MEAN, "group_id": "g1", "status": "not_done", "reason": ""},
                                              {"unit_id": _FX_BOUND, "group_id": "g1", "status": "not_done", "reason": ""}]})
        (self.repo / "bounds.py").write_text("def bound(x):\n    return x\n", encoding="utf-8")
        reply = {"changes": [_fx_change(_FX_BOUND, ["bounds.py"])],
                 "conflicts": [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                                "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                "which_is_right": "request", "kind": "unnamed_test_broke"}]}
        out = self._fx_accept("fix_ruled_accept", reply, 1)
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertIn(_FX_BOUND, out["reason"], "ほかの確かめの拒否")
        rows = conflict.items(self.place)
        self.assertEqual([(r["unit_key"], r["ruling"]["decision"], r["ruling"]["by"], r["ruling"]["text"]) for r in rows],
                         [(_FX_MEAN, conflict.ASK, fixboard.FIX_ACCEPT_BY, fixboard.SECOND_CONFLICT)], "拒否の後も積んだまま残す")
        self.assertEqual(conflict.unruled(self.place), [])
        self.assertTrue((self.place / conflict.RULINGS_FILE).is_file())

    def test_consult_check_launches_the_answer_on_an_ask(self):
        """返答の consult の頼みで答えの役の指示書を書いて go: true、答えを受けて答えのファイルを書く"""
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": ["stats.py"],
                                         "out_of_scope": []}])
        self._fx_json("p2.fix_plan.json", {"plan": [{"unit_keys": [_FX_MEAN], "approach": "分母を直す", "adds": [],
                                                      "removes": []}]})
        reply = {"changes": [], "consult": [{"item": 1, "paths": ["docs/notes.md"], "tests": [],
                                             "why": "直しに伴う変更の記録を docs に残す要がある（範囲の外）"}]}
        code, out, err = _fx_run("consult_check", self.repo, self.art, reply=json.dumps(reply, ensure_ascii=False),
                                 **{"pass": "first"})
        self.assertEqual(code, 0, err)
        self.assertEqual((out["consulted"], out["go"]), (True, True), out)
        text = pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(str(self.place / "p2.fix_plan.json"), text)
        self.assertIn("docs/notes.md", text)
        code, out, err = _fx_run("consult_check", self.repo, self.art, reply=json.dumps({"changes": []}),
                                 **{"pass": "first"})
        self.assertEqual(out["go"], False, err)
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["docs/notes.md"], "tests": [], "spec": "",
                               "reason": "記録を残すのは直しに伴う変更なので足してよい"}]}
        code, out, err = _fx_run("consult_accept", self.repo, self.art, answer=json.dumps(answer, ensure_ascii=False),
                                 **{"pass": "first"})
        self.assertEqual(code, 0, err)
        self.assertTrue(out["consulted"], out)
        self.assertIn("docs/notes.md", pathlib.Path(out["answer_file"]).read_text(encoding="utf-8"))

    def test_fix_prep_writes_the_prompt_and_skips_without_duty(self):
        import consult
        code, out, err = _fx_run("fix_prep", self.repo, self.art, group=self._fx_group([_FX_MEAN]))
        self.assertEqual(code, 0, err)
        self.assertEqual((out["go"], out["iteration"]), (True, 1), out)
        text = pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(_FX_MEAN, text)
        self.assertFalse((self.place / consult.CONFIG).exists(), "修正案の無い run は相談の控えを書かない")
        # TDD の輪が緑にしていない単位は、修正役が項目ごとに下請け（実装役・審査役）を Agent で起こす（元の g1）
        self.assertIn("## 下請けを回す", text)
        impl = (self.place / "g1-impl-1.md").read_text(encoding="utf-8")
        self.assertIn(_FX_MEAN, impl)
        self.assertIn("## works の決まり（下請け", impl)
        self.assertIn(str(self.place / "g1-1.patch"), (self.place / "g1-review-1.md").read_text(encoding="utf-8"))
        code, out, err = _fx_run("fix_prep", self.repo, self.art, group=self._fx_group(["not-owed"]))
        self.assertEqual((code, out["go"]), (0, False), err)

    def test_prep_passes_state_dir_cache_root(self):
        """修正役の指示書のライブラリの文書の節は、STATE_DIR の下 works-factory/ の run をまたぐ控えを読む（網に出ない）"""
        import libdocs
        from lib.tests.test_libdocs import FakeBoard, ok_http
        (self.repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (self.repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        state = self.tmp / "state"
        libdocs.section(FakeBoard(self.tmp / "earlier").work(""), self.repo, ["app.py"], get=ok_http(), env={},
                        shared=state / "works-factory")
        code, out, err = _fx_run("fix_prep", self.repo, self.art, group=self._fx_group([_FX_MEAN]),
                                 env_extra={"STATE_DIR": str(state), **NO_NET})
        self.assertEqual(code, 0, err)
        text = pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("ほかの run 1 本", text)

    def _fx_overflow(self):
        """承認済みの項目 1（stats.py だけ）の範囲の外の request_ok.json にも触れた返答。返り (返答, 触る前の中身)"""
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": ["stats.py"],
                                         "out_of_scope": []}])
        self._fx_json("p2.fix_plan.json", {"plan": [{"unit_keys": [_FX_MEAN], "approach": "分母を直す", "adds": [],
                                                      "removes": []}]})
        self._fx_fix_mean()
        extra = self.repo / "request_ok.json"
        before = extra.read_bytes()
        extra.write_bytes(before + b"\n")
        return {"changes": [_fx_change(_FX_MEAN, ["stats.py", "request_ok.json"])]}, before

    def test_unasked_overflow_is_queued_for_the_next_consult_check(self):
        """範囲の外のはみ出しだけの返答は、まだ聞いていなければ拒まずに相談に積み（最後の回でも輪を抜けない）、次の周の
        consult-check が積んだ頼みで答えの役を起こす（元 accept.py:549 の settle_overflow）"""
        import fixboard
        reply, before = self._fx_overflow()
        group = self._fx_group([_FX_MEAN])
        out = self._fx_accept("fix_accept", reply, 3, group=group)
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertTrue(out["reason"].startswith(fixboard.QUEUED), out["reason"])
        self.assertEqual((self.repo / "request_ok.json").read_bytes(), before + b"\n", "積んだ回は作業ツリーを変えない")
        code, out, err = _fx_run("consult_check", self.repo, self.art, reply=json.dumps(reply, ensure_ascii=False),
                                 **{"pass": "first"})
        self.assertEqual((code, out["consulted"], out["go"]), (0, True, True), err)
        self.assertIn("request_ok.json", pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8"))

    def test_denied_overflow_is_reverted_by_the_machine(self):
        """相談で deny された後の同じはみ出しは、機械が段の頭の木に戻して受け付ける"""
        reply, before = self._fx_overflow()
        group = self._fx_group([_FX_MEAN])
        self.assertFalse(self._fx_accept("fix_accept", reply, 1, group=group)["ok"])
        code, out, err = _fx_run("consult_check", self.repo, self.art, reply=json.dumps(reply, ensure_ascii=False),
                                 **{"pass": "first"})
        self.assertEqual((code, out["go"]), (0, True), err)
        answer = {"answers": [{"ask": 1, "decision": "deny", "reason": "見本の入力は直しに要らないので範囲に足さない"}]}
        code, out, err = _fx_run("consult_accept", self.repo, self.art, answer=json.dumps(answer, ensure_ascii=False),
                                 **{"pass": "first"})
        self.assertEqual((code, out["consulted"]), (0, True), err)
        out = self._fx_accept("fix_accept", reply, 2, group=group)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual((self.repo / "request_ok.json").read_bytes(), before, "戻したファイルは段の頭の姿")
        self.assertIn("sum(xs) / len(xs)", (self.repo / "stats.py").read_text(encoding="utf-8"))
        kept = json.loads((self.place / "fix-reply.json").read_text(encoding="utf-8"))
        self.assertEqual([c["files"] for c in kept["changes"]], [["stats.py"]])

    def test_rule_prompt_names_the_frozen_policy_copy(self):
        """裁定役の指示書が名指す方針の文書は、始めの記録の固めた版の写し（run の途中で書き換えた生の文書ではない）"""
        import conflict
        fields, raw_doc = moved_policy(self.tmp)
        self._fx_json("r1/start.json", fields)
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE)
        code, out, err = _fx_run("rule_prep", self.repo, self.art)
        self.assertEqual(code, 0, err)
        text = pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(fields["policy"]["copy"], text)
        self.assertNotIn(raw_doc, text)

    def test_rule_loop_writes_the_reject_and_names_it_next(self):
        import conflict
        conflict.park(self.place, [{"unit_key": _FX_MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE)
        code, out, err = _fx_run("rule_prep", self.repo, self.art)
        self.assertEqual((code, out["iteration"]), (0, 1), err)
        code, out, err = _fx_run("rule_accept", self.repo, self.art, reply=json.dumps({"rulings": []}), iteration="1")
        self.assertEqual((code, out["ok"], out["done"]), (0, False, False), err)
        reject = out["reason_file"]
        code, out, err = _fx_run("rule_prep", self.repo, self.art)
        self.assertEqual((code, out["iteration"]), (0, 2), err)
        self.assertIn(reject, pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8"))



_FX_BODY = {"between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
            "which_is_right": "request", "kind": "unnamed_test_broke", "round": 1, "source": "fix", "status": "ruled"}
_FX_SCOPE = {**_FX_BODY, "id": "c1-1", "unit_key": _FX_MEAN,
             "ruling": {"decision": "fix_test_scope", "text": "テストの期待を直してよい", "limits": ["test_stats.py"], "by": "ruler"}}
_FX_REPLAN = {**_FX_BODY, "id": "c1-2", "unit_key": _FX_BOUND, "replan": "waiting", "kind": "brief_vs_judgment",
              "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "by": "ruler", "plan_items": [1],
                         "plan_units": [_FX_BOUND]}}


class RefixCase(FixLoopPlace):
    """2 度目の修正（線の include refix-run）は置き場が 1 回目と分かれるので、1 回目の段の申し出と裁定を入力 prior_conflicts で受けて
    自分の置き場に写す（conflict.adopt_prior。元は 1 つの盤面で conflict.second_pass が 1 回目の行を見た）。ここは写した後の受け付け"""

    def first_place(self, *rows):
        first = self.tmp / "first"
        first.mkdir()
        (first / "conflicts.json").write_text(json.dumps({"items": list(rows)}, ensure_ascii=False), encoding="utf-8")
        return first

    def test_refix_sees_first_pass_rulings(self):
        """L-W18・F044: 1 回目の段の裁定 fix_test_scope の範囲のテストの変更を、2 回目の段の組の子の受け付け（first）の事後の関門が
        許す（元 works/blk-fix/lib/fixgates.py:103 の second_pass）。写さない 1 回目の形は FixLoopScriptsCase の
        test_ruled_pass_allows_ruled_test_scope_and_first_does_not が拒む"""
        import conflict
        conflict.adopt_prior(self.place, self.first_place(_FX_SCOPE, _FX_REPLAN), ["1"])
        self.assertTrue(conflict.second_pass(self.place))
        self._fx_fix_mean()
        path = self.repo / "test_stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace("mean([1, 2, 3]), 2", "mean([2, 4]), 3"), encoding="utf-8")
        reply = {"changes": [_fx_change(_FX_MEAN, ["stats.py", "test_stats.py"])]}
        out = self._fx_accept("fix_accept", reply, 1, group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_first_pass_rulings_are_not_fixed_again(self):
        """写した 1 回目の段の直す裁定（fix_test_scope・fix_code_as）は 1 回目の段が直したので、2 回目の段の裁定の後の修正の輪を
        起こさない（起こすのは 2 回目の段で新しく裁いた直す裁定だけ）"""
        import conflict
        conflict.adopt_prior(self.place, self.first_place(_FX_SCOPE), ["1"])
        code, out, err = _fx_run("fix_ruled_prep", self.repo, self.art)
        self.assertEqual((code, out["go"]), (0, False), err)

    def test_second_give_up_after_replan_is_asked_to_human(self):
        """F023: 案を直して直す義務に戻った単位（1 回目の段の待つ行が 2 回目の段で案を直した行になる）が、また TDD の確認の上限まで
        落ちたら、裁定に回さず ask_human（by tdd-repeat）で積む（元 works/.shared/core/conflict.py:567-577 の park）"""
        import conflict
        import stopby
        conflict.adopt_prior(self.place, self.first_place(_FX_REPLAN), ["1"])
        item = {"unit_key": _FX_BOUND, "between": ["bounds.py:1", "test_stats.py:8"],
                "why_both_cannot_hold": "直した案でも上限の確認が 3 回落ちた", "which_is_right": "unknown", "kind": "needs_context"}
        ids = conflict.park_claims(self.place, [{"source": conflict.GAVE_UP_SOURCE, "item": item}])
        row = next(r for r in conflict.items(self.place) if r["id"] == ids[0])
        self.assertEqual((row["ruling"]["decision"], row["ruling"]["by"]), (conflict.ASK, stopby.TDD_REPEAT))
        self.assertEqual([r["id"] for r in conflict.this_pass(self.place)], ids)


class FixAcceptCase(FixLoopPlace):
    """修正役の返答の受け付けの、事前審査への応答の照らし"""

    REVIEW = {"faces": [{"key": "穴-平均の分母が空の列で割れる", "kind": "contract_drift", "unit_keys": [_FX_MEAN]},
                        {"key": "穴-上限の単位の別の組", "kind": "contract_drift", "unit_keys": [_FX_BOUND]}],
              "shrink": [{"key": "別案-len を直に使う", "unit_keys": []}]}

    def test_unanswered_plan_face_is_rejected(self):
        """L-W19・F130: 修正役は事前審査の穴と別案に key ごとに 1 度だけ答える（plan_faces）。答えない key・事前審査に無い key・
        重複を 1 行ずつ拒み、組の子は自分の単位の穴（と単位の無い別案）だけに答える（元 review-loop.py:3115 の _plan_face_errors）"""
        self._fx_json("p2.plan_review.json", self.REVIEW)
        self._fx_fix_mean()
        answer = {"key": "穴-平均の分母が空の列で割れる", "handled": "absorbed", "how": "空の列は 0 を返すように分母の前で分けた"}
        bad = {"changes": [_fx_change(_FX_MEAN, ["stats.py"])],
               "plan_faces": [answer, answer, {**answer, "key": "穴-事前審査に無い key を答えた"}]}
        out = self._fx_accept("fix_accept", bad, 1, group=self._fx_group([_FX_MEAN]))
        self.assertFalse(out["ok"], out)
        for phrase in ("plan_faces[1] の key が重複", "'穴-事前審査に無い key を答えた' は事前審査に無い", "'別案-len を直に使う' に応答が無い"):
            self.assertIn(phrase, out["reason"])
        self.assertNotIn("穴-上限の単位の別の組", out["reason"], "ほかの組の単位の穴は問わない")
        good = {"changes": [_fx_change(_FX_MEAN, ["stats.py"])],
                "plan_faces": [answer, {"key": "別案-len を直に使う", "handled": "declared", "how": "len は空の列で 0 割りになるので採らない"}]}
        out = self._fx_accept("fix_accept", good, 2, group=self._fx_group([_FX_MEAN]))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)

    def test_fix_prompt_pastes_every_key_the_accept_asks(self):
        """#570: 組の子の修正役の指示書が貼る事前審査の key は、同じ組の受け付けが「応答が無い」と拒む key と同じ集合"""
        import fixboard
        self._fx_json("p2.plan_review.json", self.REVIEW)
        code, out, err = _fx_run("fix_prep", self.repo, self.art, group=self._fx_group([_FX_MEAN]))
        self.assertEqual(code, 0, err)
        section = pathlib.Path(out["prompt_file"]).read_text(encoding="utf-8").split(fixboard.FACES_HEAD, 1)[1]
        pasted = set(re.findall(r"^- `([^`]+)`（(?:穴|別案)", section, re.M))
        self.assertEqual(pasted, {"穴-平均の分母が空の列で割れる", "別案-len を直に使う"})
        self._fx_fix_mean()
        out = self._fx_accept("fix_accept", {"changes": [_fx_change(_FX_MEAN, ["stats.py"])]}, 1,
                              group=self._fx_group([_FX_MEAN]))
        self.assertFalse(out["ok"], out)
        self.assertEqual(set(re.findall(r"事前審査の '(.+?)' に応答が無い", out["reason"])), pasted)


class HandoffCase(unittest.TestCase):
    """修正役が人に回した物（breaks.accepted）が報告の人が決めることに届く"""

    def test_common_rules_breaks_promise_reaches_the_decisions(self):
        """部分 D2 やる事 1（S03）: 修正役の共通の決まり common.md の「人に回す物は breaks.accepted に書け……機械が人に見せる一覧
        （報告の「人が決めること」）に載せる」が本当になる: 組の子の返答の breaks.accepted が組の結果の handoffs と fix の出力の
        handoffs を通って報告の人が決めることのセクションに 1 件 1 行で出る"""
        import fixboard
        import report
        import runreport
        text = (BLOCK / "commands" / "fix-rules" / "common.md").read_text(encoding="utf-8")
        self.assertIn("**人に回す物は `breaks.accepted` に書け。**", text)
        self.assertIn("機械が人に見せる一覧（報告の「人が決めること」）に載せる", text)
        with tempfile.TemporaryDirectory() as tmp:
            place = pathlib.Path(tmp) / "fix" / "fix"
            place.mkdir(parents=True)
            (place / "fix.diff").write_text("x", encoding="utf-8")
            reply = {"changes": [{"unit_key": "u1", "breaks": {"accepted": "ADR-3 と食い違う既定を残す（docs/adr/3.md:4）"}}]}
            child = fixboard.group_result({"group_id": "g1", "unit_ids": ["u1"]}, start_tree="t", end_tree="t", tdd=None, reply=reply)
            fix = {"done": True, "units": [{"unit_id": "u1", "status": "fixed", "reason": ""}], "conflicts": None,
                   "diff": str(place / "fix.diff"), "diffs": [str(place / "fix.diff")], "delta_review": {"rounds": 1, "pass": True},
                   "handoffs": fixboard.final_lines([child], "handoffs"), "mismatched": []}
            got = runreport.build({"fix": fix}, {}, {}, None, "fixed", "", out_dir=pathlib.Path(tmp) / "report")
            body = pathlib.Path(got["report"]).read_text(encoding="utf-8").split(f"{report.DECISIONS_HEADING}\n\n", 1)[1]
        self.assertIn(f"- {fixboard.HANDOFF_HEAD}: 1 件\n  - u1: 壊すと分かって通した——ADR-3 と食い違う既定を残す（docs/adr/3.md:4）", body)


# 写しの台帳（K9）: workflows/fix/commands/ の下の指示書の全部と、YAML に直に書いた役の prompt: の全部の元（今の works
# 2aa7c66c の works/ の下）・元の sha256・許した直し (元の字, 写しの字, 訳)（前から当てると元が写しになる順）。
# prompt: の元は元の YAML の同じ役の節の prompt の値（YAML として読んだ字。sha256 もその字の物）
REVIEW_PROMPT_TAIL = ("が名指す欄の JSON だけ。\n前の回の受け付けが拒んだ理由を書いたファイル（初回は空。空でなければ、まずそのファイルを "
                      "Read で読み、書かれた理由を直した返答を丸ごと出し直せ。理由の本文はファイルにだけ在る）: "
                      "`$LOOP_PREV.{accept}.output.reason_file`")
REFIX_PROMPT_WHY = ("拒否の理由のファイルは支度の節が指示書の見出しの次の 1 行で名指す（refix_prep の reject_file。$LOOP_PREV は"
                    "筋書きで渡らない）。返す形は指示書の「返す JSON」の節が持つ")
COPIED_TEXTS = {
    "commands/delta-review.md": ("works/blk-delta/commands/delta-review.md",
                                 "e036035e56e7e7a0d14f08f3c60e84789abdbdb7b9a49c08ce5fa3fd9e7887de", [
        ("`$cut.output.diff_file`", "`$delta-cut.output.diff_file`", "切り出しの節の名が delta-cut（2 回目の cut2 と分ける）"),
        ("$cut.output.files", "$delta-cut.output.files", "切り出しの節の名が delta-cut"),
        ("`$cut.output.brief_file`", "`$delta-cut.output.brief_file`", "切り出しの節の名が delta-cut"),
        ("（`faces`・`shrink`）\n", "（`faces`・`shrink`）。null なら、この run の材料に事前審査の返答は無い\n",
         "fix の入力に事前審査の返答が無い run は材料の値が null"),
        ("$LOOP_PREV.review-accept.output.reason_file", "$LOOP_PREV.delta-accept.output.reason_file",
         "受け付けの節の名が delta-accept"),
    ]),
    "commands/fix-rules/brief.md": ("works/blk-fix/rules/brief.md",
                                    "9e3dbe4e819682536d80fe2afabe817a69133f6e255510792f82997a7cac0d7c", []),
    "commands/fix-rules/common.md": ("works/.shared/core/writerules/common.md",
                                     "b5babd288578c598fe106e7d30d3d449852aa509fd05c4715f40e3acbeef6294", [
        ("（pytest の node id か `-k`、unittest の `-k` かモジュール名。", "（実行器の絞り方——試験の id か名前で絞る。",
         "実行器の名を書かない（E13）"),
        ("包みが Edit・Write の書き込みを記録し、受け付けが版からの変更と突き合わせて、記録も申告も無い変更を拒む。",
         "受け付けが版からの変更を返答の申告（`changes[].files` と `bash_writes`）と突き合わせて、申告の無い変更を拒む。",
         "包みの書き込みの記録が無い（U6）"),
    ]),
    "commands/fix-rules/direct.md": ("works/blk-fix/rules/direct.md",
                                     "f1b27e13722aa4f6480e322244f78e5d255ac68229679ba82192d50e0f8c32c3", []),
    "commands/fix-rules/principles.md": ("works/blk-fix/rules/principles.md",
                                         "5dfb51bcef4e50ab2a104e38113aa00dbfe15041b774579a370a90b1b941ee54", []),
    "commands/fix-rules/refix.md": ("works/blk-refix/rules/refix.md",
                                    "e87d509ef9db2c497098974a6f00f2bd197ba62523a5695e6e6799e2de5499e1", []),
    "commands/fix-rules/ruler.md": ("works/blk-fix/rules/ruler.md",
                                    "1de1fa87d5d34a27060cb409a99f34e58208d4f8d1fb1093b059ae3016c26237", []),
    "commands/fix-rules/tdd.md": ("works/blk-fix/rules/tdd.md",
                                  "82a607d001d49666e7d38594e74267813ed8c7d258811f013cd5ed14699a1519", []),
    "commands/lens-silent-failure-hunter.md": ("works/blk-lens/commands/lens-silent-failure-hunter.md",
                                               "ba8c29ce63a91212aa3ec239666669e9c5af30ef5e835077666cbc3d7c317db3", [
        ("下の囲みの中が、お前への指示書そのもの（振り分けの節が組んだ、", "下のファイルが、お前への指示書そのもの（支度の節が組んだ、",
         "指示書は支度の節 lens-prep が置き場のファイルに書く"),
        ("返し方）。その指示に従え。", "返し方）。Read で全部読み、その指示に従え。", "指示書をファイルで渡す"),
        ("=====指示書ここから=====\n$lens-route.output.prompt_silent_failure_hunter\n=====指示書ここまで=====\n",
         "指示書: `$lens-prep.output.prompt_file`\n", "指示書を貼らずにファイルを名指す"),
    ]),
    "commands/review2.md": ("works/blk-refix/commands/review2.md",
                            "a6093ec64027e1c606a39fd9eae78938ff1e5b4f6d6725642c5c30bf96a03b8b", [
        ("## 付録: 人の方針（囲みの中が本文。この節の決まりで読め）\n", "## 付録: 人の方針\n", "方針を貼らずに材料で渡す"),
        ("（役も engine も書き換えない）。方針が在るなら",
         "（役も engine も書き換えない）。本文は材料 `$cut2.output.brief_file` の `policy.paste`（空なら方針は無い。長くて"
         "切り詰めたときは末尾に続きの置き場が在り、写しの置き場は `policy.path`）——在れば、先に全部読め。方針が在るなら",
         "$INPUTS.policy_paste が無いので方針は材料の policy で渡す"),
        ("方針の文書は書き換えるな。本文（空なら方針は無い）:\n\n=====人の方針ここから=====\n$INPUTS.policy_paste\n"
         "=====人の方針ここまで=====\n", "方針の文書は書き換えるな。\n", "方針を貼らない"),
    ]),
    "works-factory-fix.yaml#ruler": ("works/blk-fix/blk-fix.yaml:1757（節 rule）",
                                     "fabd4b04185b20a41238e68d785fb06e23ebf03b0871aa25f85b515a90d3755a", []),
    "works-factory-fix.yaml#fix-ruled": ("works/blk-fix/blk-fix.yaml:1868（節 fix-ruled）",
                                         "19bac0da387f893cf0d67d4c411b8c002068f38e14dae713b120c18baebf42b4", []),
    "works-factory-fix.yaml#ruled-consult-answer": ("works/blk-fix/blk-fix.yaml:1913（節 plan-answer-ruled）",
                                                    "1323fb401e69c0f217bf8ff9c9076f76ca1fa2d17ac46477ae9f4df9f24c72c2", [
        ("$fix-ruled-consult.output", "$ruled-consult-check.output", "相談の支度の節の名が ruled-consult-check"),
    ]),
    "works-factory-fix.yaml#refix": ("works/blk-refix/blk-refix.yaml:60（節 refix）",
                                     "9c27f69e8198db36e6be6e12485a7013b7225507c19165dd65bf9d05044d326a", [
        (REVIEW_PROMPT_TAIL.format(accept="refix-accept"), "の「返す JSON」の形の JSON だけ。", REFIX_PROMPT_WHY),
    ]),
    "works-factory-fix.yaml#refix2": ("works/blk-refix/blk-refix.yaml:328（節 refix2）",
                                      "3e2b5d7bc34a7d5c95b7a94960afbcb7a7564cdcae653fefd8c61f596395df6d", [
        (REVIEW_PROMPT_TAIL.format(accept="refix2-accept"), "の「返す JSON」の形の JSON だけ。", REFIX_PROMPT_WHY),
    ]),
    "works-factory-fix.yaml#tdd": ("works/blk-fix/blk-fix.yaml:183（節 tdd）",
                                   "e0f08ddf808130be63ceb2841b823757d376d510ff11aae84aab2739b55b0a7f", []),
    "works-factory-fix.yaml#tdd-new": ("works/blk-fix/blk-fix.yaml:183（節 tdd。単位が替わる周の新しい会話の節で、字は tdd と同じ）",
                                       "e0f08ddf808130be63ceb2841b823757d376d510ff11aae84aab2739b55b0a7f", []),
    "works-factory-fix.yaml#fixer": ("works/blk-fix/blk-fix.yaml:1585（節 fix）",
                                     "7d362884bfc6bb2ab759c6fe3d4fcec869ced370248dd66777db3c4fc7c66506", []),
    "works-factory-fix.yaml#consult-answer": ("works/blk-fix/blk-fix.yaml:1632（節 plan-answer）",
                                              "d4df849c558c8451ca1225e90bbbb2a5e04ffbf9664a7c52b2277f78cf9999c7", [
        ("$fix-consult.output", "$consult-check.output", "相談の支度の節の名が consult-check"),
    ]),
}


# 元の works に無い新しい指示書と prompt:（写しでないので元と許した直しを持たない）。{台帳の鍵: 足した訳}
NEW_TEXTS = {
    "commands/fix-rules/clash.md": "合わせ役の決まり（持ち主の決め clash-goes-to-ruling。#382。元は組を戻すだけで直す役が無かった）",
    "works-factory-fix.yaml#clash-fix": "合わせ役のノード（#382）",
    "works-factory-fix.yaml#clash-ruled": "裁定の後の合わせ役のノード（#382）",
}


def copied_texts() -> dict:
    """台帳の鍵 → 今の字: commands/ の下の指示書の全部（commands/<相対パス>）と、YAML の役の節の prompt: の全部（<YAML の名>#<id>）"""
    out = {f"commands/{p.relative_to(BLOCK / 'commands').as_posix()}": p.read_text(encoding="utf-8")
           for p in sorted((BLOCK / "commands").rglob("*.md"))}
    out.update({f"{YAML_PATH.name}#{nid}": n["prompt"] for nid, n in all_nodes(load()).items() if "prompt" in n})
    return out


class CopiedTextsCase(unittest.TestCase):
    """役の指示書の写しの台帳（K9）: 全部の指示書と YAML の役の prompt: が、元の works の文に台帳の直しと書き直しの記録
    （copied.REWRITES。PR #221 の語と初見の読み手の書き直し）だけを当てた物"""

    def test_every_command_is_its_original_with_only_ledgered_edits(self):
        """許した直しと書き直しを逆に当てると元のバイト（元の sha256）に戻る。台帳にも新しい物の表 NEW_TEXTS にも無い指示書・
        prompt・書き直しと、写しの無い台帳の行は赤"""
        texts = copied_texts()
        here = BLOCK.relative_to(ROOT).as_posix()
        with self.subTest(ledger="台帳と指示書・prompt の一覧"):
            self.assertEqual(set(COPIED_TEXTS) & set(NEW_TEXTS), set())
            self.assertEqual(sorted([*COPIED_TEXTS, *NEW_TEXTS]), sorted(texts))
            self.assertLessEqual({k for k in REWRITES if k.startswith(f"{here}/")}, {f"{here}/{k}" for k in COPIED_TEXTS},
                                 "台帳に無い指示書・prompt の書き直し")
        for key in sorted(set(texts) & set(COPIED_TEXTS)):
            source, sha256, edits = COPIED_TEXTS[key]
            with self.subTest(text=key, source=source):
                assert_text_is_original(self, f"{here}/{key}", texts[key], sha256, edits)
