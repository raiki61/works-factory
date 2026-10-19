# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""代役の忠実性の役の指示を prompts/test-double-fidelity.md から組む（指示の比べの 1 つ目の commit: 今の指示と同じ日本語の md と、今と
同じ字の材料のファイル material-test-double-fidelity-brief.md）。組めなければ node が落ち、出口が「役の返答を受けた記録が無い」で返す"""
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
view, values, _ = materialkit._intake_doc(place)
path = place / oldbrief.BRIEF_FILE
path.write_text(oldbrief.brief(view), encoding="utf-8")
rejected = rolekit.rejected(place, viewpoint.NAME)
ports.returns(prompt.emit(viewpoint.NAME, {"lang_line": rolekit.lang_line({"lang": values.get("lang") or ""}),
                                           "reason": rejected[-1] if rejected else "", "brief_file": str(path)},
                          {}, rolekit.attempt(place, viewpoint.NAME)))
