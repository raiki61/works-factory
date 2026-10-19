# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""ゲートの検算の役の指示を prompts/gate-efficacy.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、
出口が「役の返答を受けた記録が無い」で返す。
1 つ目の commit だけ: 今の材料のファイル（src/oldbrief.py）も place に同じ字で書き、md（今の指示と同じ字）の 3 つの値
lang_line・reason・brief_file を渡す"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
import rolekit  # noqa: E402
from src import oldbrief, viewpoint  # noqa: E402
import prompt  # noqa: E402

place = ports.place()
shared, _ = materialkit.prompt_inputs(viewpoint, place, prompt.lang)   # 共通の値（rejection）と、値が組めるかの確かめ
doc = json.loads((place / materialkit.INTAKE).read_text(encoding="utf-8"))
view = materialkit.View.from_dict(doc["view"]["repo"], doc["view"])
brief = place / oldbrief.BRIEF_FILE
brief.write_text(oldbrief.brief(view, doc["values"]), encoding="utf-8")
values = {"lang_line": rolekit.lang_line({"lang": doc["values"].get("lang") or ""}), "reason": shared["rejection"],
          "brief_file": str(brief)}
ports.returns(prompt.emit(viewpoint.NAME, values, {}, prompt.round_of(viewpoint.NAME)))
