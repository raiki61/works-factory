"""最後の承認ノードと報告の R2 の行の下に並べる材料（docs/design/r2.md の 1.5・5.2）。lib/eyeverdict.py の write_notes の R2 の半分・
r2_input_lines・ROLE_WORDS・premise_facts・premise_fact_lines の写し。控えの pointer でなく、書いた値と行を返す。"""
from __future__ import annotations

import pathlib

import design     # lib/。claims_unpassed・claims_given
import jsonfile   # lib/

from src import due, files

ROLE_WORDS = {"design": "独立の設計を作る役", "compare": "独立の設計と差分を比べる役"}   # R2 の 2 つの役の平易な名（元 line_edge.ROLE_WORDS）
NO_INPUTS = "独立の設計と比べる目に渡した入力の控えが無い（R2）"
PREMISE_NO_REPLY = "前提の検算の役の出力が無い: 偽と分かった仮定と次の run の制約に足す実測は読んでいない"


def write(out, design_premises, compare_reply) -> dict:
    """premise-inputs.json に {design: 独立設計の控え（port design_premises の値）, compare: 比べの役に貼った前提の控え r2-premises.json に
    claims_given を足した物（比べの役を起こさなかった run は null）, claims: 比べの返答の『渡されていない』の文}を書いて返す。
    拒まない・判定を書き換えない"""
    out = pathlib.Path(out)
    compare = jsonfile.read_or(out / files.PREMISES)
    claims = design.claims_unpassed(compare_reply)
    if isinstance(compare, dict):
        compare["claims_given"] = design.claims_given(claims, compare.get("given"))
    doc = {"design": design_premises, "compare": compare, "claims": claims}
    jsonfile.write(out / files.INPUTS, doc)
    return doc


def input_lines(pi) -> list:
    """最後の承認ノードと報告の R2 の行の下に並べる行: 比べの役が『渡されていない』と書いた文と、そのうち渡していた物（compare の
    claims_given）と、R2 の 2 つの役へ渡した前提の入力の控えと、独立設計の後に来た人の答え（compare の after_design）。控えが無ければその 1 行"""
    if not isinstance(pi, dict):
        return [NO_INPUTS]
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


def premise_facts(reply) -> dict:
    """前提の検算で仮定が偽（resolved）と分かった時の {key, resolution, facts}（問いの key は台帳に held で残り、実測 facts_to_add は
    次の run の制約に足す）。reply は検算の役の返答の値。resolved でない・返答が無ければ中身が空の物"""
    if not (isinstance(reply, dict) and reply.get("verdict") == due.VERDICTS[0]):
        return {"key": "", "resolution": "", "facts": []}
    return {"key": str(reply.get("key") or ""), "resolution": str(reply.get("resolution") or ""),
            "facts": [f for f in reply.get("facts_to_add") or [] if isinstance(f, str) and f.strip()]}


def premise_fact_lines(facts, replied: bool) -> list:
    """報告の前提の検算の行の下に並べる行。facts は premise_facts の値、replied は検算の役の返答のファイルが読めたか。読めなければ
    役の出力が無いと 1 行で言う"""
    if not replied:
        return [PREMISE_NO_REPLY]
    if not facts["key"]:
        return []
    return [f"仮定は偽と検算した——問い「{facts['key']}」は保留（held）のまま残す（次の run の判定が回し直した R2 を見て決める）"
            + (f": {facts['resolution']}" if facts["resolution"] else ""),
            *(f"次の run の制約に足す実測: {f}" for f in facts["facts"])]
