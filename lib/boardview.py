"""事前審査のブロック（plan-review）だけが使う、盤面の無い run の見え方と、このブロックの支度・受け付け・返りの組み立て。

今の works の事前審査と独立設計の部品（gatemarks・converge・design・planblk・planmarks）は、盤面 b を引数に取る形のまま lib/ に在る。
このブロックは盤面を持たないので、入力の指し札の先のファイルを 1 つの置き場（呼び手が渡す folder。run の置き場の plan-review/）に
写し、その置き場の上で今の works の盤面と同じ形の読むだけの見え方（view）と書き先（place）を組んで、それらの関数に渡す。
書き手が書いた控え（往復の控え plan-converge.json・決め手の控え gate-marks.json・拒みの控え）は同じ置き場に置き、見え方がそのまま
読む。run をまたいで持たない。ほかのブロックは使わない。

- view(folder, inputs, review=None)・place(folder): 見え方と書き先（今の works の tests/test_plan_gate.py の GateBase.gate が組む偽の
  盤面と同じ形。元 works/blk-plan/lib/planblk.py の盤面の読み）。見え方は stop を持たない
- rules: 見え方が b.rules で渡す、写しの rules と検証器の表のうち、このブロックの部品が読む物の書き直し（元の名のまま）
- open_pass: 差し込みの頭（元 planblk.snap と design.due・design.snap。works/blk-plan/lib/planblk.py:1062・
  works/.shared/core/design.py:492）。形 replan の項目（replan_items。元 works/.shared/core/replan.py:291 の material）と、
  修正前の関所の答えの控え（take_gate_answers。元 graphloops/rules/review-loop.py:4134 の human_gate_answered）と、それを受けた後の
  方針の文書の版（passed_version。線の節 answer-before-fix が呼ぶ）
- 方針の文書: 固めた版（始めの記録の欄 policy。置き場と写しは policy.locate・snapshot）・変化（policy_change・change_row。元
  graphloops/rules/policy_input.py）。役に貼る節は固めた版の写しの policy.section
- r2_prompt・check_design: 独立設計の支度と受け付け（元 works/.shared/core/design.py:528 の prep・:586 の check_design・
  :603 の accept_reply）
- review_material・take_review: 事前審査の支度と受け付け（元 works/blk-plan/lib/planblk.py:1085 の prep・:1134 の take・
  :1178 の with_converge）
- collect: 返す節の組み立て（元 works/blk-plan/lib/planblk.py:1441 の collect。形 replan の関所の項目は replan_asks。元
  works/.shared/core/replan.py:620 の gate）
"""
from __future__ import annotations

import copy
import datetime
import difflib
import json
import pathlib
import re
import shutil
import types

import accept
import concepthome
import converge
import design
import gate_axes
import gatemarks
import gatepolicy
import planblk
import planmarks
import policy
import promptsection
import purpose as purposelib
import rolekit
import startrec
import structmark
import worldmark
from engine.util import Reject

PLAN_NODE = "p2.fix_plan"
REVIEW_NODE = "p2.plan_review"
PURPOSE_NODE = "p0.purpose"
DIAGNOSE_NODE = "p2.diagnose"
FOLDER = "plan-review"                  # run の置き場の中のこのブロックの置き場（呼び手が run の置き場に足して folder にする）
OPEN_FILE = "open.json"                 # open_pass が置く見え方の材料（後の支度・受け付け・返りが読む）
OPEN_ERROR = "open-error.txt"           # 差し込みの頭の節が落ちた訳（返す節の訳に載る。節が書く）
JUDGMENT_COPY = "judgment.json"         # 判定の写し（planblk.lib_section が state.outputs から引く）
EXCLUDED_FILE = "pr-excluded.json"      # 判定の隣の並行 PR の外した範囲（在れば写して役の頭に名指す）
PURPOSE_REVIEW_FILE = purposelib.REVIEW_FILE   # 判定の隣の目的の監査の受けた返答（judge が必ず置く。無い・読めない時は {} で読む）
POLICY_FILE = "policy.json"             # 方針の文書を固めた版 {named, path, sha256, copy, amendments}（始めの記録の欄 policy から置く）
POLICY_DIR = policy.DIR
POLICY_CHANGED = "policy_changed"       # 関所の項目の種類（方針の文書が固めた版から変わった）
GATE_ASKED_FILE = "gate-asked.json"     # 返した関所の項目 {文: {kind, policy_change?}}（入力 gate_answers の通した行の種類と方針の変化を引く）
GATE_ANSWERS_FILE = "gate-answers.json"  # 入力 gate_answers を写した人の関所の答えの行（gatemarks が読む process.human_items の形）
PASS_WORDS = ("continue", "approve")    # 関所を通す答えの語（docs/design.md の人の関所の語）
WORLD_COPY = f"world/{worldmark.WORLD_FILE}"
STRUCTURE_ROWS = "structure/design.jsonl"
PASS_DIR = "pass-{k}"
PREMISES_FILE = "design-premises.json"  # R2 に貼った物の控え {node, given, withheld, seen, claims?}
R2_TREE = "r2-tree.json"                # 独立設計の役を起こす前の作業ツリーの姿
R2_PROMPT = "r2-prompt.md"
TREE_FILE = "tree.json"                 # 事前審査の役を起こす前の作業ツリーの姿（pass-<k>/ の中）
PROMPT_FILE = "prompt.md"
REVIEW_FILE = "review.json"
PASSES_FILE = gatemarks.PASSES_FILE
GATE_FILE = gatemarks.GATE_RECORD_FILE
FENCE = rolekit.GIVE_UP_AFTER           # 往復の柵（線の loop_group の 3 回と同じ数）
TREE_FEATURE = "review_tree"
# 元 works/.shared/core/entry.py:1228 と works/.shared/core/design.py:104
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "
PREMISE_MISS = "premise_invalid_reason の名指しが固めた版の実物に当たらない（追跡されたファイルと、その行の範囲を名指せ）: "
NO_TREE = "役を起こす前の作業ツリーの控え {name} が無い（支度の節が走っていない）"
# 元 works/.shared/core/design.py:82。指示書は「渡すのは元の目的と実測した制約だけ」と書くので、貼った前提をこの節で読み替える
DESIGN_PREMISE_REREAD = ("下の指示書の「渡すのは元の目的と実測した制約だけである」は、この run では、この節（人の関所の答え・"
                         "依頼が名指した設計書の節・対象のリポジトリの地図）も渡していると読み替えよ。")
PURPOSE_HEAD = "元の目的:"
CONSTRAINTS_HEAD = "実測した制約（kind=仮説 のものは所与にするな）:"
NOT_GIVEN_START = "依頼が名指した設計書の節: 渡っていない（線が始めの記録を渡していない。依頼の本文を読めない）"
DEFAULTS_HEAD = "線が渡していない入力を既定で読んだ: "
DEFAULT_START = ("start（始めの記録）が null——無人でない・設計だけでない・依頼のファイル無し（依頼の引用の決め手は照らせないので"
                 "人に回る）・方針の文書無し・事前審査の木は auto として読んだ")
DEFAULT_ANSWERS = "answers（人の関所の答え）が null——独立設計に貼る人の答えは無い"
PURPOSE_REVIEW_UNREAD = (f"判定の隣の {PURPOSE_REVIEW_FILE}（目的の監査の受けた返答）を読めない（{{why}}）——監査は無かったとして読み、"
                         "独立設計を目的の『狭めている』では止めない")
