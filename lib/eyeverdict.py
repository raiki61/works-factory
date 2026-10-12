"""独立の目のブロックの値を組む部品。今の works（2aa7c66c の works/）で盤面の上に在った関数を、元の名のまま値とファイルのパスを
引数で受ける形に書き直した物（元の場所は関数ごとの docstring）。目の返りは置き場 eyes_dir の <目>.json（r1・r2・r3・r4・
premise-check）で受ける。標準ライブラリと lib の部品だけ。

- r2_compare_due(design, purpose_text)・r2_premise_invalid(design): 比較役と前提の検算を起こすか
- scalars(diff_text, x_scalars)・scalars_text(s): 規模の数値と、その 1 文
- _human_passed(questions, answer)・carried_section(passed)・r4_gate_items(r4, passed)・gate_passes(r4, passed): 修正前の関所で
  人が通した行と、R4 の問いからそれを外す照らしと、外した行の控え
- human_items(start_answer, answer)・premise_section(...): R2 の比較役の頭に貼る、独立設計を作った後に分かった前提と、その控え
- prompt_texts(...)・lang_line(lang): 目の指示書に差し込む文
- read_design(path)・read_json(path): 独立設計の控え（無ければ {"missing": 訳}）と、置き場の JSON（無い・読めなければ None）
- premise_reason(design): 独立設計が問いが立たないとした訳
- fell_text(fell, ran)・collect(...)・unverified(reason, protected): ブロックの返り
- write_notes(eyes_dir, ...): 返りの欄の外で最後の関所に出す材料（R2 に渡した前提の控えと『渡されていない』の照らし・人が
  通したので R4 の問いから外した行）を置き場に書く
"""
from __future__ import annotations

import json
import pathlib
import re
import types

import changemap
import design
import gatemarks
import rolekit
import seal

R2_PREMISE_HEAD = "前提不成立: "
R2_MISSING_HEAD = f"{design.MISSING}: "
R2_NOT_COMPARED_HEAD = "独立設計と比べなかった: "
R2_NO_PURPOSE = R2_NOT_COMPARED_HEAD + "目的の文が空"
R2_NO_STANDS = R2_NOT_COMPARED_HEAD + "独立設計の返答に問いが立つかの欄（question_stands）が無い"
FELL_MARK = "の筋が落ちた"
# 元 blk-eyes/lib/eyes.py:115-117 の LATE_HEAD・LATE_ASK
LATE_HEAD = "### 独立設計の後に来た人の答え（独立設計は見ていない）"
LATE_ASK = ("上の人の関所の答えのうち、次の物は独立設計を作った後に来た。設計がこれを置いていないことを設計の漏れに数えず、"
            "答えに照らした目的で突き合わせよ。")
DRIFT_HEAD = "### 前提のずれ（修正の中の申告）"     # 元 同 :118
CONSTRAINT_HEAD = "### 記録の制約"                 # 元 同 :119
NO_CONSTRAINTS = "（記録の制約 premises.json が渡っていない）"
NO_REQUEST = "依頼のファイルが渡っていない"
START_GATE_NODE = "gate-start"   # 線の始めの関所（plan-review が独立設計に貼る人の答えの源）
# 元 .shared/core/graphloops/rules/review-loop.py:4103 の R4_ROWS（種類・R4 の返りの欄・行の頭）
R4_ROWS = (("regression", "lost", "R4 が BASE から消えたと見た能力: "), ("policy", "policy_conflicts", "R4 が見た人の方針とのぶつかり: "))
X_SCALAR = re.compile(r"^x_[a-z0-9_]+$")   # 元 graphs/review-loop.json の p3.fix の x_scalars の patternProperties
EYES = ("r1", "r2", "r3", "r4")
PREMISE = "premise-check"
LANE = {"r1": "R1", "r2": "R2", PREMISE: "R2", "r3": "R3", "r4": "R4"}
RETURN_FIELDS = ("ok", *EYES, "questions", "premise_check", "structure_after", "protected_hits")
VERDICTS = ("resolved", "escalate")
NO_FILE = "返りのファイルが無い"
NO_AFTER = "直しの後の実測: 控えが無い（測っていない run）"   # 元 blk-eyes/lib/eyes.py:93
GREEN_LINE = "最後のテストの認証が通っていない（赤は最後の関所で人が見る）"
DOC_SUFFIXES = (".md",)
DESIGN_PREMISES = "design-premises.json"   # 独立設計の役に貼った物の控え（design.json の隣。元 design.PREMISES_FILE）
R2_PREMISES = "r2-premises.json"           # 比較役に貼った物の控え（置き場。元 eyes.PREMISES_NAME）
PREMISE_INPUTS = "premise-inputs.json"     # 最後の関所に出す R2 の前提の材料（元 eyes-exit.json の premise_inputs）
GATE_PASSES = "gate-passes.json"           # 人が通したので R4 の問いから外した行（元 state.works.gate_passes）


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


