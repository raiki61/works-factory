"""根からの相対のパスの glob の読み（修正案の範囲の欄 allowed_paths・out_of_scope と、守りのファイルの一覧の型が同じ読みを引く）。

読み: * ? [..] は / を跨がない（[! は否定）・** は段をまたぐ（区切りの 1 つ丸ごとの時だけ）・末尾 / はその下の全部（'/**' と同じ）。
末尾 / の読みは _dir_glob の 1 か所に置き、3 つの口が引く。

- climbs(norm): 整えたパスが根の外へ上るか（`..` は段で見る。planmarks・consult・conflict.parse_limit も同じ物を使う）
- glob_problem(glob): 範囲の欄の glob の誤りの文（\\ の区切り・根の外・整えない綴り・`**`・`**/?*` のような字の無い丸ごとの許し）
- glob_match(path, glob): 根からの相対のパスが glob に当たるか（修正案の範囲の欄と protect.match の当て方の正本）
- globs_meet(a, b): 2 つの glob が同じパスに当たり得るか（言い切れない時は真。fix の組分けが範囲の交わる項目をつなぐ）

既製の glob の部品（pathspec・wcmatch）に置き換えない: どの部品も 2 つの glob の交わり（globs_meet）と丸ごとの許しの見分け
（glob_problem）を持たず、当て方（glob_match）だけを替えると、その 2 つが引く自前の読みと読みが 2 つに割れる。
標準の glob.translate は下限の版（pyproject.toml の requires-python >=3.12）に無い（3.13 から）。今は守りのファイルの照らしも
外のパッケージを入れない script のノード（PEP 723 の dependencies = []）で走る。
標準ライブラリだけ（lib のほかの物を import しない）。
"""
from __future__ import annotations

import posixpath
import re


def climbs(norm: str) -> bool:
    """整えたパスが根そのもの・絶対パス・`..` の段で上る物か（`..` は段で見る。`..foo/x.py` は根の中のディレクトリ `..foo` の物）"""
    return norm.startswith("/") or norm == "." or norm.split("/", 1)[0] == ".."


def _dir_glob(glob: str) -> tuple[str, tuple]:
    """範囲の glob の読みの 1 か所（glob_problem・glob_match・globs_meet が引く）: (当て方の glob, 交わりの段)。末尾 / は、その / を
    1 つだけ外した本体の下の全部と読む: 当て方は '本体/**'、交わりの段は本体の段に ('*', '**') を足して 1 段以上下と読む（段の比べの
    '**' は 0 段にも当たるので、'**' だけを足すと globs_meet('a/', 'a') が真になり、偽の glob_match('a', 'a/') と割れる）"""
    if glob.endswith("/"):
        body = glob[:-1]
        return body + "/**", tuple(body.split("/")) + ("*", "**")
    return glob, tuple(glob.split("/"))


def glob_problem(glob: str) -> str | None:
    """範囲の欄の glob（allowed_paths の行・out_of_scope の glob）の誤りの文。無ければ None。前後の空白・\\ の区切り・絶対パス
    （/・ドライブ文字・~ で始まる）・`..` の段で根の外へ上る・整えた形でない綴り（./x・a/../b・a//b）・字の無い glob（* と ? と
    [..] と / と . だけ。**・*・**/*・**/?*・[a-z]*・**/*.* のような丸ごとの許し。全部のファイルに当たり得る）を拒む。整えずに拒む（差分のパスは整えた綴りなので、整えない綴りの glob は当たらない）。
    末尾 / はその下の全部（'/**' と同じ）と読み（_dir_glob の 1 か所から引く）、'lib//' のような整えない綴りは拒む。
    ファイルの有無は見ない（新しく置くファイルも書く）"""
    if glob != glob.strip():
        return "前後に空白が在る（空白を外した、作業ツリーの根からの相対の glob にせよ）"
    if "\\" in glob:
        return "\\ が在る（区切りは / で書け。glob は作業ツリーの根からの相対）"
    if glob.startswith(("/", "~")) or re.match(r"[A-Za-z]:", glob):
        return "絶対パス（/・ドライブ文字・~ で始まる。作業ツリーの根からの相対の glob にせよ）"
    read = _dir_glob(glob)[0]
    norm = posixpath.normpath(read)
    if climbs(norm):
        return "根の外か根そのものを指す（`..` の段で上らない、根からの相対の glob にせよ）"
    if not any(_literal(seg) for seg in norm.split("/")):
        return "丸ごとの許し（字が無く * と ? と [..] と . だけの glob）は拒む。項目の直しが触るファイルかディレクトリまで狭めよ"
    if norm != read:
        return f"整えた形でない（./・..・// を含む）。整えた形 {norm} で書け"
    return None


