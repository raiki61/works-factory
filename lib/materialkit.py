"""素材の観点の族の共通の部品（docs/design/materials.md の 2 節）。

判定の前に集める素材の観点 11 本の block（workflows/<観点>/）が共に使う。観点の block は src/viewpoint.py の宣言（名・素材の名・回す
条件・『条件に当たらない』の扱い・指示の値・返答から素材への写し・観点だけの受け付け）だけを持ち、対象差分の取り方・作業ツリーの写しと
照らし・所見の場所の照らし・素材の欄の照らし・受け付けの流れ・出口はここに置く。中身は lib/judge_accept.py の material_* の写しで
（各関数の docstring に写す元）、置き場は呼び手が渡す place のフォルダだけ。lib/judge_accept.py は import しない。

公開の名:
- 定数: INTAKE・VIEW・DIFF・CHANGED・TREE・ACCEPTED・MATERIAL（place のファイルの名）・STATUSES・OK_STATUSES・
  Rule・STATUS・SILENT_STATUS・UNMEASURED・OBSERVED_STATUS・MATERIALS・READONLY_MOVED・LOCATION_HEAD・LOCATION_MARK・SNAPSHOT_FALLBACK_IDENT・
  NA_MODES・REVIEW_MD
- View・take_view・numstat_totals・worktree_tree・snapshot（対象差分の見方）
- snap_tree・moved_since（作業ツリーの写しと照らし）
- where_rows・location_problems・location_gap（所見の場所の照らし）
- Due・entry_skip・normal_run・not_entry_due・fill_entry・fill_na・fill_not_run・fill_problems・intake（回すかの決めと、回さない時の埋め）
- na_mode（『条件に当たらない』の扱い）
- check_record・material_from_findings（素材の欄の照らし）
- accept（受け付け）
- finish・report_lines・read・assemble（出口と読み手の口）
- prompt_inputs（指示の値の共通の口）
- review_md_paths（観点の正本の置き場）
"""
from __future__ import annotations

import collections
import dataclasses
import json
import os
import pathlib
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True

_GL = pathlib.Path(__file__).resolve().parent / "graphloops"
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

import accept as core_accept  # noqa: E402  （lib/accept。このモジュールに受け付けの関数 accept が在るので別名で読む）
import cite  # noqa: E402
import jsonfile  # noqa: E402
import oneline  # noqa: E402
import rolekit  # noqa: E402
from engine.util import Reject, git  # noqa: E402

# ---------------------------------------------------------------- 2.1 定数
INTAKE = "intake.json"
VIEW = "view.json"
DIFF = "diff.patch"
CHANGED = "changed-files.txt"
TREE = core_accept.TREE   # 作業ツリーの写しのファイルの名（住処は accept）
ACCEPTED = "accepted.json"
MATERIAL = "material.json"
STATUSES = ("ran", "skipped", "gave_up", "failed")
OK_STATUSES = ("ran", "skipped")
NA_MODES = ("never", "cond_true", "cond_false", "judged")
REVIEW_MD = "REVIEW.md"

# 写す元 lib/judge_accept.py の Rule・STATUS（元 works/.shared/core/scripts/review-record.py:140。表の字は元のまま）
Rule = collections.namedtuple("Rule", "fields blocks carryable observed")
STATUS = {name: Rule(*args) for name, args in {
    "found": (("count", "detail"), False, True, True),
    "clean": (("checked",), False, True, True),
    "carried_over": (("from_round", "reason"), False, True, False),
    "not_applicable": (("reason",), False, False, False),
    "awaiting_human": (("reason",), True, False, False),
    "not_run": (("reason",), True, False, False),
}.items()}
SILENT_STATUS = tuple(k for k, r in STATUS.items() if not r.observed and not r.blocks)
UNMEASURED = tuple(k for k, r in STATUS.items() if r.blocks)   # 今の周に測れていない状態（阻害になる物。gatemarks の写しの代わり。integration.md 4.2-5）
OBSERVED_STATUS = tuple(k for k, r in STATUS.items() if r.observed)
# 写す元 lib/judge_accept.py の MATERIALS（元 review-record.py:107）
MATERIALS = (
    "base_determination",  # BASE をどの規則で決めたか（P0-1）
    "local_checks",  # CI のテスト・lint のローカル実行（P0-2）
    "parallel_pr",  # 並行 PR 衝突チェック（P0-5）
    "prior_decisions",  # 先行議論の突合（P0-6）——決着済み論点の蒸し返し防止
    "local_review",  # 局所レビュー（公式 skill）
    "consistency",
    "bypass",  # 標準機構の迂回
    "hygiene",  # コード衛生（文脈遮断）
    "external_standards",  # 外部標準照合＋手元の依存
    "procedure_trace",  # 手順トレース
    "gate_efficacy",  # 新設ゲートの赤の確認
    "test_double_fidelity",  # 代役の忠実性
    "main_path_observation",  # 主経路の実行観測
    "provenance",  # 根拠の出所検査
    "fix_closure",  # 修正の閉鎖実証（P3）——直したと書くだけでなく閉じたことを確かめたか
)
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "   # 元 material.py:175
LOCATION_HEAD = "所見の場所の行がファイルに無い（差分の行番号を書いていないか。作業ツリーのファイルの行で書き直せ）"   # 元 material.py:164
LOCATION_MARK = "（works の受け付け: この行はファイルに無い——差分の行番号の疑い）"   # 元 material.py:165
SNAPSHOT_FALLBACK_IDENT = {"GIT_AUTHOR_NAME": "graphloops", "GIT_AUTHOR_EMAIL": "graphloops@localhost",
                           "GIT_COMMITTER_NAME": "graphloops", "GIT_COMMITTER_EMAIL": "graphloops@localhost"}   # 元 rules:1546


