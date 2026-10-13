"""受け付けの口。役の返答を、写した graphloops の規則（rules/review-loop.py）と検証器（scripts/review-record.py）に通す。

実行基盤を知らない関数だけを出す。ブロックの script の節がこれを呼び、結果をそのまま出口にする。
- snapshot_tree: 作業ツリーの写し（git が無視するファイルも入れる。index の印に隠れた物も入れる。tree_state の土台）
- tree_state・tree_change・tree_moved: 読むだけの役（blk-pr・blk-ci・entry.take・rejudge.take）を起こす前後の作業ツリーの姿
                 （snapshot_tree に HEAD・枝を足した物）と、その違いの文（R47）。
                 caches はテストのキャッシュの名の形（_is_test_cache）。当たる物を姿から除く（測るためにコマンドを走らせる実測役・テストを回しうる素材集めの役の見張り）
- guard・in_repo・resolve_rev・read_board・write_board・type_errors: 受け付けの部品の公開の名（ブロックのモジュールの受け付けが使う）
- touched_files: 修正が触ったファイル（テストのキャッシュは除く。index の印に隠れた物も入れる。protect が数える）
- flag_free_env: 本物の index の assume-unchanged・skip-worktree の印を外して git に作業ツリーを見せる env（protect も使う。
                 sparse checkout の範囲外の印は残す）。copy_flag_free_index はその写しの index を作る（judge_accept の版の固定も使う）

git は全部 repo を cwd にして呼ぶ。HEAD をその場で読むのは base_rev が空のときだけ（空なら repo の HEAD を版にする）。
"""
import contextlib
import fnmatch
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

# pack の中に __pycache__ を作らない。ここで立てて止まるのは下で import する engine・rules・検証器の分だけ。
# accept.py 自身の .pyc は、この行が動く前に import の時点で書かれるので、止めるのは呼び手（import する前に立てる。
# ブロックのスクリプトの前置きは script_io の docstring）
sys.dont_write_bytecode = True

CORE = pathlib.Path(__file__).resolve().parent
_GL = CORE / "graphloops"
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

import engine.util as _util  # noqa: E402
from engine.schema import validate_schema  # noqa: E402
from engine.util import Reject  # noqa: E402

RACY_NS = 2_000_000_000   # ファイルの時刻の細かさの上限（FAT の 2 秒）。これより新しい mtime は印だけでは信じない

