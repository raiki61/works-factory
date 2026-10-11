"""独立の目のブロックの値を組む部品。今の works（2aa7c66c の works/）で盤面の上に在った関数を、元の名のまま値とファイルのパスを
引数で受ける形に書き直した物（元の場所は関数ごとの docstring）。目の返りは置き場 eyes_dir の <目>.json（r1・r2・r3・r4・
premise-check）で受ける。標準ライブラリと lib の部品だけ。

- r2_compare_due(design, purpose_text)・r2_premise_invalid(design): 比較役と前提の検算を起こすか
- scalars(diff_text)・scalars_text(s): 規模の数値と、その 1 文
- _human_passed(questions, answer)・carried_section(passed)・r4_gate_items(r4, passed): 修正前の関所で人が通した行と、R4 の問いから
  それを外す照らし
- prompt_texts(...): 目の指示書に差し込む文
- read_design(path): 独立設計の控え（無ければ {"missing": 訳}）
- premise_reason(design): 独立設計が問いが立たないとした訳
- fell_text(fell, ran)・collect(...)・unverified(reason, protected): ブロックの返り
"""
from __future__ import annotations

import json
import pathlib

import changemap
import gatemarks
from design import MISSING as DESIGN_MISSING

R2_PREMISE_HEAD = "前提不成立: "
R2_MISSING_HEAD = f"{DESIGN_MISSING}: "
FELL_MARK = "の筋が落ちた"
# パスの欄を ? にして当たりに数えさせる（黙って空にしない）。元は darkfactory/lib/line_edge.py:111 の PROTECTED_UNKNOWN
PROTECTED_UNKNOWN_ROW = "?: 守りのファイルを確かめられなかった（差分が一覧に触れていないとは言えない）: "
PASS_WORDS = ("approve", "continue")   # 人の関所の通す語（docs/design.md の「書き方の決め」）
# 元 .shared/core/graphloops/rules/review-loop.py:4103 の R4_ROWS（種類・R4 の返りの欄・行の頭）
R4_ROWS = (("regression", "lost", "R4 が BASE から消えたと見た能力: "), ("policy", "policy_conflicts", "R4 が見た人の方針とのぶつかり: "))
EYES = ("r1", "r2", "r3", "r4")
PREMISE = "premise-check"
LANE = {"r1": "R1", "r2": "R2", PREMISE: "R2", "r3": "R3", "r4": "R4"}
RETURN_FIELDS = ("ok", *EYES, "questions", "premise_check", "structure_after", "protected_hits")
STATUSES = ("pass", "redesign-needed", "unverifiable")
VERDICTS = ("resolved", "escalate")
NO_FILE = "返りのファイルが無い"
NO_AFTER = "直しの後の実測: 控えが無い（測っていない run）"   # 元 blk-eyes/lib/eyes.py:93
GREEN_LINE = "最後のテストの認証が通っていない（赤は最後の関所で人が見る）"
DOC_SUFFIXES = (".md",)


def r2_compare_due(design_doc: dict, purpose_text: str) -> bool:
    """元 .shared/core/graphloops/rules/review-loop.py:1228。1 run 1 周なので再発火の条件は「1 周目は必ず」だけが残る"""
    return "missing" not in design_doc and design_doc.get("question_stands") is True and bool(purpose_text.strip())


def r2_premise_invalid(design_doc: dict) -> bool:
    """元 同 :1248（記録の reviews.R2.status == premise-invalid。立てたのは独立設計の question_stands: false）"""
    return "missing" not in design_doc and design_doc.get("question_stands") is False


def premise_reason(design_doc: dict) -> str:
    return design_doc.get("premise_invalid_reason") or design_doc.get("reason") or ""


def changed_files(diff_text: str) -> list[str]:
    return list(changemap.split_diff(diff_text)[0])


def scalars(diff_text: str) -> dict:
    """元 同 :2153 の builtin scalars。差分から数えられる規模の数値（足した行・消した行・文書の足した行・変わったファイル）。
    差分として読めない物は 0 にせず unmeasured に訳を置く"""
    files = changemap.split_diff(diff_text)[0]
    if diff_text.strip() and not files:
        return {"unmeasured": ["累積差分が git の差分の形でない"]}
    rows = [(path, line[:1]) for path, lines in files.items() for line in lines]
    return {"added_lines": sum(mark == "+" for _, mark in rows),
            "deleted_lines": sum(mark == "-" for _, mark in rows),
            "doc_lines": sum(mark == "+" and path.endswith(DOC_SUFFIXES) for path, mark in rows),
            "files": list(files)}


def scalars_text(s: dict) -> str:
    if "unmeasured" in s:
        return "規模の数値は測れなかった: " + "／".join(s["unmeasured"])
    return (f"足した行 {s['added_lines']}・消した行 {s['deleted_lines']}・文書の足した行 {s['doc_lines']}・"
            f"変わったファイル {len(s['files'])} 本（前の周は無い。1 run 1 周）")