def _read(path):
    """path の JSON。無ければ None。読めない・JSON でなければ ValueError（壊れた控えを黙って空にしない）"""
    p = pathlib.Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"{p} が読めない（{type(e).__name__}: {e}）") from None


def _write(path, doc) -> pathlib.Path:
    return jsonfile.write(path, doc, parents=True)


def review_md_paths(repo, own_file) -> tuple:
    """写す元 judge_accept.review_md_paths（元 rules:35）。(工場の観点の正本 own_file の絶対パス, 対象の根の REVIEW.md の絶対パスか "")。
    工場の正本は workflows/.shared/prompts/REVIEW.md で、lib は block の置き場を名指せないので呼び手の block がパスを渡す
    （README 9.3。前は lib/REVIEW.md を lib の中から引いた）。対象の根の REVIEW.md は在る時だけ"""
    own = pathlib.Path(own_file).resolve()
    theirs = pathlib.Path(repo).resolve() / REVIEW_MD
    return str(own), (str(theirs) if theirs.is_file() else "")


# ---------------------------------------------------------------- 2.2・2.3 対象差分の見方
@dataclasses.dataclass(frozen=True)
class View:
    """対象差分の見方（view.json）。base は引いた commit、review_rev は作業ツリーの今の姿を固めた commit"""
    repo: pathlib.Path
    base: str
    review_rev: str
    diff_file: str
    changed_files: tuple
    changed_files_file: str
    stat: str
    commits: int

    @property
    def empty(self) -> bool:
        return not self.changed_files

    def as_dict(self) -> dict:
        return {"repo": str(self.repo), "base": self.base, "review_rev": self.review_rev, "diff_file": self.diff_file,
                "changed_files": list(self.changed_files), "changed_files_file": self.changed_files_file, "stat": self.stat,
                "commits": self.commits}

    @classmethod
    def from_dict(cls, repo, doc: dict) -> "View":
        return cls(repo=pathlib.Path(repo), base=doc["base"], review_rev=doc["review_rev"], diff_file=doc["diff_file"],
                   changed_files=tuple(doc["changed_files"]), changed_files_file=doc["changed_files_file"], stat=doc["stat"],
                   commits=int(doc["commits"]))


def numstat_totals(text):
    """写す元 judge_accept.numstat_totals（元 rules:1356）。`git diff --numstat` の出力から（ファイル名の並び・追加行・削除行・行の数）"""
    if "\0" in text:
        rows, i = [], 0
        parts = text.split("\0")
        while i < len(parts):
            head = parts[i]
            if not head.strip():
                i += 1
                continue
            cols = head.split("\t")
            if len(cols) == 3 and cols[2] == "":      # 改名: ins \t dels \t "" \0 old \0 new
                if i + 2 >= len(parts):
                    break
                rows.append([cols[0], cols[1], parts[i + 2]])
                i += 3
            else:
                rows.append(cols)
                i += 1
    else:
        rows = [ln.split("\t") for ln in text.splitlines() if ln.strip()]
    full = [r for r in rows if len(r) == 3]
    names = "\n".join(r[2] for r in full)
    ins = sum(int(r[0]) for r in full if r[0].isdigit())
    dels = sum(int(r[1]) for r in full if r[1].isdigit())
    return names, ins, dels, len(rows)


def _unfrozen(what, why, hint=None):
    """写す元 judge_accept._unfrozen（元 rules:1535）。版を固定できない回の Reject（git が言った理由を必ず添える）"""
    said = " / ".join(w for w in why if w) or "git は理由を返さなかった"
    return Reject(f"この周に採点する版を固定できない（{what}。git の言い分: {said}）" + (f"——{hint}" if hint else ""))