def scalars(diff_text: str, x_scalars=None) -> dict:
    """元 同 :2153 の builtin scalars。差分から数えられる規模の数値（足した行・消した行・文書の足した行・変わったファイル）に、
    修正役が足した x_ の数値 x_scalars を足す。測れた分は返し、測れない物は 0 にせず unmeasured に訳を置く"""
    out, why = {}, []
    files = changemap.split_diff(diff_text)[0]
    if diff_text.strip() and not files:
        why.append("累積差分が git の差分の形でない")
    else:
        rows = [(path, line[:1]) for path, lines in files.items() for line in lines]
        out = {"added_lines": sum(mark == "+" for _, mark in rows),
               "deleted_lines": sum(mark == "-" for _, mark in rows),
               "doc_lines": sum(mark == "+" and path.endswith(DOC_SUFFIXES) for path, mark in rows),
               "files": list(files)}
    if x_scalars is not None and not isinstance(x_scalars, dict):
        why.append("修正役の x_scalars が object でない")
    x = x_scalars if isinstance(x_scalars, dict) else {}
    bad = [str(k) for k, v in x.items() if not (X_SCALAR.match(str(k)) and isinstance(v, (int, float)) and not isinstance(v, bool))]
    if bad:
        why.append("修正役の x_scalars の形でない欄: " + "・".join(bad))
    out.update({k: v for k, v in x.items() if str(k) not in bad})
    return {**out, "unmeasured": why} if why else out


def scalars_text(s: dict) -> str:
    parts = ([f"足した行 {s['added_lines']}・消した行 {s['deleted_lines']}・文書の足した行 {s['doc_lines']}・"
              f"変わったファイル {len(s['files'])} 本"] if "added_lines" in s else [])
    parts += [f"{k} {v}" for k, v in s.items() if k.startswith("x_")]
    text = "・".join(parts) if parts else "測れた値は無い"
    return text + ("（測れなかった: " + "／".join(s["unmeasured"]) + "）" if s.get("unmeasured") else "")


def _human_passed(questions: list, answer: dict | None) -> dict:
    """元 .shared/core/gatemarks.py:1244。修正前の関所の答え answer（{decision, text, asked}）が通す語なら、事前審査が関所の項目にした
    行 questions（{kind, text}）のうち狭める能力と事前審査の穴の行を {(種類, 頭と推しの尾を外した本文): 答えた周} で返す（台帳の
    問いの行は数えない。1 run 1 周）"""
    if not isinstance(answer, dict) or answer.get("decision") not in seal.PASS:
        return {}
    out = {}
    for a in gatemarks.row_texts(questions):
        m = gatemarks.NARROW_HEAD.match(a)
        f = None if m else gatemarks.FACE_HEAD.match(a)
        if m or f:
            out.setdefault(("regression" if m else f.group(1), gatemarks.PUSH_TAIL.sub("", a[(m or f).end():])), 1)
    return out


