"""計画のブロック（workflows/plan/）の試験。

- 形: YAML を PyYAML で読み、返りの約束（docs/design.md の「plan の返り」）・役の節の決まり（E7・E12・E16）・輪の数を見る。
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
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests import archon
from tests.bin.gitkit import committed_copy, git

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
import planblk  # noqa: E402
import planmarks  # noqa: E402
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
AI_KEYS = ("command", "prompt")
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
NIT = "stats.py mean: 変数名が短い"
LOOSE = "stats.py: 全体の書き方"
# 修正案の役の指示書の元: 今の works（raiki61/claude-plugins の 2aa7c66cf7abe1fe09699ac2942d107123214168）の
# works/.shared/core/gl-prompts/prompts/review-loop/p2.fix_plan.md の sha256 と、持ち主が許した直し（元の字, 写しの字）の 3 つ
FIX_PLAN_SHA256 = "381674c83992c9b0955f961e1e7ff2b5fd451458902f60842e36b547eeb26b95"
FIX_PLAN_TITLE = "# P2-10 修正案（writer の仕事。書く前に出す）\n"
FIX_PLAN_EDITS = [
    (FIX_PLAN_TITLE,   # 頭の 1 行（材料のファイルを読め）
     "お前は修正案の役で、新しい会話で起きている。役の定義・直す単位と番号・判定の処方・構造の目の行・世界の解の行・波及の一覧・"
     "前の回の拒否の理由（在れば）は、機械が材料のファイルに書いた。先に材料のファイル `$plan-prep.output.brief` を Read で読み、"
     "その指示に従え。\n\n" + FIX_PLAN_TITLE),
    (FIX_PLAN_TITLE + "\n"   # engine の雛形の 5 行を外す（材料のファイルが同じ物を持つ）
     "今の周に直す単位（各行の `no` は engine が振った番号。**key を写さず no の整数で指せ**——engine が名前に戻して記録する）: "
     "{{record.units | pick key,label,disposition}}\n"
     "問いの台帳（fork の出どころ・depends に挙がった単位は待ってよい——案に入れなくてよい）: "
     "{{?record.questions | pick key,kind,status,origin,depends}}\n"
     "判定者の見立て: {{record.process.diagnosis | pick framing,one_shot,one_shot_closes}}\n"
     "判定者の先行例（世界の解）: {{?record.process.precedents}}\n"
     "リポジトリ: {{inputs.cwd}}（読む版: `{{inputs.review_rev}}`）\u3000BASE: `{{record.base}}`\u3000観点の正本: {{inputs.review_md}}\n\n",
     FIX_PLAN_TITLE + "\n"),
    ("の no（上の一覧の番号。", "の no（材料の一覧の番号。"),   # no は材料の一覧で指す
]
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
        self.inputs["start"] = self.pointer("start/start.json", {"base_rev": self.base, "test_cmd": "", "tdd_suite": "",
                                                                  "thickness": "", "policy_md": "", "lang": "日本語",
                                                                  **(start or {})})
        self.inputs["units"] = json.dumps(catalog() if units is None else units, ensure_ascii=False)
        self.inputs["judgment"] = self.pointer("judge/judgment.json", judgment() if judge is None else judge)
        if world is not None:
            self.inputs["world"] = self.pointer("judge/world.jsonl", world, lines=True)
        self.doc = load()
        self.out = {}
        self.status = {}

    def pointer(self, rel, doc, *, lines=False):
        p = self.art / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in doc) if lines else json.dumps(doc, ensure_ascii=False)
        p.write_text(text, encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})

    def env(self, bound, root):
        env = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
        env.update({f"INPUTS_{k.upper()}": v for k, v in {**self.inputs, **bound}.items()})
        env.update(ARTIFACTS_DIR=str(self.art), WORKFLOW_ID=RUN_ID, WORKS_FACTORY_ROOT=str(root),
                   PYTHONDONTWRITEBYTECODE="1", WORKS_LIBDOCS_WEB="off")
        return env

    def script(self, name, bound=None, *, root=ROOT):
        """script を子で回す。終了の値 0 と、標準出力の JSON 1 つを確かめて返す。root は lib/ を探す根（WORKS_FACTORY_ROOT）"""
        p = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py")], cwd=str(self.repo), env=self.env(bound or {}, root),
                           capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
        self.case.assertEqual(p.returncode, 0, f"{name}.py が落ちた: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def value(self, ref):
        """with: の値（$<節>.output[.<欄>] か {from, if_skipped}）を Archon と同じ字にする（字はそのまま・ほかは JSON）"""
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
        """when: の式（== と && だけ）を前の節の出力で評価する"""
        ok = True
        for part in expr.split("&&"):
            m = re.fullmatch(r"\s*\$([\w-]+)\.output\.(\w+)\s*==\s*'?([\w]+)'?\s*", part)
            nid, field, want = m.groups()
            if self.status.get(nid) != "ok":
                return False
            got = self.out[nid][field]
            ok = ok and (str(got).lower() if isinstance(got, bool) else str(got)) == want
        return ok

    def until(self, expr):
        """until_bash を sh で評価する（$<節>.output.<欄> を字に替えて）"""
        text = re.sub(r"\$([\w-]+)\.output\.(\w+)", lambda m: str(self.out[m.group(1)][m.group(2)]).lower(), expr)
        return subprocess.run(["sh", "-c", text]).returncode == 0

    def include(self, *, eye=None, writer=None, typed=True, **inputs):
        """計画のブロックを 1 度差し込み、返す節の出力を返す。eye(structure_file) と writer(回の番号, 材料の字) は役の返答。
        typed なら役の返答を節の output_format で照らす（Archon と同じく受け付けの前に）"""
        self.inputs.update(inputs)
        self.out, self.status, self.typed = {}, {}, typed
        self.walk(self.doc["nodes"], eye or eye_clean, writer or writer_ok)
        return self.out[self.doc["returns"]]

    def runs(self, n):
        deps = n.get("depends_on") or []
        states = [self.status.get(d) for d in deps]
        rule = n.get("trigger_rule", "all_success")
        if rule == "all_done":
            ok = True
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
                for i in range(1, lg["max_iterations"] + 1):
                    self.walk(lg["nodes"], eye_reply, writer)
                    if self.until(lg["until_bash"]):
                        break
                else:
                    self.case.fail(f"輪 {n['id']} が max_iterations に当たった（until_bash で抜けない）")
                self.out[n["id"]], self.status[n["id"]] = json.dumps(self.out[lg["nodes"][-1]["id"]]), "ok"
                continue
            if "command" in n:
                got = (eye_reply(self.out["structure-measure"]["structure_file"]) if n["id"] == "structure-eye"
                       else writer(self.out["plan-prep"]["attempt"],
                                   pathlib.Path(self.out["plan-prep"]["brief"]).read_text(encoding="utf-8")))
                if self.typed:
                    self.case.assertEqual(validate_schema(got, n["output_format"]), [], f"{n['id']} の見本が型に合わない")
            else:
                got = self.script(n["script"], {k: self.value(v) for k, v in (n.get("with") or {}).items()})
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
    """返りの約束と入力（docs/design.md の「plan の返り」）"""

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
        roles = [n for n in nodes(doc) if any(k in n for k in AI_KEYS)]
        self.assertEqual([n["id"] for n in roles], ["structure-eye", "plan-writer"])
        for n in roles:
            self.assertIs(n["mutates_checkout"], False, n["id"])
            self.assertEqual(n["settingSources"], ["user"], n["id"])
            self.assertEqual(n["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False}, n["id"])
            self.assertNotIn("context", n, n["id"])
            self.assertEqual(n["model"], "opus", n["id"])
        eye_node, writer = roles
        self.assertEqual((eye_node["allowed_tools"], eye_node["effort"]), ([], "high"))
        self.assertEqual((writer["allowed_tools"], writer["effort"]), (["Read", "Grep", "Glob", "WebSearch", "WebFetch"], "medium"))

    def test_eye_command_reads_only_its_prep(self):
        """構造の目は道具なしの独立の会話: 指示書が読むのは支度の節の出力だけ"""
        text = (COMMANDS / "structure-eye.md").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"\$[A-Za-z][\w.-]*", text)), {"$structure-eye-prep.output.prompt"})
        refs = set(re.findall(r"\$[A-Za-z][\w.-]*", (COMMANDS / "fix-plan.md").read_text(encoding="utf-8")))
        self.assertEqual(refs, {"$plan-prep.output.brief"})

    def test_fix_plan_command_is_the_original_with_only_the_allowed_edits(self):
        """修正案の役の指示書は元の p2.fix_plan.md の文のまま: 許した直しを逆に当てると元のバイトに戻る"""
        text = (COMMANDS / "fix-plan.md").read_text(encoding="utf-8")
        for original, copied in reversed(FIX_PLAN_EDITS):
            self.assertEqual(text.count(copied), 1, copied)
            text = text.replace(copied, original)
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), FIX_PLAN_SHA256)

    def test_deadlines_are_all_twenty_days(self):
        keys = ("timeout", "idle_timeout")
        for n in nodes(load()):
            for key in keys:
                if key in n:
                    self.assertEqual(n[key], NO_DEADLINE, f"{n['id']}.{key}")
            if "script" in n or "loop_group" in n:
                self.assertEqual(n.get("timeout"), NO_DEADLINE, n["id"])
            if "command" in n:
                self.assertEqual(n.get("idle_timeout"), NO_DEADLINE, n["id"])

    def test_loops_give_up_in_the_body_before_max_iterations(self):
        doc = load()
        for nid, accept, fresh in (("structure-eye-loop", "structure-eye-accept", False), ("plan-loop", "plan-accept", True)):
            lg = node(doc, nid)["loop_group"]
            self.assertEqual(lg["max_iterations"], rolekit.GIVE_UP_AFTER, nid)
            self.assertEqual(lg["max_iterations"], eye.MAX_ATTEMPTS, nid)
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
        self.assertEqual(rows["properties"], {k: v for k, v in bare(owner["properties"]).items() if k not in added | dropped})
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
        self.assertIn("narrows の行に狭めない案を探した結果", self.reasons(run)[0])
        brief = (run.art / "plan" / "r1" / "brief-2.md").read_text(encoding="utf-8")
        self.assertTrue(brief.startswith("前の回の返答は受け付けで拒まれた。理由はファイル"), brief[:200])

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
            {"plan": [self.fixed(), self.fixed()]}, {"plan": [item(1, 2)]}, {"plan": [self.fixed()]}))
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


class CollectCase(unittest.TestCase):
    """返す節は落ちない・指し札の先はいつも在って空でない・周の番号"""

    def test_broken_inputs_still_return_the_contract(self):
        fmt = node(load(), "plan")["output_format"]
        cases = {
            "読めない start": {"start": "{壊れた"},
            "形の違う units": {"units": '{"id": 1}'},
            "在らない指し札": {"judgment": json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "judge/none.json"})},
            "ほかの run の指し札": {"judgment": json.dumps({"type": "archon_artifact", "run_id": "other", "path": "x.json"})},
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
        self.assertIn(f"- no 2 `{CLAMP}`: label=block・disposition=do-now・{planfile.FILLED_DUTY}", brief)
        self.assertIn("- 機械が差し込む no（閉じた・保留の項目。書かなくてよい）: [2]", brief)
        self.assertIn(ripple.HEAD, brief, "前の周の項目ごとの波及の一覧")
        self.assertIn("block の key key-a1-mean への答えが無い", rolekit.rejected(rnd, "plan")[0])
        side = json.loads((rnd / "p2.fix_plan.json").read_text(encoding="utf-8"))
        self.assertEqual([p["unit_keys"] for p in side["plan"]], [[MEAN], [CLAMP]], "閉じた項目 2 を機械が差し込む")
        self.assertEqual(side["block_answers"][0]["key"], "key-a1-mean")
        trace = [json.loads(x) for x in (rnd / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["op"], r.get("id")) for r in trace if r["op"] == converge.DROPPED_OP],
                         [(converge.DROPPED_OP, converge.item_id([CLAMP]))], "前のまま書いた閉じた項目の行は捨てて trace に残す")

    def test_route_up_row_keeps_ready(self):
        run = Run(self)
        out = run.include(eye=lambda f: eye_dirty(f, route=True),
                          writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        self.assertIs(out["ready"], True, out)
        rows = [json.loads(x) for x in (run.file(out["structure"]).parent / "design.jsonl").read_text(
            encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["route"], "人に上げる")

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
        self.assertIn("周を開く節の中で誤りが起きた: ModuleNotFoundError", why)
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

    def test_without_policy_or_prior_failures_neither_section(self):
        run = Run(self)
        run.include()
        brief = (run.art / "plan" / "r1" / "brief-1.md").read_text(encoding="utf-8")
        self.assertNotIn("## 人の方針", brief)
        self.assertNotIn(carry.PRIOR_HEAD, brief)

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
        self.assertEqual(names, ["eye-skipped", "give-up", "ready", "replan"])
        with archon.tree(["plan"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-plan", "--json", "--cwd", str(tree))
        try:
            report = json.loads(done.stdout)
        except json.JSONDecodeError:
            self.fail(f"workflow test の返りが読めない: {done.stdout}{done.stderr}")
        self.assertEqual(report.get("errors"), [], report)
        self.assertEqual((report["failed"], report["passed"]), (0, 4), json.dumps(report, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    unittest.main()
