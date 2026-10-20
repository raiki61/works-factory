"""書いた意図（対象のリポジトリが文で書いた憲法・決まり・設計）を探して読む（docs/design/structure.md の 3 節）。

決まった名の文書 ARCHITECTURE.md・AGENTS.md（根と、単位のファイルの上の各フォルダ）か、port intent で渡された文書と、port policy の
方針の文書。読む版 rev の追跡されたファイルだけを git show で読む（直しが意図の文書を書き換えても、比べる基準は直す前の意図）。
"""
from __future__ import annotations

import pathlib
import subprocess

TEXT_CAP = 6000   # 文書 1 本の本文の字の上限。超えた分は切り、cut に切った字の数を残す
POLICY_REV = "policy"


def _git(root, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(f"git {args[0]} が終了コード {p.returncode}: {p.stderr.strip()[-300:]}")
    return p.stdout


def _doc(path: str, rev: str, text: str, reason: str = "") -> dict:
    return {"path": path, "rev": rev, "text": text[:TEXT_CAP], "cut": max(0, len(text) - TEXT_CAP), "reason": reason}


def _names() -> tuple:
    import design   # lib/。根の地図の文書の名の住処（重い import なので使う時だけ）
    return design.MAP_NAMES


def _folders(paths) -> list:
    """paths の各ファイルの上の各フォルダ（根を除く）。浅い順・名の順"""
    seen = set()
    for path in paths:
        parts = pathlib.PurePosixPath(path).parts[:-1]
        seen.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    return sorted(seen, key=lambda f: (f.count("/"), f))


def named(root, rev: str, paths) -> list:
    """決まった名で探した文書のパス（rev に追跡されている物だけ。根が先、次に浅いフォルダから）"""
    tracked = set(_git(root, "ls-tree", "-r", "--name-only", rev).splitlines())
    names = _names()
    return [p for folder in ["", *_folders(paths)] for name in names if (p := f"{folder}/{name}".lstrip("/")) in tracked]


def _given(root, rev: str, path: str) -> dict:
    """port intent が名指した文書。rev に無い・読めなければ作業ツリーのファイルを読み、それも読めなければ text を空にして訳を残す"""
    try:
        return _doc(path, rev, _git(root, "show", f"{rev}:{path}"))
    except RuntimeError:
        pass
    try:
        return _doc(path, rev, (pathlib.Path(root) / path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        return _doc(path, rev, "", f"{path} は {rev} に無く、作業ツリーのファイルも読めない（{type(e).__name__}）")


def find(root, rev: str, paths, given, policy=None) -> list:
    """[{path, rev, text, cut, reason}]。given（port intent のパス）が空でなければその各パス、空なら決まった名で探した文書。
    policy（方針の文書のファイル。無ければ None）が在れば、最後の 1 本として足す（rev は POLICY_REV）"""
    if given:
        docs = [_given(root, rev, p) for p in given]
    else:
        docs = [_doc(p, rev, _git(root, "show", f"{rev}:{p}")) for p in named(root, rev, paths)]
    if policy is not None:
        policy = pathlib.Path(policy)
        try:
            shown = str(policy.relative_to(pathlib.Path(root).resolve()))
        except ValueError:
            shown = str(policy)
        try:
            docs.append(_doc(shown, POLICY_REV, policy.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as e:
            docs.append(_doc(shown, POLICY_REV, "", f"方針の文書が読めない（{type(e).__name__}）"))
    return docs


def shown_docs(docs) -> str:
    """指示の {intent_docs}: 本文の在る文書ごとに見出し・切った時の印の 1 行・本文。読めなかった文書は見出しだけ。文書の間は空行 1 つ"""
    out = []
    for d in docs:
        if not d["text"]:
            out.append(f"### {d['path']} (could not be read: {d['reason'] or 'empty'})")
            continue
        head = f"### {d['path']} ({d['rev'][:12]}, lines 1-{len(d['text'].splitlines())})"
        cut = f"\n(cut: the first {TEXT_CAP} characters are shown; {d['cut']} more were left out)" if d["cut"] else ""
        out.append(f"{head}{cut}\n\n{d['text']}")
    return "\n\n".join(out)
