"""計画のブロック（workflows/plan/）の試験。

- 形: YAML を PyYAML で読み、返りの約束（docs/design.md の「plan の出力」）・役の節の決まり（E7・E12・E16）・輪の数を見る。
- script: 節の script を子のプロセスで Archon と同じ順に回す（with: と工程の入力 → INPUTS_<大文字>・ARTIFACTS_DIR・WORKFLOW_ID・
  cwd は対象の根。loop_group は until_bash の式を sh で評価し、max_iterations まで）。AI の節（構造の目・修正案の役）は試験が
  返答を渡す。対象は tests/e2e/target-seed/ の git の写し（tests.bin.gitkit）。元の works の tests/test_blk_plan.py・
  test_blk_structure.py の BlockCase・EyeInputsCase の当たる場合を写す。
- 筋書き: Archon の `workflow test` で fixtures/*.stubs.yaml を回す（配線だけ。止めた Archon の源が無ければ見送る。tests/archon.py）。
"""
import copy
import hashlib
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import archon
from tests.bin import hermetic, trimmed
from tests.bin.gitkit import committed_copy, git
from tests.layers import scan
from tests.workflows import copied

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "plan"
SCRIPTS = BLOCK / "scripts"
COMMANDS = BLOCK / "commands"
LIB = ROOT / "lib"
SEED = ROOT / "tests" / "e2e" / "target-seed"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import carry  # noqa: E402
import converge  # noqa: E402
import eye  # noqa: E402
import gatemarks  # noqa: E402
import libdocs  # noqa: E402
import outcome  # noqa: E402
import planblk  # noqa: E402
import planbrief  # noqa: E402
import planmarks  # noqa: E402
import policy  # noqa: E402
import reads  # noqa: E402
import replan  # noqa: E402
import planfile  # noqa: E402  （lib/graphloops を sys.path に足す。engine より先に）
import ripple  # noqa: E402
import rolekit  # noqa: E402
import structmark  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

RUN_ID = "run-plan"
NO_DEADLINE = 1728000000
INPUTS = {"start": "", "units": "[]", "judgment": "", "world": "null", "spec": "null", "review": "", "ruling": "[]",
          "conflicts": "null", "prior_failures": "null"}
RETURNED = ["ready", "plan", "structure", "ripple", "depth", "round"]
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
NIT = "stats.py mean: 変数名が短い"
LOOSE = "stats.py: 全体の書き方"
# 役の指示書の写しの台帳（K9。tests/workflows/copied.py）。元は今の works（raiki61/claude-plugins の
# 2aa7c66cf7abe1fe09699ac2942d107123214168）の works/ の下
FIX_PLAN_TITLE = "# P2-10 修正案（writer の仕事。書く前に出す）\n"
COPIED = {
    "fix-plan.md": (
        [("works/.shared/core/gl-prompts/prompts/review-loop/p2.fix_plan.md",
          "381674c83992c9b0955f961e1e7ff2b5fd451458902f60842e36b547eeb26b95", 3485)],
        [(FIX_PLAN_TITLE,
          "お前は修正案の役で、新しい会話で起きている。役の定義・直す単位と番号・判定の処方・構造の目の行・世界の解の行・波及の一覧・"
          "前の回の拒否の理由（在れば）は、機械が材料のファイルに書いた。先に材料のファイル `$plan-prep.output.brief` を Read で読み、"
          "その指示に従え。\n\n" + FIX_PLAN_TITLE,
          "頭の 1 行（材料のファイルを読め）"),
         (FIX_PLAN_TITLE + "\n"
          "今の周に直す単位（各行の `no` は engine が振った番号。**key を写さず no の整数で指せ**——engine が名前に戻して記録する）: "
          "{{record.units | pick key,label,disposition}}\n"
          "問いの台帳（fork の出どころ・depends に挙がった単位は待ってよい——案に入れなくてよい）: "
          "{{?record.questions | pick key,kind,status,origin,depends}}\n"
          "判定者の見立て: {{record.process.diagnosis | pick framing,one_shot,one_shot_closes}}\n"
          "判定者の先行例（世界の解）: {{?record.process.precedents}}\n"
          "リポジトリ: {{inputs.cwd}}（読む版: `{{inputs.review_rev}}`）\u3000BASE: `{{record.base}}`\u3000観点の正本: {{inputs.review_md}}\n\n",
          FIX_PLAN_TITLE + "\n",
          "engine の雛形の 5 行を外す（材料のファイルが同じ物を持つ）"),
         ("の no（上の一覧の番号。", "の no（材料の一覧の番号。", "no は材料の一覧で指す")]),
    "structure-eye.md": (
        [("works/blk-structure/commands/structure-eye.md",
          "e6927788ec3f660e996d8c723fc86792f4929495afc2b68fb97b0d75610ca98f", 1238)],
        []),
}
DIRTY_ROW = {"verdict": "汚れる", "faces": [5], "evidence": ["/units/0/id"], "reason": "骨組みの無い口が増える",
             "chosen": "既存の関数の中で直す", "chosen_reason": "骨組みが在る"}
WORLD_ROW = {"finding": 1, "where": "stats.py", "class_id": "mean-denominator", "problem": "平均の分母の取り違え",
             "activity": "算術", "practice": "算術平均は要素の数で割る", "sources": [], "applies": "mean の分母",
             "not_applies": "", "versus": {"proposed": "分母を直す", "verdict": "same", "challenge": ""}, "basis": "knowledge"}


def load():
    return yaml.safe_load((BLOCK / "works-factory-plan.yaml").read_text(encoding="utf-8"))


def nodes(doc, *, inner=True):
    """節を並びの順に（inner なら loop_group の中の節も）"""
    for n in doc["nodes"]:
        yield n
        if inner and "loop_group" in n:
            yield from n["loop_group"]["nodes"]


def node(doc, nid):
    return next(n for n in nodes(doc) if n["id"] == nid)


def unit(key, label="block", disposition="do-now"):
    u = {"key": key, "label": label, "reason": f"事実: {key}。反証: 無し"}
    if disposition:
        u["disposition"] = disposition
    return u


def judgment(*extra):
    return {"framing": "算術平均と上限の枝の取り違え", "one_shot": "2 行を直す", "one_shot_closes": [MEAN, CLAMP],
            "units": [unit(MEAN), unit(CLAMP), *extra], "questions": []}


def catalog(*rows):
    return list(rows) or [{"id": MEAN, "paths": ["stats.py"], "summary": "mean の分母"},
                          {"id": CLAMP, "paths": ["stats.py"], "summary": "clamp の上限の枝"}]


def item(*keys, **more):
    return {"unit_keys": list(keys), "approach": "mean の分母を len(xs) に、clamp の上限の枝を hi に直す",
            "adds": [{"kind": "function", "name": "clamp", "canonical": "stats.py の clamp（既存の正本）"}], "removes": [],
            "shrink_first": "足す物は無い。式と戻り値を 1 か所ずつ直すだけで足りる", "narrows": [], "route": "tdd",
            "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均がその真ん中の値になる",
                       "path": "stats.mean を本物のまま呼び、戻り値を断言する", "red_kind": "assertion",
                       "red_why": "今の分母は len(xs) - 1 なので mean([1, 3]) が 4.0 を返す"}],
            "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
            "allowed_paths": ["stats.py", "test_stats.py"], "out_of_scope": [], **more}


def narrow(**more):
    return {"what": "空の列の mean が例外を投げる", "why": "空の列の平均は 0 割りの例外のまま残す", **more}


class _NodeFailed(Exception):
    """試験が落とした script の節（Archon は節を failed にして、後の節の trigger_rule に渡す）"""


FORK = "f0" * 20   # 差分の run の差分の根（読む版と違う版）


