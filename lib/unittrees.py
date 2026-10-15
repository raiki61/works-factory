"""組の差分を親の作業ツリーへ当てる口（元 works/.shared/core/unittrees.py の、fix の組の締めが使う部分）。層 L1（works の物を
何も知らない）。標準ライブラリと git だけ。

組ごとの子の run（fan_out）が直した差分（groups.diff_since）を、締めの節 join（fixboard.join_group）が親の作業ツリーへ順に当てる。
親の作業ツリー（repo）の本物の index・HEAD・枝はどの口も動かさない（index を使う手は全部一時の GIT_INDEX_FILE で回す）。

- fresh_tree(repo) -> sha: 作業ツリーの今の姿の木の sha（HEAD を空の一時の index に読んで add -A。commit も参照も作らない。
  同じ中身なら同じ sha。試験の結果の使い回しの鍵が使う）
- apply(repo, patch, union=(), unioned=None, check=None, marked=None) -> (ok, why): 作業ツリーへ当てる。一時の index で
  `git apply --cached --3way` を試し、食い違いが無い時だけ、その結果と今の姿の差分を作業ツリーへ当てる（index を汚さない）。
  当たらなければ作業ツリーを変えずに (False, 理由)。union（根からの相対のパスの並び）の中のファイルの食い違いが「挿しだけ」
  （3 方向の食い違いの塊がどれも base の側に行を持たない＝両方が同じ所に行を足しただけ）なら、作業ツリーの側の行の後に patch の
  側の行を置いて合わせる（合わせたパスを unioned に積む。check が偽を返す中身は合わせない）。並びの外のファイル・行を変えた
  塊・base の無い（両方が新しく作った）ファイルは今どおり当てない。marked（list）を渡すと、合わせられない食い違いも当てる:
  食い違いの塊を印（MARK_LABELS の名の `<<<<<<<`・`|||||||`・`=======`・`>>>>>>>`。git merge-file --diff3）つきで書き、印を
  書いたパスを marked に積む（片方が消した・バイナリなど印を書けないファイルが在れば今どおり当てない）
- markers_left(repo, paths): paths のうち食い違いの印の行が残るファイルの並び
- tests_unique(path, text): 合わせた中身の照らし（apply の check に渡す。同じ名のテストの定義が 2 つ在れば偽）
- patch_names(patch): 差分の行先のパスの並び

apply は同時に呼ばない前提（呼び手が組の差分を 1 つずつ当てる。2 つが同時に作業ツリーを書くと後の方が当たらずに返る）。
"""
from __future__ import annotations

import ast
import os
import pathlib
import shutil
import subprocess
import tempfile

# 外から継いだ git の居場所の変数は落とす（hook や節の中から呼ばれても、渡した repo・path だけを見る）
_GIT_PLACE = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
              "GIT_COMMON_DIR", "GIT_PREFIX")
# 利用者の設定に左右されない差分の形（apply が読める a/・b/ の頭・外の diff と textconv なし）
_DIFF = ["-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "diff", "--binary", "--no-renames", "--no-ext-diff",
         "--no-textconv", "--no-color", "--src-prefix=a/", "--dst-prefix=b/"]


def pathspec_without(skip) -> list:
    """git の pathspec: リポジトリの根の全部から、除くパスの頭 skip の下を外す"""
    return [":/", *[f":(top,exclude){s.rstrip('/')}" for s in skip]]


class UnitTreeError(RuntimeError):
    """git が落ちた（どのコマンドかと標準エラーを文に載せる）"""


def _env(index: str | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _GIT_PLACE}
    if index is not None:
        env["GIT_INDEX_FILE"] = index
    return env


def _git(cwd, *args, index: str | None = None, data: bytes | None = None, env: dict | None = None,
         check: bool = True) -> subprocess.CompletedProcess:
    """cwd で git を起こす（バイトのまま）。check なら落ちた時に UnitTreeError"""
    r = subprocess.run(["git", "-C", str(cwd), *args], input=data, capture_output=True,
                       env={**_env(index), **(env or {})})
    if check and r.returncode != 0:
        raise UnitTreeError(f"git {' '.join(args[:3])} が落ちた（{cwd}）: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r


def _out(cwd, *args, **kw) -> str:
    return _git(cwd, *args, **kw).stdout.decode("utf-8", "replace").strip()


def _tree_now(tree, tmp: str) -> str:
    """tree の作業ツリーの今の姿の木（一時の index に本物の index を写して add -A。本物の index は動かさない）"""
    index = os.path.join(tmp, "index")
    real = _out(tree, "rev-parse", "--path-format=absolute", "--git-path", "index")
    if os.path.isfile(real):   # 写すと stat の控えが効き、変わったファイルだけを読み直す。写しの mtime は本物に揃える
        # （git は index の mtime と同じ秒に書かれたファイルを stat で信じずに中身を読む。写しの mtime が今になると、
        # 同じ秒・同じ大きさで書き換えたファイルを変わっていないと読み、直しを落とす）
        shutil.copy2(real, index)
    _git(tree, "add", "-A", index=index)
    return _out(tree, "write-tree", index=index)


def fresh_tree(repo) -> str:
    """repo の作業ツリーの今の姿（追跡中のファイルと、.gitignore に当たらない未追跡のファイルの中身・実行ビット・シンボリック
    リンク）の木の sha。HEAD を空の一時の index に読み、add -A して write-tree する——本物の index の assume-unchanged などの
    印を継がないので、同じ中身なら同じ sha になる（_tree_now は本物の index を写すので、中身の鍵には使わない）。
    本物の index・HEAD・枝は動かさない。git の木でなければ UnitTreeError"""
    with tempfile.TemporaryDirectory(prefix="works-unit-") as tmp:
        index = os.path.join(tmp, "index")
        if _git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False).returncode == 0:
            _git(repo, "read-tree", "HEAD", index=index)
        _git(repo, "add", "-A", "--", ":/", index=index)
        return _out(repo, "write-tree", index=index)


