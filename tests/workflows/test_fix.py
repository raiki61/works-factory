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
from tests.bin import hermetic
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "fix"
YAML_PATH = BLOCK / "works-factory-fix.yaml"
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

if str(LIB / "graphloops") not in sys.path:
    sys.path.append(str(LIB / "graphloops"))

from engine.schema import validate_schema  # noqa: E402  （output_format の照らし。jsonschema に頼らない lib の小道具）

CONTRACT_FIELDS = {"done", "units", "groups", "conflicts", "replan_items", "objection", "diff", "allowed_test_changes",
                   "changed", "delta_review"}
CONTRACT_INPUTS = {"start", "baseline", "units", "judgment", "world", "plan", "ripple", "depth", "answers"}
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
                     "lens-collect", "delta-accept", "refix-prep", "cut2", "review2-accept", "refix2-prep", "tdd-prep",
                     "fix-prep", "consult-check", "consult-accept", "group-end", "fix")

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
FIX_RULES = ("common", "brief", "direct", "principles", "ruler", "tdd", "refix")
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
    """返す節 fix の output_format が約束の 10 欄をちょうど持つ"""

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

    def test_nested_shapes(self):
        props = self.fmt["properties"]
        unit = props["units"]["items"]
        self.assertEqual(set(unit["required"]), {"unit_id", "group_id", "status", "reason"})
        self.assertEqual(unit["properties"]["status"]["enum"], ["fixed", "given_up", "not_done"])
        self.assertIs(unit["additionalProperties"], False)
        group = props["groups"]["items"]
        self.assertEqual(set(group["required"]), {"group_id", "unit_ids", "returned", "reason"})
        self.assertEqual(group["properties"]["returned"], {"type": "boolean"})
        self.assertEqual(set(props["changed"]["required"]), CHANGED_MARKS)
        self.assertTrue(all(v == {"type": "boolean"} for v in props["changed"]["properties"].values()))
        self.assertEqual(set(props["delta_review"]["required"]), {"rounds", "pass"})
        for name in ("replan_items", "allowed_test_changes"):
            self.assertEqual(props[name]["items"], {"type": "string"})
        self.assertEqual(props["objection"], {"type": "string"})
        pointer = props["diff"]
        self.assertEqual(set(pointer["required"]), {"type", "run_id", "path"})
        self.assertEqual(pointer["properties"]["type"]["enum"], ["archon_artifact"])
        self.assertEqual(props["conflicts"]["type"], ["object", "null"])
        self.assertEqual({k: v for k, v in props["conflicts"].items() if k != "type"},
                         {k: v for k, v in pointer.items() if k != "type"})


