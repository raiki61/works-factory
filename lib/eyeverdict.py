"""独立の目のブロックの値を組む部品。今の works（2aa7c66c の works/）で盤面の上に在った関数を、元の名のまま値とファイルのパスを
引数で受ける形に書き直した物（元の場所は関数ごとの docstring）。目の返りは置き場 eyes_dir の <目>.json（r1・r2・r3・r4・
premise-check）で受ける。標準ライブラリと lib の部品だけ。

- r2_compare_due(design, purpose_text)・r2_premise_invalid(design): 比較役と前提の検算を起こすか
- scalars(diff_text, x_scalars, not_taken)・scalars_text(s): 規模の数値と、その 1 文
- _human_passed(questions, answer)・carried_section(passed)・r4_gate_items(r4, passed)・gate_passes(r4, passed, by)・passed_by(answer):
  修正前の関所で通した行（無人の run が推しで通した行も）と、R4 の問いからそれを外す照らしと、外した行の控えとその印。R4 の方針との
  ぶつかりは通していない行を全部問いにする
- r4_accept(eyes_dir, got, passed): R4 の返答の受け付け（輪の中。got は読めた返答と読めない訳の組）。方針とのぶつかりのうち記録された方針（policy.recorded）の行を
  名指さない行を拒んで出し直させ、GIVE_UP_AFTER 回とも通らなければ抜ける（その時は名指さない行も問いになり、collect が R4 の行の
  理由に諦めた訳を足す）。r4_rejects(eyes_dir) は出し直す役に渡す拒否の全部
- human_items(start_answer, answer)・premise_section(...): R2 の比較役の頭に貼る、独立設計を作った後に分かった前提と、その控え
- prompt_texts(...): 目の指示書に差し込む文
- one_briefs(eyes_dir, texts): まとめた役 eyes-one（run の頭の深さの段が目をまとめる run。depth.merges）が読む観点ごとの指示書
  （観点ごとの役の指示書に支度の値を差し込んだ本文）を置き場に書き、その並びの行を返す
- tdd_stages(stages, resolve)・measured_section(test_outcomes, stages): R2 の比較役に貼る機械の実測（試験の関門が返したテストごとの
  base と最後の結末を移り方ごとに全部と、修正の段ごとの TDD のループの記録。測っていない物はそう書く）
- origin_section(repo, base, head, label, ...): R2 の比較役に貼る累積差分の起点の訳（PR の根か修正前の HEAD か・PR の差分と直しの差分）
- after_section(eyes_dir, review_folder, plan)・plan_review_line(review_folder, plan): R1・R3 の頭に貼る直しの後の実測の節（外れの訳が
  在れば、訳の行と、外れの源の修正案 plan を審査した事前審査の最後の往復が外れを認めたか）
- read_design(path)・read_json(path): 独立設計の控え（無ければ {"missing": 訳}）と、置き場の JSON（無い・読めなければ None）
- premise_reason(design): 独立設計が問いが立たないとした訳
- fell_text(fell, ran)・collect(...)・unverified(reason, protected): ブロックの返り。R1 の作り直しが要るかは目の札でなく
  redesign_points の名指しで決める（名指しが在れば作り直し・無ければ直しが要るに倒す。欄が在るのに配列でない・読める項が無ければ確かめられない。
  頭の字は RAISED_BY_POINTS・UNNAMED_REDESIGN・BROKEN_POINTS）
- write_notes(eyes_dir, ...): 返りの欄の外で最後の関所に出す材料（R2 に渡した前提の控えと『渡されていない』の照らし・人が
  通したので R4 の問いから外した行）を置き場に書く（返りの notes が PREMISE_INPUTS を指し、隣の GATE_PASSES・PREMISE_FILE も約束）
- r2_input_lines・gate_pass_rows・premise_facts・premise_fact_lines: 最後の関所と報告がその隣のファイルを読む口
"""
from __future__ import annotations

import json
import pathlib
import re
import types

import accept
import boardview
import changemap
from answer import GO_WORDS, by_push, origin
import design
import gatemarks
import jsonfile
import oneline
import policy
import rolekit
import seal
import structmark
from engine.util import Reject