def worktree_tree(repo):
    """写す元 judge_accept._worktree_tree（元 rules:1501）。作業ツリーの今の姿の木の id（未追跡の新規ファイルも含め、追跡していない
    .gitignore の対象は除く）。本物の index を一時 index に写して印を外し（accept.copy_flag_free_index）てから add -A する（本物の
    index は読むだけで書かない）。git は呼び手が accept.in_repo で repo に向ける。固められなければ Reject"""
    tmp = tempfile.mkdtemp(prefix="graphloops-index-")
    idx = pathlib.Path(tmp) / "index"
    env = {"GIT_INDEX_FILE": str(idx)}
    why = []
    try:
        try:
            core_accept.copy_flag_free_index(repo, idx)
        except Reject as e:
            raise Reject(f"この周に採点する版を固定できない（本物の index を印を外して写せない: {e}）")
        if git("update-index", "-q", "--really-refresh", env=env, why=why) is None or git("add", "-A", env=env, why=why) is None:
            raise _unfrozen("一時 index への git update-index / add -A が失敗した", why)
        tree = git("write-tree", env=env, why=why)
        if tree is None or not tree.strip():
            raise _unfrozen("git write-tree が木を返さない", why)
        return tree.strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def snapshot(repo, msg):
    """写す元 judge_accept._snapshot（元 rules:1550）。作業ツリーの今の姿を commit 1 つに固めて返す（枝も index も動かさない）。
    固められなければ Reject"""
    tree = worktree_tree(repo)
    head = git("rev-parse", "HEAD")
    parent = ["-p", head.strip()] if head and head.strip() else []
    why, snap = [], None
    for ident in (None, SNAPSHOT_FALLBACK_IDENT):
        snap = git("commit-tree", tree, *parent, "-m", msg, env=ident, why=why)
        if snap is not None:
            break
    if snap is None or not snap.strip():
        raise _unfrozen("git commit-tree が版を返さない", why)
    return snap.strip()


def take_view(place, repo, base: str) -> View:
    """写す元 judge_accept._take_diff（元 rules:1399 の _take_diff と 1468 の _freeze_revision）。差分の根 base（空なら HEAD）から、
    作業ツリーの今の姿を固めた版（snapshot。未追跡の新規ファイルも入る）までの差分を place の DIFF に生バイトで書き、変更ファイル
    （accept.touched_files）を CHANGED に、見方を VIEW に書く。空の差分は止めない（判定から入る run は差分が空なのが普通）。
    版を固められない・根が引けなければ Reject"""
    out, repo_p = pathlib.Path(place), pathlib.Path(repo)
    with core_accept.in_repo(repo_p):
        rev = core_accept.resolve_rev(repo_p, base or "")
        snap = snapshot(repo_p, "works-factory material")
        raw = core_accept._git(repo_p, "diff", "--binary", rev, snap, binary=True)
        numstat = core_accept._git(repo_p, "diff", "--numstat", "-z", rev, snap)
        commits = core_accept._git(repo_p, "rev-list", "--count", f"{rev}..HEAD").strip()
    _, ins, dels, nfiles = numstat_totals(numstat)
    changed = core_accept.touched_files(repo_p, rev)
    out.mkdir(parents=True, exist_ok=True)
    f = out / DIFF
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, f)
    cf = out / CHANGED
    tmp = cf.with_name(f"{cf.name}.{os.getpid()}.tmp")
    tmp.write_text("\n".join(changed) + "\n", encoding="utf-8")
    os.replace(tmp, cf)
    view = View(repo=repo_p.resolve(), base=rev, review_rev=snap, diff_file=str(f), changed_files=tuple(changed),
                changed_files_file=str(cf), stat=f"{nfiles} files changed, {ins} insertions(+), {dels} deletions(-)",
                commits=int(commits or 0))
    _write(out / VIEW, view.as_dict())
    return view


# ---------------------------------------------------------------- 2.4 作業ツリーの写しと照らし
def snap_tree(place, repo) -> pathlib.Path:
    """写す元 judge_accept.snap_tree（元 entry.snapshot）。役を起こす前の作業ツリーの姿（accept.tree_state）を place の TREE に書く。
    在れば書き直さない（run の再開で走り直しても、役が変えた後の姿で上書きしない）。HEAD が引けなければ Reject"""
    path = pathlib.Path(place) / TREE
    if path.is_file():
        return path
    return _write(path, core_accept.tree_state(pathlib.Path(repo)))


def moved_since(place, repo, keys) -> list:
    """place の TREE から今の作業ツリーが変わった所の文。accept.moved_since を呼ぶだけ（住処は accept。integration.md 4.4-H）"""
    return core_accept.moved_since(place, repo, keys)