def apply(repo, patch: str, union=(), unioned: list | None = None, check=None,
          marked: list | None = None) -> tuple[bool, str]:
    """patch を run の作業ツリー repo へ 3 方向で当てる。(True, "") か、作業ツリーを変えずに (False, 理由)。
    一時の index（作業ツリーの今の姿）で `git apply --cached --3way` を試し、食い違い（未解決の段）が残れば当てない。
    ただし未解決のファイルが全部 union の中で、どれも挿しだけの食い違いなら合わせて通す（頭の注記。合わせたパスを unioned に積む）。
    check（任意。(パス, 合わせた中身のバイト) → 真偽）が偽を返すファイルは合わせない（呼び手の言語ごとの照らし）。
    marked（list）を渡すと、合わせられない未解決のファイルに食い違いの印を書いて当て、そのパスを marked に積む（頭の注記）。
    通れば、今の姿とその結果の木の差分を作業ツリーへそのまま当てる（git apply は全部か無しか。本物の index は読まない）"""
    if not patch.strip():
        return True, ""
    data = patch.encode("utf-8", "surrogateescape")
    with tempfile.TemporaryDirectory(prefix="works-unit-") as tmp:
        before = _tree_now(repo, tmp)
        index = os.path.join(tmp, "index")
        r = _git(repo, "apply", "--cached", "--3way", "--whitespace=nowarn", index=index, data=data, check=False)
        left = _unmerged(repo, index)
        err = r.stderr.decode("utf-8", "replace").strip()
        settled = _settle(repo, index, left, set(union), tmp, check, marked is not None) if left else ([], [])
        broke = any(ln.startswith(("error:", "fatal:")) for ln in err.splitlines())
        if broke or (r.returncode != 0 and not left) or settled is None:
            return False, (err or "3 方向で当てると食い違いが残る")
        merged, put = settled
        if merged and unioned is not None:
            unioned.extend(merged)
        if put:
            marked.extend(put)
        after = _out(repo, "write-tree", index=index)
        if after == before:
            return True, ""
        step = _git(repo, *_DIFF, before, after).stdout
    r = _git(repo, "apply", "--whitespace=nowarn", data=step, check=False)
    if r.returncode != 0:   # 試してから当てるまでの間に作業ツリーが変わった
        return False, r.stderr.decode("utf-8", "replace").strip()
    return True, ""


