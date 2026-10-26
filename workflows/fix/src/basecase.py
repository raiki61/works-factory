"""組の元の結末（docs/plans/2026-10-24-fix-weapons.md の 2.1 の base。型を問わない部品）。

組の子の頭（group-start。実行器を書き直した後のやり直しは suitefix.retry）が、木を写した後・振り分けと注文の前に 1 度だけ、直す前の
版で関わる試験を走らせて元の結末を取り、組の置き場の base.json に書く。どの型の受け付けも、この 1 つのファイルで元の結末を読む
（今までは TDD の輪の頭が取って輪の状態に書き、輪の無い組では受け付けが試験を走らせなかった）。

- take(place, repo, values, keys, reuse, *, words) -> 頭の返り: 元の結末を取り base.json を書く。取り方は今の輪の頭のまま
  （関わる試験が引ければそれだけ・引けなければ一式・関わる試験が 0 本なら走らせずに []。持ち主の決め related-tests-only）
- read(place) / path(place): base.json の読み口
- no_tests の決め（_no_tests）: 起点の木に試験らしい名のファイルが 1 本も無い時だけ、試験を走らせずに対象の宣言の一覧 list を
  起点の木の宣言（git show <rev>:.review-checks.json）から読んで走らせ、一覧が 0 件で元の結末も 0 件の時だけ真（持ち主の答え 9.1 の 12）
- suite_made_all(place): 置き場の base.json・accept.json、写した bases/<k>/、returns/ の全部と、輪の状態の suite_made の和

base.json の欄は今の輪の状態のうち受け付けが元の結末として読む欄と同じ名と形（work・exe・suite・baseline・baseline_exit・
baseline_cases・suite_made・test_cmd・test_cmd_gate・test_cmd_note・reused・related）と、rev・taken・no_tests・test_list・
suite_by_factory。取り直すのは実行器を書き直した後（suitefix.retry）だけで、ほかは書き換えない。
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import conflict          # lib/
import impact            # lib/
import jsonfile          # lib/
import leftovers         # lib/
import oneline           # lib/
import planmarks         # lib/
import related           # lib/
import tree_run          # lib/
from graphloops.engine import declared   # lib/
from baseline_red import exe_path, run_suite   # lib/

import loopkit  # noqa: E402  （lib。輪と修正の block の両方が使う部品）
from src import common, files

NO_SUITE = "テストの実行器（入力 tdd_suite）が無い run"
NO_EXE = "テストの実行器 {suite} が無いか実行できない"
NO_CASES = "元の結末が取れない（{why}）"
STATIC_ONLY = "組の単位が全部 static（試験で示す物の無い直し）——元の結末は取らない"
SUITE_BROKEN = ("工場が書いた試験の起動スクリプトが壊れている——関わる試験が起動スクリプト越しにだけ中身に届く前に落ちた（{what}。ログ {log}）"
                "のに、test_cmd を単体で走らせると通る（ログ {cmd_log}）")
# 一覧の控え test_list の status の語
LISTED, SKIPPED, ABSENT, FAILED = "listed", "skipped", "absent", "failed"
LIST_TAIL = tree_run.SETUP_TAIL


def path(place) -> pathlib.Path:
    return pathlib.Path(place) / files.BASE_FILE


def read(place) -> dict | None:
    """置き場の base.json（無い・読めなければ None）"""
    got = jsonfile.read_or(path(place))
    return got if isinstance(got, dict) else None


def read_file(base_file) -> dict | None:
    """base.json のパスから読む（空・無い・読めなければ None）"""
    if not base_file or not pathlib.Path(base_file).is_file():
        return None
    got = jsonfile.read_or(base_file)
    return got if isinstance(got, dict) else None


def take(place, repo, values: dict, keys: list, reuse, *, words: dict, rev: str, round_: int = 1, narrow=None) -> dict:
    """元の結末を取り base.json を書く。返り（組の頭の返り。tdd-start.json に書く）{go, reason, suite, base_file, state_file,
    summary_file[, suite_broken, runner_log, cmd_log]}。go は輪の状態がまだ無いので偽（振り分けと注文が状態を置いた時に真にする）。
    words は単位 → 計画の語（route.plan_words）。取るのは実行器が在り、組に計画の語が static でない単位が 1 つ以上在る時。
    static だけの組は実行器が在れば taken: false・baseline: {} で書く（受け付けは赤が出た時だけ版の写しで走らせ直す）。
    narrow は関わる試験だけで取るか（None は related.applies。持ち主の決め related-tests-only）"""
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    suite = str(values.get("tdd_suite") or "").strip()
    out = {"go": False, "reason": "", "suite": suite, "base_file": "", "state_file": "", "summary_file": ""}
    if not suite:
        return {**out, "reason": NO_SUITE}
    exe = exe_path(repo, suite)
    if not exe.is_file() or not (suite.endswith(".py") or os.access(exe, os.X_OK)):
        return {**out, "reason": NO_EXE.format(suite=suite)}
    work = place / files.BASE_DIR
    work.mkdir(parents=True, exist_ok=True)
    test_cmd = str(values.get("test_cmd") or "").strip()
    doc = {"work": str(work), "exe": str(exe), "suite": suite, "rev": rev, "taken": False, "baseline": {}, "baseline_exit": 0,
           "baseline_cases": [], "suite_made": [], "test_cmd": test_cmd, "test_cmd_gate": loopkit.GATE_OFF, "test_cmd_note": "",
           "reused": {}, "related": {"applied": False}, "no_tests": False,
           "test_list": {"status": SKIPPED, "argv": [], "count": 0, "why": "", "log": ""},
           "suite_by_factory": values.get("suite_made") is True}
    if keys and not any(words.get(k) != "static" for k in keys):
        jsonfile.write(path(place), doc)
        return {**out, "reason": STATIC_ONLY, "base_file": str(path(place))}
    narrow = related.applies(repo, test_cmd) if narrow is None else narrow
    picked = _related_pick(place, repo, keys, round_, work) if narrow else None
    note: dict = {}
    if picked is None or picked["whole"]:
        cases, code, why = run_suite(str(exe), repo, work, 0, reuse=reuse, note=note)
    elif picked["files"]:
        cases, code, why = run_suite(str(exe), repo, work, 0, args=related.args(repo, picked), only=True, reuse=reuse, note=note)
    else:
        cases, code, why = [], 0, []   # 関わる試験が無い: 元の結末は空（緑の確かめは受け付けと最後のテストの段が持つ）
    if doc["suite_by_factory"] and test_cmd:
        broke = _suite_broken(exe, repo, work, test_cmd, cases, why, narrow=picked is not None and not picked["whole"])
        if broke:
            return {**out, **broke}
    if cases is None:
        return {**out, "reason": NO_CASES.format(why="; ".join(why))}
    jsonfile.write(place / conflict.BROKEN_TESTS_FILE, {"tests": broken_related(place, repo, keys, round_, work, cases, picked)})
    gate, gate_note, gate_made = _test_cmd_gate(exe, test_cmd, repo, work / "test-cmd-0.log", reuse=reuse)
    doc.update(taken=True, baseline={loopkit._key(c): c["outcome"] for c in cases}, baseline_exit=code, baseline_cases=cases,
               suite_made=gate_made, test_cmd_gate=gate, test_cmd_note=gate_note,
               reused={"suite": t} if (t := tree_run.reused_text(note)) else {},
               related={"applied": True, **picked} if picked is not None else {"applied": False})
    doc["test_list"], doc["no_tests"] = _no_tests(place, repo, rev, keys, round_, cases)
    jsonfile.write(path(place), doc)
    return {**out, "base_file": str(path(place))}


def _declared(place, keys, round_: int) -> set:
    """起点の木の試験のファイルの宣言: 組の項目の計画の欄の受け入れの試験 tests と書き換えの試験 rewrite_tests のパス（base.json は
    注文より前に取るので、注文の名指しの代わりに計画から引く）"""
    try:
        fields = conflict.frozen_fields(pathlib.Path(place), round_) or []
    except ValueError:
        fields = []
    out = set()
    for f in fields:
        if not isinstance(f, dict) or not set(f.get("unit_keys") or []) & set(keys):
            continue
        for k in ("tests", "rewrite_tests"):
            for row in f.get(k) or []:
                i = row.get("id") if isinstance(row, dict) else None
                if isinstance(i, str) and i.strip():
                    out.add(loopkit.id_path(i))
    return out


def _no_tests(place, repo, rev: str, keys, round_: int, cases) -> tuple[dict, bool]:
    """（一覧の控え test_list, 印 no_tests）。(1) 起点の木に試験のファイル（impact.is_test_file）が 1 本も無い (2) 対象の宣言の一覧が
    0 件 (3) 元の結末が 0 件 の 3 つが全部の時だけ真。(1) が偽なら一覧を走らせない（skipped）。宣言は起点の木（rev）の物だけを読み
    （写した木の宣言は読まない。前の組・前の段の型が書いた list で決めが組の順で変わらないように）、走らせる所は写した木。
    起点の木の宣言に setup が無ければ setup=[] を渡す（None を渡すと写した木の宣言の setup が走る）"""
    rows = {"status": SKIPPED, "argv": [], "count": 0, "why": "", "log": ""}
    declared_paths = _declared(place, keys, round_)
    try:
        tree = leftovers.git_names(repo, "ls-tree", "-r", "--name-only", rev)
    except common.Unreadable:
        tree = []
    if any(impact.is_test_file(p, declared_paths) for p in tree):
        return rows, False
    text = common._tree_text(repo, rev, declared.DECL_NAME)
    argvs, bad = declared.list_of(text)
    setup, setup_bad = declared.setup_of(text)
    if bad or setup_bad:
        return {**rows, "status": FAILED, "why": bad or setup_bad}, False
    if not argvs:
        return {**rows, "status": ABSENT, "why": (f"修正前の版の {declared.DECL_NAME} に試験の一覧のコマンド list が無い"
                                                  "（run の中で足した list は読まない）")}, False
    log = pathlib.Path(place) / files.BASE_DIR / "test-list.log"
    count = 0
    for argv in argvs:
        got, why = _list_run(argv, repo, log, setup)
        if got is None:
            return {**rows, "status": FAILED, "argv": argvs, "why": why, "log": str(log)}, False
        count += got
    listed = {**rows, "status": LISTED, "argv": argvs, "count": count, "log": str(log)}
    return listed, count == 0 and not cases


def _list_run(argv, repo, log: pathlib.Path, setup) -> tuple[int | None, str]:
    """一覧の argv を作業ツリーの根で 1 つ起こし、標準出力の空でない行を数える ——（件数か None, 訳）。shell を通さない。
    tree_run.run に起点の木の setup を渡す（[] は準備なし）。終了の値が 0 でない・起こせない時は None と訳（末尾は SETUP_TAIL）"""
    log.parent.mkdir(parents=True, exist_ok=True)
    out = log.with_suffix(f".{len(argv)}.out")
    try:
        with open(out, "wb") as f, open(log, "ab") as err:
            code = tree_run.run(argv, setup=list(setup), env=tree_run.outside_env(os.environ), cwd=str(repo),
                                stdin=subprocess.DEVNULL, stdout=f, stderr=err)
    except OSError as e:
        return None, f"list の {argv} を起こせない: {oneline.one_line(e)}"
    text = out.read_bytes().decode("utf-8", "replace")
    with open(log, "ab") as f:
        f.write(out.read_bytes())
    if code != 0:
        return None, f"list の {argv} が終了コード {code} で終わった。末尾: {oneline.one_line(text[-LIST_TAIL:])}"
    return sum(1 for line in text.splitlines() if line.strip()), ""


def _related_pick(place, repo, keys, round_: int, work: pathlib.Path) -> dict:
    """元の結末を絞る選び（related.pick）。起点は、組の単位を持つ凍結した欄の files の path。欄の控えが無い run や起点が 1 つも
    無い時は、選べない（whole）として一式。欄の控えが凍結の印と食い違えば、理由の文のまま Broken（黙って一式にしない）"""
    try:
        fields = conflict.frozen_fields(pathlib.Path(place), round_) or []
    except ValueError as e:
        raise loopkit.Broken(str(e)) from None
    seeds = sorted({str(row["path"]).strip() for f in fields if isinstance(f, dict) and set(f.get("unit_keys") or []) & set(keys)
                    for row in planmarks.file_rows(f) if isinstance(row.get("path"), str) and row["path"].strip()})
    if not seeds:
        return {"whole": True, "reasons": ["修正案が触る所（欄の files）の起点が無い"], "files": [], "left": [], "far": []}
    return related.pick(repo, rev="HEAD", seeds=seeds, cache_dir=work / "impact")


def broken_related(place, repo, keys, round_: int, work: pathlib.Path, cases, picked=None) -> list:
    """関わる試験で直す前から壊れていた物のファイル [{path, ids}]（#836。docs/design/fix.md の 19 節）: 元の結末で落ちた（failure・
    error）試験のファイルのうち、修正案が触る所に直に関わる試験（_related_pick）に在る物。関わるかを選べない（whole）・落ちた試験が
    無ければ空。修正役はこのファイルをついでに直してよい（conflict.test_permits の 6 つ目の許し）"""
    failed = [c for c in cases or [] if c.get("outcome") in ("failure", "error")]
    if not failed:
        return []
    picked = picked if picked is not None else _related_pick(place, repo, keys, round_, work)
    if picked.get("whole"):
        return []
    near = set(picked.get("files") or [])
    found = {}
    for p, ids in _case_files(repo, failed).items():
        if p in near:
            found[p] = ids
    return [{"path": p, "ids": ids} for p, ids in sorted(found.items())]


def _case_files(repo, cases) -> dict:
    """結末の行 cases → {テストのファイル（根からの相対）: [鍵]}"""
    mods = common._module_files(repo)
    out = {}
    for c in cases:
        for p in mods.get(impact._junit_module(c) or "", []):
            out.setdefault(p, []).append(loopkit._key(c))
    return out


def _suite_broken(exe, repo, work: pathlib.Path, test_cmd: str, cases, why, *, narrow: bool) -> dict | None:
    """起動スクリプトが壊れているか（yes/no。#836）: 元の結末の回が結末を返さないか、試験が 1 件でも error で、test_cmd を単体で
    走らせると緑なら壊れている。関わる試験だけを渡した回（narrow）は、実行器を一式でも 1 回走らせ、それも同じく落ちる時だけ
    壊れていると読む。壊れていれば {suite_broken, reason, runner_log, cmd_log}、でなければ None"""
    def fell(got) -> bool:
        return got is None or any(c.get("outcome") == "error" for c in got)
    if not fell(cases):
        return None
    log = work / "suite-0.log"
    what = "; ".join(why) if cases is None else f"error {sum(1 for c in cases if c.get('outcome') == 'error')} 件"
    cmd_log = work / "test-cmd-alone.log"
    mat, _ = loopkit._cmd_run(repo, test_cmd, cmd_log)
    if mat["status"] != "clean":
        return None
    if narrow:
        whole, _, whole_why = run_suite(str(exe), repo, work, "whole")
        if not fell(whole):
            return None
        log = work / "suite-whole.log"
        what = "; ".join(whole_why) if whole is None else f"error {sum(1 for c in whole if c.get('outcome') == 'error')} 件"
    return {"suite_broken": True, "reason": SUITE_BROKEN.format(what=what, log=log, cmd_log=cmd_log),
            "runner_log": str(log), "cmd_log": str(cmd_log)}


def _test_cmd_gate(exe: pathlib.Path, cmd: str, repo, log: pathlib.Path, *, reuse=None) -> tuple[str, str, list]:
    """(関門, 理由, 走らせて出来たファイル)。空は (off, "", [])。実行器のファイルの中身が cmd をそのまま含めば (same_as_suite, "", [])。
    ほかは loopkit._cmd_run で 1 回走らせ、緑なら on、赤・走らないなら off と理由"""
    if not cmd:
        return loopkit.GATE_OFF, "", []
    try:
        if cmd in exe.read_text(encoding="utf-8", errors="replace"):
            return common.GATE_SAME, "", []
    except OSError:
        pass   # 読めない実行器は包みと見なさず、走らせて決める
    mat, made = loopkit._cmd_run(repo, cmd, log, reuse=reuse)
    if mat["status"] == "clean":
        return loopkit.GATE_ON, "", made
    if mat["status"] == "found":
        return loopkit.GATE_OFF, (f"run の test_cmd（{cmd}）がループの頭で赤（{mat.get('rewrote') or f'元から赤。ログ {log}'}）——"
                                 "単位ごとに確かめると毎単位を拒むのでこのループでは確かめない（一式の緑はメイングラフの最後のテストの段が確かめる）"), made
    return loopkit.GATE_OFF, f"run の test_cmd（{cmd}）をループの頭で走らせられない（{mat.get('reason', '')}）——このループでは確かめない", made


def suite_made_all(place) -> set:
    """run の全体の suite_made の和（下書き 2.1 の「run の全体の suite_made の和」）: 置き場の輪の状態の全部（common.suite_made_all。
    今の和を外さない）・置き場の base.json と accept.json・写した bases/<k>/ の base.json と accept.json の全部・returns/ の全部"""
    place = pathlib.Path(place)
    docs = [place / files.BASE_FILE, place / files.ACCEPT_FILE]
    bases = place / files.BASES_DIR
    for d in sorted(bases.glob("*")) if bases.is_dir() else []:
        docs += [d / files.BASE_FILE, d / files.ACCEPT_FILE]
    rets = place / files.RETURNS_DIR
    docs += sorted(rets.glob("*.json")) if rets.is_dir() else []
    out = set(common.suite_made_all(place))
    for p in docs:
        doc = jsonfile.read_or(p) if p.is_file() else None
        if isinstance(doc, dict):
            out |= {f for f in doc.get("suite_made") or [] if isinstance(f, str)}
    return out
