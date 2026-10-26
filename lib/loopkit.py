"""TDD の輪と、輪と同じ形の状態を回す振り分けと、受け付け・事後の関門が共に使う部品（`workflows/fix/src/common.py` から出した物。
docs/plans/2026-10-27-fix-weapons-stage2-e2.md の 1 節）。実行基盤を知らず、置き場は引数のパスで受ける。名は移す前のまま
（下線つきの名も。`workflows/weapon-tdd/src/` が同じ名で読む）。中身は移す前のまま:
- 版を木に固める・戻す（snapshot・touched・restore・restore_paths・hashes）
- 赤の判定の口（red_check と引用の照らし）・test_cmd を走らせる口（_cmd_run・_cmd_material）
- 輪の状態の読み書き（load_state・_load・_save）と状態の欄の小さな読み口（_owed・_unit・_contract・_plan_tdd・_verified）、
  止めた申し出の流し（flush_unsent・flush_claims）
- 輪の状態の骨（BASE_FIELDS・skeleton）・輪の記録の写し（RECORD_UNIT・record）・組の出口の行（FIELDS・exit_rows）
- test_files の要素の決まり（test_file・unit_test_files）・申し出の確かめ（conflict_item。置き場は引数で受ける）
"""
import hashlib
import json
import os
import pathlib
import posixpath
import shlex
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

import baseline_red  # noqa: E402  （赤・緑の判定と実行器を走らせる口の正本）
import cite  # noqa: E402  （名指しの形・引いた文が現物に在るかの照らし。寄せた後の部分一致 quoted_in）
import conflict  # noqa: E402  （食い違いの申し出の確かめ）
import impact  # noqa: E402  （変更に当たる試験の選び）
import leftovers  # noqa: E402
import oneline  # noqa: E402
import tree_run  # noqa: E402
from leftovers import git, git_names  # noqa: E402
from planmarks import test_functions  # noqa: E402  （テストの関数の id（node id の形）→ 源の引き）


MIN_WHY = 10


MIN_QUOTE = 3   # 赤の引用の下限（寄せた字数。1〜2 字の引用はどの失敗の文にも当たるので、照らす先が短くなければ拒む）


QUOTES_FIELD = "red_quotes"   # test の段の返答の欄と単位の記録の欄の名: {名指しの id: {quote: 失敗の文, why: なぜ期待どおりの理由か}}


UNSENT = "unsent"   # 状態の欄: 盤面へまだ積んでいない止めた申し出の並び（行 {source, item}）


# run の test_cmd の関門（start が 1 回だけ決める）: on＝緑の後に毎回走らせる・same_as_suite＝実行器がそのコマンドを包んだ物で
# 一式の緑と同じ（走らせない）・off＝空か、輪の頭で赤・走らない（理由は状態の test_cmd_note）。1 行ずつ定義する（根の柵の
# doc-symbols が文書の名指しを `^名前 =` の行で引く）
GATE_ON = "on"


GATE_OFF = "off"


class Broken(Exception):
    """回す側の誤り（状態が読めない・輪が済んだ後に呼んだ・入力の形が違う）。節は 2 で落ちる"""


def rules():
    """赤・緑の判定の正本のモジュール（lib/baseline_red。red_problems・green_problems・match_case・parse_junit）。元は写しの TDD 版の
    rules（review-loop-tdd.py）を盤面の graph から読んだ"""
    return baseline_red


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


def _blank(s) -> bool:
    return not isinstance(s, str) or len(s.strip()) < MIN_WHY


