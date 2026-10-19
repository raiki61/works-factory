"""入口の変換（考え entry-kind の住処の core の側。層 L3）。入口の生の入力を 1 つの入力の形に揃える。

持ち主の決め（2026-10-09）: 「依頼と変更と PR と抽象化するとやることは同じはず…どの入り口でも最終的に環境変数に何をセットするの
かだけ」。入口の種類（依頼のファイルだけ・差分の根 base・PR）を知るのは、生の事実を集める殻（dev/use.sh・dev/dogfood.sh）と、
線の最初のブロックである入口のブロック（起動の関所と節 open）だけで、その節 open の中身（core の entry.start）が入口の種類に
触れる所はこのモジュールに集める。ほかのモジュール・ブロック・境の節は、ここが作る入力の形（欄 input。約束は入口のブロックの
schemas/input.schema.json）の中身——差分が空か・依頼の行の数・PR の添え物・仕様の段を挟むか——だけを読み、入口の種類を見ない
（表 docs/concepts.json の柵 entry-kind が、入口の種類の語を読む所をこのモジュールとメイングラフの start に縛る。試験は
lib/tests/test_concept_fences.py と tests/layers/test_concept_fences.py）。
計画 docs/plans/2026-10-09-one-entry-shape.md の 2 節。

- Refused: 入口の入力を受けない（呼び手 entry が InputRefused にする。1 行）
- named_pr(raw): 入力 pr が名指した PR の番号（無ければ None）。線の入口と周の鎖の始めが同じ読みを使う
- change_base(raw, repo, reads): 差分の根を名指す生の入力（base・pr）を {base_rev, base: {rev, from, name, label}, pr} に解く
- refuse_empty(items, change, repo): 依頼の行が空で差分も空なら拒む（EMPTY_REFUSED）
- build(inp, repo): 入口の入力の形 {base, head_rev, diff, requests, request_file, pr, spec}
- request_text(inp): 盤面の依頼の文（依頼のファイルの文と PR の題・本文の在る物を並べる）
- github_reads(board_dir, repo, raw): 入口が名指した PR・issue を run の中で gh で読んだ読み出し（再開では盤面の github.json）
- write_pr_file(board_dir, inp): PR の添え物（番号・題・本文）を盤面の根の PR_FILE に置いてパスを返す（PR の無い run は ""）。
  目的の役が出典 ① PR 説明として読む（線が出口の pr_file を渡す）
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import carry  # noqa: E402  （依頼の容器の形 parts）
import ghreads  # noqa: E402  （run の中の gh の読み出し・盤面の github.json）
import oneline  # noqa: E402
import engine.util as _util  # noqa: E402
from engine.util import Reject, git  # noqa: E402

EMPTY_REFUSED = "直す物も審査する物も無い"   # 差分が空で依頼の行も空の入力を拒む文の頭
# 認証の要らない起動（起動の殻 bin/works-factory を WORKS_FACTORY_NO_AUTH=1 で起こした run。bin/_lib/launcher.py・auth_launch.py が
# 同じ名を読む）の印。この run の中の gh は利用者の gh のログインを継がないので、名指した PR・issue を読めない
NO_AUTH_ENV = "WORKS_FACTORY_NO_AUTH"
PR_FILE = "pr.md"   # 盤面の根の PR の添え物（番号・題・本文。PR の無い run は置かない）


class Refused(Exception):
    """入口の入力を受けない（文は 1 行）"""


def _word(raw: dict, key: str) -> str:
    v = raw.get(key)
    return "" if v is None else str(v).strip()


def named_pr(raw: dict):
    """入力 pr が名指した PR の番号（前後の空白は除く）。空か番号でなければ None"""
    pr = _word(raw, "pr")
    return int(pr) if pr.isdigit() else None


def _git(repo: pathlib.Path, *args) -> str:
    """repo で git を読むだけ呼ぶ。引けなければ Refused（1 行）"""
    got = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
    if got.returncode != 0:
        raise Refused(f"git {' '.join(args)} が引けない: {got.stderr.strip() or got.returncode}")
    return got.stdout.strip()


def merge_base(repo: pathlib.Path, ref: str) -> str:
    """ref と HEAD の merge-base（GitHub の PR の three-dot と同じ差分の根）"""
    rev = _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return _git(repo, "merge-base", rev, "HEAD")


def change_base(raw: dict, repo: pathlib.Path, reads=None):
    """差分の根を名指す生の入力（base か pr）を解いて {base_rev, base: {rev, from, name, label}, pr: {number, title, body} | None}
    を返す。どちらも無ければ None（差分の根は HEAD。build が埋める）。両方は拒む。base.from は誰が根を決めたかの名札（base・pr）、
    label は頭の行に書く出どころの文で、後ろの段は分岐に使わない。
    pr は gh を呼ばず、start が run の中で読んだ読み出し reads（ghreads.read_named の返りか、再開では盤面の github.json）の
    pr[<番号>] を読む（設計書 2.8）。読み出しに無い・読めなかった項・head が今の HEAD と違えば拒む（別の版を
    黙って見ない）。差分の根は GitHub が持つ base の版（baseRefOid）と HEAD の merge-base——fetch しないローカルの枝は古いことが
    あるので名前では引かない。pr の題と本文は添え物（request_text が盤面の依頼の文に並べる）"""
    base, pr = _word(raw, "base"), _word(raw, "pr")
    if base and pr:
        raise Refused(f"base={base!r} と pr={pr!r} を両方名指した——どちらの差分か決まらない（片方だけ）")
    if base:
        rev = merge_base(repo, base)
        return {"base_rev": rev, "base": {"rev": rev, "from": "base", "name": base, "label": f"base {base}"}, "pr": None}
    if not pr:
        return None
    if named_pr(raw) is None:
        raise Refused(f"pr={pr!r} は PR の番号でない")
    doc = ((reads or {}).get("pr") or {}).get(pr)
    if not isinstance(doc, dict) or not doc.get("baseRefOid") or not doc.get("headRefOid"):
        why = oneline.one_line((doc.get("reason") if isinstance(doc, dict) else "") or "読み出しにこの PR の base・head が無い")
        if isinstance(doc, dict) and doc.get("status") == ghreads.NOT_APPLICABLE:   # forge の無い対象で gh も GitHub を見つけなかった
            raise Refused(f"PR #{pr} の base・head を読めない——対象の remote に PR を持つホストが無い（{why}）。base を名指して回す")
        raise Refused(f"PR #{pr} の base・head を読めない（{why}）——利用者の gh でログインしてから回す")
    head = _git(repo, "rev-parse", "HEAD")
    if doc["headRefOid"] != head:
        raise Refused(f"PR #{pr} の head {doc['headRefOid'][:12]} が対象の HEAD {head[:12]} と違う——PR の head を"
                      "取り出した所で始める")
    oid = doc["baseRefOid"]
    if subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{oid}^{{commit}}"], capture_output=True).returncode:
        raise Refused(f"PR #{pr} の base の版 {oid[:12]} が対象に無い——fetch してから始める")
    rev = merge_base(repo, oid)
    title = str(doc.get("title") or "").strip()
    return {"base_rev": rev,
            "base": {"rev": rev, "from": "pr", "name": pr, "label": f"PR #{pr}「{title}」" if title else f"PR #{pr}"},
            "pr": {"number": pr, "title": title, "body": str(doc.get("body") or "").strip()}}


def measure(repo: pathlib.Path, base_rev: str) -> dict:
    """差分の根 base_rev から作業ツリーの今の姿までの測り（diff_of。Reject は Refused）"""
    try:
        return diff_of(repo, base_rev)
    except Reject as e:
        raise Refused(f"差分を測れない: {e}") from None


def refuse_empty(items: list, change, repo: pathlib.Path) -> None:
    """依頼の行が空で、差分の根（名指しが無ければ HEAD）から作業ツリーまでの差分も空なら Refused（EMPTY_REFUSED で始まる 1 行）。
    依頼の行が在れば git を測らない（盤面を作る前・CI の前に止める）"""
    if items:
        return
    if measure(repo, change["base_rev"] if change else _git(repo, "rev-parse", "HEAD"))["empty"]:
        raise Refused(f"{EMPTY_REFUSED}——依頼（request）を名指すか、差分の在る base・PR を名指す（差分の根から作業ツリーまでが空で、"
                      "依頼の行も無い）")


def build(inp: dict, repo: pathlib.Path) -> dict:
    """入口の節（start）が確かめた入力 inp から、入口の入力の形（始めの記録の欄 input。約束は docs/design.md の線の start の record）を作る:
    {base: {rev, from, name, label}, head_rev, diff: {empty, files, stat}, requests, request_file, pr: {number, title, body} | None,
    spec}。base は差分の根（名指しが無ければ HEAD・from head）、diff は差分の根から作業ツリーの今の姿までの測り（diff_of）、
    requests は依頼の行の数、pr は PR の番号と題と本文（目的の役が出典 ① PR 説明として読む。元は盤面の根の pr.md を線が
    渡した: works/darkfactory/darkfactory.yaml 297 行）、spec は仕様の段を挟むか。後ろの段（盤面・ブロック・境の節・報告）はこの形の中身（diff.empty・requests・pr・spec）だけを読み、入口の種類を見ない"""
    repo = pathlib.Path(repo)
    head = _git(repo, "rev-parse", "HEAD")
    base = inp.get("base") or {"rev": head, "from": "head", "name": "", "label": "HEAD"}
    pr = inp.get("pr")
    return {"base": dict(base), "head_rev": head, "diff": measure(repo, base["rev"]), "requests": len(inp["items"]),
            "request_file": inp["request_file"], "pr": {"number": pr["number"], "title": pr["title"], "body": pr["body"]} if pr else None,
            "spec": bool(inp.get("spec"))}


REQUEST_HEAD = "## 依頼"
PR_TEXT_HEAD = "## PR #{number} の題と本文"
PR_TITLE = "# PR #{number}"
PR_SUBJECT_HEAD = "## 題"
PR_BODY_HEAD = "## 本文"


def request_text(inp: dict) -> str:
    """盤面の依頼の文（DiskBoard.begin の request_text。固定材料の依頼の sha256 もこの文で照らす）。依頼のファイルの文と PR の題・
    本文の在る物を並べる: 両方なら見出し「## 依頼」「## PR #N の題と本文」つき、片方だけならその文のまま（固定材料の sha256 を
    変えない）、どちらも無ければ差分の審査の 1 行"""
    pr = inp.get("pr")
    pr_text = "\n\n".join(x for x in (pr["title"], pr["body"]) if x) if pr else ""
    req = inp["request_text"]
    if req and pr_text:
        return f"{REQUEST_HEAD}\n\n{req.strip()}\n\n{PR_TEXT_HEAD.format(number=pr['number'])}\n\n{pr_text}\n"
    if req or pr_text:
        return req or pr_text
    base = inp.get("base") or {"label": "HEAD"}
    return f"変更（{base['label']}）の審査"


def named(raw: dict, repo: pathlib.Path):
    """入力 pr と依頼の欄 pr・issue が名指した (PR の番号の並び, issue の番号の並び)。依頼が読めない・形の外なら依頼の分は
    無しにする（形の誤りは入口の節（start）が拒む）"""
    pr = named_pr(raw)
    prs, issues = ([] if pr is None else [pr]), []
    rel = _word(raw, "request")
    if rel:
        path = pathlib.Path(rel) if pathlib.Path(rel).is_absolute() else repo / rel
        try:
            parts = carry.parts(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, ValueError):
            return prs, issues
        prs, issues = list(dict.fromkeys(parts[carry.PR] + prs)), list(parts[carry.ISSUE])
    return prs, issues


def github_reads(board_dir: pathlib.Path, repo: pathlib.Path, raw: dict):
    """名指した PR・issue を run の中で gh で読んだ読み出し（ghreads.read_named。読めない項も記録して返す）。名指しが無ければ
    None。盤面の根に github.json が在れば（実行基盤の再開）それを使い、読み直さない（run の中で同じ版を見る）。
    認証の要らない起動（NO_AUTH_ENV）で名指せば、gh を呼ばずに 1 行で拒む（読めないと黙って記録しない）"""
    try:
        kept = ghreads.load_board(board_dir)
    except (OSError, ValueError) as e:
        raise Refused(f"共有ボードの {ghreads.BOARD_FILE} を読めない（{type(e).__name__}: {e}）") from None
    if kept is not None:
        return kept
    prs, issues = named(raw, repo)
    if not prs and not issues:
        return None
    if os.environ.get(NO_AUTH_ENV) == "1":
        names = "・".join([f"PR #{n}" for n in prs] + [f"issue #{n}" for n in issues])
        raise Refused(f"{names} を名指したが、この run は {NO_AUTH_ENV}=1 で起こしたので run の中の gh が利用者のログインを"
                      "継がず読めない——認証を使う起動（bin/works-factory を WORKS_FACTORY_NO_AUTH なしで起こす）で回す")
    return ghreads.read_named(repo, prs, issues)


def write_pr_file(board_dir: pathlib.Path, inp: dict) -> str:
    """PR の添え物（inp["pr"] の番号・題・本文）を盤面の根の PR_FILE に 0600 で置き（PR の本文は非公開でありうる。github.json と
    同じ扱い）、パスを返す。PR の無い run は置かずに ""。呼び直しは書き直す（中身は同じ読み出しから作るので同じ）"""
    pr = inp.get("pr")
    if not pr:
        return ""
    path = pathlib.Path(board_dir) / PR_FILE
    text = (f"{PR_TITLE.format(number=pr['number'])}\n\n{PR_SUBJECT_HEAD}\n\n{pr['title'] or '（空）'}\n\n"
            f"{PR_BODY_HEAD}\n\n{pr['body'] or '（空）'}\n")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o600)
    return str(path)


# 元 works/.shared/core/board.py 554-581 行（盤面を開かない関数が盤面のファイルに住んでいた）
def diff_of(repo, base_rev: str) -> dict:
    """差分の根 base_rev から作業ツリーの今の姿までの測り {empty, files, stat}（入口の入力の形の diff。entry.build_input と
    entry.check_inputs の拒みが読む）。作業ツリーの姿は写しの RL の _worktree_tree（未追跡の新規ファイルも含め、.gitignore の
    対象は除く）を util.GIT_CWD=repo で呼んだ木で、版を固める p1.worktree_before と同じ測り方（start の測りと空差分の柵の
    測りが食い違わない）。木が base_rev の木と同じなら空。違えば git diff --numstat で数え、stat は --shortstat の 1 行。
    GIT_CWD は呼ぶ前の値に戻す。木が引けない・base_rev が commit に引けなければ Reject"""
    repo = pathlib.Path(repo)

    def git(*args):
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else None

    base_tree = git("rev-parse", "--verify", "--quiet", "--end-of-options", f"{base_rev}^{{tree}}")
    if not base_tree:
        raise Reject(f"差分の根 '{base_rev}' がリポジトリ {repo} の commit に引けない（git rev-parse --verify）")
    old = _util.GIT_CWD
    _util.GIT_CWD = str(repo)
    try:
        tree = _worktree_tree()
    finally:
        _util.GIT_CWD = old
    if tree == base_tree:
        return {"empty": True, "files": 0, "stat": ""}
    numstat = git("diff", "--numstat", base_tree, tree)
    stat = git("diff", "--shortstat", base_tree, tree)
    if numstat is None or stat is None:
        raise Reject(f"差分の根 '{base_rev}' から作業ツリーの木 {tree[:12]} までを git diff で数えられない（リポジトリ {repo}）")
    return {"empty": False, "files": len([x for x in numstat.splitlines() if x.strip()]), "stat": stat}


# 元 works/.shared/core/graphloops/rules/review-loop.py 1501-1532 行（写しの規則の _worktree_tree）
def _worktree_tree():
    """作業ツリーの今の姿の木の id（未追跡の新規ファイルも含め、追跡していない .gitignore の対象は除く）。固められなければ Reject。
    中身が同じなら id も同じなので、前後の突合はこの id を比べるだけで済む。

    **本物の index を一時 index に写してから** `add -A` する。空の一時 index から始めていたとき、追跡中だが .gitignore に
    当たるファイルは `add -A` に拾われず、版から落ちて『削除』に見えた（実測 2026-09-25: 別のリポジトリの run で、判定役が
    これを根拠に誤った [block] を出した）。写しは stat の情報も持つので、`add -A` は変わったファイルだけをハッシュする。
    写しの上で `--really-refresh` を打つのは assume-unchanged の印を外すため——印を持ったままだと、git はそのファイルを
    見ずに古い中身で版を作る。本物の index は読むだけで書かない"""
    tmp = tempfile.mkdtemp(prefix="graphloops-index-")
    idx = pathlib.Path(tmp) / "index"
    env = {"GIT_INDEX_FILE": str(idx)}
    why = []   # git が言った失敗の理由（util.git の why）。止める文に添える
    try:
        real = git("rev-parse", "--path-format=absolute", "--git-path", "index", why=why)
        if real is None or not real.strip():
            raise _unfrozen("本物の index の場所を git rev-parse --git-path で引けない", why,
                            "git 2.31 以上か、リポジトリの中で呼んでいるかを確かめよ")
        try:
            shutil.copy2(real.strip(), idx)   # 時刻ごと写す——index の時刻が新しくなると、同じ秒に書き換えたファイル（racy git）を綺麗と見誤る
        except FileNotFoundError:
            pass   # index がまだ無い（init の直後で 1 度も add していない）＝追跡中のファイルが無いので、空から始めて落ちる物が無い
        except OSError as e:
            raise Reject(f"この周に採点する版を固定できない（本物の index を写せない: {e}）")
        if git("update-index", "-q", "--really-refresh", env=env, why=why) is None or git("add", "-A", env=env, why=why) is None:
            raise _unfrozen("一時 index への git update-index / add -A が失敗した", why)
        tree = git("write-tree", env=env, why=why)
        if tree is None or not tree.strip():
            raise _unfrozen("git write-tree が木を返さない", why)
        return tree.strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# 元 works/.shared/core/graphloops/rules/review-loop.py 1535-1539 行
def _unfrozen(what, why, hint=None):
    """版を固定できない回の Reject。**git が言った理由を必ず添える**——添えなかったとき、止まった利用者は原因
    （壊れた object・書けない置き場・git の版）を文から読めず、git を手で打ち直すしかなかった"""
    said = " / ".join(w for w in why if w) or "git は理由を返さなかった"
    return Reject(f"この周に採点する版を固定できない（{what}。git の言い分: {said}）" + (f"——{hint}" if hint else ""))