# ---------------------------------------------------------------- 2.5 所見の場所の照らし
def where_rows(node) -> list:
    """写す元 judge_accept._where_rows（元 material.py:486）。返答の中の where（字）と text（字）を持つ行の全部（入れ子を辿る）"""
    if isinstance(node, list):
        return [r for x in node for r in where_rows(x)]
    if not isinstance(node, dict):
        return []
    if isinstance(node.get("where"), str) and isinstance(node.get("text"), str):
        return [node]
    return [r for v in node.values() for r in where_rows(v)]


def location_problems(reply, repo) -> dict:
    """写す元 judge_accept._location_problems（元 material.py:497）。{where: [外れの文]}: 行の where の <パス>:<行> のうち、作業ツリーに
    在るファイルを指し、行がそのファイルに無い物"""
    root, out = pathlib.Path(repo).resolve(), {}
    for row in where_rows(reply):
        for path, a, b in cite.where_cites(row["where"]):
            p = pathlib.Path(path)
            full = (p if p.is_absolute() else root / p).resolve() if path else root
            if not path or not full.is_file() or root not in full.parents:
                continue
            ref = f"{path}:{a}" + (f"-{b}" if b else "")
            why = cite.problem(ref, root)
            if why:
                out.setdefault(row["where"], []).append(why)
    return out


def location_gap(place, name: str, reply, repo):
    """写す元 judge_accept._location_gap（元 material.py:514）。(拒む文か None, 受ける返答)。外れが在り、観点 name の輪の今の回が
    諦める回でなければ拒む文。諦める回なら外れた行の where に LOCATION_MARK を付けて受ける（場所の言い方だけで止めない）"""
    bad = location_problems(reply, repo)
    if not bad:
        return None, reply
    if not rolekit.is_last_attempt(rolekit.attempt(pathlib.Path(place), name)):
        return LOCATION_HEAD + ":\n" + "\n".join(f"  - {w}: {'; '.join(e)}" for w, e in bad.items()), reply
    marked = json.loads(json.dumps(reply))
    for row in where_rows(marked):
        if row["where"] in bad:
            row["where"] += LOCATION_MARK
    return None, marked


# ---------------------------------------------------------------- 2.6 回すかの決めと、回さない時の埋め
Due = collections.namedtuple("Due", "run why")


def entry_skip(noun: str) -> Due:
    """判定から入る run で観点を回さない決め（写す元 judge_accept.request_entry と not_request_entry の訳の字）"""
    return Due(False, f"判定から入る run の周（入口の印が在り、修正がまだ 1 ファイルも入っていない）のため、{noun}を起こさない")


def fill_entry(entry: str, requests: int | None) -> dict:
    """判定から入る run で回さない素材の状態（写す元 judge_accept._fill_one の 1 つ目の枝）。entry は出どころの文（port entry）、
    requests は依頼の行の数（観点が request を持たない時は None を渡し、件数を渡されていないと言う。0 は 0 件）"""
    count = ("この周の判定に届く人の依頼の件数は渡されていない" if requests is None
             else f"この周の判定に届く人の依頼 {requests} 件")
    return {"status": "not_applicable",
            "reason": f"判定から入る run（出どころ: {entry}。{count}）のため、P1 の役を起こしていない——依頼の外を見る目はこの周に無い"
                      "（判定役と修正前後の審査だけが見る）"}


def normal_run(noun: str) -> Due:
    """判定から入る run でないので観点を回す決め（entry_skip の対。写す元 judge_accept.request_entry の偽の枝の訳）"""
    return Due(True, f"判定から入る run でない（入力 entry が空か、対象差分が空でない）——通常の run のため、{noun}を起こす")


def is_entry_run(view, values: dict) -> bool:
    """判定から入る run の周か（写す元 judge_accept.request_entry）: 対象差分が空で（block が自分で測った事実）、line が依頼の行が
    1 件以上在ると決めて出どころの文を入力 entry に渡した時だけ真。修正が入って差分が出来た run は入口の周でない"""
    return bool(values.get("entry")) and view.empty


def not_entry_due(view, values: dict, noun: str) -> Due:
    """判定から入る run の周（is_entry_run）でない時だけ回す決め（写す元 judge_accept.not_request_entry）"""
    return entry_skip(noun) if is_entry_run(view, values) else normal_run(noun)


def fill_na(na_reason: str, why: str) -> dict:
    """当たる条件が偽の素材の状態（写す元 judge_accept._fill_one の 2 つ目の枝）"""
    return {"status": "not_applicable", "reason": f"{na_reason}（{why}）"}


def fill_not_run(why: str) -> dict:
    return {"status": "not_run", "reason": why}


