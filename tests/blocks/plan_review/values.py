"""事前審査の block の試験と筋書きが共に使う値と助け（docs/design/plan-review.md の 15.3）。

値は今の試験（tests/workflows/test_plan_review.py）の stats.py の例（tests/e2e/target-seed を対象の木にする）の写しで、例の run
（df5e111f・4bcd3c2e）の形（項目と欄・判定の単位と見立てと先行例・独立設計の返答・世界の解の行・2 往復目の往復の記録）をなぞる。
対象の名前・置き場は使い捨ての木に置き換える。

- item(unit, n)・fields(unit)・face(key, …)・review(*faces)・proposal(*items, answers=None)・fields_doc(*units, rnd=1)・judgment(…)
- Block(case): kit.Run に対象の木（target-seed を commit した物）と port の値の置き場を足した物。put(rel, doc) は run directory に
  ファイルを置いて pointer の字を返す。plan_inputs(**over) は形 plan の port の値（pointer の字）。intake(**inputs) は入口を回す
"""
import json
import shutil

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = "plan-review"
SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
UNIT_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
UNIT_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
UNIT_EXTRA = "stats.py median: 中央値が無い"
PURPOSE = "PURPOSE-MARK-7731 統計の関数が正しい値を返す（平均は定義どおりに割り、範囲の外の値は近い端に切り詰める）"
FRAMING = "FRAMING-MARK-2208 分母と上限の 2 つの誤り"
ONE_SHOT = "ONESHOT-MARK-5150 2 か所を直す"
PLAN_MARK = "PLAN-MARK-6060"
RIPPLE_MARK = "RIPPLE-MARK-9902"
POLICY_TEXT = "- 環境の組み立てを 1 か所の関数に寄せる。\n- 読むだけの gh を PATH の頭に置く今の形は保つ。"
UNITS = [{"key": UNIT_MEAN, "label": "block", "disposition": "fix", "reason": "分母が 1 少ない"},
         {"key": UNIT_CLAMP, "label": "block", "disposition": "fix", "reason": "上限で lo を返す"}]
PRECEDENTS = [{"key": UNIT_MEAN, "problem": "空でない列の平均", "source": "https://docs.python.org/3/library/statistics.html#statistics.mean",
               "verdict": "adopt", "reason": "平均の定義を公式に合わせる"},
              {"key": UNIT_CLAMP, "problem": "範囲の外の値の切り詰め", "source": "https://numpy.org/doc/stable/reference/generated/numpy.clip.html",
               "verdict": "adapt", "reason": "上限を超えた値の扱いを合わせる"}]
RIPPLE = {"items": [{"item": 1, "unit_keys": [UNIT_MEAN], "names": [], "uncovered": []},
                    {"item": 2, "unit_keys": [UNIT_CLAMP],
                     "names": [{"name": "clamp", "files": 2, "code": ["stats.py:12"],
                                "tests": ["test_stats.py::TestStats::test_clamp_above_range"]}],
                     "uncovered": [{"id": "h1", "kind": "test", "at": "test_stats.py::TestStats::test_clamp_above_range",
                                    "name": "clamp"}]}],
          "overlaps": [{"at": "stats.py", "items": [1, 2]}]}
DESIGN_TEXT = "上限は入口 1 箇所で掛け、各所では掛け直さない。平均は定義どおりに割る"
DESIGN_OK = {"question_stands": True, "reason": "問いは立っている", "design": DESIGN_TEXT,
             "elements": [{"id": "D1", "adds": ["上限の入口"], "removes": []}]}
DESIGN_NOT = {"question_stands": False, "reason": "問いは立たない", "premise_invalid_reason": "stats.py:4 は既に正しい", "design": ""}
WORLD_ROW = {"finding": 1, "where": "依頼", "class_id": "w-1", "problem": "空でない列の平均の求め方", "activity": "平均を求める",
             "practice": "要素の数で割る", "sources": [{"url": "https://docs.python.org/3/library/statistics.html", "quote": "mean"}],
             "applies": "数の列の平均", "not_applies": "", "basis": "web",
             "versus": {"proposed": "len(xs) - 1 で割る", "verdict": "differs", "challenge": "依頼は 1 少ない数で割る。定石は要素の数で割る"}}
NO_EFFECT = "上限の枝の外の値か、直した後の値だけを断言していて期待は変わらない"
REASON = "案を全部読み、写し・入口・契約のずれ・死んだ道・範囲・後退・方針・先行例を確かめた"
FACES_NONE = "写し・入口・契約のずれ・死んだ道・範囲の膨張・後退・方針・先行例を全部確かめて穴が無い"


