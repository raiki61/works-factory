"""eyes の graph のまとめ（docs/design/judge-eyes.md の 2.4。今の lib/eyeverdict.py の collect のまとめの部分）。目ごとの block の
判定の行と直した後の実測の出力を受け、変更を通してよいか（ok）と、line が読む欄と、報告の節を組む。判定の行は block が決め、ここは
決め直さない（返らなかった目を unverifiable にし、「まま R4 を回した」の尾を足すだけ）。

- TITLES: include の id → 報告の節の見出し
- rows(received, merge) -> {r1..r4: 判定の行か null}: run が真の時の目の行
- build(received, *, run, merge, skip_why) -> まとめの出力

received は include の id（structure-after・r1〜r4）→ 受け皿の got（返りが無ければ None）。
"""
import eyekit  # lib/。返らなかった目の訳（fell_text・FELL_MARK）
import oneline  # lib/
import seal  # lib/。判定の語

from src import fallback

TITLES = {"structure-after": "直した後の構造の実測", "r1": "独立の目 R1 最小性とコメント", "r2": "独立の目 R2 独立設計との比べと前提の検算",
          "r3": "独立の目 R3 全体の整合", "r4": "独立の目 R4 見えていない範囲"}
OWN_TITLE = fallback.OWN_TITLE
NO_OUTPUT = "出力が無い"
NO_COHERENCE = "まとめた R3 の行（coherence）が無い"
RAN_R4 = "まま R4 を回した"
WAITED_BY_R4 = ("r1", "r2")   # R4 が待つ目（E8）。この目が落ちても R4 は回るので、落ちた訳に尾を足す


def _got(received: dict, name: str) -> dict | None:
    got = received.get(name)
    return got if isinstance(got, dict) else None


def _row(got: dict | None, eye: str) -> dict:
    row = (got or {}).get("verdict")
    if isinstance(row, dict) and isinstance(row.get("status"), str):
        return {"status": row["status"], "reason": str(row.get("reason") or "")}
    return {"status": seal.UNVERIFIABLE, "reason": eyekit.fell_text(eye, NO_OUTPUT)}


def rows(received: dict, merge: bool) -> dict:
    r4 = _got(received, "r4")
    out = {eye: _row(_got(received, eye), eye) for eye in ("r1", "r2", "r4")}
    if merge:
        coherence = (r4 or {}).get("coherence")
        out["r3"] = ({"status": coherence["status"], "reason": str(coherence.get("reason") or "")}
                     if isinstance(coherence, dict) and isinstance(coherence.get("status"), str)
                     else {"status": seal.UNVERIFIABLE, "reason": eyekit.fell_text("r4", NO_COHERENCE)})
    else:
        out["r3"] = _row(_got(received, "r3"), "r3")
    if r4 is not None:
        for eye in WAITED_BY_R4:
            reason = out[eye]["reason"]
            if eyekit.FELL_MARK in reason and RAN_R4 not in reason:
                out[eye]["reason"] = reason.replace(eyekit.FELL_MARK, eyekit.FELL_MARK + RAN_R4, 1)
    return {eye: out[eye] for eye in ("r1", "r2", "r3", "r4")}


def _absorbed(after: dict | None) -> list:
    out = [dict(r) for r in fallback.OPTIONAL]
    for row in (after or {}).get("optional") or []:
        if isinstance(row, dict) and isinstance(row.get("node"), str) and row["node"]:
            item = {"node": row["node"], "bare": True} if row.get("bare") is True else {"node": f"structure-after__{row['node']}", "bare": False}
            if item not in out:
                out.append(item)
    return out


def build(received: dict, *, run: bool, merge: bool, skip_why: str) -> dict:
    after = _got(received, "structure-after")
    r2, r4 = _got(received, "r2"), _got(received, "r4")
    own = []
    if run:
        got_rows = rows(received, merge)
        premise = r2.get("premise_check") if r2 else None
        ok = premise is None and all(row["status"] == seal.PASSED for row in got_rows.values())
        bad = [f"{eye.upper()}: {row['status']}" for eye, row in got_rows.items() if row["status"] != seal.PASSED]
        own.append("- 変更を通してよい（どの目も pass）" if ok else
                   "- 変更を通してよいと言えない（" + "・".join(bad + (["R2 が前提の検算の道"] if premise is not None else [])) + "）")
        if merge:
            own.append("- R3 の観点は R4 の会話にまとめた（R3 の行は R4 の coherence）")
    else:
        got_rows = dict.fromkeys(("r1", "r2", "r3", "r4"))
        premise, ok = None, True
        own.append(f"- 独立の目: 深さで省いた（{oneline.one_line(skip_why) or '訳が渡されていない'}）")
    after_ok = bool(after) and after.get("ok") is True
    if not after_ok:
        why = (after or {}).get("reason") or "直した後の構造の実測の段が返らなかった"
        own.append(f"- 直した後の構造の実測が無い（{oneline.one_line(why)}）")
    sections = []
    for name, title in TITLES.items():
        got = _got(received, name)
        if got is not None and isinstance(got.get("report"), list) and not (name == "r3" and merge):
            sections.append({"title": title, "lines": [str(x) for x in got["report"]]})
    sections.append({"title": OWN_TITLE, "lines": own})
    return {"ok": ok, **got_rows,
            "questions": [str(q) for q in (r4 or {}).get("questions") or []] if run else [],
            "passes": list((r4 or {}).get("passes") or []) if run else [],
            "premise_check": premise, "notes": [str(n) for n in (r2 or {}).get("notes") or []] if run else [],
            "after": (after or {}).get("after"), "dirty": int((after or {}).get("dirty") or 0),
            "escalate": int((after or {}).get("escalate") or 0), "after_ok": after_ok,
            "report": own, "sections": sections, "optional": _absorbed(after)}