R2_PREMISE_HEAD = "前提不成立: "
R2_MISSING_HEAD = f"{design.MISSING}: "
R2_NOT_COMPARED_HEAD = "独立設計と比べなかった: "
R2_NO_PURPOSE = R2_NOT_COMPARED_HEAD + "目的の文が空"
R2_NO_STANDS = R2_NOT_COMPARED_HEAD + "独立設計の返答に問いが立つかの欄（question_stands）が無い"
FELL_MARK = "の筋が落ちた"
# 元 blk-eyes/lib/eyes.py:115-117 の LATE_HEAD・LATE_ASK
LATE_HEAD = "### 独立設計の後に来た人の答え（独立設計は見ていない）"
LATE_ASK = ("上の承認ノードの答えのうち、次の物は独立設計を作った後に来た。設計がこれを置いていないことを設計の漏れに数えず、"
            "答えに照らした目的で突き合わせよ。")
DRIFT_HEAD = "### 前提のずれ（修正の中の申告）"     # 元 同 :118
CONSTRAINT_HEAD = "### 記録の制約"                 # 元 同 :119
NO_CONSTRAINTS = "（記録の制約 premises.json が渡っていない）"
NO_REQUEST = "依頼のファイルが渡っていない"
# 元 .shared/core/graphloops/rules/review-loop.py:4103 の R4_ROWS（種類・R4 の返りの欄・行の頭）
R4_ROWS = (("regression", "lost", "R4 が BASE から消えたと見た能力: "),
           (policy.POLICY_KIND, "policy_conflicts", "R4 が見た人の方針とのぶつかり: "))
R4_NODE = "r4-scope"   # R4 の受け付けの拒否の控えの名（置き場の rejects-r4-scope.json）
R4_REJECT = (f"policy_conflicts の次の行は{policy.RECORDED_TERM}のどの行も名指さない。{policy.RECORDED_REF}の行の名指しを字のまま"
             "写して書き直すか、一覧に無いコードのコメント・docstring・テストの説明文（対象の文で、方針ではない）なら policy_conflicts "
             "から外せ。下の行を全部直して、返答を丸ごと出し直せ:")
# R1 の作り直しが要るの導き（_row）の頭の字。最後の承認ノードと報告の冒頭に平易な主語で出る
_FIX, _REDESIGN = map(gatemarks.status_named, (seal.FIX_NEEDED, seal.REDESIGN))
UNNAMED_REDESIGN = f"目は{_REDESIGN}と書いたが、組み直す設計の点（redesign_points）の名指しが無いので{_FIX}に倒した: "
RAISED_BY_POINTS = f"組み直す設計の点（redesign_points）の名指しが在るので{_REDESIGN}にした: "
BROKEN_POINTS = (f"組み直す設計の点（redesign_points）の欄が配列でないか読める項が無く、名指しの有無を決められないので"
                 f"{gatemarks.status_named(seal.UNVERIFIABLE)}にした: ")
R4_GAVE_UP = "（R4 の方針とのぶつかりの名指しが受け付けを通らなかったので、名指さない行も人に聞く: {why}）"
PREP_FILE = "prep.json"   # 支度の節が書く、目の指示書に差し込んだ値と記録された方針の一覧（policy.RECORDED_KEY）
X_SCALAR = re.compile(r"^x_[a-z0-9_]+$")   # 元 graphs/review-loop.json の p3.fix の x_scalars の patternProperties
EYES = ("r1", "r2", "r3", "r4")
PREMISE = "premise-check"
LANE = {"r1": "R1", "r2": "R2", PREMISE: "R2", "r3": "R3", "r4": "R4"}
RETURN_FIELDS = ("ok", *EYES, "questions", "premise_check", "structure_after", "protected_hits", "notes")
VERDICTS = ("resolved", "escalate")
NO_FILE = "出力のファイルが無い"
NO_AFTER = "直しの後の実測: 控えが無い（測っていない run）"   # 元 blk-eyes/lib/eyes.py:93
REVIEW_ACCEPTED = "  事前審査の最後の往復（pass-{k}）は上の外れの訳を見て案を通した（外れを認めた）"
REVIEW_BLOCKED = "  事前審査の最後の往復（pass-{k}）は上の外れの訳を見て、block の穴 {n} 件を残した（外れを認めていない）: {faces}"
REVIEW_GAVE_UP = "  事前審査の最後の往復（pass-{k}）は受け付けが諦めて案を通していない（外れを認めていない）: {why}"
REVIEW_HELD = ("  事前審査の最後の往復（pass-{k}）は block の穴を挙げ直さなかったが、前の往復の穴を保留のまま案を通していない"
               "（外れを認めていない。往復の控えの抜け方: {outcome}）")