def carried_section(passed: dict) -> str:
    """元 .shared/core/gatemarks.py:1259。R4 の指示書の頭に貼る、人が通した行と、同じ物なら本文をそのまま写せという頼み"""
    rows = [f"- [{kind}] {body}" for kind, body in passed]
    return f"{gatemarks.CARRIED_HEAD}\n\n{gatemarks.CARRIED_ASK}\n\n" + "\n".join(rows) if rows else ""


def _r4_rows(r4: dict | None) -> list[tuple]:
    """R4 の消えた能力と方針とのぶつかりの [(種類, 行の頭, 本文)]"""
    r4 = r4 or {}
    got = {"lost": (r4.get("capability_inventory") or {}).get("lost") or [], "policy_conflicts": r4.get("policy_conflicts") or []}
    return [(kind, head, x) for kind, field, head in R4_ROWS for x in got[field]]


def r4_gate_items(r4: dict | None, passed: dict) -> list[str]:
    """元 .shared/core/gatemarks.py:1266 と review-loop.py:4106 の _r4_gate_items。R4 の消えた能力と方針とのぶつかりの行から、
    人が通した行と種類も頭を除いた本文も同じ物を外す（種類が違えば聞き直す）。外した行は gate_passes が控える"""
    return [head + x for kind, head, x in _r4_rows(r4) if (kind, x) not in passed]


def gate_passes(r4: dict | None, passed: dict) -> list[dict]:
    """元 .shared/core/gatemarks.py:1276-1281。r4_gate_items が外した行を、修正前の関所で人が通した印つきで控える
    （gatemarks._keep の行の形。最後の関所と報告が「人が通した」行として並べる）"""
    return [{"node": gatemarks.R4_GATE_NODE, "round": 1, "by": gatemarks.PASSED_BY_HUMAN, "item": head + x,
             "passed_at": {"node": gatemarks.GATE_NODE, "round": passed[(kind, x)]}}
            for kind, head, x in _r4_rows(r4) if (kind, x) in passed]


def _lines(rows: list[str], none: str = "（無い）") -> str:
    return "\n".join(f"- {r}" for r in rows) if rows else none


# 元 .shared/core/graphloops/rules/review-loop.py:2822-2850 の Markdown の読み（design.named_sections が盤面の rules から引く物）
_MD_FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def _md_lines(text):
    """(行番号, 行) を、コードブロック（``` / ~~~ の囲い）の外の行だけ返す"""
    fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if _MD_FENCE.match(line):
            fence = not fence
        elif not fence:
            yield i, line


def _md_slugs(text):
    """見出しのアンカー（GitHub の書き方: 小文字にし、語の文字・- ・空白以外を落とし、空白を - に。重複は -1, -2 …）"""
    seen, out = {}, set()
    for _, line in _md_lines(text):
        m = design.MD_HEAD.match(line)
        if not m:
            continue
        h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(2).strip())   # 見出しの中のリンクは文字だけが残る
        s = re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-")
        n = seen.get(s, 0)
        seen[s] = n + 1
        out.add(s if n == 0 else f"{s}-{n}")
    return out


_MD_RULES = types.SimpleNamespace(
    MD_LINK=re.compile(r"(?<!!)\[[^\]\n]*\]\((?:<([^>\n]+)>|([^()\s<]+))(?:\s+\"[^\"]*\")?\)"),
    _md_lines=_md_lines, _md_slugs=_md_slugs)


def human_items(start_answer, answer) -> list:
    """関所の答え（{decision, text}。答えの無い関所は None）を record.process.human_items の行の形にし、答えた順に並べる。
    独立設計の控えの seen.count は、plan-review が始めの関所の答えから design.human_answers で数えた数なので、この並びの頭を数える"""
    return [{"round": 1, "node": node, "answer": a.get("decision"), "note": (a.get("text") or "").strip() or None}
            for node, a in ((START_GATE_NODE, start_answer), (gatemarks.GATE_NODE, answer)) if isinstance(a, dict)]


def _constraint_rows(constraints) -> list[str]:
    return [f"（{c.get('kind')}）{c.get('text')}" if isinstance(c, dict) else str(c) for c in constraints or []]