def fill_problems(viewpoint, fill) -> list:
    """回さない時の素材の埋め fill（viewpoint.fill の返り）の外れの文: 宣言の素材の全部を 1 つずつ持ち、status が STATUS の語で、
    status ごとの要る欄を持つ（写す元 judge_accept._fill_one はいつも全部の素材を埋めた）。合えば空"""
    if not isinstance(fill, dict):
        return [f"埋めが素材の名 → 状態の dict でない（{type(fill).__name__}）"]
    out = []
    if set(fill) != set(viewpoint.MATERIALS):
        out.append(f"埋めの素材 {sorted(fill)} が宣言の素材 {sorted(viewpoint.MATERIALS)} と違う")
    for mat, m in fill.items():
        st = m.get("status") if isinstance(m, dict) else None
        if st not in STATUS:
            out.append(f"素材 '{mat}' の status が不正: {st!r}")
            continue
        for f in STATUS[st].fields:
            v = m.get(f)
            ok = isinstance(v, int) and not isinstance(v, bool) if f in ("count", "from_round") else isinstance(v, (str, list)) and v
            if not ok:
                out.append(f"素材 '{mat}'（{st}）に '{f}' が無い")
    return out


def _all_not_run(viewpoint, why: str) -> dict:
    try:
        return {mat: fill_not_run(why) for mat in viewpoint.MATERIALS}
    except Exception:  # noqa: BLE001 — 出口の落ちた道の埋めは落ちない（宣言が壊れていれば素材を名指せない）
        return {}


def intake(viewpoint, place, repo, values: dict, unreadable: str = "") -> dict:
    """intake の node の本体（materials.md の 2.6）。port の値 values（読めなかった入力は unreadable に名と訳）から対象差分を取り、
    回すかを決め、回すなら作業ツリーを写す。place の INTAKE に {values, view, due, status, reason, fill} を書き、{due, reason} を返す。
    落ちうる所は Reject か値で受け、それ以外の例外は不具合として上げる"""
    out = pathlib.Path(place)
    view, due, status, fill = None, None, None, None
    if unreadable:
        status = "failed"
        reason = f"入力が読めない（{unreadable}）——役を起こしていない"
    else:
        try:
            view = take_view(out, repo, values.get("base") or "")
        except Reject as e:
            status, reason = "failed", f"対象差分が取れない（{e}）——役を起こしていない"
        else:
            due = viewpoint.due(view, values)
            if not due.run:
                status, reason, fill = "skipped", due.why, viewpoint.fill(view, values, due)
                bad = fill_problems(viewpoint, fill)
                if bad:
                    status, fill = "failed", None
                    reason = f"観点 {viewpoint.NAME} の回さない時の素材の埋めが決まりに合わない（{'; '.join(bad)}）——役を起こしていない"
            else:
                reason = due.why
                try:
                    snap_tree(out, repo)
                except Reject as e:
                    status, reason = "failed", f"役を起こす前の作業ツリーの姿が取れない（{e}）——役を起こしていない"
    if status == "failed":
        due, fill = Due(False, reason), _all_not_run(viewpoint, reason)
    _write(out / INTAKE, {"values": values, "view": view.as_dict() if view else None, "due": {"run": due.run, "why": due.why},
                          "status": status, "reason": reason, "fill": fill})
    return {"due": bool(due.run), "reason": reason}


def _intake_doc(place) -> tuple:
    """(View, port の値, INTAKE の中身)。INTAKE が無い・読めない・対象差分の見方を持たなければ ValueError"""
    path = pathlib.Path(place) / INTAKE
    doc = _read(path)
    if not isinstance(doc, dict):
        raise ValueError(f"{path} が無い（入口の段が走っていない）")
    if not isinstance(doc.get("view"), dict):
        raise ValueError(f"{path} に対象差分の見方が無い（入口の段が役を回さないと決めた）")
    view = View.from_dict(doc["view"]["repo"], doc["view"])
    return view, doc.get("values") or {}, doc


# ---------------------------------------------------------------- 2.7 『条件に当たらない』の扱い
def na_mode(viewpoint, view, values) -> tuple:
    """(扱いの語 NA_MODES のどれか, 理由の字)。写す元 judge_accept._na_note の決め方（文は md の共通の断片 material-na が持つ）"""
    if viewpoint.NA == "never":
        return "never", ""
    if viewpoint.NA != "cond":
        raise ValueError(f"観点 {viewpoint.NAME} の NA は never か cond（{viewpoint.NA!r}）")
    ok, why = viewpoint.applies(view, values)
    if not ok:
        return "cond_false", why
    if viewpoint.judged_na(view, values):
        return "judged", why
    return "cond_true", why