REQUEST_UNREAD = "依頼のファイル {path} を読めない（{why}）——依頼の本文は空として読み、依頼が名指した設計書の節は渡っていない"
# 案の直しの事前審査の頼みと項目の節（元 works/.shared/core/replan.py:121・126-129）
REVIEW_ASK_REPLAN = ("下は承認済みの修正案の項目の前の形と、修正の段の申し出と裁定を受けて修正案の役が直した形。直した形が裁定の文の"
                     "指摘を直したか、新しい後退（regression）や方針とのぶつかり（policy）を作らないかを見よ。前の形に在った穴を"
                     "挙げ直さない。穴は faces に挙げよ。")
ITEM_HEAD = promptsection.Section("## 直す項目 {n}（承認済みの修正案の項目の番号）", source="fn:boardview._replan_section")
OLD_HEAD = promptsection.Section("### 前の項目（承認済み。機械が貼った）", source="fn:boardview._replan_section")
NEW_HEAD = promptsection.Section("### 直した項目（修正案の役が返した形。機械が貼った）", source="fn:boardview._replan_section")
ROW_HEAD = promptsection.Section("### 修正の段の申し出と裁定（{id}）", source="fn:boardview._replan_section")
# 元 works/.shared/core/conflict.py:94-96 の申し出の欄の名
WHY_FIELD = "why_both_cannot_hold"
KIND_FIELD = "kind"
WHICH_FIELD = "which_is_right"
NO_APPROVED = "案の直しの事前審査なのに、置き場に承認済みの修正案（前の差し込みの往復の控えと凍結した欄）が無い"
REPLAN_ASKED = ("人に聞く直した項目 {n}（単位 {units}）: 約束の欄の変化 {changed}・人に聞く穴 {faces}"
                "（前の項目と直した項目は {file}）")   # 元 works/.shared/core/replan.py:162・:593 の関所の節の 1 行
REPLAN_FILE = "replan.json"             # 案の直しの項目 [{item, units, rows, old, new, contract_changed, human_faces, widened, ask}]（pass-<k>/ の中）
UNIT_ROW_KEYS = ("key", "label", "disposition", "reason")
REVIEW_MD = "REVIEW.md"
# 元 works/.shared/core/gl-prompts/prompts/review-loop/p2.plan_review.md:4・:7
UNITS_LINE = "直す単位（各行の `no` は機械が振った番号。**key を写さず no の整数で指せ**——機械が名前に戻して記録する）: "
REPO_LINE = "リポジトリ: {repo}（読む版: `{rev}`）　BASE: `{base}`　観点の正本: {review_md}"
DIFF_MISSING = "固定した版の写しが置き場に無い（消えた）——差分を作れない"   # 元 graphloops/rules/policy_input.py:94
GIVEN_UP_FACES = "事前審査の受け付けが諦めた: "


class Missing(Exception):
    """open_pass の材料が無い・読めない（返す節は failed で偽の結末を返す）"""


# ---------------------------------------------------------------- 写しの rules と検証器の表の書き直し
# 元 works/.shared/core/graphloops/rules/review-loop.py。名は元のまま
MD_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\((?:<([^>\n]+)>|([^()\s<]+))(?:\s+\"[^\"]*\")?\)")   # :2822
MD_FENCE = re.compile(r"^\s{0,3}(```|~~~)")                                                      # :2823
EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")                                                       # :467
HUMAN_FACE_KINDS = ("regression", "policy")                                                     # :4084


def _md_lines(text):
    """(行番号, 行) を、コードブロック（``` / ~~~ の囲い）の外の行だけ返す（元 review-loop.py:2827）"""
    fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if MD_FENCE.match(line):
            fence = not fence
        elif not fence:
            yield i, line


def _md_slugs(text):
    """見出しのアンカー（GitHub の書き方。重複は -1, -2 …）の集合（元 review-loop.py:2837）"""
    seen, out = {}, set()
    for _, line in _md_lines(text):
        m = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1).strip())
        s = re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-")
        n = seen.get(s, 0)
        seen[s] = n + 1
        out.add(s if n == 0 else f"{s}-{n}")
    return out


def blank(s, min_len):
    """役が埋める自由文が空同然か（表と長さの両方で見る。元 review-loop.py:480）"""
    t = (s or "").strip()
    return t.lower() in EMPTY or len(t) < min_len


def purpose_findings_vetted(b):
    """記録の目的監査の findings が裏取りの柵を通った形（全部 cite を持つ。空は偽）か（元 review-loop.py:398）"""
    rows = ((b.record.get("process", {}).get("purpose_review", {}) or {}).get("findings")) or []
    return all(isinstance(r, dict) and r.get("cite") for r in rows) if rows else False


def purpose_unusable(b):
    """目的の出典が R2 に使えない理由（None／目的不明／狭めている。元 review-loop.py:403）"""
    if (b.latest_output(PURPOSE_NODE) or {}).get("source") == "目的不明":
        return "目的不明"
    pr = b.record.get("process", {}).get("purpose_review", {}) or {}
    return "狭めている" if pr.get("verdict") == "狭めている" and purpose_findings_vetted(b) else None


def _keys_once(rows, label):
    """行の key が重複しないか（重複の文の一覧。元 review-loop.py:3067）"""
    seen, errs = set(), []
    for i, r in enumerate(rows):
        if r["key"] in seen:
            errs.append(f"{label}[{i}] の key が重複: {r['key'][:60]}")
        seen.add(r["key"])
    return errs


def plan_review_output(b, nid, out, item):
    """事前審査の穴は案の単位を指し、key は一意。穴も別案も無いなら faces_none を書く。入口の穴は no_add を併記する
    （元 review-loop.py:3096。out の unit_keys は単位の名に戻した物）"""
    planned = {k for p in (b.output_of_round(PLAN_NODE, b.round) or {}).get("plan") or [] for k in p["unit_keys"]}
    rows = (out.get("faces") or []) + (out.get("shrink") or [])
    errs = _keys_once(rows, "faces・shrink")
    for r in rows:
        stray = [k for k in r["unit_keys"] if k not in planned]
        if stray:
            errs.append(f"{r['key'][:40]}: unit_keys {[str(k)[:40] for k in stray]} は修正案に無い")
    if not rows and blank(out.get("faces_none"), 20):
        errs.append("穴も別案も挙げないなら faces_none に何を確かめて無いと言えるかを書け")
    errs += [f"faces の '{f['key'][:40]}'（entrance）に no_add（柵や入口を足さずに閉じる形。無理なら無理な理由）が無い"
             for f in out.get("faces") or [] if f["kind"] == "entrance" and blank(f.get("no_add"), 20)]
    if errs:
        raise Reject(f"{nid}: " + "; ".join(errs))


# 元 works/.shared/core/scripts/review-record.py:135・:140・:343（検証器の素材の状態の表と、人に聞く状態の問い）。表の列は
# このブロックの部品が読む blocks（gatemarks.unmeasured）だけ。状態の語の持ち主は gatemarks.MATERIAL_WORDS
BLOCKING = ("awaiting_human", "not_run")
STATUS = {s: types.SimpleNamespace(blocks=s in BLOCKING) for s in gatemarks.MATERIAL_WORDS}
ASKING = gatemarks.ASKING
VALIDATOR = types.SimpleNamespace(STATUS=STATUS, ASKING=ASKING)


