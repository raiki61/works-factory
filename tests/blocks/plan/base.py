"""plan の block の試験の助け（テストのモジュールではない）。

- 見本の値: 判定・単位の目録・修正案の項目・構造の目の行・世界の解の行（今の tests/workflows/test_plan.py の見本と同じ値）
- PlanRun: 始めの記録の無い使い捨ての run directory と、対象（tests/e2e/target-seed の git の写し）。block の YAML の node を Archon と同じ順に、
  script は子のプロセスで、AI の node は試験が渡す返答で回す（include）。port の値は YAML の既定のまま、渡した物だけを替える
"""
from __future__ import annotations

import copy
import json
import pathlib
import re
import subprocess
import sys
import tempfile

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit

ROOT = kit.ROOT
for _path in (ROOT / "lib" / "graphloops", ROOT / "lib"):
    if str(_path) not in sys.path:
        sys.path.append(str(_path))
BLOCK = kit.BLOCKS / "plan"
SEED = ROOT / "tests" / "e2e" / "target-seed"
RUN_ID = kit.RUN_ID

MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
NIT = "stats.py mean: 変数名が短い"
LOOSE = "stats.py: 全体の書き方"
DIRTY_ROW = {"verdict": "汚れる", "faces": [5], "evidence": ["/units/0/id"], "reason": "骨組みの無い口が増える",
             "chosen": "既存の関数の中で直す", "chosen_reason": "骨組みが在る"}
WORLD_ROW = {"finding": 1, "where": "stats.py", "class_id": "mean-denominator", "problem": "平均の分母の取り違え",
             "activity": "算術", "practice": "算術平均は要素の数で割る", "sources": [], "applies": "mean の分母",
             "not_applies": "", "versus": {"proposed": "分母を直す", "verdict": "same", "challenge": ""}, "basis": "knowledge"}
HANDOFF_NOTE = {"read": [{"path": "stats.py", "lines": "1-20", "why": "mean と clamp の枝を確かめた"}],
                "kept": ["分母は len(xs) にする"],
                "set_aside": [{"option": "新しい助け手を足す", "why": "stats.py に clamp の枝が在る"}],
                "open": ["空の列の扱い"]}


def doc() -> dict:
    return yaml.safe_load((BLOCK / "works-factory-plan.yaml").read_text(encoding="utf-8"))


def defaults() -> dict:
    """YAML の入力の既定の値（Archon が入力を渡さなかった port に立てる字）"""
    return {name: str(spec.get("default", "")) for name, spec in doc()["inputs"].items()}


def nodes(d=None, *, inner=True):
    """node を並びの順に（inner なら loop_group の中の node も）"""
    for n in (d or doc())["nodes"]:
        yield n
        if inner and "loop_group" in n:
            yield from n["loop_group"]["nodes"]


def node(nid, d=None):
    return next(n for n in nodes(d) if n["id"] == nid)


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
    """修正案の項目の見本。files の行の home・considered は照らしに当たらない既定（考えの名は項目の単位の番号ごとに違う字）"""
    nos = {MEAN: 1, CLAMP: 2, NIT: 3}
    return {"unit_keys": list(keys), "approach": "mean の分母を len(xs) に、clamp の上限の枝を hi に直す",
            "files": [{"path": "stats.py", "op": "modify", "responsibility": "上限の枝の戻り値を直す",
                       "home": {"concept": f"単位 {'・'.join(str(nos.get(k, k)) for k in keys)} の考え", "why": "上限の枝は stats.py の clamp が持つ"},
                       "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}],
                       "symbols": [{"name": "clamp", "change": "add"}]}],
            "shrink_first": "足す物は無い。式と戻り値を 1 か所ずつ直すだけで足りる", "narrows": [], "route": "tdd",
            "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均がその真ん中の値になる",
                       "path": "stats.mean を本物のまま呼び、戻り値を断言する", "red_kind": "assertion",
                       "red_why": "今の分母は len(xs) - 1 なので mean([1, 3]) が 4.0 を返す"}],
            "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
            "allowed_paths": ["stats.py", "test_stats.py"], "out_of_scope": [], **more}


def narrow(**more):
    return {"what": "空の列の mean が例外を投げる", "why": "空の列の平均は 0 割りの例外のまま残す", **more}


def writer_ok(n, prompt):
    return {"plan": [item(1, 2)]}


def writer_of(*replies):
    """回ごとに replies[n-1] を返す役（足りなければ最後の物）"""
    return lambda n, prompt: copy.deepcopy(replies[min(n, len(replies)) - 1])


class NodeFailed(Exception):
    """試験が落とした script の node（Archon は node を failed にして、後の node の trigger_rule に渡す）"""


