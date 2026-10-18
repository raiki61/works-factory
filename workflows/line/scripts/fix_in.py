# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正の段へ運ぶ値を 1 か所に集める中継のノード fix-in（docs/design.md の「順と承認ノード」の 7）。

fix から後ろのノードは、直す前のテスト・判定・計画の往復・修正前の承認の答えを、ここの返りの欄（$fix-in.output.<欄>）からだけ読む。
- 通常の run: 受け皿（test-gate-base-out・judge-out・plan-rounds-out・plan-rounds-review-out）の got と修正前の承認の答え・載せなかった
  問いを received に組み、平らな欄にする。go は修正前の承認を通ったか。go が真なら、修正の前に 1 度だけ run の置き場を固定材料に写す
  （lib/fixture.py の noted_capture。received を運ぶ値として控えに入れる。写せなくても止めない）
- 固定材料の run（start が取り込んだ）: start が置いた書き換え済みの運ぶ値を received にし、同じ式で平らな欄にする。go は起動の承認を
  通ったか（直す前のテスト・判定・計画・修正前の承認は飛んでいる）。写さない。返りの received は collect が飛んだ段の代わりに読む
落ちない（boundary.run）。この版より前に走った判定・計画の返り（judge_accept.require_ports・planfile.require_ports）を resume で受けた
通常の run は fallback で止める。

入力（with:）: fixture（start の fixture）・start_go・test_gate_base・judge・plan・plan_review（受け皿の出力）・before_fix_go・
before_fix_answer・deferred
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import fixture
    import judge_accept
    import planfile

# 平らな欄 ← (運ぶ値の欄, 受け皿の got の欄)
FLAT = {"baseline": ("test_gate_base", "baseline"),
        **{name: ("judge", name) for name in ("units", "judgment", "purpose", "world", "spec", "rejudge_verdict", "premises", "verify",
                                              "pr_excluded", "materials", "purpose_review", "depth_record", "decisions", "answer_ties",
                                              "purpose_means")},
        "head_depth": ("judge", "depth"),
        **{name: ("plan", name) for name in ("plan", "ripple", "structure", "fix_plan")},
        "depth": ("plan", "depth"),
        **{name: ("plan_review", name) for name in ("review", "design", "questions")}}


def got(raw) -> dict | None:
    """受け皿の出力の got（飛んだ受け皿は None）"""
    out = boundary.value(raw)
    return out.get("got") if isinstance(out, dict) else None


def received_live(env) -> dict:
    """運ぶ値。鍵は collect の欄の名（collect はこの鍵で埋める）。欄か受け皿の got の欄を変える時は lib/fixture.py の FORMAT を
    上げる（tests/workflows/test_line.py の CarriedShapeCase が main との分かれ目と比べる）"""
    return {"test_gate_base": got(env.get("INPUTS_TEST_GATE_BASE")), "judge": got(env.get("INPUTS_JUDGE")),
            "plan": got(env.get("INPUTS_PLAN")), "plan_review": got(env.get("INPUTS_PLAN_REVIEW")),
            "gate_before_fix": boundary.value(env.get("INPUTS_BEFORE_FIX_ANSWER")),
            "deferred": boundary.items(env.get("INPUTS_DEFERRED"))}


def flat(received: dict) -> dict:
    out = {name: None if received.get(part) is None else received[part][key] for name, (part, key) in FLAT.items()}
    return {**out, "answer": received.get("gate_before_fix"), "deferred": received.get("deferred") or []}


def fix_in(env, place: Path, repo: Path, run_id: str) -> dict:
    carried = boundary.pointed(env.get("INPUTS_FIXTURE"))
    start_go, live, before_fix_go = (boundary.flag(env.get("INPUTS_START_GO")), received_live(env),
                                     boundary.flag(env.get("INPUTS_BEFORE_FIX_GO")))
    if carried is not None:
        received = json.loads(carried.read_text(encoding="utf-8"))
        return {**flat(received), "go": start_go, "received": received, "stop_reason": ""}
    judge_accept.require_ports(live["judge"])
    planfile.require_ports(live["plan"])
    received, go = live, before_fix_go
    if go:
        fixture.noted_capture(place, repo, run_id=run_id, carried=received)
    return {**flat(received), "go": go, "received": None, "stop_reason": ""}


def fallback(reason: str) -> dict:
    return {**{name: None for name in FLAT}, "answer": None, "deferred": [], "go": False, "received": None,
            "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: fix_in(os.environ, Path(os.environ["ARTIFACTS_DIR"]), Path.cwd(), os.environ["WORKFLOW_ID"]), fallback)