def validator_module(b):
    return VALIDATOR


rules = types.SimpleNamespace(
    MD_LINK=MD_LINK, _md_lines=_md_lines, _md_slugs=_md_slugs, purpose_unusable=purpose_unusable,
    HUMAN_FACE_KINDS=HUMAN_FACE_KINDS, plan_review_output=plan_review_output, validator_module=validator_module)


# ---------------------------------------------------------------- 見え方と書き先
def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _tracer(folder: pathlib.Path):
    def trace(op, **row):
        with open(folder / planmarks.TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": _now(), "op": op, **row}, ensure_ascii=False) + "\n")
    return trace


def place(folder) -> types.SimpleNamespace:
    """書き手（converge の note_plan・note_answers・record_pass・stash_rejects）の書き先: round（いつも 1）・dir・work(name)・
    trace(op, **row)。置き場 folder の本物のファイルに書く"""
    d = pathlib.Path(folder)
    return types.SimpleNamespace(round=1, dir=d, work=lambda name: d / name, trace=_tracer(d))


def view(folder, inputs: dict, review: dict | None = None) -> types.SimpleNamespace:
    """読むだけの見え方。inputs は open_pass が置いた材料（read_open の返り）、review は今の往復の受けた事前審査の返答。round は
    いつも 1（converge.read は控えの周が見え方の周と違うと控えを捨てるので、同じ run の往復と案の直しを同じ周に積む）。前提の
    planblk の木の関数が読みと書きを同じ b で行うので、work(name)・scope_root・trace は置き場の本物のファイルを指す"""
    d = pathlib.Path(folder)
    outs = {PLAN_NODE: inputs.get("plan"), REVIEW_NODE: review}
    names = list(inputs.get("names") or [])
    record = {"units": copy.deepcopy(inputs.get("units") or []), "questions": copy.deepcopy(inputs.get("questions") or []),
              "materials": copy.deepcopy(inputs.get("materials") or {}),
              "process": {"human_items": copy.deepcopy(inputs.get("human_items") or []),
                          "precedents": copy.deepcopy(inputs.get("precedents") or []),
                          "diagnosis": copy.deepcopy(inputs.get("diagnosis") or {}),
                          "purpose_review": copy.deepcopy(inputs.get("purpose_review") or {})}}
    state = {"inputs": {"cwd": inputs.get("cwd") or ".", "request": inputs.get("request") or "",
                        "policy_md": inputs.get("policy_md") or "", "review_rev": inputs.get("rev") or "HEAD"},
             "works": {}, "outputs": {DIAGNOSE_NODE: {"file": JUDGMENT_COPY}}}
    return types.SimpleNamespace(
        round=1, dir=d, scope="", scope_root=d, record=record, state=state, rules=rules,
        review_body=inputs.get("review_body") or "",
        faces_schema={x: copy.deepcopy(((inputs.get("review_schema") or {}).get("properties") or {}).get(x) or {})
                      for x in ("faces", "shrink")},
        design_schema=copy.deepcopy(inputs.get("design_schema") or {}),
        work=lambda name: d / name, trace=_tracer(d),
        output_of_round=lambda node, rnd: copy.deepcopy(outs.get(node)) if rnd == 1 else None,
        latest_output=lambda node: copy.deepcopy(inputs.get("purpose")) if node == PURPOSE_NODE else None,
        pointer_rows=lambda node: {"pointers": [{"names": list(names)}]})


def _read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _write_json(path, doc) -> pathlib.Path:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def _sibling(pointed, name: str):
    """指し札の先のファイルの横の name（無ければ None）"""
    p = pathlib.Path(pointed).parent / name
    return p if p.is_file() else None


def _purpose_review(judgment) -> tuple[dict, str]:
    """判定の隣の purpose-review.json（目的の監査の受けた返答。judge が必ず置く）と、読めなかった訳（読めれば ""）。
    無い・読めない・object でない時は {} で読む"""
    p = pathlib.Path(judgment).parent / PURPOSE_REVIEW_FILE
    try:
        doc = _read_json(p)
    except (OSError, ValueError) as e:
        return {}, PURPOSE_REVIEW_UNREAD.format(why=type(e).__name__)
    if not isinstance(doc, dict):
        return {}, PURPOSE_REVIEW_UNREAD.format(why=f"object でなく {type(doc).__name__}")
    return doc, ""


def read_open(folder) -> dict:
    """open_pass が置いた材料（無い・読めなければ Missing。差し込みの頭の節が落ちた訳が在ればそれを載せる）"""
    p = pathlib.Path(folder) / OPEN_FILE
    try:
        doc = _read_json(p)
    except (OSError, ValueError) as e:
        err = p.with_name(OPEN_ERROR)
        why = err.read_text(encoding="utf-8") if err.is_file() else str(e)
        raise Missing(f"見え方の材料 {p} が無い（差し込みの頭の節が通っていない）: {why}") from None
    if not isinstance(doc, dict):
        raise Missing(f"見え方の材料 {p} が object でない")
    return doc


def pass_dir(folder, k: int) -> pathlib.Path:
    return pathlib.Path(folder) / PASS_DIR.format(k=k)


def human_items(answers) -> list:
    """人の関所の答え（承認の節の返り {decision, text} か、その並び）を design.human_answers が読む行 {round, node, kinds, answer, note}
    に。null・形の違う値は無い"""
    return [{"round": 1, "node": "gate-start", "kinds": [], "answer": a["decision"], "note": a.get("text") or ""}
            for a in _answer_rows(answers)]


def _answer_rows(answers) -> list:
    rows = answers if isinstance(answers, list) else [answers] if isinstance(answers, dict) else []
    return [a for a in rows if isinstance(a, dict) and a.get("decision")]


def take_gate_answers(folder, gate_answers) -> list:
    """入力 gate_answers（修正前の関所の答え {decision, text, asked: [通した行の文…]} か、その並び。null は無い）を、gatemarks が
    聞き直さない行と読む process.human_items の行 {round, node: gatemarks.GATE_NODE, kinds, asked, answer, note} にして
    GATE_ANSWERS_FILE に積み（同じ行は積み増さない）、積んだ全部を返す。行の種類は前の差し込みが返した関所の項目の控え
    GATE_ASKED_FILE から引く。通した行に方針の変化の行が在れば、その版を固め直す（元 graphloops/rules/review-loop.py:4137-4142）"""
    d = pathlib.Path(folder)
    have = _read_json(d / GATE_ANSWERS_FILE) if (d / GATE_ANSWERS_FILE).is_file() else []
    asked_of = _read_json(d / GATE_ASKED_FILE) if (d / GATE_ASKED_FILE).is_file() else {}
    for a in _answer_rows(gate_answers):
        texts = [x for x in a.get("asked") or [] if isinstance(x, str)]
        answer = "continue" if a["decision"] in PASS_WORDS else a["decision"]
        row = {"round": 1, "node": gatemarks.GATE_NODE,
               "kinds": sorted({(asked_of.get(x) or {}).get("kind") or "" for x in texts} - {""}),
               "asked": texts, "answer": answer, "note": a.get("text") or ""}
        if row in have:
            continue
        have.append(row)
        if answer != "continue":
            continue
        for x in texts:
            ch = (asked_of.get(x) or {}).get("policy_change")
            if ch and (d / POLICY_FILE).is_file():
                pol = _read_json(d / POLICY_FILE)
                pol.setdefault("amendments", []).append({**ch, "note": row["note"]})
                pol["path"], pol["sha256"], pol["copy"] = (ch["path"] if ch["to"] else ""), ch["to"], ch["to_copy"]
                _write_json(d / POLICY_FILE, pol)
    _write_json(d / GATE_ANSWERS_FILE, have)
    return have


def passed_version(folder, gate_answers) -> dict | None:
    """修正前の関所の答えを受けた後の方針の文書の版 {named, path, sha256, copy}。答えを take_gate_answers で控えに積み（通した方針の
    変化はここで固め直す）、置き場の POLICY_FILE を読む。この run の差し込みが版を置いていなければ None（線の節 answer-before-fix
    が始めの記録の欄 policy をこの版で書き直す）"""
    d = pathlib.Path(folder)
    if not (d / POLICY_FILE).is_file():
        return None
    take_gate_answers(d, gate_answers)
    return policy.version({"policy": _read_json(d / POLICY_FILE)})


def tree_word(start: dict | None) -> str:
    """始めの記録の機能の切り替えから事前審査の木の語（on・off・auto。名指しが無ければ auto）"""
    doc = start or {}
    if TREE_FEATURE in (doc.get("features_on") or []):
        return "on"
    if TREE_FEATURE in (doc.get("features_off") or []):
        return "off"
    return "auto"


def _request(start: dict | None) -> tuple:
    """始めの記録が名指す依頼のファイルの (パス, 本文, 読めない訳)。名指しが無ければ ("", "", "")、読めなければ本文は空で
    訳は REQUEST_UNREAD の行"""
    req = (start or {}).get("request_file") or ((start or {}).get("input") or {}).get("request_file") or ""
    if not req:
        return "", "", ""
    try:
        return req, pathlib.Path(req).read_text(encoding="utf-8"), ""
    except (OSError, UnicodeDecodeError) as e:
        return req, "", REQUEST_UNREAD.format(path=req, why=type(e).__name__)


# ---------------------------------------------------------------- 差し込みの頭
def open_pass(folder, *, cwd, judgment, purpose, plan, structure, ripple, world=None, start=None, answers=None,
              ruling=(), conflicts=None, gate_answers=None, review_schema: dict, design_schema: dict) -> dict:
    """入力の指し札の先を置き場に写し、見え方の材料 OPEN_FILE を置く。judgment・purpose・plan・structure・ripple・world・start・
    conflicts は指し札の先のパス（world・start・conflicts は null 可）、answers は始めの人の関所の答え・gate_answers は修正前の
    関所の答え（JSON の値。take_gate_answers）、ruling は裁かれた項目の番号の字（planmarks.handed。番号でない行と案の外の番号は
    訳つきの Missing）、review_schema・design_schema は事前審査と独立設計の役の型
    （ブロックの YAML の役の節の output_format）。形 replan では、前の差し込みが置き場に残した承認済みの項目を上書きする前に読み、
    直した項目と申し出と裁定の行と並べて材料に置く（replan_items）。
    返り {k（plan-fields.json の round）, form（ruling が空なら review、在れば replan）, tree, r2_go}"""
    d = pathlib.Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    out = place(d)
    start_doc = startrec.adopt(d, start) if start else None
    gate_rows = take_gate_answers(d, gate_answers)
    judged = _read_json(judgment)
    shutil.copyfile(judgment, d / JUDGMENT_COPY)
    mats = _sibling(judgment, "materials.json")
    excluded = _sibling(judgment, EXCLUDED_FILE)
    purpose_review, review_unread = _purpose_review(judgment)
    if excluded is not None:
        shutil.copyfile(excluded, d / EXCLUDED_FILE)
    fields = _read_json(plan)
    fix_plan = _read_json(pathlib.Path(plan).parent / "p2.fix_plan.json")
    k = fields["round"]
    form = "replan" if ruling else "review"
    approved = _approved(d) if form == "replan" else None
    planmarks.save(d, 1, fields["fields"], {int(n): v for n, v in (fields.get("amended") or {}).items()} or None,
                   trace=out.trace)
    _copy_world(d, world)
    _copy_structure(d, structure)
    _write_json(d / planblk.RIPPLE_PASS.format(k=converge.pass_no(out)), _read_json(ripple))
    bare, answered = converge.split("plan-revise", fix_plan)
    marked = copy.deepcopy(bare)
    bare, plan_marks = gatemarks.split(PLAN_NODE, bare)
    gatemarks.save(out, PLAN_NODE, out.round, plan_marks)
    rows = [r for r in bare.get("plan") or [] if isinstance(r, dict)]
    ruled, why = planmarks.handed(ruling, len(rows)) if form == "replan" else ([], "")
    if why:
        raise Missing(why)
    converge.note_plan(out, rows)
    if form == "review" and answered:
        converge.note_answers(out, answered)
    frozen = _frozen_policy(d, start_doc, cwd)
    units = [u for u in judged.get("units") or [] if isinstance(u, dict)]
    _, request, unread = _request(start_doc)
    defaults = [x for x, given in ((DEFAULT_START, start is not None), (DEFAULT_ANSWERS, answers is not None)) if not given]
    defaults += [x for x in (review_unread, unread) if x]
    inputs = {
        "k": k, "form": form, "ruled": ruled, "cwd": str(cwd),
        "rev": (start_doc or {}).get("base_rev") or "HEAD", "base": (start_doc or {}).get("base_rev") or "",
        "request": request, "policy_md": frozen.get("path") or "",
        "policy_copy": frozen.get("copy") or "", "excluded_file": str(d / EXCLUDED_FILE) if excluded is not None else "",
        "units": units, "names": [u["key"] for u in units if isinstance(u.get("key"), str)],
        "questions": judged.get("questions") or [], "materials": _read_json(mats) if mats else {},
        "precedents": judged.get("precedents") or [],
        "diagnosis": {x: judged[x] for x in ("framing", "one_shot") if x in judged},
        "purpose_review": purpose_review, "purpose": _read_json(purpose), "plan": bare,
        "human_items": human_items(answers) + gate_rows, "tree_word": tree_word(start_doc),
        "review_schema": review_schema, "design_schema": design_schema,
        "defaults": defaults,
    }
    b = view(d, inputs)
    if form == "replan":
        inputs["replan_items"] = replan_items(b, approved, marked.get("plan") or [], ruled,
                                              (_read_json(conflicts).get("items") or []) if conflicts else [])
    inputs["tree"] = form == "review" and _tree_on(b, inputs["tree_word"])
    _write_json(d / OPEN_FILE, inputs)
    return {"k": k, "form": form, "tree": inputs["tree"], "r2_go": r2_due(b)}


def _approved(d: pathlib.Path) -> list | None:
    """置き場に残る承認済みの修正案の項目（前の差し込みの往復の控えの案の行と、凍結した欄。planmarks.approved_items の形）。
    どちらか無ければ None"""
    rows = [r.get("row") for r in converge.read(place(d)).get("plan") or [] if isinstance(r, dict)]
    prev = types.SimpleNamespace(dir=d, round=1, work=lambda name: d / name,
                                 output_of_round=lambda node, rnd: {"plan": rows} if node == PLAN_NODE and rows else None)
    return planmarks.approved_items(prev)


def _role_item(item: dict) -> dict:
    """承認済みの項目から、役の返答の型が持てない欄（鍵 item と rewrite_tests の行の範囲 limit）を外した写し
    （元 works/.shared/core/replan.py:281）"""
    out = {k: v for k, v in item.items() if k != "item"}
    if isinstance(out.get("rewrite_tests"), list):
        out["rewrite_tests"] = [{k: v for k, v in r.items() if k != "limit"} if isinstance(r, dict) else r
                                for r in out["rewrite_tests"]]
    return out


def _bare(item: dict) -> dict:
    """項目から関所の決め手の欄を外した写し（元 works/.shared/core/replan.py:579）"""
    return gatemarks.split(PLAN_NODE, {"plan": [copy.deepcopy(item)]})[0]["plan"][0]


def replan_items(b, approved, marked_rows: list, ruled: list, conflicts: list) -> list:
    """裁かれた項目ごとの {item, units, rows（申し出と裁定の行）, old（承認済みの前の形）, new（直した形。決め手の欄つき）}。
    申し出の行は、裁定の plan_items がその項目の番号を持つか、申し出の単位がその項目の単位に在る物。承認済みの案が無い・
    項目が案の外なら Missing"""
    if approved is None:
        raise Missing(NO_APPROVED)
    now = planmarks.approved_items(b) or []
    out = []
    for n in ruled:
        if not 1 <= n <= min(len(approved), len(now), len(marked_rows)):
            raise Missing(f"裁かれた項目 {n} が承認済みの修正案（{len(approved)} 項目）か直した案（{len(now)} 項目）の外")
        units = [str(k) for k in now[n - 1].get("unit_keys") or []]
        new = {**_role_item(now[n - 1]), **{k: copy.deepcopy(v) for k, v in marked_rows[n - 1].items() if k == "narrows"}}
        mine = [c for c in conflicts if isinstance(c, dict)
                and (n in ((c.get("ruling") or {}).get("plan_items") or []) or str(c.get("unit_key")) in units)]
        out.append({"item": n, "units": units, "rows": mine, "old": _role_item(approved[n - 1]), "new": new})
    return out


def _frozen_policy(d: pathlib.Path, start_doc, cwd) -> dict:
    """この run の方針の文書の版 {named, path, sha256, copy}。始めの記録の欄 policy（run の始めに固めた版）をそのまま置き、文書を
    読み直さない。欄の無い・壊れた記録は、最初の差し込みで読んだ版を固める。関所で方針の変化を通すと take_gate_answers が固め直す"""
    if (d / POLICY_FILE).is_file():
        return _read_json(d / POLICY_FILE)
    doc = policy.version(start_doc) or policy.freeze(d, cwd, (start_doc or {}).get("policy_md") or "")
    _write_json(d / POLICY_FILE, doc)
    return doc


def policy_change(folder, cwd) -> dict | None:
    """固めた版から今の方針の文書が変わったか（変わっていなければ None。変わっていれば今の版の写しと差分のファイルを置いて
    {path, from, to, from_copy, to_copy, diff_file}。固めた版の写しが無ければ差分を作らず diff_missing に訳。置き場は名指しか
    既定の置き場を引き直す（後から既定の置き場に置いた文書も変化に数える）。元 graphloops/rules/policy_input.py:82 の change）"""
    d = pathlib.Path(folder)
    if not (d / POLICY_FILE).is_file():
        return None
    pol = _read_json(d / POLICY_FILE)
    path = policy.locate(cwd, pol.get("named") or "") or pol.get("path") or ""
    to, to_copy = policy.snapshot(d, path)
    frm = pol.get("sha256")
    if to == frm:
        return None
    ch = {"path": path, "from": frm, "to": to, "from_copy": pol.get("copy"), "to_copy": to_copy, "diff_file": None}
    if frm and not (ch["from_copy"] and pathlib.Path(ch["from_copy"]).is_file()):
        ch["diff_missing"] = DIFF_MISSING
        return ch
    diff = d / POLICY_DIR / f"{(frm or 'none')[:12]}-{(to or 'none')[:12]}.diff"
    diff.parent.mkdir(parents=True, exist_ok=True)
    old = pathlib.Path(ch["from_copy"]).read_text(encoding="utf-8", errors="replace") if ch["from_copy"] else ""
    new = pathlib.Path(to_copy).read_text(encoding="utf-8", errors="replace") if to_copy else ""
    diff.write_text("".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                                 ch["from_copy"] or "（固めた時点で文書が無い）", to_copy or "（今は文書が無い）")),
                    encoding="utf-8")
    return {**ch, "diff_file": str(diff)}


