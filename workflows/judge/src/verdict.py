"""judge の graph のまとめ（docs/design/judge-eyes.md の 1.4）。include した block の受け皿の got を読み、止めの語の順の最初の物と、
line が配る欄と、報告の節を組む。観点の判断はしない（どれも block の出力の欄を運ぶだけ）。

- TITLES: include の id → 報告の節の見出し（並びは 1.3 の順）
- stop_of(received) -> (止めの語, 訳): 1.4 の順（仕様・並行 PR・前提の実測・目的の固定・判定・判定の裏取り）の最初の物。無ければ ("", "")
- build(received, *, world_on, world_has_rows, notes) -> まとめの出力（purpose_review の欄は script が pointer を入れる。notes は
  script が読めなかった物の行）

received は include の id → 受け皿の got（返りが無ければ None）。返しの "spec-in"・"diagnose-in" は、その出力（走らなければ None）。
"""
import headdepth  # lib/。段の語
import oneline  # lib/
import stopby  # lib/

from src import fallback, feed

JUDGE_STOP = stopby.declare("judge", "受け付けを通った判定が無いままループを抜けた")   # diagnose の block と同じ名と意味
TITLES = {"head-depth": "run の頭の深さ", "spec": "仕様", "parallel-pr": "並行 PR", "premises": "前提の実測", "purpose": "目的の固定",
          "world": "世界の解", "prior-decisions": "素材: 先行議論の突合", "purpose-review": "素材: 目的の監査",
          "local-review": "素材: 局所レビュー", "consistency-bypass": "素材: 整合性と標準機構の迂回", "hygiene": "素材: コード衛生",
          "external-standards": "素材: 外部標準の照合", "procedure-trace": "素材: 手順トレース", "test-double-fidelity": "素材: 代役の忠実性",
          "main-path-observation": "素材: 主経路の実行観測", "provenance": "素材: 根拠の出所", "diagnose": "根本の診断",
          "verify": "判定の単位の裏取り"}
OWN_TITLE = fallback.OWN_TITLE
# 落ちても判定が進む段（line の collect が include の頭を付けて読む）
OPTIONAL = fallback.OPTIONAL
NO_TIER_WHY = "run の頭の深さの段が返らなかった（標準で進む）"
FELL = "{title}の段が返らなかった"


def _got(received: dict, name: str) -> dict | None:
    got = received.get(name)
    return got if isinstance(got, dict) else None


def stop_of(received: dict) -> tuple:
    spec_in = _got(received, "spec-in")
    if spec_in and spec_in.get("stop_reason"):
        return spec_in["stop_reason"], str(spec_in.get("reason") or "")
    pr = _got(received, "parallel-pr")
    if pr is None:
        return stopby.PR, FELL.format(title=TITLES["parallel-pr"])
    if pr.get("stop_reason"):
        return pr["stop_reason"], str(pr.get("reason") or "")
    for name, word in (("premises", stopby.PREMISES), ("purpose", stopby.PURPOSE)):
        got = _got(received, name)
        if got is None or got.get("ok") is not True:
            return word, str((got or {}).get("reason") or FELL.format(title=TITLES[name]))
    diagnose = _got(received, "diagnose")
    if diagnose is None:
        feed_in = _got(received, "diagnose-in")
        why = feed_in.get("reason") if feed_in and feed_in.get("ok") is not True else ""
        return JUDGE_STOP, str(why or FELL.format(title=TITLES["diagnose"]))
    if diagnose.get("stop_reason"):
        return diagnose["stop_reason"], str(diagnose.get("reason") or "")
    verify = _got(received, "verify")
    if verify and verify.get("stop_reason"):
        return verify["stop_reason"], str(verify.get("reason") or "")
    return "", ""


def _world_state(received: dict, world_on: bool) -> dict:
    world = _got(received, "world")
    if world is not None:
        return {k: world.get(k) for k in ("status", "reason", "classes", "dropped")}
    purpose = _got(received, "purpose")
    if not world_on:
        why = "世界の解の段を切った run（world: false）"
    elif purpose is None or purpose.get("ok") is not True:
        why = "目的の固定が通らなかったので回さなかった"
    else:
        return {"status": "failed", "reason": FELL.format(title=TITLES["world"]), "classes": 0, "dropped": 0}
    return {"status": "skipped", "reason": why, "classes": 0, "dropped": 0}


def _verify_why(received: dict, stop: str) -> str:
    verify, diagnose, feed_in = (_got(received, k) for k in ("verify", "diagnose", "diagnose-in"))
    if verify is not None:
        return str(verify.get("reason") or "") if verify.get("verify") is None or not verify.get("ok") else ""
    if stop or feed_in is None or diagnose is None:
        return "判定が止まったので回さなかった"
    if feed_in.get("verify") is not True:
        return f"段 {feed_in.get('tier')} では判定の裏取りを回さない（段ごとの表）"
    if diagnose.get("ready") is not True:
        return "開いた単位が無いので回さなかった"
    return FELL.format(title=TITLES["verify"])


