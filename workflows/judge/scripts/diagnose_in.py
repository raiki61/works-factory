# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返し diagnose-in（docs/design/judge-eyes.md の 1.3 の 10）: diagnose へ渡す飛ばされうる値を、include した block の返りからそろえる（素材の観点
10 本の material の配列と返らなかった観点の名・並行 PR の素材の札・世界の解の行・頭の深さの行と根拠・仕様の足した行）。判定の裏取りを回すかを、
line が引いた段ごとの表 verify_by_tier から head-depth の段（返らなければ標準）で選ぶ。前提の実測と目的の固定が通ったか（go）と、
両方の pointer も運ぶ（diagnose の when: と with: はこの返しだけを読む）。落ちない（落ちたら ok: false で diagnose を回さない）。

入力（with:）: <block>_out（include した block の返りまるごと。飛ばされた block は null。読む欄は下の名の並びで選ぶ）と spec_in（返し spec-in の返り）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

# include した block の返りのうち読む欄（src/feed.py の diagnose_values が読む物だけ）
MATERIAL = ("material",)
WORLD = ("rows",)
HEAD_DEPTH = ("tier", "rows", "why")
PREMISES = ("ok", "constraints")
PURPOSE = ("ok", "purpose")


def _plain(got):
    return None if got is None else dict(got)


def compute():
    from src import feed
    received = {
        "prior-decisions": _plain(ports.picked(os.environ.get("INPUTS_PRIOR_DECISIONS_OUT"), MATERIAL)),
        "purpose-review": _plain(ports.picked(os.environ.get("INPUTS_PURPOSE_REVIEW_OUT"), MATERIAL)),
        "local-review": _plain(ports.picked(os.environ.get("INPUTS_LOCAL_REVIEW_OUT"), MATERIAL)),
        "consistency-bypass": _plain(ports.picked(os.environ.get("INPUTS_CONSISTENCY_BYPASS_OUT"), MATERIAL)),
        "hygiene": _plain(ports.picked(os.environ.get("INPUTS_HYGIENE_OUT"), MATERIAL)),
        "external-standards": _plain(ports.picked(os.environ.get("INPUTS_EXTERNAL_STANDARDS_OUT"), MATERIAL)),
        "procedure-trace": _plain(ports.picked(os.environ.get("INPUTS_PROCEDURE_TRACE_OUT"), MATERIAL)),
        "test-double-fidelity": _plain(ports.picked(os.environ.get("INPUTS_TEST_DOUBLE_FIDELITY_OUT"), MATERIAL)),
        "main-path-observation": _plain(ports.picked(os.environ.get("INPUTS_MAIN_PATH_OBSERVATION_OUT"), MATERIAL)),
        "provenance": _plain(ports.picked(os.environ.get("INPUTS_PROVENANCE_OUT"), MATERIAL)),
        "parallel-pr": _plain(ports.picked(os.environ.get("INPUTS_PARALLEL_PR_OUT"), MATERIAL)),
        "world": _plain(ports.picked(os.environ.get("INPUTS_WORLD_OUT"), WORLD)),
        "head-depth": _plain(ports.picked(os.environ.get("INPUTS_HEAD_DEPTH_OUT"), HEAD_DEPTH)),
        "premises": _plain(ports.picked(os.environ.get("INPUTS_PREMISES_OUT"), PREMISES)),
        "purpose": _plain(ports.picked(os.environ.get("INPUTS_PURPOSE_OUT"), PURPOSE)),
        "spec-in": ports.parsed(os.environ.get("INPUTS_SPEC_IN")),   # 返し spec-in の返りまるごと（Archon が output_format で照らした値）
    }
    try:
        table = ports.json(os.environ.get("INPUTS_VERIFY_BY_TIER") or "{}", "verify-by-tier.schema.json")
    except ValueError as e:
        raise ValueError(f"入力 verify_by_tier が読めない（{e}）") from e
    return feed.diagnose_values(received, table)


def fallback(why: str) -> dict:
    return {"ok": False, "reason": f"判定へ渡す値をそろえられない（{why}）", "go": False, "purpose": None, "constraints": None, "materials": [], "missing": [], "pr_material": None,
            "world_rows": None, "row_asks": [], "depth_why": "", "spec_rows": None, "spec_origin": "", "tier": "標準", "verify": False, "reply_sources": None}


ports.run(compute, fallback)