def change_row(ch: dict) -> str:
    """関所の行の 1 行——置き場だけで本文を載せない（元 graphloops/rules/policy_input.py:105）"""
    where = (f"差分 {ch['diff_file']}" if ch.get("diff_file") else ch.get("diff_missing", "")) + \
            f"・前の版の写し {ch.get('from_copy') or '（無い）'}・今の版の写し {ch.get('to_copy') or '（無い）'}"
    return (f"人の方針の文書 {ch['path'] or '（無い）'} が固定した版から変わった: sha256 "
            f"{str(ch['from'])[:12]} → {str(ch['to'])[:12] if ch['to'] else '消えた'}（{where}）")


def _copy_world(d: pathlib.Path, world) -> None:
    """世界の解の行の写しと段の控え（world が null なら控えを置かない＝関所の軸が今どおりの決まりに戻る）"""
    state = d / worldmark.STATE_FILE
    if world is None:
        state.unlink(missing_ok=True)
        return
    dest = d / WORLD_COPY
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(world, dest)
    worldmark.write(d, status="ok", reason="", world_file=str(dest), classes=len(worldmark.rows(dest)), dropped=0)


def _copy_structure(d: pathlib.Path, structure) -> None:
    """構造の目の控えの写し（design_file は写した隣の design.jsonl を指す）"""
    doc = _read_json(structure)
    rows = _sibling(structure, "design.jsonl")
    dest = d / STRUCTURE_ROWS
    if rows is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rows, dest)
    ok = isinstance(doc, dict) and doc.get("status") == "ok"
    structmark.write(d, status="ok" if ok else "failed",
                     reason=str((doc or {}).get("reason") or "") if isinstance(doc, dict) else "構造の目の控えが object でない",
                     design_file=str(dest) if rows is not None else "", wall_s=(doc or {}).get("wall_s", 0) if isinstance(doc, dict) else 0)