# ---------------------------------------------------------------- 2.8 素材の欄の照らし
def check_record(name: str, wanted: tuple, mats: dict, mode: str) -> list:
    """写す元 judge_accept.check_record（元 rules:3665）。観点 name が書く素材 wanted の欄（status × 機械が持つ事実と、status ごとの
    要る欄）。走った観点に流用（黙って通る値）は書けない・mode（na_mode の語）が cond_true か never の not_applicable は拒む"""
    errs = []
    for mat in wanted:
        m = mats.get(mat)
        if not m:
            errs.append(f"観点 {name} は走ったが素材 '{mat}' が返答に無い")
            continue
        st = m.get("status")
        if st in SILENT_STATUS and st != "not_applicable":
            errs.append(f"素材 '{mat}'（観点 {name}）は今の周に走ったのに {st}——自分で見たと主張しない値は走らなかった観点に機械が"
                        "書く。今の周の判定を書け")
        if st == "not_applicable":
            if mode == "cond_true":
                errs.append(f"素材 '{mat}'（観点 {name}）は条件が真で走ったのに not_applicable——機械が持つ事実と食い違う")
            elif mode == "never":
                errs.append(f"素材 '{mat}'（観点 {name}）は走ったのに not_applicable——この観点は『条件に当たらない』を名乗れない。"
                            "今の周の判定を書け")
        if st not in STATUS:
            errs.append(f"素材 '{mat}' の status が不正: {st!r}")
            continue
        for f in STATUS[st].fields:
            v = m.get(f)
            if f in ("count", "from_round"):   # 元 review-record.py:351 の NUMERIC_FIELDS
                if not (isinstance(v, int) and not isinstance(v, bool)):
                    errs.append(f"素材 '{mat}'（{st}）の '{f}' は数で書け")
            elif not isinstance(v, (str, list)) or not v:
                errs.append(f"素材 '{mat}'（{st}）に '{f}' が要る（何を見たかを書け）")
    return errs


def material_from_findings(src) -> dict:
    """写す元 judge_accept.material_from_findings（元 rules:1296）。役の返答（findings と seen）を素材 1 つに写す（衛生の目の写し方）"""
    findings = src.get("findings", [])
    m = {"status": "found" if findings else "clean", "checked": src.get("seen", "")}
    if findings:
        m["count"] = len(findings)
        m["detail"] = " / ".join(f"{f.get('where', '')}: {f.get('text', '')}" for f in findings)
    return m


# ---------------------------------------------------------------- 2.9・4 受け付け
def accept(viewpoint, place, repo, raw: str) -> dict:
    """観点の役の返答の字 raw を受け付ける（materials.md の 4 節。写す元 judge_accept.material_take）。返り {ok, done, reason}。
    拒否の数えと諦めは rolekit.accept_round（GIVE_UP_AFTER 回目、出し直しても直らない拒みは 1 回目で done）"""
    out, repo_p = pathlib.Path(place), pathlib.Path(repo)

    def take(reply):
        def run():
            if not isinstance(reply, dict):
                raise Reject("返答が JSON のオブジェクトでない")
            try:
                view, values, _ = _intake_doc(out)
            except ValueError as e:
                raise Reject(f"入口の控えが読めない: {e}") from None
            moved = moved_since(out, repo_p, core_accept.status_keys(viewpoint.GUARDED))
            if moved:
                raise Reject(f"{READONLY_MOVED}素材集めの役は対象の作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない"
                             f"（{'・'.join(moved)}）。同じ時にほかの役も走りうるので、変えたのがこの役とは限らない")
            why, got, give_up = viewpoint.before(view, values, reply, out)
            if why:
                return {"ok": False, "reason": why, "give_up": bool(give_up)}
            where_gap, got = location_gap(out, viewpoint.NAME, got, repo_p)
            if where_gap:
                raise Reject(where_gap)
            with core_accept.in_repo(repo_p):
                why = viewpoint.after(view, values, got, out)
            if why:
                raise Reject(why)
            mats = viewpoint.materials_of(got)
            errs = check_record(viewpoint.NAME, viewpoint.MATERIALS, mats, na_mode(viewpoint, view, values)[0])
            if errs:
                raise Reject("素材の欄が記録の決まりに合わない: " + "; ".join(errs))
            viewpoint.after_accept(got, out)   # 観点の控えを先に書き、受けた記録 ACCEPTED を最後に書く（落ちても受けた記録が残らない）
            _write(out / ACCEPTED, {"role": viewpoint.NAME, "reply": got, "materials": mats})
            return {"ok": True, "reason": ""}
        return core_accept.guard(run)

    got = rolekit.accept_round(out, viewpoint.NAME, raw, take)
    return {"ok": got.get("ok") is True, "done": got.get("done") is True, "reason": str(got.get("reason") or "")}


