"""作業ツリーの書き込みの出どころの突き合わせ（書く役の受け付け: blk-fix の fix-accept・tdd-step、blk-refix の手直しの受け付け）。

隔離した設定の PostToolUse:Edit|Write|NotebookEdit のフック（bin/_lib/record-write.py）が、書いた後の中身の sha を
作業の場ごとの writes.jsonl（writelog.log_path）に 1 行ずつ残す。ここは版からの変更を、その記録と役の申告
（返答の欄 bash_writes: [{path, why}]）に突き合わせる。
射程: 見るのは「今の中身と同じ中身を、編集の道具が書いたか役が申告したことがあるか」まで。Bash で書いた後に同じ中身を
Edit で書き直した物は区別しない（出どころの全部は証さない）。
- writes.jsonl が無い run（記録の根の無い起動。fix の始めの節が根の在る時だけ空のファイルを作る）は拒否の理由にせず通し、NO_RECORD を
  返す（呼び手が置き場の trace.jsonl に NO_RECORD_OP で 1 行残し、報告に出る。fixboard.trace）
- 通った申告は記録に tool_name "declared" の行で足す（後ろの受け付け——fix の後の refix など——が同じ申告を求めない）
- 除くパスの頭（check・unrecorded の引数 skip。既定 ()。呼び手の script が実行基盤の工程の写しの置き場を渡す）の下は数えない
- 単位の worktree（依頼 243 の並べ。修正役の下請けが run の作業ツリーの外で書く所）の記録は、機械が差分を run の作業ツリーへ
  当てた後に carry で写す。写すのは、run の作業ツリーの今の中身が単位の worktree の今の中身と同じで、その中身に記録が在る物だけ
  （tool_name CARRY_TOOL と元の実パス from。2 つの差分を合わせて中身が違う物は写さず、役が申告する）
- 並べた組の子の run（自分の作業ツリーで直し、自分の記録を持つ）の記録は、join が子の差分を当てた後に carry_children で写す
  （子の記録の行を足してから carry・carry_merged と同じ決まり）
- TDD の輪の並べ（依頼 243 の並べの 3 段目）で sandbox の外の機械が 2 つ以上の単位の worktree の差分を 3 方向で合わせたファイルは、
  carry_merged が合わせた中身に 1 行を足す（合わせたどの単位の worktree の中身にも記録が在る時だけ。from は元の実パスの並び）。
  合わせたのは機械なので、機械が出どころを請け負う（役の sandbox の中の当てるコマンドの結果には使わない）
標準ライブラリだけ。
"""
import hashlib
import json
import os
import pathlib
import posixpath
import sys
import tempfile
import time

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import fixboard  # noqa: E402  （置き場の trace.jsonl への 1 行）
import impact  # noqa: E402  （テストのファイルの名の慣習 is_test）
from leftovers import Unreadable, git, git_names  # noqa: E402

FIELD = "bash_writes"
MIN_WHY = 10
ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["path", "why"],
    "properties": {"path": {"type": "string", "minLength": 1}, "why": {"type": "string", "minLength": MIN_WHY}},
}
BASH_WRITES_SCHEMA = {"type": "array", "items": ITEM_SCHEMA}
NO_RECORD = "書き込みの記録が無い run（記録の根の無い起動）——書き込みの出どころを突き合わせずに通した"
NO_RECORD_OP = "writes_unrecorded_run"   # 置き場の trace.jsonl の行（報告が数える）
CARRY_TOOL = "unit-merge"               # 単位の worktree の記録を写した行の tool_name（carry）
BASE_TESTS_UNREAD_OP = "writes_base_tests_unread"   # 修正前の版のテストを読み損ねた（base_test_texts。盤面の trace の行 {rev, unread}）
LEFT_OP = "writes_left"                  # 拒まずに残した記録の無い変更（欄 bash_writes を持たない手直しの役）
REJECT = ("作業ツリーの変更に、書き込みの記録（Edit・Write）も申告（bash_writes）も無い——Edit・Write で書き直すか、返答の "
          "bash_writes にパスと、Bash で書いた理由（実行の権限・バイナリ・大量の機械的な置き換え）を書け（射程: 見るのは今の中身を"
          "編集の道具が書いたか申告したかまでで、Bash で書いた後に同じ中身を Edit で書き直した物は区別しない）: ")


def pop(reply: dict) -> tuple:
    """(欄 bash_writes を外した返答, 申告の一覧)"""
    reply = dict(reply)
    return reply, reply.pop(FIELD, None) or []


def shape_problems(items) -> list:
    if not isinstance(items, list):
        return [f"{FIELD} は {{path, why}} の配列"]
    out = []
    for i in items:
        if not isinstance(i, dict) or not isinstance(i.get("path"), str) or not i["path"].strip():
            out.append(f"{FIELD} の行にパスが無い（{i!r:.120}）")
        elif not isinstance(i.get("why"), str) or len(i["why"].strip()) < MIN_WHY:
            out.append(f"{FIELD} の {i['path']} に理由（{MIN_WHY} 字以上）が無い")
        elif _rel(i["path"]) is None:
            out.append(f"{FIELD} の {i['path']} はリポジトリの根からの相対パスでない")
    return out