def _report(received: dict, stop: str, why: str, world_on: bool, verify_why: str) -> list:
    lines = [f"- 止めた（{stop}）: {oneline.one_line(why)}"] if stop else []
    head = _got(received, "head-depth")
    if head is None:
        lines.append(f"- {NO_TIER_WHY}")
    if _got(received, "world") is None and world_on and _got(received, "purpose") and _got(received, "purpose").get("ok") is True:
        lines.append(f"- {FELL.format(title=TITLES['world'])}（世界の解の行なしで進んだ）")
    elif not world_on:
        lines.append("- 世界の解: 回さなかった（world: false）")
    feed_in = _got(received, "diagnose-in") or {}
    for name in (feed_in.get("missing") or []) if feed_in.get("go") is True else []:
        lines.append(f"- {FELL.format(title=TITLES.get(name, name))}（素材は not_run で埋めた）")
    if verify_why:
        lines.append(f"- 判定の裏取り: {verify_why}")
    return lines


def _sections(received: dict, own: list) -> list:
    out = []
    for name, title in TITLES.items():
        got = _got(received, name)
        if got is not None and isinstance(got.get("report"), list):
            out.append({"title": title, "lines": [str(x) for x in got["report"]]})
    out.append({"title": OWN_TITLE, "lines": own or ["- 止めずに判定まで進んだ"]})
    return out


def _absorbed(received: dict) -> list:
    """自分の宣言に、include した block の返りの optional（[{node, bare}]）を include の id の頭を付けて足す"""
    rows = list(OPTIONAL)
    for name in TITLES:
        got = _got(received, name)
        for row in (got or {}).get("optional") or []:
            if isinstance(row, dict) and isinstance(row.get("node"), str) and row["node"]:
                rows.append(row if row.get("bare") is True else {"node": f"{name}__{row['node']}", "bare": False})
    seen, out = set(), []
    for row in rows:
        key = (row["node"], row.get("bare") is True)
        if key not in seen:
            seen.add(key)
            out.append({"node": row["node"], "bare": row.get("bare") is True})
    return out


def build(received: dict, *, world_on: bool, world_has_rows: bool, notes: tuple = ()) -> dict:
    stop, why = stop_of(received)
    head, spec_in, pr, premises, purpose, world, diagnose, verify, decisions = (
        _got(received, k) for k in ("head-depth", "spec-in", "parallel-pr", "premises", "purpose", "world", "diagnose", "verify",
                                    "prior-decisions"))
    diagnose = diagnose or {}
    verify_why = _verify_why(received, stop)
    own = [*_report(received, stop, why, world_on, verify_why), *(f"- {n}" for n in notes)]
    return {
        "ok": not stop, "stop_reason": stop, "reason": why,
        "ready": not stop and diagnose.get("ready") is True,
        "units": (diagnose.get("units") or []) if not stop else [],
        "questions": (diagnose.get("questions") or []) if not stop else [],
        **{k: diagnose.get(k) for k in ("judgment", "answer_ties", "out_of_purpose", "materials", "brief", "inputs")},
        "purpose": (purpose or {}).get("purpose"), "purpose_text": str((purpose or {}).get("purpose_text") or ""),
        "purpose_source": str((purpose or {}).get("source") or ""), "means": (purpose or {}).get("means") or [],
        "purpose_review": None,
        "constraints": (premises or {}).get("constraints"),
        "world": (world or {}).get("rows") if world_has_rows else None,
        "world_state": _world_state(received, world_on),
        "spec": (spec_in or {}).get("spec"), "spec_rows": (spec_in or {}).get("added_rows"),
        "spec_origin": str((spec_in or {}).get("added_origin") or ""),
        "excluded": (pr or {}).get("excluded"), "pr_drafts": (pr or {}).get("drafts"),
        "downgrades": [*((pr or {}).get("downgrades") or []), *(diagnose.get("downgrades") or [])],
        "decisions": (decisions or {}).get("material"),
        "tier": head["tier"] if head and head.get("tier") else headdepth.STANDARD,
        "tier_why": str(head.get("why") or "") if head else NO_TIER_WHY,
        "row_asks": (head or {}).get("rows") or [], "tier_record": (head or {}).get("record"),
        "verify": (verify or {}).get("verify"), "verify_why": verify_why,
        "report": own, "sections": _sections(received, own), "optional": _absorbed(received),
    }