SNAPSHOT_KEYS = ("porcelain", "ignored", "diff_sha256")
SNAPSHOT_SCHEMA = {"type": "object", "required": list(SNAPSHOT_KEYS), "properties": {
    "porcelain": {"type": "string"}, "ignored": {"type": "array", "items": {"type": "string"}},
    "diff_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}}


# ---------------------------------------------------------------- git と盤面のファイル
def _git(repo, *args, binary=False, env=None, stdin=None):
    """repo を cwd にして git を呼ぶ。env は今の環境の上に重ね、stdin（バイト）は標準入力に渡す。
    失敗は Reject（受け付けは『分からない』を合格に倒さない）"""
    feed = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
    try:
        r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, env={**os.environ, **(env or {})}, **feed)
    except OSError as e:
        raise Reject(f"git {' '.join(args)} を呼べない（{type(e).__name__}: {e}）")
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip()[-300:]
        raise Reject(f"git {' '.join(args)} が失敗した（{err or f'exit {r.returncode}'}）")
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


@contextlib.contextmanager
def _in_repo(repo):
    """rules に差し込まれた git（engine/util.py の git）を repo に向ける。呼び終えたら戻す"""
    old = _util.GIT_CWD
    _util.GIT_CWD = str(repo)
    try:
        yield
    finally:
        _util.GIT_CWD = old


def _rev(repo, base_rev):
    """数える・差分を取る版。空なら repo の HEAD（Ruling R2）。版として引けなければ拒む"""
    name = base_rev or "HEAD"
    if name.startswith("-"):
        raise Reject(f"base_rev {base_rev!r} は版の名前でない")
    try:
        return _git(repo, "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}").strip()
    except Reject:
        raise Reject(f"base_rev {base_rev!r} が repo {repo} の版として引けない")


def _read_board(board, name):
    p = pathlib.Path(board) / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Reject(f"共有ボードの {name} が読めない（{e}）")


def _write_board(board, name, obj):
    p = pathlib.Path(board) / name
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return p


def _type_errors(value, schema, what):
    errs = validate_schema(value, schema)
    if errs:
        raise Reject(f"{what}の型が合わない: " + "; ".join(errs[:10]) + (f"（ほか {len(errs) - 10} 件）" if len(errs) > 10 else ""))


def _guard(fn, **on_reject):
    """rules の Reject を ok: False に写す。規則の中の想定外の例外（die の SystemExit を含む）も拒否として返す"""
    try:
        return fn()
    except KeyboardInterrupt:
        raise
    except Reject as e:
        return {"ok": False, "reason": str(e), **on_reject}
    except BaseException as e:
        return {"ok": False, "reason": f"受け付けの中で例外（{type(e).__name__}: {e}）", **on_reject}


# 受け付けの部品の公開の名（ブロックのモジュールの受け付け——premises など——が私的な名前を借りずに使う。層の決まり private）
guard = _guard
in_repo = _in_repo
resolve_rev = _rev
read_board = _read_board
write_board = _write_board
type_errors = _type_errors


def _entry_digest(p: pathlib.Path, racy_after=None, marks=None, *, caches: tuple = ()) -> bytes:
    """未追跡の 1 本の sha256。symlink はリンク先の名前、ファイルは中身、フォルダ（入れ子の git リポジトリは
    git が `sub/` の 1 行で出す）は中の全部の名前と印を名前の順に続けた物（.git の下は除く）。それ以外（FIFO など）は種類だけ。
    marks（1 つの要素の list）を渡すと、ファイルは中身を読まず stat の印（mode・大きさ・mtime_ns・ino。git の index と
    同じ考え——git の Documentation/technical/racy-git.txt）にし、見た mtime_ns の最大を marks[0] に入れる。ただし
    mtime_ns が racy_after より後（写した時刻に近すぎて、同じ大きさの素早い書き換えを印で見分けられない）のファイルは中身も足す。
    caches（_is_test_cache の名の形）に当たるフォルダの中の物は辿らない"""
    if p.is_symlink():
        return hashlib.sha256(b"link\0" + os.fsencode(os.readlink(p))).digest()
    if p.is_file():
        if marks is None:
            return hashlib.sha256(b"file\0" + p.read_bytes()).digest()
        st = p.stat()
        marks[0] = max(marks[0], st.st_mtime_ns)
        h = hashlib.sha256(f"stat\0{st.st_mode} {st.st_size} {st.st_mtime_ns} {st.st_ino}".encode())
        if st.st_mtime_ns > racy_after:
            h.update(b"\0racy\0" + p.read_bytes())
        return h.digest()
    if p.is_dir():
        h = hashlib.sha256(b"dir\0")
        for top, dirs, files in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d != ".git" and not _is_test_cache(d, caches))
            for name in sorted(f for f in files if not _is_test_cache(f, caches)) + \
                    [d for d in dirs if os.path.islink(os.path.join(top, d))]:
                q = pathlib.Path(top) / name
                h.update(os.fsencode(str(q.relative_to(p))) + b"\0" + _entry_digest(q, racy_after, marks))
        return h.digest()
    return hashlib.sha256(b"other\0" if p.exists() else b"gone\0").digest()


def _ignored_digests(repo, names, *, caches: tuple = ()) -> list:
    """git が無視するパス（names）ごとの印（_entry_digest の stat の印。無視されるフォルダ——.venv・node_modules など——は
    大きいので中身を読まない）。写す時刻から RACY_NS 以内に書かれたファイルが在れば、その書き込みから RACY_NS 過ぎるまで
    （上限 RACY_NS）待って印を取り直す。待った後の書き換えは、時刻の細かさ（最大でも 2 秒）を越えて mtime が変わるので、
    印だけで見分けられる。待っても近い物（時計が進んだ mtime）は、racy として中身も足す。caches は _entry_digest と同じ"""
    for attempt in range(2):
        racy_after = time.time_ns() - RACY_NS
        marks = [0]
        digests = [_entry_digest(repo / name.rstrip("/"), racy_after, marks, caches=caches) for name in names]
        if marks[0] <= racy_after or attempt:
            return digests
        time.sleep(min(marks[0] - racy_after, RACY_NS) / 1e9 + 0.01)