def _rel(p: str):
    n = posixpath.normpath(p.strip())
    return None if n.startswith("/") or n == ".." or n.startswith("../") else n


def base_test_texts(b, repo, rev: str) -> dict:
    """修正前の版 rev（呼び手が fixboard.base_rev で選ぶ）に在ったテストの .py（名の慣習 impact.is_test の module）の中身 {パス: 中身}（git ls-tree・git show）。
    版が読めない・読めないファイルは含めない（空なら {}）が、読み損ねたことは置き場 b の trace.jsonl の行 BASE_TESTS_UNREAD_OP（版と読めなかった
    パス。版が読めなければ unread は空でなく ["<版>"]）に残す——含めなかったテストを名指す許しは凍結した欄に載らないので、後の拒否の
    原因を辿れるようにする"""
    try:
        names = git_names(repo, "ls-tree", "-r", "--name-only", rev)
    except Unreadable:
        fixboard.trace(b, BASE_TESTS_UNREAD_OP, rev=rev, unread=["<版>"])
        return {}
    out, unread = {}, []
    for path in sorted(names):
        if path.endswith(".py") and impact.is_test(path) == "module":
            try:
                out[path] = git(repo, "show", f"{rev}:{path}")
            except Unreadable:
                unread.append(path)
    if unread:
        fixboard.trace(b, BASE_TESTS_UNREAD_OP, rev=rev, unread=unread)
    return out


def changed(repo, rev: str) -> list:
    """版 rev からの変更（変えた・消した・git が無視しない新しいファイル。リポジトリの根から）。rev の木と比べる（changed_from）
    ので、rev に在る未追跡のファイル（写しの核が版を固める review_rev は作業ツリーの未追跡のファイルも入れる。仕様の段の書き手が
    版を固める前に書いた受け入れ条件のテストなど）は、中身が同じなら変更に数えない。前は本物の index と比べ、未追跡のファイルを
    全部変更と数えたので、仕様の段の run の修正の受け付けが書き手のテストを修正役の範囲の外れと拒んだ"""
    return changed_from(repo, rev)


def changed_from(repo, tree: str) -> list:
    """木 tree（commit でも、作業ツリーの写しの木 leftovers.snapshot でもよい）からの変更。changed と同じ語（変えた・消した・git が
    無視しない新しいファイル。根から）を、本物の index の代わりに tree を読んだ一時の index で取る。changed(repo, tree) は index に
    無いファイルを全部新しいと数え、tree に在って index に無いファイルを消したと数えるので、HEAD・index と違う木（修正役の並べの枝の
    項目の頭。前の項目が作ったファイルは index に無い）からは使えない。中身の比べは git に任せる（改行の変換などの filter も）。
    git の物の置き場と本物の index には書かない（役の sandbox の中の事前の確かめでも回る）"""
    with tempfile.TemporaryDirectory(prefix="works-writes-index-") as td:
        env = {**os.environ, "GIT_INDEX_FILE": str(pathlib.Path(td) / "index")}
        git(repo, "read-tree", tree, env=env)
        # 一時の index は stat を持たない: 中身で比べて stat を埋める（利用者の diff.autoRefreshIndex=false でも触っていないファイルを
        # 変わったと数えない。書くのは一時の index だけ）
        git(repo, "update-index", "-q", "--refresh", env=env)

        def names(*args):
            return {os.fsdecode(n) for n in git(repo, args[0], "-z", *args[1:], text=False, env=env).split(b"\0") if n}
        return sorted(names("diff", "--name-only", "--no-renames", "--", ":/")
                      | names("ls-files", "--others", "--exclude-standard", "--full-name", "--", ":/"))


def _sha(path: str):
    try:
        return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    except OSError:
        return None   # 消した（か読めない）ファイル


def records(log: pathlib.Path) -> dict:
    """実パス → 記録に在る中身の sha の集まり（消した申告は None）"""
    out = {}
    try:
        text = log.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return out
    for ln in text.splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("path"), str):
            out.setdefault(os.path.realpath(r["path"]), set()).add(r.get("file_sha"))
    return out


def unrecorded(repo, paths, log: pathlib.Path, declared=(), skip: tuple = ()) -> list:
    """paths のうち、今の中身の記録も申告も無い物（除くパスの頭 skip の下は数えない）"""
    rec = records(log)
    decl = {_rel(d["path"]) for d in declared}
    out = []
    for p in paths:
        if p in decl or p.startswith(tuple(skip)):
            continue
        path = os.path.join(str(repo), p)
        real = os.path.realpath(path)
        if os.path.islink(path) or _sha(real) not in rec.get(real, ()):   # symlink は編集の道具では作れない（申告が要る）
            out.append(p)
    return out


