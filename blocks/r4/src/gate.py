"""修正前の承認ノードで通した行と、R4 の問いの行（docs/design/r4.md の 1.5）。lib/eyeverdict.py の写し（_human_passed・
carried_section と declared_section の行の部分・R4_ROWS・_r4_rows・r4_gate_items・passed_by・gate_passes・R4_REJECT・R4_GAVE_UP）。
見出しと頼みの文（gatemarks.CARRIED_HEAD・CARRIED_ASK、eyeverdict.DECLARED_HEAD・DECLARED_ASK）は写さず、prompts/r4-scope.md が持つ。
"""
import answer      # lib/
import gatemarks   # lib/
import policy      # lib/

# 元 .shared/core/graphloops/rules/review-loop.py:4103 の R4_ROWS（種類・R4 の返りの欄・行の頭）
R4_ROWS = (("regression", "lost", "R4 が BASE から消えたと見た能力: "),
           (policy.POLICY_KIND, "policy_conflicts", "R4 が見た人の方針とのぶつかり: "))
R4_REJECT = (f"policy_conflicts の次の行は{policy.RECORDED_TERM}のどの行も名指さない。{policy.RECORDED_REF}の行の名指しを字のまま"
             "写して書き直すか、一覧に無いコードのコメント・docstring・テストの説明文（対象の文で、方針ではない）なら policy_conflicts "
             "から外せ。下の行を全部直して、返答を丸ごと出し直せ:")
R4_GAVE_UP = "（R4 の方針とのぶつかりの名指しが受け付けを通らなかったので、名指さない行も人に聞く: {why}）"


def lines(rows: list) -> str:
    """「- <行>」の並び"""
    return "\n".join(f"- {r}" for r in rows)


def human_passed(asked, before_fix) -> dict:
    """元 eyeverdict._human_passed。修正前の承認ノードの答え before_fix（{decision, text, asked}）が通す語なら、そこで聞いた項目 asked
    （{kind, text}）のうち狭める能力と事前審査の穴の行を {(種類, 頭と推しの尾を外した本文): 答えた周} で返す（台帳の問いの行は数えない。
    1 run 1 周）"""
    if not isinstance(before_fix, dict) or before_fix.get("decision") not in answer.GO_WORDS:
        return {}
    out = {}
    for a in gatemarks.row_texts(asked):
        m = gatemarks.NARROW_HEAD.match(a)
        f = None if m else gatemarks.FACE_HEAD.match(a)
        if m or f:
            out.setdefault(("regression" if m else f.group(1), gatemarks.PUSH_TAIL.sub("", a[(m or f).end():])), 1)
    return out


def carried_rows(passed: dict) -> str:
    """指示の段落 carried の行 `- [<種類>] <本文>`（通した行が無ければ空の字）"""
    return lines([f"[{kind}] {body}" for kind, body in passed])


def declared_rows(rows) -> str:
    """指示の段落 declared の行 `- <行>`（直さずに残すと答えた事前審査の block の行。無ければ空の字）"""
    return lines([r for r in rows or [] if isinstance(r, str) and r.strip()] if isinstance(rows, list) else [])


def rows(r4) -> list:
    """元 _r4_rows。R4 の消えた能力と方針とのぶつかりの [(種類, 行の頭, 本文)]"""
    r4 = r4 or {}
    got = {"lost": (r4.get("capability_inventory") or {}).get("lost") or [], "policy_conflicts": r4.get("policy_conflicts") or []}
    return [(kind, head, x) for kind, field, head in R4_ROWS for x in got[field]]


def r4_gate_items(r4, passed: dict) -> list:
    """元 r4_gate_items。R4 の消えた能力と方針とのぶつかりの行から、人が通した行と種類も頭を除いた本文も同じ物を外す（種類が違えば
    聞き直す）。外した行は gate_passes が控える"""
    return [head + x for kind, head, x in rows(r4) if (kind, x) not in passed]


def passed_by(before_fix) -> str:
    """元 passed_by。修正前の承認ノードの答えが通した行の控えの印: 無人の run が推しで通した答え（欄 answer.PUSHED）は PASSED_BY_PUSH、
    ほかは人"""
    return gatemarks.PASSED_BY_PUSH if answer.by_push(before_fix) else gatemarks.PASSED_BY_HUMAN


def gate_passes(r4, passed: dict, by: str) -> list:
    """元 gate_passes。r4_gate_items が外した行を、修正前の承認ノードで通した印 by つきで控える（gatemarks._keep の行の形）"""
    return [{"node": gatemarks.R4_GATE_NODE, "round": 1, "by": by, "item": head + x,
             "passed_at": {"node": gatemarks.GATE_NODE, "round": passed[(kind, x)]}}
            for kind, head, x in rows(r4) if (kind, x) in passed]