def _ignored_entries(repo) -> list:
    """git が無視するパス（repo の根から。名前の順）。git status --porcelain -z --ignored=matching（git-status(1)）の `!!` の行で、
    丸ごと無視されるフォルダ（`__pycache__/`・`.venv/` など）は `dir/` の 1 本に畳まれる"""
    fields = _git(repo, "status", "--porcelain", "-z", "--ignored=matching", "--untracked-files=all", binary=True).split(b"\0")
    out, skip = [], False
    for f in fields:
        if skip or not f:   # 名前の変わった行（X か Y が R・C）は、元の名前がもう 1 つの欄で続く
            skip = False
            continue
        if f[:1] in (b"R", b"C") or f[1:2] in (b"R", b"C"):   # Y が R は intent-to-add を伴う作業ツリーの rename
            skip = True
        elif f.startswith(b"!! ") and not _cli_owned_only(repo, os.fsdecode(f[3:])):
            out.append(os.fsdecode(f[3:]))
    return sorted(out)


def _cli_owned(path: str) -> bool:
    """path（リポジトリの根からの相対。末尾の / は問わない）が Claude Code の控えのフォルダ CLI_OWNED（深さを問わず
    `<どこか>/.claude/.cc-writes`）か、その下か"""
    parts = path.rstrip("/").split("/")
    return any(parts[i:i + len(CLI_OWNED_PARTS)] == list(CLI_OWNED_PARTS) for i in range(len(parts)))


def _cli_owned_only(repo, entry: str) -> bool:
    """entry（_ignored_entries の 1 本）が CLI_OWNED の下か、中身が全部 CLI_OWNED の下のフォルダ（git が `<dir>/.claude/` に
    畳んだ時）か。空の `<dir>/.claude/` も数えない（Claude Code が控えのフォルダを作る時に先に作る親）"""
    if _cli_owned(entry):
        return True
    if not entry.endswith("/"):
        return False
    root = pathlib.Path(repo)
    leaves = [p.relative_to(root).as_posix() for p in (root / entry).rglob("*") if not p.is_dir() or not any(p.iterdir())]
    if not leaves:
        return entry.rstrip("/").split("/")[-1] == CLI_OWNED_PARTS[0]
    return all(_cli_owned(leaf) for leaf in leaves)


# Claude Code（2.1.283）が作る原子的な書き込みの控えのフォルダ（ensureAtomicWriteStagingDirs。sandbox の Bash の cwd・起動の
# cwd・設定の置き場ごとに `<dir>/.claude/.cc-writes/` を 0700 で作り、全体の除外 ~/.config/git/ignore に **/.claude/.cc-writes/
# を足す。中は書き込みの間だけの `<名>.tmp.<16 進 8 字>` で、ふだんは空）。役の書いた物ではないので、作業ツリーの見張りは
# 深さを問わず数えない（台帳 R62: 自分食い 23 件目で根の、run 30 で works/docs/specs/ の下の物で読むだけの役が 3 回拒まれた）。
# 同じ .claude/ の下のほかの物は見る
CLI_OWNED_PARTS = (".claude", ".cc-writes")
CLI_OWNED = "/".join(CLI_OWNED_PARTS) + "/"


def _porcelain_path(line: str) -> str:
    """git status --porcelain の 1 行のパス（改名は後ろの名。引用符は外す）"""
    path = line[3:].split(" -> ")[-1]
    return path[1:-1] if len(path) >= 2 and path[0] == path[-1] == '"' else path


# テストを走らせただけで出来るキャッシュの名の形（fnmatch。パスのどこかの段が当たればキャッシュ）のうち、lib が知る物。読むだけの役が
# 対象のテストを回して作っても、修正でも作業ツリーの変更でもない。ほかのテストの実行器のキャッシュの名は呼び手が足す（judge は
# 入口の節の with: の test_caches。根の AGENTS.md の E13——lib に実行器の名を書かない）
TEST_CACHES = ("__pycache__", "*.pyc")