def carry(log: pathlib.Path, pairs) -> list:
    """pairs [(単位の worktree のファイル, run の作業ツリーの同じ相対のファイル)] のうち、2 つの今の中身が同じで、元の中身に記録が
    在る物だけ、行先の記録を足す（tool_name CARRY_TOOL・from は元の実パス）。足した行先の実パスの並び"""
    rec = records(log)
    rows, out = [], []
    for src, dst in pairs:
        src_real, dst_real = os.path.realpath(str(src)), os.path.realpath(str(dst))
        sha = _sha(src_real)
        if sha is None or os.path.islink(str(dst)) or _sha(dst_real) != sha or sha not in rec.get(src_real, ()):
            continue
        rows.append(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool_name": CARRY_TOOL, "path": dst_real,
                                "file_sha": sha, "from": src_real}, ensure_ascii=False))
        out.append(dst_real)
    if rows:
        with open(log, "a", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    return out


def carry_merged(log: pathlib.Path, dst, srcs) -> bool:
    """機械が srcs（単位の worktree の同じ相対のファイルの並び）を 3 方向で合わせた run の作業ツリーのファイル dst に、記録を
    1 行足す（tool_name CARRY_TOOL・from は元の実パスの並び）。srcs のどれもが今の中身の記録を持ち、dst が在って symlink で
    ない時だけ。足したか"""
    rec = records(log)
    reals = [os.path.realpath(str(s)) for s in srcs]
    if not reals or any(_sha(r) is None or _sha(r) not in rec.get(r, ()) for r in reals):
        return False
    dst_real = os.path.realpath(str(dst))
    sha = _sha(dst_real)
    if sha is None or os.path.islink(str(dst)):
        return False
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool_name": CARRY_TOOL, "path": dst_real,
                            "file_sha": sha, "from": reals}, ensure_ascii=False) + "\n")
    return True


def carry_children(log: pathlib.Path, repo, children) -> list:
    """並べた組の子の run の記録を、子の差分を当てた run の作業ツリーの記録 log へ写す。children は [(子の作業ツリー, 子の記録の
    ファイル, 当てたパスの並び)]。子の記録の行を log の後ろに足してから、1 つの子だけが当てたパスは carry、2 つ以上の子が当てた
    パスは carry_merged で写す（当てた後の中身が子の今の中身と同じか、合わせた全部の子の中身に記録が在る物だけ）。足した行先の
    実パスの並び"""
    copied, pairs, srcs = [], [], {}
    for tree, child_log, names in children:
        if pathlib.Path(child_log) == pathlib.Path(log) or not pathlib.Path(child_log).is_file():
            continue
        copied.append(pathlib.Path(child_log).read_text(encoding="utf-8"))
        for n in names:
            srcs.setdefault(n, []).append(pathlib.Path(tree) / n)
    if copied:
        with open(log, "a", encoding="utf-8") as f:
            f.write("".join(t if t.endswith("\n") or not t else t + "\n" for t in copied))
    for n, found in srcs.items():
        if len(found) == 1:
            pairs.append((found[0], pathlib.Path(repo) / n))
    out = carry(log, pairs) if pairs else []
    for n, found in sorted(srcs.items()):
        if len(found) > 1 and carry_merged(log, pathlib.Path(repo) / n, found):
            out.append(os.path.realpath(str(pathlib.Path(repo) / n)))
    return out


def keep_declared(log: pathlib.Path, repo, declared) -> None:
    rows = [json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool_name": "declared",
                        "path": os.path.realpath(os.path.join(str(repo), _rel(d["path"]))),
                        "file_sha": _sha(os.path.join(str(repo), _rel(d["path"]))), "why": d["why"].strip()},
                       ensure_ascii=False) for d in declared]
    if rows:
        with open(log, "a", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")


def check(reply: dict, repo, paths, log: pathlib.Path, *, strict: bool = True, skip: tuple = ()) -> dict:
    """返りは {reply（欄 bash_writes を外した返答）, problems, note, left}。
    strict でなければ記録の無い変更は拒まずに left に返す（欄を持たない役）。skip は除くパスの頭（unrecorded に渡す）"""
    reply, items = pop(reply)
    bad = shape_problems(items)
    if bad:
        return {"reply": reply, "problems": bad, "note": "", "left": []}
    if not log.is_file():
        return {"reply": reply, "problems": [], "note": NO_RECORD, "left": []}
    left = unrecorded(repo, paths, log, items, skip)
    if left and strict:
        return {"reply": reply, "problems": [REJECT + ", ".join(left)], "note": "", "left": left}
    keep_declared(log, repo, items)
    return {"reply": reply, "problems": [], "note": "", "left": left}


def trace(b, node: str, got: dict) -> None:
    """記録の無い run と、拒まずに残した変更を置き場 b の trace.jsonl に 1 行（報告が数える）"""
    if got["note"]:
        fixboard.trace(b, NO_RECORD_OP, node=node, note=got["note"])
    if got["left"]:
        fixboard.trace(b, LEFT_OP, node=node, paths=got["left"])