def _human_passed(questions: list, answer: dict | None) -> dict:
    """元 .shared/core/gatemarks.py:1244。修正前の関所の答え answer（{decision, text}）が通す語なら、そこで聞いた行 questions の
    うち狭める能力と事前審査の穴の行を {(種類, 頭と推しの尾を外した本文): 1} で返す（台帳の問いの行は数えない）"""
    if not isinstance(answer, dict) or answer.get("decision") not in PASS_WORDS:
        return {}
    out = {}
    for a in questions or []:
        if not isinstance(a, str):
            continue
        m = gatemarks.NARROW_HEAD.match(a)
        f = None if m else gatemarks.FACE_HEAD.match(a)
        if m or f:
            out.setdefault(("regression" if m else f.group(1), gatemarks.PUSH_TAIL.sub("", a[(m or f).end():])), 1)
    return out


def carried_section(passed: dict) -> str:
    """元 .shared/core/gatemarks.py:1259。R4 の指示書の頭に貼る、人が通した行と、同じ物なら本文をそのまま写せという頼み"""
    rows = [f"- [{kind}] {body}" for kind, body in passed]
    return f"{gatemarks.CARRIED_HEAD}\n\n{gatemarks.CARRIED_ASK}\n\n" + "\n".join(rows) if rows else ""


def r4_gate_items(r4: dict | None, passed: dict) -> list[str]:
    """元 .shared/core/gatemarks.py:1266 と review-loop.py:4106 の _r4_gate_items。R4 の消えた能力と方針とのぶつかりの行から、
    人が通した行と種類も頭を除いた本文も同じ物を外す（種類が違えば聞き直す）"""
    r4 = r4 or {}
    got = {"lost": (r4.get("capability_inventory") or {}).get("lost") or [], "policy_conflicts": r4.get("policy_conflicts") or []}
    return [head + x for kind, field, head in R4_ROWS for x in got[field] if (kind, x) not in passed]


def _lines(rows: list[str], none: str) -> str:
    return "\n".join(f"- {r}" for r in rows) if rows else none


def prompt_texts(*, units, fix_units, changed, answer, constraints, green_ok, ripple_file: str, world_file: str,
                 passed: dict) -> dict:
    """目の指示書に差し込む文。値は線から届いたままの形（無い物は None）"""
    unit_rows = [f"{u.get('id')}: {u.get('summary')}（{', '.join(u.get('paths') or [])}）" for u in units or [] if isinstance(u, dict)]
    fix_rows = [f"{u.get('unit_id')}（組 {u.get('group_id')}）: {u.get('status')}——{u.get('reason')}"
                for u in fix_units or [] if isinstance(u, dict)]
    changed = changed if isinstance(changed, dict) else {}
    marks = [f"{k}={str(v).lower()}" for k, v in changed.items() if isinstance(v, bool)]
    return {
        "units_text": _lines(unit_rows, "（単位の目録が渡っていない）"),
        "fixes_text": _lines(fix_rows, "（修正の単位の結末が渡っていない）"),
        "premises_text": _premises(answer, changed, constraints),
        "carried": carried_section(passed),
        "r4_context": "\n".join([
            f"- 波及の一覧: {ripple_file or '（渡っていない）'}",
            f"- 定石の行: {world_file or '（渡っていない）'}",
            f"- 修正の印: {'・'.join(marks) if marks else '（渡っていない）'}"]),
        "green_line": "" if green_ok is True else GREEN_LINE,
    }


def _premises(answer, changed: dict, constraints) -> str:
    said = (answer.get("text") or "").strip() if isinstance(answer, dict) else ""
    late = (f"{answer.get('decision')}: {said}" if said else str(answer.get("decision"))) if isinstance(answer, dict) else ""
    drift = changed.get("premise_drift")
    cons = [f"（{c.get('kind')}）{c.get('text')}" if isinstance(c, dict) else str(c) for c in constraints or []]
    return "\n\n".join([
        "### 独立設計の後に来た人の答え（修正前の関所。独立設計は見ていない）\n\n"
        + (f"- {late}" if late else "（修正前の関所の答えが渡っていない）"),
        "### 前提のずれ（修正の中の申告）\n\n" + ("- 前提のずれの申告が在る（修正の印 premise_drift）" if drift is True
                                         else "- 前提のずれの申告は無い" if drift is False else "（修正の印が渡っていない）"),
        "### 記録の制約\n\n" + (_lines(cons, "（無い）") if constraints is not None else "（記録の制約 premises.json が渡っていない）")])


def read_design(path) -> dict:
    """独立設計の控え design.json。無い・読めない・object でなければ {"missing": 訳}"""
    if path is None:
        return {"missing": "独立設計の指し札が渡っていない"}
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"missing": f"独立設計の控えが読めない: {e}"}
    return doc if isinstance(doc, dict) else {"missing": "独立設計の控えが JSON の object でない"}