def _no_test_cache(caches: tuple) -> tuple:
    """git の pathspec で _is_test_cache(·, caches) と同じ物を除く（試験で縛る）。__pycache__ という名のファイルは /** の形では
    除けず、中身は /** の無い形では除けないので両方要る"""
    return (":(top)", *(f":(top,exclude,glob)**/{c}{tail}" for c in caches for tail in ("", "/**")))


def snapshot_tree(repo: pathlib.Path, *, caches: tuple = ()) -> dict:
    """作業ツリーの写し {"porcelain": str, "ignored": [str], "diff_sha256": str}。tree_state がこれに HEAD・枝を足し、
    読むだけの役を起こす前後に比べる（判定役を起こす前に盤面に写しが無い時は、judge_accept._judge_tree_unchanged が今の写しで作業ツリーが綺麗かを見る）。
    porcelain は git status --porcelain（未追跡は 1 本ずつ）。porcelain と差分は本物の index の印を外して見る（flag_free_env。
    touched_files と同じ見え方: assume-unchanged・skip-worktree の印の付いたファイルの編集も見え、sparse checkout の範囲外は消したと見ない）。ignored は git が無視するパス（_ignored_entries。
    差分には載らないが、後の節——テスト——の緑赤を左右する物も在るので、読むだけの役が足しても見逃さない）。
    diff_sha256 は HEAD からの差分（--binary）と、未追跡のファイルの名前と中身・無視されるパスの名前と stat の印
    （_ignored_digests。中身は読まない）を続けた sha256——名前が同じまま中身だけ変わっても違う値になる。フォルダ（入れ子の
    git リポジトリ・無視されるフォルダ）は中を辿って続ける（_entry_digest）。git が効かなければ Reject を投げる。
    caches（テストのキャッシュの名の形。_is_test_cache）に当たる物を porcelain・差分・未追跡・無視されるパスと、それらのフォルダの
    中から除く（測るために試験を走らせる役が作る物を変化に数えない）。空なら何も除かない"""
    repo = pathlib.Path(repo)
    with flag_free_env(repo) as env:
        porcelain = _git(repo, "status", "--porcelain", "--untracked-files=all", env=env)
        diff = _git(repo, "diff", "--binary", "--no-ext-diff", "HEAD", *(("--", *_no_test_cache(caches)) if caches else ()),
                    binary=True, env=env)
    porcelain = "".join(f"{ln}\n" for ln in porcelain.splitlines()
                        if not (ln.startswith("?? ") and _cli_owned(_porcelain_path(ln)))
                        and not _is_test_cache(_porcelain_path(ln), caches))
    h = hashlib.sha256(diff)
    for name in sorted(n for n in _git(repo, "ls-files", "--others", "--exclude-standard", "-z", binary=True).split(b"\0") if n):
        if _is_test_cache(os.fsdecode(name), caches) or _cli_owned(os.fsdecode(name)):
            continue
        p = repo / os.fsdecode(name).rstrip("/")
        h.update(b"\0untracked\0" + name + b"\0" + _entry_digest(p, caches=caches))
    ignored = [n for n in _ignored_entries(repo) if not _is_test_cache(n, caches)]
    for name, digest in zip(ignored, _ignored_digests(repo, ignored, caches=caches)):
        h.update(b"\0ignored\0" + os.fsencode(name) + b"\0" + digest)
    return {"porcelain": porcelain, "ignored": ignored, "diff_sha256": h.hexdigest()}


TREE_KEYS = ("porcelain", "diff_sha256", "ignored", "head", "ref")
# 節の前後の git status の行の違いを実行基盤が別に照らす役（状態の照らしで守られた役）の受け付けが比べる欄。porcelain はその照らしと
# 重なるので外す。diff_sha256 は外さない: 行の字が同じままの、既に変わっていたファイルの 2 度目の書き換えを照らしは見ない
BEYOND_STATUS = tuple(k for k in TREE_KEYS if k != "porcelain")
TREE_SCHEMA = {"type": "object", "required": list(TREE_KEYS), "properties": {
    **SNAPSHOT_SCHEMA["properties"], "head": {"type": "string"}, "ref": {"type": "string"}}}


