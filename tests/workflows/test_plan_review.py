"""事前審査のブロック（workflows/plan-review/）の試験。

- YAML の形（PyYAML で読み、Archon を起こさない）: 返りの約束・入力・読むだけの節・役の節の設定・輪の形
- script の振る舞い: script を子のプロセスで、run の置き場（ARTIFACTS_DIR）・WORKFLOW_ID・INPUTS_* を一時の置き場に向けて走らせる。
  入力の指し札の先のファイル（判定・目的・修正案・構造の目・波及・始めの記録）は試験が置き場に書く。対象のリポジトリは
  tests/e2e/target-seed/ を一時のフォルダに写して git にした物
- 筋書き: tests/archon.py の使い捨ての木で archon workflow test（Archon の源が無ければ名前つきで見送る）

今の works の試験（tests/test_blk_plan.py・test_plan_gate.py・test_gate_drafts.py）の事前審査と独立設計と関所の材料の場面を、
盤面なしの形で写した。元の試験の名は各試験の docstring に書く。
"""
import copy
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

import yaml

from tests import archon
from tests.workflows import copied
from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "plan-review"
YAML = BLOCK / "works-factory-plan-review.yaml"
SEED = ROOT / "tests" / "e2e" / "target-seed"
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from lib.tests import test_gate_drafts as TD  # noqa: E402
from lib.tests import test_plan_gate as TP  # noqa: E402
import boardview  # noqa: E402
import converge  # noqa: E402
import design  # noqa: E402
import gatemarks  # noqa: E402
import gatepolicy  # noqa: E402
import planblk  # noqa: E402
import planfile  # noqa: E402
import planmarks  # noqa: E402
import policy  # noqa: E402
import reads  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402
import structmark  # noqa: E402
import worldmark  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

DEADLINE = 1728000000
RUN_ID = "run-plan-review"
ROUND_LIMIT = 20   # 線の plan-rounds の max_iterations
UNIT_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
UNIT_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
PURPOSE_MARK = "PURPOSE-MARK-7731"
CONSTRAINT_MARK = "CONSTRAINT-MARK-4410"
FRAMING_MARK = "FRAMING-MARK-2208"
ONE_SHOT_MARK = "ONESHOT-MARK-5150"
LABEL_MARK = "block"
RIPPLE_MARK = "RIPPLE-MARK-9902"
PLAN_MARK = "PLAN-MARK-6060"
CONTRACT_INPUTS = ("units", "judgment", "purpose", "world", "plan", "structure", "ripple")
# 元 works/.shared/core/gl-prompts/prompts/review-loop/p2.plan_review.md:4（sha256 4f400ecf39c7347e5c45c62cdf2446278816202653b5c6f132b56d16eade5068）
ORIGINAL_UNITS_LINE = ("直す単位（各行の `no` は engine が振った番号。**key を写さず no の整数で指せ**——engine が名前に戻して記録する）: "
                       "{{record.units | pick key,label,disposition,reason}}")
ADDED_INPUTS = {"start": "null", "answers": "null", "ruling": "[]", "conflicts": "null", "gate_answers": "null",
                "round_limit": "null", "mode": ""}
RETURN_FIELDS = ("pass", "stalled", "review", "design", "gate_axes", "ask_human", "questions")
RUN_KEYS = ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout")


# 役の指示書の写しの台帳（K9。tests/workflows/copied.py）。元は今の works（raiki61/claude-plugins の
# 2aa7c66cf7abe1fe09699ac2942d107123214168）の works/ の下。plan-review.md は役 judge の定義（engine が本文を前付けした）と
# p2.plan_review.md を順に繋いだ物
JUDGE_HEAD = ("---\nname: judge\ndescription: 呼び出し側が覆せない判定を下す上位の目。リポジトリと web は読めるが書けず、shell を持たない。\n"
              "model: opus\neffort: high\ntools: Read, Glob, Grep, WebSearch, WebFetch\n---\n\n")
REVIEW_TITLE = "修正案の事前審査（別の judge。書く前の案を叩く）\n\n"
R2_TAKEN = ("元の目的:\n{{out.p0.purpose.purpose_text}}\n\n実測した制約（kind=仮説 のものは所与にするな）: {{record.process.constraints}}\n"
            "前提のドリフト（あれば）: {{?loop.drift_notes}}\n"
            "裏取りを通っていない目的の判定（あれば）: {{?loop.purpose_review_stale}}——この周の『狭めている』は根拠が数え直されていないので、"
            "目的を独立に取れない理由としては使えない\n")
COPIED = {
    "plan-review.md": (
        [("works/.shared/core/agents/judge.md", "078d6834af474542db794660277ea99673c1df7791e797ac2b6a17932fcb181c", 3225),
         ("works/.shared/core/gl-prompts/prompts/review-loop/p2.plan_review.md",
          "4f400ecf39c7347e5c45c62cdf2446278816202653b5c6f132b56d16eade5068", 4520)],
        [(JUDGE_HEAD + "お前は judge。", "お前は judge。", "役の定義の頭（name・model・tools）を外し、本文だけを前付けする"),
         ("規律の外。\n# P2-11 " + REVIEW_TITLE, "規律の外。\n\n# " + REVIEW_TITLE,
          "見出しの段の番号 P2-11 を外し、役の本文との間を空ける"),
         ("修正役の案: {{out.p2.fix_plan.plan}}\n" + ORIGINAL_UNITS_LINE + "\n判定者の見立て: {{record.process.diagnosis | pick framing,one_shot}}\n"
          "判定者の先行例（世界の解）: {{?record.process.precedents}}\n"
          "リポジトリ: {{inputs.cwd}}（読む版: `{{inputs.review_rev}}`）\u3000BASE: `{{record.base}}`\u3000観点の正本: {{inputs.review_md}}\n",
          "材料のファイル `$review-prep.output.prompt_file` を Read で読め。役の頭の決まり（関所の項目の決め手・既にある物を量ったか・"
          "人に回す物の挙げ方・独立設計との突き合わせ・項目の works の欄）、前の往復の block（2 往復目から）、項目ごとの下請けを並べる"
          "束ね役の頼み（在れば）、修正役の案・直す単位・判定者の見立て・先行例・リポジトリと読む版・人の方針は、全部そこに在る。"
          "束ね役の頼みが在れば、それに従って下請けを起こし、返答はその頼みの形にせよ。返すのは下の決まりと返し方に合う JSON だけ。\n\n"
          "リポジトリ: 材料のファイルの『リポジトリ』の行が名指す所（読む版と観点の正本も同じ行）\n",
          "engine の雛形の 5 行を材料のファイルへ移す（下請けに貼る『リポジトリ: 』の行は残す）"),
         ("を P3 で答える", "を修正の段で答える", "段の番号 P3 を言い換える")]),
    "r2-design.md": (
        [("works/.shared/core/gl-prompts/prompts/review-loop/r2.design.md",
          "135fe61e6a01f7632b60b9df548d5508a1066c453295bf0fe0a6553159cbc6ac", 1731)],
        [("お前は blind-judge（",
          "お前は独立の目の 1 つ（R2 ゼロベース再導出（独立設計の半分））として、新しい会話で起きている。修正案も、判定の経緯も、"
          "実装も引き継いでいない。\nお前は道具を一切持たない。ファイルもリポジトリも開けない——下の囲みの中が渡された物の全部である。\n\n"
          "お前は blind-judge（",
          "新しい会話・道具なし・囲みの中が全部の 2 行を頭に"),
         (R2_TAKEN,
          "囲みの中に、元の目的と、実測した制約（kind=仮説 のものは所与にするな）と、前提のドリフトと裏取りを通っていない目的の判定"
          "（あれば）の 2 行が在る。囲みの頭に「人が決めた前提」の節が在れば、それも渡した物である。\n囲みの頭に「前の回の受け付けが"
          "拒んだ理由」の節が在れば、お前の前の返答は受け付けで拒まれている。そこに書かれた所を直した返答を丸ごと出し直せ（直した所"
          "だけを返すな）。\n\n=====渡した物ここから=====\n$r2-prep.output.prompt\n=====渡した物ここまで=====\n",
          "雛形の差し込み（目的・制約・前提のドリフト・裏取りを通っていない目的の判定）を支度の材料の囲みへ移す（4 つとも r2_prep が貼る）"),
         ("人へ）。\n", "人へ）。根拠に実物を名指すなら `<パス>:<行>` の形で書け（受け付けが依頼を固めた版で検算する）。\n",
          "問いが立たない根拠の名指しの形（受け付けが固めた版で照らす）"),
         ("比較役がやる。\n", "比較役がやる。\n\n返すのは JSON だけ: question_stands（問いが立つか）・reason（判断の理由）・"
          "premise_invalid_reason（問いが立たない時の根拠）・design（独立設計）。\n", "返し方の 1 行")]),
}


def workflow() -> dict:
    return yaml.safe_load(YAML.read_text(encoding="utf-8"))


def walk(nodes, inside=None):
    for n in nodes or []:
        yield n, inside
        if "loop_group" in n:
            yield from walk(n["loop_group"].get("nodes"), n)


def nodes() -> dict:
    return {n["id"]: n for n, _ in walk(workflow()["nodes"])}


def load_script(name: str) -> types.ModuleType:
    """ブロックの script を main を走らせずにモジュールとして読む"""
    spec = importlib.util.spec_from_file_location(f"plan_review_{name}", BLOCK / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def item(unit, n=1, **extra) -> dict:
    """修正案の項目の行（p2.fix_plan.json の plan[] の 1 行。unit_keys は単位の名）"""
    return {"unit_keys": [unit], "approach": f"{PLAN_MARK} 項目 {n} の直し: {unit} を直す",
            "adds": [{"name": f"helper_{n}", "canonical": "stats.py（新設。同じ仕事の助け手は stats.py に無い）"}],
            "removes": [], "shrink_first": "要らない", "narrows": [], **extra}


def fields(unit) -> dict:
    """修正案の項目の works の欄（plan-fields.json の fields[] の 1 行）"""
    return {"route": "direct", "route_why": "1 行の直しで済む", "tests": [], "rewrite_tests": [], "refactor": "無い",
            "allowed_paths": ["stats.py"], "out_of_scope": [], "structure": []}


def face(key, unit=UNIT_MEAN, kind="contract_drift", severity="block", **extra) -> dict:
    return {"key": key, "unit_keys": [unit], "kind": kind, "where": "stats.py mean",
            "why": f"{key} の穴になる筋道を 20 字以上で書いた行", "severity": severity, **extra}


def review(*faces, **extra) -> dict:
    out = {"faces": list(faces), "shrink": [], "reason": "案を全部読み、写し・入口・契約のずれを確かめた"}
    if not faces:
        out["faces_none"] = "写し・入口・契約のずれ・死んだ道・範囲の膨張・後退・方針を全部確かめて穴が無い"
    return {**out, **extra}


def texts(got) -> list:
    """返す節の questions（関所の項目 {kind, text}）の文の並び"""
    return gatemarks.row_texts(got["questions"])


class Run:
    """1 つの run の置き場と対象のリポジトリ。入力の指し札の先のファイルを置き、script を子のプロセスで回す"""

    def __init__(self, tmp: pathlib.Path):
        self.tmp = tmp
        self.repo = tmp / "repo"
        committed_copy(self.repo, SEED)
        self.art = tmp / "artifacts"
        self.art.mkdir()
        self.folder = self.art / boardview.FOLDER
        self.inputs = {}
        self.units = [{"key": UNIT_MEAN, "label": LABEL_MARK, "reason": "分母が 1 少ない"},
                      {"key": UNIT_CLAMP, "label": LABEL_MARK, "reason": "上限で lo を返す"}]
        self.judgment()
        self.purpose()
        self.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)])
        self.structure()
        self.ripple({"items": [], "overlaps": [], "note": RIPPLE_MARK})
        self.inputs.update(units=json.dumps([{"id": UNIT_MEAN, "paths": ["stats.py"], "summary": "mean"}]), world="null",
                           start="null", answers="null", ruling="[]", conflicts="null", gate_answers="null",
                           round_limit=str(ROUND_LIMIT))

    def put(self, rel: str, doc, raw: bool = False) -> str:
        """置き場の rel に doc を書き、その指し札の JSON の字を返す"""
        p = self.art / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc if raw else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})

    def judgment(self, questions=(), materials=None, precedents=(), constraints=None, purpose_review=None, **extra):
        self.inputs["judgment"] = self.put("judge/judgment.json", {
            "units": self.units, "questions": list(questions), "framing": f"{FRAMING_MARK} 分母と上限の 2 つの誤り",
            "one_shot": f"{ONE_SHOT_MARK} 2 か所を直す", "precedents": list(precedents), **extra})
        self.put("judge/premises.json", {"constraints": constraints if constraints is not None else [
            {"text": f"{CONSTRAINT_MARK} 空の列は例外", "measured_how": "読んだ", "kind": "実測", "measured_output": "x"}]})
        self.put("judge/materials.json", materials or {})
        self.put("judge/purpose-review.json", purpose_review or {})

    def purpose(self, **extra):
        self.inputs["purpose"] = self.put("judge/purpose.json", {"purpose_text": f"{PURPOSE_MARK} 統計の関数が正しい値を返す",
                                                                  "source_files": [], "source": "依頼", **extra})

    def plan(self, rows, rnd=1, answers=None, field_rows=None):
        doc = {"plan": rows}
        if answers is not None:
            doc[converge.ANSWERS] = answers
        self.put(f"plan/r{rnd}/p2.fix_plan.json", doc)
        self.inputs["plan"] = self.put(f"plan/r{rnd}/plan-fields.json",
                                       {"round": rnd, "fields": field_rows or [fields(r["unit_keys"][0]) for r in rows]})

    def structure(self, rows=(), status="ok"):
        self.put("plan/structure/design.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), raw=True)
        self.inputs["structure"] = self.put("plan/structure/structure-state.json",
                                            {"status": status, "reason": "", "design_file": "x", "wall_s": 0})

    def ripple(self, doc):
        self.inputs["ripple"] = self.put("plan/ripple.json", doc)

    def world(self, *rows):
        self.inputs["world"] = self.put("judge/world/world.jsonl",
                                        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), raw=True)

    def start(self, **doc):
        self.inputs["start"] = self.put("start/start.json", {"run_id": RUN_ID, "base_rev": "HEAD", "review_rev": "HEAD", **doc})

    def env(self, **extra) -> dict:
        names = {f"INPUTS_{k.upper()}": v for k, v in self.inputs.items()}
        return hermetic.child_env(**{"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": RUN_ID, "WORKS_FACTORY_ROOT": str(ROOT),
                                     "PYTHONDONTWRITEBYTECODE": "1", **names, **extra})

    def script(self, name: str, **extra) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{name}.py")], cwd=self.repo, env=self.env(**extra),
                              capture_output=True, text=True, encoding="utf-8")

    def out(self, name: str, **extra) -> dict:
        done = self.script(name, **extra)
        if done.returncode != 0:
            raise AssertionError(f"{name} が {done.returncode} で落ちた: {done.stderr}{done.stdout}")
        return json.loads(done.stdout)

    def open(self) -> dict:
        got = self.out("pass_open")
        if not got["ok"]:
            raise AssertionError(got["reason"])
        return got

    def accept(self, reply, name="review_accept") -> dict:
        return self.out(name, INPUTS_REPLY=json.dumps(reply, ensure_ascii=False))

    def pass_(self, reply) -> dict:
        """1 往復（open → review_prep → review_accept → result）を回す。返りは result の返り"""
        self.open()
        self.out("review_prep")
        got = self.accept(reply)
        if not got["ok"]:
            raise AssertionError(got["reason"])
        return self.out("result")

    def view(self, review_doc=None):
        return boardview.view(self.folder, boardview.read_open(self.folder), review_doc)

    def pointed(self, ptr: dict) -> pathlib.Path:
        self.assert_pointer(ptr)
        return self.art / ptr["path"]

    def assert_pointer(self, ptr):
        if not (ptr["type"] == "archon_artifact" and ptr["run_id"] == RUN_ID and (self.art / ptr["path"]).is_file()):
            raise AssertionError(f"指し札の先が無い: {ptr}")


class RunCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_ = Run(pathlib.Path(os.path.realpath(self._tmp.name)))


NO_EFFECT = "上限の枝の外の値か、直した後の値だけを断言していて期待は変わらない"
CHECKED = "項目の案を stats.py と test_stats.py で読み、呼び出し元と試験の期待を確かめた"
SUMMARY_REASON = "項目ごとの下請けの答えのファイルを受け、項目ごとの判定をまとめた"
MEAN_BLOCK = face("item1-mean-empty-division", UNIT_MEAN, kind="regression")
CLAMP_BLOCK = face("item2-clamp-upper-branch", UNIT_CLAMP)
PRECEDENTS = [{"key": UNIT_MEAN, "source": "https://docs.python.org/3/library/statistics.html#statistics.mean",
               "verdict": "adopt", "reason": "空の列の平均の扱いを公式に合わせる"},
              {"key": UNIT_CLAMP, "source": "https://numpy.org/doc/stable/reference/generated/numpy.clip.html",
               "verdict": "adapt", "reason": "上限を超えた値の扱いを合わせる"}]
RIPPLE = {"items": [{"item": 1, "unit_keys": [UNIT_MEAN], "names": [], "uncovered": []},
                    {"item": 2, "unit_keys": [UNIT_CLAMP],
                     "names": [{"name": "clamp", "files": 2, "code": ["stats.py:12"],
                                "tests": ["test_stats.py::TestStats::test_clamp_above_range"]}],
                     "uncovered": [{"id": "h1", "kind": "test", "at": "test_stats.py::TestStats::test_clamp_above_range",
                                    "name": "clamp"}]}],
          "overlaps": [{"at": "stats.py", "items": [1, 2]}]}
DESIGN_TEXT = "上限は入口 1 箇所で掛け、各所では掛け直さない。平均は定義どおりに割る"
DESIGN_OK = {"question_stands": True, "reason": "問いは立っている", "design": DESIGN_TEXT}
ROW_TEXT = "式と戻り値を 1 か所ずつ直すだけで足りる"
FORBIDDEN_ENV = ("INPUTS_PLAN", "INPUTS_STRUCTURE", "INPUTS_RIPPLE", "INPUTS_UNITS", "INPUTS_WORLD", "INPUTS_RULING")
R2_ENV = ("INPUTS_PURPOSE", "INPUTS_JUDGMENT", "INPUTS_START", "INPUTS_ANSWERS", "ARTIFACTS_DIR", "WORKFLOW_ID")


def answer(n, doc=RIPPLE, faces=(), resolved=(), why=NO_EFFECT) -> dict:
    """項目 n の下請けの答え（覆っていない当たりは全部 no_effect）"""
    return {"item": n, "checked": CHECKED, "faces": list(faces), "shrink": [], "resolved": list(resolved),
            "hits": [{"id": h["id"], "answer": "no_effect", "why": why} for h in planblk.ripple.uncovered(doc, n)]}


def synergy(faces=()) -> dict:
    return {"why": "2 つの項目は stats.py の別の関数を直し、順番の依存も重複も無い", "faces": list(faces)}


def summary(verdicts) -> dict:
    """束ね役の返答（項目ごとの判定の要約だけ。verdicts は {項目: [block の key]}）"""
    return {"faces": [], "shrink": [], "reason": SUMMARY_REASON,
            "items": [{"item": n, "verdict": "block" if keys else "clean",
                       "blocks": [{"key": k, "why": "下請けが挙げた穴"} for k in keys]} for n, keys in verdicts.items()]}


def env_names(text: str) -> set:
    return set(re.findall(r"os\.environ(?:\.get)?\s*[\[(]\s*\"([A-Z_]+)\"", text))


