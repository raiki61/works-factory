"""差分を切る・審査役の材料を置く・審査が要るかを決める（docs/design/delta-review.md の 1.5。写す元は lib/refix.py の _cut_delta・cut と
lib/fixboard.py の delta_review_due・snapshot）。

- due(repo, base, reply): 1 回目の審査が要るか (要るか, 訳)
- cut(place, n, repo, rev): n 回目の差分（版 rev → 今の作業ツリーの姿。未追跡の新しいファイルも・Archon の写しの置き場の下は除く）を
  delta-<n>.patch に、{file, files, rev（固めた木）, base} を cut-<n>.json に書いて返す
- brief(...): 審査役が Read する材料を review-<n>-brief.json に書く
- freeze(place, n, repo): 読むだけの役を起こす前の作業ツリーの姿を review-<n>-tree.json に撮る
"""
import pathlib

import jsonfile  # lib/
import leftovers  # lib/
import lens  # lib/
import protect  # lib/
import unittrees  # lib/

import accept  # lib/

from src import files


def _spec() -> list:
    return unittrees.pathspec_without(files.SKIP)


def absorbed(reply) -> int:
    """修正役が plan_faces で absorbed（塞いだ）と答えた穴の数"""
    rows = (reply or {}).get("plan_faces") or []
    return sum(1 for r in rows if isinstance(r, dict) and r.get("handled") == "absorbed")


def due(repo, base: str, reply) -> tuple:
    """1 回目の審査を起こすか (起こすか, 訳)。base から今の作業ツリー（Archon の写しの置き場の下を除く）への差分が空でないか、
    修正役が塞いだと言う穴が在れば起こす（差分の無い申告を誰も検算しない形を作らない）。git が落ちれば leftovers.Unreadable"""
    if leftovers.git_names(repo, "diff", "--name-only", base, leftovers.snapshot(repo), "--", *_spec()):
        return True, f"修正の差分が在る（起点 {base[:12]}）"
    k = absorbed(reply)
    if k:
        return True, f"修正の差分は空だが、修正が塞いだと言う事前審査の穴が {k} 件在る（検算する）"
    return False, (f"差分が空で、塞いだと言われた穴も無いので差分の審査を起こさない（修正前の版 {base[:12]} から作業ツリーは"
                   "変わっていない。修正が塞いだと言う事前審査の穴は 0 件）")


def cut(place, n: int, repo, rev: str) -> dict:
    place = pathlib.Path(place)
    snap = leftovers.snapshot(repo)
    raw = leftovers.git(repo, "diff", rev, snap, "--", *_spec(), text=False)
    names = leftovers.git_names(repo, "diff", "--name-only", rev, snap, "--", *_spec())
    target = place / files.patch(n)
    target.write_bytes(raw)
    doc = {"file": str(target), "files": names, "rev": snap, "base": rev}
    jsonfile.write(place / files.cut(n), doc, indent=2)
    return doc


def read_cut(place, n: int) -> dict:
    doc = jsonfile.read_or(pathlib.Path(place) / files.cut(n))
    if not isinstance(doc, dict) or not doc.get("file"):
        raise ValueError(f"{n} 回目の差分の控え {files.cut(n)} が無いか読めない")
    return doc


def freeze(place, n: int, repo) -> None:
    jsonfile.write(pathlib.Path(place) / files.review_tree(n), accept.tree_state(pathlib.Path(repo)))


def brief(place, n: int, repo, declared_at: str, *, scope: dict, reply, plan_review, lens_error: str = "", handled=()) -> pathlib.Path:
    """n 回目の審査役の材料。declared_at は対象の守りの宣言を読む commit（空は自分の一覧だけ）。1 回目は修正の差分・事前審査の穴・修正役の答え・守りのファイル・レンズの行・範囲の欄・修正の報告、
    2 回目は手直しの差分・手直しの応答 handled・守りのファイル（手直しの差分にはレンズも範囲の欄も載せない）"""
    place = pathlib.Path(place)
    d = read_cut(place, n)
    doc = {"diff_file": d["file"], "files": d["files"], "rev": d["rev"], "base": d["base"]}
    if n == 1:
        doc["plan_review"] = plan_review
        doc["plan_faces"] = (reply or {}).get("plan_faces") or []
    else:
        doc["handled"] = list(handled)
    try:   # 変わったファイルのうち守りのファイル。審査役が検査を緩める変更を見る材料（最後の承認ノードにも必ず出る）
        doc["protected_files"] = protect.hits(d["files"], protect.merged(repo, declared_at) if declared_at else protect.load())
    except protect.Broken as error:
        doc["protected_files"], doc["protected_files_error"] = [], str(error)
    if n == 1:
        if lens_error:
            doc["lens"], doc["lens_error"] = [], lens_error
        else:
            try:
                doc["lens"] = lens.brief_rows(place)
            except ValueError as error:
                doc["lens"], doc["lens_error"] = [], str(error)
        doc.update(plan_items=scope["plan_items"], ruled_paths=scope["ruled_paths"], agreed=scope["agreed"])
        doc["fix_report"] = {k: (reply or {}).get(k) or [] for k in ("changes", "not_done")} if isinstance(reply, dict) else {}
    return jsonfile.write(place / files.review_brief(n), doc, indent=2)