def status_keys(guarded) -> tuple:
    """受け付けが比べる欄: guarded（グラフが受け付けの節に渡す印。真か字の true）なら BEYOND_STATUS、ほかは TREE_KEYS"""
    return BEYOND_STATUS if guarded is True or str(guarded).strip().lower() == "true" else TREE_KEYS


def tree_state(repo: pathlib.Path, *, caches: tuple = ()) -> dict:
    """読むだけの役（blk-pr の並行 PR・blk-ci の CI・entry.take と rejudge.take が受ける役）を起こす前後に比べる作業ツリーの姿 {TREE_KEYS}:
    snapshot_tree（porcelain・git が無視するパスの一覧 ignored・diff_sha256。無視されるパスの stat の印も diff_sha256 に入る——
    無視されるファイルは差分に載らないが、後の節のテストの緑赤を左右しうる）に、HEAD の sha head・枝 ref
    （symbolic-ref。切り離した HEAD は空）を足した物。snapshot_tree は今の HEAD からの差分しか見ないので、枝の切り替え
    （gh pr checkout・git checkout）は head・ref で見る。HEAD が引けない・git が効かなければ Reject。caches は snapshot_tree と同じ"""
    repo = pathlib.Path(repo)
    try:
        head = _git(repo, "rev-parse", "--verify", "-q", "HEAD").strip()
    except Reject:
        raise Reject(f"git rev-parse HEAD が引けない（{repo}）") from None
    try:
        ref = _git(repo, "symbolic-ref", "-q", "HEAD").strip()
    except Reject:   # 切り離した HEAD（symbolic-ref -q は 1 で終わる）
        ref = ""
    return {**snapshot_tree(repo, caches=caches), "head": head, "ref": ref}


def tree_change(before: dict, now: dict, keys=TREE_KEYS) -> list:
    """tree_state（keys を SNAPSHOT_KEYS にすれば snapshot_tree）の 2 つの違いを人に向けた文の一覧で（同じなら空）。keys の欄だけを
    比べる。porcelain は違う時だけ頭の 5 行、head・ref は前と今、ignored は増えた・消えたパスの頭の 5 本。diff_sha256 が違えば
    （porcelain の行が同じままの中身の書き換えも）その 1 行を足す"""
    if all(before.get(k) == now.get(k) for k in keys):
        return []
    out = []
    if "porcelain" in keys and before["porcelain"] != now["porcelain"]:
        out.append(f"git status --porcelain: 役を起こす前 {before['porcelain'].splitlines()[:5]} / 今 {now['porcelain'].splitlines()[:5]}")
    for k in ("head", "ref"):
        if k in keys and before[k] != now[k]:
            out.append(f"{k}: 役を起こす前 {before[k] or '（切り離した HEAD）'} / 今 {now[k] or '（切り離した HEAD）'}")
    if "ignored" in keys:
        added = sorted(set(now["ignored"]) - set(before["ignored"]))
        gone = sorted(set(before["ignored"]) - set(now["ignored"]))
        if added or gone:
            out.append(f"git が無視するパス: 増えた {added[:5]} 消えた {gone[:5]}")
    if "diff_sha256" in keys and before["diff_sha256"] != now["diff_sha256"]:
        out.append("HEAD からの差分・未追跡のファイル・git が無視するパスのどれかの中身が変わった（diff_sha256）")
    return out


def tree_moved(before: dict, repo: pathlib.Path, *, caches: tuple = (), keys=TREE_KEYS) -> list:
    """役を起こす前の姿 before（tree_state）と今の作業ツリーの違いの文（tree_change。keys の欄だけを比べる）。今の姿が引けない
    （HEAD が無い・git が効かない）ときはその 1 行——起こす前は引けたので、役が HEAD を動かした（checkout --orphan など）。
    caches は before を取った時と同じ値を渡す"""
    try:
        now = tree_state(repo, caches=caches)
    except Reject as e:
        return [f"作業ツリー・HEAD が引けなくなった: {e}"]
    return tree_change(before, now, keys)