def _literal(seg: str) -> bool:
    """glob の 1 区切りに、* と ? と [..]（_segment と同じ読み）と . の外の字が在るか"""
    i = 0
    while i < len(seg):
        c = seg[i]
        if c == "[":
            j = i + 1 + (seg[i + 1:i + 2] == "!")
            j += seg[j:j + 1] == "]"
            k = seg.find("]", j)
            if k > 0:
                i = k + 1
                continue
        if c not in "*?.":   # . だけの字（*.*・**/.*）は拡張子を持つ全部・隠しの全部に当たる
            return True
        i += 1
    return False


def _segment(seg: str) -> str:
    """glob の 1 区切りを正規表現に（* と ? と [..] は / を跨がない。[! は否定）"""
    out, i = [], 0
    while i < len(seg):
        c = seg[i]
        k = -1
        if c == "[":
            j = i + 1 + (seg[i + 1:i + 2] == "!")
            j += seg[j:j + 1] == "]"
            k = seg.find("]", j)
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif k > 0:
            body = seg[i + 1:k]
            out.append("[" + ("^" + body[1:] if body.startswith("!") else body).replace("\\", "\\\\").replace("[", "\\[") + "]")
            i = k
        else:
            out.append(re.escape(c))
        i += 1
    return "".join(out)


def _glob_regex(glob: str):
    parts = glob.split("/")
    out = []
    for i, seg in enumerate(parts):
        last = i == len(parts) - 1
        if seg == "**":
            out.append(".*" if last else "(?:[^/]+/)*")
        else:
            out.append(_segment(seg) + ("" if last else "/"))
    return re.compile("".join(out) + r"\Z")


def glob_match(path: str, glob: str) -> bool:
    """根からの相対のパスが glob に当たるか（* ? [..] は / を跨がない・** は段をまたぐ。末尾 / はその下の全部で '/**' と同じ。
    読みは _dir_glob の 1 か所から引く）。範囲の欄と守りのファイルの当て方の正本"""
    return _glob_regex(_dir_glob(glob)[0]).match(path) is not None


_WILD = re.compile(r"[*?\[]")


def globs_meet(a: str, b: str) -> bool:
    """2 つの glob（glob_match の読み）が同じパスに当たり得るか。言い切れない時は真（交わらないと言える時だけ偽）。末尾 / の読みは
    _dir_glob の 1 か所から引く（'a/' は 'a/x'・'a/**' と交わり、'a' とは交わらない）"""
    if isinstance(a, str) and isinstance(b, str):
        return _parts_meet(_dir_glob(a)[1], _dir_glob(b)[1])
    return True


def _parts_meet(a: tuple, b: tuple) -> bool:
    if not a or not b:
        return all(s == "**" for s in a + b)
    if a[0] == "**":
        return _parts_meet(a[1:], b) or _parts_meet(a, b[1:])
    if b[0] == "**":
        return _parts_meet(a, b[1:]) or _parts_meet(a[1:], b)
    return _segments_meet(a[0], b[0]) and _parts_meet(a[1:], b[1:])


def _segments_meet(x: str, y: str) -> bool:
    """glob の 1 区切りどうし。両方が wildcard を持つ時は頭と尻の字だけで見る（言い切れない所は真）"""
    wx, wy = _WILD.search(x), _WILD.search(y)
    if not wx and not wy:
        return x == y
    if not wx:
        return re.fullmatch(_segment(y), x) is not None
    if not wy:
        return re.fullmatch(_segment(x), y) is not None
    hx, hy = x[:wx.start()], y[:wy.start()]
    tx, ty = (re.split(r"[*?\[\]]", s)[-1] for s in (x, y))
    return (hx.startswith(hy) or hy.startswith(hx)) and (tx.endswith(ty) or ty.endswith(tx))