REVIEW_NO_PLAN = "事前審査は直す物の無い周（形 design）で、案を審査していない"
REVIEW_UNREAD = "  事前審査の最後の往復の返答を読めない（外れを認めたかは分からない）: {why}"
GREEN_LINE = "最後のテストの認証が通っていない（赤は最後の承認ノードで人が見る）"
DOC_SUFFIXES = (".md",)
DESIGN_PREMISES = "design-premises.json"   # 独立設計の役に貼った物の控え（design.json の隣。元 design.PREMISES_FILE）
R2_PREMISES = "r2-premises.json"           # 比較役に貼った物の控え（置き場。元 eyes.PREMISES_NAME）
PREMISE_INPUTS = "premise-inputs.json"     # 最後の関所に出す R2 の前提の材料（元 eyes-exit.json の premise_inputs）
GATE_PASSES = "r4-gate-passes.json"        # 人が通したので R4 の問いから外した行（元 state.works.gate_passes。事前審査の gatemarks.PASSES_FILE とは別の物）
# まとめた役 eyes-one が 1 つの会話で見る観点（観点ごとの役の指示書の名と、平易な名。並びは読む順）
ONE_VIEWS = (("r3-coherence", "R3 全体の整合"), ("r4-scope", "R4 見えていない範囲"))
ONE_DIR = "one"   # 観点ごとの指示書の置き場（eyes/one/<役の指示書の名>.md）
# 観点ごとの指示書の、ほかの会話の物を指す差し込みの代わりの字（R4 の受け付けの拒否は、この会話の中に在る）
ONE_REJECTS = "（この会話の指示書の頭の「前の回の受け付けが拒んだ理由」のセクションを見よ）"
FIX_DIFF_ROW = "この run の直しの差分"   # 起点の訳の行の名（前提の検算の指示書 premise-check.md がこの名で行を指す）


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


def scalars(diff_text: str, x_scalars=None, not_taken: str = "") -> dict:
    """元 同 :2153 の builtin scalars。差分から数えられる規模の数値（足した行・消した行・文書の足した行・変わったファイル）に、
    修正役が足した x_ の数値 x_scalars を足す。測れた分は返し、測れない物は 0 にせず unmeasured に訳を置く（差分が取れなかった訳
    not_taken が在れば差分の数は測れない）"""
    out, why = {}, []
    files = changemap.split_diff(diff_text)[0]
    if not_taken:
        why.append(not_taken)
    elif diff_text.strip() and not files:
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
    if not isinstance(answer, dict) or answer.get("decision") not in GO_WORDS:
        return {}
    out = {}
    for a in gatemarks.row_texts(questions):
        m = gatemarks.NARROW_HEAD.match(a)
        f = None if m else gatemarks.FACE_HEAD.match(a)
        if m or f:
            out.setdefault(("regression" if m else f.group(1), gatemarks.PUSH_TAIL.sub("", a[(m or f).end():])), 1)
    return out


def carried_section(passed: dict) -> str:
    """元 .shared/core/gatemarks.py:1259。R4 の指示書の頭に貼る、修正前の関所で通した行と、同じ物なら本文をそのまま写せという頼み"""
    rows = [f"- [{kind}] {body}" for kind, body in passed]
    return f"{gatemarks.CARRIED_HEAD}\n\n{gatemarks.CARRIED_ASK}\n\n" + "\n".join(rows) if rows else ""


DECLARED_HEAD = "## 直す側が直さずに残すと答えた、案の審査の block（案の審査の返答と直す側の答えから機械が並べた）"
DECLARED_ASK = ("下の行は、修正案の審査が挙げ、直す側が直さずに残すと答えた block（key: 穴の訳（直す側の答え））。累積差分の後も"
                "まだ在るかを読み、在る物はこの変更が手を付けていない残りとして扱え: この変更が入れた・露呈させた害なら redesign-needed、"
                "知らせるだけで足りるなら surfaced に挙げる（text の頭に [suggest]）。消えていれば挙げない")


def declared_section(rows) -> str:
    """R4 の指示書の頭に貼る、修正役が直さずに残すと答えた事前審査の block の行（fixboard.declared_lines の行。無ければ空）"""
    rows = [r for r in rows or [] if isinstance(r, str) and r.strip()] if isinstance(rows, list) else []
    return f"{DECLARED_HEAD}\n\n{DECLARED_ASK}\n\n" + "\n".join(f"- {r}" for r in rows) if rows else ""


def _r4_rows(r4: dict | None) -> list[tuple]:
    """R4 の消えた能力と方針とのぶつかりの [(種類, 行の頭, 本文)]"""
    r4 = r4 or {}
    got = {"lost": (r4.get("capability_inventory") or {}).get("lost") or [], "policy_conflicts": r4.get("policy_conflicts") or []}
    return [(kind, head, x) for kind, field, head in R4_ROWS for x in got[field]]


