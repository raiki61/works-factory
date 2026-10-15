# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""素材集めの役（with: の role）の材料を judge/material-<役>-brief.md に描く（lib/judge_accept.material_prep）。
輪の頭の節として、前の周の受け付けが拒んだ理由（with: の reason。boundary.prev_reason）と、役の文の頭に足す言語の 1 行
（始めの記録の lang から rolekit.pointed_lang_line）も返す（役の指示書が $<この節>.output.reason・lang_line で読む。E5）。
材料を描けなかった時も同じ reason・lang_line を返す
{brief_file, brief, review_md, repo_review_md, reason, lang_line}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
role = os.environ.get("INPUTS_ROLE", "")
review_md, repo_review_md = ja.review_md_paths(boundary.lib_root(), Path.cwd())
carried = {**boundary.prev_reason(), "lang_line": rolekit.pointed_lang_line(os.environ.get("INPUTS_START"), boundary.pointed)}
try:
    out = ja.material_prep(jdir, role, Path.cwd(), review_md, repo_review_md)
except Exception as e:  # noqa: BLE001  落ちずに理由を本文に書く（受け付けが返答を拒む）
    text = f"素材集めの役 {role} の材料を描けなかった（{type(e).__name__}: {e}）。material を not_run（この理由）で返せ。\n"
    out = {"brief_file": "", "brief": text, "review_md": review_md, "repo_review_md": repo_review_md}
boundary.returns({**{k: str(out[k]) for k in ("brief_file", "brief", "review_md", "repo_review_md")}, **carried})
