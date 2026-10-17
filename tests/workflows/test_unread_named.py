"""読めないポインタの入力を、黙って空や当たりにせず名指す（落とし穴 K15。持ち主の決め no-silent-loosen）。

ブロックごとに、宣言の入力のうちポインタの物を 1 つずつ壊れた先（run の置き場に無いファイル gone/x9.json）にして、その入力を読む
script を子のプロセスで走らせ、返り（標準出力の JSON）か書いたファイルに、その入力の名が載ることを見る。
- ポインタの入力: YAML の inputs: の description に「ポインタ」が在る物（「〜のポインタの先から読む」のように、ほかの入力のポインタを言う
  だけの物は除く）。docs/design.md の「サブグラフの出力の約束」の入力の欄と同じ物になる。report の入力（ブロックの返りの束）と
  線の request（ファイルのパス）はポインタでないので見ない
- 読む script: script の字に `INPUTS_<名>` が在るか、`INPUTS_{…}` を組んで読む script が名の字を持つ物。YAML の順に、SETUPS が
  名指す前の script（with: で読む値と置き場の控えを作る節）の後に走らせる。with: の `$INPUTS.<名>`・`$<節>.output.<欄>` は
  ブロックの入力と前に走らせた script の返りで解き、役の節の返りと `$LOOP_PREV` は空の字
- 名指し: 同じ入力を読める先にした run（対照）と比べ、壊れた run だけが返すか書く字（JSON は葉の字、ほかは行）のうち、入力の名を
  語として持ち（パスの一部 `start.json`・`plan/r1` は語に数えない）、読めない・無いことも言う物（UNREAD）が 1 つ以上在る。
  落ちた script の標準エラーは数えない（返りでも材料でもない）
- 今名指さない入力は表 UNNAMED に行ごとに名指して許す。表の行が今は名指していれば赤（直ったら表から消す）
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.layers import scan
from tests.layers.scan import script_reads as reads

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEED = ROOT / "tests" / "e2e" / "target-seed"
RUN_ID = "run-unread"
GONE = "gone/x9.json"
BROKEN = json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": GONE})
SKIP = ("line", "chain", "report")   # chain の入力にポインタは無い
POINTER = re.compile(r"ポインタ(?!の先)")


def flat(nodes) -> list[dict]:
    out = []
    for node in nodes or []:
        out.append(node)
        if isinstance(node.get("loop_group"), dict):
            out.extend(flat(node["loop_group"].get("nodes")))
    return out


def pointer_inputs(doc: dict) -> list[str]:
    return [name for name, spec in (doc.get("inputs") or {}).items()
            if isinstance(spec, dict) and POINTER.search(spec.get("description") or "")]


def readers(block: pathlib.Path, doc: dict, name: str) -> list[dict]:
    return [node for node in flat(doc["nodes"]) if "script" in node
            and reads((block / "scripts" / f"{node['script']}.py").read_text(encoding="utf-8"), name)]


def leaves(value) -> list[str]:
    if isinstance(value, dict):
        return [s for v in value.values() for s in leaves(v)]
    if isinstance(value, list):
        return [s for v in value for s in leaves(v)]
    return [value] if isinstance(value, str) else []


def said(text: str) -> list[str]:
    """字を、JSON なら葉の字、JSON の行の並びなら行ごとの葉の字、ほかは行に分ける"""
    try:
        return leaves(json.loads(text))
    except ValueError:
        pass
    out = []
    for line in text.splitlines():
        try:
            out.extend(leaves(json.loads(line)))
        except ValueError:
            out.append(line)
    return out


UNREAD = re.compile(r"読めな|読めず|読み損|無い|壊れ|unread|missing|not found|No such file")


def named(name: str, strings) -> bool:
    """字のどれかが、入力の名を語として持ち、読めない・無いことも言う"""
    word = scan.word(re.escape(name))
    return any(word.search(s) and UNREAD.search(s) for s in strings)


class Place:
    """1 回の run の置き場と対象のリポジトリ。seed が入力のポインタの先を書く"""

    def __init__(self, tmp: pathlib.Path):
        self.tmp = tmp
        self.art = tmp / "art"
        self.art.mkdir()
        self.repo = tmp / "repo"
        committed_copy(self.repo, SEED)
        self.head = git(self.repo, "rev-parse", "HEAD")

    def put(self, rel: str, doc) -> str:
        path = self.art / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})

    def start(self, **more) -> str:
        return self.put("start/start.json", {"run_id": RUN_ID, "base_rev": self.head, "test_cmd": "", "tdd_suite": "",
                                             "policy_md": "", "request_file": "", "thickness": "", "lang": "日本語",
                                             "final_gate": "always", "features_cut": [], "answers": [], **more})


def judgment(p: Place) -> str:
    unit = {"key": "stats.py mean: 分母", "label": "block", "disposition": "do-now", "reason": "分母が 1 少ない"}
    return p.put("judge/judgment.json", {"units": [unit], "questions": [], "framing": "分母の誤り", "one_shot": "分母を直す",
                                         "precedents": []})


# 判定の出力の欄が指す置き場のファイル（入力の名 → (置き場のパス, 中身)）
JUDGE_FILES = {"premises": ("judge/premises.json", {"constraints": []}), "materials": ("judge/materials.json", {}),
               "answer_ties": ("judge/answer-ties.json", {"rounds": {"1": []}}),
               "verify": ("judge/judge-verify.json", {"units": [], "synergy": {}}),
               "pr_excluded": ("judge/pr-excluded.json", {"node": "p0.parallel_pr", "excluded": []}),
               "depth_record": ("judge/depth-head.json", {"depth": "標準", "why": "x", "items": [], "facts": {}, "groups": []}),
               "decisions": ("judge/material-prior-decisions.json", {"reply": {"settled": []}}),
               "purpose_review": ("judge/purpose-review.json", {}), "purpose_means": ("judge/purpose-means.json", {"means": []})}


def judge_files(p: Place, *names: str) -> dict:
    return {name: p.put(*JUDGE_FILES[name]) for name in names}


def units() -> str:
    return json.dumps([{"id": "stats.py mean: 分母", "paths": ["stats.py"], "summary": "mean"}], ensure_ascii=False)


WORLD_ROW = {"finding": 1, "where": "stats.py", "class_id": "mean-denominator", "problem": "平均の分母の取り違え",
             "activity": "算術", "practice": "算術平均は要素の数で割る", "sources": [], "applies": "mean の分母",
             "not_applies": "", "versus": {"proposed": "分母を直す", "verdict": "same", "challenge": ""}, "basis": "knowledge"}


def world(p: Place) -> str:
    """judge の world.jsonl（行 2 つ。1 つの JSON としては読めない。対照の run が落ちたと数えるのは 0 以外で終わった script だけなので、
    読めない訳を返りに載せて 0 で終わる plan・plan-review と report の 2 行は lib の試験が縛る）"""
    second = {**WORLD_ROW, "finding": 2, "class_id": "mean-empty", "problem": "空の並びの平均"}
    return p.put("judge/world.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in (WORLD_ROW, second)))


def plan_fields(p: Place) -> str:
    p.put("plan/r1/p2.fix_plan.json", {"plan": []})
    return p.put("plan/r1/plan-fields.json", {"round": 1, "fields": []})


def eyes(p: Place) -> dict:
    return {"units": units(), "judgment": judgment(p), "purpose": p.put("judge/purpose.json", {"purpose_text": "平均が正しい"}),
            "world": world(p), "plan": plan_fields(p), "ripple": p.put("plan/ripple.json", {"items": [], "overlaps": []}),
            "depth": json.dumps([{"unit_id": "stats.py mean: 分母", "depth": "標準", "why": ["測った"]}], ensure_ascii=False),
            "design": p.put("plan-review/design.json", {"question_stands": True, "reason": "立つ", "design": "設計"}),
            "diff": p.put("fix/diff.patch", "diff --git a/stats.py b/stats.py\n--- a/stats.py\n+++ b/stats.py\n@@ -1 +1 @@\n-a\n+b\n"),
            "changed": json.dumps({"premise_drift": False}), "fix_units": "[]", "green_ok": "true",
            "test_outcomes": json.dumps({"rows": [], "unmeasured": ""}),
            "diffs": json.dumps([json.loads(p.put("fix/fix/tdd-unit.json", []))]),
            "start": p.start(), "plan_questions": "null", "answers": "null", "start_answers": "null", "x_scalars": "null",
            **judge_files(p, "answer_ties", "materials", "premises", "decisions")}


def fix(p: Place) -> dict:
    return {"start": p.start(), "baseline": p.put("test-gate/base/baseline.json",
                                                  {"suite": "", "test_cmd": "", "rev": p.head, "exit": 0, "cases": []}),
            "units": units(), "judgment": judgment(p), "plan": plan_fields(p),
            "ripple": p.put("plan/ripple.json", {"items": [], "overlaps": []}), "depth": "[]", "answers": "null",
            "only_items": "", "mode": "",
            "group": json.dumps({"group_id": "g1", "unit_ids": ["stats.py mean: 分母"], "items": []}, ensure_ascii=False),
            "from_tree": "", "out_dir": "", **judge_files(p, "answer_ties", "materials", "depth_record")}


def judge(p: Place) -> dict:
    request = p.tmp / "request.json"
    request.write_text(json.dumps([{"where": "stats.py", "text": "mean が誤る"}], ensure_ascii=False), encoding="utf-8")
    start = p.put("entry/start.json", {
        "run_id": RUN_ID, "base_rev": p.head, "test_cmd": "", "adapter": "", "final_gate": "always", "thickness": "",
        "request_file": str(request), "features_cut": ["judge_verify"], "answers": [], "gates": "",
        "input": {"base": {"rev": p.head, "from": "head", "name": "", "label": "HEAD"}, "head_rev": p.head,
                  "diff": {"empty": True, "files": 0, "stat": ""}, "requests": 1, "request_file": str(request), "pr": None,
                  "spec": False}})
    return {"start": start, "baseline": p.put("test-gate/base/baseline.json", {
        "suite": "", "test_cmd": "", "rev": p.head, "exit": 0, "cases": [],
        "material": {"status": "clean", "count": 0, "checked": "exit 0"}}),
        "objection": "", "prior_failures": p.put("prior.json", [{"where": "受け付け", "text": "前の失敗"}])}


def merge(p: Place) -> dict:
    return {"mode": "seal", "start": p.start(), "diff": p.put("fix/diff.patch", ""), "fingerprint": "", "green_ok": "",
            "eyes_ok": "", "sealed_hash": "", "answer": "", "r2": ""}


def plan(p: Place) -> dict:
    return {"start": p.start(), "units": units(), "judgment": judgment(p), "world": world(p),
            "spec": p.put("judge/spec.json", {"requirements": [], "tests": []}),
            "review": p.put("plan-review/pass-1/review.json", {"faces": [], "shrink": [], "reason": "穴が無い"}),
            "ruling": "[]", "conflicts": p.put("fix/conflicts.json", {"items": []}),
            "prior_failures": p.put("prior.json", [{"where": "受け付け", "text": "前の失敗"}]),
            **judge_files(p, "verify", "pr_excluded", "depth_record", "answer_ties", "materials", "decisions")}


def plan_review(p: Place) -> dict:
    p.put("plan/structure/design.jsonl", "")
    return {"units": units(), "judgment": judgment(p), "purpose": p.put("judge/purpose.json", {"purpose_text": "平均が正しい"}),
            "world": world(p), "plan": plan_fields(p),
            "structure": p.put("plan/structure/structure-state.json",
                               {"status": "ok", "reason": "", "design_file": "x", "wall_s": 0}),
            "ripple": p.put("plan/ripple.json", {"items": [], "overlaps": []}), "start": p.start(), "answers": "null",
            "ruling": "[]", "conflicts": p.put("fix/conflicts.json", {"items": []}), "gate_answers": "null", "round_limit": "null",
            "mode": "", "head_depth": "",
            **judge_files(p, "premises", "materials", "pr_excluded", "purpose_review", "decisions", "purpose_means")}


def test_gate(p: Place) -> dict:
    return {"mode": "final", "start": p.start(), "baseline": p.put("test-gate/base/baseline.json", {
        "suite": "", "test_cmd": "", "rev": p.head, "exit": 0, "cases": []})}


# ブロック -> (入力の読める先を置いて入力の字を返す seed, 読む script の前に走らせる節の id)
SETUPS = {
    "eyes": (eyes, ()),
    "fix": (fix, ()),
    "judge": (judge, ("intake",)),
    "merge": (merge, ()),
    "plan": (plan, ("round",)),
    "plan-review": (plan_review, ()),
    "test-gate": (test_gate, ()),
}

FELL = "落ちて止まる（標準エラーに例外の 1 行だけで、返りにも材料にも入力の名が無い）"
RENAMED = "返りか材料に「読めない」と書くが、入力の名でなく言い換え（{words}）かパスだけで、どの入力かが分からない"
PATH_ONLY = "先のパスを役の材料に貼るだけで、先が無くても黙って進む（役が読めずに空として扱いうる）"

# (ブロック, 入力) -> 訳。壊れた先を名指さない入力
UNNAMED = {
    ("eyes", "judgment"): "prep は判定のパスを返りに載せるだけで、先が無くても黙って進む。区分 E。区分の issue で外す",
    **{("eyes", name): "prep が先の無い判定の欄（結び・素材の状態・制約・決定記録の突合）を null と同じに「無い」と読み、入力の名を言わない"
                       "（判定の隣を名で開いていた時と同じ読み）。区分 E。区分の issue で外す"
       for name in ("answer_ties", "materials", "premises", "decisions")},
    ("eyes", "purpose"): f"prep が{FELL}。区分 E。区分の issue で外す",
    ("eyes", "world"): f"prep が{PATH_ONLY}。区分 E。区分の issue で外す",
    ("eyes", "plan"): RENAMED.format(words="structure-after の「修正案の外れの訳が読めない」") + "。区分 E。区分の issue で外す",
    ("eyes", "ripple"): f"prep が{PATH_ONLY}。区分 E。区分の issue で外す",
    ("eyes", "design"): RENAMED.format(words="prep と verdict の「独立設計の控えが読めない」") + "。区分 E。区分の issue で外す",
    ("eyes", "start"): f"prep が{FELL}。protected・structure-after は例外の字だけを返す。区分 E。区分の issue で外す",
    ("fix", "start"): f"prep と group-start（単独の run の組の子の頭）が{FELL}。区分 F。区分の issue で外す",
    ("fix", "baseline"): f"prep と group-start（単独の run の組の子の頭）が{FELL}（「元の結末が読めない」も標準エラーだけ）。区分 F。区分の issue で外す",
    ("fix", "judgment"): f"prep と group-start（単独の run の組の子の頭）が{FELL}。区分 F。区分の issue で外す",
    ("fix", "plan"): f"prep と group-start（単独の run の組の子の頭）が{FELL}。区分 F。区分の issue で外す",
    ("fix", "ripple"): f"prep と group-start（単独の run の組の子の頭）が{FELL}。区分 F。区分の issue で外す",
    ("fix", "plan_review"): f"prep と group-start（単独の run の組の子の頭）が{FELL}。ほかの fix のポインタの入力と同じ。区分 F。区分の issue で外す",
    **{("fix", name): f"prep と group-start（単独の run の組の子の頭）が{FELL}（入力の名と先を言う例外で止まるが標準エラーだけ）。"
                      "ほかの fix のポインタの入力と同じ。区分 F。区分の issue で外す"
       for name in ("answer_ties", "materials", "depth_record")},
    ("fix", "prior_conflicts"): f"prep と group-start（単独の run の組の子の頭）が{FELL}（先が無いと黙って写さずに進めず、入力の名を言って止まる）。"
                                "区分 F。区分の issue で外す",
    ("judge", "start"): RENAMED.format(words="intake の「始めの記録か前の失敗の行が読めない」。2 つの入力のどちらかを言わない")
                        + "。区分 J。区分の issue で外す",
    ("judge", "baseline"): RENAMED.format(words="diagnose-prep の「直す前の結末が読めない」") + "。区分 J。区分の issue で外す",
    ("judge", "prior_failures"): RENAMED.format(words="intake の「始めの記録か前の失敗の行が読めない」。2 つの入力のどちらかを言わない")
                                 + "。区分 J。区分の issue で外す",
    ("merge", "start"): "merge の返りの reason が例外の字（FileNotFoundError とパス）だけで、入力の名が無い。区分 M。区分の issue で外す",
    ("plan", "judgment"): RENAMED.format(words="round の「判定が読めない」") + "。plan-prep は TypeError で落ちる。区分 P。区分の issue で外す",
    ("plan-review", "judgment"): "open の返りの reason が例外の字だけで、入力の名が無い。区分 P。区分の issue で外す",
    ("plan-review", "purpose"): "open の返りの reason が例外の字だけで、入力の名が無い。r2-prep は落ちる。区分 P。区分の issue で外す",
    ("plan-review", "world"): "open の返りの reason が例外の字だけで、入力の名が無い。区分 P。区分の issue で外す",
    ("plan-review", "plan"): "open の返りの reason が例外の字だけで、入力の名が無い。区分 P。区分の issue で外す",
    ("plan-review", "structure"): "open の返りの reason が例外の字だけで、入力の名が無い。区分 P。区分の issue で外す",
    ("plan-review", "ripple"): "open の返りの reason が例外の字だけで、入力の名が無い。区分 P。区分の issue で外す",
    ("plan-review", "start"): "open の返りの reason が例外の字だけで、入力の名が無い。r2-prep は落ちる。区分 P。区分の issue で外す",
    ("plan-review", "conflicts"): "open が読めない申し出を黙って「申し出なし」として進む（返りにも材料にも読めない訳が無い）。"
                                  "区分 P。区分の issue で外す",
    ("test-gate", "start"): f"run と ci-prep が{FELL}。result は証拠に例外の字だけを書く。区分 T。区分の issue で外す",
    ("test-gate", "baseline"): "result が読めない base の結末を黙って「無い」と読む（返りにも証拠にも読めない訳が無い）。区分 T。区分の issue で外す",
}


class Observed:
    """1 つの入力の、対照の run と壊れた run の字"""

    def __init__(self, block: str, name: str):
        self.block, self.name = block, name
        self.folder = ROOT / "workflows" / block
        self.doc = yaml.safe_load((self.folder / f"works-factory-{block}.yaml").read_text(encoding="utf-8"))
        self.seed, before = SETUPS[block]
        nodes = {node["id"]: node for node in flat(self.doc["nodes"]) if "script" in node}
        wanted = {node["id"] for node in readers(self.folder, self.doc, name)} | set(before)
        self.order = [node for nid, node in nodes.items() if nid in wanted]
        self.readers = [node["id"] for node in readers(self.folder, self.doc, name)]

    def run(self, broken: bool) -> tuple[set, list]:
        """(返りと書いたファイルの字の集まり, 落ちた script の (id, 終了の値, 標準エラーの最後の行))"""
        with tempfile.TemporaryDirectory() as tmp:
            place = Place(pathlib.Path(tmp))
            inputs = self.seed(place)
            if broken:
                inputs[self.name] = BROKEN
            seeded = {path: path.read_bytes() for path in place.art.rglob("*") if path.is_file()}
            outputs, strings, fell = {}, [], []
            for node in self.order:
                bound = {key: self.bound(value, inputs, outputs) for key, value in (node.get("with") or {}).items()}
                env = hermetic.child_env(**{f"INPUTS_{k.upper()}": v for k, v in {**inputs, **bound}.items()},
                                         ARTIFACTS_DIR=str(place.art), WORKFLOW_ID=RUN_ID, WORKS_FACTORY_ROOT=str(ROOT),
                                         PYTHONDONTWRITEBYTECODE="1", WORKS_LIBDOCS_WEB="off")
                done = subprocess.run([sys.executable, str(self.folder / "scripts" / f"{node['script']}.py")],
                                      cwd=place.repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                      encoding="utf-8")
                if done.returncode != 0:
                    fell.append((node["id"], done.returncode, (done.stderr.strip().splitlines() or [""])[-1]))
                lines = [line for line in done.stdout.splitlines() if line.strip()]
                try:
                    outputs[node["id"]] = json.loads(lines[-1]) if lines else None
                except ValueError:
                    outputs[node["id"]] = None
                strings.extend(said(done.stdout))
            for path in sorted(place.art.rglob("*")):
                if path.is_file() and seeded.get(path) != path.read_bytes():
                    strings.extend(said(path.read_text(encoding="utf-8", errors="replace")))
            real = os.path.realpath(tmp)
            return {s.replace(real, "<tmp>").replace(tmp, "<tmp>") for s in strings}, fell

    @staticmethod
    def bound(value, inputs: dict, outputs: dict) -> str:
        """with: の値を Archon と同じ字にする（字はそのまま、ほかは JSON）。解けない参照は空の字"""
        if isinstance(value, dict) and "from" in value:
            value = value["from"]
        if not isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        got = re.fullmatch(r"\$INPUTS\.(\w+)", value)
        if got:
            return inputs.get(got.group(1), "")
        got = re.fullmatch(r"\$([\w-]+)\.output(?:\.(\w+))?", value)
        if got:
            out = outputs.get(got.group(1))
            out = out.get(got.group(2)) if isinstance(out, dict) and got.group(2) else out
            return "" if out is None else out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        return "" if value.startswith("$") else value


def pointer_rows() -> list[tuple[str, str]]:
    rows = []
    for spec in sorted((ROOT / "workflows").glob("*/works-factory-*.yaml")):
        block = spec.parent.name
        if block not in SKIP:
            rows.extend((block, name) for name in pointer_inputs(yaml.safe_load(spec.read_text(encoding="utf-8"))))
    return rows


class UnreadNamedCase(unittest.TestCase):
    maxDiff = None

    def test_every_block_has_a_setup(self):
        blocks = {p.name for p in (ROOT / "workflows").iterdir() if (p / f"works-factory-{p.name}.yaml").is_file()}
        self.assertEqual(sorted(blocks - set(SKIP)), sorted(SETUPS))

    def test_every_pointer_input_unreadable_is_named(self):
        quiet = {}
        for block, name in pointer_rows():
            with self.subTest(block=block, input=name):
                seen = Observed(block, name)
                if not seen.readers:
                    quiet[(block, name)] = "読む script が無い"
                    continue
                control, fell = seen.run(broken=False)
                self.assertEqual(fell, [], "読める先の対照の run で script が落ちた（seed を直す）")
                broken, fell = seen.run(broken=True)
                if not named(name, broken - control):
                    quiet[(block, name)] = f"落ちた script: {fell}" if fell else "返りにも材料にも入力の名が無い"
        new = {row: why for row, why in quiet.items() if row not in UNNAMED}
        self.assertEqual(sorted(new), [], f"壊れた先を名指さない入力: {new}")
        self.assertEqual(sorted(UNNAMED.keys() - set(quiet)), [], "表の行が今は名指している（表から消す）")

    def test_every_unnamed_row_has_a_reason(self):
        for row, reason in UNNAMED.items():
            with self.subTest(row=row):
                self.assertTrue(reason.endswith("区分の issue で外す") or "読む script が無い" in reason, reason)

    def test_naming_counts_only_new_words_outside_paths(self):
        control = {"plan/r1/round.json", "start は読めた"}
        self.assertTrue(named("start", {"start が読めない: gone/x9.json"} - control))
        self.assertFalse(named("start", {"    start = read_json(boundary.resolve(json.loads(start_raw)))"}))
        self.assertFalse(named("start", {"start は読めた"} - control))
        self.assertFalse(named("plan", {"plan/r1/x.json", "plan-review/failed", "plan_dir"}))
        self.assertFalse(named("start", {"FileNotFoundError: <tmp>/art/gone/x9.json"}))
        self.assertEqual(said('{"a": ["start が読めない", 1], "start": null}'), ["start が読めない"])
        self.assertEqual(said('{"a": "x"}\nplain\n'), ["x", "plain"])

    def test_pointer_inputs_are_read_from_the_description(self):
        doc = {"inputs": {"a": {"description": "判定のポインタ（judgment.json）"},
                          "units": {"description": "単位の目録。判定の単位は judgment のポインタの先から読む"},
                          "b": {"description": "JSON の配列"}, "c": {"default": ""}}}
        self.assertEqual(pointer_inputs(doc), ["a"])
        self.assertTrue(reads('os.environ["INPUTS_START"]', "start"))
        self.assertFalse(reads('os.environ["INPUTS_START_ANSWERS"]', "start"))
        self.assertTrue(reads('for name in ("ripple", "world"):\n    os.environ.get(f"INPUTS_{name.upper()}")', "world"))


if __name__ == "__main__":
    unittest.main()
