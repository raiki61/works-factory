"""承認された仕様を固める（今の lib/judge_accept.py の sha_file・sha_and_why・_file_sha・_spec_run・spec_freeze の写し。
docs/design/spec.md の 1.5）。受け入れ条件の run のコマンドを走らせて終了コードを取り、テストのファイルの sha256 とともに
spec.json に 1 度だけ書く。足した依頼の行（受け入れ条件 1 件が 1 行）は依頼の行のファイルに積まず added-rows.json に書く。
期限は置かない（持ち主の決め no-timeouts）。"""
from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

import tree_run   # lib/
from engine.util import READ_CAP, read_capped   # lib/graphloops/engine/util.py

from src import files

ORIGIN = files.ORIGIN
PROVENANCE = files.PROVENANCE


def sha_and_why(path) -> tuple:
    """ファイルの（sha256, ""）か、測れなければ（None, 訳）。役が指したパスは read_capped を通して開く"""
    data, why = read_capped(str(path), READ_CAP)
    return (None, why) if data is None else (hashlib.sha256(data).hexdigest(), "")


def file_sha(root, rel):
    p = pathlib.Path(root) / rel
    return sha_and_why(p)[0] if p.is_file() else None


def run_command(root, cmd) -> tuple:
    """受け入れ条件 1 件の run を今の作業ツリーで走らせた終了コード（走らなければ None と理由）。走らせるのは人が承認ノードで
    コマンドの字面を見て通した後だけ"""
    try:
        code = tree_run.run(["/bin/sh", "-c", cmd], cwd=str(root), env=tree_run.outside_env(os.environ),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        return None, f"{type(e).__name__}: {e}"
    return code, ""


def row_of(a: dict, requirement_text: str) -> dict:
    """受け入れ条件 1 件（exit_at_approval を持つ）の依頼の行。依頼の行として後の段へ渡る材料で、役の観察と同じく反証の対象"""
    code = a["exit_at_approval"]
    return {"where": f"{a['file']}: {a['name']}",
            "text": f"{PROVENANCE}受け入れ条件 {a['key']}（要件 {a['requirement']}）がまだ満たされていない——承認の時点で `{a['run']}` が "
                    + ("走らない" if code is None else
                       "既に exit 0（緑——赤を見ていないので、テストが要件を確かめているかを疑え）" if code == 0 else f"exit {code}"),
            "mechanism": f"Given/When/Then の本文は {a['file']} の {a['name']} が正本（記録に写さない）。要件: {requirement_text}",
            "measured": f"承認の時点（round 1）の実測: `{a['run']}` → " + (a.get("run_error") or "") + ("" if code is None else f"exit {code}"),
            "false_positive_if": f"`{a['run']}` が今の版で exit 0 で、{a['file']} が承認の後に変わっていない（sha256 {str(a['sha256'])[:12]}）なら誤り"}


def freeze(place, root, pend, approval) -> dict:
    """承認済みの仕様を spec.json（requirements・acceptance[{key, requirement, file, name, run, sha256, exit_at_approval, run_error?}]・
    out_of_scope・approval）に 1 度だけ固め、受け入れ条件を依頼の行として added-rows.json に書く。pend は承認ノードに見せた仕様
    （gate.approve の pending）、approval は答えの記録。spec.json は最後に書く（在れば固め終わっている）"""
    place = pathlib.Path(place)
    rows = []
    for a in pend["acceptance"]:
        code, err = run_command(root, a["run"])
        rows.append({**a, "exit_at_approval": code, **({"run_error": err} if err else {})})
    texts = {r["key"]: r["text"] for r in pend["requirements"]}
    added = [row_of(a, texts[a["requirement"]]) for a in rows]
    files.write(place / files.ADDED_ROWS, added)
    files.write(place / files.SPEC, {**pend, "acceptance": rows, "approval": approval})
    return {"ok": True, "problems": []}
