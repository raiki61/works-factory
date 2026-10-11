"""判定役の材料を組む（lib/judge_accept.diagnose_prep）。対象差分 judge/diff.patch・素材の 15 欄 judge/materials.json・
材料 judge/diagnose-brief.md を書く。再審の道・止めの控えが在れば組まない。素材の役が諦めていれば、残りで組んだ上で止める。
{go, brief_file, review_md, repo_review_md, reason}"""
import json
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
review_md, repo_review_md = ja.review_md_paths(boundary.lib_root(), Path.cwd())
out = {"go": False, "brief_file": "", "review_md": review_md, "repo_review_md": repo_review_md, "reason": ""}
try:
    start = ja.read_json(jdir / ja.START_FILE) or ja.start_view({})
    objection = os.environ.get("INPUTS_OBJECTION", "")
    raw = os.environ.get("INPUTS_PRIOR_FAILURES", "") or "null"
    ptr = json.loads(raw) if raw.strip() not in ("", "null") else None
    path = boundary.resolve(ptr) if isinstance(ptr, dict) else None
    prior = [] if objection.strip() else ja.prior_rows(path, Path.cwd(), start)
    out = ja.diagnose_prep(jdir, Path.cwd(), start, objection, prior, review_md, repo_review_md)
except Exception as e:  # noqa: BLE001  落ちずに go 偽と理由を返す
    out = {**out, "go": False, "reason": f"判定役の材料を組めない（{type(e).__name__}: {e}）"}
boundary.returns({"go": bool(out["go"]), **{k: str(out[k]) for k in ("brief_file", "review_md", "repo_review_md", "reason")}})