class InputsCase(unittest.TestCase):
    def test_contract_inputs_and_extra_inputs_default_empty(self):
        doc = load()
        inputs = doc["inputs"]
        self.assertEqual(set(inputs), CONTRACT_INPUTS | EXTRA_INPUTS)
        for name in EXTRA_INPUTS:
            self.assertEqual(inputs[name].get("default"), "", name)

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
        env = {k: v for k, v in os.environ.items() if not k.startswith(("INPUTS_", "PR_REVIEW_TOOLKIT"))}
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
        prep = self._run("refix_prep", "refix-prep")
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
        bad = self._run("refix_accept", "refix-accept", reply=json.dumps(_RV_HANDLED, ensure_ascii=False), iteration="1")
        self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
        self.assertIn("other.py", pathlib.Path(bad["reason_file"]).read_text(encoding="utf-8"))
        again = self._run("refix_prep", "refix-prep")
        self.assertEqual(again["iteration"], 2)
        self.assertIn(bad["reason_file"], pathlib.Path(again["prompt_file"]).read_text(encoding="utf-8"))
        (self.repo / "other.py").unlink()
        ok = self._run("refix_accept", "refix-accept", reply=json.dumps(_RV_HANDLED, ensure_ascii=False), iteration="2")
        self.assertEqual((ok["ok"], ok["done"]), (True, True), ok)
        cut2 = self._run("cut2", "cut2")
        self.assertEqual((cut2["go"], cut2["files"]), (True, ["stats.py"]), cut2)

    def test_refix_prompts_name_the_frozen_policy_copy(self):
        """1 回目と 2 回目の手直しの指示書が名指す方針の文書は、始めの記録の固めた版の写し（run の途中で書き換えた生の文書ではない）"""
        fields, raw_doc = moved_policy(self.tmp)
        self._json("r1/start.json", fields)
        self._cut()
        self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))
        prep = self._run("refix_prep", "refix-prep")
        text = pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(fields["policy"]["copy"], text)
        self.assertNotIn(raw_doc, text)
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        self.assertTrue(self._run("refix_accept", "refix-accept", reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                                  iteration="1")["ok"])
        self.assertTrue(self._run("cut2", "cut2")["go"])
        review2 = {**_RV_REVIEW, "checks": [{"key": _RV_FACE, "closed": False, "why": "docstring は足したが平均の定義を書いていない"}]}
        self.assertTrue(self._run("review2_accept", "review2-accept", reply=json.dumps(review2, ensure_ascii=False))["ok"])
        prep = self._run("refix2_prep", "refix2-prep")
        self.assertTrue(prep["go"], prep)
        text = pathlib.Path(prep["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(fields["policy"]["copy"], text)
        self.assertNotIn(raw_doc, text)

    def test_refix_undeclared_write_is_rejected(self):
        """記録の無い run の書き込みの出どころ（U6 の狭め）: 手直しの段の頭の木からの変更が handled[].files にも bash_writes にも無ければ拒む"""
        self._cut()
        self._run("delta_accept", "delta-accept", reply=json.dumps(_RV_REVIEW, ensure_ascii=False))
        self.assertTrue(self._run("refix_prep", "refix-prep")["go"])
        self.assertTrue((self.place / "refix1-head.json").is_file())
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8").replace("def mean(xs):\n", 'def mean(xs):\n    """算術平均"""\n'),
                     encoding="utf-8")
        undeclared = {"handled": [{"key": _RV_FACE, "handled": "declared",
                                   "how": "直さずに残す訳を述べた（stats.py の変更は申告しない）"}]}
        bad = self._run("refix_accept", "refix-accept", reply=json.dumps(undeclared, ensure_ascii=False), iteration="1")
        self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
        self.assertIn("stats.py", bad["reason"])
        ok = self._run("refix_accept", "refix-accept", reply=json.dumps(_RV_HANDLED, ensure_ascii=False), iteration="2")
        self.assertEqual((ok["ok"], ok["done"]), (True, True), ok)

    def test_refix_accepts_read_the_recorder_log(self):
        """記録の根が在る run の 1 回目・2 回目の手直しの受け付けは、作業ツリーの記録を読み、記録の無い変更を拒む"""
        import writelog
        import writes
        log = writelog.log_path(writelog.root(self.cfg), self.repo)
        log.parent.mkdir(parents=True)
        log.write_text("", encoding="utf-8")
        p = self.repo / "stats.py"
        for n, (prep, accept) in enumerate((("refix_prep", "refix_accept"), ("refix2_prep", "refix2_accept")), 1):
            with self.subTest(accept=accept):
                if n == 1:
                    self._cut()
                else:
                    self.assertTrue(self._run("cut2", "cut2")["go"])
                nid, review = ("delta-accept", _RV_REVIEW) if n == 1 else ("review2-accept", {**_RV_REVIEW, "checks": [
                    {"key": _RV_FACE, "closed": False, "why": "docstring は足したが平均の定義を書いておらず、穴が残る"}]})
                self.assertTrue(self._run(nid.replace("-", "_"), nid, reply=json.dumps(review, ensure_ascii=False))["ok"])
                self.assertTrue(self._run(prep, prep.replace("_", "-"))["go"])
                p.write_text(p.read_text(encoding="utf-8") + f"\n# 手直し {n}\n", encoding="utf-8")
                bad = self._run(accept, accept.replace("_", "-"), reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
                                iteration="1")
                self.assertEqual((bad["ok"], bad["done"]), (False, False), bad)
                self.assertIn(writes.REJECT + "stats.py", bad["reason"])
                _record(log, p)
                ok = self._run(accept, accept.replace("_", "-"), reply=json.dumps(_RV_HANDLED, ensure_ascii=False),
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
        self.assertFalse(self._run("refix_prep", "refix-prep")["go"])

    def test_not_launched_roles_are_done(self):
        """支度が go: false で役を起こさなかった時（with: reply が null）は、受け付けが done: true で輪を抜ける"""
        self._cut()
        self.assertEqual(self._run("refix_prep", "refix-prep")["go"], False)
        for script, nid, extra in (("refix_accept", "refix-accept", {"iteration": "1"}),
                                   ("review2_accept", "review2-accept", {}),
                                   ("refix2_accept", "refix2-accept", {"iteration": "1"})):
            out = self._run(script, nid, reply="null", **extra)
            self.assertEqual((out["ok"], out["done"]), (True, True), (nid, out))
        self.assertFalse(self._run("cut2", "cut2")["go"])
        self.assertFalse(self._run("refix2_prep", "refix2-prep")["go"])
        self.assertFalse((self.place / "delta" / "review-2.json").exists())

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

    def test_scripts_do_not_name_queues_or_take(self):
        for name in ("delta_cut", "delta_accept", "lens_prep", "lens_collect", "refix_prep", "refix_accept", "cut2",
                     "review2_accept", "refix2_prep", "refix2_accept"):
            text = (BLOCK / "scripts" / f"{name}.py").read_text(encoding="utf-8")
            self.assertIsNone(NO_QUEUE.search(text), name)
            self.assertNotIn("../", text, name)


# ---------------------------------------------------------------- script の振る舞い（prep・join・tdd_unit・collect・clean・assert_changed）

_BLK_RUN = "wf-blk"
_BLK_MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
              "path_changed")


def _blk_run(script, repo, art, inputs=None, node_path="fix__x", env_extra=None):
    """scripts/<script>.py を一時の対象のリポジトリ repo で起こす。(終了の値, 標準出力の JSON か None, 標準エラー)。
    env_extra は子の環境に足す（hermetic.dropped の名は継がない）"""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("INPUTS_", "ARCHON_")) and not hermetic.dropped(k)}
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
           "changed": {k: False for k in _BLK_MARKS}, "allowed_test_changes": [], "verified": []}
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
                "baseline": "", "world": "", "ripple": "", "answers": "null"}

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

    # ---- route.py
    def test_route_returns_the_shape_of_the_mode(self):
        """route は境の置き場だけを sys.path に足して fixio を読む（fixio の頭は lib/ を読まない）"""
        fmt = all_nodes(load())["route"]["output_format"]
        for mode, group in (("", False), ("group", True)):
            code, out, err = _blk_run("route", self.repo, self.art, {"mode": mode}, "fix__route")
            self.assertEqual(code, 0, err)
            self.assertEqual(out, {"group": group})
            self.assertEqual(validate_schema(out, fmt), [], out)

    # ---- prep.py
    def test_prep_two_groups_run_side_by_side(self):
        subprocess.run(["git", "remote", "add", "origin", str(self.tmp / "origin.git")], cwd=self.repo, check=True)
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
        self.assertEqual(json.loads((self.place / "r1" / "start.json").read_text(encoding="utf-8"))["request_file"], "")

    def test_prep_writes_only_copies_the_children_adopt(self):
        """prep が置き場に書く入力の写しは、組の子が親から写す一覧 fixboard.ADOPTED に全部載る（載らない写しは子で黙って空になる）"""
        import fixboard
        import planmarks
        _blk_write(self.art / "in" / "ripple.json", [{"path": "stats.py"}])
        _blk_write(self.art / "in" / "world.json", {"facts": []})
        _blk_write(self.art / "in" / "baseline.json", {"cases": [], "exit": 0, "suite": "", "test_cmd": "", "rev": "HEAD"})
        inputs = {**self.prep_inputs(), "ripple": _blk_ptr("in/ripple.json"), "world": _blk_ptr("in/world.json"),
                  "baseline": _blk_ptr("in/baseline.json"), "depth": '[{"unit_id": "A", "depth": "標準", "why": "x"}]',
                  "answers": '{"decision": "approve", "text": "stats.py の外は触らない"}', "units": '["A"]',
                  "only_items": '["1"]'}
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

    def test_join_marks_missing_result_not_done(self):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []},
                                    {"group_id": "g2", "unit_ids": ["B", "C"], "items": []}], start, par=False)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], start, start))
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        joined = json.loads((self.place / "join.json").read_text(encoding="utf-8"))
        self.assertEqual([(u["unit_id"], u["status"]) for u in joined["units"]],
                         [("A", "fixed"), ("B", "not_done"), ("C", "not_done")])
        self.assertFalse(joined["groups"][1]["returned"])
        self.assertTrue(joined["groups"][1]["reason"])
        group_items = self.fmt["properties"]["groups"]
        unit_items = self.fmt["properties"]["units"]
        self.assertEqual(validate_schema(joined["groups"], group_items), [])
        self.assertEqual(validate_schema(joined["units"], unit_items), [])

    def test_join_in_order_drops_what_a_failed_child_left(self):
        """並べない run で結果を書かずに落ちた子の変更は、その子の始めの木に戻す（前の組の直しは残す）"""
        start = self.snapshot(self.repo)
        src = (self.repo / "stats.py").read_text(encoding="utf-8")
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": []}], start, par=False)
        (self.repo / "stats.py").write_text(src.replace("len(xs) - 1", "len(xs)"), encoding="utf-8")
        t1 = self.snapshot(self.repo)
        _blk_write(out_dir / "g1" / "result.json", _blk_result("g1", ["A"], t1, start))
        _blk_write(out_dir / "g2" / "group-start.json", {"start_tree": t1})
        (self.repo / "stats.py").write_text(src.replace("len(xs) - 1", "0"), encoding="utf-8")
        (self.repo / "half.py").write_text("Y = 1\n", encoding="utf-8")
        code, out, err = _blk_run("join", self.repo, self.art)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        self.assertEqual(self.snapshot(self.repo), t1)
        g2 = json.loads((self.place / "join.json").read_text(encoding="utf-8"))["groups"][1]
        self.assertFalse(g2["returned"])
        self.assertIn("half.py", g2["reason"])
        self.assertEqual(json.loads((out_dir / "g2" / "dropped.json").read_text(encoding="utf-8"))["paths"],
                         ["half.py", "stats.py"])

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

    def test_collect_returns_the_contract_when_the_boundary_cannot_be_read(self):
        """境の口（.shared）も lib も読めない写しから起こしても、返す節は落ちずに約束の形の done: false を返す（stdlib だけの最後の手）"""
        lone = self.tmp / "lone" / "fix" / "scripts"
        lone.mkdir(parents=True)
        (lone / "collect.py").write_bytes((BLOCK / "scripts" / "collect.py").read_bytes())
        env = {k: v for k, v in os.environ.items() if not k.startswith(("INPUTS_", "ARCHON_", "WORKS_FACTORY_ROOT"))}
        env.update({"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": _BLK_RUN, "PYTHONDONTWRITEBYTECODE": "1"})
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
        env = {k: v for k, v in os.environ.items() if not k.startswith(("INPUTS_", "ARCHON_"))}
        env.update({"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": _GRP_RUN,
                    "ARCHON_NODE_EXECUTION": json.dumps({"path": nid}), "WORKS_FACTORY_ROOT": str(ROOT),
                    "PYTHONDONTWRITEBYTECODE": "1", "INPUTS_GROUP": json.dumps(_GRP_GROUP, ensure_ascii=False),
                    "INPUTS_OUT_DIR": str(self.out_dir), "INPUTS_FROM_TREE": "", "INPUTS_MODE": "group"})
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
        self.assertEqual(self._grp_run("tdd_prep", "tdd-prep"), {"prompt_file": "", "go": False})
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

    def test_group_start_in_order_drops_what_the_failed_child_before_left(self):
        """親の作業ツリーで 1 つずつ回る子は、前の組の子が結果を書かずに落ちて残した変更を戻してから始める"""
        import leftovers
        before = leftovers.snapshot(self.repo)
        (self.out_dir / "g0").mkdir()
        (self.out_dir / "g0" / "group-start.json").write_text(json.dumps({"start_tree": before}), encoding="utf-8")
        (self.repo / "half.py").write_text("Y = 1\n", encoding="utf-8")
        self._grp_run("group_start", "group-start")
        self.assertFalse((self.repo / "half.py").exists())
        self.assertEqual(json.loads((self.out_dir / "g0" / "dropped.json").read_text(encoding="utf-8"))["paths"],
                         ["half.py"])
        began = json.loads((self.out_dir / "g1" / "group-start.json").read_text(encoding="utf-8"))
        self.assertEqual(began["start_tree"], before)

    def test_tdd_step_reads_the_recorder_log(self):
        """記録の根が在る run の TDD の輪の受け付けは、group-start が作った作業ツリーの記録を読み、記録の無い変更を拒む"""
        import writelog
        import writes
        env, root = _recorder_root(self.tmp)
        self._grp_parent_inputs(str(self.suite))
        with mock.patch.dict(os.environ, env):
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
        2 度走らせない）。置き場（fixio.line_top）・run の名（始めの記録の run_id）・落とす変数・2 つの起こし口の指紋が揃って当たる"""
        count = self.tmp / "test-cmd-count"
        test_cmd = f"{sys.executable} -c \"open({str(count)!r}, 'a').write('1\\n')\""
        line = self.tmp / "parent-art"
        self._grp_parent_inputs(str(self.suite), test_cmd=test_cmd, run_id="line-run")
        _blk_write(line / "start" / "record.json", {"run_id": "line-run", "test_cmd": test_cmd, "base_rev": "", "tdd_suite": ""})
        env = {k: v for k, v in os.environ.items() if not k.startswith(("INPUTS_", "ARCHON_"))}
        env.update({"ARTIFACTS_DIR": str(line), "WORKFLOW_ID": "line-run", "ARCHON_NODE_EXECUTION": json.dumps({"path": "test-gate"}),
                    "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "INPUTS_MODE": "base",
                    "INPUTS_START": json.dumps({"type": "archon_artifact", "run_id": "line-run", "path": "start/record.json"})})
        gate = subprocess.run([sys.executable, str(ROOT / "workflows" / "test-gate" / "scripts" / "run.py")], cwd=self.repo,
                              env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(gate.returncode, 0, gate.stderr)
        self.assertEqual(json.loads(gate.stdout)["material"]["status"], "clean", gate.stdout)
        self.assertEqual(self._grp_run("group_start", "group-start")["tdd"], True)
        self.assertEqual(len(count.read_text(encoding="utf-8").split()), 1)

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
        self.assertEqual(self._grp_run("tdd_prep", "tdd-prep"), {"prompt_file": "", "go": False})
        end = self._grp_run("group_end", "group-end")
        result = json.loads(pathlib.Path(end["result_file"]).read_text(encoding="utf-8"))
        self.assertTrue(result["tdd"]["ran"])
        self.assertEqual([(u["unit_key"], u["gave_up"]) for u in result["tdd"]["units"]], [(_GRP_MEAN, "green")])
        self.assertEqual([(u["unit_id"], u["status"]) for u in result["units"]], [(_GRP_MEAN, "given_up")])
        self.assertEqual([r["unit_key"] for r in result["conflicts"]], [_GRP_MEAN])

    def _grp_prompt(self):
        return pathlib.Path(self._grp_run("tdd_prep", "tdd-prep")["prompt_file"]).read_text(encoding="utf-8")

    def test_group_end_writes_the_result(self):
        """組の結果を out_dir/<group_id>/result.json に約束の形で書く（修正の輪の結末・返答の写し・許したテストを読む）"""
        import leftovers
        self._grp_run("group_start", "group-start")
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        (self.place / "fix-units.json").write_text(json.dumps({_GRP_MEAN: {"status": "fixed", "reason": ""}},
                                                              ensure_ascii=False), encoding="utf-8")
        (self.place / "fix-reply.json").write_text(json.dumps({"changes": [], "gates_changed": True,
                                                               "rejudge_requested": "単位の見立てが違う"},
                                                              ensure_ascii=False), encoding="utf-8")
        (self.place / "allowed-tests.json").write_text(json.dumps(["test_stats.py"]), encoding="utf-8")
        out = self._grp_run("group_end", "group-end")
        self.assertEqual(out["result_file"], str(self.out_dir / "g1" / "result.json"))
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(set(result), {"group_id", "unit_ids", "end_tree", "start_tree", "units", "tdd", "conflicts",
                                       "objection", "changed", "allowed_test_changes", "verified", "reply_file",
                                       "tdd_state", "worktree"})
        self.assertEqual(result["tdd_state"], "", "輪の無い組")
        self.assertEqual(result["worktree"], os.path.realpath(self.repo))
        self.assertEqual(result["units"], [{"unit_id": _GRP_MEAN, "status": "fixed", "reason": ""}])
        self.assertEqual(result["end_tree"], leftovers.snapshot(self.repo))
        self.assertNotEqual(result["end_tree"], result["start_tree"])
        self.assertEqual((result["tdd"]["ran"], result["tdd"]["units"]), (False, []))
        self.assertEqual(result["changed"], {k: k == "gates_changed" for k in CHANGED_MARKS})
        self.assertEqual((result["objection"], result["allowed_test_changes"], result["verified"], result["conflicts"]),
                         ("単位の見立てが違う", ["test_stats.py"], [], []))
        self.assertEqual(result["reply_file"], str(self.place / "fix-reply.json"))

    def test_group_child_starts_its_log_and_reports_where_join_finds_it(self):
        """並べた子は自分の作業ツリーの記録を group-start で空で作り、group-end の結果の worktree から join が同じ記録を引く"""
        import writelog
        env, root = _recorder_root(self.tmp)
        with mock.patch.dict(os.environ, env):
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
    env_extra は子の環境に足す（hermetic.dropped の名は継がない）"""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("INPUTS_", "ARCHON_")) and not hermetic.dropped(k)}
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


class FixLoopScriptsCase(unittest.TestCase):
    """修正の輪・裁定の後の修正の輪・範囲の相談・裁定の輪の script を、一時の対象のリポジトリと一時の置き場で起こす"""

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
        self.assertEqual(set(kept["changed"]), set(CHANGED_MARKS))

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
        self.assertEqual(set(kept["changed"]), set(CHANGED_MARKS))
        self.assertEqual(json.loads((self.place / "allowed-tests.json").read_text(encoding="utf-8")), ["test_stats.py"])

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

