"""考えの住処の柵の道具（run の中の構造のブロックが対象の表に当てる）。

表 docs/concepts.json（地図 docs/concepts.md の隣）が、住処の在る考えごとに柵を持つ: 語の形（pattern。正規表現）・
知ってよい所（allowed。fnmatch の形で `*` は `/` もまたぐ）・既知の漏れ（known。"<表の持ち主のフォルダからのパス>" → [行の数, 理由]）・
結んだ写し（bound。任意。[{paths, lines, by, why}]: paths のファイルで lines（正規表現）に当たる行は、源の値を試験 by が縛る写しなので
数えない。流れの道具が値を決まった置き場からしか読まないなど、写しが消せない時の形。どの行が写しかは by の試験が表の行を読んで縛る）。
表の exclude（文書・写し・生成物・試験の材料）と allowed の外の追跡されたファイルで、pattern に当たる行を「ファイル →
行の数」で数える。

対象のリポジトリでは、表は追跡されたファイルの中の決まった名（concepthome.TABLE_NAME。根か、どのフォルダの下でも）で探し、
表の中のパスはその docs/ の親のフォルダ（持ち主のフォルダ）からの相対で読む。表が無い対象では何も数えない（作らない）。

- tracked(root)・hit(path, globs)
- count_lines(text, fence, path) -> int: 1 つのファイルの柵の語の行の数（結んだ写しの行を除く。places・scan_change が使う）
- check_table(doc): 表の形の確かめ（concepts の表・pattern と bound の lines が正規表現・allowed と bound の paths が配列。外れは ValueError か re.error）
- tables(repo, rev=None) -> ([(持ち主のフォルダ, 表)], [読めない表の訳]): 対象の表を探して読む（投げない）。rev を渡せば
  その版の木の表を読む（直しが表を広げても、直しの前の表で数える）
- changed(repo, base_rev, *, skip_prefix) -> [パス]: base_rev と今の作業ツリーで変わった・足したファイル（実行基盤の写しの置き場 skip_prefix の下と入れ子のリポジトリは除く。skip_prefix が空なら ValueError）
- places(repo, base, table, paths) -> [{concept, what, path, lines, home, known_places}]: 単位のファイル（repo からの相対）に
  当たる柵ごとの行の数・住処（allowed）か・その考えを知る場所の数（持ち主のフォルダの中で exclude の外の全部。住処を含む）
- scan_change(repo, base_rev, table, base="", *, skip_prefix) -> [{concept, what, path, before, after}]: base_rev と今の作業ツリーの間で変わった
  ファイル（持ち主のフォルダの中だけ）を各柵で数え、住処の外で行の数が増えた物（path は repo からの相対）

標準ライブラリと concepthome（探し方）だけを使う。
"""
from __future__ import annotations

import fnmatch
import json
import pathlib
import re
import subprocess

import concepthome


def tracked(root):
    """root からのパスの一覧: 追跡された物と、まだ追跡されていない .gitignore に当たらない物（足したファイルを commit の前から数える）"""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return list(dict.fromkeys(f for f in out.split("\0") if f))


def hit(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _bound(fence, path: str) -> list:
    """path に当たる結んだ写しの行の形（正規表現）の並び"""
    return [re.compile(b["lines"]) for b in fence.get("bound") or [] if hit(path, b["paths"])]


def count_lines(text: str, fence, path: str) -> int:
    pat, copies = re.compile(fence["pattern"]), _bound(fence, path)
    return sum(1 for line in text.splitlines() if pat.search(line) and not any(c.search(line) for c in copies))


def _text(path: pathlib.Path) -> str | None:
    """テキストの中身（読めない・テキストでない物は None）"""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    return None if "\0" in text else text


# ---------------------------------------------------------------- 対象のリポジトリに当てる口
def _show(repo, rev: str, name: str) -> bytes | None:
    p = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{name}"], capture_output=True, stdin=subprocess.DEVNULL)
    return p.stdout if p.returncode == 0 else None


def _rev_names(repo, rev: str) -> tuple[list[str], str]:
    p = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only", rev], capture_output=True,
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        return [], p.stderr.decode("utf-8", "replace").strip()[-300:] or f"git ls-tree が終了コード {p.returncode}"
    return [n for n in p.stdout.decode("utf-8", "surrogateescape").split("\0") if n], ""


def tables(repo, rev: str | None = None) -> tuple[list[tuple[str, dict]], list[str]]:
    """([(持ち主のフォルダ, 表)], [読めない表の訳])。表は追跡されたファイル（rev なら その版の木）の中の concepthome.TABLE_NAME
    （浅い順）。投げない"""
    names, why = _rev_names(repo, rev) if rev else concepthome.tracked_names(pathlib.Path(repo))
    out, bad = [], [f"木を読めなかった: {why}"] if why else []
    for name in concepthome.pick_tables(names):
        try:
            raw = _show(repo, rev, name) if rev else (pathlib.Path(repo) / name).read_bytes()
            if raw is None:
                raise OSError(f"{rev} に読めない")
            doc = json.loads(raw.decode("utf-8"))
            check_table(doc)
        except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError, AttributeError, re.error) as e:
            bad.append(f"{name}: {e}")
            continue
        out.append((concepthome.base_of(name), doc))
    return out, bad


