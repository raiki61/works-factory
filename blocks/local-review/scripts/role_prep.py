# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""局所レビューの役の指示を prompts/local-review.md から組む（1 つ目の commit だけ: 今の指示と同じ 5 つの値を入れ、材料のファイルも
今と同じ字で書く）。組めなければ node が落ち、出口が「役の返答を受けた記録が無い」で返す"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
import rolekit  # noqa: E402
from src import lenses, oldbrief, viewpoint  # noqa: E402
import prompt  # noqa: E402

place = ports.place()
view, port_values, _ = materialkit._intake_doc(place)
own, theirs = materialkit.review_md_paths(view.repo)
brief_file = place / "material-local-review-brief.md"
brief_file.write_text(oldbrief.brief(view, own, theirs, lenses.skills()), encoding="utf-8")
rejected = rolekit.rejected(place, viewpoint.NAME)
values = {"lang_line": rolekit.lang_line({"lang": port_values.get("lang") or ""}), "reason": str(rejected[-1]) if rejected else "",
          "brief_file": str(brief_file), "review_md": own, "repo_review_md": theirs}
ports.returns(prompt.emit(viewpoint.NAME, values, {}, prompt.round_of(viewpoint.NAME)))
