# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""外部標準照合の役の指示を prompts/external-standards.md から組む。1 つ目の commit だけ、今の指示と同じ字になるよう、材料のファイル
（src/oldbrief.py）を書き、今の指示の差し込み口 5 つ（lang_line・reason・brief_file・review_md・repo_review_md）に値を渡す。
組めなければ node が落ち、出口が「役の返答を受けた記録が無い」で返す"""
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
view, ported, _ = materialkit._intake_doc(place)
own, theirs = materialkit.review_md_paths(view.repo)
rejected = rolekit.rejected(place, viewpoint.NAME)
values = {"lang_line": rolekit.lang_line({"lang": ported.get("lang") or ""}), "reason": rejected[-1] if rejected else "",
          "brief_file": str(oldbrief.brief(view, ported, place)), "review_md": own, "repo_review_md": theirs}
ports.returns(prompt.emit(viewpoint.NAME, values, {}, prompt.round_of(viewpoint.NAME)))