def fell_text(fell: list, ran: str = "") -> str:
    """元 blk-eyes/lib/eyes.py:307。fell は [{lane, eye, state}]。尾は元の「<実行基盤の名>の節が落ちた」から名を外した（E3）"""
    names = "・".join(f["lane"] for f in fell)
    head = f"{names} {FELL_MARK}まま {ran} を回した" if ran else f"{names} {FELL_MARK}"
    return head + "（" + "・".join(f"{f['eye']}: {f['state']}" for f in fell) + "。節が落ちた）"


def _read_eye(eyes_dir: pathlib.Path, eye: str) -> tuple[dict | None, str]:
    """(目の返り, 読めない訳)"""
    path = eyes_dir / f"{eye}.json"
    if not path.is_file():
        return None, NO_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"返りのファイルが読めない: {e}"
    return (doc, "") if isinstance(doc, dict) else (None, "返りのファイルが JSON の object でない")


def _protected(protected: dict | None) -> tuple[list, bool]:
    """守りのパスの節の返り（節が落ちていれば None）から (protected_hits, 確かめられたか)。約束の形でない返りも落ちたと数える"""
    if not isinstance(protected, dict) or not isinstance(protected.get("hits"), list):
        return [PROTECTED_UNKNOWN_ROW + "守りのパスの節が落ちた"], False
    return list(protected["hits"]), not protected.get("broken")


def unverified(reason: str, protected: dict | None) -> dict:
    """目を数えられない時の返り（r1〜r4 は unverifiable、ok は false）。protected は collect と同じ"""
    row = {"status": "unverifiable", "reason": reason}
    return {"ok": False, **{e: dict(row) for e in EYES}, "questions": [], "premise_check": None, "structure_after": None,
            "protected_hits": _protected(protected)[0]}


def collect(*, eyes_dir, run_eyes: bool, compare_due: bool, premise_due: bool, design: dict, after_ptr,
            protected: dict | None, passed: dict) -> dict:
    """元 blk-eyes/lib/eyes.py:489 の collect と :291 の fallen。目の返りを eyes_dir/<目>.json から読んでブロックの返りを組む。
    protected は守りのパスの節の返り（節が落ちていれば None）。ok は省いていない目が全部 pass で、前提の検算の道でなく、
    守りのパスを確かめられた時だけ true"""
    eyes_dir = pathlib.Path(eyes_dir)
    hits, guarded = _protected(protected)
    out = {"ok": False, **{e: None for e in EYES}, "questions": [], "premise_check": None, "structure_after": after_ptr,
           "protected_hits": hits}
    if not run_eyes:
        out["ok"] = guarded
        return out
    docs, fell = {}, {}
    due = [*EYES, *([PREMISE] if premise_due else [])]
    if not premise_due and not compare_due:
        due.remove("r2")
    for eye in due:
        docs[eye], why = _read_eye(eyes_dir, eye)
        if docs[eye] is None:
            fell[eye] = {"lane": LANE[eye], "eye": eye, "state": why}
    for eye in ("r1", "r3", "r4"):
        out[eye] = _row(eye, docs.get(eye), fell.get(eye), ran="R4" if eye == "r1" and docs.get("r4") else "")
    if "missing" in design:
        out["r2"] = {"status": "unverifiable", "reason": R2_MISSING_HEAD + str(design["missing"])}
    elif premise_due:
        out["r2"] = {"status": "unverifiable",
                     "reason": R2_PREMISE_HEAD + premise_reason(design)}
        check = docs.get(PREMISE)
        out["premise_check"] = ({"verdict": check["verdict"], "reason": str(check.get("reason"))}
                                if check and check.get("verdict") in VERDICTS
                                else {"verdict": "escalate", "reason": fell_text([fell.get(PREMISE) or _off_contract(PREMISE)])})
    elif compare_due:
        out["r2"] = _row("r2", docs.get("r2"), fell.get("r2"), ran="R4" if docs.get("r4") else "")
    else:
        out["r2"] = {"status": "unverifiable", "reason": "独立設計と比べなかった（問いが立つかの欄か目的の文が無い）"}
    out["questions"] = r4_gate_items(docs.get("r4"), passed)
    out["ok"] = guarded and all(out[e]["status"] == "pass" for e in EYES)
    return out


def _off_contract(eye: str) -> dict:
    return {"lane": LANE[eye], "eye": eye, "state": "返りの判定の語が約束の外"}


def _row(eye: str, doc: dict | None, fell: dict | None, *, ran: str) -> dict:
    if doc is None or doc.get("status") not in STATUSES:
        return {"status": "unverifiable", "reason": fell_text([fell or _off_contract(eye)], ran)}
    return {"status": doc["status"], "reason": str(doc.get("reason"))}
