# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""整合性と迂回の役の指示を prompts/consistency-bypass.md から組む。1 つ目の commit だけ、今の材料のファイルを place に書き、今の指示の
5 つの値（lang_line・reason・brief_file・review_md・repo_review_md）で組む。組めなければ node が落ち、出口が「役の返答を受けた記録が無い」で返す"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
import rolekit  # noqa: E402  （lib/）
from src import oldbrief, viewpoint  # noqa: E402
import prompt  # noqa: E402

place = ports.place()
view, values, _ = materialkit._intake_doc(place)
brief_file = place / "material-consistency-bypass-brief.md"
brief_file.write_text(oldbrief.brief(view, values), encoding="utf-8")
own, theirs = materialkit.review_md_paths(view.repo)
rejected = rolekit.rejected(place, viewpoint.NAME)
ports.returns(prompt.emit(viewpoint.NAME, {"lang_line": rolekit.lang_line({"lang": values.get("lang") or ""}),
                                           "reason": rejected[-1] if rejected else "", "brief_file": str(brief_file),
                                           "review_md": own, "repo_review_md": theirs}, {},
                          prompt.round_of(viewpoint.NAME)))