class YamlCase(unittest.TestCase):
    """ブロックの YAML の形（元 tests/test_blk_plan.py の YamlCase の事前審査と独立設計の側）"""

    def test_reads_roles_are_the_role_nodes_by_their_tools(self):
        """読んだ証拠の節が名指す役は YAML の役の節と同じ: 道具を持つ役は review_reads.ROLE、持たない役は planblk.DESIGN_ROLE
        （役が道具を得たのに null と書く黙った緩みを赤にする）"""
        roles = [n for n in nodes().values() if "command" in n or "prompt" in n]
        self.assertEqual({n["id"] for n in roles if n.get("allowed_tools")}, {load_script("review_reads").ROLE})
        self.assertEqual({n["id"] for n in roles if not n.get("allowed_tools")}, {planblk.DESIGN_ROLE})

    def test_returns_review_and_outcome_pass(self):
        doc = workflow()
        self.assertEqual((doc["name"], doc["returns"], doc["outcome_field"]), ("works-factory-plan-review", "review", "pass"))

    def test_return_output_format_is_exactly_the_contract(self):
        """返す節の output_format は返りの約束の欄をちょうど持ち、全部 required・additionalProperties: false"""
        fmt = nodes()["review"]["output_format"]
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURN_FIELDS))
        self.assertEqual(sorted(fmt["required"]), sorted(RETURN_FIELDS))
        self.assertIs(fmt["additionalProperties"], False)
        props = fmt["properties"]
        for name in ("pass", "stalled", "ask_human"):
            self.assertEqual(props[name], {"type": "boolean"})
        self.assertEqual(props["questions"], {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["kind", "text"],
                                                           "properties": {"kind": {"type": "string"}, "text": {"type": "string"}}}})
        for name in ("review", "design"):
            self.assertEqual(props[name]["properties"]["type"]["enum"], ["archon_artifact"])
            self.assertEqual(sorted(props[name]["required"]), ["path", "run_id", "type"])
        axes = props["gate_axes"]
        self.assertEqual(sorted(axes["required"]), sorted(boardview.gate_axes.AXES))
        for axis in boardview.gate_axes.AXES:
            self.assertEqual(axes["properties"][axis]["properties"], {"ok": {"type": "boolean"}, "note": {"type": "string"}})

    def test_inputs_are_the_contract_and_the_added_defaults(self):
        got = workflow()["inputs"]
        self.assertEqual(set(got), set(CONTRACT_INPUTS) | set(ADDED_INPUTS))
        for name in CONTRACT_INPUTS:
            self.assertIs(got[name].get("required"), True, name)
        for name, default in ADDED_INPUTS.items():
            self.assertEqual(got[name].get("default"), default, name)

    def test_no_run_owned_keys_at_the_head(self):
        """差し込まれるブロックは工程の頭に run の持ち物を書かない（Archon が読み込みで捨てる。workflows/AGENTS.md の E16）"""
        self.assertEqual([k for k in RUN_KEYS if k in workflow()], [])

    def test_ai_and_script_nodes_are_read_only(self):
        for n, _ in walk(workflow()["nodes"]):
            if "loop_group" in n:
                continue
            with self.subTest(n["id"]):
                self.assertIs(n.get("mutates_checkout"), False)

    def test_role_nodes(self):
        """役の節の設定は今の works の節 r2-design・plan-review のまま（模型と深さは役の前付け blind-judge・judge）。独立設計は
        context を書かず、拒まれた後の出し直しは輪（fresh_context: false）の中で前の会話を継ぐ（今の works の r2-design と同じ）"""
        got = nodes()
        self.assertNotIn("context", got["r2-design"])
        self.assertEqual(got["plan-review"]["context"], "fresh")
        for nid in ("r2-design", "plan-review"):
            with self.subTest(nid):
                n = got[nid]
                self.assertEqual((n["command"], n["model"], n["effort"]), (nid, "opus", "high"))
                self.assertEqual(n["settingSources"], ["user"])
                self.assertEqual(n["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False})
                self.assertEqual(n["idle_timeout"], DEADLINE)
        self.assertEqual(got["r2-design"]["allowed_tools"], [])
        # 節の systemPrompt（字）は Archon の Claude の既定 {preset: claude_code}（作業ツリーの git の様子を入れる）を置き換える
        # （止めた Archon の packages/providers/src/claude/provider.ts の systemPrompt の既定と節の上書き）
        self.assertIn("blind-judge", got["r2-design"]["systemPrompt"])
        self.assertNotIn("systemPrompt", got["plan-review"])
        self.assertEqual(got["plan-review"]["allowed_tools"], ["Read", "Grep", "Glob", "WebSearch", "WebFetch", "Agent", "Write"])

    def test_role_prefaces_are_the_ported_role_bodies(self):
        """事前審査の指示書の頭は役 judge の本文、独立設計の systemPrompt は役 blind-judge の本文と字が同じ（今の works の
        engine が役の定義 agents/<役>.md の本文を前付けした形。写しは lib/agents/）"""
        def body(role: str) -> str:
            return (LIB / "agents" / f"{role}.md").read_text(encoding="utf-8").split("---", 2)[2].strip()
        text = (BLOCK / "commands" / "plan-review.md").read_text(encoding="utf-8")
        self.assertEqual(text[:text.index("\n\n# 修正案の事前審査")], body("judge"))
        self.assertEqual(nodes()["r2-design"]["systemPrompt"], body("blind-judge"))

    def test_loops_are_three_and_end_on_accept_done(self):
        """出し直しの輪は 3 回（諦めの数 rolekit.GIVE_UP_AFTER と同じ）で、until_bash は同じ輪の受け付けの done"""
        got = nodes()
        for loop, accept_id, fresh in (("r2-design-loop", "r2-accept", False), ("review-loop", "review-accept", True)):
            with self.subTest(loop):
                group = got[loop]["loop_group"]
                self.assertEqual(group["max_iterations"], boardview.rolekit.GIVE_UP_AFTER)
                self.assertIn(f"${accept_id}.output.done", group["until_bash"])
                self.assertIs(group["fresh_context"], fresh)
                self.assertEqual(got[loop]["timeout"], DEADLINE)
        self.assertEqual(got["r2-design-loop"]["when"], "$open.output.r2_go == true")
        self.assertEqual(got["review-loop"]["trigger_rule"], "all_done")
        self.assertEqual(got["review"]["trigger_rule"], "all_done")

    def test_role_formats_are_mainline_plus_marks(self):
        """事前審査の役の型は、写しの p2.plan_review の型に、関所の決め手の欄（gatemarks）と壁打ちと束ね役の欄（converge）を足した物"""
        fmt = nodes()["plan-review"]["output_format"]
        row = fmt["properties"]["faces"]["items"]["properties"]
        strip = lambda d: {k: v for k, v in d.items() if k != "note"}  # noqa: E731
        for name, schema in {**gatemarks.MARK_SCHEMA, gatemarks.NO_NARROW: gatemarks.NO_NARROW_SCHEMA}.items():
            with self.subTest(name):
                got = row[name]
                want = strip(schema)
                if name == gatemarks.RECOMMEND:
                    want = {**want, "properties": schema["properties"]}
                self.assertEqual(got, want)
        self.assertEqual(fmt["properties"]["resolved"], converge.RESOLVED_SCHEMA)
        self.assertEqual(fmt["properties"]["items"], converge.ITEMS_SCHEMA)
        self.assertEqual(fmt["properties"]["design_map"], converge.DESIGN_MAP_SCHEMA)
        self.assertEqual(fmt["properties"]["origins"], converge.ORIGIN_SCHEMA)
        self.assertEqual(sorted(fmt["required"]), ["faces", "reason", "shrink"])
        self.assertLessEqual(set(boardview.HUMAN_FACE_KINDS), set(row["kind"]["enum"]), "人の関所に回す穴の種類が役の返りの kind に無い")

    def test_recommend_is_optional_on_both_roles(self):
        """元 tests/test_gate_drafts.py の SchemaCase.test_gate_rows_have_the_recommend_field: 推しの欄は事前審査の faces の行と
        修正案の narrows の行の型に在り、どちらも required に入れない"""
        faces = nodes()["plan-review"]["output_format"]["properties"]["faces"]["items"]
        plan_doc = yaml.safe_load((ROOT / "workflows" / "plan" / "works-factory-plan.yaml").read_text(encoding="utf-8"))
        writer = next(n for g in plan_doc["nodes"] for n in [g, *g.get("loop_group", {}).get("nodes", [])] if n["id"] == "plan-writer")
        narrows = writer["output_format"]["properties"]["plan"]["items"]["properties"]["narrows"]["items"]
        for name, row in (("faces", faces), ("narrows", narrows)):
            with self.subTest(name):
                self.assertIn(gatemarks.RECOMMEND, row["properties"])
                self.assertNotIn(gatemarks.RECOMMEND, row["required"])

    def test_scripts_read_role_formats_from_the_yaml(self):
        """script は外のパッケージ無しで走るので、役の節の型は JSON の形で書き、差し込みの頭の script の node_schema で読む
        （節の id と YAML の並びの読みは script の側に置く。lib/AGENTS.md の E3）"""
        text = YAML.read_text(encoding="utf-8")
        got = nodes()
        script = load_script("pass_open")
        for nid in ("r2-design", "plan-review"):
            self.assertEqual(script.node_schema(text, nid), got[nid]["output_format"])
        for nid, word in (("nope", "ノード nope が無い"), ("review-loop", "output_format が無い"), ("review", "JSON の形でない")):
            with self.subTest(nid), self.assertRaises(ValueError) as cm:
                script.node_schema(text, nid)
            self.assertIn(word, str(cm.exception))

    def test_commands_read_only_their_prep(self):
        """役の指示書が読む節の出力は自分の支度の物だけ（独立設計は $r2-prep.output.prompt だけ）。{{…}} の差し込みは使わない"""
        for name, ref in (("r2-design", "$r2-prep.output.prompt"), ("plan-review", "$review-prep.output.prompt_file")):
            with self.subTest(name):
                text = (BLOCK / "commands" / f"{name}.md").read_text(encoding="utf-8")
                self.assertEqual(re.findall(r"\$[A-Za-z][\w-]*\.output(?:\.[\w-]+)*", text), [ref])
                self.assertNotIn("{{", text)
                self.assertNotIn("$INPUTS", text)

    def test_review_command_carries_the_rules_after_the_repository_line(self):
        """事前審査の役の指示書は写しの p2.plan_review の決まり（見ること 1〜8・shrink・返し方・根拠は読む版で取る）を、下請けに貼る
        『リポジトリ: 』の行の後ろに持つ"""
        text = (BLOCK / "commands" / "plan-review.md").read_text(encoding="utf-8")
        rules = text[text.index(planblk.RULES_FROM):]
        for word in ("## 見ること", "kind=copy", "kind=entrance", "no_add", "kind=contract_drift", "kind=dead_path",
                     "kind=scope_creep", "kind=regression", "kind=policy", "kind=precedent", "6・7 の穴", "shrink",
                     "## 返し方", "faces_none", "根拠は読む版で取れ"):
            self.assertIn(word, rules)

    def test_r2_command_is_the_original_with_only_the_allowed_edits(self):
        """独立設計の指示書は元の r2.design.md の字のまま: 許した直しを逆に当てると元のバイトに戻る"""
        self.assertEqual(copied.restore_problems(BLOCK / "commands" / "r2-design.md", *COPIED["r2-design.md"]), [])

    def test_review_command_is_the_original_with_only_the_allowed_edits(self):
        """事前審査の指示書は役 judge の定義と元の p2.plan_review.md を繋いだ字のまま: 許した直しを逆に当てると元のバイトに戻る"""
        self.assertEqual(copied.restore_problems(BLOCK / "commands" / "plan-review.md", *COPIED["plan-review.md"]), [])

    def test_script_names_do_not_hide_lib_modules(self):
        names = {p.stem for p in (BLOCK / "scripts").glob("*.py")}
        self.assertEqual(names, {"pass_open", "r2_prep", "r2_accept", "review_prep", "review_accept", "review_reads", "result"})
        self.assertEqual(names & {p.stem for p in LIB.glob("*.py")}, set())

    def test_scripts_read_only_declared_inputs(self):
        """script が読む INPUTS_* は工程の入力か、節の with: の結び"""
        doc = workflow()
        declared = {f"INPUTS_{k.upper()}" for k in doc["inputs"]}
        by_script = {n["script"]: {f"INPUTS_{k.upper()}" for k in (n.get("with") or {})}
                     for n, _ in walk(doc["nodes"]) if "script" in n}
        for name, bound in by_script.items():
            with self.subTest(name):
                text = (BLOCK / "scripts" / f"{name}.py").read_text(encoding="utf-8")
                reads = {x for x in env_names(text) if x.startswith("INPUTS_")}
                self.assertLessEqual(reads, declared | bound)

    def test_no_loop_prev_reaches_a_role(self):
        """元 YamlCase.test_no_loop_prev_reaches_a_prompt: 役に届く文に $LOOP_PREV が無い（前の拒みは支度が本文か材料の頭に貼る）"""
        texts = [YAML.read_text(encoding="utf-8"), *(p.read_text(encoding="utf-8") for p in (BLOCK / "commands").glob("*.md"))]
        self.assertFalse([t for t in texts if "$LOOP_PREV" in t])

    def test_loop_ids_unique_across_blocks(self):
        """元 YamlCase.test_loop_ids_unique_across_blocks: 輪の中の id は差し込まれても頭が付かないので、木に在るほかのブロックと
        線の輪の中の id と重ならない"""
        def body_ids(doc):
            return {n["id"] for n, inside in walk(doc.get("nodes")) if inside is not None}
        mine = body_ids(workflow())
        for other in sorted((ROOT / "workflows").glob("*/works-factory-*.yaml")):
            if other.parent == BLOCK:
                continue
            with self.subTest(other.parent.name):
                self.assertEqual(mine & body_ids(yaml.safe_load(other.read_text(encoding="utf-8"))), set())


class CopiedTextsCase(unittest.TestCase):
    """指示書の写しの台帳（K9）: commands/ の全部が台帳に在り、許した直しを逆に当てると元のバイトに戻る"""

    def test_every_command_is_its_original_with_only_ledgered_edits(self):
        names = sorted(p.name for p in (BLOCK / "commands").glob("*.md"))
        self.assertEqual(names, sorted(COPIED), "台帳に無い指示書か、指示書の無い台帳の行")
        self.assertLessEqual(copied.rewritten(BLOCK / "commands"), set(COPIED), "台帳に無い指示書の書き直し")
        for name in names:
            with self.subTest(name):
                self.assertEqual(copied.restore_problems(BLOCK / "commands" / name, *COPIED[name]), [])


class IsolationCase(RunCase):
    """独立設計に禁じた入力が届かない（持ち主の決め independent-verdict・premises-purpose。元 tests/test_blk_plan.py の
    ScriptCase.test_design_before_plan_reaches_plan_review・test_independent_design_input_has_no_means）"""

    def test_r2_prep_reads_only_the_allowed_names(self):
        """Archon は工程の入力を全部の script に INPUTS_* で渡すので、r2_prep が読む名を字で縛る（名を組んで読む書き方も無い）"""
        text = (BLOCK / "scripts" / "r2_prep.py").read_text(encoding="utf-8")
        self.assertLessEqual(env_names(text), set(R2_ENV))
        for name in FORBIDDEN_ENV:
            self.assertNotIn(name, text)
        for built in ("os.environ[f", "os.getenv", "environ.items", "environ.keys", "\"INPUTS_\" +", "'INPUTS_' +", "environ)"):
            self.assertNotIn(built, text)

    def test_prompt_carries_purpose_and_constraints_only(self):
        """全部の INPUTS_* を置いた環境で回しても、目的の文と制約は届き、修正案・単位の label・判定の見立て・波及は届かない"""
        r = self.run_
        r.units[0]["label"] = "LABEL-MARK-3131"
        r.judgment()
        r.world(TP.WORLD_ROW)
        r.start(base_rev="HEAD")
        prompt = r.out("r2_prep")["prompt"]
        for want in (PURPOSE_MARK, CONSTRAINT_MARK):
            self.assertIn(want, prompt)
        for leak in (PLAN_MARK, "LABEL-MARK-3131", FRAMING_MARK, ONE_SHOT_MARK, RIPPLE_MARK, UNIT_MEAN, "w-mean", str(r.repo) + "/"):
            self.assertNotIn(leak, prompt)
        premises = (r.folder / boardview.PREMISES_FILE).read_text(encoding="utf-8")
        for leak in (PLAN_MARK, FRAMING_MARK, RIPPLE_MARK):
            self.assertNotIn(leak, premises)

    def test_prompt_carries_drift_and_unvetted_purpose_lines(self):
        """元の指示書の 2 行（前提のドリフト・裏取りを通っていない目的の判定）を材料に持つ。R2 は修正の前に 1 度だけ走るのでドリフトは
        無い。目的の監査の『狭めている』が裏取り（cite）の無い findings に乗っていれば、その行を名指す（元 review-loop.py:1838）"""
        r = self.run_
        r.open()
        prompt = r.out("r2_prep")["prompt"]
        self.assertIn(boardview.DRIFT_LINE.format(notes=boardview.NONE_YET), prompt)
        self.assertIn(boardview.STALE_LINE.format(stale=boardview.NONE_YET), prompt)
        r.judgment(purpose_review={"verdict": "狭めている", "reason": "要約が狭い", "findings": ["素の文字列"]})
        r.open()
        prompt = r.out("r2_prep")["prompt"]
        self.assertIn(boardview.STALE_WHY, prompt)
        self.assertNotIn(boardview.STALE_LINE.format(stale=boardview.NONE_YET), prompt)

    def test_purpose_means_do_not_reach_the_design(self):
        """目的の役が分けた依頼の解き方 means（purpose.json の隣）は独立設計に渡らない"""
        sentinel = "読むだけの役を足して生のログから引用つきで判じさせる手段"
        self.run_.put("judge/purpose-means.json", {"means": [sentinel]})
        prompt = self.run_.out("r2_prep")["prompt"]
        self.assertNotIn(sentinel, prompt)
        self.assertNotIn(sentinel, (self.run_.folder / boardview.PREMISES_FILE).read_text(encoding="utf-8"))

    def test_defaults_are_named_in_the_premises(self):
        """線が始めの記録と人の答えを渡さない時は、名指しの節は渡っていないと貼り、控えの withheld に訳を残す"""
        prompt = self.run_.out("r2_prep")["prompt"]
        self.assertIn(boardview.NOT_GIVEN_START, prompt)
        ledger = json.loads((self.run_.folder / boardview.PREMISES_FILE).read_text(encoding="utf-8"))
        whats = {(w["kind"], w["what"]) for w in ledger["withheld"]}
        self.assertLessEqual({("named_section", "start"), ("human_answer", "answers")}, whats)

    def test_unreadable_request_file_is_named(self):
        """始めの記録が名指す依頼のファイルが無い・UTF-8 でない時は、名指しが無い時と同じ空にせず、独立設計の本文と控えの
        withheld と事前審査の材料の頭に読めない訳を残す（持ち主の決め no-silent-loosen）"""
        r = self.run_
        broken = r.tmp / "request-utf16.md"
        broken.write_bytes("依頼".encode("utf-16"))
        for label, req, why in (("無い", r.tmp / "no-such-request.md", "FileNotFoundError"),
                                ("UTF-8 でない", broken, "UnicodeDecodeError")):
            with self.subTest(label):
                r.start(request_file=str(req), features_off=["review_tree"])
                line = boardview.REQUEST_UNREAD.format(path=req, why=why)
                self.assertIn(line, r.out("r2_prep")["prompt"])
                ledger = json.loads((r.folder / boardview.PREMISES_FILE).read_text(encoding="utf-8"))
                self.assertIn({"kind": "named_section", "what": str(req), "why": line}, ledger["withheld"])
                r.open()
                text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
                self.assertTrue(text.startswith(boardview.DEFAULTS_HEAD), text[:200])
                self.assertIn(line, text.splitlines()[0])

    def test_human_answers_and_named_sections_are_pasted(self):
        """人の関所の答えと、依頼が名指した設計書の節（固めた版のファイルから）を前提として貼る"""
        r = self.run_
        doc = r.repo / "docs" / "design.md"
        doc.parent.mkdir()
        doc.write_text("# 設計\n\n## 2 上限\n\n上限は入口で掛ける\n\n## 3 平均\n\n定義どおり\n", encoding="utf-8")
        git(r.repo, "add", "-A")
        git(r.repo, "commit", "-qm", "設計書")
        req = r.tmp / "request.json"
        req.write_text(json.dumps({"findings": [{"where": "stats.py", "text": "`docs/design.md` 2 節のとおりに直す"}]},
                                  ensure_ascii=False), encoding="utf-8")
        r.start(request_file=str(req))
        r.inputs["answers"] = json.dumps({"decision": "approve", "text": "空の列は例外のままにする"}, ensure_ascii=False)
        prompt = r.out("r2_prep")["prompt"]
        self.assertIn(design.HUMAN_HEAD, prompt)
        self.assertIn("空の列は例外のままにする", prompt)
        self.assertIn("上限は入口で掛ける", prompt)
        self.assertNotIn("定義どおり", prompt)
        self.assertIn(design.MAP_HEAD, prompt)




class DesignCase(RunCase):
    """独立設計の支度と受け付け（元 tests/test_blk_plan.py の ScriptCase.test_design_* ）"""

    def designed(self, reply=None):
        r = self.run_
        prompt = r.out("r2_prep")["prompt"]
        return prompt, r.accept(DESIGN_OK if reply is None else reply, "r2_accept")

    def test_design_accepted_and_reaches_the_review(self):
        """元 test_design_before_plan_reaches_plan_review: 通った設計は design.json に控え、事前審査の材料の頭にその設計と
        食い違いを contract_drift・block で挙げる頼みが載る。同じ run の 2 度目の差し込みでは回さない"""
        r = self.run_
        r.start(features_off=["review_tree"])
        self.assertTrue(r.open()["r2_go"])
        _, got = self.designed()
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (True, True, False), got)
        self.assertEqual(json.loads((r.folder / design.DESIGN_FILE).read_text(encoding="utf-8")), DESIGN_OK)
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        for want in (planblk.DESIGN_HEAD, planblk.DESIGN_ASK, DESIGN_TEXT):
            self.assertIn(want, text)
        self.assertFalse(r.open()["r2_go"], "設計を 2 度作らない")

    def test_anchor_must_be_in_the_frozen_version(self):
        """問いが立たない根拠の名指し（パス:行）が固めた版に無い返答を拒む。在れば受ける"""
        r = self.run_
        r.open()
        bad = {"question_stands": False, "reason": "問いが立たない", "premise_invalid_reason": "stats.py:999 で既に満たされている",
               "design": ""}
        _, got = self.designed(bad)
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(boardview.PREMISE_MISS), got["reason"])
        self.assertIn("stats.py:999", got["reason"])
        _, got = self.designed({**bad, "premise_invalid_reason": "stats.py:9 で既に満たされている"})
        self.assertTrue(got["ok"], got)

    def test_give_up_on_the_third_reject_still_done(self):
        """元 test_design_gave_up_does_not_stop_plan_review: 3 回とも拒まれても輪は 3 回目の done で抜け、事前審査は設計なしで
        進む。2 回目からの本文の頭に前の拒みの文が貼られる。返す節の design の指し札は諦めた訳"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        rounds = [self.designed({"reason": "型に合わない"}) for _ in range(boardview.rolekit.GIVE_UP_AFTER)]
        self.assertEqual([(g["ok"], g["done"], g["give_up"]) for _, g in rounds],
                         [(False, False, False)] * 2 + [(False, True, True)])
        self.assertTrue(rounds[1][0].startswith(boardview.rolekit.REJECT_HEADING))
        until = nodes()["r2-design-loop"]["loop_group"]["until_bash"].replace("$r2-accept.output.done", "true")
        self.assertEqual(subprocess.run(["sh", "-c", until]).returncode, 0)
        self.assertFalse(r.open()["r2_go"], "諦めた設計は起こし直さない")
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(f"独立設計は無い（{design.MISSING}: ", text)
        self.assertIn("question_stands", text)
        self.assertTrue(r.accept(review())["ok"])
        got = r.out("result")
        self.assertTrue(got["pass"], got)
        missing = json.loads(r.pointed(got["design"]).read_text(encoding="utf-8"))
        self.assertIn("拒まれた", missing["missing"])

    def test_off_schema_reply_names_the_type_error(self):
        """独立設計の返答は役の型（差し込みの頭が YAML から控えた物）で照らし、拒みの訳は型の誤りの欄を名指す"""
        r = self.run_
        r.open()
        _, got = self.designed({"reason": "x"})
        self.assertFalse(got["ok"], got)
        self.assertIn("独立設計の返答", got["reason"])
        self.assertIn("question_stands", got["reason"])

    def test_design_handoff_is_traced(self):
        """返す節は設計の控えを返り design で渡した・渡せなかったを trace に残す（元 design.hand の r2_design_handed・r2_design_missing）"""
        def ops(r):
            rows = [json.loads(x) for x in (r.folder / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
            return [(x["op"], x.get("file"), bool(x.get("reason"))) for x in rows if x["op"] in (design.HANDED_OP, design.MISSING_OP)]

        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        self.designed()
        self.assertTrue(r.pass_(review(design_map=ReviewAcceptCase.full_map()))["pass"])
        self.assertEqual(ops(r), [(design.HANDED_OP, str(r.folder / design.DESIGN_FILE), False)])
        self.setUp()
        r = self.run_
        r.start(features_off=["review_tree"])
        r.pass_(review())
        self.assertEqual(ops(r), [(design.MISSING_OP, None, True)])

    def test_tree_change_rejected(self):
        """元 test_design_tree_change_rejected: 道具ゼロの役でも、起こす前の作業ツリーの姿と比べて変わっていれば拒む"""
        r = self.run_
        r.open()
        r.out("r2_prep")
        (r.repo / "stats.py").write_text("# 変えた\n", encoding="utf-8")
        got = r.accept(DESIGN_OK, "r2_accept")
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(planblk.READONLY_MOVED), got["reason"])
        self.assertFalse((r.folder / design.DESIGN_FILE).exists())

    def test_skipped_when_purpose_unusable(self):
        """元 test_design_skipped_when_purpose_unusable: 目的不明・裏取りを通った『狭めている』では回さず、事前審査はその訳を読む"""
        r = self.run_
        r.purpose(source="目的不明")
        r.start(features_off=["review_tree"])
        self.assertFalse(r.open()["r2_go"])
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(design.UNUSABLE["目的不明"], text)

    def test_skipped_when_purpose_review_sibling_narrows(self):
        """judge が判定の隣に置く purpose-review.json の裏取りを通った『狭めている』では回さない。cite の無い行なら回す"""
        r = self.run_
        r.judgment(purpose_review={"verdict": "狭めている", "reason": "r", "findings": [{"text": "t", "cite": "c", "hits": 1}]})
        self.assertNotIn("purpose_review", json.loads((r.art / "judge" / "judgment.json").read_text(encoding="utf-8")))
        self.assertFalse(r.open()["r2_go"])
        r.judgment(purpose_review={"verdict": "狭めている", "reason": "r", "findings": [{"text": "t", "hits": 1}]})
        self.assertTrue(r.open()["r2_go"])

    def test_unreadable_purpose_review_sibling_is_named(self):
        """判定の隣の purpose-review.json が無い・壊れている・object でない時は監査無しとして読み、その訳を事前審査の材料の頭に残す
        （持ち主の決め no-silent-loosen）"""
        r = self.run_
        r.start(features_off=["review_tree"])
        sibling = r.art / "judge" / "purpose-review.json"
        for body, why in ((None, "FileNotFoundError"), ("{broken", "JSONDecodeError"), ("[1]", "object でなく list")):
            with self.subTest(why):
                if body is None:
                    sibling.unlink()
                else:
                    sibling.write_text(body, encoding="utf-8")
                self.assertTrue(r.open()["r2_go"])
                text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
                self.assertIn(boardview.PURPOSE_REVIEW_UNREAD.format(why=why), text.splitlines()[0])

    def test_not_stands_is_not_a_face(self):
        """元 test_design_not_stands_is_not_a_face: 問いが立たないと返した設計は突き合わせず、穴にも挙げさせない"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        _, got = self.designed({"question_stands": False, "reason": "問いが立たない", "premise_invalid_reason": "識別子は既にある",
                                "design": ""})
        self.assertTrue(got["ok"], got)
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(planblk.DESIGN_NOT_STANDS.format(reason="識別子は既にある（根拠の実物の名指しなし）"), text)
        self.assertNotIn(planblk.DESIGN_ASK, text)

    def test_unpassed_claims_are_paired_with_what_was_given(self):
        """設計が『渡されていない』と書いた文は、控えの渡した物と並べて控える（独立の目が突き合わせる）"""
        r = self.run_
        (r.repo / "AGENTS.md").write_text("# 地図\n\n統計の関数を置く\n", encoding="utf-8")
        git(r.repo, "add", "-A")
        git(r.repo, "commit", "-qm", "地図")
        r.open()
        _, got = self.designed({**DESIGN_OK, "reason": "対象のリポジトリの地図が渡されていない。問いは立つ"})
        self.assertTrue(got["ok"], got)
        claims = json.loads((r.folder / boardview.PREMISES_FILE).read_text(encoding="utf-8"))["claims"]
        self.assertTrue(claims and all(c["kind"] == "repo_map" for c in claims), claims)


class NoFixDesignCase(RunCase):
    """L-W07（元 works/darkfactory/lib/line_edge.py:1107-1119 の plan_edge と works/tests/test_line_a.py::LineCase.test_no_fix_path）:
    直す物が無い周は修正案を作らず、最後の R2 が要る独立設計だけを作る。入力 mode が design の差し込みは、修正案（plan・structure・
    ripple は null）を読まずに独立設計の輪だけを回し、事前審査を回さず、返す節は通った形（関所の項目・問い無し）と design の指し札を返す"""

    def test_design_mode_makes_only_the_design(self):
        r = self.run_
        r.inputs.update(plan="null", structure="null", ripple="null", mode="design")
        got = r.open()
        self.assertEqual((got["form"], got["r2_go"]), ("design", True), got)
        self.assertEqual(nodes()["review-loop"]["when"], "$open.output.ok == true && $open.output.form != 'design'")
        prompt = r.out("r2_prep")["prompt"]
        self.assertIn(PURPOSE_MARK, prompt)
        self.assertTrue(r.accept(DESIGN_OK, "r2_accept")["ok"])
        out = r.out("result")
        self.assertEqual((out["pass"], out["stalled"], out["ask_human"], out["questions"]), (True, False, False, []), out)
        self.assertEqual(json.loads(r.pointed(out["design"]).read_text(encoding="utf-8")), DESIGN_OK)
        self.assertEqual(json.loads(r.pointed(out["review"]).read_text(encoding="utf-8"))["faces"], [])
        self.assertTrue(all(axis["ok"] for axis in out["gate_axes"].values()), out["gate_axes"])
        self.assertEqual(workflow()["inputs"]["mode"]["default"], "")