# ---------------------------------------------------------------- 2.10 出口と読み手の口
def _ordered(viewpoint, mats: dict) -> dict:
    return {mat: mats[mat] for mat in viewpoint.MATERIALS if mat in mats}


def _material_doc(viewpoint, place) -> dict:
    """出口の素材 {role, status, reason, reply, materials, base, commits}（finish の 1〜5。base・commits は対象差分の見方の
    引いた根と根から HEAD までの commit の数。見方が無ければ null）"""
    doc = _material_body(viewpoint, place)
    try:
        view = (_read(pathlib.Path(place) / INTAKE) or {}).get("view") or {}
    except (ValueError, AttributeError):
        view = {}
    return {**doc, "base": view.get("base"), "commits": view.get("commits")}


def _material_body(viewpoint, place) -> dict:
    out = pathlib.Path(place)
    name = viewpoint.NAME
    try:
        doc = _read(out / INTAKE)
        if not isinstance(doc, dict):
            raise ValueError("無い（入口の段が走っていない）")
    except ValueError as e:
        reason = f"{INTAKE} が読めない（{e}）"
        return {"role": name, "status": "failed", "reason": reason, "reply": None, "materials": _all_not_run(viewpoint, reason)}
    if doc.get("status") in ("failed", "skipped"):
        return {"role": name, "status": doc["status"], "reason": str(doc.get("reason") or ""), "reply": None,
                "materials": _ordered(viewpoint, doc.get("fill") or {})}
    acc = _read(out / ACCEPTED)
    if isinstance(acc, dict):
        return {"role": name, "status": "ran", "reason": "", "reply": acc.get("reply"),
                "materials": _ordered(viewpoint, acc.get("materials") or {})}
    gave = rolekit.given_up_reason(out, name)
    if gave:
        return {"role": name, "status": "gave_up", "reason": gave, "reply": None,
                "materials": _all_not_run(viewpoint, f"{gave}——素材集めの役の返答を受けられなかった")}
    reason = f"観点 {name} の役の返答を受けた記録が無い（ループが落ちたか、走っていない）"
    return {"role": name, "status": "failed", "reason": reason, "reply": None, "materials": _all_not_run(viewpoint, reason)}


def finish(viewpoint, place, pointer) -> dict:
    """finish の node の本体（materials.md の 2.10）。素材の状態を place の MATERIAL に書き、block の返り
    {ok, status, reason, material, report} を返す。pointer は place の中のパスから出力の pointer を作る口。落ちない（K1・K13）"""
    out = pathlib.Path(place)
    try:
        doc = _material_doc(viewpoint, out)
    except Exception as e:  # noqa: BLE001 — 出口は落ちない
        reason = f"出口が落ちた（{type(e).__name__}: {oneline.one_line(e)}）"
        doc = {"role": viewpoint.NAME, "status": "failed", "reason": reason, "reply": None,
               "materials": _all_not_run(viewpoint, reason), "base": None, "commits": None}
    material = None
    try:
        material = pointer(_write(out / MATERIAL, doc))
    except Exception as e:  # noqa: BLE001
        why = f"{MATERIAL} が書けない（{type(e).__name__}: {oneline.one_line(e)}）"
        doc = {**doc, "status": "failed", "reason": f"{doc['reason']}／{why}" if doc["reason"] else why}
    try:
        report = report_lines(doc) + list(viewpoint.report_lines(doc))
    except Exception as e:  # noqa: BLE001
        report = [f"観点 {viewpoint.NAME}: 報告の行が組めない（{type(e).__name__}: {oneline.one_line(e)}）"]
    return {"ok": doc["status"] in OK_STATUSES, "status": doc["status"], "reason": doc["reason"], "material": material,
            "report": report}


def _flat(value) -> str:
    return oneline.one_line("・".join(map(str, value)) if isinstance(value, list) else value)


def report_lines(doc) -> list:
    """報告の行: 素材ごとに 1 行。素材を書かない観点は観点の status の 1 行と reason（空でなければ）"""
    mats = doc.get("materials") or {}
    if not mats:
        return [f"観点 {doc.get('role')}: {doc.get('status')}"] + ([oneline.one_line(doc["reason"])] if doc.get("reason") else [])
    out = []
    for name, m in mats.items():
        st = m.get("status")
        if st == "found":
            tail = f"（{m.get('count')} 件）: {_flat(m.get('detail', ''))}"
        elif st == "clean":
            tail = f"（見た所: {_flat(m.get('checked', ''))}）"
        else:
            tail = f"（{_flat(m.get('reason', ''))}）"
        out.append(f"素材 {name}: {st}{tail}")
    return out


