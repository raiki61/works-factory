"""素材集めの役（with: の role）の材料を judge/material-<役>-brief.md に描く（lib/judge_accept.material_prep）。
{brief_file, brief, review_md, repo_review_md}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
role = os.environ.get("INPUTS_ROLE", "")
review_md, repo_review_md = ja.review_md_paths(boundary.lib_root(), Path.cwd())
try:
    out = ja.material_prep(jdir, role, Path.cwd(), review_md, repo_review_md)
except Exception as e:  # noqa: BLE001  落ちずに理由を本文に書く（受け付けが返答を拒む）
    text = f"素材集めの役 {role} の材料を描けなかった（{type(e).__name__}: {e}）。material を not_run（この理由）で返せ。\n"
    out = {"brief_file": "", "brief": text, "review_md": review_md, "repo_review_md": repo_review_md}
boundary.returns({k: str(out[k]) for k in ("brief_file", "brief", "review_md", "repo_review_md")})