def _tree_on(b, word: str) -> bool:
    """事前審査を木にするか（on・off、auto は開いた項目が planblk.TREE_AUTO_MIN 以上。元 planblk.prep の review_tree）"""
    if word != "auto":
        return word == "on"
    return len(planblk._opened(b, planblk._item_rows(b))) >= planblk.TREE_AUTO_MIN


def r2_due(b) -> bool:
    """独立設計を回すか: 同じ run の置き場に設計の控えが無く（壊れた控えも作り直さない）・諦めていず・目的が使える
    （元 works/.shared/core/design.py:492 の due のうち、盤面の節の表と再発火の条件を除いた物）"""
    got, broken = design.made(b.dir, b.design_schema)
    return (got is None and not broken and not rolekit.given_up_reason(b.dir, design.NODE)
            and not design.unusable(b))


# ---------------------------------------------------------------- 独立設計
def r2_view(request: str, answers) -> types.SimpleNamespace:
    """独立設計の前提を組むだけの見え方（人の関所の答え・依頼の本文・rules だけ。修正案・判定・波及は持たない）"""
    return types.SimpleNamespace(record={"process": {"human_items": human_items(answers)}},
                                 state={"inputs": {"request": request}}, rules=rules)


def r2_prompt(folder, *, cwd, purpose, judgment, start=None, answers=None) -> str:
    """独立設計の役に貼る本文: 人が決めた前提の節（人の関所の答え・依頼が名指した設計書の節・対象のリポジトリの地図）と、元の目的
    （purpose.json の purpose_text）と、実測した制約（judgment の隣の premises.json の constraints だけ。判定の中身は読まない）と、
    人の方針（差し込みの頭が固めた方針の文書の置き場。run をまたいで人が決めた前提なので実測した制約と同じく渡す。元の
    graphloops の r2.design の prompt_append）。前の回の拒みは頭に貼る。貼った物の控えを PREMISES_FILE、役を起こす前の作業ツリーの姿を R2_TREE に置く"""
    d = pathlib.Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    start_doc = _read_json(start) if start else None
    text = _read_json(purpose).get("purpose_text") or ""
    premises = _sibling(judgment, "premises.json")
    constraints = (_read_json(premises).get("constraints") or []) if premises else []
    req, request, unread = _request(start_doc)
    parts, ledger = design.premises(r2_view(request, answers), cwd)
    if start_doc is None:
        parts.insert(0, f"{design.NAMED_HEAD}\n\n- {NOT_GIVEN_START}")
        ledger["withheld"].append({"kind": "named_section", "what": "start", "why": NOT_GIVEN_START})
    elif unread:
        parts.insert(0, f"{design.NAMED_HEAD}\n\n- {unread}")
        ledger["withheld"].append({"kind": "named_section", "what": req, "why": unread})
    if answers is None:
        ledger["withheld"].append({"kind": "human_answer", "what": "answers", "why": DEFAULT_ANSWERS})
    if premises is None:
        ledger["withheld"].append({"kind": "constraint", "what": "premises.json", "why": "判定の隣に実測した制約のファイルが無い"})
    body = (f"{PURPOSE_HEAD}\n{text}\n\n{CONSTRAINTS_HEAD} "
            f"{json.dumps(constraints, ensure_ascii=False)}")
    if parts:
        body = f"{design.DESIGN_PREMISE_HEAD}\n\n{DESIGN_PREMISE_REREAD}\n\n" + "\n\n".join(parts) + f"\n\n---\n\n{body}"
    pol = _read_json(d / POLICY_FILE) if (d / POLICY_FILE).is_file() else {}
    prompt = "\n\n".join(x for x in (body, policy.section(pol.get("copy"))) if x)
    rows = rolekit.rejected(d, design.NODE)
    if rows:
        prompt = rolekit.with_reject(prompt, rows[-1])
    _write_json(d / PREMISES_FILE, {"node": design.NODE, **ledger})
    _write_json(d / R2_TREE, accept.tree_state(pathlib.Path(cwd)))
    (d / R2_PROMPT).write_text(prompt, encoding="utf-8")
    return prompt