def check_table(doc) -> None:
    if not isinstance(doc, dict) or not isinstance(doc.get("concepts"), dict):
        raise ValueError("concepts の表が無い")
    for k, v in doc["concepts"].items():
        for f in v.get("fences") or []:
            re.compile(f["pattern"])
            if not isinstance(f.get("allowed"), list):
                raise ValueError(f"{k} の allowed が配列でない")
            bound = f.get("bound", [])
            if not isinstance(bound, list):
                raise ValueError(f"{k} の bound が配列でない")
            for b in bound:
                if not (isinstance(b, dict) and isinstance(b.get("paths"), list) and isinstance(b.get("lines"), str)
                        and isinstance(b.get("by"), str) and b["by"]):
                    raise ValueError(f"{k} の bound の行が {{paths: [...], lines: <正規表現>, by: <縛る試験>}} の形でない")
                re.compile(b["lines"])


def _within(path: str, base: str) -> str | None:
    """repo からの相対のパスを、持ち主のフォルダ base からの相対に（外なら None）"""
    if not base:
        return path
    return path[len(base) + 1:] if path.startswith(base + "/") else None


def _fences(table: dict):
    for k, v in (table.get("concepts") or {}).items():
        for f in v.get("fences") or []:
            yield k, f


def places(repo, base: str, table: dict, paths) -> list[dict]:
    """単位のファイル（repo からの相対）に当たる柵ごとの {concept, what, path, lines, home, known_places}。表の exclude に当たる・
    持ち主のフォルダの外・読めないファイルは見ない。known_places は持ち主のフォルダの中で exclude の外の、その柵の語の在るファイルの数"""
    root = pathlib.Path(repo) / base if base else pathlib.Path(repo)
    exclude = table.get("exclude") or []
    rel = [(p, _within(p, base)) for p in paths]
    rel = [(p, r) for p, r in rel if r is not None and not hit(r, exclude)]
    if not rel:
        return []
    every = None
    out = []
    for k, f in _fences(table):
        hits = []
        for p, r in rel:
            text = _text(root / r)
            n = count_lines(text, f, r) if text is not None else 0
            if n:
                hits.append((p, r, n))
        if not hits:
            continue
        if every is None:
            every = [x for x in tracked(root) if not hit(x, exclude)]
        total = sum(1 for x in every if (t := _text(root / x)) is not None and count_lines(t, f, x))
        out += [{"concept": k, "what": f["what"], "path": p, "lines": n, "home": hit(r, f["allowed"]),
                 "known_places": total} for p, r, n in hits]
    return out


def changed(repo, base_rev: str, *, skip_prefix: str) -> list[str]:
    """base_rev と今の作業ツリー（まだ追跡されていない物を含む）の間で変わった・足したファイル（repo からの相対）。流れの道具の
    写し（skip_prefix の下）と、入れ子のリポジトリ（ls-files が / で終わる名で出す）は除く。git が落ちれば CalledProcessError。
    skip_prefix が空なら ValueError（"" はどのパスの頭にも当たり、全部のファイルが黙って外れる）"""
    if not skip_prefix:
        raise ValueError("skip_prefix が空（全部のファイルが外れる）")

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True,
                              stdin=subprocess.DEVNULL).stdout.decode("utf-8", "surrogateescape")
    diff = git("diff", "--name-only", "-z", "--no-renames", base_rev, "--").split("\0")
    new = git("ls-files", "-z", "--others", "--exclude-standard").split("\0")
    return list(dict.fromkeys(f for f in diff + new if f and not f.endswith("/") and not f.startswith(skip_prefix)))


def _old(repo, rev: str, path: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"], capture_output=True, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        return ""   # 前の版に無いファイル
    try:
        text = p.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return ""
    return "" if "\0" in text else text


def scan_change(repo, base_rev: str, table: dict, base: str = "", *, skip_prefix: str) -> list[dict]:
    """[{concept, what, path, before, after}]: base_rev と今の作業ツリーで変わったファイルのうち、持ち主のフォルダ base の中で
    exclude と allowed の外の物を各柵で数え、行の数が増えた物（path は repo からの相対）。git が落ちれば CalledProcessError"""
    exclude = table.get("exclude") or []
    files = []
    for p in changed(repo, base_rev, skip_prefix=skip_prefix):
        r = _within(p, base)
        if r is not None and not hit(r, exclude):
            files.append((p, r))
    out = []
    olds, news = {}, {}
    for k, f in _fences(table):
        for p, r in files:
            if hit(r, f["allowed"]):
                continue
            if p not in news:
                news[p] = _text(pathlib.Path(repo) / p) or ""
                olds[p] = _old(repo, base_rev, p)
            after = count_lines(news[p], f, r)
            before = count_lines(olds[p], f, r)
            if after > before:
                out.append({"concept": k, "what": f["what"], "path": p, "before": before, "after": after})
    return out
