"""works の範囲の宣言（`.works-checks.json`）の読み手と、範囲の外で回さなかった段の決め方と字。

今の works（版 2aa7c66cf7abe1fe09699ac2942d107123214168）の `works/.shared/core/board.py`:450-504 の SCOPE_DECL・read_scope・
skipped_steps・scope_word・skipped_text を、元の名のまま字のとおり写した物。どれも盤面に届かない。read_scope が読む
declared.DECL_NAME は lib/graphloops/engine/declared.py から読む。request_files は依頼の where が名指すパスの読み
（元 `works/.shared/core/graphloops/rules/review-loop.py`:2293 `_pr_files` の差分が空の周の分）。
"""
import json
import os
import pathlib
import re
import subprocess
import sys

_GL = pathlib.Path(__file__).resolve().parent / "graphloops"
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

from engine import declared  # noqa: E402

# works の範囲の宣言: 対象のルートのこのファイル {段の名: {"paths_ignore": [ルートからのファイルかフォルダのパス, …]}} が、対象の宣言
# （declared.DECL_NAME。graphloops の engine と共有する）の段ごとに、段が見ない所を足す。対象の宣言には触らない（works は元の
# graphloops の読み手を変えない）。CI の paths-ignore と同じ考えで、glob でなくパスの頭が一致する物をその下と読む
SCOPE_DECL = ".works-checks.json"


def read_scope(root, steps: list) -> tuple:
    """対象のルートの範囲の宣言を読む ——（{段の名: paths_ignore}, 誤り）。無ければ（{}, None）。書式の誤り・steps（対象の宣言の段）に
    無い名は（None, 宣言の名を名指した理由）——黙って効かない宣言にしない"""
    path = pathlib.Path(root) / SCOPE_DECL
    if not path.is_file():
        return {}, None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, f"範囲の宣言 {SCOPE_DECL} が読めない（{type(e).__name__}: {e}）"

    def rel(x):
        q = pathlib.PurePosixPath(x) if isinstance(x, str) and x else None
        return q is not None and not q.is_absolute() and ".." not in q.parts and str(q) != "."
    if not isinstance(d, dict) or not all(isinstance(v, dict) and set(v) == {"paths_ignore"} and isinstance(v["paths_ignore"], list)
                                          and v["paths_ignore"] and all(rel(x) for x in v["paths_ignore"]) for v in d.values()):
        return None, (f"範囲の宣言 {SCOPE_DECL} は {{段の名: {{\"paths_ignore\": [ルートからの相対パス, …]}}}} だけ"
                      "（空・絶対・.. を含む・ルートの丸ごとのパスは読まない）")
    unknown = sorted(set(d) - {s["name"] for s in steps})
    if unknown:
        return None, (f"範囲の宣言 {SCOPE_DECL} の段 {unknown} が対象の宣言 {declared.DECL_NAME} の段"
                      f"（{[s['name'] for s in steps]}）に無い")
    return {k: list(v["paths_ignore"]) for k, v in d.items()}, None


def skipped_steps(steps: list, ignores: dict, changed) -> list:
    """宣言の段のうち、変更が全部その段の paths_ignore（ignores[段の名]。段が見ない所）の下に在る段 ——[{name, paths_ignore}]。
    changed は変更のパス（ルートから）を返す口で、範囲を持つ段が在る時だけ呼ぶ。口が無い・None か空を返した（変更を測れない）
    なら []——測れない時は絞らない（多く走らせる側は赤を見逃さない）。全段が外れる時も []——1 段も回さない緑（何も確かめて
    いない clean）を作らない"""
    scoped = [s["name"] for s in steps if ignores.get(s["name"])]
    files = changed() if scoped and changed else None
    if not files:
        return []

    def under(f, ignore):
        return any(f == p or f.startswith(p + "/") for p in (str(pathlib.PurePosixPath(x)) for x in ignore))
    out = [{"name": n, "paths_ignore": list(ignores[n])} for n in scoped if all(under(f, ignores[n]) for f in files)]
    return out if len(out) < len(steps) else []


def scope_word(s: dict) -> str:
    """範囲の外で回さなかった段 {name, paths_ignore} の名と範囲（素材の文と最後のテストの報告の行が同じ字で出す）"""
    return f"{s['name']}（変更が全部 {'・'.join(s['paths_ignore'])} の下で、段が見ない所）"


def skipped_text(skipped: list) -> str:
    """範囲の外で回さなかった段の一覧の句（素材の文と修正前のテストの行が同じ字で出す）"""
    return "範囲の外で回さなかった段: " + "・".join(scope_word(s) for s in skipped)


def request_files(root, wheres) -> list:
    """依頼の where（文字列の並び）のどれかに名として現れる（前後が名の字でない）、追跡中のパス（ルートから・名前の順）。判定から入る run は差分が
    空なので、範囲と照らす変更を依頼の where で決める。git が読めなければ []（足さない）
    （元 works/.shared/core/graphloops/rules/review-loop.py:2293 `_pr_files` の、差分が空の周の分）"""
    wheres = [w for w in wheres or () if isinstance(w, str)]
    if not wheres:
        return []
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=str(root), capture_output=True, stdin=subprocess.DEVNULL)
    except OSError:
        return []
    if out.returncode != 0:
        return []
    tracked = [os.fsdecode(t) for t in out.stdout.split(b"\0") if t]
    text = "\n".join(wheres)
    return sorted({t for t in tracked if t in text and re.search(r"(?<![A-Za-z0-9_.\-/])" + re.escape(t) + r"(?![A-Za-z0-9_\-])", text)})
