"""AI ノードの群ごとの既定の模型と effort の表。

グラフの AI ノードは `model: '@wf-<群>'` と群の名だけを書き、模型の字も effort も書かない。群の既定の値はここ 1 か所に置く。
入口の殻は新しい run に、この表の値を群の別名にした run 1 本ぶんの設定の層を渡す（bin/_lib/place.py の run_config）。呼ぶ人は run を
起こす時に群の名を指して値を付け替えられる。ノードに effort を書くと別名の effort より先に採られて付け替えが効かないので、
ノードにも工程の根にも effort を書かない（柵は workflows/AGENTS.md の E7）。

- GROUPS: '@wf-<群>' → {model, effort, what}。群の名は工場に固有の接頭辞 '@wf-' で始める。どのノードがどの群かは持たない
  （結びはグラフの `model:` が持つ）
- default_of(group): 群の既定の (model, effort)。表に無い名は KeyError
- MODELS・EFFORTS: 役が選んでよい模型と effort の語（弱い順）
- direction(default, chosen): 既定の組と選んだ組の向き（上げ・下げ・同じ・混ざる）
- choices(rows): 頭の深さの役が返した群の選びの行を表と許す語で照らす。外れた行だけ既定に戻して訳を残す（例外を出さない）
"""

GROUPS = {
    "@wf-judge-materials": {"model": "sonnet", "effort": "medium", "what": "判定の素材集めと、読むだけで結論を返す判定の役"},
    "@wf-judge-spec": {"model": "opus", "effort": "medium", "what": "判定の仕様の役"},
    "@wf-judge-core": {"model": "opus", "effort": "high", "what": "判定の本体の審査と、判定の確かめの役"},
    "@wf-fix-writers": {"model": "sonnet", "effort": "high", "what": "修正の書き手（衝突の直し・修正・手直し・TDD）"},
    "@wf-fix-ruler": {"model": "opus", "effort": "high", "what": "修正の規則を決める役"},
    "@wf-fix-consult": {"model": "opus", "effort": "medium", "what": "修正の相談の答えを決める役"},
    "@wf-fix-review": {"model": "sonnet", "effort": "medium", "what": "修正の差分を見る審査の役"},
    "@wf-eyes-read": {"model": "sonnet", "effort": "medium", "what": "目の読むだけの役（コメントの読み）"},
    "@wf-eyes-scope": {"model": "sonnet", "effort": "medium", "what": "目の範囲と整合を見る役"},
    "@wf-eyes-core": {"model": "opus", "effort": "high", "what": "目の本体（最小性・比較・前提の確かめ）"},
    "@wf-plan-structure": {"model": "opus", "effort": "high", "what": "計画の構造を見る役"},
    "@wf-plan-writer": {"model": "opus", "effort": "medium", "what": "計画を書く役"},
    "@wf-plan-review": {"model": "opus", "effort": "high", "what": "計画の設計の審査の役"},
    "@wf-report": {"model": "sonnet", "effort": "medium", "what": "報告の書き手と冷えた読み手"},
    "@wf-test-gate": {"model": "sonnet", "effort": "medium", "what": "試験の起動スクリプトの書き手（試験の関門の用意と、修正の段の書き直し）"},
}


def default_of(group: str) -> tuple[str, str]:
    """群の既定の (model, effort)。表に無い名は KeyError"""
    row = GROUPS[group]
    return row["model"], row["effort"]


MODELS = ("haiku", "sonnet", "opus")
EFFORTS = ("low", "medium", "high", "max")
UP, DOWN, SAME, MIXED = "上げ", "下げ", "同じ", "混ざる"


def direction(default: tuple, chosen: tuple) -> str:
    """既定の (model, effort) に対する選んだ組の向き。両方が強い側か片方だけ強いなら上げ、弱い側なら下げ、模型と effort が逆向きなら混ざる"""
    model = MODELS.index(chosen[0]) - MODELS.index(default[0])
    effort = EFFORTS.index(chosen[1]) - EFFORTS.index(default[1])
    if model == effort == 0:
        return SAME
    if model >= 0 and effort >= 0:
        return UP
    return DOWN if model <= 0 and effort <= 0 else MIXED


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def _line(group, model, effort, why, fallback) -> dict:
    """控えの 1 行。群が表に在れば既定を添える（表に無い群の既定・向きは None・同じ）"""
    default = default_of(group) if group in GROUPS else (None, None)
    way = SAME if fallback or None in default else direction(default, (model, effort))
    return {"group": group, "model": model, "effort": effort, "why": why,
            "default": {"model": default[0], "effort": default[1]}, "direction": way, "fallback": fallback}


def choices(rows) -> list:
    """役が返した群の選びの行（{group, model, effort, why}）の並びを、表と許す語で照らして控える形にする。行ごとに
    {group, model, effort, why, default: {model, effort}, direction, fallback}。群が表に無い・模型か effort が許す語に無い・
    同じ群の 2 行目・形の壊れた行は、その行だけ既定の値に戻して訳を fallback に残す（表に無い群は戻す先が無く model・effort は None）。
    下げの行も既定にせず記録する。並びでない・空の入力は []。例外は出さない"""
    if not isinstance(rows, (list, tuple)):
        return []
    out, seen = [], set()
    for raw in rows:
        row = raw if isinstance(raw, dict) else {}
        group, model, effort, why = (_text(row.get(k)) for k in ("group", "model", "effort", "why"))
        if not isinstance(raw, dict):
            fallback = "行が object でない"
        elif group not in GROUPS:
            fallback = f"群 {group!r} が表に無い" if group else "group が字でない・空"
        elif group in seen:
            fallback = f"{group} の 2 行目（最初の行だけ採る）"
        elif model not in MODELS or effort not in EFFORTS:
            fallback = f"許さない語（model {row.get('model')!r}・effort {row.get('effort')!r}。許すのは {'・'.join(MODELS)} と {'・'.join(EFFORTS)}）"
        else:
            fallback = ""
        if group in GROUPS:
            seen.add(group)
        if fallback:
            model, effort = default_of(group) if group in GROUPS else (None, None)
        out.append(_line(group, model, effort, why, fallback))
    return out