class PlanRun:
    """1 つの run の置き場と対象。include() で block を 1 度回す（Archon と同じ順に script を回し、AI の node は試験が返答を渡す）"""

    def __init__(self, case, *, units=None, judge=None, world=None, structure=None, **inputs):
        self.case = case
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.art = self.tmp / "art"
        self.art.mkdir()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.doc = doc()
        self.inputs = defaults()
        self.inputs.update(base=self.base, review_rev=self.base,
                           units=json.dumps(catalog() if units is None else units, ensure_ascii=False),
                           judgment=self.pointer("judge/judgment.json", judgment() if judge is None else judge))
        if world is not None:
            self.inputs["world_rows"] = self.pointer("judge/world.jsonl", world, lines=True)
        if structure is not None:
            self.inputs["structure"] = structure
        self.inputs.update({k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in inputs.items()})
        self.out, self.status, self.loop_prev = {}, {}, {}
        self.env_extra: dict = {}
        self.prompts: list = []

    # ---- 値の用意
    def pointer(self, rel, content, *, lines=False):
        p = self.art / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in content) if lines else json.dumps(content, ensure_ascii=False)
        p.write_text(text, encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})

    def file(self, rel, content, *, lines=False) -> str:
        """port の file 形に渡す、run の置き場のファイルの pointer の字"""
        return self.pointer(rel, content, lines=lines)

    def place(self) -> pathlib.Path:
        return self.art

    def round_dir(self, k=None) -> pathlib.Path:
        if k is None:
            k = json.loads((self.art / "current-round.json").read_text(encoding="utf-8"))["round"]
        return self.art / f"r{k}"

    def read(self, rel):
        return json.loads((self.art / rel).read_text(encoding="utf-8"))

    # ---- script
    def env(self, bound):
        named = {f"INPUTS_{k.upper()}": v for k, v in {**self.inputs, **bound}.items()}
        named.update(ARTIFACTS_DIR=str(self.art), WORKFLOW_ID=RUN_ID, WORKS_FACTORY_ROOT=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
                     WORKS_LIBDOCS_WEB="off")
        named.update(self.env_extra)
        return hermetic.child_env(**named)

    def script(self, name, bound=None, *, check=True):
        p = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{name}.py")], cwd=str(self.repo), env=self.env(bound or {}),
                           capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
        if not check:
            return p
        self.case.assertEqual(p.returncode, 0, f"{name}.py が落ちた: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    # ---- node の並びを Archon と同じ順に回す
    def value(self, ref):
        """with: の値（$<node>.output[.<欄>] か $LOOP_PREV.<node>.output.<欄> か {from, if_skipped}）を Archon と同じ字にする"""
        if not isinstance(ref, (str, dict)):
            return json.dumps(ref)
        if isinstance(ref, str) and not ref.startswith("$"):
            return ref
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
        """when: の式（==・!= と && だけ）を前の node の出力で評価する"""
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
        text = re.sub(r"\$([\w-]+)\.output\.(\w+)", lambda m: str(self.out[m.group(1)][m.group(2)]).lower(), expr)
        return subprocess.run(["sh", "-c", text], env=hermetic.child_env()).returncode == 0

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

    def include(self, *, writer=None, fixer=None, typed=True, **inputs):
        """block を 1 度回し、出口 finish の出力を返す。writer(回の番号, 指示の字) は修正案の役の返答、fixer は出し直しの役の返答
        （足りなければ writer と同じ）。typed なら役の返答を node の output_format で照らす（Archon と同じく受け付けの前に）"""
        self.inputs.update({k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in inputs.items()})
        self.out, self.status, self.loop_prev, self.typed = {}, {}, {}, typed
        self.walk(self.doc["nodes"], writer or writer_ok, fixer or writer or writer_ok)
        return self.out[self.doc["returns"]]

    def walk(self, body, writer, fixer):
        from engine.schema import validate_schema
        for n in body:
            if not self.runs(n):
                self.status[n["id"]] = "skipped"
                continue
            if "loop_group" in n:
                lg = n["loop_group"]
                self.loop_prev = {}
                for _ in range(1, lg["max_iterations"] + 1):
                    self.walk(lg["nodes"], writer, fixer)
                    self.loop_prev = {b["id"]: self.out[b["id"]] for b in lg["nodes"] if self.status.get(b["id"]) == "ok"}
                    if self.until(lg["until_bash"]):
                        break
                else:
                    self.case.fail(f"輪 {n['id']} が max_iterations に当たった（until_bash で抜けない）")
                self.out[n["id"]], self.status[n["id"]] = json.dumps(self.out[lg["nodes"][-1]["id"]]), "ok"
                continue
            if "prompt" in n:
                prompt = self.out[n["prompt"].split(".")[0][1:]]["prompt"]
                self.prompts.append((n["id"], prompt))
                n_round = sum(1 for nid, _ in self.prompts if nid == n["id"])
                got = (fixer if n["id"] == "plan-writer-fix" else writer)(n_round, prompt)
                if self.typed:
                    self.case.assertEqual(validate_schema(got, n["output_format"]), [], f"{n['id']} の見本が型に合わない")
            else:
                got = self.script(n["script"], {k: self.value(v) for k, v in (n.get("with") or {}).items()}, check=False)
                if got.returncode != 0:
                    self.status[n["id"]] = "failed"
                    continue
                got = json.loads(got.stdout)
                self.case.assertEqual(validate_schema(got, n["output_format"]), [], n["id"])
            self.out[n["id"]], self.status[n["id"]] = got, "ok"

    def pointed(self, ptr):
        self.case.assertEqual((ptr["type"], ptr["run_id"]), ("archon_artifact", RUN_ID))
        p = self.art / ptr["path"]
        self.case.assertTrue(p.is_file() and p.stat().st_size > 0, f"pointer の先が無いか空: {ptr['path']}")
        return p

    def json(self, ptr):
        return json.loads(self.pointed(ptr).read_text(encoding="utf-8"))
