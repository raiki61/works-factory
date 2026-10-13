"""埋め P6: 親の run の script が、子の run（`workflow:` のノードが起こした run）の出力のポインタを読む（docs/polyfills.md）。

境の口の boundary.resolve は自分の run のポインタしか読まない。止めた Archon にも、ほかの run のポインタを run の中から読む口が無い
（packages/workflows/src/artifact-pointer.ts の「a future in-workflow resolver」）。run の置き場は <artifactsRoot>/runs/<run の id>
（packages/paths/src/archon-paths.ts の getRunArtifactsDirForRoot）で、子と親は同じ runs/ の下に兄弟で並ぶので、自分の置き場の隣から
子の置き場を引く。子が出した札は子の run が自分の置き場に照らした物だが、symlink を辿った先は誰も照らしていない（同じファイルの
「real-path resolution at read time is not yet implemented」）ので、ここで辿った先が子の置き場の中かを照らす。
"""
import os
import re
from pathlib import Path

import boundary

RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def resolve(ptr) -> Path:
    """子の run の札 {type, run_id, path} の先の、子の置き場の中のパス（symlink を辿った後）。形が違う・置き場の外へ出る物は ValueError"""
    if not isinstance(ptr, dict) or ptr.get("type") != boundary.POINTER_TYPE:
        raise ValueError(f"{boundary.POINTER_TYPE} のポインタでない: {ptr!r}")
    run_id, rel = ptr.get("run_id"), ptr.get("path")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError(f"子の run の id の形でない: {run_id!r}")
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or "\0" in rel:
        raise ValueError(f"ポインタのパスは子の run の置き場からの相対: {rel!r}")
    home = (Path(os.environ["ARTIFACTS_DIR"]).resolve().parent / run_id).resolve()
    target = (home / rel).resolve()
    try:
        target.relative_to(home)
    except ValueError:
        raise ValueError(f"ポインタの先 {target} が子の run の置き場 {home} の外") from None
    return target