def _moved(before_file: pathlib.Path, repo, keys=accept.TREE_KEYS) -> list:
    if not before_file.is_file():
        raise Reject(NO_TREE.format(name=before_file.name))
    return accept.tree_moved(_read_json(before_file), pathlib.Path(repo), keys=keys)


def check_design(folder, raw, repo, *, keys=accept.TREE_KEYS) -> dict:
    """独立設計の受け付け: 作業ツリーが役の前と同じ（keys の欄で比べる）→ 型（差し込みの頭が置いた材料の役の型） → 問いが立たない時は根拠の名指し（パス:行）が固めた版に在る。通れば
    design.json と、返答が『渡されていない』と書いた文と控えの given の対（PREMISES_FILE の claims）。拒みは控えに積み、
    GIVE_UP_AFTER 回目で done・give_up。返り {ok, done, give_up, reason}"""
    d = pathlib.Path(folder)

    def run():
        reply, why = rolekit.parse_reply(raw)
        if reply is None:
            raise Reject(why)
        moved = _moved(d / R2_TREE, repo, keys)
        if moved:
            raise Reject(READONLY_MOVED + "；".join(moved))
        accept.type_errors(reply, read_open(d)["design_schema"], "独立設計の返答")
        if not reply["question_stands"]:
            misses = design.anchor_misses(reply.get("premise_invalid_reason") or reply["reason"], repo)
            if misses:
                raise Reject(PREMISE_MISS + "・".join(misses))
        accept.write_board(d, design.DESIGN_FILE, reply)
        ledger = _read_json(d / PREMISES_FILE) if (d / PREMISES_FILE).is_file() else {}
        ledger["claims"] = design.claims_given(design.claims_unpassed(reply), ledger.get("given") or [])
        _write_json(d / PREMISES_FILE, ledger)
        return {"ok": True, "reason": ""}
    return _done(d, design.NODE, accept.guard(run))


def _done(d: pathlib.Path, name: str, got: dict) -> dict:
    out = rolekit.with_done(d, name, {"ok": got["ok"], "reason": got.get("reason", "")})
    return {"ok": out["ok"], "done": out["done"], "give_up": bool(out["done"] and not out["ok"]), "reason": out["reason"]}


# ---------------------------------------------------------------- 事前審査
def review_body(command_text: str, *, repo, rev: str, base: str, review_md, policy_md: str = "") -> str:
    """役の指示書のうち審査の決まりの本文（planblk._review_rules が下請けに貼る）: 指示書の『リポジトリ: 』の行から末尾までと、
    人の方針の節（在れば。元の下請けの決まりは描いた指示書の末尾の人の方針までを切り出した）。その行は対象のリポジトリ・読む版・
    BASE・観点の正本の実物に置き換える（指示書は run ごとの値を持たない）。行が無ければ空"""
    at = command_text.find(planblk.RULES_FROM)
    if at < 0:
        return ""
    rest = command_text[at + 1:]
    line_end = rest.find("\n")
    tail = rest[line_end:].rstrip("\n") if line_end >= 0 else ""
    pol = policy.section(policy_md)
    return "\n" + REPO_LINE.format(repo=repo, rev=rev, base=base, review_md=review_md) + tail + (f"\n\n{pol}" if pol else "")


def _units_text(b) -> str:
    """直す単位（番号つき。写しの指示書の record.units | pick key,label,disposition,reason）"""
    rows = [{"no": n, **{k: u[k] for k in UNIT_ROW_KEYS if k in u}} for n, u in enumerate(b.record["units"], 1)]
    return json.dumps(rows, ensure_ascii=False, indent=1)


def _defaults_line(inputs: dict) -> str:
    return DEFAULTS_HEAD + "／".join(inputs.get("defaults") or []) if inputs.get("defaults") else ""


def _json_block(doc) -> list:
    return ["```json", json.dumps(doc, ensure_ascii=False, indent=1), "```"]