def tests_unique(path: str, text: bytes) -> bool:
    """合わせた中身 text（path のファイル）の照らし（apply の check に渡す）: .py なら、モジュールとクラスの本体ごとに test・Test
    で始まる定義の名が 2 つ無いか（後の定義が前を隠す）。読めない（構文の誤り・文字の誤り）なら偽。.py でなければ真"""
    if not str(path).endswith(".py"):
        return True
    try:
        tree = ast.parse(text.decode("utf-8"))
    except (SyntaxError, ValueError):
        return False
    kinds = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    bodies = [tree.body] + [n.body for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for body in bodies:
        names = [n.name for n in body if isinstance(n, kinds) and n.name.lower().startswith("test")]
        if len(names) != len(set(names)):
            return False
    return True


def markers_left(repo, paths) -> list:
    """paths（根からの相対）のうち、食い違いの印の始めか終わりの行（`<<<<<<< `・`>>>>>>> `）が残るファイル（無いファイルは外す）"""
    out = []
    for p in paths:
        f = pathlib.Path(repo) / p
        if f.is_file() and any(ln.startswith((b"<<<<<<< ", b">>>>>>> ")) for ln in f.read_bytes().splitlines()):
            out.append(p)
    return out


def patch_names(patch: str) -> list:
    """patch の行先のパス（`diff --git a/x b/x` の b 側。--no-renames なので a と同じ）"""
    out = []
    for ln in patch.splitlines():
        if ln.startswith("diff --git a/") and " b/" in ln:
            name = ln.rsplit(" b/", 1)[1]
            if name not in out:
                out.append(name)
    return out


def _unmerged(repo, index: str) -> dict:
    """一時の index の未解決のパス → {段: (mode, sha)}"""
    out = {}
    for ln in _out(repo, "ls-files", "-u", index=index).splitlines():
        head, _, path = ln.partition("\t")
        mode, sha, stage = head.split()
        out.setdefault(path, {})[int(stage)] = (mode, sha)
    return out


def _insert_only(text: bytes) -> bytes | None:
    """`git merge-file --diff3 -L ours -L base -L theirs` の出力を、塊がどれも base の側に行を持たない時だけ ours の行の後に
    theirs の行を置いた中身にする。base の側に行の在る塊・閉じない塊・改行で終わらない ours の行が在れば None"""
    out, state, ours, base, theirs = [], None, [], [], []
    for ln in text.splitlines(keepends=True):
        s = ln.rstrip(b"\r\n")
        if state is None:
            if s == b"<<<<<<< ours":
                state, ours, base, theirs = "ours", [], [], []
            else:
                out.append(ln)
        elif state == "ours":
            if s == b"||||||| base":
                state = "base"
            else:
                ours.append(ln)
        elif state == "base":
            if s == b"=======":
                state = "theirs"
            else:
                base.append(ln)
        elif s == b">>>>>>> theirs":
            if base or any(not x.endswith(b"\n") for x in ours):
                return None
            out += ours + theirs
            state = None
        else:
            theirs.append(ln)
    return None if state is not None else b"".join(out)


def _union(repo, index: str, left: dict, allowed: set, tmp: str, check=None) -> list | None:
    """未解決のパス left を全部、挿しだけの食い違いとして一時の index で合わせる。合わせたパスの並びか、1 つでも合わせられなければ
    None（index はそのまま。呼び手は当てない）"""
    plan = []
    for path, stages in sorted(left.items()):
        if path not in allowed or set(stages) != {1, 2, 3}:
            return None
        files = []
        for n in (2, 1, 3):
            f = os.path.join(tmp, f"union-{n}")
            pathlib.Path(f).write_bytes(_git(repo, "cat-file", "blob", stages[n][1]).stdout)
            files.append(f)
        r = _git(repo, "merge-file", "-p", "--diff3", "-L", "ours", "-L", "base", "-L", "theirs", *files, check=False)
        if r.returncode > 127:   # 落ちた（食い違いの数は 127 まで）
            return None
        text = _insert_only(r.stdout)
        if text is None or (check is not None and not check(path, text)):
            return None
        plan.append((path, stages[2][0], text))
    for path, mode, text in plan:
        sha = _out(repo, "hash-object", "-w", "--stdin", data=text)
        _git(repo, "update-index", "--cacheinfo", f"{mode},{sha},{path}", index=index)
    return [p for p, _, _ in plan]



MARK_LABELS = ("今の作業ツリー", "元", "当てる差分")


def _settle(repo, index: str, left: dict, allowed: set, tmp: str, check, marking: bool) -> tuple[list, list] | None:
    """未解決のパス left を一時の index で解く: (合わせたパス, 印を書いたパス) か、解けなければ None。marking が偽なら全部を
    挿しだけの食い違いとして合わせ（_union）、真なら合わせられる物を 1 つずつ合わせて残りに印を書く（_mark）"""
    if not marking:
        merged = _union(repo, index, left, allowed, tmp, check)
        return None if merged is None else (merged, [])
    merged = [p for p in sorted(left) if p in allowed and _union(repo, index, {p: left[p]}, allowed, tmp, check)]
    put = _mark(repo, index, {p: st for p, st in left.items() if p not in merged}, tmp)
    return None if put is None else (merged, put)


def _mark(repo, index: str, left: dict, tmp: str) -> list | None:
    """未解決のパス left に食い違いの印を書いた中身（git merge-file --diff3。印の名は MARK_LABELS。両方が新しく作ったファイルは空の
    base で）を一時の index に置く。置いたパスの並びか、印を書けない物（片方が消した・普通のファイルでない・バイナリで落ちた）が
    1 つでも在れば None（index はそのまま）"""
    plan = []
    labels = [a for name in MARK_LABELS for a in ("-L", name)]
    for path, stages in sorted(left.items()):
        if set(stages) not in ({1, 2, 3}, {2, 3}) or not all(stages[n][0].startswith("100") for n in (2, 3)):
            return None
        files = []
        for n in (2, 1, 3):
            f = os.path.join(tmp, f"mark-{n}")
            pathlib.Path(f).write_bytes(_git(repo, "cat-file", "blob", stages[n][1]).stdout if n in stages else b"")
            files.append(f)
        r = _git(repo, "merge-file", "-p", "--diff3", *labels, *files, check=False)
        if not 0 <= r.returncode <= 127:   # 落ちた（食い違いの数は 127 まで）
            return None
        plan.append((path, stages[2][0], r.stdout))
    for path, mode, text in plan:
        sha = _out(repo, "hash-object", "-w", "--stdin", data=text)
        _git(repo, "update-index", "--cacheinfo", f"{mode},{sha},{path}", index=index)
    return [p for p, _, _ in plan]