def _reached(st, repo, seeds=None, direct_only=True) -> tuple[list, bool]:
    """緑の回に足す試験 ——（根からの相対の試験のファイル, 一式を回すか）。単位の頭からの変更（走らせて出来たファイルを
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
    return [f for f in sel["selected"] if impact.PYTEST_FILE.match(posixpath.basename(f)) and (pathlib.Path(repo) / f).is_file()
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



# 事後の関門の束（同じブロックの fixgates。計画 220 Task 4）が輪と同じ決まりで読む口の公開の別名（輪の中の名は変えない。
# 名指しの外の既存のテストの書き換え・名指しの node id・関数の幅・範囲の外の差分の塊。preflight F11・F13）
unnamed_edits = _unnamed_edits


abs_ids = _abs_ids


def retry_max() -> int:
    """段ごとの諦めの回数（rolekit.GIVE_UP_AFTER。元の写しの rules の RETRY_MAX と同じ 3）"""
    import rolekit
    return rolekit.GIVE_UP_AFTER


def conflict_item(st, reply, repo, owed: set, try_query=None, *, request_file, cite_root, briefs_by_unit) -> tuple:
    """phase conflict の返答（どの段でも）の確かめ ——（問題, 申し出の 1 件か None）。名指しが現物に在れば問題は空で、止め方
    （振り分けの段は義務から外す・ほかの段は作業ツリーを単位の頭に戻して次の単位へ）は呼び手（route._conflict・tdd._conflict）。
    owed は申し出てよい単位、try_query は conflict.problems に渡す。盤面の控えに積むのは節（盤面を開く口）。
    置き場は状態から引かず呼び手が値で渡す: request_file は依頼のファイル、cite_root は名指しを許す作業ツリーと依頼のファイルの外の根
    （conflict.problems の board_dir）、briefs_by_unit は今の周の brief の行（planbrief.by_unit_at の値）"""
    extra = sorted(set(reply) - {"phase", *conflict.FIELDS, conflict.CORRECT})
    if extra:
        return [f"食い違いの申し出の欄は phase と {list(conflict.FIELDS)}（query なら {conflict.CORRECT} も）だけ（{extra}）"], None
    item = {k: reply.get(k) for k in conflict.FIELDS}
    if conflict.CORRECT in reply:
        item[conflict.CORRECT] = reply[conflict.CORRECT]
    probs = conflict.problems([item], repo=repo, board_dir=cite_root, owed=owed, request_file=request_file,
                              try_query=try_query, briefs=briefs_by_unit)
    return (probs, None) if probs else ([], item)


def test_file(f) -> str | None:
    """TDD の輪の単位の test_files の要素の決まり: 空でない文字列を posixpath.normpath で整えたパス（ほかは None）。書き手
    tddloop の確かめ（要素が 1 つでも外れれば並びごと拒む）と読み手 unit_test_files（外れた要素を落とす）がここから引く"""
    return posixpath.normpath(f.strip()) if isinstance(f, str) and f.strip() else None


def unit_test_files(unit) -> list:
    """TDD の輪の単位の行の test_files のうち、決まり（test_file）に合う要素だけを整えた並び（子の result.json の写しも読む口。
    並びでない test_files は空、形の違う要素は落とす）"""
    files = (unit or {}).get("test_files")
    if not isinstance(files, list):
        return []
    return [p for p in map(test_file, files) if p]


# ---------------------------------------------------------------- 輪の状態の骨・輪の記録・組の出口の行
BASE_FIELDS = ("exe", "suite", "baseline", "baseline_exit", "baseline_cases", "suite_made", "test_cmd", "test_cmd_gate",
               "test_cmd_note", "reused", "related")   # 元の結末の控え base.json から輪の状態へ写す欄（同じ名と形）


def skeleton(base: dict, work, base_file, keys: list, excused: dict, contract: dict, handoff: str, light=()) -> dict:
    """輪の状態の辞書の骨（鍵の並びの 1 か所。振り分けの状態と輪の状態が同じ形を共に使う）。純粋な関数: ファイルも置き場も作らない。
    base は元の結末の控え（BASE_FIELDS の欄を同じ名で写す）、work は状態の置き場、keys は振る単位（open_units）、excused は直す義務から
    外れた単位 {key: 理由}、contract は単位の約束、handoff は輪の頭の木、light は緑の後の test_cmd を走らせない軽量の単位。段は route"""
    return {**{f: base[f] for f in BASE_FIELDS}, "work": str(work), "base_file": str(base_file), "open_units": keys,
            "excused": excused, "handoff": handoff, "phase": "route", "tries": 0, "reason": "", "iterations": 0,
            "runs": 1, "order": [], "units": {}, "queue": [], "cur": 0, "unit_head": "", "green_tree": "",
            "done": False, "note": "", "frozen": {}, "parked": [], "parked_why": {}, "contract": contract,
            "light": sorted(set(light) & set(keys)), "calls": [], "kinds": []}


RECORD_UNIT = {"route": "", "why": "", "tests": [], "test_files": [], "red": "", "green": "", "gave_up": "", "files": [],
               "red_tree": "", "test_hashes": {}}   # 記録の単位の行の欄と、その単位の状態に無い時の値（test_hashes は赤が通った単位にしか付かない）


def record(st, summary: str) -> dict:
    """輪の記録 record.json の中身（形は schemas/tdd-record.schema.json）。輪が抜ける時の状態から、輪の外が読む欄だけを同じ名と形で写す:
    輪の全体の frozen・frozen_tree・handoff・suite_made・no_suite・note・done・calls と summary.md の在りか summary（パスの字）、
    組の結果の tdd の欄（exit_fields の order・parked・parked_why・suite・test_cmd_gate・test_cmd_note・reused・related）、単位ごと
    （order の単位）の RECORD_UNIT の欄。どの抜け方でも同じ形で書く（諦めた・direct の単位には test_hashes が無いので {} に揃える）"""
    units = {k: {f: json.loads(json.dumps(st["units"][k].get(f, default))) for f, default in RECORD_UNIT.items()} for k in st["order"]}
    return {"frozen": st["frozen"], "frozen_tree": st["frozen_tree"], "handoff": st["handoff"], "suite_made": list(st["suite_made"]),
            "no_suite": st.get("no_suite") is True, "note": st["note"], "done": True, "calls": list(st.get("calls") or []),
            "summary": summary, "order": list(st["order"]), "parked": list(st.get("parked") or []),
            "parked_why": dict(st.get("parked_why") or {}), "suite": st["suite"], "test_cmd_gate": st.get("test_cmd_gate", GATE_OFF),
            "test_cmd_note": st.get("test_cmd_note", ""), "reused": dict(st.get("reused") or {}), "related": dict(st.get("related") or {}),
            "units": units}


FIELDS = ("unit_key", "route", "why", "tests", "test_files", "red", "green", "refactor", "gave_up", "problems", QUOTES_FIELD,
          "quote_unchecked", "stub_files", "test_cmd", "refactor_why")


def exit_rows(st) -> dict:
    """出口の欄 tdd のうち、輪の状態（済んだ物）から組む部分: {ran: true, suite, reason, units: [{FIELDS の欄}], test_cmd: {gate, note}, calls}
    と、あれば reused・related・no_suite（状態が実行器の止まりで輪を止めた時。reason は状態の note）。単位の行は order の単位、続けて
    振り分けの段で止めた単位（parked の行。why は parked_why）。欄の意味は tdd.exit_fields の docstring。組の頭の返りの印（組の頭・
    受け付けが no-suite で止めた組）は呼び手が重ねる"""
    rows = [{f: st["units"][k][f] for f in FIELDS} for k in st["order"]]
    rows += [{**{f: _unit(k, "parked")[f] for f in FIELDS}, "why": st.get("parked_why", {}).get(k, "")}
             for k in st.get("parked", []) if k not in st["order"]]   # 振り分けの段で止めた単位
    out = {"ran": True, "suite": st["suite"], "reason": st["note"], "units": rows,
           "test_cmd": {"gate": st.get("test_cmd_gate", GATE_OFF), "note": st.get("test_cmd_note", "")},
           "calls": st.get("calls", [])}
    if st.get("reused"):
        out["reused"] = st["reused"]
    if st.get("related", {}).get("applied"):
        out["related"] = st["related"]
    if st.get("no_suite") is True:
        out.update(no_suite=True, reason=st["note"])
    return out
