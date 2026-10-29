"""書いた意図（対象のリポジトリが文で書いた憲法・決まり・設計）を探して読む（docs/design/structure.md の 3 節）。

決まった名の文書 ARCHITECTURE.md・AGENTS.md（根と、単位のファイルの上の各フォルダ）か、port intent で渡された文書と、port policy の
方針の文書。読む版 rev の追跡されたファイルだけを git show で読む（直しが意図の文書を書き換えても、比べる基準は直す前の意図）。
それらの文書が名指したファイルのうち版 rev に無い物（指示ファイルが先に取り込まれ、指す正典はまだ取り込まれていない枝にだけ在る、など）は、
ほかの版で探して本文を読み（cite.elsewhere）、どの版にも無い物は本文の空の行で名指す（欄 pointed_by に名指した文書、at に見つけた版の名）。
"""
from __future__ import annotations

import pathlib
import subprocess

import cite   # lib/。文書が名指したファイルを、版に無ければほかの版で探す

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


def pointed(root, rev: str, docs) -> list:
    """docs の本文が名指したファイルのうち、版 rev に無い物の行 [{path, rev, text, cut, reason, pointed_by, at}]（名指した文書の順・
    重なりなし）。ほかの版で見つけた物は、その版のパスと commit と本文。どの版にも無い物は名指しのままのパスと空の本文と訳。rev が
    読めなければ RuntimeError"""
    seen, out = {d["path"] for d in docs}, []
    for d in docs:
        paths = [p for p in cite.named_files(d["text"]) if p not in seen]
        if not paths:
            continue
        try:
            rows = cite.elsewhere(root, rev, paths)
        except OSError as e:
            raise RuntimeError(str(e)) from None
        for r in rows:
            seen.update({r["path"], r["found"]})
            why = "" if r["commit"] else f"{d['path']} が名指すが、版 {rev[:12]} にもほかのどの版にも無い"
            out.append({**_doc(r["found"] or r["path"], r["commit"] or rev, r["text"], why), "pointed_by": d["path"], "at": r["at"]})
    return out


def find(root, rev: str, paths, given, policy=None) -> list:
    """[{path, rev, text, cut, reason}]。given（port intent のパス）が空でなければその各パス、空なら決まった名で探した文書。それらが
    名指し、版 rev に無いファイルの行（pointed。欄 pointed_by・at が足される）を続けて足す。policy（方針の文書のファイル。無ければ None）が
    在れば、最後の 1 本として足す（rev は POLICY_REV）"""
    if given:
        docs = [_given(root, rev, p) for p in given]
    else:
        docs = [_doc(p, rev, _git(root, "show", f"{rev}:{p}")) for p in named(root, rev, paths)]
    docs += pointed(root, rev, docs)
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
        away = f"; pointed to by {d['pointed_by']}, not in the version under review, taken from {d.get('at') or 'another version'}" \
            if d.get("pointed_by") else ""
        head = f"### {d['path']} ({d['rev'][:12]}, lines 1-{len(d['text'].splitlines())}{away})"
        cut = f"\n(cut: the first {TEXT_CAP} characters are shown; {d['cut']} more were left out)" if d["cut"] else ""
        out.append(f"{head}{cut}\n\n{d['text']}")
    return "\n\n".join(out)


def pointed_rows(docs) -> list:
    """控えの欄 pointed: 名指された文書のうち版に無かった物ごとに {path, by（名指した文書）, found（ほかの版で見つけたか）, at（見つけた版の
    ref の名。名が無ければ commit の頭 12 字。無い物は空）}（line が修正前の承認ノードで人に問う。docs/design/structure.md の 3 節）"""
    return [{"path": d["path"], "by": d["pointed_by"], "found": bool(d["text"]),
             "at": (d.get("at") or d["rev"][:12]) if d["text"] else ""} for d in docs if d.get("pointed_by")]


def report_lines(docs) -> list:
    """報告の日本語の行: 名指された文書のうち版に無かった物ごとに 1 行（ほかの版から読んだか、どの版にも無いか）"""
    out = []
    for d in docs:
        if not d.get("pointed_by"):
            continue
        where = f"{d.get('at') or d['rev'][:12]} の版から読んで書いた意図に足した" if d["text"] else "どの版にも無く読めない"
        out.append(f"書いた意図: {d['pointed_by']} が名指す {d['path']} は、読む版に無い（{where}）")
    return out