def read(path) -> dict:
    """読み手の口: material.json を読み、role（字）・status（STATUSES のどれか）・materials（dict）・base（字か null）・commits（整数か
    null）を確かめて中身を返す。外れれば ValueError"""
    doc = _read(path)
    if not isinstance(doc, dict):
        raise ValueError(f"素材のファイル {path} が無いか JSON のオブジェクトでない")
    if not isinstance(doc.get("role"), str) or not doc["role"]:
        raise ValueError(f"素材のファイル {path} の role が字でない（{doc.get('role')!r}）")
    if doc.get("status") not in STATUSES:
        raise ValueError(f"素材のファイル {path} の status が {'・'.join(STATUSES)} のどれでもない（{doc.get('status')!r}）")
    if not isinstance(doc.get("materials"), dict):
        raise ValueError(f"素材のファイル {path} の materials がオブジェクトでない")
    if doc.get("base") is not None and not isinstance(doc["base"], str):
        raise ValueError(f"素材のファイル {path} の base が字か null でない")
    if doc.get("commits") is not None and (not isinstance(doc["commits"], int) or isinstance(doc["commits"], bool)):
        raise ValueError(f"素材のファイル {path} の commits が整数か null でない")
    return doc


def assemble(docs: list, *, local_checks: dict | None = None) -> dict:
    """読み手（diagnose）が素材の 15 欄（MATERIALS）にそろえる口（写す元 judge_accept.fill_materials）。docs は read の返りの並び
    （観点の block と並行 PR の block の material.json。回さない・諦めた素材の埋めは各 materials に在る）→ local_checks は渡された
    修正前の CI の素材 → base_determination は docs の引いた根 base と commit の数 commits（両方を持つ最初の doc。無ければ not_run）
    → fix_closure は P1 時点の not_applicable → 残りは not_run（走っていない）"""
    mats = {}
    for doc in docs:
        mats.update({k: v for k, v in (doc.get("materials") or {}).items() if isinstance(v, dict)})
    if local_checks is not None:
        mats["local_checks"] = local_checks
    seen = next((d for d in docs if isinstance(d.get("base"), str) and d["base"]
                 and isinstance(d.get("commits"), int) and not isinstance(d.get("commits"), bool)), None)
    if "base_determination" not in mats:
        mats["base_determination"] = (
            {"status": "found", "count": seen["commits"], "detail": f"{seen['base']}（始めの記録の差分の根。空なら HEAD）"} if seen else
            {"status": "not_run", "reason": "どの素材の観点も対象差分の根と commit の数を返していない"})
    if "fix_closure" not in mats:
        mats["fix_closure"] = {"status": "not_applicable", "reason": "P1 時点。修正は P3 でこれから行う"}
    for name in MATERIALS:
        if name not in mats:
            mats[name] = {"status": "not_run", "reason": "走っていない（どのノードも返していない）"}
    return {name: mats[name] for name in MATERIALS}


# ---------------------------------------------------------------- 2.11 指示の値の共通の口
def prompt_inputs(viewpoint, place, lang) -> tuple:
    """prep の本体（materials.md の 2.11）。(values, when)。INTAKE から View と port の値を戻し、観点の値と段落の真偽に、共通の値
    （lang・rejection・na_why）と共通の真偽（rejected・na_never・na_cond_true・na_cond_false・na_judged）を足す。lang は port の字を
    人に見せる欄の言語の値にする口（空なら既定の言語の文。block の口 prompt.lang）。観点の値・真偽の名が共通の名と重なれば ValueError。rejection と na_why は、段落が入らない回も空の字で
    渡す（指示を組む口は選ばれない段落の中の差し込み口も数える）。na_why と na_* の真偽は、返答が material の欄を持つ観点
    （viewpoint.NA_PARAGRAPH が真。md が共通の断片 material-na を差し込む）だけに足す。INTAKE が無い・見方を持たなければ ValueError"""
    out = pathlib.Path(place)
    view, ports_values, _ = _intake_doc(out)
    rejected = rolekit.rejected(out, viewpoint.NAME)
    mode, why = na_mode(viewpoint, view, ports_values)
    values = {"lang": lang(ports_values.get("lang") or ""), "rejection": rolekit.rejects_text(rejected)}
    when = {"rejected": bool(rejected)}
    if viewpoint.NA_PARAGRAPH:
        values["na_why"] = why
        when.update({f"na_{m}": m == mode for m in NA_MODES})
    own_values, own_when = viewpoint.values(view, ports_values), viewpoint.when(view, ports_values)
    clash = sorted((set(own_values) & set(values)) | (set(own_when) & set(when)))
    if clash:
        raise ValueError(f"観点 {viewpoint.NAME} の指示の値か段落の名 {clash} が共通の名と重なる")
    return {**own_values, **values}, {**own_when, **when}
