# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""衛生の役の指示を prompts/hygiene.md から組む（前の回までの却下は place の控えから全部）。組めなければ node が落ち、
出口が「役の返答を受けた記録が無い」で返す。1 つ目の commit だけ、今の材料のファイルも place に書く（指示の比べ）"""
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
own, theirs = materialkit.review_md_paths(view.repo)
rejected = rolekit.rejected(place, viewpoint.NAME)
(place / oldbrief.BRIEF_FILE).write_text(oldbrief.brief(view, values), encoding="utf-8")
ports.returns(prompt.emit(viewpoint.NAME,
                          {"lang_line": rolekit.lang_line({"lang": values.get("lang") or ""}),
                           "reason": rejected[-1] if rejected else "", "review_md": own, "repo_review_md": theirs,
                           "brief": (place / oldbrief.BRIEF_FILE).read_text(encoding="utf-8")},
                          {}, prompt.round_of(viewpoint.NAME)))
