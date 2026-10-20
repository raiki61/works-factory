"""judge の graph のまとめが落ちた時の出力（docs/design/judge-eyes.md の 0 節の「返す node は落ちない」）。標準ライブラリだけ
（verdict の script が lib と境の口を読めない時にも同じ形を返す）。

- include_id(name) -> block の名 name を include した node の id（INCLUDE_IDS の行は <名>-run、ほかは名のまま）
- OPTIONAL: 落ちても判定が進む段の宣言 [{node, bare}]（世界の解・run の頭の深さ・素材の観点 10 本。頭は include の id）
- fallen(why) -> 1.2 の欄を全部持つ止めの出力（stop_reason は works:judge）
"""
OWN_TITLE = "判定のまとめ"
# 素材の観点の block の名。gate-efficacy は入れない（重い検算は run の中で回さない持ち主の決め 2026-10-19。diagnose は
# 返らない観点を materialkit.assemble で not_run に埋める）
MATERIAL_IDS = ("prior-decisions", "purpose-review", "local-review", "consistency-bypass", "hygiene", "external-standards",
                "procedure-trace", "test-double-fidelity", "main-path-observation", "provenance")
# include の id が block の名と違う block（<名>-run）。block の中の node（loop_group の本体の中の物も）と同じ id で include すると、
# Archon の include の展開は本体の中の `$<id>.output` を改めず、include の返す node を指してしまう（tests/layers/test_block_shape.py の 13）
INCLUDE_IDS = {name: f"{name}-run" for name in ("head-depth", "premises", "purpose", *MATERIAL_IDS, "diagnose")}


def include_id(name: str) -> str:
    return INCLUDE_IDS.get(name, name)


OPTIONAL = [{"node": f"{include_id(name)}__", "bare": False} for name in ("world", "head-depth", *MATERIAL_IDS)]
JUDGE_STOP = "works:judge"
STANDARD = "標準"


def fallen(why: str) -> dict:
    line = f"- 判定のまとめが落ちた（{why}）"
    return {"ok": False, "stop_reason": JUDGE_STOP, "reason": f"判定のまとめが落ちた: {why}", "ready": False, "units": [], "questions": [],
            "judgment": None, "answer_ties": None, "out_of_purpose": None, "materials": None, "brief": None, "inputs": None,
            "purpose": None, "purpose_text": "", "purpose_source": "", "means": [], "purpose_review": None, "constraints": None,
            "world": None, "world_state": {"status": "failed", "reason": why, "classes": 0, "dropped": 0}, "spec": None,
            "spec_rows": None, "spec_origin": "", "excluded": None, "pr_drafts": None, "downgrades": [], "decisions": None,
            "tier": STANDARD, "tier_why": why, "row_asks": [], "tier_record": None, "verify": None, "verify_why": why,
            "report": [line], "sections": [{"title": OWN_TITLE, "lines": [line]}], "optional": [dict(r) for r in OPTIONAL]}