def frow(path, *adds, op="modify") -> dict:
    """修正案の項目の files の 1 行（home・considered は照らしに当たらない既定）"""
    return {"path": path, "op": op, "responsibility": "この行の受け持ち",
            "home": {"concept": f"{path} の考え（{'・'.join(adds) or op}）", "why": "この行の path が住処だから"},
            "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}],
            "symbols": [{"name": n, "change": "add"} for n in adds]}


def item(unit, n=1, **extra) -> dict:
    """修正案の項目の行（修正案の役の返答の plan[] の 1 行。unit_keys は単位の名）"""
    return {"unit_keys": [unit], "approach": f"{PLAN_MARK} 項目 {n} の直し: {unit} を直す",
            "files": [frow("stats.py", f"helper_{n}")], "shrink_first": "要らない", "narrows": [], **extra}


def fields(unit=UNIT_MEAN) -> dict:
    """修正案の項目の works の欄（plan-fields.json の fields[] の 1 行）"""
    return {"route": "direct", "route_why": "1 行の直しで済む", "tests": [], "rewrite_tests": [], "refactor": "無い",
            "allowed_paths": ["stats.py"], "out_of_scope": [], "structure": []}


def proposal(*items, answers=None) -> dict:
    doc = {"plan": list(items)}
    if answers is not None:
        doc["block_answers"] = list(answers)
    return doc


def fields_doc(*items, rnd=1) -> dict:
    return {"round": rnd, "fields": [fields(it["unit_keys"][0]) for it in items]}


def judgment(units=None, precedents=(), **extra) -> dict:
    return {"units": list(units if units is not None else UNITS), "questions": [], "framing": FRAMING, "one_shot": ONE_SHOT,
            "precedents": list(precedents), **extra}


def face(key, unit=UNIT_MEAN, kind="contract_drift", severity="block", reach="breaks_fix", **extra) -> dict:
    """事前審査の穴の行（unit_keys は単位の名か番号）"""
    return {"key": key, "unit_keys": [unit], "kind": kind, "where": "stats.py mean",
            "why": f"{key} の穴になる筋道を 20 字以上で書いた行", "severity": severity, "reach": reach, **extra}


def review(*faces, **extra) -> dict:
    out = {"faces": list(faces), "shrink": [], "reason": REASON}
    if not faces:
        out["faces_none"] = FACES_NONE
    return {**out, **extra}


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class Block(kit.Run):
    """事前審査の block の run: 対象の木は target-seed を commit した物。port の値は run directory に置いたファイルの pointer で渡す"""

    def __init__(self, case):
        super().__init__(case, BLOCK)
        for path in SEED.iterdir():
            if path.is_file():
                shutil.copy(path, self.repo / path.name)
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "seed")

    def put(self, rel: str, doc, raw: bool = False) -> str:
        """run directory の rel に doc を書き、その pointer の字を返す（raw は字のまま書く）"""
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if raw else dump(doc), encoding="utf-8")
        return self.pointer(rel)

    def world(self, *rows) -> str:
        return self.put("judge/world/world.jsonl", "".join(dump(r) + "\n" for r in rows), raw=True)

    def structure(self, rows=(), status="ok") -> str:
        self.put("eyes/structure/design.jsonl", "".join(dump(r) + "\n" for r in rows), raw=True)
        return self.put("eyes/structure/state.json", {"status": status, "reason": "", "design_file": str(self.artifacts / "eyes/structure/design.jsonl"),
                                                 "wall_s": 0})

    def plan_inputs(self, items=None, *, answers=None, rnd=1, **over) -> dict:
        """形 plan の port の値（修正案・欄・判定・波及の一覧は pointer。木は off）。over で足し・置き換える"""
        items = list(items) if items is not None else [item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)]
        return {"proposal": self.put(f"plan/r{rnd}/p2.fix_plan.json", proposal(*items, answers=answers)),
                "fields": self.put(f"plan/r{rnd}/plan-fields.json", fields_doc(*items, rnd=rnd)),
                "judgment": self.put("judge/judgment.json", judgment()), "purpose": PURPOSE,
                "ripple": self.put(f"plan/r{rnd}/ripple.json", {**RIPPLE, "note": RIPPLE_MARK}),
                "structure": self.structure(), "tree": "off", **over}

    def intake(self, **inputs) -> dict:
        return self.script("intake", **inputs)

    def read(self, name: str):
        return json.loads((self.artifacts / name).read_text(encoding="utf-8"))