def _names(repo, cmd, *args, env=None) -> list:
    """git <cmd> -z <args> が出すパスの一覧（NUL 区切り。日本語などの名前も引用符や \\ の書き換え無しでそのまま）"""
    return [os.fsdecode(n) for n in _git(repo, cmd, "-z", *args, binary=True, env=env).split(b"\0") if n]


def _marks(repo, env=None) -> tuple:
    """index（env の GIT_INDEX_FILE。無ければ本物）で外す印の付いたパス（バイト）: (assume-unchanged の物, skip-worktree の物)。
    skip-worktree は作業ツリーに実物が在る物だけ——実物の無い物は sparse checkout の範囲外の普通の姿で、印を外すと
    消した物に見える（git add -A も範囲外を消さない。green_cert.fresh_tree と同じ見え方）"""
    assumed, skipped = [], []
    for rec in _git(repo, "ls-files", "-v", "-z", binary=True, env=env).split(b"\0"):
        tag, path = rec[:1], rec[2:]
        if tag.islower():
            assumed.append(path)
        if tag in (b"S", b"s") and os.path.lexists(os.path.join(repo, os.fsdecode(path))):
            skipped.append(path)
    return assumed, skipped


def clear_marks(repo, env) -> None:
    """env の GIT_INDEX_FILE が指す index（本物の index の写し）から印を外す（外す物は _marks）"""
    for flag, paths in zip(("--no-assume-unchanged", "--no-skip-worktree"), _marks(repo, env)):
        if paths:
            _git(repo, "update-index", "-z", flag, "--stdin", env=env, stdin=b"\0".join(paths) + b"\0")


def copy_flag_free_index(repo, index) -> None:
    """本物の index を index（パス）に写し、写しの印を外す（clear_marks）。本物の index が無ければ（まだ何も add していない
    リポジトリ）写さない。本物の index は読むだけ。git が効かなければ Reject"""
    real = _git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index").strip()
    try:
        shutil.copy2(real, index)
    except FileNotFoundError:
        return
    except OSError as e:
        raise Reject(f"本物の index を写せない: {e}")
    clear_marks(repo, {"GIT_INDEX_FILE": str(index)})


@contextlib.contextmanager
def flag_free_env(repo):
    """git に渡す env の差分。本物の index の印（_marks）を外して作業ツリーを見せる
    （外す印が在る時だけ、印を外した写しの一時の index を指す。本物の index は触らない）"""
    if not any(_marks(repo)):
        yield {}
        return
    with tempfile.TemporaryDirectory(prefix="works-touched-") as tmp:
        index = os.path.join(tmp, "index")
        copy_flag_free_index(repo, index)
        yield {"GIT_INDEX_FILE": index}


def _is_test_cache(name: str, caches: tuple = TEST_CACHES) -> bool:
    """パス name のどこかの段がテストのキャッシュの名の形 caches（fnmatch）に当たるか。テストを走らせただけで出来る物で、修正ではない"""
    return any(fnmatch.fnmatchcase(part, c) for part in name.rstrip("/").split("/") for c in caches)


def _touched(repo, rev) -> tuple:
    """(追跡しているファイルで rev から変わった物, 未追跡のファイル)。どちらもテストのキャッシュを除き、名前の順"""
    with flag_free_env(repo) as env:
        tracked = _names(repo, "diff", "--name-only", "--no-renames", rev, env=env)
    untracked = _names(repo, "ls-files", "--others", "--exclude-standard", "--full-name", "--", ":/")
    return (sorted(n for n in set(tracked) if not _is_test_cache(n)),
            sorted(n for n in set(untracked) if not _is_test_cache(n)))


def touched_files(repo: pathlib.Path, rev: str) -> list:
    """修正が触ったファイル（repo の根からのパス、名前の順）。git diff --name-only <rev> と未追跡のファイル
    （入れ子の git リポジトリは `sub/` の 1 本）。本物の index の assume-unchanged・skip-worktree の印を付けた物も挙げる
    （flag_free_env）。テストのキャッシュ（_is_test_cache）は除く"""
    tracked, untracked = _touched(repo, rev)
    return sorted(set(tracked) | set(untracked))