def r4_gate_items(r4: dict | None, passed: dict) -> list[str]:
    """元 .shared/core/gatemarks.py:1266 と review-loop.py:4106 の _r4_gate_items。R4 の消えた能力と方針とのぶつかりの行から、
    人が通した行と種類も頭を除いた本文も同じ物を外す（種類が違えば聞き直す）。外した行は gate_passes が控える"""
    return [head + x for kind, head, x in _r4_rows(r4) if (kind, x) not in passed]


def r4_accept(eyes_dir, got: tuple, passed: dict) -> dict:
    """R4 の返答の受け付け {ok, done, give_up, reason, reply}。got は (読めた返答, 読めない訳)（rolekit.parse_reply か、拒まれた後の
    出し直しを前の答えと合わせる rolekit.resubmitted の返り）。方針とのぶつかりのうち、人が通しておらず記録された方針の行
    （支度の控え PREP_FILE の policy.RECORDED_KEY）を名指さない行が在れば拒む。reply は読めた返答（読めなければ None）で、諦めた
    時も返す"""
    eyes_dir = pathlib.Path(eyes_dir)
    reply, _ = got
    recorded = read_json(eyes_dir / PREP_FILE)[policy.RECORDED_KEY]

    def check() -> dict:
        off = [x for kind, _, x in _r4_rows(reply) if kind == policy.POLICY_KIND and (kind, x) not in passed
               and not policy.hits(recorded, x)]
        if off:
            raise Reject(R4_REJECT + "\n" + _lines(off))
        return {"ok": True}

    return {**rolekit.round_outcome(rolekit.accept_parsed(eyes_dir, R4_NODE, got, lambda _: accept.guard(check))), "reply": reply}


def r4_rejects(eyes_dir) -> str:
    """R4 の受け付けがこれまでに拒んだ理由の全部（rolekit.rejects_text。resume で輪が 1 周目から回り直すと役は新しい会話で起き、前の拒否が会話に無いので最後の 1 件では足りない）"""
    return rolekit.rejects_text(rolekit.rejected(pathlib.Path(eyes_dir), R4_NODE))


def passed_by(answer) -> str:
    """修正前の関所の答えが通した行の控えの印: 無人の run が推しで通した答え（欄 answer.PUSHED）は PASSED_BY_PUSH、ほかは人"""
    return gatemarks.PASSED_BY_PUSH if by_push(answer) else gatemarks.PASSED_BY_HUMAN


