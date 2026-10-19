# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""出所検査の役の指示を prompts/provenance.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、
出口が「役の返答を受けた記録が無い」で返す"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
from src import viewpoint  # noqa: E402
import prompt  # noqa: E402
from src import oldbrief  # noqa: E402

BRIEF = "material-provenance-brief.md"   # 今の材料のファイルの名

doc = json.loads((ports.place() / materialkit.INTAKE).read_text(encoding="utf-8"))
view = materialkit.View.from_dict(doc["view"]["repo"], doc["view"])
values, _ = materialkit.prompt_inputs(viewpoint, ports.place(), prompt.lang)
brief = ports.place() / BRIEF
brief.write_text(oldbrief.brief(view, doc.get("values") or {}), encoding="utf-8")
# 今の指示の穴（lang_line・reason・brief_file）に値を入れる。1 つ目の commit だけ
ports.returns(prompt.emit(viewpoint.NAME, {"lang_line": values["lang"], "reason": values["rejection"], "brief_file": str(brief)}, {},
                          prompt.round_of(viewpoint.NAME)))
