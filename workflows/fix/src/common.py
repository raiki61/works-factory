"""修正の block の型を問わない部品（docs/plans/2026-10-24-fix-weapons.md の 4.1 の 2）。

TDD の輪（src/tdd.py）の中に在り、修正役の受け付け（board・facts・gates）・合わせ役（clash）・確かめ直しが借りていた部品を
ここに集めた。型のモジュール（tdd・variant・remove・static・tidy・pin）と型を問わない部品（basecase・route・duties）はここを
import し、型のモジュールどうしは import しない（tests/layers/test_weapon_imports.py）。中身は移す前のまま:
- 版を木に固める・戻す（snapshot・touched・restore・restore_paths・restore_tests・hashes）と版・作業ツリーの読み口（rev_source・
  _tree_text・_now_text・frozen_source）
- test_cmd を走らせる口（_cmd_run・_cmd_material）
- 輪の状態の読み書きと状態の欄の小さな読み口（load_state・_load・_save・_owed・_unit・_contract・_plan_tdd・states・suite_made）と、
  止めた申し出の流し（flush_unsent・flush_claims）
- 赤の判定の唯一の口（red_check・red_rerun）と、凍ったテストのファイルの照らし（frozen_problems・frozen_asks・test_spans）
- 受け付けが変更に当たる試験を選んで走らせる口（selected_problems）と版の写しの結末（_base_reds）
"""
import ast
import difflib
import hashlib
import json
import os
import pathlib
import posixpath
import re
import subprocess
import sys
import tempfile
import shlex
import unittest

sys.dont_write_bytecode = True

import baseline_red  # noqa: E402  （lib。赤・緑の判定と実行器を走らせる口の正本）
from baseline_red import run_suite  # noqa: E402  （lib。実行器を走らせる口の正本）
import cite  # noqa: E402  （.shared/core。名指しの形・引いた文が現物に在るかの照らし。寄せた後の部分一致 quoted_in）
import conflict  # noqa: E402  （lib。食い違いの申し出の確かめ・直す義務から外れた単位）
from src import files as fixnames  # noqa: E402
import impact  # noqa: E402  （.shared/core。変更に当たる試験の選び）
import planmarks  # noqa: E402  （.shared/core。修正案の項目の works の欄。単位の約束）
from planmarks import test_functions  # noqa: E402,F401  （.shared/core。テストの関数の id（pytest の node id の形）→ 源の引き。fixgates・fixboard が tddloop.test_functions の名で読む）
import tree_run  # noqa: E402
import jsonfile  # noqa: E402
import leftovers  # noqa: E402
import oneline  # noqa: E402
from leftovers import Unreadable, git, git_names  # noqa: E402


STATE, PROMPT, SUMMARY = fixnames.TDD_STATE_FILE, "next.md", "summary.md"


MIN_WHY = 10


MIN_QUOTE = 3   # 赤の引用の下限（寄せた字数。1〜2 字の引用はどの失敗の文にも当たるので、照らす先が短くなければ拒む）


QUOTES_FIELD = "red_quotes"   # test の段の返答の欄と単位の記録の欄の名: {名指しの id: {quote: 失敗の文, why: なぜ期待どおりの理由か}}


UNSENT = "unsent"   # 状態の欄: 盤面へまだ積んでいない止めた申し出の並び（行 {source, item}）


NO_SUITE = "テストの実行器（入力 tdd_suite）が無いか元の結末を取らない組（static だけの組。ほかの組は no-suite で止まる）——受け付けは試験を走らせない"


# run の test_cmd の関門（start が 1 回だけ決める）: on＝緑の後に毎回走らせる・same_as_suite＝実行器がそのコマンドを包んだ物で
# 一式の緑と同じ（走らせない）・off＝空か、輪の頭で赤・走らない（理由は状態の test_cmd_note）。1 行ずつ定義する（根の柵の
# doc-symbols が文書の名指しを `^名前 =` の行で引く）
GATE_ON = "on"


GATE_SAME = "same_as_suite"


GATE_OFF = "off"


class Broken(Exception):
    """回す側の誤り（状態が読めない・輪が済んだ後に呼んだ・入力の形が違う）。節は 2 で落ちる"""


def rules():
    """赤・緑の判定の正本のモジュール（lib/baseline_red。red_problems・green_problems・match_case・parse_junit）。元は写しの TDD 版の
    rules（review-loop-tdd.py）を盤面の graph から読んだ"""
    return baseline_red


# ---------------------------------------------------------------- 版を木に固める・戻す
snapshot = leftovers.snapshot   # 作業ツリーの今の姿の木の sha（正本は leftovers。輪の中の名は変えない）


def touched(repo, a: str, b: str) -> list:
    """木 a から木 b で変わったパス（足した・消したを含む）"""
    return sorted(set(git_names(repo, "diff-tree", "-r", "--name-only", "--no-renames", a, b)))


def restore(repo, tree: str) -> list:
    """作業ツリーを木 tree の姿に戻す（その後に変わった・足した・消したファイルだけ）。戻したパスを返す"""
    return restore_paths(repo, tree, touched(repo, tree, snapshot(repo)))


def restore_paths(repo, tree: str, paths) -> list:
    """作業ツリーの paths だけを木 tree の姿に戻す（tree に無いパスは消す）。戻したパスを返す"""
    paths = sorted(set(paths))
    if not paths:
        return []
    keep = set(paths) & set(git_names(repo, "ls-tree", "-r", "--name-only", tree))
    for p in paths:
        if p not in keep:
            f = pathlib.Path(repo) / p
            if f.is_file() or f.is_symlink():
                f.unlink()
    if keep:
        with tempfile.TemporaryDirectory(prefix="works-tdd-index-") as td:
            env = {**os.environ, "GIT_INDEX_FILE": str(pathlib.Path(td) / "index")}
            git(repo, "read-tree", tree, env=env)
            git(repo, "checkout-index", "-f", "--", *sorted(keep), env=env)
    return paths


def _chain_at(src, line: int):
    """.py の中身 src の line を含む最も内側の関数の名の連なり（`<クラス>::<名前>` か `<名前>`。_def_line の name の形）。無い・構文が
    読めなければ None"""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    best = []

    def walk(body, chain):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top = min([node.lineno] + [d.lineno for d in node.decorator_list])
                if top <= line <= node.end_lineno and len(chain) + 1 > len(best):
                    best[:] = [*chain, node.name]
            if isinstance(node, ast.ClassDef):
                walk(node.body, [*chain, node.name])
    walk(tree.body, [])
    return "::".join(best) if best else None


def restore_tests(repo, tree: str, specs, *, ref=None) -> list:
    """名指したテストの関数の幅だけを木 tree の姿に戻す（木に無い関数は消す。ファイル全体は戻さない: 同じファイルに在る許した直しや
    輪の受け入れのテストを残す）。specs は `<パス>:<行>`（行は ref の木のそのファイルの関数の中の行。ref が無ければ tree。どの関数かを
    名で引き直して tree と作業ツリーの同じ名の関数を入れ替える）か、テストの id `<パス>::<クラス>::<名前>`（作業ツリーで足した関数を
    消す・木に在れば戻す）。関数の幅は _function_span（デコレータと上のコメントの行から本体の終わり）。作業ツリーの関数が引けない
    （消えた）spec は戻せない。戻したパスの一覧を返す"""
    repo = pathlib.Path(repo)
    want: dict = {}
    for spec in specs:
        if "::" in spec:
            path, _, name = spec.partition("::")
        else:
            got = conflict.parse_limit(spec)
            if not got or not got[1]:
                continue
            path = got[0]
            name = _chain_at(_tree_text(repo, ref or tree, path) or "", got[1][0])
        path = posixpath.normpath(path)
        if name and name not in want.setdefault(path, []):
            want[path].append(name)
    done = []
    for path, names in want.items():
        old, now = _tree_text(repo, tree, path), _now_text(repo, path)
        if now is None or not path.endswith(".py"):
            continue
        old_lines, now_lines = (old or "").splitlines(), now.splitlines()
        edits = []
        for name in names:
            line = _def_line(now, name)
            span = _function_span(now_lines, line) if line else None
            if span is None:
                continue
            was = _def_line(old, name) if old is not None else None
            base = _function_span(old_lines, was) if was else None
            if base is not None:
                edits.append((span[0], span[1], old_lines[base[0] - 1:base[1]]))
            else:   # 木に無い関数（作業ツリーで足した物）は消す。上の空の行 1 本も（足した時に置いた区切り）
                top = span[0] - 1 if span[0] > 1 and not now_lines[span[0] - 2].strip() else span[0]
                edits.append((top, span[1], []))
        for a, b, lines in sorted(edits, reverse=True):
            now_lines[a - 1:b] = lines
        if edits:
            (repo / path).write_text("\n".join(now_lines) + ("\n" if now.endswith("\n") or not now_lines else ""), encoding="utf-8")
            done.append(path)
    return done