def _replan_section(row: dict) -> str:
    """案の直しの項目ごとの節: 番号・unit_keys（字のまま）・前の項目・申し出と裁定の行（字のまま）・直した項目
    （元 works/.shared/core/replan.py:387 の _section の事前審査の側。項目の brief は修正のブロックの置き場に在り、読まない）"""
    old = row["old"]
    lines = [ITEM_HEAD.format(n=row["item"]), "",
             f"- unit_keys（この字のまま写せ）: {json.dumps(old.get('unit_keys'), ensure_ascii=False)}", "",
             OLD_HEAD, "", *_json_block(old)]
    for c in row.get("rows") or []:
        ru = c.get("ruling") or {}
        lines += ["", ROW_HEAD.format(id=c.get("id")), "",
                  f"- 申し出の単位: {c.get('unit_key')}",
                  f"- 申し出の名指し（between）: {', '.join(c.get('between') or [])}",
                  f"- 申し出の理由（{WHY_FIELD}）: {c.get(WHY_FIELD)}",
                  f"- 申し出の種類（kind）: {c.get(KIND_FIELD) or '（無し）'}",
                  f"- 正しいと見た側（{WHICH_FIELD}）: {c.get(WHICH_FIELD)}",
                  f"- 裁定（{ru.get('decision')}）の文: {ru.get('text')}"]
    lines += ["", NEW_HEAD, "", *_json_block(row["new"])]
    return "\n".join(lines)


def review_material(folder, repo, command_text: str, review_md, *, shared=None) -> pathlib.Path:
    """事前審査の材料のファイル pass-<k>/prompt.md を書き、役を起こす前の作業ツリーの姿を pass-<k>/tree.json に置く。材料は
    役の頭（planblk.head。関所の決め手・既にある物を量ったか・人に回す物の挙げ方・ライブラリの文書・独立設計の節・修正案の
    works の欄・2 往復目からは前の往復の block と答え・木なら下請けのファイルと束ね役の頼み）と、写しの指示書の差し込み（修正案・
    単位・判定者の見立て・先行例・リポジトリと読む版と BASE）と、人の方針（在れば）と、考えの住処の地図（今の works の包みが
    旗 concept-map の役の system prompt の末尾に足した物）。形 replan では独立設計の節と、裁かれた項目ごとの前の形・申し出と
    裁定・直した形（元 works/.shared/core/replan.py:423 の prep）を見させる。shared はライブラリの文書の run をまたぐ控えの根
    （planblk.lib_section）"""
    d = pathlib.Path(folder)
    inputs = read_open(d)
    p = pass_dir(d, inputs["k"])
    p.mkdir(parents=True, exist_ok=True)
    rev, base = inputs.get("rev") or "HEAD", inputs.get("base") or inputs.get("rev") or "HEAD"
    inputs = {**inputs, "review_body": review_body(command_text, repo=repo, rev=rev, base=base, review_md=review_md,
                                                   policy_md=inputs.get("policy_copy") or "")}
    b = view(d, inputs)
    main = p / PROMPT_FILE
    if inputs["form"] == "replan":
        part = "\n\n".join([planblk.design_only(b), REVIEW_ASK_REPLAN, planmarks.REVIEW_ASK,
                             *(_replan_section(r) for r in inputs.get("replan_items") or [])])
    else:
        part = "\n\n".join(x for x in (planblk.design_section(b), converge.review_section(b),
                                       planblk.tree_part(b, main) if inputs.get("tree") else "") if x)
    head = planblk.head("plan-review", excluded_file=inputs.get("excluded_file") or "",
                        lib_docs=planblk.lib_section(b, pathlib.Path(repo), shared), design_part=part)
    diag = (b.record["process"].get("diagnosis") or {})
    body = "\n\n".join(x for x in (
        _defaults_line(inputs), head, "## 差し込み（機械が貼った）",
        "修正役の案: " + json.dumps((inputs.get("plan") or {}).get("plan") or [], ensure_ascii=False, indent=1),
        UNITS_LINE + _units_text(b),
        "判定者の見立て: " + json.dumps(diag, ensure_ascii=False),
        ("判定者の先行例（世界の解）: " + json.dumps(b.record["process"]["precedents"], ensure_ascii=False))
        if b.record["process"]["precedents"] else "",
        REPO_LINE.format(repo=repo, rev=rev, base=base, review_md=review_md),
        policy.section(inputs.get("policy_copy")), concepthome.section(pathlib.Path(repo))) if x)
    last = rolekit.rejected(p, REVIEW_NODE)
    if last:
        body = rolekit.with_reject(body, last[-1])
    main.write_text(body + "\n", encoding="utf-8")
    _write_json(p / TREE_FILE, accept.tree_state(pathlib.Path(repo)))
    return main


def _unit_name(names: list, k):
    return names[k - 1] if isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= len(names) else k


def named(b, reply: dict) -> dict:
    """返答の faces・shrink の unit_keys の番号を単位の名に戻した写し（戻せない番号は番号のまま。照らしが拒む）"""
    names = b.pointer_rows(REVIEW_NODE)["pointers"][0]["names"]
    out = copy.deepcopy(reply)
    for field in ("faces", "shrink"):
        for row in out.get(field) or []:
            if isinstance(row, dict) and isinstance(row.get("unit_keys"), list):
                row["unit_keys"] = [_unit_name(names, k) for k in row["unit_keys"]]
    return out


def _lines(head: str, gaps: list) -> str:
    return head + "\n" + "\n".join(f"  - {g}" for g in gaps)


def take_review(folder, raw, repo, *, keys=accept.TREE_KEYS) -> dict:
    """事前審査の受け付け（元 planblk.take と with_converge の事前審査の側）。作業ツリーが役の前と同じ（keys の欄で比べる）→ 推しの形 → 型（役の型） → 木なら下請けの
    答えのまとめ（planblk.tree_merge）・木でなければ独立設計の引用と design_map（planblk.design_gaps）→ 前の往復の block の行き先
    （converge.resolved_gaps）→ 審査の決まり（rules.plan_review_output）。通れば決め手の欄を gate-marks.json に置き、形 review なら
    往復を控え（converge.record_pass）、返答を pass-<k>/review.json に書く。拒みは pass-<k>/ の控えに積み、GIVE_UP_AFTER 回目で
    done・give_up（その時は最後の拒みの訳を reason に置いた空の返答を review.json に書く）。返り {ok, done, give_up, reason}"""
    d = pathlib.Path(folder)
    inputs = read_open(d)
    p = pass_dir(d, inputs["k"])
    p.mkdir(parents=True, exist_ok=True)
    got = _done(p, REVIEW_NODE, accept.guard(lambda: _take(d, p, inputs, raw, repo, keys)))
    if got["give_up"]:
        _write_json(p / REVIEW_FILE, {"faces": [], "shrink": [], "reason": GIVEN_UP_FACES + got["reason"]})
    return got


