# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返し diagnose-in（docs/design/judge-eyes.md の 1.3 の 10）: diagnose へ渡す飛ばされうる値を、受け皿の got からそろえる（素材の観点 10 本の
material の配列と返らなかった観点の名・並行 PR の素材の札・世界の解の行・頭の深さの行と根拠・仕様の足した行）。判定の裏取りを回すかを、
line が引いた段ごとの表 verify_by_tier から head-depth の段（返らなければ標準）で選ぶ。前提の実測と目的の固定が通ったか（go）と、
両方の pointer も運ぶ（diagnose の when: と with: はこの返しだけを読む）。落ちない（落ちたら ok: false で diagnose を回さない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def _got(raw):
    raw = ports.text(raw).strip()
    whole = None if raw in ("", "null") else ports.json(raw)
    return whole.get("got") if isinstance(whole, dict) else None


def _value(raw):
    raw = ports.text(raw).strip()
    return None if raw in ("", "null") else ports.json(raw)


def compute():
    from src import feed
    received = {
        "prior-decisions": _got(os.environ.get("INPUTS_PRIOR_DECISIONS_OUT")),
        "purpose-review": _got(os.environ.get("INPUTS_PURPOSE_REVIEW_OUT")),
        "local-review": _got(os.environ.get("INPUTS_LOCAL_REVIEW_OUT")),
        "consistency-bypass": _got(os.environ.get("INPUTS_CONSISTENCY_BYPASS_OUT")),
        "hygiene": _got(os.environ.get("INPUTS_HYGIENE_OUT")),
        "external-standards": _got(os.environ.get("INPUTS_EXTERNAL_STANDARDS_OUT")),
        "procedure-trace": _got(os.environ.get("INPUTS_PROCEDURE_TRACE_OUT")),
        "test-double-fidelity": _got(os.environ.get("INPUTS_TEST_DOUBLE_FIDELITY_OUT")),
        "main-path-observation": _got(os.environ.get("INPUTS_MAIN_PATH_OBSERVATION_OUT")),
        "provenance": _got(os.environ.get("INPUTS_PROVENANCE_OUT")),
        "parallel-pr": _got(os.environ.get("INPUTS_PARALLEL_PR_OUT")),
        "world": _got(os.environ.get("INPUTS_WORLD_OUT")),
        "head-depth": _got(os.environ.get("INPUTS_HEAD_DEPTH_OUT")),
        "premises": _got(os.environ.get("INPUTS_PREMISES_OUT")),
        "purpose": _got(os.environ.get("INPUTS_PURPOSE_OUT")),
        "spec-in": _value(os.environ.get("INPUTS_SPEC_IN")),
    }
    return feed.diagnose_values(received, ports.json(os.environ.get("INPUTS_VERIFY_BY_TIER") or "{}", "verify-by-tier.schema.json"))


def fallback(why: str) -> dict:
    return {"ok": False, "reason": f"判定へ渡す値をそろえられない（{why}）", "go": False, "purpose": None, "constraints": None, "materials": [], "missing": [], "pr_material": None,
            "world_rows": "", "row_asks": [], "depth_why": "", "spec_rows": "", "spec_origin": "", "tier": "標準", "verify": False}


ports.run(compute, fallback)