def hashes(repo, files) -> dict:
    """ファイル → 中身の sha256（無ければ None）"""
    out = {}
    for f in files:
        p = pathlib.Path(repo) / f
        out[f] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    return out


def _quote_target(case: dict, log) -> str:
    """赤の引用を照らす先: その testcase の failure の message と本文。どちらも空ならその回のログ（無い・読めなければ空）"""
    text = " ".join(filter(None, [case.get("fail_message") or "", case.get("fail_text") or ""]))
    if cite.flat(text):
        return text
    try:
        return pathlib.Path(log).read_text(encoding="utf-8", errors="replace") if log else ""
    except OSError:
        return ""


def _quote_problem(t: str, entry, target: str) -> str:
    """名指し t の引用 entry（{quote, why}）を照らし先 target と照らした拒否の文（通れば空）"""
    if not isinstance(entry, dict) or not isinstance(entry.get("quote"), str) or not isinstance(entry.get("why"), str):
        return f"{t}: {QUOTES_FIELD} の値は {{quote（失敗の文）, why（理由）}}"
    quote, shown = cite.flat(entry["quote"]), cite.flat(target)
    if len(quote) < min(MIN_QUOTE, len(shown)):
        return f"{t}: quote が短すぎる（{MIN_QUOTE} 字以上。結末の失敗の文をそのまま引け）"
    if not cite.quoted_in(entry["quote"], target):
        return f"{t}: quote が結末の失敗の文に無い——赤の時の失敗の文をそのまま引け（作り話の引用は通らない。空白・改行・色の違いは無視する）"
    if _blank(entry["why"]):
        return f"{t}: why（なぜ期待どおりの理由で落ちたか。機能が無いから・打ち間違いでない）を {MIN_WHY} 字以上で書け"
    return ""


def red_check(named: list, cases: list, code, baseline, quotes=None, log=None) -> tuple[list, list]:
    """赤の判定の唯一の口（輪の test の段・事後の関門が呼ぶ）——（問題の文, 引用を照らせなかった名指し）。
    事実は言語に依らず、baseline_red の red_problems が見る物だけ: 名指しが全部 failure で落ちる（error・一式に居ない・もう通る・飛ばされた
    は拒む）・名指しの外は元（baseline）のまま・一式が 0 以外で終わる。返す文は事実だけで、言い足しは足さない。
    quotes（{名指しの id: {quote, why}}。None は引用を見ない）が在れば、事実が通った failure の名指しごとに、quote が failure の
    message と本文を寄せた文（cite.quoted_in）に在るか・短すぎないか（MIN_QUOTE）・why が MIN_WHY 字以上かを照らす。両方が空なら
    役が引いた時だけ log（その回のログ）と照らす。照らす先が無い名指し（failure の文が空で、log にも文が無い）は引用が無くても拒まず、
    unchecked に返す。failure の文が在る名指しは、quotes が渡されていれば引用が要る"""
    probs = list(rules().red_problems(named, cases, code, baseline))
    given = {_norm_id(k): v for k, v in (quotes or {}).items() if isinstance(k, str)}
    unchecked = []
    for t in named:
        c = rules().match_case(t, cases)
        if c is None or c["outcome"] != "failure":
            continue
        entry = given.get(_norm_id(t))
        own = cite.flat(" ".join([c.get("fail_message") or "", c.get("fail_text") or ""]))
        if entry is None:
            if not own:
                unchecked.append(t)
            elif quotes is not None:
                probs.append(f"{t}: 失敗の文の引用と理由が無い——{QUOTES_FIELD} に結末の failure の文をそのまま引き、なぜ期待どおりの"
                             "理由で落ちたかを書け")
            continue
        target = _quote_target(c, log)
        if not cite.flat(target):
            unchecked.append(t)   # 引いたが照らす先が無い（ログも空）。拒まず、照らせなかったと残す
            continue
        bad = _quote_problem(t, entry, target)
        if bad:
            probs.append(bad)
    return probs, unchecked


RED_TREE_MOVED = "赤の木の中のテストのファイルが赤の記録と違う（赤を確かめ直せない）"


def red_rerun(tree, u: dict, exe: str, work: pathlib.Path, n, baseline=None) -> tuple:
    """単位の記録 u の赤を、記録の赤の木（red_tree。仮の実装を含む）で確かめ直す唯一の口（事後の関門 fixgates._red_green が
    呼ぶ）——（問題の文の並びか None, 実行器が走らない理由）。作業ツリー tree を赤の木の姿にし、
    その中のテストのファイルが記録（test_hashes）と同じかを照らしてから（違えば [RED_TREE_MOVED]）名指しだけを回し、red_check の
    事実（名指しが failure で落ちる）で照らす。引用は赤の回に照らし済みで、回ごとに変わる文（番地・秒・一時のパス）で誤って
    戻さないため、照らし直さない。回した後は tree を元の姿に戻す。実行器が走らなければ (None, 理由)。tree は赤の木の
    オブジェクトを読める git の作業ツリー（同じリポジトリの worktree）。baseline（元の結末）が None なら名指しの行だけで見る
    （事後の関門。名指しの外は今の木の一式が見る）"""
    tests, files = list(u.get("tests") or []), list(u.get("test_files") or [])
    recorded = u.get("test_hashes") or {}
    final = snapshot(tree)
    try:
        restore(tree, u["red_tree"])
        if any(h != recorded.get(f) for f, h in hashes(tree, files).items()):
            return [RED_TREE_MOVED], []
        cases, code, why = run_suite(exe, tree, work, n, abs_ids(tree, tests), only=True)
    finally:
        restore(tree, final)
    if cases is None:
        return None, why
    if baseline is None:
        cases = [c for t in tests if (c := rules().match_case(t, cases)) is not None]
    return red_check(tests, cases, code, baseline)[0], []


def _key(c) -> str:
    return f"{c['classname']}::{c['name']}"   # baseline_red の _key と同じ形（元の結末の鍵）


def _abs_paths(repo, files) -> list:
    """根からの相対パス（node id の頭も）を絶対パスにする。実行器は自分の置き場へ cd しうるので、相対では解けない"""
    root = pathlib.Path(repo).absolute()
    return [str(root / f) for f in files]


def _abs_ids(repo, ids) -> list:
    """名指し『<相対パス>::…』を『<絶対パス>::…』の node id にする"""
    parts = [i.partition("::") for i in ids]
    return [a + sep + rest for a, (_, sep, rest) in zip(_abs_paths(repo, [p[0] for p in parts]), parts)]


# ---------------------------------------------------------------- 状態
def load_state(state_file) -> dict:
    """輪の状態（frozen・frozen_tree など）を読む口（受け付けが止めた単位の直しを戻す先を決める）"""
    return _load(state_file)