def _take(d: pathlib.Path, p: pathlib.Path, inputs: dict, raw, repo, keys) -> dict:
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise Reject(why)
    moved = _moved(p / TREE_FILE, repo, keys)
    if moved:
        raise Reject(READONLY_MOVED + "；".join(moved))
    if not isinstance(reply.get("faces"), list):
        accept.type_errors(reply, inputs["review_schema"], "事前審査の返答")
    gaps = gatemarks.recommend_gaps(REVIEW_NODE, reply)
    if gaps:
        raise Reject(_lines(planblk.RECOMMEND_REJECT, gaps))
    accept.type_errors(reply, inputs["review_schema"], "事前審査の返答")
    b = view(d, inputs)
    bare, resolved = converge.split("plan-review", reply)
    bare, tree = converge.tree_split(bare)
    merged = {"review": bare, "resolved": resolved, "synergy": [], "hits": {}, "files": {}, "gaps": [], "off": True}
    if inputs["form"] == "review":
        merged = planblk.tree_merge(b, bare, tree, resolved)
        if merged["gaps"]:
            raise Reject(_lines(planblk.TREE_REJECT, merged["gaps"]))
    if merged.get("off"):
        items = inputs.get("ruled") if inputs["form"] == "replan" else converge.open_items(b)
        gaps = planblk.design_gaps(b, merged["review"].get("faces"), items, tree.get(converge.DESIGN_MAP) or [])
        if gaps:
            raise Reject(_lines(planblk.DESIGN_QUOTE_REJECT, gaps))
    review = named(b, merged["review"])
    if inputs["form"] == "review":
        gaps = converge.resolved_gaps(b, review["faces"], merged["resolved"])
        if gaps:
            raise Reject(_lines(planblk.RESOLVED_REJECT, gaps))
    rules.plan_review_output(b, REVIEW_NODE, review, None)
    bare_review, marks = gatemarks.split(REVIEW_NODE, review)
    out = place(d)
    gatemarks.save(out, REVIEW_NODE, out.round, marks)
    if inputs["form"] == "review":
        if merged.get("precedents"):
            planblk.save_precedents(b, *merged["precedents"])
        files = {**merged["files"], PROMPT_FILE: str(p / PROMPT_FILE)}
        converge.record_pass(out, bare_review, resolved=merged["resolved"], fence=FENCE, files=files,
                             synergy=merged["synergy"], hits=merged["hits"])
    # 壁打ちの欄 resolved は写しの型の外なので外して照らしたが、plan の往復の控え（planfile.converge_record）が review.json から読む
    _write_json(p / REVIEW_FILE, {**review, converge.RESOLVED: merged["resolved"]} if merged["resolved"] else review)
    return {"ok": True, "reason": ""}


# ---------------------------------------------------------------- 返す節
def _faces_of(row: dict, review: dict, rows: list) -> list:
    """事前審査の穴のうち直した項目 row の分: unit_keys が項目の単位と重なる行と、どの直した項目とも重ならない行
    （元 works/.shared/core/replan.py:496 の _review_of）"""
    mine = set(row["units"])
    every = set().union(*(set(r["units"]) for r in rows))
    out = []
    for f in review.get("faces") or []:
        keys = {str(k) for k in f.get("unit_keys") or []} if isinstance(f, dict) else set()
        if keys & mine or not keys & every:
            out.append(f)
    return out


def replan_asks(d: pathlib.Path, p: pathlib.Path, inputs: dict, review: dict) -> list:
    """案の直しで人に聞く項目 [(種類, 文)]: 直した項目のうち、約束の欄（planmarks.contract_diff）が変わったか、人に聞く種類の穴
    （HUMAN_FACE_KINDS）が在る物。無人の run で範囲を広げただけ（planmarks.widened）の直しは聞かない。項目ごとの判じを
    pass-<k>/replan.json に置く（元 works/.shared/core/replan.py:620 の gate）"""
    rows = inputs.get("replan_items") or []
    alone = gatepolicy.unattended(d)
    out = []
    for row in rows:
        faces = _faces_of(row, review, rows)
        human = [f for f in faces if isinstance(f, dict) and f.get("kind") in HUMAN_FACE_KINDS]
        old, new = _bare(row["old"]), _bare(row["new"])
        row["contract_changed"] = planmarks.contract_diff(old, new)
        row["human_faces"] = [f.get("key") for f in human]
        row["widened"] = planmarks.widened(old, new) if alone and row["contract_changed"] and not human else None
        row["ask"] = bool((row["contract_changed"] and not row["widened"]) or human)
    _write_json(p / REPLAN_FILE, rows)
    for row in rows:
        if row["ask"]:
            faces = {f.get("key"): f for f in _faces_of(row, review, rows) if isinstance(f, dict)}
            out.append(("replan", REPLAN_ASKED.format(
                n=row["item"], units="、".join(row["units"]), changed="・".join(row["contract_changed"]) or "（無し）",
                faces="／".join(f"[{faces[k].get('kind')}] {k}: {faces[k].get('why')}" for k in row["human_faces"]) or "（無し）",
                file=p / REPLAN_FILE)))
    return out


def _note_asked(d: pathlib.Path, items: list, changed: dict | None) -> None:
    doc = _read_json(d / GATE_ASKED_FILE) if (d / GATE_ASKED_FILE).is_file() else {}
    for kind, text in items:
        doc[text] = {"kind": kind, **({"policy_change": changed} if kind == POLICY_CHANGED and changed else {})}
    _write_json(d / GATE_ASKED_FILE, doc)


def collect(folder) -> dict:
    """返す節の中身（パスは置き場の中の実物）: {pass, stalled, review, design, gate_axes, ask_human, questions}。questions の行は
    関所の項目の種類と文 {kind, text}（gatemarks.question_row。線が無人の run で台帳の問いだけを報告へ回し、ほかの種類で止まる）。
    抜け方は形 review なら往復の控えの converge.decide（record_pass が決めた語）、形 replan なら block の有無（stalled はいつも偽）。
    受け付けが諦めた往復は pass: false・stalled: true で、諦めた訳を questions に載せる。関所の項目は、形 review なら
    gatemarks.plan_gate_items、形 replan なら約束の欄が変わったか人に聞く穴の在る直した項目だけ（replan_asks）で、どちらも方針の
    文書の変化を足す。聞かずに通した行は pass-<k>/gate-passes.json、4 つの軸は gate_axes.gather。返した項目の種類と方針の変化を
    GATE_ASKED_FILE に積む（次の差し込みが入力 gate_answers の通した行を引く）"""
    d = pathlib.Path(folder)
    inputs = read_open(d)
    p = pass_dir(d, inputs["k"])
    gave = rolekit.given_up_reason(p, REVIEW_NODE)
    review = _read_json(p / REVIEW_FILE) if (p / REVIEW_FILE).is_file() else None
    if review is None:
        raise Missing(f"事前審査の返答 {p / REVIEW_FILE} が無い（受け付けが通っていない）")
    b = view(d, inputs, None if gave else review)
    blocks = converge.block_faces(review)
    if gave:
        ok, stalled = False, True
    elif inputs["form"] == "review":
        outcome = converge.read(b)["outcome"]
        ok, stalled = outcome == converge.CLEAN, outcome in converge.STUCK
    else:
        ok, stalled = not blocks, False
    items = gatemarks.plan_gate_items(b) if inputs["form"] == "review" else replan_asks(d, p, inputs, review)
    changed = policy_change(d, inputs["cwd"])
    if changed:
        items.append((POLICY_CHANGED, change_row(changed)))
    _note_asked(d, items, changed)
    questions = [gatemarks.question_row(kind, text) for kind, text in items]
    if gave:
        questions.append(gatemarks.question_row(gatemarks.GIVEN_UP_KIND, GIVEN_UP_FACES + gave))
    _write_json(p / PASSES_FILE, gatemarks.passes(b))
    _write_json(p / GATE_FILE, {"items": [{"kind": k, "text": t} for k, t in items], "converge": converge.lines(b)})
    got, _ = design.made(d, b.design_schema)
    design_file = d / design.DESIGN_FILE if got is not None else _write_json(p / design.DESIGN_FILE, {"missing": design.missing(b)})
    return {"pass": ok, "stalled": stalled, "review": p / REVIEW_FILE, "design": design_file,
            "gate_axes": gate_axes.gather(b), "ask_human": bool(questions), "questions": questions}