class Run:
    """1 つの run の置き場と対象。include(…) で計画のブロックを 1 度差し込む（Archon と同じ順に script を回す）"""

    def __init__(self, case, *, start=None, units=None, judge=None, world=None):
        self.case = case
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.art = self.tmp / "art"
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.inputs = dict(INPUTS)
        self.inputs["start"] = self.pointer("start/start.json", {"base_rev": self.base, "review_rev": self.base,
                                                                  "test_cmd": "", "tdd_suite": "",
                                                                  "thickness": "", "policy_md": "", "lang": "日本語",
                                                                  **(start or {})})
        self.inputs["units"] = json.dumps(catalog() if units is None else units, ensure_ascii=False)
        self.inputs["judgment"] = self.pointer("judge/judgment.json", judgment() if judge is None else judge)
        if world is not None:
            self.inputs["world"] = self.pointer("judge/world.jsonl", world, lines=True)
        self.doc = load()
        self.out = {}
        self.status = {}
        self.env_extra = {}
        self.config = self.tmp / "claude"   # 隔離した設定の置き場（読んだ証拠の記録の根は試験が作る）

    def pointer(self, rel, doc, *, lines=False):
        p = self.art / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in doc) if lines else json.dumps(doc, ensure_ascii=False)
        p.write_text(text, encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})

    def env(self, bound, root):
        named = {f"INPUTS_{k.upper()}": v for k, v in {**self.inputs, **bound}.items()}
        named.update(ARTIFACTS_DIR=str(self.art), WORKFLOW_ID=RUN_ID, WORKS_FACTORY_ROOT=str(root),
                     PYTHONDONTWRITEBYTECODE="1", WORKS_LIBDOCS_WEB="off", CLAUDE_CONFIG_DIR=str(self.config))
        named.update(self.env_extra)
        return hermetic.child_env(**named)

    def script(self, name, bound=None, *, root=ROOT):
        """script を子で回す。終了の値 0 と、標準出力の JSON 1 つを確かめて返す。root は lib/ を探す根（WORKS_FACTORY_ROOT）"""
        p = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py")], cwd=str(self.repo), env=self.env(bound or {}, root),
                           capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
        self.case.assertEqual(p.returncode, 0, f"{name}.py が落ちた: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def value(self, ref):
        """with: の値（$<節>.output[.<欄>] か $LOOP_PREV.<節>.output.<欄> か {from, if_skipped} か字でない定数）を Archon と同じ字に
        する（字はそのまま・ほかは JSON。$LOOP_PREV は輪の 1 周目は空の字）"""
        if not isinstance(ref, (str, dict)):
            return json.dumps(ref)
        prev = re.fullmatch(r"\$LOOP_PREV\.([\w-]+)\.output\.(\w+)", ref) if isinstance(ref, str) else None
        if prev:
            got = self.loop_prev.get(prev.group(1), {}).get(prev.group(2), "")
            return got if isinstance(got, str) else json.dumps(got, ensure_ascii=False)
        if isinstance(ref, dict):
            nid = ref["from"].split(".")[0][1:]
            if self.status.get(nid) != "ok":
                return json.dumps(ref.get("if_skipped"))
            ref = ref["from"]
        m = re.fullmatch(r"\$([\w-]+)\.output(?:\.(\w+))?", ref)
        got = self.out[m.group(1)]
        got = got[m.group(2)] if m.group(2) else got
        return got if isinstance(got, str) else json.dumps(got, ensure_ascii=False)

    def when(self, expr):
        """when: の式（==・!= と && だけ）を前の節の出力で評価する"""
        ok = True
        for part in expr.split("&&"):
            m = re.fullmatch(r"\s*\$([\w-]+)\.output\.(\w+)\s*(==|!=)\s*'?([\w]+)'?\s*", part)
            nid, field, op, want = m.groups()
            if self.status.get(nid) != "ok":
                return False
            got = self.out[nid][field]
            same = (str(got).lower() if isinstance(got, bool) else str(got)) == want
            ok = ok and same == (op == "==")
        return ok

    def until(self, expr):
        """until_bash を sh で評価する（$<節>.output.<欄> を字に替えて）"""
        text = re.sub(r"\$([\w-]+)\.output\.(\w+)", lambda m: str(self.out[m.group(1)][m.group(2)]).lower(), expr)
        return subprocess.run(["sh", "-c", text], env=hermetic.child_env()).returncode == 0

    def include(self, *, eye=None, writer=None, typed=True, **inputs):
        """計画のブロックを 1 度差し込み、返す節の出力を返す。eye(structure_file) と writer(回の番号, 材料の字) は役の返答。
        typed なら役の返答を節の output_format で照らす（Archon と同じく受け付けの前に）"""
        self.inputs.update(inputs)
        self.out, self.status, self.typed, self.loop_prev = {}, {}, typed, {}
        self.walk(self.doc["nodes"], eye or eye_clean, writer or writer_ok)
        return self.out[self.doc["returns"]]

    def runs(self, n):
        deps = n.get("depends_on") or []
        states = [self.status.get(d) for d in deps]
        rule = n.get("trigger_rule", "all_success")
        if rule == "all_done":
            ok = True
        elif rule == "one_success":
            ok = "ok" in states
        elif rule == "none_failed_min_one_success":
            ok = "ok" in states and "failed" not in states
        else:
            ok = all(s == "ok" for s in states)
        return ok and (self.when(n["when"]) if "when" in n else True)

    def walk(self, body, eye_reply, writer):
        for n in body:
            if not self.runs(n):
                self.status[n["id"]] = "skipped"
                continue
            if "loop_group" in n:
                lg = n["loop_group"]
                self.loop_prev = {}
                for i in range(1, lg["max_iterations"] + 1):
                    self.walk(lg["nodes"], eye_reply, writer)
                    self.loop_prev = {b["id"]: self.out[b["id"]] for b in lg["nodes"] if self.status.get(b["id"]) == "ok"}
                    if self.until(lg["until_bash"]):
                        break
                else:
                    self.case.fail(f"輪 {n['id']} が max_iterations に当たった（until_bash で抜けない）")
                self.out[n["id"]], self.status[n["id"]] = json.dumps(self.out[lg["nodes"][-1]["id"]]), "ok"
                continue
            if "command" in n or "prompt" in n:
                got = (eye_reply(self.out["structure-measure"]["structure_file"]) if n["id"] == "structure-eye"
                       else writer(self.out["plan-prep"]["attempt"],
                                   pathlib.Path(self.out["plan-prep"]["brief"]).read_text(encoding="utf-8")))
                if self.typed:
                    self.case.assertEqual(validate_schema(got, n["output_format"]), [], f"{n['id']} の見本が型に合わない")
            else:
                try:
                    got = self.script(n["script"], {k: self.value(v) for k, v in (n.get("with") or {}).items()})
                except _NodeFailed:
                    self.status[n["id"]] = "failed"
                    continue
                self.case.assertEqual(validate_schema(got, n["output_format"]), [], n["id"])
            self.out[n["id"]], self.status[n["id"]] = got, "ok"

    def file(self, ptr):
        self.case.assertEqual((ptr["type"], ptr["run_id"]), ("archon_artifact", RUN_ID))
        p = self.art / ptr["path"]
        self.case.assertTrue(p.is_file() and p.stat().st_size > 0, f"指し札の先が無いか空: {ptr['path']}")
        return p

    def json(self, ptr):
        return json.loads(self.file(ptr).read_text(encoding="utf-8"))


def eye_clean(structure_file):
    doc = json.loads(pathlib.Path(structure_file).read_text(encoding="utf-8"))
    return {"rows": [{"unit_id": u["id"], "verdict": "汚れない", "faces": [], "evidence": [f"/units/{i}/id"],
                      "reason": "足す形が増えない"} for i, u in enumerate(eye.measured(doc))]}


def eye_dirty(structure_file, route=None):
    rows = eye_clean(structure_file)["rows"]
    rows[0].update(DIRTY_ROW, evidence=["/units/0/id"])
    if route:
        rows[0].update(route="人に上げる", undecided_because="方針の文書も前の決定も当たったが、どちらの避け方にも決め手が無い",
                       rejected=[{"option": "新しい口を足す", "cost": "知る場所が増える"}])
    return {"rows": rows}


def writer_ok(n, brief):
    return {"plan": [item(1, 2)]}


def writer_of(*replies):
    """回ごとに replies[n-1] を返す役（足りなければ最後の物）"""
    return lambda n, brief: copy.deepcopy(replies[min(n, len(replies)) - 1])


class ShapeCase(unittest.TestCase):
    """返りの約束と入力（docs/design.md の「plan の出力」）"""

    def test_name_inputs_and_return(self):
        doc = load()
        self.assertEqual(doc["name"], "works-factory-plan")
        self.assertEqual({k: v["default"] for k, v in doc["inputs"].items()}, INPUTS)
        self.assertEqual((doc["returns"], doc["outcome_field"]), ("plan", "ready"))

    def test_return_node_carries_exactly_the_contract(self):
        fmt = node(load(), "plan")["output_format"]
        self.assertEqual(fmt["required"], RETURNED)
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURNED))
        self.assertIs(fmt["additionalProperties"], False)
        self.assertEqual(fmt["properties"]["ready"], {"type": "boolean"})
        self.assertEqual(fmt["properties"]["round"]["type"], "integer")
        for key in ("plan", "structure", "ripple"):
            ptr = fmt["properties"][key]
            self.assertEqual((ptr["type"], sorted(ptr["required"])), ("object", ["path", "run_id", "type"]), key)
            self.assertEqual(ptr["properties"]["type"]["enum"], ["archon_artifact"], key)
        row = fmt["properties"]["depth"]["items"]
        self.assertEqual(sorted(row["required"]), ["depth", "unit_id", "why"])
        self.assertEqual(row["properties"]["depth"]["enum"], ["軽量", "標準"])

    def test_composed_block_declares_no_run_owned_keys(self):
        """include された工程の頭のこれらの鍵は Archon が警告つきで落とす（guides/authoring-workflows.md の Composed behaviour）"""
        doc = load()
        for key in ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout"):
            self.assertNotIn(key, doc, key)

    def test_role_nodes_are_read_only_and_isolated(self):
        doc = load()
        roles = [n for n in nodes(doc) if any(k in n for k in scan.ROLE_KINDS)]
        self.assertEqual([n["id"] for n in roles], ["structure-eye", "plan-writer", "plan-writer-fix"])
        for n in roles:
            self.assertIs(n["mutates_checkout"], False, n["id"])
            self.assertEqual(n["settingSources"], ["user"], n["id"])
            self.assertEqual(n["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False}, n["id"])
            self.assertNotIn("context", n, n["id"])
            self.assertEqual(n["model"], "opus", n["id"])
        eye_node, writer, fix = roles
        self.assertEqual((eye_node["allowed_tools"], eye_node["effort"]), ([], "high"))
        self.assertEqual((writer["allowed_tools"], writer["effort"]), (["Read", "Grep", "Glob", "WebSearch", "WebFetch"], "medium"))
        launch = ("model", "effort", "allowed_tools", "settingSources", "sandbox", "mutates_checkout", "idle_timeout", "retry")
        self.assertEqual({k: fix[k] for k in launch}, {k: writer[k] for k in launch}, "出し直しの役は修正案の役と同じ起こし方")

    def test_resubmit_role_continues_the_writer_conversation(self):
        """#571: 拒まれた後の出し直しは plan-writer-fix が plan-writer の会話の続きで起きる。輪は会話を続け（fresh_context: false）、
        振り分けは plan-prep の resubmit（拒まれた周の値 $LOOP_PREV.plan-accept.output.ok を受ける）。plan-writer-fix は plan-writer の
        後ろの層に置き（並んだ層は会話を切る）、context を書かない。受け付けは両方の返答を if_skipped: null で受ける"""
        doc = load()
        body = {n["id"]: n for n in node(doc, "plan-loop")["loop_group"]["nodes"]}
        self.assertEqual(list(body), ["plan-prep", "plan-writer", "plan-writer-fix", "plan-accept"])
        self.assertEqual(body["plan-prep"]["with"]["prev"], "$LOOP_PREV.plan-accept.output.ok")
        self.assertIn("resubmit", body["plan-prep"]["output_format"]["required"])
        self.assertEqual(body["plan-writer"]["when"], "$plan-prep.output.resubmit != true")
        fix = body["plan-writer-fix"]
        self.assertEqual(fix["when"], "$plan-prep.output.resubmit == true")
        self.assertEqual((fix["depends_on"], fix["trigger_rule"]), (["plan-prep", "plan-writer"], "none_failed_min_one_success"))
        self.assertNotIn("context", fix)
        self.assertIn("$plan-prep.output.brief", fix["prompt"])
        accept = body["plan-accept"]
        self.assertEqual((accept["depends_on"], accept["trigger_rule"]),
                         (["plan-writer", "plan-writer-fix"], "none_failed_min_one_success"))
        self.assertEqual((accept["with"]["reply"], accept["with"]["fix_reply"]),
                         ({"from": "$plan-writer.output", "if_skipped": None}, {"from": "$plan-writer-fix.output", "if_skipped": None}))

    def test_resubmit_schema_is_the_writer_schema_without_required_plus_whole_plan(self):
        doc = load()
        first, fix = node(doc, "plan-writer")["output_format"], node(doc, "plan-writer-fix")["output_format"]
        self.assertEqual(fix["required"], [])
        self.assertEqual(fix["properties"].pop(planfile.WHOLE_PLAN), {"type": "boolean"})
        self.assertEqual({**fix, "required": first["required"]}, first)

    def test_eye_command_reads_only_its_prep(self):
        """構造の目は道具なしの独立の会話: 指示書が読むのは支度の節の出力だけ"""
        text = (COMMANDS / "structure-eye.md").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"\$[A-Za-z][\w.-]*", text)), {"$structure-eye-prep.output.prompt"})
        refs = set(re.findall(r"\$[A-Za-z][\w.-]*", (COMMANDS / "fix-plan.md").read_text(encoding="utf-8")))
        self.assertEqual(refs, {"$plan-prep.output.brief"})

    def test_fix_plan_command_is_the_original_with_only_the_allowed_edits(self):
        """修正案の役の指示書は元の p2.fix_plan.md の文のまま: 許した直しを逆に当てると元のバイトに戻る"""
        self.assertEqual(copied.restore_problems(COMMANDS / "fix-plan.md", *COPIED["fix-plan.md"]), [])

    def test_eye_command_is_the_original(self):
        """構造の目の指示書は元の blk-structure/commands/structure-eye.md の字のまま（台帳の直しは無く、書き直しは copied_rewrites.json の件だけ）"""
        self.assertEqual(copied.restore_problems(COMMANDS / "structure-eye.md", *COPIED["structure-eye.md"]), [])

    def test_deadlines_are_all_twenty_days(self):
        keys = ("timeout", "idle_timeout")
        for n in nodes(load()):
            for key in keys:
                if key in n:
                    self.assertEqual(n[key], NO_DEADLINE, f"{n['id']}.{key}")
            if "script" in n or "loop_group" in n:
                self.assertEqual(n.get("timeout"), NO_DEADLINE, n["id"])
            if "command" in n or "prompt" in n:
                self.assertEqual(n.get("idle_timeout"), NO_DEADLINE, n["id"])

    def test_loops_give_up_in_the_body_before_max_iterations(self):
        doc = load()
        for nid, accept, fresh in (("structure-eye-loop", "structure-eye-accept", False), ("plan-loop", "plan-accept", False)):
            lg = node(doc, nid)["loop_group"]
            self.assertEqual(lg["max_iterations"], rolekit.GIVE_UP_AFTER, nid)
            self.assertIs(lg["fresh_context"], fresh, nid)
            self.assertEqual(lg["until_bash"], f'done=${accept}.output.done; test "$done" = true', nid)

    def test_writer_output_carries_works_fields_and_gate_marks(self):
        fmt = node(load(), "plan-writer")["output_format"]
        row = fmt["properties"]["plan"]["items"]
        self.assertIn("structure", row["properties"])
        self.assertEqual(row["properties"]["unit_keys"]["items"]["type"], ["integer", "string"])
        marks = row["properties"]["narrows"]["items"]["properties"]
        self.assertLessEqual({"decided_by", "undecided_because", "fences", "world", "recommend", "no_narrow"}, set(marks))
        self.assertNotIn("description", fmt)

    def test_role_schemas_match_their_lib_owners(self):
        """役の型は lib の持ち主の型の写し（Archon の YAML は lib を読めない）。写しが持ち主とずれたら落ちる"""
        def bare(schema):
            if isinstance(schema, dict):
                return {k: bare(v) for k, v in schema.items() if not (k in ("note", "description") and isinstance(v, str))}
            return [bare(v) for v in schema] if isinstance(schema, list) else schema

        doc = load()
        fmt = node(doc, "plan-writer")["output_format"]["properties"]
        row = fmt["plan"]["items"]["properties"]
        for key, want in planmarks.FIELD_SCHEMA.items():
            self.assertEqual(row[key], want, key)
        self.assertEqual(set(fmt["plan"]["items"]["required"]), set(planmarks.CORE_KEYS + planmarks.REQUIRED))
        self.assertIn(gatemarks.NO_NARROW, row["narrows"]["items"]["required"])
        marks = row["narrows"]["items"]["properties"]
        for key in gatemarks.FIELDS:
            self.assertEqual(marks[key], bare(gatemarks.MARK_SCHEMA[key]), key)
        self.assertEqual(marks[gatemarks.NO_NARROW], bare(gatemarks.NO_NARROW_SCHEMA))
        self.assertEqual(fmt[converge.ANSWERS], converge.ANSWER_SCHEMA)
        owner = json.loads((LIB / "design-row.schema.json").read_text(encoding="utf-8"))
        added = {"route_reason"}           # 受け付けが足す
        dropped = {"precedents"}           # 今の works の structure-eye の型に無い
        unrequired = {"route"}             # 今の works の structure-eye の型は任意（受け付けが既定の行き先を足す）
        rows = node(doc, "structure-eye")["output_format"]["properties"]["rows"]["items"]
        self.assertEqual(trimmed.without_trimmed(rows["properties"]),
                         {k: v for k, v in bare(owner["properties"]).items() if k not in added | dropped})
        self.assertEqual(rows["required"], [k for k in owner["required"] if k not in added | unrequired])
        self.assertIs(rows["additionalProperties"], owner["additionalProperties"])

    def test_scripts_are_read_only_uv_scripts(self):
        """E7: 読むだけの script の節も mutates_checkout: false。script は uv の宣言を頭に持ち、.pyc を書かない（test-gate と同じ）"""
        for n in nodes(load()):
            if "script" in n:
                self.assertIs(n.get("mutates_checkout"), False, n["id"])
                text = (SCRIPTS / f"{n['script']}.py").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# /// script\n"), n["script"])
                self.assertIn("sys.dont_write_bytecode = True", text, n["script"])

    def test_reads_roles_are_the_role_nodes_by_their_tools(self):
        """読んだ証拠の節が名指す役は YAML の役の節と同じ: 道具を持つ役は plan_reads.ROLE、持たない役は QUIET（役が道具を得たのに
        null と書く黙った緩みを赤にする）"""
        spec = importlib.util.spec_from_file_location("plan_script_plan_reads", SCRIPTS / "plan_reads.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def every(body):
            for n in body:
                yield n
                yield from every(n.get("loop_group", {}).get("nodes", []))
        roles = [n for n in every(load()["nodes"]) if any(k in n for k in scan.ROLE_KINDS)]
        # 出し直しの役は修正案の役の会話の続きなので、読んだ証拠は同じ役に数える
        self.assertEqual({n["id"] for n in roles if n.get("allowed_tools")} - {"plan-writer-fix"}, {mod.ROLE})
        self.assertEqual({n["id"] for n in roles if not n.get("allowed_tools")}, set(mod.QUIET))

    def test_fallback_names_match_lib(self):
        """落ちない 2 つの節（round・plan）は lib を読めない時に標準ライブラリだけで同じ置き場に書く。その字が lib と同じ"""
        def loaded(name):
            spec = importlib.util.spec_from_file_location(f"plan_script_{name}", SCRIPTS / f"{name}.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

        rnd, col = loaded("round"), loaded("plan_collect")
        self.assertEqual((rnd.PLAN_DIR, rnd.ROUND_FILE, rnd.STRUCTURE_DIR),
                         (planfile.PLAN_DIR, planfile.ROUND_FILE, planfile.STRUCTURE_DIR))
        self.assertEqual((col.PLAN_DIR, col.ROUND_FILE, col.RIPPLE_FILE, col.DESIGN_FILE, col.UNREAD_STRUCTURE, col.FIELDS_FILE,
                          col.STATE_FILE),
                         (planfile.PLAN_DIR, planfile.ROUND_FILE, planfile.RIPPLE_FILE, planfile.DESIGN_FILE,
                          planfile.UNREAD_STRUCTURE, planmarks.FIELDS_FILE, structmark.STATE_FILE))

    def test_script_names_differ_from_lib_modules(self):
        """script のフォルダが sys.path の頭に来るので、lib のモジュールと同じ名の script は import で自分を読む"""
        lib = {p.stem for p in LIB.glob("*.py")}
        mine = {p.stem for p in SCRIPTS.glob("*.py")}
        self.assertEqual(mine & lib, set())
        self.assertEqual(mine, {n["script"] for n in nodes(load()) if "script" in n})


class CopiedTextsCase(unittest.TestCase):
    """指示書の写しの台帳（K9）: commands/ の全部が台帳に在り、許した直しを逆に当てると元のバイトに戻る"""

    def test_every_command_is_its_original_with_only_ledgered_edits(self):
        names = sorted(p.name for p in COMMANDS.glob("*.md"))
        self.assertEqual(names, sorted(COPIED), "台帳に無い指示書か、指示書の無い台帳の行")
        self.assertLessEqual(copied.rewritten(COMMANDS), set(COPIED), "台帳に無い指示書の書き直し")
        for name in names:
            with self.subTest(name):
                self.assertEqual(copied.restore_problems(COMMANDS / name, *COPIED[name]), [])
class EyeTypeCase(unittest.TestCase):
    """構造の目の返答の型の正本は目の節の output_format だけ（受け付けの eye.problems は行の意味だけを見る）"""

    def fmt(self) -> dict:
        return node(load(), "structure-eye")["output_format"]

    def test_trimmed_min_length_kept_by_pattern(self):
        self.assertEqual(trimmed.missing_patterns(self.fmt()), [])

    def test_vocabulary_matches_output_format(self):
        """受け付けと指示書が使う語（eye.VERDICTS・eye.ROUTES）と形の数（eye.FORMS）は、目の節の output_format の enum と faces の範囲"""
        row = self.fmt()["properties"]["rows"]["items"]["properties"]
        self.assertEqual(row["verdict"]["enum"], list(eye.VERDICTS))
        self.assertEqual(row["route"]["enum"], list(eye.ROUTES))
        self.assertEqual((row["faces"]["items"]["minimum"], row["faces"]["items"]["maximum"]), (1, len(eye.FORMS)))

    def test_rows_outside_the_type_are_rejected(self):
        """元 lib/tests/test_structure_eye.py の test_bad_rows_are_named の型の側: 知らない行き先・形の外の欄・形の番号の型"""
        clean = {"unit_id": "u-1", "verdict": "汚れない", "faces": [], "evidence": ["/units/0/measure"], "reason": "形が増えない"}
        self.assertEqual(validate_schema({"rows": [clean]}, self.fmt()), [])
        for name, row in (("知らない行き先", {**clean, "route": "後で"}), ("形の外の欄", {**clean, "note": "x"}),
                          ("真偽を形の番号に", {**clean, "faces": [True]}), ("形の番号の外", {**clean, "faces": [7]})):
            with self.subTest(name):
                self.assertTrue(validate_schema({"rows": [row]}, self.fmt()))


class StageACase(unittest.TestCase):
    """段 A（元 tests/test_blk_structure.py の BlockCase・EyeInputsCase）"""

    def measure(self, run, **inputs):
        run.inputs.update(inputs)
        rnd = run.script("round")
        return run.script("structure_measure", {"dir": rnd["dir"]})

    def test_measures_units_and_writes_empty_design_rows(self):
        run = Run(self)
        got = self.measure(run)
        doc = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "ok", doc)
        self.assertEqual([u["id"] for u in doc["units"]], [MEAN, CLAMP])
        self.assertEqual(pathlib.Path(got["design_file"]).stat().st_size, 0)
        self.assertEqual((got["eye"], got["reused"]), (True, False))

    def test_measure_failure_and_unreadable_units_do_not_stop(self):
        run = Run(self)
        shutil.rmtree(run.repo / ".git")   # git の無い対象では実測が落ちる
        doc = json.loads(pathlib.Path(self.measure(run)["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "failed", doc)
        self.assertTrue(doc["reason"])
        run = Run(self)
        got = self.measure(run, units="{壊れた")
        doc = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "failed", doc)
        self.assertFalse(got["eye"])

    def test_unit_without_paths_is_skipped_and_named(self):
        run = Run(self, units=[*catalog(), {"id": LOOSE, "paths": [], "summary": "書き方の全体"}],
                  judge=judgment(unit(LOOSE)))
        out = run.file(run.include(writer=writer_of({"plan": [item(1, 2, 3)]}))["structure"]).parent
        doc = json.loads((out / "structure.json").read_text(encoding="utf-8"))
        self.assertEqual([u["id"] for u in doc["units"]], [MEAN, CLAMP])
        self.assertEqual(json.loads((out / "skipped-units.json").read_text(encoding="utf-8")), [LOOSE])
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn(f"構造の目が見ていない単位（paths が空で実測しなかった）: `{LOOSE}`", brief)

    def test_eye_sees_concept_rows_and_policy(self):
        run = Run(self, units=[{"id": MEAN, "paths": ["src/edge.py"], "summary": "境の節が結末の語を書く"}],
                  start={"policy_md": "POLICY.md"})
        files = {"src/report.py": 'OUT = "round_limit"\n', "src/edge.py": 'x = "round_limit"\n',
                 "POLICY.md": "決まり: 結末の語は report.py だけが持つ\n",
                 "docs/concepts.md": "# 地図\n\n### `outcome` run の結末\n\n- 状態: 住処あり\n- 住処: `src/report.py`\n",
                 "docs/concepts.json": json.dumps({"exclude": ["docs/**"], "concepts": {"outcome": {
                     "status": "住処あり", "fences": [{"what": "結末の語", "pattern": "\"round_limit\"",
                                                     "allowed": ["src/report.py"], "known": {}}]}}}, ensure_ascii=False)}
        for rel, text in files.items():
            (run.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (run.repo / rel).write_text(text, encoding="utf-8")
        git(run.repo, "add", "-A")
        git(run.repo, "commit", "-q", "-m", "concepts")
        got = self.measure(run)
        prompt = run.script("eye_prep", {"structure_file": got["structure_file"]})["prompt"]
        self.assertIn("### `outcome` run の結末", prompt)
        self.assertIn("known_places", prompt)
        self.assertIn("結末の語は report.py だけが持つ", prompt)

    MAP = ("# 地図\n\n### `outcome` run の結末\n\n- 状態: 住処あり\n- 住処: `src/report.py`\n\n"
           "### `halt` 止め札\n\n- 状態: 住処あり\n- 住処: `src/halt.py`\n")
    TABLE = {"exclude": ["docs/**"], "concepts": {
        "outcome": {"status": "住処あり", "fences": [{"what": "結末の語", "pattern": "\"round_limit\"",
                                                     "allowed": ["src/report.py"], "known": {}}]},
        "halt": {"status": "住処あり", "fences": [{"what": "止め札", "pattern": "\"STOP\"", "allowed": ["src/halt.py"],
                                                  "known": {}}]}}}

    def target(self, run, files):
        """元 tests/test_blk_structure.py の EyeInputsCase.target の形を種に commit する"""
        for rel, text in files.items():
            (run.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (run.repo / rel).write_text(text, encoding="utf-8")
        git(run.repo, "add", "-A")
        git(run.repo, "commit", "-q", "-m", "target")

    def edge_run(self, **start):
        return Run(self, units=[{"id": MEAN, "paths": ["src/edge.py"], "summary": "境の節が結末の語を書く"}], start=start)

    def test_fresh_measure_drops_old_eye_state(self):
        run = Run(self)
        rnd = run.script("round")
        out = run.art / "plan" / planfile.read_round(run.art / rnd["dir"])["structure"]
        out.mkdir(parents=True)
        (out / eye.EYE_FILE).write_text('{"status": "gave_up"}', encoding="utf-8")
        (out / planfile.DESIGN_FILE).write_text('{"unit_id": "前の行"}\n', encoding="utf-8")
        got = run.script("structure_measure", {"dir": rnd["dir"]})
        self.assertFalse((out / eye.EYE_FILE).exists())
        self.assertEqual(pathlib.Path(got["design_file"]).read_bytes(), b"")

    def test_concept_rows_only_for_unit_paths(self):
        """元 tests/test_blk_structure.py の test_eye_sees_concept_rows_for_unit_paths"""
        run = self.edge_run()
        self.target(run, {"src/report.py": 'OUT = "round_limit"\n', "src/edge.py": 'x = "round_limit"\n',
                          "src/halt.py": 'S = "STOP"\n', "docs/concepts.md": self.MAP,
                          "docs/concepts.json": json.dumps(self.TABLE, ensure_ascii=False)})
        got = self.measure(run)
        unit_ = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))["units"][0]
        self.assertEqual([r["id"] for r in unit_["concepts"]["rows"]], ["outcome"])
        self.assertEqual([(x["concept"], x["path"], x["home"], x["known_places"]) for x in unit_["concepts"]["places"]],
                         [("outcome", "src/edge.py", False, 2)])
        prompt = run.script("eye_prep", {"structure_file": got["structure_file"]})["prompt"]
        self.assertIn("### `outcome` run の結末", prompt)
        self.assertNotIn("### `halt`", prompt)

    def test_no_map_no_table_measures_only(self):
        run = self.edge_run()
        self.target(run, {"src/edge.py": 'x = "round_limit"\n'})
        got = self.measure(run)
        doc = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["units"][0]["concepts"], {"rows": [], "places": []})
        self.assertFalse((run.repo / "docs").exists())

    def test_eye_sees_root_map_and_cut_policy(self):
        """元 tests/test_blk_structure.py の test_eye_sees_policy_text（根の地図の文書）と、長い方針の文書の切りの印"""
        run = self.edge_run(policy_md="POLICY.md")
        long_policy = "決まり: 結末の語は report.py だけが持つ\n" + "あ" * planfile.context.TEXT_CAP
        self.target(run, {"src/edge.py": 'x = "round_limit"\n', "POLICY.md": long_policy,
                          "AGENTS.md": "# 対象の決まり\n\n層は下へだけ依存する\n"})
        got = self.measure(run)
        prompt = run.script("eye_prep", {"structure_file": got["structure_file"]})["prompt"]
        self.assertIn("結末の語は report.py だけが持つ", prompt)
        self.assertIn("層は下へだけ依存する", prompt)
        cut = len(long_policy) - planfile.context.TEXT_CAP
        self.assertIn(f"…（{cut} 字を切った）", prompt)

    def test_measure_records_timing(self):
        doc = json.loads(pathlib.Path(self.measure(Run(self))["structure_file"]).read_text(encoding="utf-8"))
        timing = doc["timing"]
        self.assertIsInstance(timing[eye.WALL], float)
        for key in ("started_at", "finished_at"):
            self.assertRegex(timing[key], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$", key)

    def test_same_units_and_head_reuse_the_measure(self):
        run = Run(self)
        first = run.include()
        second = run.include(review=run.pointer("review/p2.plan_review.json", {"faces": []}))
        self.assertEqual(run.out["structure-measure"]["reused"], True)
        self.assertEqual(run.status["structure-eye-loop"], "skipped")
        self.assertEqual(first["structure"], second["structure"])


class AcceptCase(unittest.TestCase):
    """受け付け（欠けごとに名指して拒む・3 回目で諦める・通った案の置き方）"""

    def reasons(self, run):
        return [r for r in rolekit.rejected(run.art / "plan" / "r1", "plan")]

    def test_accepted_plan_files(self):
        run = Run(self)
        out = run.include(writer=writer_of({"plan": [item(1, 2, narrows=[narrow(
            no_narrow="狭めない案として空の列に 0 を返す形を当たったが、呼び手が例外を捕まえている")])]}))
        self.assertIs(out["ready"], True, out)
        fields = run.json(out["plan"])
        self.assertEqual(sorted(fields), ["fields", "round"])
        self.assertEqual(fields["round"], 1)
        self.assertEqual(fields["fields"][0]["unit_keys"], [MEAN, CLAMP], "役が番号で返した単位が id に戻る")
        self.assertEqual(fields["fields"][0]["route"], "tdd")
        side = json.loads((run.file(out["plan"]).parent / "p2.fix_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(side["plan"][0]["unit_keys"], [MEAN, CLAMP])
        self.assertNotIn("route", side["plan"][0])
        self.assertIn("no_narrow", side["plan"][0]["narrows"][0], "narrows の行に関所の決め手の欄が残る")
        self.assertEqual(json.loads((run.art / "plan" / "r1" / "slots.json").read_text(encoding="utf-8")), [MEAN, CLAMP])
        state = run.json(out["structure"])
        self.assertEqual(state["status"], "ok", state)
        self.assertEqual(run.json(out["ripple"])["error"], "")
        self.assertEqual(out["depth"][0]["unit_id"], MEAN)

    def test_ripple_skips_the_runtime_copy(self):
        """作業ツリーの中の工程の写し（境の RUNTIME_COPY_DIRS）の当たりは、項目ごとの波及にも単位の波及にも数えない"""
        run = Run(self)
        runtime = run.repo / ".archon" / "workflows" / "x" / "y.py"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("from stats import clamp\nclamp(1, 0, 2)\n", encoding="utf-8")
        git(run.repo, "add", "-f", ".archon")
        git(run.repo, "commit", "-qm", "工程の写し")
        out = run.include(writer=writer_of({"plan": [item(1, 2)]}))
        items = run.json(out["ripple"])["items"]
        self.assertEqual([h["at"] for h in items[0]["uncovered"] if h["at"].startswith(".archon/")], [], items)
        units = run.script("ripple_units", {"dir": "plan/r1", "judgment": run.pointer(
            "judge/plus.json", judgment(unit("stats.py +clamp: 上限の枝")))})
        rows = json.loads((run.art / units["ripple_file"]).read_text(encoding="utf-8"))["units"]
        hits = [at for u in rows for r in u["names"] for at in r["code"] + r["tests"]]
        self.assertTrue(hits, rows)
        self.assertEqual([at for at in hits if str(at).startswith(".archon/")], [], rows)

    def reject_once(self, run, bad, *, eye_reply=None):
        out = run.include(eye=eye_reply, writer=writer_of(bad, {"plan": [item(1, 2)]}))
        self.assertIs(out["ready"], False if bad is None else True, out)
        return self.reasons(run)[0]

    def test_missing_unit_rejected(self):
        why = self.reject_once(Run(self), {"plan": [item(1)]})
        self.assertIn("どの案にも入っていない単位", why)
        self.assertIn(CLAMP[:40], why)

    def test_unknown_number_names_allowed_numbers(self):
        why = self.reject_once(Run(self), {"plan": [item(1, 2, 7)]})
        self.assertIn("今の周に直す単位に無い key ['7']", why)
        self.assertIn("案に入れてよい no は [1, 2]", why)

    def test_unit_without_duty_rejected_by_label(self):
        run = Run(self, judge=judgment(unit(NIT, "nit", None)))
        why = self.reject_once(run, {"plan": [item(1, 2, NIT)]})
        self.assertIn("label=nit", why)

    def test_works_field_gaps_rejected(self):
        """型は役の節の output_format が照らす。型に合っても欠けた・誤った works の欄（tdd なのに受け入れテストが無い・direct の訳が無い・
        根の外の範囲）を受け付けが名指す"""
        run = Run(self)
        bad = {"plan": [item(1, tests=[]), item(2, route="direct", allowed_paths=["../outside.py"])]}
        out = run.include(writer=writer_of(bad, {"plan": [item(1, 2)]}))
        self.assertIs(out["ready"], True)
        why = self.reasons(run)[0]
        self.assertTrue(why.startswith(planmarks.REJECT) or planmarks.REJECT in why, why)
        for word in ("plan[0].tests: route が tdd", "plan[1].route_why", "plan[1].allowed_paths[0]"):
            self.assertIn(word, why)

    def test_dirty_structure_row_needs_answer(self):
        run = Run(self)
        out = run.include(eye=eye_dirty, writer=writer_of({"plan": [item(1, 2)]}, {"plan": [item(1, 2, structure=[
            {"row": MEAN, "follows": True}])]}))
        self.assertIs(out["ready"], True, out)
        why = self.reasons(run)[0]
        self.assertIn(f"設計の行 {MEAN} に従うか", why)

    def test_world_row_needs_answer(self):
        run = Run(self, world=[WORLD_ROW])
        out = run.include(writer=writer_of({"plan": [item(1, 2)]}, {"plan": [item(1, 2, structure=[
            {"world": "mean-denominator", "follows": True}])]}))
        self.assertIs(out["ready"], True, out)
        self.assertIn("世界の解の行 mean-denominator にどの項目も答えていない", self.reasons(run)[0])
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn("類 mean-denominator", brief)

    def test_narrow_without_no_narrow_rejected(self):
        run = Run(self)
        # Archon の型（JSON Schema の minLength）は空白も数えるので、空白で埋めた短い答えは型を通って受け付けに届く。
        # 試験の型の照らし（engine.schema）は空白を除いて数えるので、ここでは外す
        short = " " * 18 + "無い"
        out = run.include(typed=False, writer=writer_of({"plan": [item(1, 2, narrows=[narrow(no_narrow=short)])]},
                                                        {"plan": [item(1, 2)]}))
        self.assertIs(out["ready"], True)
        why = self.reasons(run)[0]
        self.assertIn("narrows の行に狭めない案を探した結果", why)
        self.assertEqual((run.status["plan-writer"], run.status["plan-writer-fix"]), ("skipped", "ok"))

    def test_resubmit_brief_carries_the_last_reject_and_the_merged_answer(self):
        """#571: 拒まれた後の回の材料は出し直しの役の短い指示書: 今の周の最後の拒否の文を字のまま貼り、受け付けが合わせた前の答えの
        控えを名指す（材料は会話に在るので貼らない）。前の回の拒否は会話に在るので最後の 1 件だけ"""
        run = Run(self)
        briefs = {}

        def writer(n, brief):
            briefs[n] = brief
            return copy.deepcopy([{"plan": [item(1)]}, {"plan": [item(1, 2), item(2)]}, {"plan": [item(1, 2)]}][n - 1])

        self.assertIs(run.include(writer=writer)["ready"], True)
        first, second = self.reasons(run)
        rnd = run.art / "plan" / "r1"
        self.assertTrue(briefs[3].startswith(rolekit.RESUBMIT_ASK.partition("\n")[0]), briefs[3][:200])
        self.assertIn(second, briefs[3])
        self.assertNotIn(first, briefs[3])
        self.assertIn(str(rolekit.candidate_path(rnd, planfile.ROLE)), briefs[3])
        self.assertNotIn(planfile.UNITS_HEAD, briefs[3])
        self.assertFalse(rolekit.rejects_text_path(rnd, planfile.ROLE).exists(), "拒否の全部のファイルは resume の時だけ書く")

    def test_resume_brief_names_every_reject_of_the_round(self):
        """resume で輪が 1 周目から回り直すと、前の周の値（prev）が空で、1 回目の役が新しい会話で全部の材料から起きる。その材料の
        頭の 1 行が名指すファイルに、この周の拒否の全部が古い順に届く（#345）"""
        run = Run(self)
        bad = {"plan": [item(1)]}
        self.assertIs(run.include(writer=writer_of(bad))["ready"], False)
        rnd = run.art / "plan" / "r1"
        reasons = rolekit.rejected(rnd, planfile.ROLE)
        got = run.script("plan_prep", {"dir": "plan/r1", "prev": ""})
        self.assertEqual((got["resubmit"], got["attempt"]), (False, 4))
        brief = pathlib.Path(got["brief"]).read_text(encoding="utf-8")
        rejects = rolekit.rejects_text_path(rnd, planfile.ROLE)
        self.assertTrue(brief.startswith(rolekit.REJECT_LINE.format(path=rejects)), brief[:200])
        self.assertIn(planfile.UNITS_HEAD, brief)
        self.assertEqual(rejects.read_text(encoding="utf-8"), rolekit.rejects_text(reasons) + "\n")

    def test_partial_resubmit_is_merged_into_the_one_shot_shape(self):
        """#571: 出し直しの役は拒まれた項目だけを返し、受け付けが前の答えの控えと合わせてから照らす。合わせた答え（reply.json・
        p2.fix_plan.json）は 1 回で書いた答えと同じ形"""
        once = Run(self)
        whole = {"plan": [item(1), item(2)]}
        self.assertIs(once.include(writer=writer_of(whole))["ready"], True)
        run = Run(self)
        bad = {"plan": [item(1), item(2, tests=[])]}
        out = run.include(writer=writer_of(bad, {"plan": [item(2)]}))
        self.assertIs(out["ready"], True, out)
        self.assertEqual(len(self.reasons(run)), 1)
        rnd, ref = run.art / "plan" / "r1", once.art / "plan" / "r1"
        for name in (planfile.REPLY_FILE, planfile.FIX_PLAN_FILE):
            with self.subTest(name):
                self.assertEqual(json.loads((rnd / name).read_text(encoding="utf-8")),
                                 json.loads((ref / name).read_text(encoding="utf-8")))
        slot_list = json.loads((rnd / planfile.SLOTS_FILE).read_text(encoding="utf-8"))
        self.assertEqual(json.loads(rolekit.candidate_path(rnd, planfile.ROLE).read_text(encoding="utf-8")),
                         planfile.named(whole, slot_list), "控えは受け付けと同じく単位の名に戻した形")

    def test_empty_resubmit_rechecks_the_previous_answer(self):
        """空の出し直しは前の答えのまま全体を照らし直す（直っていなければ同じ理由で拒む）"""
        run = Run(self)
        out = run.include(writer=writer_of({"plan": [item(1)]}, {}, {"plan": [item(1, 2)]}))
        self.assertIs(out["ready"], True, out)
        first, again = self.reasons(run)
        self.assertEqual(again, first)

    def test_whole_plan_resubmit_drops_items(self):
        """項目を消す出し直しは whole_plan: true と案の全部（plan が丸ごと置き換わる。whole_plan は控えに残り、受けた案には残らない）"""
        run = Run(self)
        out = run.include(writer=writer_of({"plan": [item(1, 2), item(2)]}, {"whole_plan": True, "plan": [item(1, 2)]}))
        self.assertIs(out["ready"], True, out)
        rnd = run.art / "plan" / "r1"
        slot_list = json.loads((rnd / planfile.SLOTS_FILE).read_text(encoding="utf-8"))
        self.assertEqual(json.loads(rolekit.candidate_path(rnd, planfile.ROLE).read_text(encoding="utf-8")),
                         {**planfile.named({"plan": [item(1, 2)]}, slot_list), planfile.WHOLE_PLAN: True})
        self.assertNotIn(planfile.WHOLE_PLAN, json.loads((rnd / planfile.REPLY_FILE).read_text(encoding="utf-8")))

    def test_unit_in_two_items_rejected(self):
        why = self.reject_once(Run(self), {"plan": [item(1, 2), item(2)]})
        self.assertIn("2 つの案に入った単位", why)
        self.assertIn(CLAMP[:40], why)

    def test_string_number_is_a_name_and_asks_for_no(self):
        """元 tests/test_blk_plan.py の test_plan_reply_by_number_string_rejected: 字の "1" は番号に戻さず、知らない名として拒む"""
        why = self.reject_once(Run(self), {"plan": [item("1", "2")]})
        self.assertIn("今の周に直す単位に無い key ['1', '2']", why)
        self.assertIn("no で指せ", why)
        self.assertNotIn("key を字面のまま写せ", why)

    def test_info_defer_question_rejected_by_label(self):
        info, defer, question = "stats.py: 補足の情報", "stats.py clamp: 引数の順が読みにくい", "stats.py: 空の列をどう扱うか"
        run = Run(self, judge=judgment(unit(info, "info", None), unit(defer, "suggest", "defer"),
                                       unit(question, "question", None)))
        why = self.reject_once(run, {"plan": [item(1, 2, info, defer, question)]})
        self.assertIn(planblk.NOT_OWED_REJECT, why)
        for word in ("label=info", "label=suggest（disposition=defer）", "label=question"):
            self.assertIn(word, why)
        self.assertIn("案に入れてよい no（必ず入れる物を含む）は [1, 2]", why)

    def test_every_reason_in_one_rejection(self):
        """元は段ごとに最初の拒否で返した。今は網羅と works の欄の欠けを 1 回の拒否に並べる"""
        why = self.reject_once(Run(self), {"plan": [item(1, tests=[])]})
        self.assertIn(planfile.COVERS_REJECT, why)
        self.assertIn(planmarks.REJECT, why)

    def test_malformed_recommend_rejected(self):
        run = Run(self)
        bad = narrow(no_narrow="狭めない案として空の列に 0 を返す形を当たったが、呼び手が例外を捕まえている",
                     recommend={"answer": "たぶん通す", "note": "空の列は残す", "why": "呼び手が捕まえる"})
        out = run.include(typed=False, writer=writer_of({"plan": [item(1, 2, narrows=[bad])]}, {"plan": [item(1, 2)]}))
        self.assertIs(out["ready"], True)
        why = self.reasons(run)[0]
        self.assertIn(planblk.RECOMMEND_REJECT, why)
        self.assertIn("plan[0].narrows[0]", why)

    def test_rewrite_limit_resolved(self):
        rewrite = {"id": "test_stats.py::TestStats::test_clamp_above_range", "behavior": "上限を超えた値に上限を返す",
                   "old": "lo を返す", "new": "上限を超えたら hi を返す"}
        run = Run(self)
        out = run.include(writer=writer_of({"plan": [item(1, 2, rewrite_tests=[rewrite])]}))
        self.assertIs(out["ready"], True, out)
        self.assertEqual(run.json(out["plan"])["fields"][0]["rewrite_tests"][0]["limit"], "test_stats.py:14")

    def test_fields_are_frozen_in_the_round_trace(self):
        run = Run(self)
        out = run.include()
        raw = run.file(out["plan"]).read_bytes()
        trace = [json.loads(x) for x in (run.art / "plan" / "r1" / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        saved = [r for r in trace if r["op"] == planmarks.SAVED_OP]
        self.assertEqual([(r["round"], r["sha256"]) for r in saved], [(1, hashlib.sha256(raw).hexdigest())])

    def test_role_that_moved_the_tree_is_refused(self):
        """元 tests/test_blk_plan.py の test_readonly_tree_changed_rejected: 役を起こす前の作業ツリーの姿と比べ、書き換え・commit を拒んで
        出し直させる（次の回の支度が姿を取り直す）"""
        def edit(repo):
            (repo / "stats.py").write_text((repo / "stats.py").read_text(encoding="utf-8") + "\n# 役が書いた\n", encoding="utf-8")

        def commit(repo):
            edit(repo)
            git(repo, "commit", "-qam", "役が commit した")

        for name, move in (("書き換え", edit), ("commit", commit)):
            with self.subTest(name):
                run = Run(self)

                def writer(n, brief, run=run, move=move):
                    if n == 1:
                        move(run.repo)
                    return {"plan": [item(1, 2)]}

                out = run.include(writer=writer)
                self.assertIs(out["ready"], True, out)
                why = self.reasons(run)
                self.assertEqual(len(why), 1, why)
                self.assertTrue(why[0].startswith(planblk.READONLY_MOVED), why[0])
                self.assertTrue((run.art / "plan" / "r1" / planfile.TREE_FILE).is_file())

    def test_status_guarded_leaves_index_only_change_to_the_status_check(self):
        """修正案の役は mutates_checkout: false なので、plan-accept の with: の status_guarded が真: Archon の状態の照らし（git status の
        行の違い）が見る index だけの変化では拒まない。行の字が同じままの、既に変わっていたファイルの書き換えは拒む"""
        def stage(repo):
            git(repo, "add", "stats.py")

        def rewrite(repo):
            with open(repo / "stats.py", "a", encoding="utf-8") as f:
                f.write("# 役が書いた\n")

        for name, move, refused in (("index だけ", stage, False), ("書き換え", rewrite, True)):
            with self.subTest(name):
                run = Run(self)
                with open(run.repo / "stats.py", "a", encoding="utf-8") as f:
                    f.write("# 前から在った変更\n")

                def writer(n, brief, run=run, move=move):
                    if n == 1:
                        move(run.repo)
                    return {"plan": [item(1, 2)]}

                out = run.include(writer=writer)
                self.assertIs(out["ready"], True, out)
                why = self.reasons(run)
                self.assertEqual(len(why), 1 if refused else 0, why)
                if refused:
                    self.assertIn("中身が変わった", why[0])

    def test_unsavable_plan_halts_without_counting_a_rejection(self):
        """P025: 受けた案の控えを置けない周は、役の拒否に数えず（出し直させず）に輪を止める（plan_accept の halt の道）"""
        run = Run(self)
        calls = []

        def writer(n, brief):
            calls.append(n)
            (run.art / "plan" / "r1" / (planmarks.FIELDS_FILE + ".tmp")).mkdir(exist_ok=True)
            return {"plan": [item(1, 2)]}

        out = run.include(writer=writer)
        self.assertEqual({k: run.out["plan-accept"][k] for k in ("ok", "done", "give_up")},
                         {"ok": False, "done": True, "give_up": True})
        self.assertIn(planmarks.FIELDS_FILE, run.out["plan-accept"]["reason"])
        self.assertEqual(calls, [1])
        self.assertEqual(self.reasons(run), [])
        self.assertIs(out["ready"], False)

    def test_unusable_ledger_is_a_done_give_up_reject(self):
        """拒否の控えが読めない周（控えの名がディレクトリ）でも、plan_accept の script は非 0 で落ちず、done・give_up 真の拒否で輪を止める。
        回を先に読むので、返答を照らさず案のファイルも書かない"""
        run = Run(self)

        def writer(n, brief):
            (run.art / "plan" / "r1" / "rejects-plan.json").mkdir(exist_ok=True)
            return {"plan": [item(1, 2)]}

        run.include(writer=writer)
        got = run.out["plan-accept"]
        self.assertEqual({k: got[k] for k in ("ok", "done", "give_up")}, {"ok": False, "done": True, "give_up": True})
        self.assertIn("拒否の控えが扱えない", got["reason"])
        self.assertFalse((run.art / "plan" / "r1" / planfile.FIX_PLAN_FILE).exists())

    def test_accepted_plan_has_item_ripple(self):
        """種の 1 回目の受け付けの後の ripple.json: 項目ごとに、変える名の呼び出し元と試験の覆っていない当たり"""
        run = Run(self)
        out = run.include()
        doc = run.json(out["ripple"])
        self.assertEqual(doc["error"], "")
        self.assertEqual(doc["items"][0]["unit_keys"], [MEAN, CLAMP])
        self.assertIn("request_ok.json:8", [h["at"] for h in doc["items"][0]["uncovered"]])

    def test_three_rejections_give_up_with_every_pointer(self):
        """元 tests/test_blk_plan.py の test_give_up_ends_loop: 3 回目の拒否で done・give_up。until_bash で輪を抜ける"""
        run = Run(self)
        out = run.include(writer=writer_of({"plan": [item(1)]}))
        self.assertEqual({k: run.out["plan-accept"][k] for k in ("ok", "done", "give_up", "attempt")},
                         {"ok": False, "done": True, "give_up": True, "attempt": 3})
        self.assertIs(out["ready"], False)
        self.assertEqual(run.json(out["plan"]), {"round": 1, "fields": []})
        self.assertEqual(run.json(out["ripple"])["items"], [])
        self.assertIn("3 回とも受け付けで拒まれた", run.json(out["ripple"])["error"])
        run.file(out["structure"])
        self.assertEqual(out["depth"], [])


class ReplanCase(unittest.TestCase):
    """案の直し（ruling つきの 2 度目の差し込み）"""

    def setUp(self):
        self.run_ = Run(self)
        first = self.run_.include()
        self.assertIs(first["ready"], True, first)
        self.first = first
        self.conflicts = self.run_.pointer("fix/conflicts.json", {"items": [
            {"id": "c1", "unit_key": CLAMP, "kind": "scope", "between": ["stats.py", "test_stats.py"],
             "why_both_cannot_hold": "試験を直さないと上限の枝を直した証が立たない", "which_is_right": "plan",
             "ruling": {"decision": "fix_plan_item", "text": "項目 1 の allowed_paths に request_ok.json を足せ", "limits": [],
                        "plan_items": [1]}},
            {"id": "c2", "unit_key": MEAN, "kind": "scope", "between": ["stats.py"],
             "why_both_cannot_hold": "人が決める", "which_is_right": "human",
             "ruling": {"decision": "ask_human", "text": "人に聞く裁定の文", "limits": []}}]})

    def fixed(self):
        return item(MEAN, CLAMP, allowed_paths=["stats.py", "test_stats.py", "request_ok.json"])

    def test_replan_rejects_extra_items_and_changed_keys_then_amends(self):
        run = self.run_
        out = run.include(ruling='["1"]', conflicts=self.conflicts, writer=writer_of(
            {"plan": [self.fixed(), self.fixed()]}, {"whole_plan": True, "plan": [item(1, 2)]},
            {"whole_plan": True, "plan": [self.fixed()]}))
        self.assertIs(out["ready"], True, out)
        self.assertEqual((out["round"], run.out["round"]["mode"]), (2, "replan"))
        self.assertEqual(run.status["ripple-units"], "skipped")
        rnd = run.art / "plan" / "r2"
        why = rolekit.rejected(rnd, "plan")
        self.assertIn("plan[] は 1 項目", why[0])
        self.assertIn("一字も変えずに写す", why[1])
        brief = (rnd / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn("項目 1 の allowed_paths に request_ok.json を足せ", brief)
        self.assertIn("## 直す項目 1", brief)
        self.assertNotIn("人に聞く裁定の文", brief, "fix_plan_item でない裁定の行は渡さない")
        self.assertIn("## 考えの住処の地図", brief)
        trace = [json.loads(x) for x in (rnd / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["items"] for r in trace if r["op"] == planmarks.AMEND_OP], [[1]])
        fields = run.json(out["plan"])
        self.assertEqual(fields["round"], 2)
        self.assertEqual(sorted(fields["amended"]["1"]), sorted(["unit_keys", "approach", "adds", "removes", "shrink_first",
                                                                 "narrows"]))
        self.assertEqual(fields["fields"][0]["allowed_paths"], ["stats.py", "test_stats.py", "request_ok.json"])
        trip = json.loads((rnd / "replan.json").read_text(encoding="utf-8"))
        row = trip["items"][0]
        self.assertEqual((row["item"], row["contract_changed"]), (1, ["allowed_paths"]))
        self.assertEqual(row["widened"], {"allowed_paths": ["request_ok.json"], "out_of_scope": []})
        before = [h["at"] for h in run.json(self.first["ripple"])["items"][0]["uncovered"]]
        after = [h["at"] for h in run.json(out["ripple"])["items"][0]["uncovered"]]
        self.assertIn("request_ok.json:8", before, "1 回目の案は request_ok.json の当たりを覆っていない")
        self.assertNotIn("request_ok.json:8", after, "波及の一覧が直した項目で作り直される")


    def test_three_rejections_give_up_without_amending(self):
        """案の直しの役も 3 回拒まれたら諦めて ready: false。承認済みの案（前の周の控え）は書き換えない"""
        run = self.run_
        before = (run.art / "plan" / "r1" / planmarks.FIELDS_FILE).read_bytes()
        out = run.include(ruling='["1"]', conflicts=self.conflicts, writer=writer_of({"plan": [item(1, 2)]}))
        self.assertEqual({k: run.out["plan-accept"][k] for k in ("ok", "done", "give_up", "attempt")},
                         {"ok": False, "done": True, "give_up": True, "attempt": 3})
        self.assertIs(out["ready"], False)
        self.assertEqual((run.art / "plan" / "r1" / planmarks.FIELDS_FILE).read_bytes(), before)
        self.assertEqual(run.json(out["plan"]), {"round": 2, "fields": []})
        error = run.json(out["ripple"])["error"]
        self.assertIn("3 回とも受け付けで拒まれた", error)
        self.assertIn(replan.REPLAN_REJECT, error)
        rows = json.loads((run.file(out["plan"]).parent / planblk.REPLAN_GAVE_UP_FILE).read_text(encoding="utf-8"))
        self.assertEqual([(r["item"], r["ruling"]) for r in rows], [(1, "項目 1 の allowed_paths に request_ok.json を足せ")])
        self.assertTrue(rows[0]["why"].startswith(planblk.PLAN_GAVE_UP_WHY.split("{")[0]), rows[0]["why"])

    def test_replan_writer_that_moved_the_tree_is_refused(self):
        """P049 の形 replan: 案の直しの役が作業ツリーを書き換えれば、直した項目を照らす前に拒み、直した案を置かない"""
        run = self.run_

        def writer(n, brief):
            stats = run.repo / "stats.py"
            stats.write_text(stats.read_text(encoding="utf-8") + f"\n# 役が書いた {n}\n", encoding="utf-8")
            return {"plan": [self.fixed()]}

        out = run.include(ruling='["1"]', conflicts=self.conflicts, writer=writer)
        self.assertIs(out["ready"], False)
        rnd = run.art / "plan" / "r2"
        why = rolekit.rejected(rnd, "plan")
        self.assertEqual(len(why), 3, why)
        for w in why:
            self.assertTrue(w.startswith(planblk.READONLY_MOVED), w)
        for name in (planfile.REPLY_FILE, replan.TRIP_FILE):
            self.assertFalse((rnd / name).exists(), name)

    def test_brief_of_the_item_is_named(self):
        """元 replan._section の「この項目の brief」の行: 案の直しの材料が、承認済みの項目と判定から組んだ項目の brief を名指す"""
        run = self.run_
        out = run.include(ruling='["1"]', conflicts=self.conflicts, writer=writer_of({"plan": [self.fixed()]}))
        self.assertIs(out["ready"], True, out)
        rnd = run.art / "plan" / "r2"
        item_brief = rnd / planfile.ITEM_BRIEF_FILE.format(no=1)
        self.assertIn(f"- この項目の brief: {item_brief}", (rnd / "brief-1.md").read_text(encoding="utf-8"))
        text = item_brief.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(planbrief.TITLE.format(n=1)), text[:200])
        self.assertIn(f"### {MEAN}", text)
        self.assertIn("mean の分母を len(xs) に", text)

    def test_replan_reuses_the_first_measure_after_the_tree_moved(self):
        """案の直しは修正の後の HEAD で測り直さず、1 回目の実測と構造の目の行を使う"""
        run = self.run_
        (run.repo / "stats.py").write_text((run.repo / "stats.py").read_text(encoding="utf-8") + "\n# 直した\n", encoding="utf-8")
        git(run.repo, "commit", "-qam", "修正")
        out = run.include(ruling='["1"]', conflicts=self.conflicts, eye=lambda f: self.fail("構造の目を起こした"),
                          writer=writer_of({"plan": [self.fixed()]}))
        self.assertIs(out["ready"], True, out)
        self.assertIs(run.out["structure-measure"]["reused"], True)
        self.assertEqual(run.status["structure-eye-loop"], "skipped")
        self.assertEqual(out["structure"], self.first["structure"])

    def test_ruling_outside_the_plan_skips_the_role(self):
        run = self.run_
        out = run.include(ruling='["5"]', conflicts=self.conflicts, writer=lambda n, brief: self.fail("役を起こした"))
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertIs(out["ready"], False)
        self.assertIn("ruling の項目 '5' が承認済みの修正案（1 項目）の番号でない", run.json(out["ripple"])["error"])


class ReplanWithoutPlanCase(unittest.TestCase):
    def test_replan_without_an_accepted_plan_skips_the_role(self):
        run = Run(self)
        out = run.include(ruling='["1"]', writer=lambda n, brief: self.fail("役を起こした"))
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertIs(out["ready"], False)
        self.assertIn("直す元の承認済みの修正案が無い", run.json(out["ripple"])["error"])


RECORDER = ROOT / "bin" / "_lib" / "record-read.py"


class ReadsCase(unittest.TestCase):
    """読んだ証拠（plan-reads の節。lib/reads・planfile.collect_reads）: 隔離した設定のフック（bin/_lib/record-read.py を実物で
    起こす）が作業の場ごとに書いた記録から、この周の修正案の役が材料を読んだかを集める（元 planblk.collect_reads）"""

    def run_with_root(self):
        run = Run(self)
        (run.config / reads.ROOT).mkdir(parents=True)
        return run

    def hook(self, run, tool, session="s-1", **tool_input):
        event = {"session_id": session, "tool_name": tool, "tool_input": tool_input, "tool_use_id": f"toolu_{tool}",
                 "cwd": str(run.repo), "hook_event_name": "PostToolUse"}
        done = subprocess.run([sys.executable, str(RECORDER), str(run.config / reads.ROOT)], input=json.dumps(event),
                              text=True, encoding="utf-8", capture_output=True, cwd=str(run.repo),
                              env=hermetic.child_env(PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)

    def reader(self, run, reply):
        """材料を Read で読んでから返す修正案の役"""
        def writer(n, brief):
            self.hook(run, "Read", file_path=run.out["plan-prep"]["brief"])
            return copy.deepcopy(reply)
        return writer

    def index(self, run, k=1, owner="plan"):
        return json.loads((run.art / "plan" / f"r{k}" / reads.index_name(owner)).read_text(encoding="utf-8"))

    def test_writer_reads_its_brief_are_recorded(self):
        run = self.run_with_root()
        self.assertIs(run.include(writer=self.reader(run, {"plan": [item(1, 2)]}))["ready"], True)
        self.assertEqual(run.out["plan-reads"]["ok"], True)
        self.assertEqual(run.out["plan-reads"]["missing"], [])
        index = self.index(run)
        self.assertEqual(index["structure-eye"], None, "道具を持たない役は名指して null")
        doc = json.loads(pathlib.Path(index["plan-writer"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["rows"], [{"path": str(run.art / "plan" / "r1" / "brief-1.md"), "hook": "read"}])

    def test_unread_brief_and_reject_file_are_missing(self):
        """拒まれた後の出し直しの指示書も渡したパスに数え、読んでいなければ missing（受け付けは拒まない）。拒否の理由は出し直しの
        指示書に貼るので、拒否の全部のファイルは無い（resume で 1 回目の役が起き直した時だけ書く）"""
        run = self.run_with_root()
        self.hook(run, "Read", file_path=str(run.repo / "stats.py"))
        out = run.include(writer=writer_of({"plan": [item(1)]}, {"plan": [item(1, 2)]}))
        self.assertIs(out["ready"], True)
        rnd = run.art / "plan" / "r1"
        self.assertEqual(run.out["plan-reads"]["missing"], [str(rnd / "brief-1.md"), str(rnd / "brief-2.md")])

    def test_reads_before_the_round_opened_are_not_counted(self):
        """K14: 記録は周を開いた時刻（round.json の at）から後の行で切る。前の周・前の差し込みの読みを今の周の物に数えない"""
        run = self.run_with_root()

        def writer(n, brief):
            self.hook(run, "Read", file_path=run.out["plan-prep"]["brief"])
            log = reads.reads_path(run.config / reads.ROOT, run.repo)
            rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
            log.write_text("".join(json.dumps({**r, "ts": "2000-01-01T00:00:00"}) + "\n" for r in rows), encoding="utf-8")
            return {"plan": [item(1, 2)]}

        self.assertIs(run.include(writer=writer)["ready"], True)
        self.assertEqual(run.out["plan-reads"]["missing"], [str(run.art / "plan" / "r1" / "brief-1.md")])

    def test_session_that_read_only_the_policy_is_not_the_roles(self):
        """役の session を決めるのは役だけに渡した材料 brief-*.md。方針の写しは別の役も読むので、それだけを読んだ session の
        読みと web を修正案の役の物に数えない"""
        run = self.run_with_root()
        copy_ = str(run.tmp / "frozen.md")
        pathlib.Path(copy_).write_text("# 方針\n", encoding="utf-8")
        run.inputs["start"] = run.pointer("start/start.json", {
            "base_rev": run.base, "policy_md": "POLICY.md",
            "policy": {"named": "POLICY.md", "path": "/repo/POLICY.md", "sha256": "a" * 64, "copy": copy_}})

        def writer(n, brief):
            self.hook(run, "Read", file_path=run.out["plan-prep"]["brief"])
            self.hook(run, "Read", session="S-judge", file_path=copy_)
            self.hook(run, "WebFetch", session="S-judge", url="https://judge.example/")
            return {"plan": [item(1, 2)]}

        self.assertIs(run.include(writer=writer)["ready"], True)
        self.assertEqual(run.out["plan-reads"]["missing"], [copy_])
        doc = json.loads(pathlib.Path(self.index(run)["plan-writer"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["web"], {"fetches": [], "searches": []})

    def test_round_without_the_role_names_it(self):
        run = Run(self, judge={"units": [unit(NIT, "nit", None)], "questions": []})
        run.include(writer=lambda n, brief: self.fail("役を起こした"))
        self.assertEqual(run.status["plan-reads"], "ok")
        index = self.index(run)
        self.assertEqual(index["plan-writer"], None)
        self.assertTrue(index["why"].startswith(reads.NOT_LAUNCHED), index)

    def test_replan_reads_do_not_overwrite_planning_reads(self):
        run = self.run_with_root()
        self.assertIs(run.include(writer=self.reader(run, {"plan": [item(1, 2)]}))["ready"], True)
        first = (run.art / "plan" / "r1" / reads.index_name("plan")).read_bytes()
        conflicts = run.pointer("fix/conflicts.json", {"items": [
            {"id": "c1", "unit_key": CLAMP, "kind": "scope", "between": ["stats.py"], "why_both_cannot_hold": "試験と両立しない",
             "which_is_right": "plan", "ruling": {"decision": "fix_plan_item", "text": "項目 1 を直せ", "limits": [], "plan_items": [1]}}]})
        out = run.include(ruling='["1"]', conflicts=conflicts, writer=self.reader(run, {"plan": [item(MEAN, CLAMP)]}))
        self.assertIs(out["ready"], True, out)
        self.assertEqual((run.art / "plan" / "r1" / reads.index_name("plan")).read_bytes(), first)
        index = self.index(run, 2, reads.REPLAN)
        self.assertEqual(sorted(index), ["replan-plan-writer", "replan-structure-eye"])
        self.assertEqual(pathlib.Path(index["replan-plan-writer"]).name, reads.evidence_name("replan-plan-writer"))
        doc = json.loads(pathlib.Path(index["replan-plan-writer"]).read_text(encoding="utf-8"))
        self.assertEqual([r["hook"] for r in doc["rows"]], ["read"])


class CollectCase(unittest.TestCase):
    """返す節は落ちない・指し札の先はいつも在って空でない・周の番号"""

    def test_broken_inputs_still_return_the_contract(self):
        fmt = node(load(), "plan")["output_format"]
        cases = {
            "読めない start": {"start": "{壊れた"},
            "形の違う units": {"units": '{"id": 1}'},
            "在らない指し札": {"judgment": json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "judge/none.json"})},
            "ほかの run のポインタ": {"judgment": json.dumps({"type": "archon_artifact", "run_id": "other", "path": "x.json"})},
        }
        for name, bad in cases.items():
            with self.subTest(name):
                run = Run(self)
                run.inputs.update(bad)
                out = run.script("plan_collect", {"dir": "plan/r1"})
                self.assertEqual(validate_schema(out, fmt), [])
                self.assertIs(out["ready"], False)
                for key in ("plan", "structure", "ripple"):
                    run.file(out[key])
        run = Run(self)
        run.include()
        shutil.rmtree(run.art / "plan")
        out = run.script("plan_collect", {"dir": "plan/r1"})
        self.assertEqual(validate_schema(out, fmt), [])
        self.assertIs(out["ready"], False)
        for key in ("plan", "structure", "ripple"):
            run.file(out[key])
        out = run.script("plan_collect", {"dir": "壊れた"})
        self.assertEqual(validate_schema(out, fmt), [])

    def test_first_round_reads_empty_and_null_review_alike(self):
        for review in ("", "null"):
            with self.subTest(review=review):
                run = Run(self)
                out = run.include(review=review)
                self.assertEqual((out["round"], out["ready"]), (1, True))
                brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
                self.assertNotIn(planfile.PRIOR_HEAD, brief)
                self.assertFalse((run.art / "plan" / "r1" / "review").exists())

    def test_rounds_count_and_second_round_gets_review(self):
        run = Run(self)
        self.assertEqual(run.include(writer=writer_of({"plan": [item(1), item(2)]}))["round"], 1)
        review = run.pointer("review/p2.plan_review.json", {"faces": [
            {"key": "key-a1-mean", "kind": "regression", "where": "stats.py", "why": "空の列が落ちる", "severity": "block",
             "unit_keys": [MEAN]}]})
        second = writer_of({"plan": [item(1)]}, {"plan": [item(1, approach="空の列も直す形にした案の手順をここに書いた"), item(2)],
                                                  "block_answers": [{"key": "key-a1-mean", "handled": "fixed",
                                                                     "how": "空の列を先に返す枝を足した"}]})
        out = run.include(review=review, writer=second)
        self.assertEqual((out["round"], out["ready"]), (2, True), out)
        rnd = run.art / "plan" / "r2"
        self.assertTrue((rnd / "review" / "p2.plan_review.json").is_file())
        brief = (rnd / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn(planfile.PRIOR_HEAD, brief)
        self.assertIn("### key-a1-mean", brief)
        self.assertIn(f"- no 1 `{MEAN}`: label=block・disposition=do-now・{planfile.FILLED_DUTY}", brief)
        self.assertIn(f"- no 2 `{CLAMP}`: label=block・disposition=do-now・{planfile.FILLED_DUTY}", brief)
        self.assertIn(planfile.FILLED_LINE.format(nos=[1, 2]), brief)
        self.assertIn(ripple.HEAD, brief, "前の周の項目ごとの波及の一覧")
        self.assertIn("block の key key-a1-mean への答えが無い", rolekit.rejected(rnd, "plan")[0])
        side = json.loads((rnd / "p2.fix_plan.json").read_text(encoding="utf-8"))
        self.assertEqual([p["unit_keys"] for p in side["plan"]], [[MEAN], [CLAMP]], "閉じた項目 2 を機械が差し込む")
        self.assertEqual(side["block_answers"][0]["key"], "key-a1-mean")
        trace = [json.loads(x) for x in (rnd / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["op"], r.get("id")) for r in trace if r["op"] == converge.DROPPED_OP],
                         [(converge.DROPPED_OP, converge.item_id([CLAMP]))], "前のまま書いた閉じた項目の行は捨てて trace に残す")

    def test_second_round_brief_has_no_independent_design(self):
        """元 tests/test_blk_plan.py の test_revise_prompt_names_blocks_and_keys: 2 周目の材料に独立設計の節は無い（役の頭は貼り直す）"""
        run = Run(self)
        run.include()
        run.include(review=run.pointer("review/p2.plan_review.json", {"faces": []}))
        brief = (run.art / "plan" / "r2" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn(planfile.PRIOR_HEAD, brief)
        self.assertTrue(brief.startswith(planblk.HEAD["plan"]))
        self.assertNotIn(planblk.DESIGN_HEAD, brief)

    def test_depth_follows_start_thickness_and_checks(self):
        """深さは直す義務の単位だけ。始めの記録の thickness が言えば全部その深さ、試験の命令が無ければ軽量にしない（訳つき）"""
        run = Run(self, start={"thickness": "軽量", "test_cmd": "python3 -m unittest"}, judge=judgment(unit(NIT, "nit", None)))
        out = run.include()
        self.assertEqual([(d["unit_id"], d["depth"], d["why"]) for d in out["depth"]],
                         [(k, "軽量", "入力 thickness の名指し（軽量）") for k in (MEAN, CLAMP)])
        run = Run(self)
        out = run.include()
        self.assertEqual({d["depth"] for d in out["depth"]}, {"標準"})
        self.assertTrue(all(d["why"] for d in out["depth"]), out["depth"])

    def test_second_round_changing_a_closed_item_is_rejected(self):
        run = Run(self)
        self.assertIs(run.include(writer=writer_of({"plan": [item(1), item(2)]}))["ready"], True)
        review = run.pointer("review/p2.plan_review.json", {"faces": [
            {"key": "key-a1-mean", "kind": "regression", "where": "stats.py", "why": "空の列が落ちる", "severity": "block",
             "unit_keys": [MEAN]}]})
        answers = [{"key": "key-a1-mean", "handled": "fixed", "how": "空の列を先に返す枝を足した"}]
        changed = item(2, approach="閉じた項目 2 の手順を書き換えた形をここに書いた")
        out = run.include(review=review, writer=writer_of(
            {"plan": [item(1, approach="空の列も直す形にした案の手順をここに書いた"), changed], "block_answers": answers},
            {"whole_plan": True, "plan": [item(1, approach="空の列も直す形にした案の手順をここに書いた")]}))
        self.assertIs(out["ready"], True, out)
        why = rolekit.rejected(run.art / "plan" / "r2", "plan")[0]
        self.assertTrue(why.startswith(planblk.CLOSED_REJECT), why)

    def test_second_round_returns_only_changed_items(self):
        """#571: 2 往復目の修正案の役は変えた項目だけを返す。返さない開いた項目は機械が前の往復の行を差し込み、受けた案は全部の
        項目を持つ。fixed と答えた block の項目を変えていない答えは拒む"""
        run = Run(self)
        self.assertIs(run.include(writer=writer_of({"plan": [item(1), item(2)]}))["ready"], True)
        first = json.loads((run.art / "plan" / "r1" / planfile.REPLY_FILE).read_text(encoding="utf-8"))["plan"]
        review = run.pointer("review/p2.plan_review.json", {"faces": [
            {"key": "key-a1-mean", "kind": "regression", "where": "stats.py", "why": "空の列が落ちる", "severity": "block",
             "unit_keys": [MEAN]},
            {"key": "key-b1-clamp", "kind": "regression", "where": "stats.py", "why": "下限の枝が抜ける", "severity": "block",
             "unit_keys": [CLAMP]}]})
        changed = item(1, approach="空の列も直す形にした案の手順をここに書いた")
        fixed_both = [{"key": "key-a1-mean", "handled": "fixed", "how": "空の列を先に返す枝を足した"},
                      {"key": "key-b1-clamp", "handled": "fixed", "how": "下限の枝も直したことにした"}]
        disputed = [fixed_both[0], {"key": "key-b1-clamp", "handled": "disputed", "how": "下限の枝は呼び手が先に弾いている"}]
        out = run.include(review=review, writer=writer_of({"plan": [changed], "block_answers": fixed_both},
                                                          {"block_answers": disputed}))
        self.assertIs(out["ready"], True, out)
        why = rolekit.rejected(run.art / "plan" / "r2", "plan")
        self.assertEqual(len(why), 1, why)
        self.assertIn("block key-b1-clamp を fixed と答えたが、その block の項目 2 を変えていない", why[0])
        got = json.loads((run.art / "plan" / "r2" / planfile.REPLY_FILE).read_text(encoding="utf-8"))["plan"]
        self.assertEqual(got[1], first[1], "返さない開いた項目は前の往復の行のまま")
        self.assertEqual(got[0]["approach"], changed["approach"])
        kept = json.loads(rolekit.candidate_path(run.art / "plan" / "r2", planfile.ROLE).read_text(encoding="utf-8"))
        self.assertEqual(kept["plan"], got, "出し直しの役が読む控えは、機械が前の往復の行を差し込んだ案の全体")

    def test_second_round_counts_its_own_rejections(self):
        """拒否の控えは周ごと: 1 周目に 2 回拒まれても、2 周目は 0 から数えて 3 回まで出し直せる"""
        run = Run(self)
        bad = {"plan": [item(1)]}
        self.assertIs(run.include(writer=writer_of(bad, bad, {"plan": [item(1, 2)]}))["ready"], True)
        self.assertEqual(len(rolekit.rejected(run.art / "plan" / "r1", "plan")), 2)
        out = run.include(review=run.pointer("review/p2.plan_review.json", {"faces": []}),
                          writer=writer_of(bad, bad, {"plan": [item(1, 2)]}))
        self.assertIs(out["ready"], True, out)
        self.assertEqual(run.out["plan-accept"]["attempt"], 3)
        self.assertEqual(len(rolekit.rejected(run.art / "plan" / "r2", "plan")), 2)

    def test_route_up_row_keeps_ready(self):
        run = Run(self)
        out = run.include(eye=lambda f: eye_dirty(f, route=True),
                          writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        self.assertIs(out["ready"], True, out)
        rows = [json.loads(x) for x in (run.file(out["structure"]).parent / "design.jsonl").read_text(
            encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["route"], "人に上げる")

    def test_failed_structure_note_reaches_the_brief(self):
        """元 tests/test_structure_eye.py の test_block_reason_reaches_the_mark: 構造の境の中の失敗は節を落とさず、行なしで計画する"""
        run = Run(self)
        out = run.include(eye=lambda f: {"rows": []})
        self.assertEqual((run.status["structure-state"], run.status["plan-loop"]), ("ok", "ok"))
        self.assertIs(out["ready"], True, out)
        reason = run.json(out["structure"])["reason"]
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn(f"{structmark.MISSING}（理由: {reason}", brief)

    def test_unwritable_state_still_plans(self):
        """構造の控えを鍵の置き場に書けない周も節を落とさず、周のフォルダに訳つきの failed の控えを置いて計画へ進む"""
        run = Run(self)
        rnd = run.script("round")
        out = run.art / "plan" / planfile.read_round(run.art / rnd["dir"])["structure"]
        (out / structmark.STATE_FILE).mkdir(parents=True)
        shutil.rmtree(run.art / "plan" / "r1")
        got = run.include()
        self.assertEqual(run.status["structure-state"], "ok")
        self.assertIs(got["ready"], True, got)
        state = run.json(got["structure"])
        self.assertEqual(state["status"], "failed")
        self.assertIn(planfile.UNWRITABLE_STATE, state["reason"])
        self.assertEqual(got["structure"]["path"], f"plan/r1/{planfile.STRUCTURE_DIR}/{structmark.STATE_FILE}")

    def test_failed_state_node_gives_not_ready(self):
        """構造の境の節そのものが落ちた周は計画の役を起こさず ready: false（線は計画なしで修正へ進まない）"""
        run = Run(self)
        run.doc = copy.deepcopy(run.doc)
        node(run.doc, "structure-state")["script"] = "no_such_script"
        script = run.script

        def failing(name, bound=None, **kw):
            if name == "no_such_script":
                raise _NodeFailed
            return script(name, bound, **kw)

        run.script = failing
        out = run.include(writer=lambda n, brief: self.fail("役を起こした"))
        self.assertEqual((run.status["structure-state"], run.status["plan-loop"]), ("failed", "skipped"))
        self.assertIs(out["ready"], False)

    def test_eye_without_rows_leaves_failed_state(self):
        run = Run(self)
        out = run.include(eye=lambda f: {"rows": []})
        self.assertEqual(run.out["structure-eye-accept"]["give_up"], True)
        state = run.json(out["structure"])
        self.assertEqual(state["status"], "failed", state)
        self.assertIs(out["ready"], True)

    def test_nothing_owed_skips_the_role(self):
        run = Run(self, judge={"units": [unit(NIT, "nit", None)], "questions": []})
        out = run.include(writer=lambda n, brief: self.fail("役を起こした"))
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertIs(out["ready"], False)
        self.assertIn(planfile.NOTHING_OWED, run.json(out["ripple"])["error"])
        for key in ("plan", "structure", "ripple"):
            run.file(out[key])
        self.assertTrue(outcome.plan_nothing_owed({"plan": {**out, "plan": str(run.file(out["plan"]))}}),
                        "結末の決めが計画の書いた控えから義務 0 件の周を読めない")
        self.assertEqual((run.status["structure-measure"], run.status["structure-eye-loop"]), ("skipped", "skipped"))
        self.assertEqual(out["structure"]["path"], "plan/r1/structure/structure-state.json", "使い回す実測の控えに書かない")
        state = run.json(out["structure"])
        self.assertEqual(state["status"], "failed")
        self.assertIn(planfile.NOTHING_OWED, state["reason"])

    def test_stuck_unit_skips_the_role(self):
        """同じ key の単位が開いた行と開いていない行で来た判定は行き止まり（必ず入れるのに案に入れられない）"""
        run = Run(self, judge={"units": [unit(MEAN), unit(MEAN, "nit", None)], "questions": []})
        out = run.include(writer=lambda n, brief: self.fail("役を起こした"))
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertIs(out["ready"], False)
        self.assertIn(planblk.PLAN_STUCK, run.json(out["ripple"])["error"])
        self.assertFalse(outcome.plan_nothing_owed({"plan": {**out, "plan": str(run.file(out["plan"]))}}))

    def test_unreadable_pointer_inputs_are_not_absent(self):
        """空の字と null だけが「無い」。線が渡した指し札が読めない入力は、役を起こさずに ready: false で訳を残す"""
        missing = json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "nowhere/x.json"})
        for name in ("start", "world", "review"):
            with self.subTest(name):
                run = Run(self)
                if name == "review":
                    self.assertIs(run.include()["ready"], True)
                out = run.include(**{name: missing}, writer=lambda n, brief: self.fail("役を起こした"))
                self.assertEqual(run.status["plan-loop"], "skipped")
                self.assertIs(out["ready"], False)
                error = run.json(out["ripple"])["error"]
                self.assertIn(f"{name} が読めない", error)
                self.assertIn("nowhere/x.json", error)
        run = Run(self)
        out = run.include(start="{壊れた", writer=lambda n, brief: self.fail("役を起こした"))
        self.assertIs(out["ready"], False)
        self.assertIn("start が読めない", run.json(out["ripple"])["error"])


class OwedAnswersCase(unittest.TestCase):
    """依頼の answers（始めの記録の欄）が答えた関所の問いの出どころ・depends は、plan の直す義務に戻る（P002。fix と同じ gatemarks.duty
    の口で数える。plan に関所の答えは届かない——行き止まりの判定は 1 回目の周で、修正前の関所より前に走る）"""

    FORK = {"key": "q-mean", "kind": "fork", "status": "held", "origin": MEAN, "options": ["a", "b"], "reason": "割れる"}

    def duty_line(self, run) -> str:
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        return next(line for line in brief.splitlines() if line.startswith("- no ") and f"`{MEAN}`" in line)

    def test_answered_fork_origin_returns_to_duty(self):
        """P002: 答えの無い fork の出どころは「入れてもよい」、依頼の answers がその fork に答えれば「必ず案に入れる」（外せば網羅の拒否）"""
        for answers, duty in (([], "入れてもよい"), ([{"question": "q-mean", "text": "a を選ぶ"}], "必ず案に入れる")):
            with self.subTest(answers=answers):
                run = Run(self, start={"answers": answers}, judge={**judgment(), "questions": [self.FORK]})
                self.assertIs(run.include()["ready"], True)
                self.assertIn(duty, self.duty_line(run))

    def test_answered_origin_that_is_not_open_is_stuck(self):
        """P010: 依頼の答えで直す義務に戻った出どころが開いていない（defer）なら行き止まり。役を起こさず、理由 PLAN_STUCK に no と key"""
        judge = {"units": [unit(MEAN), unit(CLAMP, "suggest", "defer")], "questions": [{**self.FORK, "origin": CLAMP}]}
        run = Run(self, start={"answers": [{"question": "q-mean", "text": "a を選ぶ"}]}, judge=judge)
        out = run.include(writer=lambda n, brief: self.fail("役を起こした"))
        self.assertIs(out["ready"], False)
        error = run.json(out["ripple"])["error"]
        self.assertIn(planblk.PLAN_STUCK, error)
        self.assertIn(CLAMP, error)


class SurvivesCase(unittest.TestCase):
    """周を開く節と返す節は落ちない（返す節が周の dir を束ねる。線は落ちた返す節の先へ進めない）"""

    def test_round_and_return_node_survive_a_lib_that_does_not_load(self):
        run = Run(self)
        broken = run.tmp / "no-lib"
        broken.mkdir()
        rnd = run.script("round", root=broken)
        self.assertEqual(validate_schema(rnd, node(load(), "round")["output_format"]), [])
        self.assertEqual((rnd["round"], rnd["dir"], rnd["go"]), (1, "plan/r1", False))
        why = json.loads((run.art / "plan" / "r1" / "round.json").read_text(encoding="utf-8"))["why"]
        self.assertIn("周を開くノードの中で誤りが起きた: ModuleNotFoundError", why)
        out = run.script("plan_collect", {"dir": rnd["dir"]}, root=broken)
        self.assertEqual(validate_schema(out, node(load(), "plan")["output_format"]), [])
        self.assertEqual((out["ready"], out["round"], out["depth"]), (False, 1, []))
        for key in ("plan", "structure", "ripple"):
            run.file(out[key])
        self.assertEqual(run.json(out["structure"])["status"], "failed")
        self.assertIn("ModuleNotFoundError", (run.art / "plan" / "r1" / "collect-error.txt").read_text(encoding="utf-8"))
        self.assertEqual(run.script("round")["dir"], "plan/r2", "lib が読める次の周は数え続ける")

    def test_round_takes_over_a_folder_left_half_open(self):
        run = Run(self)
        (run.art / "plan" / "r1").mkdir(parents=True)
        rnd = run.script("round", root=run.tmp / "no-lib")
        self.assertEqual(rnd["dir"], "plan/r1")

    def test_question_with_depends_that_is_not_a_list(self):
        """判定の問いの depends が数でも周を開け、深さは直す義務の単位だけ"""
        judge = judgment()
        judge["questions"] = [{"key": "q", "kind": "fork", "status": "held", "origin": CLAMP, "depends": 3}]
        run = Run(self, judge=judge)
        out = run.include(writer=writer_of({"plan": [item(1)]}))
        self.assertIs(out["ready"], True, out)
        self.assertEqual([d["unit_id"] for d in out["depth"]], [MEAN])


class BriefCase(unittest.TestCase):
    """修正案の材料に元の works が渡していた節（方針の文書・考えの住処の地図・前の run で通らなかった物）"""

    def test_brief_carries_policy_concept_map_and_prior_failures(self):
        run = Run(self, start={"policy_md": "POLICY.md"})
        run.inputs["prior_failures"] = run.pointer("start/prior-failures-in.json",
                                                   [{"where": "修正案の受け付け", "text": "単位の網羅が 3 回とも欠けた"}])
        self.assertIs(run.include()["ready"], True)
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn("## 人の方針\n\n人が決めた、run をまたいで効く決まり（役も engine も書き換えない）。文書の置き場: POLICY.md", brief)
        self.assertIn(carry.PRIOR_HEAD, brief)
        self.assertIn("- 修正案の受け付け: 単位の網羅が 3 回とも欠けた", brief)
        self.assertIn("## 考えの住処の地図", brief)

    def test_plan_prep_policy_is_frozen_copy(self):
        """修正案の材料と構造の目が名指す方針は、始めの記録の固めた版の写し（policy_md の生の文書ではない）"""
        frozen = {"named": "POLICY.md", "path": "/repo/POLICY.md", "sha256": "a" * 64, "copy": "/run/policy/frozen.md"}
        run = Run(self, start={"policy_md": "POLICY.md", "policy": frozen})
        self.assertIs(run.include()["ready"], True)
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn("文書の置き場: /run/policy/frozen.md", brief)
        self.assertNotIn("文書の置き場: POLICY.md", brief)
        rnd = run.script("round")
        got = run.script("structure_measure", {"dir": rnd["dir"]})
        self.assertEqual(json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))["policy_path"],
                         "/run/policy/frozen.md")

    def test_prep_passes_state_dir_cache_root(self):
        """修正案の材料のライブラリの文書の節は、STATE_DIR の下 works-factory/ の run をまたぐ控えを読む（網に出ない）"""
        import libdocs
        from lib.tests.test_libdocs import FakeBoard, ok_http
        run = Run(self, judge=judgment(unit("app.py の requests の使い方")))
        (run.repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (run.repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        git(run.repo, "add", "app.py", "requirements.txt")
        git(run.repo, "commit", "-q", "-m", "app")
        state = run.tmp / "state"
        libdocs.section(FakeBoard(run.tmp / "earlier").work(""), run.repo, ["app.py"], get=ok_http(), env={},
                        shared=state / "works-factory")
        run.env_extra = {"STATE_DIR": str(state), "WORKS_LIBDOCS_WEB": "", "https_proxy": "http://127.0.0.1:9",
                         "HTTPS_PROXY": "http://127.0.0.1:9"}
        run.include()
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn("ほかの run 1 本", brief)

    def test_without_policy_or_prior_failures_neither_section(self):
        run = Run(self)
        run.include()
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertNotIn("## 人の方針", brief)
        self.assertNotIn(carry.PRIOR_HEAD, brief)

    def brief(self, run, n=1, k=1):
        return (run.art / "plan" / f"r{k}" / f"brief-{n}.md").read_text(encoding="utf-8")

    def test_dirty_structure_rows_reach_the_brief(self):
        run = Run(self)
        self.assertIs(run.include(eye=eye_dirty, writer=writer_of({"plan": [item(1, 2, structure=[
            {"row": MEAN, "follows": True}])]}))["ready"], True)
        brief = self.brief(run)
        for word in (structmark.PLAN_HEAD, structmark.PLAN_ASK, DIRTY_ROW["chosen"]):
            self.assertIn(word, brief)
        self.assertNotIn(structmark.MISSING, brief)

    def test_brief_carries_structure_rows(self):
        """元 structmark.plan_section の行の形: 判定・形・根拠・避け方"""
        run = Run(self)
        run.include(eye=eye_dirty, writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        brief = self.brief(run)
        self.assertIn(f"- {MEAN}: 汚れる（形 5・根拠 /units/0/id）", brief)
        self.assertIn(f"避け方: {DIRTY_ROW['chosen']}", brief)

    def test_failed_structure_marks_the_brief(self):
        run = Run(self)
        out = run.include(eye=lambda f: {"rows": []})
        self.assertIs(out["ready"], True, out)
        brief = self.brief(run)
        self.assertIn(f"{structmark.MISSING}（理由: 構造の目の返答が 3 回とも受け付けで拒まれた", brief)
        self.assertNotIn(structmark.PLAN_ASK, brief)
        self.assertEqual(rolekit.rejected(run.art / "plan" / "r1", "plan"), [], "構造の行への答えを求めない")

    def test_clean_only_structure_rows_need_no_answer(self):
        run = Run(self)
        self.assertIs(run.include(eye=eye_clean)["ready"], True)
        brief = self.brief(run)
        self.assertIn(structmark.PLAN_HEAD, brief)
        self.assertNotIn(structmark.PLAN_ASK, brief)
        self.assertIn(structmark.PLAN_NONE, brief)
        self.assertIn(structmark.PLAN_CLEAN_HEAD, brief)
        self.assertIn(f"- {MEAN}: 汚れない（", brief.split(structmark.PLAN_CLEAN_HEAD, 1)[1])
        self.assertEqual(rolekit.rejected(run.art / "plan" / "r1", "plan"), [], "structure を書かない案は通る")

    def test_clean_structure_rows_sit_outside_the_ask(self):
        run = Run(self)
        run.include(eye=eye_dirty, writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        brief = self.brief(run)
        self.assertIn(structmark.PLAN_ASK, brief)
        self.assertNotIn(structmark.PLAN_NONE, brief)
        head, tail = brief.split(structmark.PLAN_CLEAN_HEAD, 1)
        asked = head.split(structmark.PLAN_ASK, 1)[1]
        self.assertIn(f"- {MEAN}: 汚れる（", asked)
        self.assertNotIn(": 汚れない（", asked)
        self.assertIn(": 汚れない（", tail)
        self.assertNotIn(": 汚れる（", tail)

    def test_prescriptions_reach_the_brief(self):
        judge = judgment()
        judge["units"][0]["prescriptions"] = ["分母を len(xs) にする"]
        run = Run(self, judge=judge)
        self.assertIs(run.include()["ready"], True)
        brief = self.brief(run)
        self.assertIn(planblk.PRESCRIPTION_HEAD, brief)
        self.assertIn(f"{planblk.PRESCRIPTION_UNIT_HEAD.format(key=MEAN)}\n\n1. 分母を len(xs) にする", brief)
        self.assertNotIn(planblk.PRESCRIPTION_UNIT_HEAD.format(key=CLAMP), brief)
        self.assertIn(planblk.PRESCRIPTION_SOURCE.format(path=run.art / "judge" / "judgment.json"), brief)

    def test_brief_opens_with_the_role_head(self):
        run = Run(self)
        run.include()
        brief = self.brief(run)
        self.assertTrue(brief.startswith(planblk.HEAD["plan"]), brief[:200])
        for word in (planblk.ITEMS_RULE, planblk.REUSE_RULE, planblk.TARGET_TEXT_PLAN, planmarks.HEAD, gatemarks.HEAD[planmarks.NODE],
                     policy.RECORDED_HEAD, policy.RECORDED_NONE, "承認ノードの人の答え: この役には渡っていない"):
            self.assertIn(word, brief)

    def test_units_section_carries_catalog_ledger_and_view(self):
        judge = judgment(unit(NIT, "nit", None))
        judge["questions"] = [{"key": "q-mean", "kind": "fork", "status": "held", "origin": CLAMP, "depends": []}]
        judge["precedents"] = [{"source": "https://example.org/mean", "verdict": "adopt"}]
        run = Run(self, judge=judge)
        self.assertIs(run.include()["ready"], True)
        brief = self.brief(run)
        for word in (planfile.UNITS_HEAD, "  - paths: stats.py", "  - summary: mean の分母",
                     f"- 入れてはいけない単位（受け付けが拒む）: `{NIT}`（label=nit", "問いの台帳（", '"key": "q-mean"',
                     "判定者の見立て: ", '"framing": "算術平均と上限の枝の取り違え"', "判定者の先行例（世界の解）: ",
                     "https://example.org/mean",
                     f"- no 2 `{CLAMP}`: label=block・disposition=do-now・入れてもよい"):
            self.assertIn(word, brief)

    def test_repo_line_names_base_and_review_md(self):
        """P035: 差分の run（入口の差分の根 input.base.rev が読む版 review_rev と違う）では、読む版と BASE を別の値で描く"""
        run = Run(self, start={"input": {"base": {"rev": FORK, "from": "base", "name": "fork", "label": "base fork"}}})
        run.include()
        brief = self.brief(run)
        self.assertIn(f"リポジトリ: {run.repo.resolve()}（読む版: `{run.base}`）　BASE: `{FORK}`　観点の正本: {LIB / 'REVIEW.md'}",
                      brief)

    def test_excluded_range_named(self):
        run = Run(self)
        run.include()
        self.assertNotIn(planblk.EXCLUDED_HEAD, self.brief(run))
        run = Run(self)
        run.pointer("judge/pr-excluded.json", {"paths": ["other.py"]})
        run.include()
        self.assertIn(f"{planblk.EXCLUDED_HEAD}: {run.art / 'judge' / 'pr-excluded.json'}", self.brief(run))

    def test_brief_carries_lib_docs_section(self):
        run = Run(self)
        run.include()
        brief = self.brief(run)
        self.assertIn(libdocs.TITLE, brief)
        self.assertIn("ライブラリの文書を取る物は無い（0 本）", brief)

    def test_brief_ends_with_language_rule(self):
        for lang, want in (("日本語", "日本語"), ("", rolekit.LANG_DEFAULT)):
            with self.subTest(lang=lang):
                run = Run(self, start={"lang": lang})
                run.include()
                self.assertEqual(self.brief(run).splitlines()[-1], rolekit.LANG_RULE.format(lang=want))

    def test_spec_reaches_the_brief(self):
        run = Run(self)
        run.include()
        self.assertNotIn(planfile.SPEC_HEAD, self.brief(run))
        run = Run(self)
        run.inputs["spec"] = run.pointer("judge/spec.json", {"requirements": ["空の列の平均は 0"],
                                                             "acceptance": ["test_stats.py::TestStats::test_mean_of_empty"]})
        run.include()
        brief = self.brief(run)
        self.assertIn(planfile.SPEC_HEAD, brief)
        self.assertIn("test_stats.py::TestStats::test_mean_of_empty", brief)

    def test_units_ripple_reaches_the_brief(self):
        """元 tests/test_blk_plan.py の test_units_ripple_reaches_plan_prompt"""
        run = Run(self)
        run.include()
        brief = self.brief(run)
        self.assertIn(ripple.UNITS_HEAD, brief)
        self.assertIn(f"### 単位 {MEAN}", brief)
        self.assertIn(f"### 単位 {CLAMP}", brief)
        self.assertTrue((run.art / "plan" / "r1" / planfile.RIPPLE_UNITS_FILE).is_file())

    def test_prior_failures_of_wrong_shape_are_named_unread(self):
        run = Run(self)
        run.inputs["prior_failures"] = run.pointer("start/prior-failures-in.json", {"where": "x"})
        self.assertIs(run.include()["ready"], True)
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertIn(planfile.UNREAD_INPUTS_HEAD, brief)
        self.assertIn("- prior_failures: ", brief)


class FixtureCase(unittest.TestCase):
    """Archon の `workflow test` で筋書き（fixtures/*.stubs.yaml）を回す（配線だけ）"""

    def test_fixtures_pass(self):
        names = sorted(p.name.removesuffix(".stubs.yaml") for p in (BLOCK / "fixtures").glob("*.stubs.yaml"))
        self.assertEqual(names, ["eye-skipped", "give-up", "ready", "replan", "resubmit"])
        with archon.tree(["plan"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-plan", "--json", "--cwd", str(tree))
        try:
            report = json.loads(done.stdout)
        except json.JSONDecodeError:
            self.fail(f"workflow test の返りが読めない: {done.stdout}{done.stderr}")
        self.assertEqual(report.get("errors"), [], report)
        self.assertEqual((report["failed"], report["passed"]), (0, len(names)), json.dumps(report, ensure_ascii=False)[:4000])



if __name__ == "__main__":
    unittest.main()
