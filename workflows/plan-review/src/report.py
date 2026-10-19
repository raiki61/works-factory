"""事前審査の報告の行（docs/design/plan-review.md の 12 節）。この block は 1 往復分の 1 行だけを組む（往復ごとの記録の行・
聞かずに通した行は line が、受けた設計の返答の行は設計を返した側が組む）。

- 形 plan で通った時: 「事前審査（<k> 往復目・修正案）: block <key の並びか「無い」>・suggest <n> 件・別案 <n> 件<・木（項目 <n> 本）>」
- 形 replan で通った時: 「事前審査（案の直し・項目 <番号>）: block …・suggest … 件・別案 … 件」
- 形 text で通った時: 頭の 1 行「事前審査（方針の文）: 穴 <n> 件（block <m>）・別案 <n> 件」と、block の穴ごとに「- [<kind>] <key>: <why の 1 行>」
- 諦めた・落ちた時: 「事前審査: <reason>」
- どの時も、読んだ証拠が欠けた時は「事前審査の役が渡したファイルを読んだ記録が無い（<パス>…）」、集める node が落ちた時は
  「事前審査: 読んだ証拠を集められなかった（<訳>）」を後ろに足す（今の報告の読んだ証拠の行。受け付けの条件ではない）
"""
from __future__ import annotations

import converge   # lib/。block_faces
import oneline    # lib/

HEAD = "事前審査"
PLAN_WORD = "修正案"
NONE = "無い"


def _counts(review: dict) -> str:
    blocks = [str(f.get("key")) for f in converge.block_faces(review)]
    suggests = [f for f in review.get("faces") or [] if isinstance(f, dict) and f.get("severity") == "suggest"]
    shrink = [s for s in review.get("shrink") or [] if isinstance(s, dict)]
    return f"block {'、'.join(blocks) or NONE}・suggest {len(suggests)} 件・別案 {len(shrink)} 件"


def lines(*, status: str, form: str, reason: str, review: dict | None = None, k: int = 0, ruled=(), tree_items: int = 0,
          missing=(), proof_failed: str = "") -> list:
    """報告の行（頭の行と、読んだ証拠の欠けの行）。missing は役が読んだ跡の無いパス、proof_failed は集める node が落ちた訳"""
    out = _head(status=status, form=form, reason=reason, review=review, k=k, ruled=ruled, tree_items=tree_items)
    if missing:
        out.append(f"{HEAD}の役が渡したファイルを読んだ記録が無い（{'・'.join(map(str, missing))}）")
    if proof_failed:
        out.append(f"{HEAD}: 読んだ証拠を集められなかった（{oneline.one_line(proof_failed)}）")
    return out


def _head(*, status: str, form: str, reason: str, review: dict | None, k: int, ruled, tree_items: int) -> list:
    """報告に載せる日本語の行。status は ok・gave_up・failed、review は受けた審査の返答（review.json。通った時だけ読む）、k は
    形 plan の往復の番号、ruled は形 replan の裁かれた項目の番号、tree_items は木の往復で下請けを起こした項目の数（木でなければ 0）"""
    if status != "ok" or not isinstance(review, dict):
        return [f"{HEAD}: {oneline.one_line(reason)}"]
    if form == "text":
        faces = [f for f in review.get("faces") or [] if isinstance(f, dict)]
        blocks = converge.block_faces(review)
        shrink = [s for s in review.get("shrink") or [] if isinstance(s, dict)]
        return [f"{HEAD}（方針の文）: 穴 {len(faces)} 件（block {len(blocks)}）・別案 {len(shrink)} 件",
                *(f"- [{f.get('kind')}] {f.get('key')}: {oneline.one_line(f.get('why'))}" for f in blocks)]
    if form == "replan":
        return [f"{HEAD}（案の直し・項目 {'、'.join(str(n) for n in ruled)}）: {_counts(review)}"]
    tree = f"・木（項目 {tree_items} 本）" if tree_items else ""
    return [f"{HEAD}（{k} 往復目・{PLAN_WORD}）: {_counts(review)}{tree}"]
