# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""run の頭の深さの役の支度（lib/headdepth）。依頼の行（judge/request.json）と始めの記録から事実を測り、役を起こす前の機械の止めを
通す。先に標準の控え judge/depth-head.json を書き（止めに当たればその深さと訳）、材料を judge/depth-head-brief.md に置く。
落ちない: 中の誤りは全部捕まえ、標準の控えと go 偽と訳を返す（深さは判定を止めない）。{go, brief_file, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

out = {"go": False, "brief_file": "", "reason": ""}
try:
    sys.path.append(str(boundary.lib_root()))
    import headdepth
    import judge_accept as ja
    import startrec

    jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
    try:
        stop = ja.read_stop(jdir)
        start_file = boundary.pointed(os.environ.get("INPUTS_START"))
        start = startrec.load(start_file) if start_file else {}
        facts = headdepth.facts(ja.read_json(jdir / ja.REQUEST_FILE, []) or [], start, Path.cwd())
        go, depth, why = (False, headdepth.STANDARD, f"止まっている（{stop['stop_reason']}）") if stop else headdepth.gate(facts)
        headdepth.write(jdir, headdepth.record(depth or headdepth.STANDARD, why or headdepth.NO_REPLY, facts_doc=facts))
        brief = jdir / headdepth.BRIEF
        brief.write_text(headdepth.brief(facts), encoding="utf-8")
        out = {"go": go, "brief_file": str(brief) if go else "", "reason": why}
    except Exception as e:  # noqa: BLE001  深さの支度は判定を止めない
        why = f"run の頭の深さの支度が落ちた（{type(e).__name__}: {e}）"
        headdepth.write(jdir, headdepth.record(headdepth.STANDARD, why))
        out = {"go": False, "brief_file": "", "reason": why}
except Exception as e:  # noqa: BLE001  境の口か lib を読めない
    out = {"go": False, "brief_file": "", "reason": f"run の頭の深さの支度が lib を読めない（{type(e).__name__}: {e}）"}
boundary.returns(out)