class ReviewAcceptCase(RunCase):
    """事前審査の受け付け（審査役 1 つ。元 tests/test_blk_plan.py の ScriptCase・ConvergeReviewCase の事前審査の側）"""

    def setUp(self):
        super().setUp()
        self.run_.start(features_off=["review_tree"])

    def prepped(self):
        self.run_.open()
        self.run_.out("review_prep")

    def test_entrance_needs_no_add(self):
        """元 ScriptCase.test_plan_review_entrance_needs_no_add"""
        self.prepped()
        got = self.run_.accept(review(face("entrance-without-no-add", kind="entrance")))
        self.assertFalse(got["ok"])
        self.assertIn("no_add", got["reason"])
        got = self.run_.accept(review(face("entrance-with-no-add", kind="entrance", no_add="柵を足さずに 2 つの入口を 1 つの口にまとめる形")))
        self.assertTrue(got["ok"], got)

    def test_malformed_recommend_rejected(self):
        self.prepped()
        got = self.run_.accept(review(face("regression-recommend", kind="regression", severity="suggest",
                                           recommend={"answer": "continue", "note": "x", "why": "推す理由を書いた"})))
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(planblk.RECOMMEND_REJECT), got["reason"])

    def test_faces_none_and_units_and_keys(self):
        """穴も別案も挙げない返答は faces_none が要る。案に無い単位・重複の key は拒む（元 rules の plan_review_output）"""
        self.prepped()
        for bad, word in (({"faces": [], "shrink": [], "reason": "写し・入口・契約のずれを全部見て穴が無いと判じた理由"}, "faces_none"),
                          (review(face("unknown-unit-key", unit="判定に無い単位の key")), "判定に無い単位の key"),
                          (review(face("duplicated-key"), face("duplicated-key")), "重複")):
            with self.subTest(word=word):
                got = self.run_.accept(bad)
                self.assertFalse(got["ok"])
                self.assertIn(word, got["reason"])

    def test_reply_by_number_is_named(self):
        """元 ScriptCase.test_plan_review_reply_by_number: unit_keys を no の整数で指してよく、受けた返答では単位の名に戻る"""
        self.prepped()
        got = self.run_.accept(review(face("number-pointed-face", unit=2, kind="regression", severity="suggest")))
        self.assertTrue(got["ok"], got)
        saved = json.loads((self.run_.folder / "pass-1" / boardview.REVIEW_FILE).read_text(encoding="utf-8"))
        self.assertEqual(saved["faces"][0]["unit_keys"], [UNIT_CLAMP])

    def test_read_only_tree_changed_rejected(self):
        """元 ScriptCase.test_readonly_tree_changed_rejected・ConvergeReviewCase.test_again_reply_still_checked_by_board_and_tree:
        役の前後で作業ツリーが変われば拒み、往復を控えない。commit して HEAD を動かしても拒む"""
        r = self.run_
        self.prepped()
        (r.repo / "stats.py").write_text("# 変えた\n", encoding="utf-8")
        got = r.accept(review(MEAN_BLOCK))
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(planblk.READONLY_MOVED), got["reason"])
        git(r.repo, "commit", "-qam", "役が commit した")
        got = r.accept(review())
        self.assertFalse(got["ok"])
        self.assertIn("head", got["reason"])
        self.assertEqual(converge.read(r.view())["passes"], [])

    def test_unreadable_reply_goes_back_to_the_role(self):
        self.prepped()
        got = self.run_.out("review_accept", INPUTS_REPLY="{JSON でない")
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("JSON", got["reason"])

    def test_give_up_on_the_third_reject(self):
        """3 回とも拒まれたら done・give_up で輪を抜け、返す節は止めた（stalled）と諦めた訳を返す"""
        r = self.run_
        self.prepped()
        rows = [r.accept(review(face("entrance-without-no-add", kind="entrance"))) for _ in range(3)]
        self.assertEqual([(g["ok"], g["done"], g["give_up"]) for g in rows], [(False, False, False)] * 2 + [(False, True, True)])
        got = r.out("result")
        self.assertEqual((got["pass"], got["stalled"], got["ask_human"]), (False, True, True))
        self.assertTrue(any(q.startswith(boardview.GIVEN_UP_FACES) for q in texts(got)), texts(got))
        saved = json.loads(r.pointed(got["review"]).read_text(encoding="utf-8"))
        self.assertEqual((saved["faces"], saved["shrink"]), ([], []))
        self.assertIn("no_add", saved["reason"])

    def test_reject_reason_pasted_in_the_next_material(self):
        r = self.run_
        self.prepped()
        got = r.accept(review(face("entrance-without-no-add", kind="entrance")))
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(boardview.rolekit.REJECT_HEADING), text[:200])
        self.assertIn(got["reason"].splitlines()[0][:40], text)

    def test_material_carries_the_mainline_inputs(self):
        """材料は役の頭（関所の決め手・狭めない案・既にある物を量ったか・人に回す物）と、写しの指示書の差し込み（修正案・番号つきの
        単位・判定者の見立て・先行例・リポジトリと読む版と観点の正本・人の方針）を持つ。修正案の頭の入れてよい no の節は載らない
        （元 ScriptCase.test_plan_review_head_unchanged・test_prompt_rendered_from_mainline の事前審査の側）"""
        r = self.run_
        r.judgment(precedents=PRECEDENTS)
        pol = r.tmp / "policy.md"
        pol.write_text("# 方針\n- POLICY-MARK 公開の口を減らさない\n", encoding="utf-8")
        r.start(features_off=["review_tree"], policy_md=str(pol), base_rev="HEAD")
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        for want in (gatemarks.HEAD["p2.plan_review"], planblk.REUSE_REVIEW, planblk.HANDOFF_REVIEW, PLAN_MARK, '"no": 1',
                     FRAMING_MARK, ONE_SHOT_MARK, "numpy.clip", f"リポジトリ: {r.repo}", str(LIB / "REVIEW.md"),
                     "## 人の方針", "POLICY-MARK", planmarks.REVIEW_HEAD):
            self.assertIn(want, text)
        self.assertNotIn(planblk.PLAN_SLOTS_HEAD, text)
        self.assertNotIn("{{", text)
        self.assertIn(boardview.DEFAULT_ANSWERS, text.splitlines()[0])

    def test_repo_line_reads_review_rev_apart_from_base(self):
        """P035: 差分の run（入口の差分の根 input.base.rev が読む版 review_rev と違う）では、材料のリポジトリの行が読む版と BASE を
        別の値で描く（元 p2.plan_review.md の雛形の inputs.review_rev と record.base）"""
        r = self.run_
        head = git(r.repo, "rev-parse", "HEAD")
        fork = "f0" * 20
        r.start(features_off=["review_tree"], review_rev=head,
                input={"base": {"rev": fork, "from": "base", "name": "fork", "label": "base fork"}})
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(f"リポジトリ: {r.repo}（読む版: `{head}`）　BASE: `{fork}`", text)

    def test_material_carries_plan_fields(self):
        """元 tests/test_blk_plan.py の test_plan_review_prompt_carries_fields: 項目ごとの works の欄（受け入れテストの id・道・
        書いてよいパス）を JSON で貼り、見る点を頼む"""
        r = self.run_
        test = {"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均がその真ん中の値になる",
                "path": "本物の経路: stats.mean を本物のまま呼ぶ", "red_kind": "assertion", "red_why": "分母が 1 少ない"}
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)],
               field_rows=[{**fields(UNIT_MEAN), "route": "tdd", "tests": [test]}, fields(UNIT_CLAMP)])
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        for want in (planmarks.REVIEW_HEAD, planmarks.REVIEW_ASK, planmarks.FIELDS_ITEM_HEAD.format(n=1), '"route": "tdd"',
                     test["id"], "本物の経路: stats.mean を本物のまま呼ぶ", '"allowed_paths"'):
            self.assertIn(want, text)

    def test_material_lists_deviations(self):
        """元 tests/test_blk_plan.py の test_plan_review_sees_deviations・test_world_deviation_listed_for_review: 欄 structure の外れの
        訳を DEVIATION_HEAD の節に並べ、世界の解の類には依頼の解き方との比べの文を添える"""
        r = self.run_
        r.world({**TP.WORLD_ROW, "versus": {**TP.WORLD_ROW["versus"], "challenge": "WC-8841 定石は分母を要素の数にする"}})
        row_dev = {"row": UNIT_MEAN, "deviation": "既存の関数の中で直すと呼び手の約束が変わるので外す（DEV-MARK-1）"}
        world_dev = {"world": TP.WORLD_ROW["class_id"], "deviation": "依頼の解き方に従い分母を変えない（https://example.org/a）"}
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)],
               field_rows=[{**fields(UNIT_MEAN), "structure": [row_dev, world_dev]}, fields(UNIT_CLAMP)])
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        at = text.index(planmarks.DEVIATION_HEAD)
        self.assertLess(at, text.index(planmarks.REVIEW_HEAD))
        self.assertIn("DEV-MARK-1", text[at:])
        self.assertIn("WC-8841", text[at:])

    def test_excluded_range_named(self):
        """元 ScriptCase.test_excluded_range_named: 判定の隣の並行 PR の外した範囲が在れば、役の頭に名指す"""
        r = self.run_
        r.put("judge/pr-excluded.json", {"excluded": ["docs/"]})
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(planblk.EXCLUDED_HEAD, text)
        self.assertIn(str(r.folder / boardview.EXCLUDED_FILE), text)

    def test_tampered_fields_stop_the_prep(self):
        """元 PlanReviewFrozenFieldsCase.test_tampered_fields_halt_plan_review_prep: 置き場の修正案の欄の控えが凍結の印と食い違えば、
        支度は控えを名指して落ちる（書き換えた欄を審査に見せない）"""
        r = self.run_
        r.open()
        p = r.folder / planmarks.FIELDS_FILE
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["fields"][0]["route"] = "tdd"
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        done = r.script("review_prep")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn(planmarks.FIELDS_FILE, done.stderr)

    def test_policy_change_asks(self):
        """元 ScriptCase.test_policy_change_asks: 固めた後に方針の文書を書き換えると、関所の問いに方針の文書が変わった行が載る"""
        r = self.run_
        pol = r.tmp / "policy.md"
        pol.write_text("# 方針\n- 公開の口を減らさない\n", encoding="utf-8")
        r.start(features_off=["review_tree"], policy_md=str(pol))
        r.open()
        pol.write_text("# 方針\n- 公開の口を減らさない\n- 足した\n", encoding="utf-8")
        got = r.pass_(review())
        self.assertTrue(got["ask_human"])
        self.assertTrue(any("人の方針の文書" in q and "が固定した版から変わった" in q for q in texts(got)), texts(got))

    def test_design_drift_face_needs_quotes_in_both(self):
        """元 ConvergeReviewCase.test_design_drift_face_needs_quotes_in_both"""
        r = self.run_
        r.plan([item(UNIT_MEAN, 1, shrink_first=ROW_TEXT), item(UNIT_CLAMP, 2)])
        r.open()
        DesignCase.designed(self)
        r.out("review_prep")
        drift = lambda why, head: face("design-drift-mean-split", why=head + why)  # noqa: E731
        cases = (("設計と継ぎ目の置き方が違う、という穴だ", "引用が無い"),
                 (f"設計の「上限は入口 2 箇所で掛け」に対し案の「{ROW_TEXT}」は食い違う", "設計の引用の字が 1 つ違う"),
                 (f"設計の「上限は入口 1 箇所で掛け」に対し案の「{ROW_TEXT[:-1]}ぬ」は食い違う", "案の行の引用の字が違う"),
                 ("設計の「上限は入口 1 箇所で掛け」を引いただけで案の行を引かない", "案の行の引用が無い"),
                 (f"案の「{ROW_TEXT}」を引いただけで設計の行を引かない", "設計の引用が無い"))
        for head in (design.DRIFT_HEAD, design.UNPAIRED_HEAD):
            for why, label in cases:
                with self.subTest(head=head, case=label):
                    got = r.accept(review(drift(why, head), design_map=self.full_map()))
                    self.assertFalse(got["ok"], got)
                    self.assertTrue(got["reason"].startswith(planblk.DESIGN_QUOTE_REJECT), got["reason"])
                    self.assertIn("design-drift-mean-split", got["reason"])
        good = f"設計の「上限は入口 1 箇所で掛け」に対し案の「{ROW_TEXT}」は継ぎ目の置き方が違う"
        got = r.accept(review(drift(good, design.UNPAIRED_HEAD), design_map=self.full_map()))
        self.assertTrue(got["ok"], got)

    @staticmethod
    def full_map():
        return [{"item": n, "name": f"helper_{n}", "design_quote": None, "why": "設計に対の無い助け手の名だけを足す"} for n in (1, 2)]

    def test_design_map_must_cover_every_added_name(self):
        """元 ConvergeReviewCase.test_design_map_must_cover_every_added_name: 対応表が add の name を欠く・2 行書く・設計に無い字を
        引く返答は拒み、全部の name を 1 行ずつ持つ返答は受ける。受けた返答に design_map は残らない"""
        r = self.run_
        r.open()
        DesignCase.designed(self)
        r.out("review_prep")
        row = {"item": 1, "name": "helper_1", "design_quote": "上限は入口 1 箇所で掛け", "why": "設計の上限の掛け方に案の助け手が当たる"}
        other = self.full_map()[1]
        for label, bad in (("欠ける", [other]), ("設計に無い字", [{**row, "design_quote": "上限は入口 2 箇所で掛け"}, other]),
                           ("2 行", [row, row, other])):
            with self.subTest(label):
                got = r.accept(review(design_map=bad))
                self.assertFalse(got["ok"], got)
                self.assertTrue(got["reason"].startswith(planblk.DESIGN_QUOTE_REJECT), got["reason"])
                self.assertRegex(got["reason"], r"(add|name) helper_1")
        got = r.accept(review(design_map=[row, other]))
        self.assertTrue(got["ok"], got)
        saved = json.loads((r.folder / "pass-1" / boardview.REVIEW_FILE).read_text(encoding="utf-8"))
        self.assertNotIn(converge.DESIGN_MAP, saved)

    def test_design_quotes_not_checked_without_design(self):
        """元 ConvergeReviewCase.test_design_quotes_not_checked_without_design"""
        self.prepped()
        got = self.run_.accept(review(face("design-drift-no-design", why=design.DRIFT_HEAD + "設計と継ぎ目の置き方が違う、という穴だ")))
        self.assertTrue(got["ok"], got)


class PolicyCase(RunCase):
    """方針の文書は run の始め（線の start）に固めた版を使う（元 works/.shared/core/graphloops/rules/policy_input.py:61 の resolve は盤面の
    on_init で固めた）"""

    def frozen_start(self) -> pathlib.Path:
        """版 A を線の start と同じ口（policy.freeze）で固めた始めの記録を置き、文書を版 B に書き換える"""
        r = self.run_
        pol = r.tmp / "policy.md"
        pol.write_text("# 方針\n- POLICY-A-1111 版 A\n", encoding="utf-8")
        r.start(features_off=["review_tree"], policy_md=str(pol), policy=policy.freeze(r.art, r.repo, str(pol)))
        pol.write_text("# 方針\n- POLICY-B-2222 版 B\n", encoding="utf-8")
        return pol

    def test_policy_frozen_at_run_start(self):
        """P216: 始めの記録が持つ方針の版（sha256 と写し）を固めた版として使い、run の始めから事前審査の最初の差し込みまでに書き換えた
        文書は、最初の差し込みで変化（人の方針の文書が固定した版から変わった）の行になる"""
        self.frozen_start()
        got = self.run_.pass_(review())
        self.assertTrue(got["ask_human"])
        self.assertTrue(any("人の方針の文書" in q and "が固定した版から変わった" in q for q in texts(got)), texts(got))