def constraints_text(constraints) -> str:
    """記録の制約（premises.json の constraints。読めなければ None）の行の並び"""
    return _lines(_constraint_rows(constraints)) if constraints is not None else NO_CONSTRAINTS


def premise_section(*, human_items, request_text, repo, changed, constraints, design_seen) -> tuple[str, dict]:
    """元 blk-eyes/lib/eyes.py:389 の premise_section。(比較役の頭に貼る、独立設計を作った後に分かった前提の節の並び,
    貼った物の控え {node, given, withheld, seen, after_design?})。人の関所の答え・依頼が名指した設計書の節・地図は design.premises
    （盤面の口は record.process.human_items・inputs.request・写しの rules の Markdown の読み）の 1 回の呼び出しで組む。依頼の文が
    無ければ（始めの記録か依頼のファイルが無い）名指しの節に「渡っていない」の 1 行を置く。after_design は独立設計の控えの seen の
    数より後の答えで、控えが無ければ数えない（元と同じ）。続けて前提のずれの申告（changed の premise_drift と
    premise_drift_note）と記録の制約を貼る"""
    board = types.SimpleNamespace(record={"process": {"human_items": human_items}},
                                  state={"inputs": {"request": request_text or ""}}, rules=_MD_RULES)
    parts, ledger = design.premises(board, repo)
    if request_text is None:
        parts.insert(len(parts) - 1, f"{design.NAMED_HEAD}\n\n- {NO_REQUEST}")
        ledger["withheld"].append({"kind": "named_section", "what": "依頼", "why": NO_REQUEST})
    if isinstance(design_seen, dict):
        answers = [g["what"] for g in ledger["given"] if g.get("kind") == "human_answer"]
        ledger["after_design"] = answers[design_seen.get("count") or 0:]
        if ledger["after_design"]:
            parts.append(f"{LATE_HEAD}\n\n{LATE_ASK}\n\n{_lines(ledger['after_design'])}")
    changed = changed if isinstance(changed, dict) else None
    drift_flag = changed.get("premise_drift") if changed else None
    drift = [str(changed.get("premise_drift_note") or "").strip() or "（申告の文なし）"] if drift_flag is True else []
    ledger["given"] += [{"kind": "drift", "what": d} for d in drift] + [{"kind": "constraint", "what": c}
                                                                         for c in _constraint_rows(constraints)]
    parts.append(f"{DRIFT_HEAD}\n\n" + (_lines(drift) if drift_flag is not None else "（修正の印が渡っていない）"))
    parts.append(f"{CONSTRAINT_HEAD}\n\n{constraints_text(constraints)}")
    return "\n\n".join(parts), {"node": "r2.compare", **ledger}


def lang_line(lang) -> str:
    """元 .shared/core/rolekit.py:147 の lang_line。言語は始めの記録の lang（空なら依頼文の言語）"""
    return rolekit.lang_line({"lang": lang})


def prompt_texts(*, units, fix_units, changed, constraints, green_ok, ripple_file: str, world_file: str, passed: dict) -> dict:
    """目の指示書に差し込む文。値は線から届いたままの形（無い物は None）"""
    unit_rows = [f"{u.get('id')}: {u.get('summary')}（{', '.join(u.get('paths') or [])}）" for u in units or [] if isinstance(u, dict)]
    fix_rows = [f"{u.get('unit_id')}（組 {u.get('group_id')}）: {u.get('status')}——{u.get('reason')}"
                for u in fix_units or [] if isinstance(u, dict)]
    changed = changed if isinstance(changed, dict) else {}
    marks = [f"{k}={str(v).lower()}" for k, v in changed.items() if isinstance(v, bool)]
    return {
        "units_text": _lines(unit_rows, "（単位の目録が渡っていない）"),
        "fixes_text": _lines(fix_rows, "（修正の単位の結末が渡っていない）"),
        "constraints_text": constraints_text(constraints),
        "carried": carried_section(passed),
        "r4_context": "\n".join([
            f"- 波及の一覧: {ripple_file or '（渡っていない）'}",
            f"- 定石の行: {world_file or '（渡っていない）'}",
            f"- 修正の印: {'・'.join(marks) if marks else '（渡っていない）'}"]),
        "green_line": "" if green_ok is True else GREEN_LINE,
    }


