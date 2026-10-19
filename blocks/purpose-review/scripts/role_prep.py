# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目的の監査の役の指示を prompts/purpose-review.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、
出口が「役の返答を受けた記録が無い」で返す。【1 つ目の commit だけ】今の指示の 3 つの値（lang_line・reason・brief_file）を入れ、
今の材料のファイルも書く"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
from src import oldbrief, viewpoint  # noqa: E402
import prompt  # noqa: E402

place = ports.place()
view, port_values, _ = materialkit._intake_doc(place)
own, _ = materialkit.prompt_inputs(viewpoint, place, prompt.lang)
(place / oldbrief.BRIEF_FILE).write_text(oldbrief.brief(view, port_values), encoding="utf-8")
values = {"lang_line": own["lang"], "reason": own["rejection"], "brief_file": str(place / oldbrief.BRIEF_FILE)}
ports.returns(prompt.emit(viewpoint.NAME, values, {}, prompt.round_of(viewpoint.NAME)))