class ConvergeCase(RunCase):
    """往復の決め（review_accept と result を往復ごとに子のプロセスで続けて回す。元 ConvergeReviewCase の
    test_persisted_review_taken_and_gate_opens_design_item・test_rereview_must_account_for_every_previous_block・
    test_rereview_prompt_carries_previous_blocks_and_answers・test_clean_review_taken_as_today・test_again_does_not_settle_human_gate）"""
    ANSWERS = [{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足して確かめる形に直した"}]

    def setUp(self):
        super().setUp()
        self.run_.start(features_off=["review_tree"])

    def first(self):
        got = self.run_.pass_(review(MEAN_BLOCK))
        self.assertEqual((got["pass"], got["stalled"]), (False, False), got)
        rec = converge.read(self.run_.view())
        self.assertEqual(rec["outcome"], converge.AGAIN)
        self.assertEqual([it["state"] for it in rec["passes"][-1]["items"]], [converge.OPEN, converge.CLOSED])
        self.run_.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す"), item(UNIT_CLAMP, 2)], rnd=2,
                       answers=self.ANSWERS)
        return got

    def test_clean_first_pass(self):
        got = self.run_.pass_(review())
        self.assertEqual((got["pass"], got["stalled"], got["ask_human"]), (True, False, False))
        self.assertEqual(converge.read(self.run_.view())["outcome"], converge.CLEAN)

    def test_first_block_is_not_stalled(self):
        got = self.first()
        self.assertTrue(got["ask_human"], "regression の穴は関所に載る")
        pass1 = self.run_.folder / converge.PASS_DIR / "pass-1"
        self.assertTrue((pass1 / boardview.PROMPT_FILE).is_file())

    def test_same_block_again_stalls_with_a_design_item(self):
        """2 往復目に同じ block → 止めた（PERSISTED）。関所に止まりの行と block の穴が載る（見え方の周はいつも 1 なので控えが捨てられない）"""
        self.first()
        got = self.run_.pass_(review(MEAN_BLOCK))
        self.assertEqual((got["pass"], got["stalled"], got["ask_human"]), (False, True, True), got)
        self.assertEqual(converge.read(self.run_.view())["outcome"], converge.PERSISTED)
        self.assertTrue(any(q.startswith(gatemarks.STUCK_ITEM + "。理由: ") for q in texts(got)), texts(got))
        self.assertTrue(any(q.startswith("事前審査の穴 [regression] " + MEAN_BLOCK["key"]) for q in texts(got)))

    def test_rereview_must_account_for_every_previous_block(self):
        r = self.run_
        self.first()
        r.open()
        r.out("review_prep")
        got = r.accept(review())
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(planblk.RESOLVED_REJECT), got["reason"])
        self.assertIn(MEAN_BLOCK["key"], got["reason"])
        self.assertEqual(len(converge.read(r.view())["passes"]), 1)
        got = r.accept(review(resolved=[MEAN_BLOCK["key"]]))
        self.assertTrue(got["ok"], got)
        got = r.out("result")
        self.assertEqual((got["pass"], got["stalled"]), (True, False))
        doc = converge.read(r.view())
        self.assertEqual((len(doc["passes"]), doc["outcome"], doc["passes"][1]["resolved"]), (2, converge.CLEAN, [MEAN_BLOCK["key"]]))
        self.assertEqual(doc["passes"][1]["answers"], self.ANSWERS)

    def test_pass_row_keeps_each_pass_rejections(self):
        """往復の行に、その往復の計画の周の拒否（plan-fields.json の隣の rejects-plan.json）と事前審査の拒否の行を残す。拒否の控えは
        周・差し込みごとなので、次の往復は 0 から数える（元 planblk.with_converge の converge.stash_rejects）"""
        r = self.run_
        r.put("plan/r1/" + rolekit.rejects_path(pathlib.Path("."), planfile.ROLE).name,
              [{"at": "t1", "reason": "計画の 1 回目の拒否"}])
        r.open()
        r.out("review_prep")
        self.assertFalse(r.accept(review(face("x" * 20, kind="不明")))["ok"])
        self.assertTrue(r.accept(review(MEAN_BLOCK))["ok"])
        r.out("result")
        r.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す"), item(UNIT_CLAMP, 2)], rnd=2,
               answers=self.ANSWERS)
        r.pass_(review(resolved=[MEAN_BLOCK["key"]]))
        rows = [[(x["role"], x["reason"]) for x in p["rejects"]] for p in converge.read(r.view())["passes"]]
        self.assertEqual(rows[0][0], (planfile.ROLE, "計画の 1 回目の拒否"))
        self.assertEqual([role for role, _ in rows[0]], [planfile.ROLE, boardview.REVIEW_NODE])
        self.assertEqual(rows[1], [], "2 往復目は拒否を数え直す")

    def test_answers_written_by_the_plan_block_reach_the_record(self):
        """計画のブロックが 2 周目に書いた block への答え（p2.fix_plan.json の脇の block_answers）が、指し札で渡ると往復の控えの
        2 往復目の answers に入る（2 つのブロックの script を続けて回す。K6）"""
        from tests.workflows import test_plan as plan_block
        r = self.run_
        plan_run = plan_block.Run(self)
        first = plan_run.include()
        self.assertIs(first["ready"], True, first)

        def hand(out):
            shutil.copytree(plan_run.art / "plan", r.art / "plan", dirs_exist_ok=True)
            for key in ("plan", "structure", "ripple"):
                r.inputs[key] = json.dumps({**out[key], "run_id": RUN_ID})

        hand(first)
        got = r.pass_(review(MEAN_BLOCK))
        self.assertEqual(got["pass"], False, got)
        review_rel = got["review"]["path"]
        (plan_run.art / review_rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(r.art / review_rel, plan_run.art / review_rel)
        answers = [{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足した"}]
        second = plan_run.include(
            review=json.dumps({**got["review"], "run_id": plan_block.RUN_ID}),
            writer=plan_block.writer_of({"plan": [plan_block.item(1, 2, approach="空の列を先に弾いて mean の分母を直す案にした")],
                                         "block_answers": answers}))
        self.assertIs(second["ready"], True, second)
        hand(second)
        r.pass_(review(resolved=[MEAN_BLOCK["key"]]))
        self.assertEqual(converge.read(r.view())["passes"][1]["answers"], answers)

    def test_rereview_material_carries_previous_blocks_and_answers(self):
        r = self.run_
        self.first()
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        for w in (converge.REREVIEW_ASK, MEAN_BLOCK["key"], MEAN_BLOCK["where"], MEAN_BLOCK["why"], "修正案の役の答え:",
                  self.ANSWERS[0]["how"]):
            self.assertIn(w, text)

    def test_first_material_has_no_rereview(self):
        r = self.run_
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertNotIn(converge.REREVIEW_ASK, text)

    def test_other_block_not_fewer_is_unsettled(self):
        """2 往復目に別の block が 1 つ残る → 開いた block が 1 → 1 で減らないので止めた（UNSETTLED）"""
        r = self.run_
        keys = ["mean-block-first-000", "mean-block-second-00"]
        for n, key in enumerate(keys, 1):
            if n > 1:
                r.plan([item(UNIT_MEAN, 1, approach=f"mean の直し {n} 回目"), item(UNIT_CLAMP, 2)], rnd=n,
                       answers=[{"key": keys[n - 2], "handled": "fixed", "how": "前の穴を直した形に案を書き直した"}])
            got = r.pass_(review(face(key), resolved=keys[:n - 1]))
        self.assertEqual((got["pass"], got["stalled"]), (False, True), got)
        self.assertEqual(converge.read(r.view())["outcome"], converge.UNSETTLED)

    def decay(self, rnd):
        """1 往復目に 2 項目へ block を 1 つずつ、計画の周 rnd の 2 往復目に項目 1 へ新しい block を 1 つ（開いた block が 2 → 1）"""
        r = self.run_
        got = r.pass_(review(MEAN_BLOCK, CLAMP_BLOCK))
        self.assertEqual((got["pass"], got["stalled"]), (False, False), got)
        r.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す"),
                item(UNIT_CLAMP, 2, approach="clamp の上限の枝で hi を返す")], rnd=rnd,
               answers=[{"key": f["key"], "handled": "fixed", "how": "項目の手順を書き直して確かめた"} for f in (MEAN_BLOCK, CLAMP_BLOCK)])
        return r.pass_(review(face("mean-block-after-fix-0"), resolved=[MEAN_BLOCK["key"], CLAMP_BLOCK["key"]]))

    def test_decreasing_blocks_go_again(self):
        """開いた block が 2 → 1 に減った往復は、止めずに修正案の役へ返す（関所の止まりの行は無い）"""
        got = self.decay(2)
        self.assertEqual((got["pass"], got["stalled"]), (False, False), got)
        doc = converge.read(self.run_.view())
        self.assertEqual([p["outcome"] for p in doc["passes"]], [converge.AGAIN, converge.AGAIN])
        self.assertNotIn("capped", doc["passes"][-1])

    def test_capped_decay_stops_at_loop_max(self):
        """開いた block が 2 → 1 と減り続けていても、線の往復の輪の上限の周（計画の周が入力 round_limit）の往復は止まる: 抜け方は
        again → unsettled で、最後の行に capped が在る。関所の止まりの行の理由は上限に届いた事実を仕組みの異常として言う"""
        got = self.decay(ROUND_LIMIT)
        self.assertEqual((got["pass"], got["stalled"], got["ask_human"]), (False, True, True), got)
        doc = converge.read(self.run_.view())
        self.assertEqual([p["outcome"] for p in doc["passes"]], [converge.AGAIN, converge.UNSETTLED])
        self.assertIs(doc["passes"][-1].get("capped"), True)
        self.assertNotIn("capped", doc["passes"][0])
        stuck = [q for q in texts(got) if q.startswith(gatemarks.STUCK_ITEM + "。理由: ")]
        self.assertEqual(len(stuck), 1, got["questions"])
        self.assertIn(converge.CAP_WHY.split("（")[0].format(n=2), stuck[0])
        self.assertIn("仕組みの異常として止めた", stuck[0])


class TreeCase(RunCase):
    """事前審査を木にする（元 tests/test_blk_plan.py の TreeReviewCase の事前審査の側）。下請けの答えのファイルは試験が書く"""

    def setUp(self):
        super().setUp()
        r = self.run_
        r.judgment(precedents=PRECEDENTS)
        r.ripple(RIPPLE)
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, adds=[{"name": "clamp", "canonical": "stats.clamp の上限の枝"}])])

    def prepped(self) -> str:
        r = self.run_
        self.assertTrue(r.open()["tree"])
        return pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")

    def items_dir(self, k=1) -> pathlib.Path:
        return self.run_.folder / planblk.ITEMS_DIR.format(k=k)

    def write_answers(self, k, rows, syn=None, fetched=True):
        """下請けが書く答えのファイル。fetched なら、その項目の下請けが開く先行例の出典の確かめの行を足す"""
        b = self.run_.view()
        pre = planblk.precedent_plan(b, converge.open_items(b))
        for n, row in rows.items():
            ids = [x["id"] for x in pre.get(n) or [] if x["cached"] is None and x["fetch_by"] == n] if fetched else []
            if ids and "precedents" not in row:
                row = {**row, "precedents": [{"id": i, "found": True, "quote": "出典は在り、単位の問題に当たっている"} for i in ids]}
            p = planblk.answer_file(b, k, n)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
        if syn is not None:
            planblk.synergy_file(b, k).write_text(json.dumps(syn, ensure_ascii=False), encoding="utf-8")

    def surplus_rows(self) -> list:
        path = self.run_.folder / "trace.jsonl"
        return [r for r in (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines())
                if r.get("op") == planblk.SURPLUS_OP]

    def test_aggregator_spawns_item_subagents_and_synergy(self):
        """元 test_review_prompt_spawns_item_subagents_and_synergy・test_aggregator_names_one_subagent_type"""
        text = self.prepped()
        b = self.run_.view()
        self.assertIn(planblk.AGG_HEAD, text)
        self.assertIn(f"subagent_type は全部 {planblk.SUBAGENT_TYPE}", text)
        folder = self.items_dir()
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["item-1.md", "item-2.md", "synergy.md"])
        for name in ("item-1.md", "item-2.md", "synergy.md"):
            self.assertIn(str(folder / name), text)
        for n in (1, 2):
            self.assertIn(str(planblk.answer_file(b, 1, n)), (folder / f"item-{n}.md").read_text(encoding="utf-8"))
            self.assertFalse(str(planblk.answer_file(b, 1, n)).startswith(str(self.run_.repo)), "作業ツリーの外")
        self.assertIn(str(planblk.synergy_file(b, 1)), (folder / "synergy.md").read_text(encoding="utf-8"))
        self.assertIn("test_clamp_above_range", (folder / "item-2.md").read_text(encoding="utf-8"))
        self.assertIn("stats.py: 項目 1, 2", (folder / "synergy.md").read_text(encoding="utf-8"))

    def test_brief_carries_only_its_item_inline(self):
        """元 test_brief_carries_only_its_item_inline: 下請けのファイルは審査の決まり（指示書の『リポジトリ: 』の行から）・独立設計の節・
        自分の項目だけを持ち、項目の節より前は全部の項目で同じバイト"""
        self.prepped()
        one, two = ((self.items_dir() / f"item-{n}.md").read_text(encoding="utf-8") for n in (1, 2))
        for part in ("## 見ること", "## 返し方", planblk.DESIGN_HEAD, f"リポジトリ: {self.run_.repo}"):
            self.assertIn(part, one)
        self.assertIn("分母が 1 少ない", one)
        self.assertNotIn("上限で lo を返す", one)
        self.assertNotIn("test_clamp_above_range", one)
        head1, _, item1 = one.partition(planblk.ITEM_HEAD.format(n=1))
        head2, _, _ = two.partition(planblk.ITEM_HEAD.format(n=2))
        self.assertTrue(item1)
        self.assertEqual(head1, head2)

    def test_machine_merges_item_answers_into_review(self):
        """元 test_machine_merges_item_answers_into_review"""
        r = self.run_
        self.prepped()
        self.write_answers(1, {1: answer(1), 2: answer(2)}, syn=synergy())
        got = r.accept(summary({1: [], 2: []}))
        self.assertTrue(got["ok"], got)
        rec = converge.read(r.view())
        self.assertEqual(rec["outcome"], converge.CLEAN)
        items = rec["passes"][-1]["items"]
        self.assertEqual([it["state"] for it in items], [converge.CLOSED, converge.CLOSED])
        self.assertEqual([h["id"] for h in items[1]["hits"]], ["h1"])
        self.assertIn("item-2.json", rec["passes"][-1]["files"])
        saved = json.loads((r.folder / "pass-1" / boardview.REVIEW_FILE).read_text(encoding="utf-8"))
        self.assertEqual(saved["faces"], [])
        self.assertNotIn("items", saved)
        self.assertTrue(r.out("result")["pass"])

    def test_invalid_answer_goes_back_to_its_item_only(self):
        """元 test_invalid_answer_goes_back_to_its_item_only"""
        r = self.run_
        self.prepped()
        self.write_answers(1, {1: answer(1), 2: answer(2, why="同上")}, syn=synergy())
        got = r.accept(summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(planblk.TREE_REJECT), got["reason"])
        self.assertIn("項目 2", got["reason"])
        self.assertNotIn("項目 1（", got["reason"])
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        redo = text[text.index(planblk.REDO_HEAD):]
        self.assertIn(str(self.items_dir() / "item-2.md"), redo)
        self.assertNotIn(str(self.items_dir() / "item-1.md"), redo)
        brief = (self.items_dir() / "item-2.md").read_text(encoding="utf-8")
        errs = json.loads(brief[brief.index(planblk.ERRORS_HEAD):].split("```json\n", 1)[1].split("\n```", 1)[0])
        self.assertEqual(errs["item"], 2)
        self.write_answers(1, {2: answer(2)})
        self.assertTrue(r.accept(summary({1: [], 2: []}))["ok"])

    def test_item_design_quotes_reopen_only_that_item(self):
        """元 test_item_design_quotes_reopen_only_that_item"""
        r = self.run_
        r.open()
        DesignCase.designed(self)
        self.prepped()
        bad_quote = "上限は入口 2 箇所で掛け"
        drift = face("item1-design-drift", why=design.DRIFT_HEAD + f"設計の「{bad_quote}」に対し案の「{PLAN_MARK} 項目 1 の直し」は食い違う")
        one = {**answer(1, faces=[drift]), converge.DESIGN_MAP: [
            {"item": 1, "name": "helper_1", "design_quote": None, "why": "設計に対の無い助け手の名だけを足す"}]}
        two = {**answer(2), converge.DESIGN_MAP: [
            {"item": 2, "name": "clamp", "design_quote": None, "why": "設計は上限の枝の関数を足さないので対が無い"}]}
        self.write_answers(1, {1: one, 2: two})
        got = r.accept(summary({1: [drift["key"]], 2: []}))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(planblk.TREE_REJECT), got["reason"])
        self.assertIn(bad_quote, got["reason"])
        self.assertNotIn("項目 2（", got["reason"])
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        redo = text[text.index(planblk.REDO_HEAD):]
        self.assertIn(str(self.items_dir() / "item-1.md"), redo)
        self.assertNotIn(str(self.items_dir() / "item-2.md"), redo)
        self.assertIn(str(self.items_dir() / "item-2.md"), text[text.index(planblk.DONE_HEAD):text.index(planblk.REDO_HEAD)])
        brief = (self.items_dir() / "item-1.md").read_text(encoding="utf-8")
        self.assertIn(bad_quote, brief[brief.index(planblk.ERRORS_HEAD):])

    def test_synergy_design_quotes_checked_against_named_items(self):
        """元 test_synergy_design_quotes_checked_against_named_items"""
        r = self.run_
        r.open()
        DesignCase.designed(self)
        self.prepped()
        maps = {1: {**answer(1), converge.DESIGN_MAP: [{"item": 1, "name": "helper_1", "design_quote": None,
                                                         "why": "設計に対の無い助け手の名だけを足す"}]},
                2: {**answer(2), converge.DESIGN_MAP: [{"item": 2, "name": "clamp", "design_quote": None,
                                                         "why": "設計は上限の枝の関数を足さないので対が無い"}]}}
        self.write_answers(1, maps)

        def syn_face(quote):
            return {**face("synergy-design-drift", unit=UNIT_MEAN), "unit_keys": [UNIT_MEAN, UNIT_CLAMP],
                    "why": design.DRIFT_HEAD + f"設計の「{quote}」に対し案の「{PLAN_MARK} 項目 1 の直し」は食い違う"}
        self.write_answers(1, {}, syn=synergy([syn_face("上限は入口 2 箇所で掛け")]))
        got = r.accept(summary({1: [], 2: []}))
        self.assertFalse(got["ok"], got)
        self.assertIn("相乗りの審査", got["reason"])
        self.assertIn("上限は入口 2 箇所で掛け", got["reason"])
        self.write_answers(1, {}, syn=synergy([syn_face("上限は入口 1 箇所で掛け")]))
        self.assertTrue(r.accept(summary({1: [], 2: []}))["ok"])

    def test_aggregator_reply_is_summary_only(self):
        """元 test_aggregator_reply_is_summary_only"""
        r = self.run_
        self.prepped()
        self.write_answers(1, {1: answer(1, faces=[MEAN_BLOCK]), 2: answer(2)})
        got = r.accept({**summary({1: [MEAN_BLOCK["key"]], 2: []}), "faces": [MEAN_BLOCK]})
        self.assertFalse(got["ok"])
        self.assertIn("faces", got["reason"])
        got = r.accept(summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn("項目 1", got["reason"])
        got = r.accept(summary({1: [MEAN_BLOCK["key"]], 2: []}))
        self.assertTrue(got["ok"], got)
        self.assertEqual(converge.read(r.view())["outcome"], converge.AGAIN)

    def test_all_clean_pass_needs_synergy(self):
        """元 test_all_clean_pass_needs_synergy"""
        r = self.run_
        self.prepped()
        self.write_answers(1, {1: answer(1), 2: answer(2)})
        got = r.accept(summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn("相乗り", got["reason"])
        self.write_answers(1, {}, syn=synergy())
        self.assertTrue(r.accept(summary({1: [], 2: []}))["ok"])
        self.assertEqual(converge.read(r.view())["outcome"], converge.CLEAN)

    def test_item_answer_cannot_name_other_items(self):
        """元 test_item_answer_cannot_name_other_items"""
        r = self.run_
        self.prepped()
        other = face("item1-names-clamp", unit=UNIT_CLAMP)
        self.write_answers(1, {1: answer(1, faces=[other]), 2: answer(2)})
        got = r.accept(summary({1: [other["key"]], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn("項目 1", got["reason"])

    def test_second_pass_reviews_diff_and_carries_answers_and_notes(self):
        """元 test_second_pass_reviews_diff_and_carries_answers_and_notes（直しの役の側は plan のブロック）: 2 往復目の下請けは差分と
        前の block の行き先だけを見て、前の往復で答えた当たりは機械が引き継ぎ、suggest の穴は最後の返答に残る"""
        r = self.run_
        r.start(features_on=["review_tree"])
        self.prepped()
        note = face("item1-mean-docstring-note", severity="suggest",
                    why="mean の docstring が分母を言っていないので、直した後に読み手が分母を取り違えうる")
        self.write_answers(1, {1: answer(1, faces=[note]), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.assertTrue(r.accept(summary({1: [], 2: [CLAMP_BLOCK["key"]]}))["ok"])
        self.assertEqual(r.out("result")["pass"], False)
        rec = converge.read(r.view())
        self.assertEqual([it["state"] for it in rec["passes"][-1]["items"]], [converge.CLOSED, converge.OPEN])
        two = item(UNIT_CLAMP, 2, adds=[{"name": "clamp", "canonical": "stats.clamp の上限の枝"}],
                   approach="clamp の上限の枝で hi を返し、上限ちょうどの値はそのまま返す（定義どおり）")
        r.plan([item(UNIT_MEAN, 1), two], rnd=2,
               answers=[{"key": CLAMP_BLOCK["key"], "handled": "fixed", "how": "上限の枝を hi に直し、境の値の扱いを書いた"}])
        r.open()
        r.out("review_prep")
        brief = (self.items_dir(2) / "item-2.md").read_text(encoding="utf-8")
        diff = brief[brief.index(planblk.DIFF_HEAD):]
        self.assertIn("上限ちょうどの値はそのまま返す", diff)
        self.assertIn(planblk.DIFF_ASK, brief)
        self.assertNotIn(planblk.DIFF_FULL_ASK, brief)
        self.assertIn(CLAMP_BLOCK["key"], brief)
        self.assertIn(planblk.CARRIED_HEAD, brief)
        self.assertFalse((self.items_dir(2) / "item-1.md").exists(), "閉じた項目は審査しない")
        self.write_answers(2, {2: {**answer(2, resolved=[CLAMP_BLOCK["key"]]), "hits": []}}, syn=synergy())
        got = r.accept(summary({2: []}))
        self.assertTrue(got["ok"], got)
        rec = converge.read(r.view())
        self.assertEqual(rec["outcome"], converge.CLEAN)
        hits = rec["passes"][-1]["items"][1]["hits"]
        self.assertEqual([(h["id"], h.get("carried")) for h in hits], [("h1", 1)])
        saved = json.loads((r.folder / "pass-2" / boardview.REVIEW_FILE).read_text(encoding="utf-8"))
        self.assertIn(note["key"], [f["key"] for f in saved["faces"]])

    def second_pass_brief(self, first=None, edit=None, edit_fields=None) -> str:
        """2 項目の案（first。既定は setUp の案）の 1 往復目は項目 2 だけ block。項目 2 の行を edit が、項目 2 の works の欄を
        edit_fields が直した後の 2 往復目の項目 2 の下請けのファイル"""
        r = self.run_
        r.start(features_on=["review_tree"])
        rows = first or [item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, adds=[{"name": "clamp", "canonical": "stats.clamp の上限の枝"}])]
        r.plan(rows)
        self.prepped()
        self.write_answers(1, {1: answer(1), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.assertTrue(r.accept(summary({1: [], 2: [CLAMP_BLOCK["key"]]}))["ok"])
        r.out("result")
        fixed = copy.deepcopy(rows)
        field_rows = [fields(x["unit_keys"][0]) for x in fixed]
        if edit is not None:
            edit(fixed[1])
        if edit_fields is not None:
            edit_fields(field_rows[1])
        r.plan(fixed, rnd=2, field_rows=field_rows,
               answers=[{"key": CLAMP_BLOCK["key"], "handled": "fixed", "how": "上限の枝を hi に直し、境の値の扱いを書いた"}])
        r.open()
        r.out("review_prep")
        return (self.items_dir(2) / "item-2.md").read_text(encoding="utf-8")

    def test_tree_item_contract_change_is_reviewed_whole(self):
        """元 test_tree_item_contract_change_is_reviewed_whole・test_contract_field_change_is_reviewed_whole: 2 往復目、約束の欄
        （allowed_paths）に 1 行足しただけの開いた項目の下請けのファイルは、差分に絞らず全部を審査せよと頼み、変わった欄の名を言う。
        字の割合は小さくても、直しが触れる物が変わるので差分の外の読み直しが要る"""
        brief = self.second_pass_brief(edit_fields=lambda row: row["allowed_paths"].append("README.md"))
        self.assertIn("約束の欄（allowed_paths）が変わった。" + planblk.DIFF_FULL_ASK, brief)
        self.assertIn("README.md", brief[brief.index(planblk.DIFF_HEAD):])
        self.assertNotIn(planblk.DIFF_ASK, brief)

    def test_large_item_change_is_reviewed_whole(self):
        """元 test_large_item_change_is_reviewed_whole: 開いた項目の approach を丸ごと書き直し、前の行の字の DIFF_FULL_SHARE を
        超えて変えた直しの後は、差分に絞らず全部を審査せよと頼む（約束の欄は変わっていないので欄の名は言わない）"""
        big = "".join(f"手順 {i}: {c} の入口で空の列を弾き、{c} の出口で分母を {i} 倍に直さず len(xs) に揃える。"
                      for i, c in enumerate("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥", 1))
        brief = self.second_pass_brief(edit=lambda row: row.update(approach=big))
        self.assertIn(f"{planblk.DIFF_HEAD}\n\n{planblk.DIFF_FULL_ASK}", brief)
        self.assertNotIn(planblk.DIFF_ASK, brief)
        self.assertNotIn("約束の欄（", brief)

    def test_narrows_gate_marks_only_change_stays_diff(self):
        """元 test_narrows_gate_marks_only_change_stays_diff: narrows の行の関所の決め手の欄（world・recommend）の長い文を丸ごと
        書き直しただけの直しは、約束の欄の変更にも大きい変更にも数えず差分のまま"""
        narrow = {**TP.NARROW, "no_narrow": "空の列で例外を投げる今の動きを残すと直したい呼び手が成り立たない",
                  "decided_by": "", "undecided_because": "", "fences": [],
                  "world": "Python 公式の statistics.mean は空の列で例外を投げる",
                  "recommend": {"answer": "continue", "why": "空の列の例外は前から同じで、能力は減らない", "note": "今の動きのまま通す"}}
        first = [item(UNIT_MEAN, 1),
                 item(UNIT_CLAMP, 2, adds=[{"name": "clamp", "canonical": "stats.clamp の上限の枝"}], narrows=[narrow])]
        long_world = "".join(f"事例 {i}: {c} の標準の平均は空の列で StatisticsError を投げ、呼び手が捕まえて 0 を返す慣習が広い。"
                             for i, c in enumerate("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥", 1))
        long_why = "".join(f"理由 {i}: {c} の呼び手は例外の型を前から同じに受けるので、通しても能力は減らず、利用者の経路も変わらない。"
                           for i, c in enumerate("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥", 1))

        def reword(row):
            row["narrows"][0]["world"] = long_world
            row["narrows"][0]["recommend"] = {"answer": "continue", "why": long_why, "note": "今の動きのまま通してよい"}

        brief = self.second_pass_brief(first=first, edit=reword)
        self.assertIn(planblk.DIFF_ASK, brief)
        self.assertNotIn(planblk.DIFF_FULL_ASK, brief)

    def test_precedent_sources_are_fetched_once_per_run(self):
        """元 test_precedent_sources_are_fetched_once_per_run"""
        r = self.run_
        r.start(features_on=["review_tree"])
        self.prepped()
        one, two = ((self.items_dir() / f"item-{n}.md").read_text(encoding="utf-8") for n in (1, 2))
        self.assertIn("statistics.mean", one)
        self.assertNotIn("numpy.clip", one)
        self.assertEqual((len(planblk.fetch_ids(one)), len(planblk.fetch_ids(two))), (1, 1))
        self.write_answers(1, {1: answer(1), 2: answer(2, faces=[CLAMP_BLOCK])}, fetched=False)
        got = r.accept(summary({1: [], 2: [CLAMP_BLOCK["key"]]}))
        self.assertFalse(got["ok"])
        self.assertIn("precedents", got["reason"])
        self.write_answers(1, {1: answer(1), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.assertTrue(r.accept(summary({1: [], 2: [CLAMP_BLOCK["key"]]}))["ok"])
        cache = json.loads((r.folder / planblk.PRECEDENT_CACHE).read_text(encoding="utf-8"))
        self.assertEqual(len(cache), 2)
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach="clamp の上限の枝で hi を返す（直した）",
                                          adds=[{"name": "clamp", "canonical": "stats.clamp の上限の枝"}])], rnd=2,
               answers=[{"key": CLAMP_BLOCK["key"], "handled": "fixed", "how": "上限の枝を hi に直し、境の値の扱いを書いた"}])
        r.open()
        r.out("review_prep")
        brief = (self.items_dir(2) / "item-2.md").read_text(encoding="utf-8")
        self.assertIn("numpy.clip", brief)
        self.assertIn(planblk.PRECEDENT_CACHED, brief)
        self.assertEqual(planblk.fetch_ids(brief), [])

    def test_surplus_rows_dropped(self):
        """元 test_surplus_precedent_row_dropped・test_surplus_hit_dropped: 余りの行は拒まずに trace に残して捨てる"""
        r = self.run_
        self.prepped()
        b = r.view()
        pre = planblk.precedent_plan(b, converge.open_items(b))
        other = next(x["id"] for x in pre[1] if x["fetch_by"] == 1)
        own = [x["id"] for x in pre[2] if x["fetch_by"] == 2]
        stray_pre = {"id": other, "found": False, "quote": "余りの確かめ（この項目の下請けが開く出典でない）"}
        stray_hit = {"id": "H-not-in-ripple", "answer": "no_effect", "why": NO_EFFECT}
        mine = [{"id": i, "found": True, "quote": "出典は在り、単位の問題に当たっている"} for i in own]
        two = answer(2)
        self.write_answers(1, {1: answer(1), 2: {**two, "hits": two["hits"] + [stray_hit], "precedents": mine + [stray_pre]}},
                           syn=synergy())
        self.assertTrue(r.accept(summary({1: [], 2: []}))["ok"])
        rows = json.dumps([x for x in self.surplus_rows() if x.get("item") == 2], ensure_ascii=False)
        self.assertIn(other, rows)
        self.assertIn(stray_hit["id"], rows)
        cache = json.loads((r.folder / planblk.PRECEDENT_CACHE).read_text(encoding="utf-8"))
        self.assertNotIn(stray_pre["quote"], json.dumps(cache, ensure_ascii=False))
        hits = converge.read(r.view())["passes"][-1]["items"][1]["hits"]
        self.assertEqual([h["id"] for h in hits], ["h1"])

    def test_missing_precedent_row_refused_without_surplus_lines(self):
        """元 test_missing_precedent_row_refused_without_surplus_lines"""
        r = self.run_
        self.prepped()
        b = r.view()
        pre = planblk.precedent_plan(b, converge.open_items(b))
        other = next(x["id"] for x in pre[1] if x["fetch_by"] == 1)
        own = [x["id"] for x in pre[2] if x["fetch_by"] == 2]
        self.write_answers(1, {1: answer(1)})
        stray = {"id": other, "found": False, "quote": "余りの確かめ（この項目の下請けが開く出典でない）"}
        self.write_answers(1, {2: {**answer(2), "precedents": [stray]}}, syn=synergy(), fetched=False)
        got = r.accept(summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn(f"先行例の出典 {own[0]} の確かめの行が無い", got["reason"])
        self.assertNotIn("開く出典でない", got["reason"])

    def test_item_and_synergy_schema_take_origins(self):
        """項目の下請けの答えの型と相乗りの下請けの答えの型は、任意の欄 origins（converge.ORIGIN_SCHEMA）を持つ"""
        self.prepped()
        b = self.run_.view()
        for schema in (planblk.item_schema(b), planblk.synergy_schema(b)):
            self.assertEqual(schema["properties"][converge.ORIGINS], converge.ORIGIN_SCHEMA)
            self.assertNotIn(converge.ORIGINS, schema["required"])

    def test_origin_ask_only_where_writers_are(self):
        """出自の頼みは書き手の居る層にだけ置く: 1 往復目はどのファイルにも頼みが無く、2 往復目の束ね役の指示書は ORIGIN_ASK を
        持たない。項目の下請けのファイルは REREVIEW_ASK と ORIGIN_ASK を、相乗りのファイルは ORIGIN_ASK を持つ。
        下請けの答えの origins は往復の行に照らして入り、束ね役の返答の origins は拒む"""
        r = self.run_
        main = self.prepped()
        for text in (main, *(p.read_text(encoding="utf-8") for p in sorted(self.items_dir().glob("*.md")))):
            self.assertNotIn(converge.ORIGIN_ASK, text)
            self.assertNotIn(converge.REREVIEW_ASK, text)
        self.write_answers(1, {1: answer(1, faces=[MEAN_BLOCK]), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.assertTrue(r.accept(summary({1: [MEAN_BLOCK["key"]], 2: [CLAMP_BLOCK["key"]]}))["ok"])
        r.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾き、分母を len(xs) に直す"),
                item(UNIT_CLAMP, 2, approach="clamp の上限の枝で hi を返す", adds=[{"name": "clamp", "canonical": "stats.clamp の上限の枝"}])],
               rnd=2, answers=[{"key": f["key"], "handled": "fixed", "how": "項目の手順を書き直して確かめた"} for f in (MEAN_BLOCK, CLAMP_BLOCK)])
        self.assertTrue(r.open()["tree"])
        main = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertNotIn(converge.ORIGIN_ASK, main, "束ね役の指示書に書き手の居ない頼みを貼らない")
        for name in ("item-1.md", "item-2.md"):
            text = (self.items_dir(2) / name).read_text(encoding="utf-8")
            self.assertIn(converge.REREVIEW_ASK, text, name)
            self.assertIn(converge.ORIGIN_ASK, text, name)
        self.assertIn(converge.ORIGIN_ASK, (self.items_dir(2) / "synergy.md").read_text(encoding="utf-8"))
        again = face("item1-mean-new-hole-0")
        claim = [{"key": again["key"], "origin": converge.ORIGIN_INTRODUCED}]
        self.write_answers(2, {1: {**answer(1, faces=[again], resolved=[MEAN_BLOCK["key"]]), converge.ORIGINS: claim},
                               2: answer(2, resolved=[CLAMP_BLOCK["key"]])})
        got = r.accept({**summary({1: [again["key"]], 2: []}), converge.ORIGINS: claim})
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(planblk.TREE_REJECT), got["reason"])
        self.assertIn("origins", got["reason"])
        self.assertEqual(len(converge.read(r.view())["passes"]), 1)
        self.assertTrue(r.accept(summary({1: [again["key"]], 2: []}))["ok"])
        row = converge.read(r.view())["passes"][-1]
        self.assertEqual((row["outcome"], row["origins"], row["origins_claimed"]),
                         (converge.AGAIN, {again["key"]: converge.ORIGIN_INTRODUCED}, []))   # 開いた block は 2 → 1 に減る

    def test_review_tree_off_second_pass_takes_checked_origins(self):
        """審査役 1 つ（木にしない）の 2 往復目: 材料に出自の頼み ORIGIN_ASK が在る（1 往復目には無い）。返答の origins は役の型
        （converge.ORIGIN_SCHEMA）で確かめ、型の外れは出し直させて往復も記録しない。正しい申告は往復の行に照らして入る"""
        r = self.run_
        r.start(features_off=["review_tree"])
        self.assertFalse(r.open()["tree"])
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertNotIn(converge.ORIGIN_ASK, text)
        self.assertTrue(r.accept(review(MEAN_BLOCK))["ok"])
        r.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す"), item(UNIT_CLAMP, 2)], rnd=2,
               answers=[{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足した"}])
        self.assertFalse(r.open()["tree"])
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(converge.REREVIEW_ASK, text)
        self.assertIn(converge.ORIGIN_ASK, text)
        new = face("mean-boundary-value-0")

        def send(claim):
            return r.accept(review(new, resolved=[MEAN_BLOCK["key"]], origins=claim))

        for claim in ([{"key": new["key"], "origin": "guessed"}], [{"key": [new["key"]], "origin": converge.ORIGIN_MISSED}]):
            with self.subTest(claim=claim):
                got = send(claim)
                self.assertFalse(got["ok"], got)
                self.assertIn(converge.ORIGINS, got["reason"])
                self.assertEqual(len(converge.read(r.view())["passes"]), 1)
        got = send([{"key": new["key"], "origin": converge.ORIGIN_REPHRASED, "of": MEAN_BLOCK["key"]}])
        self.assertTrue(got["ok"], got)
        row = converge.read(r.view())["passes"][-1]
        self.assertEqual((row["origins"], row["origins_claimed"]), ({new["key"]: converge.ORIGIN_REPHRASED}, []))

    def test_review_tree_off_is_one_reviewer(self):
        """元 test_review_tree_off_is_one_reviewer: 始めの記録の features_off の review_tree なら 2 項目でも審査役 1 つ"""
        r = self.run_
        r.start(features_off=["review_tree"])
        self.assertFalse(r.open()["tree"])
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertNotIn(planblk.AGG_HEAD, text)
        self.assertFalse(self.items_dir().exists())
        self.assertTrue(r.accept(review())["ok"])

    def test_review_tree_on_one_item_is_tree(self):
        r = self.run_
        r.start(features_on=["review_tree"])
        r.plan([item(UNIT_MEAN, 1)])
        self.assertTrue(r.open()["tree"])

    def test_review_tree_auto_one_item_plan_is_one_reviewer(self):
        """元 test_review_tree_auto_one_item_plan_is_one_reviewer・test_single_item_plan_needs_no_synergy"""
        r = self.run_
        r.plan([item(UNIT_MEAN, 1)])
        r.ripple({"items": [], "overlaps": []})
        self.assertFalse(r.open()["tree"])
        r.out("review_prep")
        self.assertTrue(r.accept(review())["ok"])

    def test_review_tree_auto_counts_open_items_per_pass(self):
        """元 test_review_tree_auto_counts_open_items_per_pass: 2 項目の 1 往復目は木、項目 1 だけが開いた 2 往復目は審査役 1 つ"""
        r = self.run_
        self.prepped()
        self.write_answers(1, {1: answer(1, faces=[MEAN_BLOCK]), 2: answer(2)})
        self.assertTrue(r.accept(summary({1: [MEAN_BLOCK["key"]], 2: []}))["ok"])
        self.assertEqual(converge.open_items(r.view()), [1])
        r.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾き、分母を len(xs) に直す"),
                item(UNIT_CLAMP, 2, adds=[{"name": "clamp", "canonical": "stats.clamp の上限の枝"}])], rnd=2,
               answers=[{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足した"}])
        self.assertFalse(r.open()["tree"])
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertNotIn(planblk.AGG_HEAD, text)
        self.assertFalse(self.items_dir(2).exists())
        self.assertTrue(r.accept(review(resolved=[MEAN_BLOCK["key"]]))["ok"])
        self.assertEqual(converge.read(r.view())["outcome"], converge.CLEAN)


RECORDER = ROOT / "bin" / "_lib" / "record-read.py"


class ReadsCase(RunCase):
    """読んだ証拠（review-reads の節。lib/reads・boardview.collect_reads）: 隔離した設定のフック（bin/_lib/record-read.py を実物で
    起こす）が作業の場ごとに書いた記録から、事前審査の役が材料を読んだか・束ね役が下請けを何人起こしたか・web を引いたかを集める
    （元 planblk.collect_reads。元は実行基盤の出来事 tool_called からも引いた）"""

    def setUp(self):
        super().setUp()
        self.config = self.run_.tmp / "claude"
        (self.config / reads.ROOT).mkdir(parents=True)

    def hook(self, tool, session="s-1", **tool_input):
        event = {"session_id": session, "tool_name": tool, "tool_input": tool_input, "tool_use_id": f"toolu_{tool}",
                 "cwd": str(self.run_.repo), "hook_event_name": "PostToolUse"}
        done = subprocess.run([sys.executable, str(RECORDER), str(self.config / reads.ROOT)], input=json.dumps(event),
                              text=True, encoding="utf-8", capture_output=True, cwd=str(self.run_.repo),
                              env=hermetic.child_env(PYTHONDONTWRITEBYTECODE="1", CLAUDE_PROJECT_DIR=str(self.run_.repo)))
        self.assertEqual(done.returncode, 0, done.stderr)

    def collect(self):
        got = self.run_.out("review_reads", CLAUDE_CONFIG_DIR=str(self.config))
        self.assertTrue(got["ok"], got)
        return got, json.loads(pathlib.Path(got["index_file"]).read_text(encoding="utf-8"))

    def test_reads_collected_from_the_hook_records(self):
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        prompt = r.out("review_prep")["prompt_file"]
        self.hook("Read", file_path=prompt)
        got, index = self.collect()
        self.assertEqual(pathlib.Path(got["index_file"]).name, reads.index_name("plan-review"))
        self.assertEqual(index["r2-design"], None, "道具を持たない役は名指して null")
        doc = json.loads(pathlib.Path(index["plan-review"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["rows"], [{"path": prompt, "hook": "read"}])
        self.assertEqual((doc["sources"]["hook"], got["missing"]), ("recorded", []))

    def test_unread_material_is_missing_and_no_root_is_named(self):
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        prompt = r.out("review_prep")["prompt_file"]
        self.hook("Read", file_path=str(r.repo / "stats.py"))
        got, _ = self.collect()
        self.assertEqual(got["missing"], [prompt])
        got = r.out("review_reads", CLAUDE_CONFIG_DIR=str(r.tmp / "no-config"))
        doc = json.loads(pathlib.Path(json.loads(pathlib.Path(got["index_file"]).read_text(encoding="utf-8"))["plan-review"])
                         .read_text(encoding="utf-8"))
        self.assertEqual((doc["sources"]["hook"], got["missing"]), ("none", []))
        self.assertEqual(doc["sources"]["why"], reads.NO_ROOT)

    def test_agent_launches_counted_against_item_files(self):
        """束ね役の Agent の起動の数と subagent_type を、この差し込みで書いた下請けのファイルの数と並べて trace に残す（拒まない）"""
        r = self.run_
        r.judgment(precedents=PRECEDENTS)
        r.ripple(RIPPLE)
        self.assertTrue(r.open()["tree"])
        self.hook("Read", file_path=r.out("review_prep")["prompt_file"])
        for _ in range(3):
            self.hook("Agent", subagent_type=planblk.SUBAGENT_TYPE, prompt="項目を見よ")
        self.collect()
        rows = [json.loads(x) for x in (r.folder / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        got = [{k: x[k] for k in ("launched", "types", "item_files", "synergy_files")} for x in rows if x["op"] == planblk.AGENT_OP]
        self.assertEqual(got, [{"launched": 3, "types": {planblk.SUBAGENT_TYPE: 3}, "item_files": 2, "synergy_files": 1}])

    def test_web_calls_recorded(self):
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        self.hook("Read", file_path=r.out("review_prep")["prompt_file"])
        self.hook("WebFetch", url="https://docs.python.org/3/library/statistics.html", prompt="空の列")
        self.hook("WebSearch", query="statistics.mean empty")
        _, index = self.collect()
        doc = json.loads(pathlib.Path(index["plan-review"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["web"], {"fetches": ["https://docs.python.org/3/library/statistics.html"],
                                      "searches": ["statistics.mean empty"]})

    def test_records_before_the_pass_opened_are_not_counted(self):
        """K14: 記録は差し込みを開いた時刻から後の行で切る。前の差し込みの読みと下請けの起動を、今の差し込みの物に数えない"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        prompt = r.out("review_prep")["prompt_file"]
        self.hook("Read", file_path=prompt)
        self.hook("Agent", subagent_type=planblk.SUBAGENT_TYPE, prompt="項目を見よ")
        log = reads.reads_path(self.config / reads.ROOT, r.repo)
        rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
        log.write_text("".join(json.dumps({**x, "ts": "2000-01-01T00:00:00"}) + "\n" for x in rows), encoding="utf-8")
        got, _ = self.collect()
        self.assertEqual(got["missing"], [prompt])
        trace = [json.loads(x) for x in (r.folder / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([x["launched"] for x in trace if x["op"] == planblk.AGENT_OP], [0])

    def test_other_sessions_in_the_same_checkout_are_not_the_roles(self):
        """同じ作業の場で並んで走る別の役（線の判定のやり直し）の web と下請けを、事前審査の役の物に数えない"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        self.hook("Read", file_path=r.out("review_prep")["prompt_file"])
        self.hook("WebFetch", session="S-judge", url="https://judge.example/")
        self.hook("Agent", session="S-judge", subagent_type="general-purpose")
        _, index = self.collect()
        doc = json.loads(pathlib.Path(index["plan-review"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["web"], {"fetches": [], "searches": []})
        trace = [json.loads(x) for x in (r.folder / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([x["launched"] for x in trace if x["op"] == planblk.AGENT_OP], [0])

    def test_session_that_read_only_the_policy_is_not_the_roles(self):
        """役の session を決めるのは役だけに渡した材料 prompt.md。方針の写しは別の役も読むので、それだけを読んだ session の
        読みと web を事前審査の役の物に数えない"""
        r = self.run_
        pol = r.tmp / "policy.md"
        pol.write_text("# 方針\n", encoding="utf-8")
        r.start(features_off=["review_tree"], policy_md=str(pol), policy=policy.freeze(r.tmp / "frozen", r.repo, str(pol)))
        r.open()
        copy = boardview.read_open(r.folder)["policy_copy"]
        self.assertTrue(copy)
        self.hook("Read", file_path=r.out("review_prep")["prompt_file"])
        self.hook("Read", session="S-judge", file_path=copy)
        self.hook("WebFetch", session="S-judge", url="https://judge.example/")
        got, index = self.collect()
        self.assertEqual(got["missing"], [copy])
        doc = json.loads(pathlib.Path(index["plan-review"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["web"], {"fetches": [], "searches": []})

    def test_replan_reads_are_named_apart(self):
        """案の直しの差し込みの読んだ証拠は reads-replan-<役>.json と reads-replan-block.json（1 回目の物と名を分ける）"""
        r = self.run_
        r.start(features_off=["review_tree"])
        self.assertTrue(r.pass_(review())["pass"])
        first, _ = self.collect()
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach=f"{PLAN_MARK} 直した項目 2")], rnd=2)
        r.inputs.update(ruling=json.dumps(["2"]), conflicts=r.put("fix/conflicts.json", {"items": [ReplanCase.CONFLICT]}))
        r.open()
        r.out("review_prep")
        got, index = self.collect()
        self.assertEqual(pathlib.Path(got["index_file"]).name, reads.index_name(reads.REPLAN))
        self.assertEqual(pathlib.Path(index["replan-plan-review"]).name, reads.evidence_name("replan-plan-review"))
        self.assertTrue(pathlib.Path(first["index_file"]).is_file())


class ReplanCase(RunCase):
    """形 replan（案の直しの事前審査。ruling が空でない）: 壁打ちを回さず 1 回で返り、stalled はいつも偽（元
    works/blk-plan/lib/planblk.py:25 の『replan では壁打ちを回さない』）。材料は裁かれた項目ごとに、置き場の往復の控えから
    読んだ承認済みの前の形・申し出と裁定・直した形を貼り、人に聞くのは約束の欄が変わったか人に聞く穴の在る項目だけ
    （元 works/.shared/core/replan.py:423 の prep と :620 の gate）"""

    CONFLICT = {"id": "c-clamp", "unit_key": UNIT_CLAMP, "between": ["項目 2", "test_stats.py"],
                "why_both_cannot_hold": "上限の枝の試験が lo を期待していて案と両立しない", "kind": "plan",
                "which_is_right": "test", "ruling": {"decision": "fix_plan_item", "text": "RULING-MARK-3131 試験の側を正とせよ"}}

    def replan(self, field_rows=None, ruled="2", approach=f"{PLAN_MARK} 直した項目 2", **start):
        """review の形の往復を 1 度通した後に、項目 2 を直した案で形 replan の支度まで回す。返りは材料の本文"""
        r = self.run_
        r.start(features_off=["review_tree"], **start)
        self.assertTrue(r.pass_(review())["pass"])
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, **({"approach": approach} if approach else {}))], rnd=2,
               field_rows=field_rows)
        r.inputs.update(ruling=json.dumps([ruled]),
                        conflicts=r.put("fix/conflicts.json", {"items": [self.CONFLICT]}))
        got = r.open()
        self.assertEqual((got["form"], got["tree"]), ("replan", False))
        return pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")

    def test_replan_is_one_shot(self):
        r = self.run_
        text = self.replan()
        for word in (boardview.REVIEW_ASK_REPLAN, planmarks.REVIEW_ASK, boardview.ITEM_HEAD.format(n=2), boardview.OLD_HEAD,
                     boardview.NEW_HEAD, boardview.ROW_HEAD.format(id="c-clamp"), "RULING-MARK-3131", "直した項目 2"):
            self.assertIn(word, text)
        self.assertNotIn(boardview.ITEM_HEAD.format(n=1), text)
        self.assertNotIn(converge.REREVIEW_ASK, text)
        self.assertTrue(r.accept(review(CLAMP_BLOCK))["ok"])
        got = r.out("result")
        self.assertEqual((got["pass"], got["stalled"], got["ask_human"]), (False, False, False), texts(got))
        self.assertEqual(len(converge.read(r.view())["passes"]), 1)

    def designed_replan(self):
        """設計の立った review の形の往復の後に、項目 2 を直した案で形 replan の支度まで回す。返りは材料の本文"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        DesignCase.designed(self)
        r.out("review_prep")
        self.assertTrue(r.accept(review(design_map=ReviewAcceptCase.full_map()))["ok"])
        r.out("result")
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach=f"{PLAN_MARK} 直した項目 2")], rnd=2)
        r.inputs.update(ruling=json.dumps(["2"]), conflicts=r.put("fix/conflicts.json", {"items": [self.CONFLICT]}))
        self.assertEqual(r.open()["form"], "replan")
        return pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")

    def test_replan_material_carries_the_independent_design(self):
        """元 replan.prep の plan-review の頼み: 独立設計の節（design_only）・REVIEW_ASK_REPLAN・planmarks.REVIEW_ASK・項目ごとの節"""
        text = self.designed_replan()
        at = [text.index(w) for w in (planblk.DESIGN_HEAD, DESIGN_TEXT, boardview.REVIEW_ASK_REPLAN, planmarks.REVIEW_ASK,
                                      boardview.ITEM_HEAD.format(n=2))]
        self.assertEqual(at, sorted(at))

    def test_replan_material_shows_only_ruled_items(self):
        """元 tests/test_replan.py の test_review_role_sees_design_only_and_both_forms: 案の直しの事前審査は裁かれた項目だけを見る
        （直していない項目の案・欄を貼らない）"""
        text = self.replan()
        self.assertIn("直した項目 2", text)
        self.assertNotIn(f"{PLAN_MARK} 項目 1 の直し", text)
        self.assertNotIn(planmarks.REVIEW_HEAD, text)

    def test_replan_drift_quotes_checked_and_extra_fields_dropped(self):
        """形 replan の受け付け: 壁打ちと束ね役の任意の欄（resolved・items。synergy は役の型に無い）は外してから照らし、独立設計が立つ時は穴の
        引用と design_map を直した項目の行と照らす（元 replan._take の drop_fields と design.quote_gaps）"""
        r = self.run_
        self.designed_replan()
        drift = face("clamp-drift-no-quote", UNIT_CLAMP, why=design.DRIFT_HEAD + "設計と継ぎ目の置き方が違う、という穴だ")
        fresh = [{"item": 2, "name": "helper_2", "design_quote": None, "why": "設計に対の無い助け手の名だけを足す"}]
        got = r.accept(review(drift, design_map=fresh))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(planblk.DESIGN_QUOTE_REJECT), got["reason"])
        got = r.accept(review(design_map=fresh, resolved=[], items=[{"item": 2, "verdict": "clean", "blocks": []}]))
        self.assertTrue(got["ok"], got)
        kept = json.loads((r.folder / "pass-2" / boardview.REVIEW_FILE).read_text(encoding="utf-8"))
        for key in ("resolved", "items", "design_map"):
            self.assertNotIn(key, kept)

    def test_contract_change_or_human_face_asks(self):
        """約束の欄（allowed_paths）を変えた直しと、人に聞く種類の穴（regression）が在る直しは人に聞く"""
        r = self.run_
        widened = [fields(UNIT_MEAN), {**fields(UNIT_CLAMP), "allowed_paths": ["stats.py", "test_stats.py"]}]
        self.replan(field_rows=widened)
        self.assertTrue(r.accept(review())["ok"])
        got = r.out("result")
        self.assertTrue(got["ask_human"])
        self.assertEqual(len(texts(got)), 1, texts(got))
        self.assertIn("allowed_paths", texts(got)[0])
        rows = json.loads((r.folder / "pass-2" / boardview.REPLAN_FILE).read_text(encoding="utf-8"))
        self.assertEqual([(x["item"], x["contract_changed"], x["ask"]) for x in rows], [(2, ["allowed_paths"], True)])

        self.setUp()
        r = self.run_
        self.replan()
        self.assertTrue(r.accept(review(face("clamp-regression", UNIT_CLAMP, kind="regression", severity="suggest")))["ok"])
        got = r.out("result")
        self.assertTrue(got["ask_human"])
        self.assertIn("clamp-regression", texts(got)[0])

    def test_unattended_widen_only_is_not_asked(self):
        """無人の run で、範囲を広げただけ（allowed_paths に足しただけで、ほかの欄は同じ）の直しは聞かない（planmarks.widened）"""
        r = self.run_
        widened = [fields(UNIT_MEAN), {**fields(UNIT_CLAMP), "allowed_paths": ["stats.py", "test_stats.py"]}]
        self.replan(field_rows=widened, approach="", **{gatepolicy.UNATTENDED_KEY: gatepolicy.UNATTENDED})
        self.assertTrue(r.accept(review())["ok"])
        got = r.out("result")
        self.assertEqual((got["ask_human"], got["questions"]), (False, []))

    def test_replan_after_review_reads_the_revised_plan(self):
        """設計が立った review の形の往復の後の replan は、審査している直した案の行と照らす: 直した案で変わった add の名の
        design_map を受け、前の往復の案の名だけの対応表は拒む"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        DesignCase.designed(self)
        r.out("review_prep")
        self.assertTrue(r.accept(review(design_map=ReviewAcceptCase.full_map()))["ok"])
        r.out("result")
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, adds=[{"name": "clamp_entry", "canonical": "stats.py の入口"}])], rnd=2)
        r.inputs["ruling"] = json.dumps(["2"])
        self.assertEqual(r.open()["form"], "replan")
        r.out("review_prep")
        stale = [{"item": 2, "name": "helper_2", "design_quote": None, "why": "設計に対の無い助け手の名だけを足す"}]
        got = r.accept(review(design_map=stale))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(planblk.DESIGN_QUOTE_REJECT), got["reason"])
        fresh = [{"item": 2, "name": "clamp_entry", "design_quote": "上限は入口 1 箇所で掛け", "why": "設計の入口の上限に案の名が当たる"}]
        self.assertTrue(r.accept(review(design_map=fresh))["ok"])

    def test_replan_review_gave_up_names_each_item(self):
        """形 replan の事前審査が 3 回とも拒まれたら、裁かれた項目ごとの諦めの訳と裁定の文（字のまま）を review.json の隣に置く"""
        r = self.run_
        self.replan()
        for _ in range(rolekit.GIVE_UP_AFTER):
            got = r.accept({"faces": "x"})
        self.assertTrue(got["give_up"], got)
        out = r.out("result")
        self.assertIs(out["pass"], False)
        rows = json.loads(r.pointed(out["review"]).with_name(planblk.REPLAN_GAVE_UP_FILE).read_text(encoding="utf-8"))
        self.assertEqual([(x["item"], x["ruling"]) for x in rows], [(2, self.CONFLICT["ruling"]["text"])])
        self.assertTrue(rows[0]["why"].startswith(planblk.REVIEW_GAVE_UP_WHY.split("{")[0]), rows[0]["why"])

    def test_replan_without_block_passes(self):
        r = self.run_
        self.replan()
        self.assertTrue(r.accept(review())["ok"])
        got = r.out("result")
        self.assertEqual((got["pass"], got["stalled"]), (True, False))

    def test_replan_with_unknown_ruling_asks_human(self):
        """番号でない ruling の形 replan は、差し込みの頭が訳つきで落ち、返す節が pass: false・ask_human: true で訳を名指す
        （黙って 0 項目を審査して通さない）"""
        r = self.run_
        r.start(features_off=["review_tree"])
        self.assertTrue(r.pass_(review())["pass"])
        r.inputs["ruling"] = json.dumps(["x"])
        self.assertFalse(r.out("pass_open")["ok"])
        got = r.out("result")
        self.assertEqual((got["pass"], got["ask_human"]), (False, True))
        self.assertTrue(any("ruling の項目 'x'" in q for q in texts(got)), texts(got))

    def test_replan_without_an_approved_plan_names_it(self):
        """同じ run の置き場に承認済みの案（前の差し込みの往復の控え）が無ければ、差し込みの頭は ok: false でその訳を返す"""
        r = self.run_
        r.inputs["ruling"] = json.dumps(["1"])
        got = r.out("pass_open")
        self.assertFalse(got["ok"])
        self.assertIn(boardview.NO_APPROVED, got["reason"])


class GateFromPlanCase(RunCase):
    """修正案の決め手が関所に届く（元 tests/test_plan_gate.py の PlanGateCase.test_decided_narrow_passes_and_is_recorded・
    test_undecided_narrow_asks を p2.fix_plan.json から回す）。聞かずに通した行は questions に載らず、review の隣の
    gate-passes.json に出どころつきで載る"""

    def test_decided_narrow_passes_and_undecided_asks(self):
        r = self.run_
        r.start(features_off=["review_tree"])
        decided = {**TP.NARROW, "no_narrow": "空の列で例外を投げる今の動きを残すと直したい呼び手が成り立たない",
                   "decided_by": "https://docs.python.org/3/library/statistics.html#statistics.mean の定義",
                   "undecided_because": "", "fences": [], "world": "公式の statistics.mean は空の列で例外を投げる"}
        r.plan([item(UNIT_MEAN, 1, narrows=[decided]), item(UNIT_CLAMP, 2)])
        got = r.pass_(review())
        self.assertFalse(got["ask_human"], got)
        self.assertEqual(got["gate_axes"], {a: {"ok": True, "note": ""} for a in boardview.gate_axes.AXES})
        passes = json.loads((r.pointed(got["review"]).parent / boardview.PASSES_FILE).read_text(encoding="utf-8"))
        self.assertEqual([(p["by"], p["decided_by"]) for p in passes], [(gatemarks.PASSED_BY, decided["decided_by"])])
        r.plan([item(UNIT_MEAN, 1, narrows=[{**decided, "undecided_because": "世界の解が 2 つに割れる"}]), item(UNIT_CLAMP, 2)],
               rnd=2)
        got = r.pass_(review())
        self.assertTrue(got["ask_human"])
        self.assertTrue(any(TP.NARROW["what"] in q for q in texts(got)), texts(got))
        self.assertFalse(got["gate_axes"]["obvious"]["ok"])


    def test_non_human_face_kinds_are_not_asked(self):
        """関所に載るのは人に聞く種類の穴（HUMAN_FACE_KINDS）だけ: contract_drift の block の穴だけの返答は人に聞かない"""
        r = self.run_
        r.start(features_off=["review_tree"])
        got = r.pass_(review(face("mean-contract-drift", kind="contract_drift")))
        self.assertEqual((got["pass"], got["ask_human"], got["questions"]), (False, False, []), got)


class ResultCase(RunCase):
    """返す節は落ちない（元に無い。持ち主の決めと docs/design.md の『返す節は落ちない』）と、返りが output_format を満たす"""

    def check(self, got):
        self.assertEqual(validate_schema(got, nodes()["review"]["output_format"]), [], got)
        for name in ("review", "design"):
            self.run_.assert_pointer(got[name])

    def test_result_matches_the_output_format(self):
        self.run_.start(features_off=["review_tree"])
        got = self.run_.pass_(review(face("regression-face-ask", kind="regression", severity="suggest")))
        self.check(got)
        self.assertTrue(got["ask_human"])

    def test_questions_carry_their_kinds(self):
        """P250: 返りの questions の行は関所の項目の種類 {kind, text} を持つ（線は無人の run で台帳の問い（fork・escalate）だけを報告へ
        回し、ほかの種類では止まる。関所の文の冒頭の種類と ASK_GATE_HEAD の有無もこれで決まる）。行は置き場の gate.json の項目と同じ"""
        self.run_.start(features_off=["review_tree"])
        got = self.run_.pass_(review(face("regression-face-ask", kind="regression", severity="suggest")))
        self.assertEqual([q["kind"] for q in got["questions"]], ["regression"], got["questions"])
        gate = json.loads((self.run_.pointed(got["review"]).parent / boardview.GATE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(got["questions"], [gatemarks.question_row(i["kind"], i["text"]) for i in gate["items"]])

    def test_tampered_fields_reason_reaches_the_return(self):
        """凍結の欄の控えが受け付けの後に書き換わった差し込みは、支度の節が落ちた訳を置き場に残し、返す節がそれを読んで
        questions に控えの名と「凍結と食い違う」を載せ、pass: false で返す（元は盤面を止めて訳を残した）"""
        r = self.run_
        r.open()
        p = r.folder / planmarks.FIELDS_FILE
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["fields"][0]["route"] = "tdd"
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.assertNotEqual(r.script("review_prep").returncode, 0)
        got = r.out("result")
        self.check(got)
        self.assertIs(got["pass"], False)
        self.assertTrue(any(planmarks.FIELDS_FILE in q and "凍結と食い違う" in q for q in texts(got)), got["questions"])

    def test_gate_files_carry_kinds_and_items(self):
        """返した関所の項目の種類と方針の変化を gate-asked.json に積み、項目の全部と壁打ちの行を pass-<k>/gate.json に残す"""
        r = self.run_
        pol = r.tmp / "policy.md"
        pol.write_text("# 方針\n- 公開の口を減らさない\n", encoding="utf-8")
        r.start(features_off=["review_tree"], policy_md=str(pol))
        r.plan([item(UNIT_MEAN, 1, narrows=[dict(TP.NARROW)]), item(UNIT_CLAMP, 2)])
        r.open()
        pol.write_text("# 方針\n- 公開の口を減らさない\n- 足した\n", encoding="utf-8")
        got = r.pass_(review())
        gate = json.loads((r.pointed(got["review"]).parent / gatemarks.PLAN_GATE_FILE).read_text(encoding="utf-8"))
        self.assertEqual([x["kind"] for x in gate["items"]], ["regression", boardview.POLICY_CHANGED])
        self.assertEqual([x["text"] for x in gate["items"]], texts(got))
        self.assertIn("converge", gate)
        asked = json.loads((r.folder / boardview.GATE_ASKED_FILE).read_text(encoding="utf-8"))
        self.assertEqual(sorted(asked), sorted(texts(got)))
        self.assertEqual({t: (v["kind"], "policy_change" in v) for t, v in asked.items()},
                         {texts(got)[0]: ("regression", False), texts(got)[1]: (boardview.POLICY_CHANGED, True)})

    def test_broken_inputs_never_fail_the_return_node(self):
        """壊れた入力（読めない指し札・空の字・JSON でない字・ほかの run の札・在らない先）で open が ok: false を返し、返す節は
        終了の値 0 で、pass: false・ask_human: true・訳を名指す questions の、output_format に合う JSON を返す"""
        other = json.dumps({"type": "archon_artifact", "run_id": "other-run", "path": "judge/judgment.json"})
        missing = json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "judge/no-such.json"})
        for label, value, word in (("空の字", "", "JSONDecodeError"), ("JSON でない字", "{壊れた", "JSONDecodeError"),
                                   ("ほかの run の札", other, "ほかの run のポインタ"), ("在らない先", missing, "no-such.json"),
                                   ("ポインタでない", json.dumps({"path": "x"}), "ポインタでない")):
            with self.subTest(label):
                self.run_.inputs["judgment"] = value
                opened = self.run_.out("pass_open")
                self.assertFalse(opened["ok"])
                self.assertIn(word, opened["reason"])
                done = self.run_.script("result")
                self.assertEqual(done.returncode, 0, done.stderr)
                got = json.loads(done.stdout)
                self.check(got)
                self.assertEqual((got["pass"], got["stalled"], got["ask_human"]), (False, False, True))
                self.assertTrue(any(word in q for q in texts(got)), texts(got))
                self.assertFalse(any(a["ok"] for a in got["gate_axes"].values()))

    def test_failed_open_drops_the_previous_material(self):
        """同じ run の前の差し込みが通っていても、後の差し込みの open が落ちたら、返す節は前の結末でなく落ちた訳を返す"""
        r = self.run_
        r.start(features_off=["review_tree"])
        self.assertTrue(r.pass_(review())["pass"])
        r.inputs.update(ruling=json.dumps(["1"]), judgment="{壊れた")
        self.assertFalse(r.out("pass_open")["ok"])
        got = r.out("result")
        self.check(got)
        self.assertEqual((got["pass"], got["ask_human"]), (False, True))
        self.assertTrue(any("JSONDecodeError" in q for q in texts(got)), texts(got))

    def test_open_refuses_fields_count_apart_from_plan_rows(self):
        """修正案の項目の数と plan-fields.json の欄の数が違えば、往復の控えの行に欄を重ねられないので open は訳つきで落ちる
        （欄を黙って空にすると約束の欄の比べが消え、全部の審査に戻す枝が黙って止まる）"""
        r = self.run_
        r.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)], field_rows=[fields(UNIT_MEAN)])
        opened = r.out("pass_open")
        self.assertFalse(opened["ok"])
        self.assertIn("修正案の項目の数 2", opened["reason"])

    def test_empty_folder_never_fails_the_return_node(self):
        """open も受け付けも走らず plan-review/ が空でも、返す節は偽の結末を返す"""
        done = self.run_.script("result")
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.check(got)
        self.assertEqual((got["pass"], got["ask_human"]), (False, True))
        self.assertTrue(any(boardview.OPEN_FILE in q for q in texts(got)), texts(got))

    def test_open_without_accepted_review_never_fails(self):
        r = self.run_
        r.open()
        done = r.script("result")
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.check(got)
        self.assertTrue(any(boardview.REVIEW_FILE in q for q in texts(got)), texts(got))


class FailSafeCase(RunCase):
    """差し込みの頭と返す節は境の口と lib を読めない時も落ちない。差し込みの頭は始めに前の差し込みの材料を消し、返す節は境の口を
    通さずに failed/ の返答・設計の控え・聞かずに通した行（report が review.json の隣を名で開く）と指し札を組む"""

    BROKEN = {"WORKS_FACTORY_ROOT": "/nonexistent-works-factory-root"}

    def test_script_literals_match_the_lib(self):
        import gate_axes
        opened, result = load_script("pass_open"), load_script("result")
        self.assertEqual((opened.FOLDER, opened.OPEN_FILE, opened.OPEN_ERROR),
                         (boardview.FOLDER, boardview.OPEN_FILE, boardview.OPEN_ERROR))
        self.assertEqual(result.FAILED.split("/")[0], boardview.FOLDER)
        self.assertEqual((result.REVIEW_FILE, result.DESIGN_FILE, result.PASSES_FILE, result.GATE_FILE),
                         (boardview.REVIEW_FILE, design.DESIGN_FILE, boardview.PASSES_FILE, boardview.GATE_FILE))
        self.assertEqual(result.AXES, gate_axes.AXES)
        self.assertEqual(result.FAILED_KIND, gatemarks.GIVEN_UP_KIND)

    def test_result_without_the_lib_returns_the_failed_shape(self):
        r = self.run_
        done = r.script("result", **self.BROKEN)
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual(validate_schema(got, nodes()["review"]["output_format"]), [], got)
        self.assertEqual((got["pass"], got["ask_human"]), (False, True))
        self.assertTrue(texts(got)[0].startswith("出力ノードが落ちた: "), texts(got))
        for name in ("review", "design"):
            r.assert_pointer(got[name])
        passes = r.pointed(got["review"]).with_name(boardview.PASSES_FILE)
        self.assertEqual(json.loads(passes.read_text(encoding="utf-8")), [])

    def test_failed_return_writes_the_passes_beside_the_review(self):
        """lib の中で落ちた時も、review の隣に聞かずに通した行の空のファイルが在る"""
        r = self.run_
        got = r.out("result")
        self.assertFalse(got["pass"])
        self.assertEqual(json.loads(r.pointed(got["review"]).with_name(boardview.PASSES_FILE).read_text(encoding="utf-8")), [])

    def test_unwritable_converge_record_is_named(self):
        """往復の控えを書けない往復は黙って進めない: 受け付けが拒みに数え、3 回目で諦め、返りの questions が控えの名を持ち pass は偽
        （元 tests/test_blk_plan.py の with_converge の halt_unsaved）"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        r.out("review_prep")
        (r.folder / (converge.RECORD + ".tmp")).mkdir()
        for _ in range(rolekit.GIVE_UP_AFTER):
            got = r.accept(review())
        self.assertEqual((got["ok"], got["give_up"]), (False, True), got)
        self.assertIn(converge.RECORD, got["reason"])
        out = r.out("result")
        self.assertIs(out["pass"], False)
        self.assertTrue(any(converge.RECORD in q for q in texts(out)), out["questions"])

    def test_open_without_the_lib_drops_the_previous_material(self):
        """前の差し込みが通った後、差し込みの頭が lib を読めずに落ちても、返す節は前の差し込みの結末を今回の物として返さない"""
        r = self.run_
        r.start(features_off=["review_tree"])
        self.assertTrue(r.pass_(review())["pass"])
        done = r.script("pass_open", **self.BROKEN)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(json.loads(done.stdout)["ok"])
        self.assertFalse((r.folder / boardview.OPEN_FILE).exists())
        got = r.out("result")
        self.assertEqual((got["pass"], got["ask_human"]), (False, True))
        self.assertTrue(any("ModuleNotFoundError" in q for q in texts(got)), texts(got))


class ScriptHeadCase(unittest.TestCase):
    """script は全部 uv の script の宣言を頭に持つ。無いと、対象のリポジトリに pyproject.toml が在る時に uv run が対象の
    プロジェクトの .venv・uv.lock を作り、mutates_checkout: false の節が落ちる"""

    def test_every_script_declares_itself(self):
        for path in sorted((BLOCK / "scripts").glob("*.py")):
            with self.subTest(path.name):
                self.assertTrue(path.read_text(encoding="utf-8").startswith(
                    '# /// script\n# requires-python = ">=3.12"\n# dependencies = []\n# ///\n'))

    def test_uv_run_leaves_a_python_project_untouched(self):
        uv = shutil.which("uv")
        if uv is None:
            self.skipTest("uv が無い")
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(os.path.realpath(tmp)) / "repo"
            committed_copy(repo, SEED)
            (repo / "pyproject.toml").write_text('[project]\nname = "seed"\nversion = "0"\nrequires-python = ">=3.12"\n',
                                                 encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "pyproject")
            art = repo.parent / "artifacts"
            art.mkdir()
            env = hermetic.child_env(ARTIFACTS_DIR=str(art), WORKFLOW_ID=RUN_ID, WORKS_FACTORY_ROOT=str(ROOT),
                                     PYTHONDONTWRITEBYTECODE="1")
            for path in sorted((BLOCK / "scripts").glob("*.py")):
                subprocess.run([uv, "run", str(path)], cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
                with self.subTest(path.name):
                    self.assertFalse((repo / ".venv").exists())
                    self.assertFalse((repo / "uv.lock").exists())
                    self.assertEqual(git(repo, "status", "--porcelain", "--ignored"), "")


class KindsCase(unittest.TestCase):
    def test_role_kinds_are_exactly_the_eight_looked_at(self):
        """役の返りの穴の種類は、指示書の『見ること』の 8 つ（copy・entrance・contract_drift・dead_path・scope_creep・regression・
        policy・precedent）とちょうど同じ並び"""
        text = (BLOCK / "commands" / "plan-review.md").read_text(encoding="utf-8")
        looked = re.findall(r"^\d\. \*\*[^*]+\*\*（kind=(\w+)）", text, re.M)
        enum = nodes()["plan-review"]["output_format"]["properties"]["faces"]["items"]["properties"]["kind"]["enum"]
        self.assertEqual(len(looked), 8)
        self.assertEqual(enum, looked)


class PortedMaterialCase(RunCase):
    """今の works の事前審査の材料に在って、移した時に落ちていた物を戻した（人の方針の節・BASE・no の整数で指す行・考えの住処の
    地図・独立設計に貼る方針・返答の型の照らし）"""

    def policy(self) -> pathlib.Path:
        pol = self.run_.tmp / "policy.md"
        pol.write_text("# 方針\n- POLICY-MARK-8080 公開の口を減らさない\n", encoding="utf-8")
        return pol

    def test_material_carries_policy_base_units_and_concept_map(self):
        r = self.run_
        r.start(features_off=["review_tree"], policy_md=str(self.policy()), base_rev="HEAD")
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        for want in (boardview.UNITS_LINE, f"BASE: `HEAD`", policy.HEAD, policy.PREFACE, "POLICY-MARK-8080",
                     policy.RULE, "## 考えの住処の地図"):
            self.assertIn(want, text)
        self.assertLess(text.index(policy.RULE), text.index("## 考えの住処の地図"))

    def test_material_pastes_the_frozen_copy(self):
        """P192: 事前審査の材料と独立設計の材料に貼る方針の本文は、run の始めに固めた版の写し（元 works/.shared/core/policy.py の brief は
        record.process.policy.copy を貼った）。後から書き換えた文書の字は貼らず、変化は関所の行だけが言う"""
        PolicyCase.frozen_start(self)
        r = self.run_
        r.open()
        texts = {"事前審査": pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8"),
                 "独立設計": r.out("r2_prep")["prompt"]}
        for name, text in texts.items():
            with self.subTest(material=name):
                self.assertIn("POLICY-A-1111", text)
                self.assertNotIn("POLICY-B-2222", text)

    def test_prep_passes_state_dir_cache_root(self):
        """材料のライブラリの文書の節は、STATE_DIR の下 works-factory/ の run をまたぐ控えを読む（網に出ない）"""
        import libdocs
        from lib.tests.test_libdocs import FakeBoard, ok_http
        r = self.run_
        (r.repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (r.repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        git(r.repo, "add", "app.py", "requirements.txt")
        git(r.repo, "commit", "-q", "-m", "app")
        r.units[0]["reason"] += "（app.py の requests）"
        r.judgment()
        state = r.tmp / "state"
        libdocs.section(FakeBoard(r.tmp / "earlier").work(""), r.repo, ["app.py"], get=ok_http(), env={},
                        shared=state / "works-factory")
        r.start(features_off=["review_tree"])
        r.open()
        got = r.out("review_prep", STATE_DIR=str(state), https_proxy="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9")
        self.assertIn("ほかの run 1 本", pathlib.Path(got["prompt_file"]).read_text(encoding="utf-8"))

    def test_units_line_is_the_original_instruction_line(self):
        """材料の直す単位の行は元の指示書 p2.plan_review.md:4 の行（engine を機械に読み替え、雛形を番号つきの単位に置き換えた物）。
        元の字は単位を key のまま書かせた行を持たず、外した行も戻っていない"""
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        head = ORIGINAL_UNITS_LINE[:ORIGINAL_UNITS_LINE.index("{{")].replace(" engine ", "機械").replace("——engine ", "——機械")
        line = next(x for x in text.splitlines() if x.startswith("直す単位"))
        self.assertEqual(line, head + "[")
        self.assertIn(f'"no": 2,\n  "key": "{UNIT_CLAMP}"', text)
        command = (BLOCK / "commands" / "plan-review.md").read_text(encoding="utf-8")
        for where in (text, command):
            self.assertNotIn("key を字のまま", where)

    def test_gate_answers_reach_the_lib_through_the_open_script(self):
        """入力 gate_answers は差し込みの頭の script から lib の控えに届く（通すの言葉は continue に揃う）"""
        r = self.run_
        r.inputs["gate_answers"] = json.dumps({"decision": "approve", "text": "GATE-MARK-5151 通す", "asked": ["問いの行"]},
                                              ensure_ascii=False)
        r.open()
        rows = json.loads((r.folder / boardview.GATE_ANSWERS_FILE).read_text(encoding="utf-8"))
        self.assertEqual([(x["answer"], x["note"], x["asked"]) for x in rows], [("continue", "GATE-MARK-5151 通す", ["問いの行"])])

    def test_role_prompts_paste_the_frozen_copy(self):
        """役に貼る方針は始めの記録の固めた版の写し（始めの後に文書を書き換えても、事前審査・下請け・独立設計は固めた版を読む）"""
        r = self.run_
        r.ripple(RIPPLE)
        pol = self.policy()
        r.start(policy_md=str(pol), policy=policy.freeze(r.tmp / "frozen", r.repo, str(pol)))
        pol.write_text("# 方針\n- POLICY-MARK-9191 書き換えた\n", encoding="utf-8")
        got = r.open()
        self.assertTrue(got["tree"] and got["r2_go"])
        texts = [pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8"), r.out("r2_prep")["prompt"],
                 *(p.read_text(encoding="utf-8") for p in sorted((r.folder / planblk.ITEMS_DIR.format(k=1)).glob("item-*.md")))]
        self.assertGreater(len(texts), 2)
        for text in texts:
            self.assertIn("POLICY-MARK-8080", text)
            self.assertNotIn("POLICY-MARK-9191", text)

    def test_no_policy_no_section(self):
        r = self.run_
        r.open()
        text = pathlib.Path(r.out("review_prep")["prompt_file"]).read_text(encoding="utf-8")
        self.assertNotIn(policy.HEAD + "\n", text)
        self.assertNotIn(policy.RULE, text)

    def test_item_subagents_get_the_policy(self):
        """下請けの決まりは指示書の『リポジトリ: 』の行から末尾までに人の方針の節を足した物（元の下請けは描いた指示書の末尾の
        人の方針までを受けた）"""
        r = self.run_
        r.ripple(RIPPLE)
        r.start(policy_md=str(self.policy()))
        self.assertTrue(r.open()["tree"])
        r.out("review_prep")
        briefs = sorted((r.folder / planblk.ITEMS_DIR.format(k=1)).glob("item-*.md"))
        self.assertTrue(briefs)
        for path in briefs:
            text = path.read_text(encoding="utf-8")
            self.assertIn("POLICY-MARK-8080", text)
            self.assertIn(policy.RULE, text)

    def test_design_prompt_gets_the_policy(self):
        r = self.run_
        r.start(policy_md=str(self.policy()))
        self.assertTrue(r.open()["r2_go"])
        prompt = r.out("r2_prep")["prompt"]
        self.assertIn("POLICY-MARK-8080", prompt)
        self.assertIn(policy.RULE, prompt)

    def test_reply_out_of_the_role_format_is_rejected(self):
        r = self.run_
        r.start(features_off=["review_tree"])
        r.open()
        r.out("review_prep")
        got = r.accept(review(face("bad-kind-face", kind="taste")))
        self.assertFalse(got["ok"])
        self.assertIn("事前審査の返答の型が合わない", got["reason"])


class QuoteFoldCase(unittest.TestCase):
    """元 tests/test_blk_plan.py の QuoteFoldCase: 独立設計の引用の照らしは両側を NFKC にし空白の並びを畳む。字の 1 つ違いは見逃さない。
    関所の依頼の引用の照らしは畳まない"""

    def test_width_and_whitespace_folded_but_one_char_difference_missing(self):
        import cite
        source = "上限は入口 1 箇所で掛ける。\n呼び手は値を渡すだけにする"
        self.assertEqual(cite.missing_quotes("「上限は入口 1 箇所で掛ける。 呼び手は値を渡す」", source), [])
        self.assertEqual(cite.missing_quotes("「上限は入口 １ 箇所で掛ける」", source), [])
        self.assertEqual(cite.missing_quotes("「上限は入口 2 箇所で掛ける」", source), ["上限は入口 2 箇所で掛ける"])
        self.assertEqual(cite.missing_quotes("引用の無い文", source), [])
        self.assertEqual(cite.quotes("短い「ab」と「四文字以上の引用」"), ["四文字以上の引用"])

    def test_request_quote_check_of_sources_stays_literal(self):
        import cite
        request = "上限は入口 1 箇所で掛ける"
        for quote in ("上限は入口 １ 箇所で掛ける", "上限は入口  1 箇所で掛ける", "上限は入口 1箇所で掛ける"):
            with self.subTest(quote):
                self.assertIn("依頼の文に無い", cite.sources_problem(f"依頼の本文「{quote}」", ".", quoted=request))
        self.assertEqual(cite.sources_problem("依頼の本文「上限は入口 1 箇所で掛ける」", ".", quoted=request), "")


class FixtureCase(unittest.TestCase):
    """筋書き（fixtures/*.stubs.yaml）を止めた Archon の workflow test で回す。Archon の源か bun が無ければ名前つきで見送る"""

    def test_fixtures_pass_in_archon(self):
        names = sorted(p.name for p in (BLOCK / "fixtures").glob("*.stubs.yaml"))
        self.assertEqual(names, sorted(f"{n}.stubs.yaml" for n in (
            "pass", "block", "stalled", "ask-human", "r2-skipped", "r2-give-up", "review-give-up", "open-failed")))
        with archon.tree([BLOCK.name]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-plan-review", "--cwd", str(tree))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"{len(names)} passed, 0 failed", done.stdout)


# ---------------------------------------------------------------- 関所の材料（見え方で直に回す）
class GateBase(unittest.TestCase):
    """関所の材料を見え方で直に回す（元 tests/test_plan_gate.py の GateBase.gate の偽の盤面を boardview の見え方に置き換えた物。
    盤面・git・子のプロセスなし）。返りは元の写しの RL の human_gate と同じ形: 項目が無ければ {"ok": True}、在れば
    {"decision": "ask", "ask": {"kinds": 種類の並び（重ねず並べ替えた物）, "items": 項目の文の並び}}"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(os.path.realpath(self._tmp.name))

    def gate(self, narrows=(), faces=(), questions=(), units=(), materials=None, unattended=False):
        """(返り, 見え方)。materials は記録の素材 {名: {status, reason}}"""
        if unattended:
            (self.tmp / startrec.REL).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / startrec.REL).write_text(json.dumps({gatepolicy.UNATTENDED_KEY: gatepolicy.UNATTENDED}), encoding="utf-8")
        inputs = {"plan": {"plan": [{"unit_keys": ["u"], "narrows": list(narrows)}]}, "questions": list(questions),
                  "units": list(units), "materials": dict(materials or {}), "cwd": str(self.tmp)}
        b = boardview.view(self.tmp, inputs, {"faces": list(faces)})
        items = gatemarks.plan_gate_items(b)
        if not items:
            return {"ok": True}, b
        return {"decision": "ask", "ask": {"kinds": sorted({k for k, _ in items}), "items": [t for _, t in items]}}, b


# 決め手は在るが柵に当たる行（元 tests/test_gate_drafts.py の ASKED。利用者の run ac9e02ab の 2 件の形）
ASKED = {**TP.DECIDED, "fences": ["policy_doc"]}


def gate_text(asking: dict) -> str:
    """修正前の関所の文（元 line_edge.gate_text の組み立てを gatemarks で直に呼ぶ）"""
    return gatemarks.gate_text(asking, run_id="run-1", node=gatemarks.GATE_NODE, record_name="process.human_items")


def ledger(b, q) -> dict:
    """見え方の台帳に在る q と同じ key の問い（boardview.view は台帳を写して持つので、gatemarks.request_answer の同じ物の照らしには
    台帳の側の問いを渡す）"""
    return next(x for x in b.record["questions"] if x.get("key") == q["key"])


def continued(b, got, note=""):
    """関所に continue で答えた行を積む（元 human_gate_answered と同じ形）"""
    b.record["process"]["human_items"].append({"round": 1, "kinds": got["ask"]["kinds"], "asked": got["ask"]["items"],
                                               "answer": "continue", "note": note, "node": gatemarks.GATE_NODE})


class PlanGateCase(GateBase):
    """修正前の関所が、決め手の在る項目を人に聞かずに通すか。決め手の出どころ decided_by が在り undecided_because が空で柵の印
    fences が無い行は通して state.works.gate_passes に出どころつきで残し、柵の印か undecided_because の在る行・欄の無い行は聞く"""

    def test_decided_narrow_passes_and_is_recorded(self):
        """元 tests/test_plan_gate.py の PlanGateCase.test_decided_narrow_passes_and_is_recorded。決め手の揃った狭めは聞かずに
        通し、出どころつきで通した行に残る"""
        got, b = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}])
        self.assertEqual(got, {"ok": True})
        passes = b.state["works"].get("gate_passes") or []
        self.assertEqual([(p["node"], p["by"], p["decided_by"]) for p in passes],
                         [("p2.human_gate", "decided", TP.DECIDED["decided_by"])])
        self.assertIn(TP.NARROW["what"], passes[0]["item"])

    def test_decided_regression_face_passes(self):
        """元 tests/test_plan_gate.py の PlanGateCase.test_decided_regression_face_passes。決め手の揃った後退の穴も聞かずに通す"""
        got, b = self.gate(faces=[{**TP.FACE, **TP.DECIDED}])
        self.assertEqual(got, {"ok": True})
        self.assertEqual([p["by"] for p in b.state["works"].get("gate_passes") or []], ["decided"])

    def test_fenced_narrow_asks_even_if_decided(self):
        """元 tests/test_plan_gate.py の PlanGateCase.test_fenced_narrow_asks_even_if_decided。柵の印の在る行は決め手が在っても聞く"""
        got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED, "fences": ["external_write"]}])
        self.assertEqual(got.get("decision"), "ask", got)

    def test_undecided_narrow_asks(self):
        """元 tests/test_plan_gate.py の PlanGateCase.test_undecided_narrow_asks。undecided_because の在る行は聞く"""
        got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED, "undecided_because": "世界の解が 2 つに割れる"}])
        self.assertEqual(got.get("decision"), "ask", got)

    def test_asked_row_shows_what_the_world_does(self):
        """元 tests/test_plan_gate.py の PlanGateCase.test_asked_row_shows_what_the_world_does。人に回す行は、役が書いた世界の解の
        1 文を項目の尾に載せる（書いていなければそう出す。欄の無い行には付けない）"""
        world = "rjsf と JSON Forms はどちらも見せ方を UI schema に分ける（https://jsonforms.io/faq/）が、置き場は決めていない"
        for mark, tail in (({**TP.DECIDED, "undecided_because": "置き場が割れる", "world": world}, f"（世界の解: {world}）"),
                           ({**TP.DECIDED, "undecided_because": "置き場が割れる", "world": ""}, "（世界の解: 役が書いていない）")):
            with self.subTest(tail=tail):
                got, _ = self.gate(narrows=[{**TP.NARROW, **mark}])
                self.assertTrue(got["ask"]["items"][0].endswith(tail), got["ask"]["items"])
        got, _ = self.gate(narrows=[dict(TP.NARROW)])
        self.assertNotIn("世界の解", got["ask"]["items"][0])

    def test_asked_row_shows_the_no_narrow(self):
        """人に回す行は、役が書いた狭めない案の 1 文を項目の尾に載せる（no_narrow を書いた行だけ）"""
        no_narrow = "空の列に 0 を返す形を当たったが、呼び手が例外を捕まえて別の道に進むので採れない"
        got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED, "undecided_because": "置き場が割れる", "no_narrow": no_narrow}])
        self.assertIn(f"（狭めない案: {no_narrow}）", got["ask"]["items"][0])
        got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED, "undecided_because": "置き場が割れる"}])
        self.assertNotIn("狭めない案", got["ask"]["items"][0])

    def test_rule_points_at_world_rows(self):
        """元 tests/test_plan_gate.py の PlanGateCase.test_rule_points_at_world_rows。関所の決め手の頼みは、世界の調べを役に
        任せず、頭の世界の解の行を使えと言い、依頼の解き方を決め手にしない（計画 world-solution の W8・5.3 節の 6）"""
        for node, text in gatemarks.HEAD.items():
            with self.subTest(node):
                self.assertIn("世界の解の行", text)
                self.assertNotIn("web を引くかは任せる", text)
                self.assertIn("依頼が示した解き方は決め手にならない", text)

    def test_mixed_rows_ask_only_the_undecided(self):
        """元 tests/test_plan_gate.py の PlanGateCase.test_mixed_rows_ask_only_the_undecided。決め手の在る行と欄の無い行が並べば、
        欄の無い行だけを聞き、決め手の在る行は項目に出さず記録に残す"""
        got, b = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}, {"what": "負の上限の clamp", "why": "上限が負の時の結果が変わる"}])
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertEqual(len(got["ask"]["items"]), 1)
        self.assertIn("負の上限の clamp", got["ask"]["items"][0])
        self.assertEqual([p["by"] for p in b.state["works"].get("gate_passes") or []], ["decided"])


class FourAxesCase(GateBase):
    """関所に載せずにグラフの中で決めてよいかは、自明（決め手の出どころが現物に在る）・世界の解（world か URL の決め手）・汚くない
    （その単位の構造の目の行が人に上げる行でない）・やりすぎでない（柵の印が無く、修正案の単位の外を名指さない）の 4 つが全部揃う時だけ。
    人がいる run も無人の run も同じ（持ち主 2026-10-09 の決め 1。計画 2026-10-09-clean-whole の Task 2.6）"""

    def put_rows(self, *rows):
        design = self.tmp / "design.jsonl"
        design.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        structmark.write(self.tmp, status="ok", reason="", design_file=str(design), wall_s=0)

    def test_decided_by_must_exist(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_decided_by_must_exist。決め手の出どころが現物に無ければ聞き、通した行に
        残さない"""
        mark = {**TP.DECIDED, "decided_by": "docs/adr/0099-nope.md:3 の決め"}
        got, b = self.gate(narrows=[{**TP.NARROW, **mark}])
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertIn("決め手の出どころが現物に無い", got["ask"]["items"][0])
        self.assertEqual(b.state["works"].get("gate_passes") or [], [])

    def test_decided_by_url_passes(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_decided_by_url_passes。URL の決め手は通る"""
        got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}])
        self.assertEqual(got, {"ok": True})

    def test_decided_by_file_line_passes(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_decided_by_file_line_passes。現物に在るパス:行の決め手は通る"""
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0002-keep.md").write_text("# 決め\n\n空の列は例外のまま\n", encoding="utf-8")
        mark = {**TP.DECIDED, "decided_by": "docs/0002-keep.md:3（人の前の決定）"}
        got, _ = self.gate(narrows=[{**TP.NARROW, **mark}])
        self.assertEqual(got, {"ok": True})

    def test_no_world_asks(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_no_world_asks。世界の解（world か URL の決め手）が無ければ聞く"""
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED, "decided_by": "keep.md:1", "world": ""}])
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertIn("世界の解", got["ask"]["items"][0])

    def test_face_outside_plan_units_asks(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_face_outside_plan_units_asks。修正案の単位の外を名指す穴は聞く"""
        got, _ = self.gate(faces=[{**TP.FACE, **TP.DECIDED, "unit_keys": ["別の単位"]}])
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertIn("修正案の単位の外", got["ask"]["items"][0])

    def test_eye_route_up_becomes_gate_item(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_eye_route_up_becomes_gate_item。構造の目が人に上げた行は修正前の関所の
        項目になる（推し＝chosen・捨てた案と代償＝rejected）。その単位の決め手の行は聞かずに通さない（汚くないの軸が揃わない）。
        無人の run でも同じ（止まって答えの下書きを残す）"""
        self.put_rows(TP.ROUTE_UP)
        for unattended in (False, True):
            with self.subTest(unattended=unattended):
                got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}], unattended=unattended)
                self.assertEqual(got.get("decision"), "ask", got)
                items = got["ask"]["items"]
                design = [x for x in items if x.startswith(gatemarks.DESIGN_HEAD)]
                self.assertEqual(len(design), 1, items)
                for want in (TP.ROUTE_UP["undecided_because"], TP.ROUTE_UP["chosen"], "境の節に写す", "知る場所が 2 つになる"):
                    self.assertIn(want, design[0])
                self.assertIn(gatemarks.DESIGN_KIND, got["ask"]["kinds"])
                self.assertTrue(any("構造の目" in x and TP.NARROW["what"] in x for x in items), items)

    def test_request_quote_must_be_in_request(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_request_quote_must_be_in_request。依頼の引用「…」は依頼の文に字のまま
        在る時だけ出どころになる"""
        req = self.tmp / "request.json"
        req.write_text(json.dumps({"findings": [{"where": "stats.py", "text": "空の列の mean は今までどおり例外でよい"}]},
                                  ensure_ascii=False), encoding="utf-8")
        (self.tmp / startrec.REL).parent.mkdir(parents=True, exist_ok=True)
        (self.tmp / startrec.REL).write_text(json.dumps({"request_file": str(req)}), encoding="utf-8")
        ok = {**TP.DECIDED, "decided_by": "依頼の本文「空の列の mean は今までどおり例外でよい」"}
        self.assertEqual(self.gate(narrows=[{**TP.NARROW, **ok}])[0], {"ok": True})
        bad = {**TP.DECIDED, "decided_by": "依頼の本文「空の列は 0 を返す」"}
        got, _ = self.gate(narrows=[{**TP.NARROW, **bad}])
        self.assertIn("依頼の文に無い", got["ask"]["items"][0])

    def test_sources_ignore_times_and_dirs_and_take_absolute_request_cites(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_sources_ignore_times_and_dirs_and_take_absolute_request_cites。出どころの
        照らしは時刻と出典の引用を数えず、フォルダだけを出どころにせず、依頼の絶対パスの引用を受ける"""
        import cite
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "x.md").write_text("一\n二\n三\n", encoding="utf-8")
        req = self.tmp / "req.json"
        req.write_text("[]\n[]\n", encoding="utf-8")
        self.assertEqual(cite.sources_problem("12:30 に決めた docs/x.md:3 の「三」の行", self.tmp), "")   # 時刻と出典の引用は数えない
        self.assertEqual(cite.sources_problem(f"{req}:2", self.tmp / "docs", [str(self.tmp)]), "")
        self.assertEqual(cite.sources_problem("docs/ の慣習", self.tmp), cite.NO_SOURCE)                # フォルダだけは出どころでない
        self.assertIn("依頼の文に無い", cite.sources_problem("依頼の本文「無い字の並び」", self.tmp, quoted="ある字"))

    def test_clean_route_rows_do_not_block(self):
        """元 tests/test_plan_gate.py の FourAxesCase.test_clean_route_rows_do_not_block。構造の目が自分で決めた行は関所を止めない"""
        self.put_rows({**TP.ROUTE_UP, "route": "自分で決める", "route_reason": "決め手で決まる", "undecided_because": ""})
        got, _ = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}])
        self.assertEqual(got, {"ok": True})


class WorldGateCase(GateBase):
    """関所の軸「世界の解か」は、役が書く world の文でなく、世界の解の行への修正案の答えで機械が決める（worldmark.world_ok）:
    答えの要る行が無い・従う・依頼の外の出どころで訳の立つ外れなら揃う。依頼を出どころにした外れは修正前の関所の項目になる
    （人がいる run も無人の run も同じ。計画 world-solution の W9・5.3 節の 6）"""

    def put_world(self, *rows):
        wf = self.tmp / "world-out" / worldmark.WORLD_FILE
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        (self.tmp / worldmark.STATE_FILE).write_text(json.dumps(
            {"status": "ok", "reason": "", "world_file": str(wf), "classes": len(rows), "dropped": 0}), encoding="utf-8")

    def put_answers(self, *answers):
        (self.tmp / planmarks.FIELDS_FILE).write_text(json.dumps({"round": 1, "fields": [{"structure": list(answers)}]},
                                                                 ensure_ascii=False), encoding="utf-8")

    def put_request(self):
        req = self.tmp / "request.json"
        req.write_text(json.dumps({"findings": [{"where": "stats.py", "text": TP.REQUEST_LINE}]}, ensure_ascii=False),
                       encoding="utf-8")
        (self.tmp / startrec.REL).parent.mkdir(parents=True, exist_ok=True)
        (self.tmp / startrec.REL).write_text(json.dumps({"request_file": str(req)}), encoding="utf-8")

    def test_following_world_row_passes_without_asking(self):
        """元 tests/test_plan_gate.py の WorldGateCase.test_following_world_row_passes_without_asking。世界の解の行に従う案の行は、
        役が world の文を書かず URL の決め手も無くても、世界の解の軸が揃う（機械が決める）"""
        (self.tmp / "keep.md").write_text("空の列は例外のまま\n", encoding="utf-8")
        mark = {**TP.DECIDED, "decided_by": "keep.md:1", "world": ""}
        got, _ = self.gate(narrows=[{**TP.NARROW, **mark}])
        self.assertEqual(got.get("decision"), "ask", "世界の解の行が無い run は今どおり world か URL が要る")
        self.put_world(TP.WORLD_ROW)
        self.put_answers({"world": "w-mean", "follows": True})
        got, b = self.gate(narrows=[{**TP.NARROW, **mark}])
        self.assertEqual(got, {"ok": True})
        self.assertEqual([p["by"] for p in b.state["works"].get("gate_passes") or []], ["decided"])

    def test_world_deviation_becomes_gate_item(self):
        """元 tests/test_plan_gate.py の WorldGateCase.test_world_deviation_becomes_gate_item。出どころの無い外れは修正前の関所の
        項目（種類 world）になり、行の定石と依頼の解き方との比べが載る"""
        self.put_world(TP.WORLD_ROW)
        self.put_answers({"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"})
        got, _ = self.gate()
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertIn(gatemarks.WORLD_KIND, got["ask"]["kinds"])
        item = next(x for x in got["ask"]["items"] if "w-mean" in x)
        for want in ("WG-4410", "呼び手の都合で 0 を返す形に寄せたい", "人に聞く訳"):
            self.assertIn(want, item)

    def test_world_deviation_is_asked_once(self):
        """元 tests/test_plan_gate.py の WorldGateCase.test_world_deviation_is_asked_once。世界の行から外れる案の項目に決め手の
        揃った narrows の行が在っても、類の id が関所の項目に載るのは世界の解の外れの項目の 1 度だけ。narrows の行は世界の解の軸で
        止めず、聞かずに通した行に残る"""
        self.put_world(TP.WORLD_ROW)
        self.put_answers({"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"})
        got, b = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}])
        self.assertEqual(got.get("decision"), "ask", got)
        items = got["ask"]["items"]
        self.assertEqual(len([x for x in items if "w-mean" in x]), 1, items)
        self.assertEqual(got["ask"]["kinds"].count(gatemarks.WORLD_KIND), 1, got["ask"]["kinds"])
        passed = [p["item"] for p in b.state["works"].get("gate_passes") or []]
        self.assertTrue(any(x.startswith("修正案 1 が狭める能力") for x in passed), passed)

    def test_deviation_cited_to_request_goes_to_human(self):
        """元 tests/test_plan_gate.py の WorldGateCase.test_deviation_cited_to_request_goes_to_human。依頼を出どころにした外れは、
        引用が依頼に在っても人に回る。行の外れは世界の解の外れの項目が 1 度だけ聞き、同じ項目の決め手の揃った narrows の行は
        世界の解の軸で止めない。依頼の外の出どころ（現物に在るパス:行）で訳の立つ外れはグラフの中で通り、通した行に残る"""
        self.put_request()
        self.put_world(TP.WORLD_ROW)
        self.put_answers({"world": "w-mean", "deviation": f"依頼の本文「{TP.REQUEST_LINE}」に従い、定石から外れる"})
        got, b = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}])
        self.assertEqual(got.get("decision"), "ask", got)
        items = got["ask"]["items"]
        self.assertEqual(len([x for x in items if "w-mean" in x and "依頼" in x]), 1, items)
        self.assertEqual([x for x in items if x.startswith("修正案 1 が狭める能力")], [], items)
        self.assertTrue(any(p["item"].startswith("修正案 1 が狭める能力") for p in b.state["works"].get("gate_passes") or []))
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0007-zero.md").write_text("# 決め\n\n空の列は 0 を返す\n", encoding="utf-8")
        self.put_answers({"world": "w-mean", "deviation": "人の前の決定 docs/0007-zero.md:3 が 0 を返すと決めた"})
        got, b = self.gate(narrows=[{**TP.NARROW, **TP.DECIDED}])
        self.assertEqual(got, {"ok": True})
        self.assertTrue(any("w-mean" in p["item"] for p in b.state["works"].get("gate_passes") or []))

    def test_world_item_the_human_continued_is_not_asked_again(self):
        """元 tests/test_plan_gate.py の WorldGateCase.test_world_item_the_human_continued_is_not_asked_again。人が continue で
        通した世界の解の外れの項目は聞き直さない（構造の目の設計の問いと同じ）"""
        self.put_world(TP.WORLD_ROW)
        self.put_answers({"world": "w-mean", "deviation": "呼び手の都合で 0 を返す形に寄せたい、と考えた"})
        got, _ = self.gate()
        asked = [x for x in got["ask"]["items"] if "w-mean" in x]
        self.assertEqual(len(asked), 1, got)
        _, b = self.gate()
        b.record["process"]["human_items"] = [{"node": gatemarks.GATE_NODE, "answer": "continue", "asked": asked, "round": 1}]
        self.assertEqual([x for _, x in gatemarks.plan_gate_items(b) if "w-mean" in x], [])

    def test_knowledge_row_named_in_gate_item(self):
        """元 tests/test_plan_gate.py の WorldGateCase.test_knowledge_row_named_in_gate_item。web で確かめていない（knowledge）行
        からの外れは、依頼の外の出どころが在っても人に回り、項目にそう名指す"""
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "0007-zero.md").write_text("# 決め\n\n空の列は 0 を返す\n", encoding="utf-8")
        self.put_world({**TP.WORLD_ROW, "basis": "knowledge", "sources": []})
        self.put_answers({"world": "w-mean", "deviation": "人の前の決定 docs/0007-zero.md:3 が 0 を返すと決めた"})
        got, _ = self.gate()
        self.assertEqual(got.get("decision"), "ask", got)
        item = next(x for x in got["ask"]["items"] if "w-mean" in x)
        self.assertIn(worldmark.NOT_WEB, item)


class LedgerAsksCase(GateBase):
    """問いの台帳で人に聞く状態の fork・escalate が修正前の関所の項目に載り（無人の run では載せない）、関所の continue でその
    出どころが修正役に戻ったと言い（一言の「保留: <key>」は戻さない）、読めなかった保留を名指す。直す義務の数え・報告の文は
    ほかのブロックの試験が持つ"""

    def answer(self, b, got, note=""):
        """元 human_gate_answered と同じ形の行を積む"""
        continued(b, got, note)

    def test_hold_note_keeps_the_fork_origin_exempt(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_hold_note_keeps_the_fork_origin_exempt を gatemarks の側で: 一言の
        「保留: <key>」は答えに数えず、出どころは直す義務から外したまま（元は直す義務の数えで見ていた。数えは fix の物）"""
        got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.answer(b, got, note=f"狭めは通す。保留: {TP.FORK['key']}")
        self.assertFalse(gatemarks.answered(b, ledger(b, TP.FORK)))
        self.assertEqual(gatemarks.withheld(b), {TP.FORK_UNIT})
        self.assertEqual(gatemarks.returned(b), set())

    def test_hold_note_names_only_the_whole_key(self):
        """元 LedgerAsksCase.test_hold_note_names_only_the_whole_key を gatemarks の側で: 「保留: q-empty-mean-2」は key が前方で
        重なる q-empty-mean を保留にしない"""
        longer = {**TP.FORK, "key": TP.FORK["key"] + "-2", "origin": TP.OTHER_UNIT}
        got, b = self.gate(questions=[TP.FORK, longer], units=TP.UNITS)
        self.answer(b, got, note=f"保留: {longer['key']}。")
        self.assertTrue(gatemarks.answered(b, ledger(b, TP.FORK)))
        self.assertEqual(gatemarks.withheld(b), {TP.OTHER_UNIT})

    def test_hold_note_lists_several_keys(self):
        """元 LedgerAsksCase.test_hold_note_lists_several_keys を gatemarks の側で: 並べた問いはどれも保留にする"""
        other = {**TP.FORK, "key": TP.FORK["key"] + "-b", "origin": TP.OTHER_UNIT}
        for sep in ("・", "/", "／", "、", " "):
            with self.subTest(sep=sep):
                got, b = self.gate(questions=[TP.FORK, other], units=TP.UNITS)
                self.answer(b, got, note=f"保留: {TP.FORK['key']}{sep}{other['key']}")
                self.assertEqual(gatemarks.withheld(b), {TP.FORK_UNIT, TP.OTHER_UNIT})

    def test_stop_or_another_gate_does_not_return_the_origin(self):
        """元 LedgerAsksCase.test_stop_or_another_gate_does_not_return_the_origin を gatemarks の側で: stop と修正の後の関所の
        continue は修正前の関所の答えに数えない"""
        got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
        b.record["process"]["human_items"].append({"round": 1, "kinds": ["fork"], "asked": got["ask"]["items"],
                                                   "answer": "stop", "note": "", "node": "p2.human_gate"})
        b.record["process"]["human_items"].append({"round": 1, "kinds": ["regression"], "asked": got["ask"]["items"],
                                                   "answer": "continue", "note": "", "node": "r4.human_gate"})
        self.assertEqual((gatemarks.withheld(b), gatemarks.returned(b)), ({TP.FORK_UNIT}, set()))

    def test_held_fork_is_asked_with_options_and_recommendation(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_held_fork_is_asked_with_options_and_recommendation。保留の fork は
        選択肢と推しと出どころを載せて聞き、関所の文は台帳の問いへの答え方を言う（台帳の問いの無い関所では言わない）"""
        got, _ = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertEqual(got["ask"]["kinds"], ["fork"])
        row = got["ask"]["items"][0]
        for needle in (TP.FORK["key"], "例外・0 を返す", "推し: 例外", TP.FORK_UNIT):
            self.assertIn(needle, row)
        text = gate_text({"node": "p2.human_gate", **got["ask"]})
        self.assertIn(gatemarks.ASK_GATE_HEAD, text)
        self.assertIn("問いの理由の推しで直す", text)
        self.assertIn("保留: <問いの key>", text)
        self.assertNotIn(gatemarks.ASK_GATE_HEAD, gate_text({"node": "p2.human_gate", "kinds": ["regression"],
                                                             "items": ["x"], "question": "q"}))

    def test_recommendation_missing_is_said(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_recommendation_missing_is_said。推しが無ければそう出す"""
        got, _ = self.gate(questions=[{**TP.FORK, "reason": "空の列の意味が 2 つに割れる"}], units=TP.UNITS)
        self.assertIn("推し: 判定の役が書いていない", got["ask"]["items"][0])

    def test_decided_or_non_fork_held_question_is_not_asked(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_decided_or_non_fork_held_question_is_not_asked。決着した問いと fork で
        ない保留の問いは関所に載せない"""
        for q in ({**TP.FORK, "status": "decided", "resolution": "例外"}, {**TP.FORK, "kind": "field", "origin": None}):
            with self.subTest(q["status"] + q["kind"]):
                got, _ = self.gate(questions=[q], units=TP.UNITS)
                self.assertEqual(got, {"ok": True})

    def test_escalate_is_asked(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_escalate_is_asked。status が escalate の問いは種類 escalate で聞く"""
        got, _ = self.gate(questions=[{**TP.FORK, "kind": "stuck", "status": "escalate"}], units=TP.UNITS)
        self.assertEqual(got["ask"]["kinds"], ["escalate"])

    def test_continue_returns_the_fork_origin_to_the_owed_units(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_continue_returns_the_fork_origin_to_the_owed_units。continue を受けた
        fork の出どころは修正役への戻りの行に載り、答えた問いは関所に 2 度出さない（直す義務の数え・最後の関所の文は落とした）"""
        got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.answer(b, got, note="例外で")
        self.assertIn(TP.FORK_UNIT, "\n".join(gatemarks.returned_lines(b)))
        self.assertEqual(gatemarks.plan_gate_items(b), [])   # 答えた問いは関所に 2 度出さない

    def test_continue_returns_a_deferred_origin_the_fixer_was_promised(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_continue_returns_a_deferred_origin_the_fixer_was_promised。開いて
        いない単位（suggest の defer）を出どころに持つ fork に関所で答えると、修正役への約束（returned_lines）に載る（直す義務の
        数えとの突き合わせは落とした）"""
        units = [{"key": TP.FORK_UNIT, "label": "suggest", "disposition": "defer"}, {"key": TP.OTHER_UNIT, "label": "block"}]
        got, b = self.gate(questions=[TP.FORK], units=units)
        self.answer(b, got, note="例外で")
        self.assertIn(TP.FORK_UNIT, "\n".join(gatemarks.returned_lines(b)))

    def test_origin_missing_from_the_round_units_is_not_promised(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_origin_missing_from_the_round_units_is_not_promised。今の周の units に
        無い出どころ（defer の台帳だけに在る key）は、答えても直す義務に戻せないので、修正役に「直す義務に戻った」と約束しない"""
        gone = {**TP.FORK, "origin": "stats.py median: 台帳だけに在る単位"}
        got, b = self.gate(questions=[gone], units=TP.UNITS)
        self.answer(b, got, note="例外で")
        self.assertNotIn(gone["origin"], "\n".join(gatemarks.returned_lines(b)))

    def test_hold_note_with_words_after_the_key_keeps_the_fork_origin_exempt(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_hold_note_with_words_after_the_key_keeps_the_fork_origin_exempt。
        「保留: <key>は来週決める」「保留: <key>（来週）」のように key の後ろに言葉が続いても、台帳の key と照らして保留にする"""
        for note in (f"保留: {TP.FORK['key']}は来週決める", f"保留: {TP.FORK['key']}（来週）"):
            with self.subTest(note=note):
                got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
                self.answer(b, got, note=note)
                self.assertFalse(gatemarks.answered(b, TP.FORK))

    def test_hold_note_names_a_key_that_holds_a_separator(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_hold_note_names_a_key_that_holds_a_separator。台帳の key が区切りの字
        （/）を含んでも、「保留: <key>」はその問いを保留にする"""
        slashed = {**TP.FORK, "key": "storage/backend"}
        got, b = self.gate(questions=[slashed], units=TP.UNITS)
        self.answer(b, got, note=f"保留: {slashed['key']}")
        self.assertFalse(gatemarks.answered(b, slashed))

    def test_unread_hold_is_shown_to_the_human(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_unread_hold_is_shown_to_the_human。台帳の key を拾えない「保留」
        （打ち間違いの key・コロン無し）は答えた扱いのまま、「読めなかった保留」の行（報告の冒頭と最後の関所の文が並べる
        gatemarks.unread_hold_lines）に一言の断片と答えた扱いになった問いの key を並べる"""
        for note in ("保留: q-emty-mean", "q-emty-mean は保留"):
            with self.subTest(note=note):
                got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
                self.answer(b, got, note=note)
                self.assertTrue(gatemarks.answered(b, TP.FORK))
                rows = [r for r in gatemarks.unread_hold_lines(b) if "読めなかった保留" in r]
                self.assertTrue(rows, gatemarks.unread_hold_lines(b))
                self.assertIn("q-emty-mean", "\n".join(rows))
                self.assertIn(TP.FORK["key"], "\n".join(rows))

    def test_unread_hold_beside_a_read_key_is_shown(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_unread_hold_beside_a_read_key_is_shown。正しい key と打ち間違いを
        並べた「保留:」は、正しい key を保留にしたまま、打ち間違いの側を「読めなかった保留」に並べる。key の後ろの言葉（英語・
        「-」も）だけなら並べない"""
        for tail in ("・q-typo", "・q-typo は来週", ", q-typo"):
            with self.subTest(tail=tail):
                got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
                self.answer(b, got, note=f"保留: {TP.FORK['key']}{tail}")
                self.assertFalse(gatemarks.answered(b, TP.FORK))
                rows = "\n".join(r for r in gatemarks.unread_hold_lines(b) if "読めなかった保留" in r)
                self.assertIn("「q-typo」", rows, gatemarks.unread_hold_lines(b))
        for tail in ("は来週決める", " until Monday", " - 来週決める"):
            with self.subTest(tail=tail):
                got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
                self.answer(b, got, note=f"保留: {TP.FORK['key']}{tail}")
                self.assertFalse(gatemarks.answered(b, TP.FORK))
                self.assertEqual(gatemarks.unread_hold_lines(b), [])

    def test_unattended_run_does_not_open_the_gate_for_questions_only(self):
        """元 tests/test_plan_gate.py の LedgerAsksCase.test_unattended_run_does_not_open_the_gate_for_questions_only。無人の run:
        保留の問いだけでは関所を開かない（無人の殻の stop で修正が飛ばない）。狭めの在る関所は今どおり開く（問いの行は載せない）。
        直す義務の数え・報告の冒頭は落とした"""
        (self.tmp / "r1").mkdir()
        (self.tmp / "r1" / "start.json").write_text('{"unattended": "true"}', encoding="utf-8")
        got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.assertEqual(got, {"ok": True})
        got, _ = self.gate(narrows=[TP.NARROW], questions=[TP.FORK], units=TP.UNITS)
        self.assertEqual((got["ask"]["kinds"], len(got["ask"]["items"])), (["regression"], 1))


class EscalateAsksCase(GateBase):
    """status が escalate の問い（kind が fork でない）も、関所に載せる問いと同じ 1 つの決まりで扱う: 関所に載り、continue で
    出どころを修正役に戻し、無人の run では関所を開かない。直す義務の数え・報告の文はほかのブロックの試験が持つ"""
    answer = LedgerAsksCase.answer

    def test_hold_note_keeps_the_escalate_origin_exempt(self):
        """元 EscalateAsksCase.test_hold_note_keeps_the_escalate_origin_exempt を gatemarks の側で"""
        got, b = self.gate(questions=[TP.ESCALATE], units=TP.UNITS)
        continued(b, got, note=f"保留: {TP.ESCALATE['key']}")
        self.assertEqual((gatemarks.withheld(b), gatemarks.returned(b)), ({TP.FORK_UNIT}, set()))

    def test_unanswered_escalate_origin_is_not_owed(self):
        """元 tests/test_plan_gate.py の EscalateAsksCase.test_unanswered_escalate_origin_is_not_owed。答える前の escalate は種類
        escalate で関所に載る（直す義務の数えは落とした）"""
        got, b = self.gate(questions=[TP.ESCALATE], units=TP.UNITS)
        self.assertEqual(got["ask"]["kinds"], ["escalate"])

    def test_continue_returns_the_escalate_origin(self):
        """元 tests/test_plan_gate.py の EscalateAsksCase.test_continue_returns_the_escalate_origin。continue を受けた escalate の
        出どころは修正役への戻りの行に載る（直す義務の数えは落とした）"""
        got, b = self.gate(questions=[TP.ESCALATE], units=TP.UNITS)
        self.answer(b, got, note="例外で")
        self.assertIn(TP.FORK_UNIT, "\n".join(gatemarks.returned_lines(b)))

    def test_unattended_run_keeps_the_escalate_origin_exempt(self):
        """元 tests/test_plan_gate.py の EscalateAsksCase.test_unattended_run_keeps_the_escalate_origin_exempt。無人の run では
        escalate だけで関所を開かない（直す義務の数え・報告の冒頭は落とした）"""
        (self.tmp / "r1").mkdir()
        (self.tmp / "r1" / "start.json").write_text('{"unattended": "true"}', encoding="utf-8")
        got, b = self.gate(questions=[TP.ESCALATE], units=TP.UNITS)
        self.assertEqual(got, {"ok": True})

    def test_skip_mark_only_on_questions_still_exempting(self):
        """元 tests/test_plan_gate.py の EscalateAsksCase.test_skip_mark_only_on_questions_still_exempting。held_lines は、答えて
        戻した問いと関所に載らない問いに「答えが無いと直さない単位」を付けない（最後の関所の文は落とした）"""
        awaiting = {"key": "q-awaiting-pr", "kind": "awaiting", "status": "held", "origin": "parallel_pr", "reason": "人が確かめる"}
        for q in (TP.FORK, TP.ESCALATE):
            got, b = self.gate(questions=[q, awaiting], units=TP.UNITS)
            self.answer(b, got, note="例外で")
            rows = gatemarks.held_lines(b)
            self.assertFalse([r for r in rows if TP.SKIP_MARK in r], (q["kind"], rows))
        _, b = self.gate(questions=[TP.ESCALATE], units=TP.UNITS)
        self.assertIn(f"{TP.SKIP_MARK}: {TP.FORK_UNIT}", "\n".join(gatemarks.held_lines(b)))

    def test_skip_mark_drops_a_unit_another_answer_returned(self):
        """元 tests/test_plan_gate.py の EscalateAsksCase.test_skip_mark_drops_a_unit_another_answer_returned。保留の問いと答えた
        問いが同じ出どころを持つと、その単位は直す義務に戻るので、保留の問いの行に「答えが無いと直さない単位」として並べない
        （戻らなかった depends だけを並べる。直す義務の数えは落とした）"""
        held = {**TP.ESCALATE, "depends": [TP.OTHER_UNIT]}
        got, b = self.gate(questions=[TP.FORK, held], units=TP.UNITS)
        self.answer(b, got, note=f"保留: {held['key']}")
        rows = [r for r in gatemarks.held_lines(b) if held["key"] in r]
        self.assertEqual([r.split(f"{TP.SKIP_MARK}: ")[1].split(f"／{gatemarks.ANSWER_KEY_HEAD}")[0] for r in rows],
                         [TP.OTHER_UNIT])

    def test_gate_item_exemption_and_return_name_the_same_units(self):
        """元 tests/test_plan_gate.py の EscalateAsksCase.test_gate_item_exemption_and_return_name_the_same_units。fork と escalate
        の両方で、関所の項目が名指す単位・答える前に直す義務から外れる単位（P240。元 works/tests/test_plan_gate.py:602 の exempt）・
        答えて戻る単位が同じ。答えた後は外れる単位が無い"""
        for q in (TP.FORK, TP.ESCALATE):
            got, b = self.gate(questions=[q], units=TP.UNITS)
            named = {u for u in (TP.FORK_UNIT, TP.OTHER_UNIT) if u in got["ask"]["items"][0]}
            exempt = gatemarks.withheld(b)
            self.answer(b, got)
            self.assertEqual((q["kind"], named, exempt, gatemarks.returned(b)), (q["kind"], *({TP.FORK_UNIT},) * 3))
            self.assertEqual(gatemarks.withheld(b), set())


class DesignOnlyCase(GateBase):
    """設計だけの run（start の控えの design_only）: 修正前の関所を項目の有無に関わらず開け、無人の run でも開け、
    その行に continue を受けた後は 2 度聞かない。design_only の無い・空の run は今どおり項目だけで開く"""

    def start(self, **doc):
        (self.tmp / "r1").mkdir(exist_ok=True)
        (self.tmp / "r1" / "start.json").write_text(json.dumps(doc), encoding="utf-8")

    def test_design_only_run_opens_the_gate_without_items(self):
        """元 tests/test_plan_gate.py の DesignOnlyCase.test_design_only_run_opens_the_gate_without_items。設計だけの run は項目が
        無くても関所を開き、continue を受けた後は 2 度聞かない"""
        for doc in ({}, {"design_only": ""}):
            with self.subTest(doc=doc):
                self.start(**doc)
                got, _ = self.gate()
                self.assertEqual(got, {"ok": True})
        self.start(design_only="true")
        got, b = self.gate()
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertEqual((got["ask"]["kinds"], len(got["ask"]["items"])), (["design_only"], 1))
        self.assertIn("design_only", gatemarks.KIND_WORDS)   # 関所の文が『人が決める項目』と書かない
        continued(b, got)
        self.assertEqual(gatemarks.plan_gate_items(b), [])   # continue を受けた設計だけの行は 2 度聞かない

    def test_design_only_opens_even_when_unattended(self):
        """元 tests/test_plan_gate.py の DesignOnlyCase.test_design_only_opens_even_when_unattended。無人の run でも設計だけの行は
        載り（無人の殻が stop を返して報告へ進む）、問いの行は今どおり載せない"""
        self.start(unattended="true", design_only="true")
        got, _ = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertEqual(got["ask"]["kinds"], ["design_only"])


class ConvergeGateCase(GateBase):
    """事前審査の壁打ちが止まった（converge の控えの抜け方が persisted・unsettled）案: 修正前の関所を修正に進まない行で開け、行の尾に
    止まった理由（converge.stuck_reason）を付ける。入力 design_only と重なっても行は 1 つ。無人の run でも載る。その行の全文に
    continue を受けた後は 2 度聞かず、理由が変われば聞き直す"""

    def fake(self):
        """converge.record_pass の書き先（今の周 1・置き場 self.tmp）"""
        return types.SimpleNamespace(round=1, dir=self.tmp, work=lambda name: self.tmp / name, trace=lambda op, **kw: None)

    def converged(self, outcome, blocks=("a-key-001",)):
        """控えに往復と抜け方を置く（converge.record_pass を往復の数だけ）"""
        fake = self.fake()
        faces = [{"key": k, "kind": "regression", "where": "stats.py", "why": "穴", "severity": "block"} for k in blocks]
        reviews = {converge.CLEAN: [[]], converge.AGAIN: [faces], converge.PERSISTED: [faces, faces]}[outcome]
        for review in reviews:
            row = converge.record_pass(fake, {"faces": review}, resolved=[], files={})
        self.assertEqual(row["outcome"], outcome)

    start = DesignOnlyCase.start

    def test_stuck_opens_design_item_with_reason(self):
        """元 tests/test_plan_gate.py の ConvergeGateCase.test_stuck_opens_design_item_with_reason。壁打ちが止まった案は修正に
        進まない行で関所を開け、尾に止まった理由を付ける。普通の run の止まりは設計だけの行と名乗らない"""
        self.converged(converge.PERSISTED)
        got, b = self.gate()
        self.assertEqual(got.get("decision"), "ask", got)
        self.assertEqual(got["ask"]["kinds"], ["design_only"])
        self.assertTrue(got["ask"]["items"][0].startswith(gatemarks.STUCK_ITEM + "。理由: "), got["ask"]["items"])
        self.assertIn("a-key-001", got["ask"]["items"][0])
        self.assertEqual(got["ask"]["items"][0], f"{gatemarks.STUCK_ITEM}。理由: {converge.stuck_reason(b)}")
        self.assertNotIn("設計だけの run", got["ask"]["items"][0])   # 普通の run の止まりは設計だけの行と名乗らない（f2）

    def test_clean_or_again_does_not_open(self):
        """元 tests/test_plan_gate.py の ConvergeGateCase.test_clean_or_again_does_not_open。抜け方が clean・again なら開かない"""
        for outcome in (converge.CLEAN, converge.AGAIN):
            with self.subTest(outcome=outcome):
                (self.tmp / converge.RECORD).unlink(missing_ok=True)
                self.converged(outcome)
                got, _ = self.gate()
                self.assertEqual(got, {"ok": True})

    def test_stuck_opens_even_when_unattended(self):
        """元 tests/test_plan_gate.py の ConvergeGateCase.test_stuck_opens_even_when_unattended。無人の run でも止まった案の行は
        載り、問いの行は載せない"""
        self.start(unattended="true")
        self.converged(converge.PERSISTED)
        got, _ = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.assertEqual(got["ask"]["kinds"], ["design_only"])

    def test_design_only_and_stuck_give_one_line(self):
        """元 tests/test_plan_gate.py の ConvergeGateCase.test_design_only_and_stuck_give_one_line。設計だけの run の止まりは
        1 行で、頭は設計だけの行"""
        self.start(design_only="true")
        self.converged(converge.PERSISTED)
        got, _ = self.gate()
        self.assertEqual(got["ask"]["kinds"], ["design_only"])
        self.assertEqual(len(got["ask"]["items"]), 1)
        self.assertTrue(got["ask"]["items"][0].startswith(gatemarks.DESIGN_ONLY_ITEM + "。理由: "), got["ask"]["items"])

    def test_design_only_alone_keeps_todays_text(self):
        """元 tests/test_plan_gate.py の ConvergeGateCase.test_design_only_alone_keeps_todays_text。止まりの無い設計だけの run の
        行は今どおりの文"""
        self.start(design_only="true")
        got, b = self.gate()
        self.assertEqual(got["ask"]["items"], [gatemarks.DESIGN_ONLY_ITEM])
        self.assertEqual(gatemarks.design_item(b), gatemarks.DESIGN_ONLY_ITEM)

    def test_continue_answers_only_that_reason(self):
        """元 tests/test_plan_gate.py の ConvergeGateCase.test_continue_answers_only_that_reason。同じ理由の行に continue を
        受けたら 2 度聞かず、別の key で止まり理由が変われば聞き直す"""
        self.converged(converge.PERSISTED)
        got, b = self.gate()
        continued(b, got)
        self.assertEqual(gatemarks.plan_gate_items(b), [])   # 同じ理由の行に continue を受けた: 2 度聞かない
        fake = self.fake()
        face = {"key": "b-key-002", "kind": "regression", "where": "stats.py", "why": "別の穴", "severity": "block"}
        for _ in range(2):
            converge.record_pass(fake, {"faces": [face]}, resolved=[], files={})
        self.assertEqual(converge.read(fake)["outcome"], converge.PERSISTED)
        again = gatemarks.plan_gate_items(b)   # 別の key で止まった: 理由が変わったのでもう一度聞く
        self.assertEqual([k for k, _ in again], ["design_only"])
        self.assertIn("b-key-002", again[0][1])


class PlainSubjectCase(GateBase):
    """関所の文は平易な名を主語にし、盤面の内部の名（節の名・記録の欄・目の名・状態の語）は括弧に回す"""

    def test_plan_gate_text_subjects_are_plain(self):
        """元 tests/test_plan_gate.py の PlainSubjectCase.test_plan_gate_text_subjects_are_plain。修正前の関所の文の行は内部の名を
        主語にしない"""
        text = gate_text({"node": "p2.human_gate", "kinds": ["regression"], "question": "狭まる能力を代償に採るか",
                          "items": ["項目 A"]})
        self.assertEqual(TP.internal_subjects(text), [])


class QuotedQuestionCase(GateBase):
    """盤面の問いの文は本線の答え方（continue --note・--detail）で書かれているので、関所の文には引用（> の行）として載せ、
    引用の後に読み替えの 1 行（--note・--detail がこのラインでどう読まれるか）を添え、答え方は answer.line の 1 通りだけ"""

    def asking(self):
        return {"node": "p2.human_gate", "kinds": ["regression"], "question": TP.MAINLINE_Q, "items": ["項目 A"]}

    def check_gate(self, text, continue_line):
        self.assertEqual(TP.unquoted_mainline(text), [])
        quoted = [x.lstrip()[1:].strip() for x in text.splitlines() if x.lstrip().startswith(">")]
        self.assertEqual(quoted, [x.strip() for x in TP.MAINLINE_Q.splitlines()])
        after = text.split(quoted[-1], 1)[1].split("答え方", 1)[0]
        note = [x for x in after.splitlines() if "--note" in x and "--detail" in x]
        self.assertEqual(len(note), 1, after)
        self.assertEqual(text.count(continue_line), 1, "答え方の continue は 1 通りだけ")

    def test_plan_gate_quotes_mainline_question(self):
        """元 tests/test_plan_gate.py の QuotedQuestionCase.test_plan_gate_quotes_mainline_question。修正前の関所の文は本線の問いの
        文を引用で載せ、読み替えの 1 行を添え、答え方の continue は 1 通りだけ"""
        self.check_gate(gate_text(self.asking()), gatemarks.answer.line("run-1", "continue", "<通す範囲と条件>"))


class RequestAnswersCase(GateBase):
    """依頼の answers が台帳の問いの key か出どころに当たれば、関所の continue と同じ 1 つの述語で答えたと読む。直す義務の数え・
    報告の文はほかのブロックの試験が持つ"""

    def answers(self, *rows):
        (self.tmp / "r1").mkdir(exist_ok=True)
        (self.tmp / "r1" / "start.json").write_text(json.dumps({"answers": list(rows)}, ensure_ascii=False), encoding="utf-8")

    def test_requester_answer_by_origin_moves_awaiting_out_of_held(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_requester_answer_by_origin_moves_awaiting_out_of_held。出どころで
        当てた依頼者の答えは awaiting を保留から答えた行へ移す（最後の関所の文・報告の冒頭は落とした）"""
        self.answers({"question": "parallel_pr", "text": "並行する PR は無い"})
        _, b = self.gate(questions=[TP.AWAITING_PR], units=TP.UNITS)
        self.assertEqual(gatemarks.held_lines(b), [])
        done = "\n".join(gatemarks.answered_lines(b))
        self.assertIn("依頼者の答え: 並行する PR は無い", done)
        self.assertNotIn(gatemarks.GATE_CONTINUED, done)

    def test_requester_answer_by_key_skips_gate_and_returns_origin(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_requester_answer_by_key_skips_gate_and_returns_origin。key で当てた
        依頼者の答えは関所を開かず、出どころを修正役に戻す（直す義務の数えは落とした）"""
        self.answers({"question": TP.FORK["key"], "text": "例外のまま"})
        got, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.assertEqual(got, {"ok": True}, "答えた問いは修正前の関所に載せない")
        self.assertEqual(gatemarks.pending(b), [])
        self.assertIn("依頼者の答え: 例外のまま", "\n".join(gatemarks.returned_lines(b)))

    def test_measured_answer_shows_command_and_output(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_measured_answer_shows_command_and_output。命令と出力つきの答えは
        答えた行に命令と出力を載せる"""
        self.answers({"question": "parallel_pr", "text": "一覧は空", "command": "gh pr list --state open",
                      "output": "no open pull requests"})
        _, b = self.gate(questions=[TP.AWAITING_PR], units=TP.UNITS)
        line = gatemarks.answered_lines(b)[0]
        self.assertIn("人が手元で実行: `gh pr list --state open`", line)
        self.assertIn("no open pull requests", line)

    def test_unmatched_answer_is_shown_and_question_stays_held(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_unmatched_answer_is_shown_and_question_stays_held。当たらない答えは
        名指し、問いは保留のまま（最後の関所の文・報告の冒頭は落とした）"""
        self.answers({"question": "parallel-pr", "text": "無い"})
        _, b = self.gate(questions=[TP.AWAITING_PR], units=TP.UNITS)
        self.assertEqual(len(gatemarks.held_lines(b)), 1)
        self.assertIn("parallel-pr", "\n".join(gatemarks.unmatched_answer_lines(b)))

    def test_answer_hitting_several_questions_answers_none(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_answer_hitting_several_questions_answers_none。出どころで当てた
        答えが同じ単位の別の問い（fork と escalate）に当たれば、どれにも答えた扱いにせず名指す（最後の関所の文・報告の冒頭は
        落とした）"""
        self.answers({"question": TP.FORK_UNIT, "text": "例外のまま"})
        got, b = self.gate(questions=[TP.FORK, TP.ESCALATE], units=TP.UNITS)
        self.assertEqual(got.get("decision"), "ask", "どちらの問いも関所に載る")
        self.assertEqual(gatemarks.answered_lines(b), [])
        self.assertEqual(gatemarks.returned_lines(b), [])
        self.assertEqual(len(gatemarks.held_lines(b)), 2)
        line = "\n".join(gatemarks.unmatched_answer_lines(b))
        self.assertIn(f"複数の問いに当たった: {TP.FORK_UNIT} → {TP.FORK['key']}・{TP.ESCALATE['key']}", line)

    def test_answer_by_key_is_not_ambiguous(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_answer_by_key_is_not_ambiguous。key で当てた答えは、同じ出どころの
        問いが他に在ってもその問いだけに当たる"""
        self.answers({"question": TP.ESCALATE["key"], "text": "直さない"})
        _, b = self.gate(questions=[TP.FORK, TP.ESCALATE], units=TP.UNITS)
        self.assertIn("依頼者の答え: 直さない", "\n".join(gatemarks.answered_lines(b)))
        self.assertEqual(len(gatemarks.held_lines(b)), 1)
        self.assertEqual(gatemarks.unmatched_answer_lines(b), [])

    def test_answer_hitting_settled_question_is_shown(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_answer_hitting_settled_question_is_shown。決着済みの問いに当たった
        答えも、答えた行・当たらなかった行のどちらからも落とさず名指す（最後の関所の文・報告の冒頭は落とした）"""
        self.answers({"question": "parallel_pr", "text": "無い"})
        _, b = self.gate(questions=[{**TP.AWAITING_PR, "status": "decided"}], units=TP.UNITS)
        self.assertEqual(gatemarks.answered_lines(b), [])
        line = "\n".join(gatemarks.unmatched_answer_lines(b))
        self.assertIn(f"決着済みの問いに当たった答え: parallel_pr → {TP.AWAITING_PR['key']}（decided）", line)
        self.assertIn("依頼者の答え: 無い", line)

    def ties(self, *rows):
        gatemarks.save_answer_ties(self.tmp, 1, list(rows))

    def test_tie_to_question_key_answers_it(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_tie_to_question_key_answers_it。question の字が問いの key と違う
        答えでも、判定が key q-7 に結べば答えた扱いになり、当たらない行に並ばない"""
        q7 = {**TP.FORK, "key": "q-7"}
        self.answers({"question": "空の列の扱い", "text": "例外のまま"})
        self.ties({"answer": "空の列の扱い", "to": "q-7"})
        got, b = self.gate(questions=[q7], units=TP.UNITS)
        self.assertEqual(got, {"ok": True}, "答えた問いは修正前の関所に載せない")
        self.assertTrue(gatemarks.answered(b, ledger(b, q7)))
        self.assertEqual(gatemarks.answer_binds(b, gatemarks.request_answers(b)[0]), [q7], "結びが当てる問いは key q-7 の 1 つ")
        self.assertEqual(gatemarks.unmatched_answer_lines(b), [])
        self.assertIn("依頼者の答え: 例外のまま", "\n".join(gatemarks.answered_lines(b)))

    def test_tie_to_unit_and_none_rows(self):
        """元 tests/test_plan_gate.py の RequestAnswersCase.test_tie_to_unit_and_none_rows。単位に結んだ答えはその単位の答えとして
        修正役に渡り、none に結んだ答えは訳つきで当たらない行に並ぶ。字の一致の道は今どおり"""
        self.answers({"question": TP.FORK["key"], "text": "例外のまま"}, {"question": "単位への答え", "text": "上限は 10"},
                     {"question": "もう無い問い", "text": "あれは取り下げた"})
        self.ties({"answer": "単位への答え", "to": TP.OTHER_UNIT},
                  {"answer": "もう無い問い", "none": "その問いは前の run で決着して今の台帳に無い"})
        _, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.assertTrue(gatemarks.answered(b, ledger(b, TP.FORK)))
        returned = "\n".join(gatemarks.returned_lines(b))
        self.assertIn(f"依頼で答えた単位 {TP.OTHER_UNIT}", returned)
        self.assertIn("依頼者の答え: 上限は 10", returned)
        unmatched = "\n".join(gatemarks.unmatched_answer_lines(b))
        self.assertIn("もう無い問い", unmatched)
        self.assertIn("その問いは前の run で決着して今の台帳に無い", unmatched)
        self.assertNotIn("単位への答え", unmatched)
        self.assertNotIn(TP.FORK["key"], unmatched)
        # 判定が none に結んでも、台帳に key が字のまま等しい問いが在れば答えた扱いのまま、当たらない行にも並ばない
        # （判定の後に機械が立てる問いの key で書かれた答え）
        self.answers({"question": TP.FORK["key"], "text": "例外のまま"})
        self.ties({"answer": TP.FORK["key"], "none": "判定の返答にその問いが無く、後で機械が台帳に立てる問い"})
        _, b = self.gate(questions=[TP.FORK], units=TP.UNITS)
        self.assertTrue(gatemarks.answered(b, ledger(b, TP.FORK)))
        self.assertEqual(gatemarks.unmatched_answer_lines(b), [])


class MaterialAnswersCase(GateBase):
    """依頼の answers の question が、今の周に測れていない素材（not_run・awaiting_human）の名なら、その素材から立った問いと素材に
    当たる（計画 request-answers の決め 2 の出どころ。利用者の声 10-09 の C2）"""
    answers = RequestAnswersCase.answers

    def test_field_question_named_by_material_is_answered_by_material_name(self):
        """元 tests/test_plan_gate.py の MaterialAnswersCase.test_field_question_named_by_material_is_answered_by_material_name。
        origin を持てない field の問いでも、key の頭が測れていない素材の名なら、機械はその素材を出どころと読んで答えを結ぶ"""
        self.answers({"question": "parallel_pr", "text": "並行する PR は無い"})
        _, b = self.gate(questions=[TP.FIELD_PR], units=TP.UNITS, materials=TP.PR_NOT_RUN)
        self.assertEqual(gatemarks.held_lines(b), [])
        self.assertIn("依頼者の答え: 並行する PR は無い", "\n".join(gatemarks.answered_lines(b)))
        self.assertEqual(gatemarks.unmatched_answer_lines(b), [])
        self.assertEqual(gatemarks.origin_of(b, TP.FIELD_PR), "parallel_pr")

    def test_key_prefix_needs_a_word_boundary_and_an_unmeasured_material(self):
        """元 tests/test_plan_gate.py の MaterialAnswersCase.test_key_prefix_needs_a_word_boundary_and_an_unmeasured_material。key の
        頭が素材の名でも、名の字が続く（別の名の断片）か、素材が測れている（clean）なら出どころと読まない"""
        for name, q, mats in (("名の断片", {**TP.FIELD_PR, "key": "parallel_prs の確かめ"}, TP.PR_NOT_RUN),
                              ("測れた素材", TP.FIELD_PR, {"parallel_pr": {"status": "clean", "reason": "交差なし"}})):
            with self.subTest(name):
                _, b = self.gate(questions=[q], units=TP.UNITS, materials=mats)
                self.assertEqual(gatemarks.origin_of(b, q), "")

    def test_answer_to_material_without_question_is_not_unmatched(self):
        """元 tests/test_plan_gate.py の MaterialAnswersCase.test_answer_to_material_without_question_is_not_unmatched。判定役が問いを
        立てなかった素材にも、素材の名の答えは当たる（利用者の run f6eaf0a0）。命令と出力が無ければ測りの代わりにしない（決め 4）"""
        self.answers({"question": "parallel_pr", "text": "並行する PR は無い"})
        _, b = self.gate(units=TP.UNITS, materials=TP.PR_NOT_RUN)
        self.assertEqual(gatemarks.unmatched_answer_lines(b), [])
        self.assertEqual(gatemarks.measured_materials(b), set())
        line = "\n".join(gatemarks.answered_lines(b))
        self.assertIn("素材 parallel_pr", line)
        self.assertIn("依頼者の答え: 並行する PR は無い", line)
        self.assertNotIn(gatemarks.HAND_CHECKED, line)

    def test_measured_answer_closes_the_material_as_hand_checked(self):
        """元 tests/test_plan_gate.py の MaterialAnswersCase.test_measured_answer_closes_the_material_as_hand_checked。命令と出力
        つきの答えは、素材を『人が手元で確かめた（実測とは書かない）』にする（報告の冒頭と最後の関所の文は落とした）"""
        self.answers(TP.MEASURED)
        _, b = self.gate(questions=[TP.FIELD_PR], units=TP.UNITS, materials=TP.PR_NOT_RUN)
        self.assertEqual(gatemarks.measured_materials(b), {"parallel_pr"})

    def test_answer_hitting_several_material_questions_closes_nothing(self):
        """元 tests/test_plan_gate.py の MaterialAnswersCase.test_answer_hitting_several_material_questions_closes_nothing。素材の名の
        答えが key の頭がその名の問い 2 つに当たる時は、どれにも答えず、素材も人が確かめた物にしない（答えたと言わない物で残りを
        外さない）"""
        self.answers(TP.MEASURED)
        two = [TP.FIELD_PR, {**TP.FIELD_PR, "key": "parallel_pr: 別の確かめ"}]
        _, b = self.gate(questions=two, units=TP.UNITS, materials=TP.PR_NOT_RUN)
        self.assertEqual(gatemarks.measured_materials(b), set())
        self.assertEqual(gatemarks.material_lines(b), [])
        self.assertIn("複数の問いに当たった", "\n".join(gatemarks.unmatched_answer_lines(b)))

    def test_answer_to_measured_material_is_still_unmatched(self):
        """元 tests/test_plan_gate.py の MaterialAnswersCase.test_answer_to_measured_material_is_still_unmatched。測れている素材
        （clean）の名の答えは素材に当てない（答えは要らなかった。黙って捨てずに名指す）"""
        self.answers(TP.MEASURED)
        _, b = self.gate(units=TP.UNITS, materials={"parallel_pr": {"status": "clean", "reason": "交差なし"}})
        self.assertEqual(gatemarks.measured_materials(b), set())
        self.assertIn("parallel_pr", "\n".join(gatemarks.unmatched_answer_lines(b)))


class PushCase(GateBase):
    """関所の項目の推し（gatemarks の recommend）が人に回す行の尾と関所の文に載るか"""

    def test_asked_row_carries_the_recommend_and_the_gate_pushes_it(self):
        """元 tests/test_gate_drafts.py の PushCase.test_asked_row_carries_the_recommend_and_the_gate_pushes_it。人に回す行は推しを
        尾に載せ、関所の文の冒頭 3 行の推しに出す"""
        got, _ = self.gate(narrows=[{**TP.NARROW, **ASKED, gatemarks.RECOMMEND: TD.REC}])
        item = got["ask"]["items"][0]
        self.assertTrue(item.endswith(f"／推し: 通す（continue）——{TD.REC['note']}（理由: {TD.REC['why']}）"), item)
        text = gate_text({"node": "p2.human_gate", **got["ask"]})
        self.assertIn(f"推し: 通す（continue）——{TD.REC['note']}", text.splitlines()[2])

    def test_slash_in_the_push_is_kept_out_of_the_tail_mark(self):
        """元 tests/test_gate_drafts.py の PushCase.test_slash_in_the_push_is_kept_out_of_the_tail_mark。推しの文に「／」が在っても
        尾は 1 つの区切りで終わる（R4 の照らしで外す形 PUSH_TAIL と、推しの拾い PUSH_IN が全文を読む）"""
        rec = {**TD.REC, "note": "A／B の範囲で通す"}
        got, _ = self.gate(narrows=[{**TP.NARROW, **ASKED, gatemarks.RECOMMEND: rec}])
        item = got["ask"]["items"][0]
        self.assertEqual(item.count("／"), 1, item)
        self.assertNotIn("推し", gatemarks.PUSH_TAIL.sub("", item))

    def test_row_without_recommend_is_as_before(self):
        """元 tests/test_gate_drafts.py の PushCase.test_row_without_recommend_is_as_before。推しの無い行は推しの尾を付けない"""
        got, _ = self.gate(narrows=[{**TP.NARROW, **ASKED}])
        self.assertNotIn("／推し", got["ask"]["items"][0])


if __name__ == "__main__":
    unittest.main()
