"""judge の graph の返し 2 つの中身（docs/design/judge-eyes.md の 1.3 の 4 と 10）。値を組むだけで、観点の判断はしない。

- MATERIAL_IDS: 素材の観点の include の id（観点の順。diagnose の materials の並びと、報告の節の並び）
- spec_gate(spec_on, got) -> {go, stop_reason, reason}: 仕様の段を挟まないか、spec の status が approved なら go
- merged(request, added) -> 依頼: 依頼の行（配列か findings を持つ容器）の後ろに、仕様が足した受け入れ条件の行を積む
- diagnose_values(received, verify_by_tier) -> diagnose を回すか（go）と、渡す飛ばされうる値と、判定の裏取りを回すかと、素材の観点の
  返答の引き方（REPLY_SOURCES。観点の役の名と欄の名は graph のここが持ち、diagnose は持たない）
"""
import headdepth  # lib/。段の語
import stopby  # lib/

from src import fallback

SPEC_STOP = stopby.declare("spec", "仕様のループが諦めた・固まらなかった")   # spec の block と同じ名と意味
APPROVED = "approved"
MATERIAL_IDS = fallback.MATERIAL_IDS
SPEC_FELL = "仕様の段が返らなかった"
# diagnose の入力 reply_sources（shared:reply-sources.schema.json）: 判定の材料の鍵 → (素材の観点の role, その返答の中の欄。None は返答
# まるごと)。hygiene の findings・procedure-trace の unmeasured・external-standards の rankings は今も判定役に届いていないので載せない
REPLY_KEYS = {
    "local_findings": ("local-review", "findings"),
    "consistency_findings": ("consistency-bypass", "findings"),
    "bypass_findings": ("consistency-bypass", "bypass_findings"),
    "external_findings": ("external-standards", "findings"),
    "procedure_findings": ("procedure-trace", "findings"),
    "test_double_fidelity": ("test-double-fidelity", None),
    "main_path_observation": ("main-path-observation", None),
    "provenance": ("provenance", None),
    "prior_decisions": ("prior-decisions", None),
    "purpose_review": ("purpose-review", None),
}
# 返答の行を材料の行に辿る素材（P1 の目だけ。prior-decisions と purpose-review は辿らない）と、記録された方針を持つ素材
TRAIL_ROLES = ("local-review", "consistency-bypass", "hygiene", "external-standards", "procedure-trace",
               "test-double-fidelity", "main-path-observation", "provenance")
DECISIONS_ROLE = "prior-decisions"
REPLY_SOURCES = {"replies": [{"key": key, "role": role, "field": field} for key, (role, field) in REPLY_KEYS.items()],
                 "trail": list(TRAIL_ROLES), "decisions": DECISIONS_ROLE}


def spec_gate(spec_on: bool, got: dict | None) -> dict:
    if not spec_on:
        return {"go": True, "stop_reason": "", "reason": ""}
    if not isinstance(got, dict):
        return {"go": False, "stop_reason": SPEC_STOP, "reason": SPEC_FELL}
    if got.get("status") == APPROVED:
        return {"go": True, "stop_reason": "", "reason": ""}
    return {"go": False, "stop_reason": str(got.get("stop_reason") or SPEC_STOP),
            "reason": str(got.get("reason") or f"仕様の段が承認で終わらなかった（{got.get('status')}）")}


def merged(request, added: list):
    """仕様が足した行は、今の judge の spec_freeze が依頼の行のファイルに積んだのと同じく、後の段（並行 PR・前提の実測・世界の解・
    先行議論の突合）が依頼の行として読む"""
    if not added:
        return request
    if isinstance(request, dict):
        return {**request, "findings": [*(request.get("findings") or []), *added]}
    return [*(request or []), *added]


def diagnose_values(received: dict, verify_by_tier: dict) -> dict:
    """received は include の id → 受け皿の got（返りが無ければ None）。素材の観点の id と parallel-pr・world・head-depth・
    premises・purpose と、返し spec-in の出力を "spec-in" で持つ。go は前提の実測と目的の固定が通ったか（diagnose の when: が読む。
    Archon は when: が飛んだ node の出力を読むと落とすので、diagnose は返しの欄だけを読む）"""
    materials, missing = [], []
    for name in MATERIAL_IDS:
        got = received.get(name)
        if isinstance(got, dict) and got.get("material"):
            materials.append(got["material"])
        else:
            missing.append(name)
    pr, world, head, spec, premises, purpose = (received.get(k) for k in ("parallel-pr", "world", "head-depth", "spec-in", "premises",
                                                                           "purpose"))
    premises = premises if isinstance(premises, dict) else {}
    purpose = purpose if isinstance(purpose, dict) else {}
    head = head if isinstance(head, dict) else None
    spec = spec if isinstance(spec, dict) else {}
    tier = head["tier"] if head and head.get("tier") else headdepth.STANDARD
    verify = verify_by_tier.get(tier) is True
    return {"ok": True, "reason": "", "go": premises.get("ok") is True and purpose.get("ok") is True,
            "purpose": purpose.get("purpose"), "constraints": premises.get("constraints"), "materials": materials, "missing": missing,
            "pr_material": pr.get("material") if isinstance(pr, dict) else None,
            "world_rows": world.get("rows") if isinstance(world, dict) else None,
            "row_asks": (head.get("rows") or []) if head else [],
            "depth_why": str(head.get("why") or "") if head else "",
            "spec_rows": spec.get("added_rows"), "spec_origin": str(spec.get("added_origin") or ""),
            "tier": tier, "verify": verify, "reply_sources": REPLY_SOURCES}