def gate_passes(r4: dict | None, passed: dict, by: str = gatemarks.PASSED_BY_HUMAN) -> list[dict]:
    """元 .shared/core/gatemarks.py:1276-1281。r4_gate_items が外した行を、修正前の関所で通した印 by つきで控える
    （gatemarks._keep の行の形。最後の関所と報告が「人が通した」か「推しを採って通した」行として並べる）"""
    return [{"node": gatemarks.R4_GATE_NODE, "round": 1, "by": by, "item": head + x,
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
    独立設計の控えの seen.count は、plan-review が始めの関所の答えから design.human_answers で数えた数なので、この並びの頭を数える。
    無人の run が推しで通した答えは欄 answer.PUSHED を行にも写す（design.human_answers・policy.recorded が人の答えから外す）"""
    return [{"round": 1, "node": node, "answer": a.get("decision"), "note": (a.get("text") or "").strip() or None, **origin(a)}
            for node, a in ((gatemarks.START_GATE_NODE, start_answer), (gatemarks.GATE_NODE, answer)) if isinstance(a, dict)]


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


def one_briefs(eyes_dir, texts: dict) -> str:
    """まとめた役が読む観点ごとの指示書（ONE_VIEWS の順）を eyes_dir/ONE_DIR/<名>.md に書き、「- <平易な名>: `<パス>`」の行の並びを返す。
    texts は {観点ごとの役の指示書の名: 支度の値を差し込んだ本文}（差し込みは目のブロックの prep。R4 の拒否の理由は、観点ごとの役なら
    輪の頭の節から届く物なので ONE_REJECTS の字に替える）"""
    d = pathlib.Path(eyes_dir) / ONE_DIR
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, view in ONE_VIEWS:
        path = d / f"{name}.md"
        path.write_text(texts[name], encoding="utf-8")
        rows.append(f"- {view}: `{path}`")
    return "\n".join(rows)


def prompt_texts(*, units, fix_units, changed, constraints, green_ok, ripple_file: str, world_file: str, passed: dict,
                 declared=None) -> dict:
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
        "plan_declared": declared_section(declared),
        "r4_context": "\n".join([
            f"- 波及の一覧: {ripple_file or '（渡っていない）'}",
            f"- 定石の行: {world_file or '（渡っていない）'}",
            f"- 修正の印: {'・'.join(marks) if marks else '（渡っていない）'}"]),
        "green_line": "" if green_ok is True else GREEN_LINE,
    }


OUTCOMES_HEAD = "### テストごとの base と最後の結末（試験の関門が base と最後に測った 1 件ごと。移り方ごとに全部）"
TDD_PROVED_HEAD = "### TDD のループの記録（修正の段ごと。赤→緑を確かめた単位は名指しのテストつき）"


def tdd_stages(stages, resolve) -> list:
    """修正の段ごとの TDD の記録（fixboard.tdd_units の本文）か読めない訳の並び。stages は段ごとの返りの控えの欄の並び（無ければ None）、
    resolve はポインタを置き場の中のパスに戻す関数。記録の読み手は fixbeside.tdd"""
    import fixbeside
    if stages is None:
        return []
    if not isinstance(stages, list):
        return [f"修正の段の控え（records）が並びでない（{type(stages).__name__}）"]
    return [fixbeside.tdd(stage, resolve) for stage in stages]


def measured_section(test_outcomes, stages: list) -> str:
    """R2 の比較役に貼る機械の実測の節。test_outcomes は試験の関門（final）の返りの欄 {rows, unmeasured}（無ければ None）、stages は
    tdd_stages の並び。測っていない物は推し量らずにそう書く"""
    return "\n".join([OUTCOMES_HEAD, "", *outcome_lines(test_outcomes), "", TDD_PROVED_HEAD, "", *tdd_record_lines(stages)])


# 移り方（base の側→最後の側）の並びの順と、名に添える読み。ここに無い移り方（飛ばし・片側に居ない）は後ろに出会った順
TRANSITIONS = {"赤→緑": "base で赤・最後に緑", "緑→緑": "base でも最後でも緑", "緑→赤": "base で緑・最後に赤", "赤→赤": "base でも最後でも赤"}


def outcome_side(outcome: str) -> str:
    import baseline_red
    if outcome in baseline_red.FAILED:
        return "赤"
    return {"passed": "緑", "skipped": "飛ばし", "": "測っていない"}.get(outcome, outcome)


def outcome_lines(test_outcomes) -> list[str]:
    """テストを移り方ごとにまとめ、移り方の行の下に全部のテストを名指す（緑→緑も省かない。赤の側は結末と落ちた文を添える）"""
    import baseline_red
    if not isinstance(test_outcomes, dict):
        return ["- 試験の関門がテストごとに base と最後を比べた結果（test_outcomes）が渡っていない。どのテストが base と最後に緑か赤かは分からない"]
    if test_outcomes.get("unmeasured"):
        return [f"- 比べていない（{oneline.one_line(test_outcomes['unmeasured'])}）。テストごとの base と最後の結末は測っていない"]
    groups: dict[str, list[str]] = {t: [] for t in TRANSITIONS}
    for r in test_outcomes.get("rows") or []:
        base, final = r.get("base") or "", r.get("final") or ""
        notes = [f"{side} {o}" for side, o in (("base", base), ("最後", final)) if o in baseline_red.FAILED]
        if notes and (why := oneline.one_line(r.get("fail_message") or "")[:200]):
            notes[-1] += f": {why}"
        groups.setdefault(f"{outcome_side(base)}→{outcome_side(final)}", []).append(
            f"  - `{r.get('key')}`" + (f"（{'・'.join(notes)}）" if notes else ""))
    out = []
    for move, rows in groups.items():
        if rows:
            out += [f"- {move}{f'（{TRANSITIONS[move]}）' if move in TRANSITIONS else ''}: {len(rows)} 件", *rows]
    return out or ["- 無い（base と最後のどちらの一式にもテストが居ない）"]


def tdd_record_lines(stages: list) -> list[str]:
    """段ごとの記録を、報告と同じ描き方（report.tdd_lines。段の名は report.tdd_stage_groups）の行に"""
    import report
    named, notes = [], []
    for n, stage in enumerate(stages):
        if isinstance(stage, str):
            notes.append(f"- TDD のループの記録を読めない（{stage}）")
            continue
        named += report.tdd_stage_groups(n, stage)
    rows = [r if r.startswith(" ") else f"- {r}" for r in report.tdd_lines(named)]
    return (rows or ["- 無い（修正の段が走っていない）"]) + notes


def origin_section(repo, base: str, head: str, label: str, *, cumulative_empty: bool, skip=()) -> str:
    """R2 の比較役に貼る累積差分の起点の訳。起点 base（入口の差分の根）が修正前の HEAD head と同じ版か PR の根かを書き、PR の差分
    （base → head。fixboard.pr_diff）とこの run の直しの差分（head → 作業ツリー。fixboard.run_diff）で変わったファイルを分けて
    名指す。どちらも累積差分と同じく除くパスの頭 skip の下は載せない。累積差分が空（cumulative_empty）なら、打ち消し合ったのか何も変えていないのかを分ける。
    label は入口が書いた起点の出どころの文"""
    import fixboard
    import leftovers
    import unittrees
    if not base:
        return "- 累積差分の起点が分からない（始めの記録に入口の base が無い）"
    try:
        base_sha, head_sha = fixboard.pr_revs(repo, base, head)
        pr_files = fixboard.pr_diff(repo, base_sha, head_sha, skip, "--name-only").splitlines()
        commits = int(unittrees._out(repo, "rev-list", "--count", f"{base_sha}..{head_sha}"))
        fix_files = changed_files(fixboard.run_diff(repo, head_sha, skip))
    except (unittrees.UnitTreeError, leftovers.Unreadable, ValueError) as e:
        return f"- 累積差分の起点を測れない（{oneline.one_line(e)}）"
    where = f"（{label}）" if label else ""
    if base_sha == head_sha:
        rows = [f"- 起点は修正前の HEAD `{base_sha[:12]}`{where}。PR の差分は無い（累積差分はこの run の直しの差分だけ）"]
    else:
        rows = [f"- 起点は PR の根 `{base_sha[:12]}`{where}で、修正前の HEAD `{head_sha[:12]}` との間に PR の commit が {commits} 個在る。"
                "累積差分は PR の差分と直しの差分を合わせた物",
                f"- PR の差分（起点 → 修正前の HEAD）で変わったファイル: {'、'.join(pr_files) or '無い'}"]
    rows.append(f"- {FIX_DIFF_ROW}（修正前の HEAD → 作業ツリー）で変わったファイル: {'、'.join(fix_files) or '無い'}")
    if cumulative_empty:
        rows.append("- 累積差分が空なのは、PR の変更と直しが打ち消し合った（直しが PR の変更を元に戻した）から。何もしていないのではない"
                    if pr_files and fix_files else "- 累積差分が空なのは、PR も直しも何も変えていないから")
    return "\n".join(rows)


def after_section(eyes_dir, review_folder, plan) -> str:
    """R1・R3 の頭に貼る直しの後の実測の節: 数の 1 文（控えが無ければ NO_AFTER）。修正案の外れの訳が在る run は、訳の行と事前審査の
    最後の往復の結論を続ける（持ち主の決め tell-downstream。訳の無い run は数の 1 文だけ）。plan は外れの訳の源の plan-fields.json"""
    counts = structmark.after_counts(eyes_dir)
    if not counts:
        return NO_AFTER
    devs = structmark.deviation_lines(eyes_dir)
    return "\n".join([counts, *devs, plan_review_line(review_folder, plan)] if devs else [counts])


def plan_review_line(review_folder, plan) -> str:
    """事前審査の置き場 review_folder の最後に開いた往復が修正案 plan（plan-fields.json）を通したか（往復と案が組むかの照らしの
    持ち主は boardview.read_open_of、通否の持ち主は boardview.verdict）"""
    try:
        inputs = boardview.read_open_of(review_folder, plan)
        if inputs.get("form") == boardview.DESIGN_FORM:
            return REVIEW_UNREAD.format(why=REVIEW_NO_PLAN)
        k = inputs["k"]
        v = boardview.verdict(pathlib.Path(review_folder), inputs)
    except (boardview.Missing, KeyError) as e:
        return REVIEW_UNREAD.format(why=e)
    if v.ok:
        return REVIEW_ACCEPTED.format(k=k)
    if v.gave:
        return REVIEW_GAVE_UP.format(k=k, why=v.gave)
    if v.blocks:
        return REVIEW_BLOCKED.format(k=k, n=len(v.blocks), faces="; ".join(f"{f.get('key')}: {f.get('why')}" for f in v.blocks))
    return REVIEW_HELD.format(k=k, outcome=v.outcome)


def read_json(path):
    """置き場の JSON（パスが無い・ファイルが無い・読めなければ None）"""
    return None if path is None else jsonfile.read_or(path)


def read_design(path) -> dict:
    """独立設計の控え design.json。無い・読めない・object でなければ {"missing": 訳}"""
    if path is None:
        return {"missing": "独立設計のポインタが渡っていない"}
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"missing": f"独立設計の控えが読めない: {e}"}
    return doc if isinstance(doc, dict) else {"missing": "独立設計の控えが JSON の object でない"}


def fell_text(fell: list, ran: str = "") -> str:
    """元 blk-eyes/lib/eyes.py:307。fell は [{lane, eye, state}]。尾は元の「<実行基盤の名>の節が落ちた」から名を外した（E3）"""
    names = "・".join(f["lane"] for f in fell)
    head = f"{names} {FELL_MARK}まま {ran} を回した" if ran else f"{names} {FELL_MARK}"
    return head + "（" + "・".join(f"{f['eye']}: {f['state']}" for f in fell) + "。ノードが落ちた）"


def _read_eye(eyes_dir: pathlib.Path, eye: str) -> tuple[dict | None, str]:
    """(目の返り, 読めない訳)"""
    path = eyes_dir / f"{eye}.json"
    if not path.is_file():
        return None, NO_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"出力のファイルが読めない: {e}"
    return (doc, "") if isinstance(doc, dict) else (None, "出力のファイルが JSON の object でない")


def _protected(protected: dict | None) -> tuple[list, bool]:
    """守りのパスの節の返り（節が落ちていれば None）から (protected_hits, 確かめられたか)。約束の形でない返りも落ちたと数える"""
    if not isinstance(protected, dict) or not isinstance(protected.get("hits"), list):
        return [seal.unknown_row("守りのパスのノードが落ちた")], False
    return list(protected["hits"]), not protected.get("broken")


def unverified(reason: str, protected: dict | None) -> dict:
    """目を数えられない時の返り（r1〜r4 は unverifiable、ok は false）。protected は collect と同じ"""
    row = {"status": seal.UNVERIFIABLE, "reason": reason}
    return {"ok": False, **{e: dict(row) for e in EYES}, "questions": [], "premise_check": None, "structure_after": None,
            "protected_hits": _protected(protected)[0], "notes": None}


def collect(*, eyes_dir, run_eyes: bool, compare_due: bool, premise_due: bool, design: dict, after_ptr,
            protected: dict | None, passed: dict) -> dict:
    """元 blk-eyes/lib/eyes.py:489 の collect と :291 の fallen。目の返りを eyes_dir/<目>.json から読んでブロックの返りを組む。
    protected は守りのパスの節の返り（節が落ちていれば None）。R4 の受け付けが諦めていれば R4 の行の理由に R4_GAVE_UP を足す。
    ok は省いていない目が全部 pass で、前提の検算の道でなく、守りのパスを確かめられた時だけ true"""
    eyes_dir = pathlib.Path(eyes_dir)
    hits, guarded = _protected(protected)
    out = {"ok": False, **{e: None for e in EYES}, "questions": [], "premise_check": None, "structure_after": after_ptr,
           "protected_hits": hits, "notes": None}
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
    gave_up = rolekit.given_up_reason(eyes_dir, R4_NODE)
    if gave_up:
        out["r4"]["reason"] += R4_GAVE_UP.format(why=gave_up)
    out["ok"] = guarded and all(out[e]["status"] == seal.PASSED for e in EYES)
    return out


def write_notes(eyes_dir, *, design_ledger, passed: dict, by: str = gatemarks.PASSED_BY_HUMAN) -> None:
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
             GATE_PASSES: gate_passes(_read_eye(eyes_dir, "r4")[0], passed, by)}
    for name, doc in notes.items():
        (eyes_dir / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


ROLE_WORDS = {"design": "独立の設計を作る役", "compare": "独立の設計と差分を比べる役"}   # R2 の 2 つの役の平易な名（元 line_edge.ROLE_WORDS）
PREMISE_FILE = "premise-check.json"   # 前提の検算（PREMISE）の役の返り（置き場。key・resolution・facts_to_add を持つ）


def r2_input_lines(eyes_dir) -> list:
    """元 works/darkfactory/lib/line_edge.py:529-557 の _r2_inputs。最後の関所と報告の R2 の行の下に並べる行: 比較役が『渡されていない』
    と書いた文と、そのうち渡していた物（compare の claims_given）と、R2 の 2 つの役へ渡した前提の入力の控え（PREMISE_INPUTS）と、
    独立設計の後に来た人の答え（compare の after_design）。控えが無ければその 1 行"""
    pi = read_json(pathlib.Path(eyes_dir) / PREMISE_INPUTS)
    if not isinstance(pi, dict):
        return ["独立の設計と比べる目に渡した入力の控えが無い（R2）"]
    out = [f"独立の設計と比べる目が渡されていないと書いた（R2）: {c}" for c in pi.get("claims") or []]
    led = pi["compare"] if isinstance(pi.get("compare"), dict) else {}
    out += [f"独立の設計と比べる目が渡されていないと書いたが、渡していた（R2）: {m.get('claim')} ← {m.get('kind')}: {m.get('what')}"
            for m in led.get("claims_given") or [] if isinstance(m, dict)]
    late = led.get("after_design")
    if late:
        out.append(f"独立設計の後に来た人の答え（{ROLE_WORDS['compare']}にだけ渡った）: " + "／".join(str(x) for x in late))
    for role in ("design", "compare"):
        led = pi.get(role)
        if not isinstance(led, dict):
            out.append(f"{ROLE_WORDS[role]}に渡した入力の控えが無い（{role}）")
            continue
        given = "／".join(f"{g.get('kind')}: {g.get('what')}" for g in led.get("given") or [] if isinstance(g, dict)) or "（前提の入力は無い）"
        out.append(f"{ROLE_WORDS[role]}に渡した前提の入力（{role}）: {given}")
        held = [w for w in led.get("withheld") or [] if isinstance(w, dict)]
        if held:
            out.append("run に在ったが渡していない: " + "／".join(f"{w.get('kind')}: {w.get('what')}（{w.get('why')}）" for w in held))
    return out


def gate_pass_rows(eyes_dir) -> list | None:
    """人が通したので R4 の問いから外した行（GATE_PASSES。gate_passes の形）。控えが無い・読めなければ None"""
    rows = read_json(pathlib.Path(eyes_dir) / GATE_PASSES)
    return rows if isinstance(rows, list) else None


def premise_facts(eyes_dir) -> dict:
    """前提の検算で仮定が偽（resolved）と分かった時の {key, resolution, facts}（元 review-loop.py:1310-1331 の premise_question と
    :3751-3755 の finalize。問いの key は台帳に held で残り、実測 facts_to_add は次の run の制約に足す）。resolved でない・返りが無ければ
    facts が空の物"""
    doc = read_json(pathlib.Path(eyes_dir) / PREMISE_FILE)
    if not (isinstance(doc, dict) and doc.get("verdict") == "resolved"):
        return {"key": "", "resolution": "", "facts": []}
    return {"key": str(doc.get("key") or ""), "resolution": str(doc.get("resolution") or ""),
            "facts": [f for f in doc.get("facts_to_add") or [] if isinstance(f, str) and f.strip()]}


def premise_fact_lines(eyes_dir) -> list:
    """最後の関所と報告の前提の検算の行の下に並べる行（仮定が偽と分かった問いの key と、次の run の制約に足す実測）"""
    got = premise_facts(eyes_dir)
    if not got["key"]:
        return []
    return [f"仮定は偽と検算した——問い「{got['key']}」は保留（held）のまま残す（次の run の判定が回し直した R2 を見て決める）"
            + (f": {got['resolution']}" if got["resolution"] else ""),
            *(f"次の run の制約に足す実測: {f}" for f in got["facts"])]


def _off_contract(eye: str) -> dict:
    return {"lane": LANE[eye], "eye": eye, "state": "出力の判定の語が約束の外"}


def _row(eye: str, doc: dict | None, fell: dict | None, *, ran: str) -> dict:
    """目の返りの行。許す語は目ごと（seal.eye_statuses）"""
    if doc is None or doc.get("status") not in seal.eye_statuses(eye):
        return {"status": seal.UNVERIFIABLE, "reason": fell_text([fell or _off_contract(eye)], ran)}
    status, reason = doc["status"], str(doc.get("reason"))
    if seal.FIX_NEEDED not in seal.eye_statuses(eye) or status == seal.UNVERIFIABLE:
        return {"status": status, "reason": reason}
    named = doc.get("redesign_points")
    points = [p.strip() for p in named if isinstance(p, str) and p.strip()] if isinstance(named, list) else []
    if not points and named not in (None, []):
        return {"status": seal.UNVERIFIABLE, "reason": BROKEN_POINTS + reason}
    if points:
        head = "" if status == seal.REDESIGN else RAISED_BY_POINTS
        return {"status": seal.REDESIGN, "reason": f"{head}{reason}（組み直す設計の点: {'／'.join(points)}）"}
    if status == seal.REDESIGN:
        return {"status": seal.FIX_NEEDED, "reason": UNNAMED_REDESIGN + reason}
    return {"status": status, "reason": reason}