def read_json(path):
    """置き場の JSON（パスが無い・ファイルが無い・読めなければ None）"""
    if path is None:
        return None
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
        return [seal.unknown_row("守りのパスの節が落ちた")], False
    return list(protected["hits"]), not protected.get("broken")


def unverified(reason: str, protected: dict | None) -> dict:
    """目を数えられない時の返り（r1〜r4 は unverifiable、ok は false）。protected は collect と同じ"""
    row = {"status": seal.UNVERIFIABLE, "reason": reason}
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
    ran = "R4" if docs.get("r4") else ""
    for eye in ("r1", "r3", "r4"):
        out[eye] = _row(eye, docs.get(eye), fell.get(eye), ran=ran if eye == "r1" else "")
    if "missing" in design:
        out["r2"] = {"status": seal.UNVERIFIABLE, "reason": R2_MISSING_HEAD + str(design["missing"])}
    elif premise_due:
        out["r2"] = {"status": seal.UNVERIFIABLE, "reason": R2_PREMISE_HEAD + premise_reason(design)}
        check = docs.get(PREMISE)
        out["premise_check"] = ({"verdict": check["verdict"], "reason": str(check.get("reason"))}
                                if check and check.get("verdict") in VERDICTS
                                else {"verdict": "escalate", "reason": fell_text([fell.get(PREMISE) or _off_contract(PREMISE)], ran)})
    elif compare_due:
        out["r2"] = _row("r2", docs.get("r2"), fell.get("r2"), ran=ran)
    else:
        out["r2"] = {"status": seal.UNVERIFIABLE, "reason": R2_NO_PURPOSE if design.get("question_stands") is True else R2_NO_STANDS}
    out["questions"] = r4_gate_items(docs.get("r4"), passed)
    out["ok"] = guarded and all(out[e]["status"] == seal.PASSED for e in EYES)
    return out


def write_notes(eyes_dir, *, design_ledger, passed: dict) -> None:
    """元 blk-eyes/lib/eyes.py:525-534 の premise_inputs と gatemarks.r4_gate_items の gate_passes。返りの欄の外で最後の関所に
    出す材料を eyes_dir に書く: PREMISE_INPUTS に R2 の 2 つの役へ渡した前提の控え（design は独立設計の控え design_ledger、
    compare は prep が書いた R2_PREMISES）と、比較役の返りの『渡されていない』の文（claims）と、そのうち compare の given に
    当たる物（compare.claims_given）。拒まない・判定を書き換えない。GATE_PASSES に人が通したので R4 の問いから外した行"""
    eyes_dir = pathlib.Path(eyes_dir)
    compare = read_json(eyes_dir / R2_PREMISES)
    claims = design.claims_unpassed(_read_eye(eyes_dir, "r2")[0])
    if isinstance(compare, dict):
        compare["claims_given"] = design.claims_given(claims, compare.get("given"))
    notes = {PREMISE_INPUTS: {"design": design_ledger, "compare": compare, "claims": claims},
             GATE_PASSES: gate_passes(_read_eye(eyes_dir, "r4")[0], passed)}
    for name, doc in notes.items():
        (eyes_dir / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _off_contract(eye: str) -> dict:
    return {"lane": LANE[eye], "eye": eye, "state": "返りの判定の語が約束の外"}


def _row(eye: str, doc: dict | None, fell: dict | None, *, ran: str) -> dict:
    if doc is None or doc.get("status") not in seal.STATUSES:
        return {"status": seal.UNVERIFIABLE, "reason": fell_text([fell or _off_contract(eye)], ran)}
    return {"status": doc["status"], "reason": str(doc.get("reason"))}