def _load(state_file) -> dict:
    try:
        return json.loads(pathlib.Path(state_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Broken(f"TDD のループの状態が読めない（{state_file}: {e}）")


def _save(state_file, st: dict) -> None:
    p = pathlib.Path(state_file)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def _owed(st) -> list:
    """TDD の直す義務: start が conflict.fix_duty から組んだ単位（open_units）から、外れた単位（excused）と食い違いで止めた
    単位（parked）を除いた物"""
    out = set(st.get("excused", {})) | set(st.get("parked", []))
    return [k for k in st["open_units"] if k not in out]


def _not_owed_why(st, k) -> str:
    if k in st.get("excused", {}):
        return f"直す義務から外れた——{st['excused'][k]}"
    if k in st.get("parked", []):
        return "食い違いで止めた"
    return "直す義務の単位に無い"


def _unit(key, route, why="") -> dict:
    return {"unit_key": key, "route": route, "why": why, "tests": [], "test_files": [], "red": "", "green": "",
            "refactor": "", "gave_up": "", "problems": [], "files": [], "what": "", QUOTES_FIELD: {},
            "quote_unchecked": [], "stub_files": [], "red_tree": "", "test_cmd": "", "refactor_why": ""}


def _cmd_run(repo, cmd: str, log: pathlib.Path, *, reuse: dict | None = None) -> tuple[dict, list[str]]:
    """test_cmd を 1 回走らせる——（素材 {status: clean・found・not_run, reason, detail, count}, 新しく出来たパス）。
    決まりは 1 つ: 既存のファイルを書き換えた（変えた・消した）test_cmd は緑でない。書き換えたパスは走らせる前の木に戻し
    （restore_paths。緑を出した木と残る木を違えない）、素材を赤（found）にして、書き換えたパスと戻したことを rewrote の文に載せる。
    suite_made に積んでよいのは新しく出来たパスだけ（積むと書き込みの出どころの照合・凍結の照らしから外れる）。
    起こし方は baseline_red.run_suite と同じ tree_run.reuse_run（自分のプロセスグループ・標準入力は空・環境は tree_run.outside_env・
    出力は log）で、コマンドの 1 行は tree_run.command_argv の形（direct か shell）、優先度は実行器と同じ baseline_red.lowered（nice -n 19 と同じだけ下げる）。
    元は entry.local_checks_material（試験の枠 tree_run.slotted_run・nice・同じ run の控えの使い回し）で走らせた。枠は外し、
    使い回しは reuse を渡した呼び（ループの頭）だけ"""
    pre = snapshot(repo)
    mat = _cmd_material(repo, cmd, pathlib.Path(log), reuse=reuse)
    post = snapshot(repo)
    made = sorted(set(git_names(repo, "diff-tree", "-r", "--name-only", "--no-renames", "--diff-filter=A", pre, post)))
    rewrote = sorted(set(touched(repo, pre, post)) - set(made))
    restore_paths(repo, pre, rewrote)
    if rewrote:
        why = (f"test_cmd が作業ツリーの既存のファイルを書き換える（{', '.join(rewrote[:10])}。元に戻した。ログ {log}）——"
               "書き換えた木で出た緑は数えない（書き換えた物を書き込みの出どころの照合から外さない）")
        mat = {**mat, "status": "found", "count": 1, "rewrote": why}
    return mat, made


def _cmd_material(repo, cmd: str, log: pathlib.Path, *, reuse: dict | None = None) -> dict:
    """test_cmd を対象の根で走らせた素材（_cmd_run の 1 か所の起こし。tree_run.reuse_run）。終了コード 0 なら clean、ほかは found・count 1
    （detail はログの末尾）、起こせなければ not_run（reason）。reuse（tree_run.reuse_place の返り）の控えから使い回した回は、clean の
    checked に出どころ（tree_run.reused_text）を足す"""
    cmd = (cmd or "").strip()
    if not cmd:
        return {"status": "not_run", "reason": "テストのコマンド（test_cmd）が空で、走らせる物が無い"}
    log.parent.mkdir(parents=True, exist_ok=True)
    argv, how = tree_run.command_argv(cmd)
    nice_kw, bare = baseline_red.lowered()   # 実行器と同じ 1 か所（下げられなければ下げずに、ログに 1 行）
    launched = f"{shlex.join(argv)}（起こし方 {how}）"
    note = {}
    with open(log, "wb") as f:
        if bare:
            f.write(f"{bare}\n".encode("utf-8"))
            f.flush()
        try:
            code = tree_run.reuse_run(argv, tree_run.outside_env(os.environ), place=reuse, note=note, stdin=subprocess.DEVNULL,
                                      stdout=f, stderr=subprocess.STDOUT, cwd=str(repo), **nice_kw)
        except OSError as e:
            return {"status": "not_run", "reason": f"{launched} でテストのコマンドを起こせない: {e}"}
    kind = tree_run.launch_kind(code)
    if kind == "broken":
        return {"status": "not_run", "reason": f"{launched} でテストのコマンドを起こせない（exit None。ログ {log}）"}
    tail = oneline.one_line(log.read_text(encoding="utf-8", errors="replace"))[-2000:]
    ran = f"{launched} を対象の根で走らせた: exit {code}（ログ {log}）"
    if kind == "clean":
        reused = tree_run.reused_text(note)
        return {"status": "clean", "count": 0, "checked": f"{ran} ／ 控えから使った（{reused}）" if reused else ran, "detail": tail}
    return {"status": "found", "count": 1, "detail": f"{ran} ／ 末尾: {tail}"}


# ---------------------------------------------------------------- 返答の確かめ（節 tdd-step）
def _blank(s) -> bool:
    return not isinstance(s, str) or len(s.strip()) < MIN_WHY


def _reached(st, repo, seeds=None, direct_only=True) -> tuple[list, bool]:
    """緑の回に足す試験 ——（根からの相対の pytest の試験のファイル, 一式を回すか）。単位の頭からの変更（走らせて出来たファイルを
    除く）を起点に地図を引き（impact.map の seeds。置き場は work/impact）、直に関わる試験（impact.select_tests の direct_only。
    起点か深さ 1。先の試験は受け付けと同じく線の最後のテストの段に任せる）のうち作業ツリーに在り、
    元の結末に載ったモジュール（元の一式が走らせた物。元で赤だった試験が届いただけで拒まれない）のファイル。地図が引けない・
    run_all なら ([], True)（合図なしの一式）。
    seeds（根からの相対のパス）を渡せばそれを起点にし、direct_only が偽なら地図が届く試験の全部を選ぶ（組を当てた後の確かめ直し
    fixboard.rerun_problem が、前の組と重なったファイルを起点に広げる口。F411 の 2）"""
    if seeds is None:
        seeds = set(touched(repo, st["unit_head"], snapshot(repo))) - set(st["suite_made"])
    seeds = sorted(seeds)
    try:
        sel = impact.select_tests(impact.map(repo, seeds=seeds, cache_dir=pathlib.Path(st["work"]) / "impact"),
                                  direct_only=direct_only)
    except (RuntimeError, OSError, ValueError):
        return [], True
    if sel["run_all"]:
        return [], True
    base = {impact._junit_module({"classname": k.partition("::")[0]}) for k in st["baseline"]}
    return [f for f in sel["selected"] if PYTEST_FILE.match(posixpath.basename(f)) and (pathlib.Path(repo) / f).is_file()
            and impact._mod(f) in base], False


def _contract(st, k) -> dict | None:
    """単位 k の約束（start が plan_contract で組んだ状態の contract の行）。約束の無い単位・約束の無い run は None"""
    return (st.get("contract") or {}).get(k)


def _plan_tdd(st, k, how="direct に振れない") -> str:
    """約束で tdd の単位を direct へ回す返答を拒む文（約束が無いか tdd でなければ空）"""
    c = _contract(st, k)
    if not c or c.get("route") != "tdd":
        return ""
    return (f"'{k}' は承認済みの修正案で tdd（受け入れのテスト {len(c.get('tests') or [])} 本）——{how}。"
            "案の前提が誤りなら phase conflict で申し出よ")


def _norm_id(test_id: str) -> str:
    """名指しのパスの部分を posixpath.normpath で整えた id（`./a.py::T::t` と `a.py::T::t` を同じに見る）"""
    path, sep, rest = test_id.strip().partition("::")
    return posixpath.normpath(path) + sep + rest


def _unnamed_edits(repo, tree: str, files: list[str], allowed: set[str]) -> list[str]:
    """files のうち木 tree に在った .py で、木の時の test_functions に在った id の源が変わった・消えた物のうち、allowed に無い
    id（_id_base で整え、parametrize の `[…]` を落として比べる）。import の行・補助の関数・新しいテストは見ない。今の中身が構文として読めなければ、木の時の
    test* 関数は全部消えた側に数える（拒む側。実行器の結末は消えたテストを数えない）。.py でないファイルは見ない（関数の幅が引けない）"""
    ok = {_id_base(a) for a in allowed}
    py = [f for f in files if f.endswith(".py")]
    there = set(git_names(repo, "ls-tree", "-r", "--name-only", tree, "--", *py)) if py else set()
    out = []
    for f in py:
        if f not in there:
            continue   # 木に無かった（この段で足した）ファイル
        old = git(repo, "show", f"{tree}:{f}")
        p = pathlib.Path(repo) / f
        new = test_functions(p.read_text(encoding="utf-8", errors="replace") if p.is_file() else "", f)
        out += [i for i, body in test_functions(old, f).items() if new.get(i) != body and _id_base(i) not in ok]
    return out


def _id_base(test_id: str) -> str:
    """_norm_id から parametrize の `[…]` を落とした id（`t.py::test_x[1]` の許しは関数 `t.py::test_x` の書き換えを覆う）"""
    return _norm_id(test_id).split("[", 1)[0]


def _verified(st) -> set:
    """輪がもう赤→緑を確かめたテストの id（_norm_id。緑に届いた tdd の単位の名指し）"""
    return {_norm_id(t) for u in st.get("units", {}).values() if u.get("route") == "tdd" and u.get("green") == "ok"
            for t in u.get("tests") or []}


def verified_rewrites(state_file) -> list[str]:
    """約束の書き換えの名指し（修正案の rewrite_tests の id。書いたまま）のうち、輪が赤→緑を確かめた物。受け付けはこれを
    テストの変更の許しから外す（conflict.ruled_test_limits の skip_ids。輪の後の修正役に確かめなしで書き換えさせない）。
    状態が無い（輪の無い run）なら空"""
    if not state_file or not pathlib.Path(state_file).is_file():
        return []
    st = _load(state_file)
    done = _verified(st)
    ids = (i for c in (st.get("contract") or {}).values() for i in c.get("rewrites") or [])
    return [i for i in dict.fromkeys(ids) if _norm_id(i) in done]


def id_path(test_id: str) -> str:
    """名指し（`<パス>::…`）のパスの部分（posixpath.normpath で整えた物）"""
    return posixpath.normpath(test_id.strip().partition("::")[0])


def _mark_parked(st, key, why) -> None:
    st.setdefault("parked", []).append(key)
    st.setdefault("parked_why", {})[key] = why


def flush_unsent(state_file, park) -> None:
    """状態の未送の並び UNSENT（step が保存と同じ 1 回の書き込みで積んだ止めた申し出）を park で盤面へ流す（flush_claims）。
    節 tdd-step が毎回呼ぶ（済んだ輪の resume の早抜けでも、前の周が積めなかった申し出を積む）"""
    st = _load(state_file)
    flush_claims(state_file, st, st, UNSENT, park)


def flush_claims(state_file, st: dict, holder: dict, field: str, park) -> None:
    """状態の st に保存した、盤面にまだ積んでいない申し出の並び holder[field] を park に渡し、渡せたら空にして保存し直す
    （申し出を積む口は conflict.park で、同じ申し出を積み増さない。積みの途中で落ちても、次の呼びが残りを積む。積む口が無ければ何もしない）"""
    claims = holder.get(field)
    if not claims or park is None:
        return
    park(list(claims))
    holder[field] = []
    _save(state_file, st)


# ---------------------------------------------------------------- 輪の後
def frozen_problems(state_file, repo, allowed=(), *, since=None, skip_spans=()) -> list:
    """輪で緑になった単位のテストのファイルが、輪が済んだ時から変わっていれば、その文（状態が無ければ空）。
    allowed はテストの変更の許し（承認済みの修正案の rewrite_tests と裁定 fix_test_scope の範囲。conflict.test_permits を
    conflict.ruled_test_limits が引く）で、その中だけの変更は通す。
    since（木の sha）が在れば、凍結の基準を輪が済んだ時の中身でなくその木のファイルにする（後の輪の状態の handoff を渡す。
    後の輪が同じファイルに足したテストは後の輪の凍結で見る）。skip_spans は [(パス, 関数の名)]（名は `<クラス>::<名前>` か
    `<名前>`。test_spans の形）で、基準の木のその関数の範囲（_function_span）の変更だけを通す（直した項目の単位の古い受け入れの
    テストの関数）。
    .py のファイルに足しただけの物（_without_additions。新しい関数・クラス、既存のクラスの新しいメソッド、新しい名の import・代入で、
    既存のテストが読む名にも枠の掛け金にも当たらない物）は凍結に数えない（依頼 195i の 2: 別の項目が測りのテストを足しただけで人の
    関所を通らせない）。足した物を除いた中身が基準の木と同じ（コードの木もコメントの行も。_same_code）なら通し、許しの範囲が在れば
    足した物を除いた中身で範囲の外の塊を見る。既存の文の書き換え・消し・skip の印の追加は今どおり拒む
    文は 1 ファイル 1 文（許しの無いファイルを 1 つの文に並べない）。範囲の外の塊が全部、輪の受け入れのテストでない既存のテストの
    関数の幅に収まるファイルは frozen_asks が相談の頼みに直す（同じ文を line に持つ）"""
    return [line for _, line, _ in _frozen_rows(state_file, repo, allowed, since, skip_spans)]


def _frozen_rows(state_file, repo, allowed, since, skip_spans) -> list:
    """凍ったファイルの検査の本体（frozen_problems と frozen_asks が共有する、判定の式の 1 か所）。返り [(パス, 文, 範囲の外の塊
    （`a-b` の文の並び。旧い側の行。許しの範囲が無ければ変わった塊の全部。読めなければ ["（輪が済んだ時の姿が読めない）"]）)]"""
    if not state_file:
        return []
    st = _load(state_file)
    now = hashes(repo, st["frozen"])
    then = _tree_hashes(repo, since, st["frozen"]) if since else st["frozen"]
    moved = [f for f in st["frozen"] if now[f] != then[f]]
    base = since or st.get("frozen_tree") or st.get("handoff")
    scope = {}
    for lim in allowed:
        got = conflict.parse_limit(lim)
        if got:
            m = cite.CITE.match(lim.strip())
            # 1 行の指し（`<パス>:<行>`）だけが関数の幅に広がる。`<行>-<行>` は書いたとおり
            scope.setdefault(got[0], []).append(got[1] and (*got[1], bool(m) and not m["b"]))
    for path, name in skip_spans:
        if path in moved:
            line = _def_line(_tree_text(repo, base, path), name)
            if line:
                scope.setdefault(path, []).append((line, line, True))   # def の行の 1 行の指し（関数の幅に広がる）
    out = []
    for f in moved:
        spans = scope.get(f)
        if spans and None in spans:
            continue
        was = _tree_text(repo, base, f) if f.endswith(".py") else None
        pruned = _without_additions(was, _now_text(repo, f), f)
        if not spans:
            if not any(_same_code(was, lines) for lines in pruned):
                bad = min([_hunks_outside(repo, base, f, []), *(_hunks_outside(repo, base, f, [], new=lines) for lines in pruned)],
                          key=len)
                out.append((f, f"TDD のループで凍ったテストのファイルを書き換えた: {[f]}（ループで直した単位のテストは変えない）", bad))
            continue
        # 足した物を除いた中身のどれか（と今どおりの中身）で範囲の外の塊が無ければ通す。並べるのは一番少ない物
        bad = min([_hunks_outside(repo, base, f, spans), *(_hunks_outside(repo, base, f, spans, new=lines) for lines in pruned)],
                  key=len)
        if bad:
            out.append((f, f"TDD のループで凍ったテストのファイル {f} を、テストの変更の許し（修正案の rewrite_tests の名指しまたは裁定 "
                           f"fix_test_scope）の範囲の外で書き換えた: 旧い行 {', '.join(bad)}"
                           "（範囲に並べた行だけ直してよい。.py の 1 行の指しはその行を含む関数の全体）", bad))
    return out


def frozen_asks(state_file, repo, allowed=(), since=None, skip_spans=(), rev=None) -> list:
    """frozen_problems と同じ計算で、凍ったファイルごとの相談の頼み [{path, tests: [<パス>:<関数の def の行>], line, ref}]。範囲の外の
    塊（足しただけの文を除いた後の物）が全部、輪の受け入れのテスト（test_spans）でない既存のテストの関数の幅（_function_span）の中に
    収まるファイルだけ。塊が 1 つでも関数の外（import の行・モジュールの直下の定数・クラスの属性など）か、輪の受け入れのテストの
    関数に掛かれば頼みにしない（成り立たない frozen の文のまま）。line はそのファイルの frozen_problems の文と同じ。
    頼みの行の番号は修正前の版 rev の物（範囲の相談の合意の行の読む木は 1 つ。conflict.agreed_permits）で、凍結の基準の木の関数を
    id で rev の木へ引き直す。rev に無い関数（輪が足した物）・rev が読めない時は頼みにしない。ref は rev で、restore_tests の ref に渡す"""
    rows = _frozen_rows(state_file, repo, allowed, since, skip_spans)
    if not rows or not rev:
        return []
    st = _load(state_file)
    base = since or st.get("frozen_tree") or st.get("handoff")
    mine = test_spans(state_file, list(st.get("units") or {}))
    out = []
    for path, line, bad in rows:
        old = _tree_text(repo, base, path)
        spans = _hunk_functions(old, bad) if path.endswith(".py") else None
        if not spans:
            continue
        guarded = [_function_span(old.splitlines(), _def_line(_tree_text(repo, base, p), n) or 0) for p, n in mine if p == path]
        if any(g and s[0] <= g[1] and g[0] <= s[1] for s in spans for g in guarded):
            continue
        before = _tree_text(repo, rev, path)
        ids = [planmarks.id_at(old, path, s[1]) for s in spans]   # 関数の幅の最後の行は幅の中（最も外側の関数の id）
        lines = [planmarks.line_in(before, i) if i and before is not None else None for i in ids]
        if all(lines):
            out.append({"path": path, "tests": [f"{path}:{n}" for n in lines], "line": line, "ref": rev})
    return out


def _hunk_functions(src, bad: list):
    """src の関数の幅 (始め, 終わり) の並び（重なりは 1 つ）で、bad の塊（`a-b` か `a`。旧い側の行）が全部収まる物。1 つでも関数の
    外・幅をまたぐ・読めない塊が在れば None。bad が空でも None"""
    if not bad or src is None:
        return None
    lines = src.splitlines()
    out = []
    for text in bad:
        a, sep, b = text.partition("-")
        if not a.isdigit() or (sep and not b.isdigit()):
            return None
        a, b = int(a), int(b) if sep else int(a)
        span = _function_span(lines, a)
        if span is None or b > span[1]:
            return None
        if span not in out:
            out.append(span)
    return out


def _tree_text(repo, tree, path):
    """木 tree の path の中身（無い・読めなければ None）"""
    try:
        return git(repo, "show", f"{tree}:{path}") if tree else None
    except Unreadable:
        return None


def _tree_hashes(repo, tree, files) -> dict:
    """ファイル → 木 tree での中身の sha256（無ければ None。hashes と同じ形で比べる）"""
    out = {}
    for f in files:
        try:
            out[f] = hashlib.sha256(git(repo, "show", f"{tree}:{f}", text=False)).hexdigest()
        except Unreadable:
            out[f] = None
    return out


def _def_line(src, name: str):
    """.py の中身 src の関数 name（`<クラス>::<名前>` か `<名前>`。test_functions の id のパスの後ろ）の頭の行（デコレータが在れば
    その行）。無い・構文が読めなければ None"""
    if src is None:
        return None
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    want = name.split("::")

    def walk(body, chain):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and [*chain, node.name] == want:
                return min([node.lineno] + [d.lineno for d in node.decorator_list])
            if isinstance(node, ast.ClassDef):
                got = walk(node.body, [*chain, node.name])
                if got:
                    return got
        return None
    return walk(tree.body, [])


def test_spans(state_file, keys) -> list:
    """輪が tdd で緑にした単位のうち keys の単位の受け入れのテスト（単位の tests。名指しの id）を [(パス, 関数の名)] に
    （frozen_problems の skip_spans の形。名は id のパスの後ろ。parametrize の `[…]` は落とす）。状態が無ければ空"""
    if not state_file:
        return []
    st = _load(state_file)
    out = []
    for k in keys:
        u = st.get("units", {}).get(k) or {}
        if u.get("route") != "tdd" or u.get("green") != "ok":
            continue
        for t in u.get("tests") or []:
            path, sep, rest = _id_base(t).partition("::")
            if sep and (path, rest) not in out:
                out.append((path, rest))
    return out


def frozen_source(state_file, repo, *, since=None):
    """凍結の検査が行を読む輪の後の木（since が在ればその木。無ければ frozen_tree、それも無ければ handoff。frozen_problems の
    基準の木と同じ）から、パスの中身を読む口（conflict.ruled_test_limits の source。修正案の limit をその木でテストの id から
    引き直す）。状態・木・パスが読めなければ口は None を返す（許しを捨てる側）。状態は口を呼んだ時に読む"""
    def read(path):
        try:
            st = _load(state_file) if state_file else {}
            tree = since or st.get("frozen_tree") or st.get("handoff")
            return git(repo, "show", f"{tree}:{path}") if tree else None
        except (Broken, Unreadable):
            return None
    return read


def rev_source(repo, rev):
    """版 rev の木から、パスの中身を読む口（conflict.ruled_test_limits の base。範囲の相談の合意の行は修正前の版の行で、凍結の検査が
    読む木へ移す元）。版・パスが読めなければ口は None を返す（許しを捨てる側）"""
    def read(path):
        try:
            return git(repo, "show", f"{rev}:{path}") if rev else None
        except Unreadable:
            return None
    return read


def _now_text(repo, path):
    """作業ツリーの path の中身（無ければ None）"""
    p = pathlib.Path(repo) / path
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def _hunks_outside(repo, tree, path, spans, new=None) -> list:
    """輪が済んだ時の木の path と今のファイル（new が在ればその行の一覧）の差分の塊のうち、旧い側の行が spans のどれにも収まらない物
    （`a-b` の文）。span は (始め, 終わり, 1 行の指しか)。1 行の指しの .py は _function_span で関数の幅に広げる。
    木が無い・木に path が無い時はファイル全体を 1 つの外の塊にする"""
    if new is None:
        new = (_now_text(repo, path) or "").splitlines()
    try:
        old = git(repo, "show", f"{tree}:{path}").splitlines() if tree else None
    except Unreadable:
        old = None
    if old is None:
        return ["（ループが済んだ時の姿が読めない）"]
    wide = []
    for s, e, single in (sp for sp in spans if sp):
        w = _function_span(old, s) if single and path.endswith(".py") else None
        w = _padded(old, w) if w else None   # 関数を丸ごと消す塊は前後の区切りの空行を含む（空行は許しの幅の中）
        wide.append((*(w or (s, e)), w is not None))
    bad = []
    for tag, i1, i2, _, _ in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        ins = i2 == i1
        a, b = (i1 + 1, i2) if not ins else (max(i1, 1), max(i1, 1))   # 足しただけの塊は直前の行（頭なら 1 行目）で見る
        # 関数の幅に広げた span では、足しただけの塊が幅の直前（def・デコレータの真上）に入るのも幅の中
        if not any(s <= a and b <= e or (ins and f and s - 1 <= a <= e) for s, e, f in wide):
            bad.append(f"{a}-{b}" if b != a else str(a))
    return bad


def _padded(old, span):
    """関数の幅 span (始め, 終わり) を、前と後ろに続く空行まで広げた幅"""
    a, b = span
    while a > 1 and not old[a - 2].strip():
        a -= 1
    while b < len(old) and not old[b].strip():
        b += 1
    return a, b


# 凍ったファイルに足しただけの物（frozen_problems）。既存のテストに効く名・枠の掛け金は足した物に数えない
_MODULE_HOOKS = frozenset({"setUpModule", "tearDownModule", "setup_module", "teardown_module", "setup_function",
                           "teardown_function", "setup", "teardown", "load_tests", "pytestmark", "pytest_plugins",
                           "collect_ignore", "collect_ignore_glob"})


_CLASS_HOOKS = frozenset({*dir(unittest.TestCase), "setup_method", "teardown_method", "setup_class",
                          "teardown_class", "setup", "teardown", "pytestmark"})


def _old_names(tree) -> set:
    """木の中の名の全部（planmarks.code_idents に global・nonlocal の名と、識別子か点つきの名の形の文字列の各部を足す。
    fixture の名・getattr・mock.patch の的も含める）"""
    out = planmarks.code_idents(tree)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and planmarks.DOTTED_NAME.fullmatch(n.value):
            out.update(n.value.split("."))
    return out


def _bound(node, top: bool):
    """足してよい形の文が縛る名の一覧（足してよい形でなければ None）。モジュールの直下は関数・クラス・import（* と __future__ を
    除く）・名だけへの代入、既存のクラスの直下は関数だけ"""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return [node.name]
    if not top:
        return None
    if isinstance(node, ast.ClassDef):
        return [node.name]
    if isinstance(node, ast.Import):
        return [a.asname or a.name.split(".")[0] for a in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.module == "__future__" or any(a.name == "*" for a in node.names):
            return None
        return [a.asname or a.name for a in node.names]
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else None
    if targets is None or not all(isinstance(t, ast.Name) for t in targets):
        return None
    return [t.id for t in targets]


def _addable(node, src: str, names: set, top: bool) -> bool:
    """new の文 node が、既存のテストに効かない足した物か: 縛る名が旧い木の名（names）に無く、枠の掛け金（モジュールなら
    _MODULE_HOOKS・pytest_*、クラスなら _CLASS_HOOKS・_ で始まる名）でも dunder でもなく、デコレータに autouse が無い"""
    got = _bound(node, top)
    if not got:
        return False
    for n in got:
        if n in names or (n.startswith("__") and n.endswith("__")):
            return False
        if top and (n in _MODULE_HOOKS or n.startswith("pytest_")):
            return False
        if not top and (n in _CLASS_HOOKS or n.startswith("_")):
            return False
    return not any("autouse" in (ast.get_source_segment(src, d) or "autouse") for d in getattr(node, "decorator_list", []))


def _without_additions(old_src, new_src, path: str) -> list:
    """凍ったファイルの今の中身 new_src から足しただけの文（_addable。モジュールの直下と、旧い木にも在った直下のクラスの中）を
    除いた行の一覧の候補（足した文の直前に続く同じ字下げのコメントの行と空の行を、それぞれ除いた物と除かない物。足した所の前後の
    空の行が許しの範囲の外の塊にならないように）。.py でない・どちらかが
    読めない・構文が読めない・足した文が無ければ空（足した物を除けない＝今どおりファイルの変更で見る）"""
    if not path.endswith(".py") or old_src is None or new_src is None:
        return []
    try:
        old, new = ast.parse(old_src), ast.parse(new_src)
    except (SyntaxError, ValueError):
        return []
    names = _old_names(old)
    classes = {n.name for n in old.body if isinstance(n, ast.ClassDef)}
    picked = []
    for node in new.body:
        if _addable(node, new_src, names, True):
            picked.append(node)
        elif isinstance(node, ast.ClassDef) and node.name in classes:
            picked += [m for m in node.body if _addable(m, new_src, names, False)]
    if not picked:
        return []
    lines = new_src.splitlines()
    out = []
    for comments, blanks in ((True, True), (True, False), (False, True), (False, False)):
        drop = set()
        for node in picked:
            top = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            while comments and top > 1 and lines[top - 2].startswith(" " * node.col_offset + "#"):
                top -= 1
            while blanks and top > 1 and not lines[top - 2].strip():
                top -= 1
            drop.update(range(top, node.end_lineno + 1))
        got = [x for i, x in enumerate(lines, 1) if i not in drop]
        if got not in out:
            out.append(got)
    return out


def _same_code(old_src, lines) -> bool:
    """行の一覧 lines が旧い中身 old_src と同じコードか: コードの木（ast.dump。文字列の中の空の行も見る）が同じで、空でない行の
    並び（コメントも）が同じ。空の行の数だけの違いは通す"""
    if old_src is None:
        return False
    try:
        same = ast.dump(ast.parse(old_src)) == ast.dump(ast.parse("\n".join(lines)))
    except (SyntaxError, ValueError):
        return False
    return same and [x for x in old_src.splitlines() if x.strip()] == [x for x in lines if x.strip()]


def _function_span(old, line):
    """old（行の一覧）の line を含む最も外側の関数（メソッドも。クラスそのものには広げない）の幅 (始め, 終わり)。
    始めは最初のデコレータの行から、直前に続く def と同じ字下げのコメントの行まで上へ。
    関数の外の行・構文が読めない時は None（1 行のまま＝拒む側）"""
    try:
        tree = ast.parse("\n".join(old))
    except (SyntaxError, ValueError):
        return None
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top = min([node.lineno] + [d.lineno for d in node.decorator_list])
            if top <= line <= node.end_lineno and (best is None or top < best[1]):
                best = (node, top)
    if best is None:
        return None
    node, top = best
    while top > 1 and old[top - 2].startswith(" " * node.col_offset + "#"):   # def と同じ字下げのコメントだけ（前の関数の本体の末尾のコメントは字下げが深い）
        top -= 1
    return top, node.end_lineno


def suite_made(state_file) -> list:
    """実行器を走らせて出来たファイル（書き込みの出どころの突き合わせから外す。状態が無ければ空）"""
    return _load(state_file).get("suite_made", []) if state_file else []


def states(board_dir) -> list:
    """盤面の根の輪の状態 tdd-<k>/ の STATE を番号の順に（run の全部の輪。2 回目の修正の段の輪は 1 回目の後に起きる）。
    置き場が無ければ空"""
    got = []
    for d in pathlib.Path(board_dir).glob("tdd-*"):
        k = d.name[len("tdd-"):]
        if k.isdigit() and (d / STATE).is_file():
            got.append((int(k), d / STATE))
    return [p for _, p in sorted(got)]


def suite_made_all(board_dir) -> set:
    """run の全部の輪（states）の suite_made の和（書き込みの出どころの突き合わせと案の項目の照らしが外す）"""
    return {f for p in states(board_dir) for f in suite_made(p)}


ACCEPT_RUN = "accept"   # 受け付けが走らせた回のログ・JUnit の名（suite-accept.log）


NO_SELECTED = "変えたファイルに当たる試験が無い"


PYTEST_FILE = re.compile(r"^(test_.*|.*_test)\.py$")   # pytest の既定の python_files（conftest.py・*-suite.py などは試験のモジュールでない）


def _args(root, files, kexpr) -> list:
    """受け付けが実行器に足す引数: 選んだ試験のうち root の中に在る pytest の試験のモジュール（絶対パス。.sh・.bats を渡すと
    収集器が無く一式ごと止まり、conftest.py・実行器の台本の .py を名指しすると pytest が型に依らず import する）と、段の中を
    絞る -k（一式を回す時は付けない）"""
    py = [f for f in files if PYTEST_FILE.match(posixpath.basename(f)) and (pathlib.Path(root) / f).is_file()]
    return [*_abs_paths(root, py), *(["-k", kexpr] if kexpr else [])]


def selected_problems(state_file, repo, rev, uncompared=None, *, named=(), accept=None, seen=None) -> tuple:
    """(赤の文の一覧, 知らせ)。選ぶのは変更に直に関わる試験と名指しの試験（_named_files）だけで、届くだけの先の試験は
    final_left に残す。実行器の後ろに足すのは、選んだ試験のうちこの run で変えた・足したファイルだけ（ADR 0071 の
    3 の 1。届いただけの段の外の試験は手元で走らせない）。実行器の既定の一式の中は -k で選んだ全部のモジュールに絞る。
    実行器の無い run（状態が無い）・当たる試験が無い・実行器が走らない・選んだ試験が 1 件も走らなかった時は赤にせず知らせだけ。
    元の結末に無い試験の赤は、版の写しでその試験を名指しで回して、版でも赤なら外す（版の写しの結末は _base_reds が盤面の根に控え、
    受け付けの回をまたいで使い回す）。版の写しの結末に出ない（走らせられない・名指しを聞かない実行器）試験は比べられない:
    受け口 uncompared（並び）を渡す呼び（組を当てた後の確かめ直し。#846）は赤に数えずその鍵を足し、渡さない呼びは赤のまま。
    版に試験のファイルが無い試験（この直しで足した）は比べるまでもなく新しい赤。
    外した鍵と比べられなかった鍵は黙って捨てず、件数と名（頭の 20 件）を赤の行か知らせに出す。
    state_file は輪の状態か元の結末 base.json（下書き docs/plans/2026-10-24-fix-weapons.md の 2.1。同じ名と形の欄を読む）。名指しは
    named（注文の units[].tests と permits の rewrite の行。orders.named_tests）と、輪の状態なら今の _named_files の和（狭めない）。
    書き戻す 4 つの欄（final_left・final_far・ci_left・suite_made の足し）は置き場の accept.json に書く（accept はそのフォルダ。None は
    state_file が base.json ならその隣、輪の状態なら輪のフォルダの親。suite_made は前の回との和）。輪の状態にも今と同じく書く
    （base.json は書き換えない）。seen（dict）を渡せば走らせた回の結末の行（走らなければ None）・訳・ログを seen の cases・why・log に
    置く（変えない段の同じ結果の照らしと、受け付けの止め board.no_suite_at_accept）"""
    if not state_file:
        return [], NO_SUITE
    st = _load(state_file)
    is_base = pathlib.Path(state_file).name == fixnames.BASE_FILE
    acc_dir = pathlib.Path(accept) if accept is not None else \
        (pathlib.Path(state_file).parent if is_base else pathlib.Path(st["work"]).parent)
    work = pathlib.Path(st["work"])
    m = impact.map(repo, rev=rev, diff=True, cache_dir=work / "impact")
    names = sorted(set(_named_files(st)) | {posixpath.normpath(str(i).partition("::")[0]) for i in named or () if str(i).strip()})
    sel = impact.select_tests(m, direct_only=True, named=names)
    st["final_left"], st["final_far"] = sel["left"], sel["far"]
    st.setdefault("suite_made", [])

    def save():
        if not is_base:
            _save(state_file, st)
        acc = accept_values(acc_dir)
        jsonfile.write(acc_dir / fixnames.ACCEPT_FILE, {**acc, "final_left": st["final_left"], "final_far": st["final_far"],
                                                     "ci_left": st.get("ci_left", []),
                                                     "suite_made": sorted(set(acc.get("suite_made") or []) | set(st["suite_made"]))})
    final = (f"。最後のテストの段に任せた {len(sel['left'])} 件（変更に直には関わらず届くだけ。受け付けは回さない）: "
             f"{', '.join(sel['left'])[:300]}") if sel["left"] else ""
    if sel["far"]:
        final += (f"。最後のテストの段に任せた、地図の遠く（深さ 2 以上）の分からない物 {len(sel['far'])} 件（受け付けは一式を回さない）: "
                  f"{', '.join(sel['far'])[:300]}")
    if not sel["run_all"] and not sel["modules"]:
        st["ci_left"] = []
        save()
        return [], NO_SELECTED + final
    changed = set(m["seeds"]["from_diff"])
    files = [f for f in sel["selected"] if f in changed]
    kexpr = "" if sel["run_all"] else " or ".join(sel["modules"])
    pre = snapshot(repo)
    cases, code, why = run_suite(st["exe"], repo, work, ACCEPT_RUN, _args(repo, files, kexpr))
    st["suite_made"] = sorted(set(st["suite_made"]) | set(touched(repo, pre, snapshot(repo))))
    st["ci_left"] = _left_to_ci(sel["selected"], files, cases)
    save()
    if seen is not None:
        seen.update(cases=cases, why=list(why or []), log=str(work / f"suite-{ACCEPT_RUN}.log"))
    what = "一式（" + "・".join(sel["reasons"])[:200] + "）" if sel["run_all"] else \
        f"選んだ試験（ファイル {', '.join(files)[:300]}・-k {kexpr[:300]}）"
    ci = f"。手元で回さなかった {len(st['ci_left'])} 件（run はその緑を確かめない）: {', '.join(st['ci_left'])[:300]}" if st["ci_left"] else ""
    ci += final
    if cases is None:
        return [], f"{what}を走らせられない（{'; '.join(why)}）{ci}"
    if not cases:
        return [], (f"{what}が一式の結末に 0 件——選んだ試験が 1 件も走らなかった（-k が何にも当たらない・実行器が足した試験を"
                    f"拾わない。ログ {work / f'suite-{ACCEPT_RUN}.log'}）。新しい赤が無いことは確かめていない{ci}")
    reds = {_key(c): c for c in cases if c["outcome"] in ("failure", "error")
            and st["baseline"].get(_key(c)) not in ("failure", "error")}
    red = list(reds)
    fresh = [k for k in red if k not in st["baseline"]]
    tail = ""
    if fresh:
        base, why = _base_reds(st, repo, rev, [reds[k] for k in fresh])
        left_out = [k for k in fresh if (base or {}).get(k) in ("failure", "error")]
        unknown = [k for k in fresh if (base or {}).get(k) is None]
        red = [k for k in red if k not in left_out]
        if left_out:
            tail = f"。版の写しでも赤だったので外した {len(left_out)} 件: {', '.join(left_out[:20])}"
        if unknown:
            cause = "; ".join(why) or "名指しで走らせても版の写しの結末に出ない"
            if uncompared is None:
                tail += f"。元の結末に無い {len(unknown)} 件は版の姿で比べられず赤のまま（{cause}）: {', '.join(unknown[:20])}"
            else:
                red = [k for k in red if k not in unknown]
                uncompared.extend(unknown)
                tail += (f"。版の姿と比べられなかった {len(unknown)} 件（{cause}。新しい赤に数えず人に聞く）: "
                         f"{', '.join(unknown[:20])}")
    if not red:
        return [], f"{what}: {len(cases)} 件で新しい赤なし{ci}{tail}"
    # 行はテストのファイルごと（修正の受け付けが最後の回にパスで単位に結ぶ）。頭に選んだファイルの一覧を置かない（ほかの
    # ファイルの赤の行がそのパスを名指して、関わらない単位に結ばないように）
    label = "一式" if sel["run_all"] else f"選んだ試験（-k {kexpr[:300]}）"
    return [f"受け付けが走らせた{label}で、元で赤でなかった試験が赤{where}: {ids[:20]}（{len(ids)} 件。"
            f"ログ {work / f'suite-{ACCEPT_RUN}.log'}{tail}）——直した単位のどこかを直して出し直せ"
            for where, ids in _by_test_file(repo, [reds[k] for k in red]).items()], ""


def _by_test_file(repo, cases) -> dict:
    """赤の case をテストのファイルごとに分けた {「（ファイル <根からのパス>）」: [id]}（現れた順）。ファイルは case のモジュール
    （impact._junit_module）が impact._mod に等しいテストのファイル（impact.tree_files と impact.is_test）で、同じ名のモジュールが
    2 つ以上在れば全部を名指す。見つからない case の鍵は ""（パスを名指さない）"""
    files = _module_files(repo)
    out = {}
    for c in cases:
        hit = files.get(impact._junit_module(c) or "", [])
        out.setdefault(f"（ファイル {', '.join(hit)}）" if hit else "", []).append(_key(c))
    return out


def _module_files(repo) -> dict:
    """{モジュールの名（impact._mod）: [その名のテストのファイル（根からの相対。impact.tree_files と impact.is_test）]}"""
    files = {}
    for p in impact.tree_files(repo) or []:
        if impact.is_test(p) == "module":
            files.setdefault(impact._mod(p), []).append(p)
    return files


def _left_to_ci(selected, run_files, cases) -> list:
    """選んだ試験のうち、手元で名指さず（run_files に無く）結末にもモジュールが 1 件も出なかった物（手元で回さなかった）。実行器の
    既定の段は対象ごとに違うので、段の一覧を写さず結末から決める。結末が無ければ名指さなかった物は全部"""
    ran = {impact._junit_module(c) for c in cases or []}
    return [t for t in selected if t not in run_files and impact._mod(t) not in ran]


def _named_files(st) -> list:
    """修正案の約束の受け入れ・書き換えのテストと、輪で名指したテストのファイル（根からの相対。受け付けは直に関わる試験に足す）"""
    ids = [t.get("id", "") if isinstance(t, dict) else str(t)
           for c in (st.get("contract") or {}).values() for t in [*(c.get("tests") or []), *(c.get("rewrites") or [])]]
    ids += [t for u in (st.get("units") or {}).values() for t in [*(u.get("tests") or []), *(u.get("test_files") or [])]]
    return sorted({posixpath.normpath(i.partition("::")[0]) for i in ids if i and i.strip()})


def accept_values(place) -> dict:
    """置き場の accept.json（受け付けが書き戻した final_left・final_far・ci_left・suite_made と、写した物の印。無い・読めなければ {}）"""
    got = jsonfile.read_or(pathlib.Path(place) / fixnames.ACCEPT_FILE) if (pathlib.Path(place) / fixnames.ACCEPT_FILE).is_file() else None
    return got if isinstance(got, dict) else {}


def accept_dir(state_file) -> pathlib.Path | None:
    """state_file（輪の状態か base.json）の受け付けが書き戻す accept.json のフォルダ（selected_problems の accept の既定と同じ。
    無い・読めなければ None）"""
    if not state_file or not pathlib.Path(state_file).is_file():
        return None
    if pathlib.Path(state_file).name == fixnames.BASE_FILE:
        return pathlib.Path(state_file).parent
    return pathlib.Path(_load(state_file)["work"]).parent


def _accepted(state_file, key: str) -> list:
    d = accept_dir(state_file)
    return list(accept_values(d).get(key) or []) if d is not None else []


def final_left(state_file) -> list:
    """受け付けが直に関わらないので回さず、線の最後のテストの段に任せた試験（accept.json の欄。無い・まだ選んでいなければ空）"""
    return _accepted(state_file, "final_left")


def final_far(state_file) -> list:
    """受け付けが一式を回す理由にせず最後のテストの段に任せた、地図の遠く（深さ 2 以上）の分からない物の理由（impact の far。accept.json）"""
    return _accepted(state_file, "final_far")


def ci_left(state_file) -> list:
    """受け付けが手元で回さなかった試験（accept.json の欄。無い・まだ選んでいなければ空。受け付けの知らせの文にも同じ名が載る）"""
    return _accepted(state_file, "ci_left")


REV_CACHE = "accept-rev-cache.json"   # 版の写しの結末の控え（盤面の根。run の全部の輪と受け付けの回が使い回す）


def rev_id(repo, rev: str) -> str:
    """版 rev の commit の sha（引けなければ rev のまま。控えの鍵に使う: 名前が同じでも指す版が変われば別の鍵）"""
    try:
        return git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip() or rev
    except Unreadable:
        return rev


def exe_id(repo, exe) -> list:
    """実行器の控えの鍵: repo の中なら根からの相対パス（中身は版が決める。版の木の中の同じ物を走らせる）、外なら絶対パスと中身の sha"""
    p = pathlib.Path(exe)
    try:
        return ["repo", p.absolute().relative_to(pathlib.Path(repo).absolute()).as_posix()]
    except ValueError:
        return ["abs", str(p.absolute()), hashes(p.parent, [p.name])[p.name]]


def load_json(path: pathlib.Path, default):
    """控えのファイル（無い・読めない・形が違えば default。控えは使い回しの手がかりで、無くても走らせ直すだけ）"""
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return got if isinstance(got, type(default)) else default


temp_tree = baseline_red.temp_tree   # 版の一時の worktree（lib に上げた。試験の関門の最後のテストも使う）


BASE_ABSENT = "absent"   # 版の写しの結末の語の外: 版にその試験のファイルが無い（この直しで足した試験。比べるまでもなく新しい赤）


def _case_ids(repo, cases) -> dict:
    """結末の行 cases → {鍵: [名指しの id『<根からの相対パス>::<クラス>::<名前>』]}。ファイルは行のモジュール（impact._junit_module）が
    impact._mod に等しいテストのファイル（_module_files。同じ名のモジュールが 2 つ以上在れば全部）、クラスは classname の
    モジュールの後ろの部分。ファイルが引けない行は載せない"""
    files = _module_files(repo)
    out = {}
    for c in cases:
        mod = impact._junit_module(c) or ""
        parts = [x for x in c["classname"].split(".") if x]
        tail = parts[len(parts) - parts[::-1].index(mod):] if mod in parts else []
        for path in files.get(mod, []):
            out.setdefault(_key(c), []).append("::".join([path, *tail, c["name"]]))
    return out


def _base_reds(st, repo, rev, cases) -> tuple:
    """(版 rev の姿で結末の行 cases の試験を名指しで回した {鍵: 結末の語か BASE_ABSENT か None（結末に出ない・名指しを引けない）}
    か None（写せない・実行器が走らない）, 問題)。比べたい試験は名指し（_case_ids）で ONLY_ENV を付けて走らせる（走らせる試験を差分から
    自分で選ぶ実行器は、差分の無い版の写しでは既定の一式に比べたい試験を選ばない。#846）。版の姿は一時の git worktree（--detach）に
    出して走らせ、作業ツリー・index・枝は動かさない（写しに .git が在るので、git を読む試験も今の木と同じ条件で走る）。実行器が repo の
    中に在れば写しの中の同じ物を走らせる（自分の置き場から根を引く実行器が写しの根で走るように）。
    写しは版の姿だけ（今の木から何も写さない）なので、結末は版・実行器・名指しで決まる。走らせた結末は盤面の根の REV_CACHE に残し、
    同じ版・同じ実行器で、比べたい鍵が全部前の回の結末に在れば走らせずに使う（run の中で版は動かないので、受け付けの回・2 回目の
    修正の段をまたいで 1 回で足りる。195g は回ごとに 3 分半）。結末が取れなかった回は残さない"""
    cache = pathlib.Path(st["work"]).parent / REV_CACHE
    key = {"rev": rev_id(repo, rev), "exe": exe_id(repo, st["exe"])}
    rows = load_json(cache, [])
    seen = {}
    for r in rows:
        if isinstance(r, dict) and {k: r.get(k) for k in key} == key and isinstance(r.get("outcomes"), dict):
            seen.update(r["outcomes"])
    wanted = [_key(c) for c in cases]
    if all(k in seen for k in wanted):
        return {k: seen[k] for k in wanted}, []
    ids = _case_ids(repo, cases)
    with temp_tree(repo, rev) as (copy, cant):
        if copy is None:
            return None, [f"版 {rev} を写せない（{'; '.join(cant)}）"]
        got = {k: None for k in wanted}
        for k in wanted:
            if ids.get(k) and not any((copy / i.partition("::")[0]).is_file() for i in ids[k]):
                got[k] = BASE_ABSENT
        named = sorted({i for k in wanted if got[k] is None for i in ids.get(k, []) if (copy / i.partition("::")[0]).is_file()})
        if named:
            exe = pathlib.Path(st["exe"])
            try:
                inner = copy / exe.absolute().relative_to(pathlib.Path(repo).absolute())
                exe = inner if inner.is_file() else exe
            except ValueError:
                pass
            ran, _, why = run_suite(str(exe), copy, pathlib.Path(st["work"]), f"{ACCEPT_RUN}-rev", _abs_ids(copy, named), only=True)
            if ran is None:
                return None, why
            outcome = {_key(c): c["outcome"] for c in ran}
            got.update({k: outcome[k] for k in wanted if got[k] is None and k in outcome})
    jsonfile.write(cache, [*rows, {**key, "outcomes": got}])
    return got, []


# 事後の関門の束（同じブロックの fixgates。計画 220 Task 4）が輪と同じ決まりで読む口の公開の別名（輪の中の名は変えない。
# 名指しの外の既存のテストの書き換え・名指しの node id・関数の幅・範囲の外の差分の塊。preflight F11・F13）
unnamed_edits = _unnamed_edits


abs_ids = _abs_ids


function_span = _function_span


hunks_outside = _hunks_outside


def retry_max() -> int:
    """段ごとの諦めの回数（rolekit.GIVE_UP_AFTER。元の写しの rules の RETRY_MAX と同じ 3）"""
    import rolekit
    return rolekit.GIVE_UP_AFTER


def conflict_item(st, reply, repo, owed: set, try_query=None) -> tuple:
    """phase conflict の返答（どの段でも）の確かめ ——（問題, 申し出の 1 件か None）。名指しが現物に在れば問題は空で、止め方
    （振り分けの段は義務から外す・ほかの段は作業ツリーを単位の頭に戻して次の単位へ）は呼び手（route._conflict・tdd._conflict）。
    owed は申し出てよい単位、try_query は conflict.problems に渡す。盤面の控えに積むのは節（盤面を開く口）"""
    from src import runvals
    import planbrief
    extra = sorted(set(reply) - {"phase", *conflict.FIELDS, conflict.CORRECT})
    if extra:
        return [f"食い違いの申し出の欄は phase と {list(conflict.FIELDS)}（query なら {conflict.CORRECT} も）だけ（{extra}）"], None
    item = {k: reply.get(k) for k in conflict.FIELDS}
    if conflict.CORRECT in reply:
        item[conflict.CORRECT] = reply[conflict.CORRECT]
    board_dir = pathlib.Path(st["work"]).parent
    probs = conflict.problems([item], repo=repo, board_dir=board_dir, owed=owed, request_file=runvals.read(board_dir)["request_file"],
                              try_query=try_query, briefs=planbrief.by_unit_at(board_dir))
    return (probs, None) if probs else ([], item)
