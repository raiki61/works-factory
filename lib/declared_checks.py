"""CI の節（修正前の p0.local_checks・修正後の p4.ci）を盤面なしで走らせる口: 対象の宣言（.review-checks.json）の段と test_cmd を
走らせ、素材（material）を組み、任せ先の役の素材の欄の決まりを照らす。名は今の works の CI の節の語 CI_BUILTIN（entry.py:442）。

今の works（版 2aa7c66cf7abe1fe09699ac2942d107123214168）の関数を元の名で写した物（各関数の docstring の末尾に元の `<パス>:<行>`）。
盤面の引数 b・記録への控え（process.checks）・試験の枠と控え（tree_run.slotted_run・同じ run の中の使い回し）・台帳の人待ちは外した。
- 字のまま（継ぎ目の直しだけ）: TEST_CMD_STEP・local_checks_material・_nice19・_launched・_cmd_material・_same_step・env_only_red・
  _suite_kind・suites_line・CiRefused（InputRefused ごと）・_with_test_cmd・_junit_unran・_tail（TAIL_LINES・TAIL_BYTES ごと）
- 書き直し: tree_runner・_engine_log・checks_plan・checks_reply・_skipped_note・run_ci
- 新しい関数: material_problems
"""
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import time

import baseline_red
import checkscope
import gatemarks
import tree_run

_GL = pathlib.Path(__file__).resolve().parent / "graphloops"
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

from engine import declared  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

DECL_NAME = declared.DECL_NAME
TEST_CMD_STEP = "test_cmd"
TAIL_LINES = 20      # 走らせた語の出力のうち、返答に写す末尾の行数（全体は置き場のファイルに残す）
TAIL_BYTES = 2000    # その上限（バイト）。1 行が長い出力で返答が膨らまないように

# 素材の欄の決まり（material_problems）。出どころは今の works の写しの graph（works/.shared/core/graphloops/graphs/review-loop.json）の
# p0.local_checks・p4.ci の schema と、検証器の素材の表（works/.shared/core/scripts/review-record.py:140-151 の STATUS・351 の NUMERIC_FIELDS）
STATUSES = ("found", "clean", "not_applicable", "awaiting_human", "not_run")
FIELDS = ("count", "detail", "checked", "reason")
STATUS_FIELDS = {"found": ("count", "detail"), "clean": ("checked",), "not_applicable": ("reason",),
                 "awaiting_human": ("reason",), "not_run": ("reason",)}
NUMERIC_FIELDS = ("count",)
MATERIAL_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["status"],
                   "properties": {"status": {"type": "string", "enum": list(STATUSES)},
                                  **{k: {"type": "integer", "minimum": 0} if k in NUMERIC_FIELDS else {"type": "string"}
                                     for k in FIELDS}}}
CANT = {False: "awaiting_human", True: "not_run"}   # 走らせられない時の status（判定の前・後。after_judge か mode == "final" で引く）


class InputRefused(Exception):
    """入力を受けない（AI を起こす前に run を止める）。文は人に向けた 1 行（元 works/.shared/core/entry.py:445-449）"""

    def __init__(self, msg):
        super().__init__(" ".join(str(msg).split()))


class CiRefused(InputRefused):
    """CI の節を走らせられない（範囲の宣言の誤り・宣言に無い段の名・範囲の宣言だけが在る）。走らせる前に止める
    （元 works/.shared/core/entry.py:452-453）"""


def _tail(data):
    """元 works/.shared/core/graphloops/engine/role_run.py:513-515"""
    text = data.decode("utf-8", "replace").rstrip()
    return "\n".join(text.splitlines()[-TAIL_LINES:])[-TAIL_BYTES:]


# ---------------------------------------------------------------- test_cmd
def local_checks_material(repo: pathlib.Path, test_cmd: str, log_path: pathlib.Path, *, launched: dict | None = None,
                          niced: bool = False) -> dict:
    """任せ先に落ちた CI の節に渡す素材 {"material": …} を組む。
    test_cmd を tree_run.command_argv の形（direct か shell）で tree_run.run に走らせ（対象の根で・標準入力は空・環境は
    tree_run.outside_env。標準出力と標準エラーを log_path に）、終了コード 0 なら clean（checked が要る）、他は found・count 1。
    detail はログの末尾（宣言の段の末尾と同じ切り方）。起こせなければ（shell の先頭の語が tree_run.prove_launchable の証明を
    通らない回も）not_run。test_cmd が空なら走らせずに not_run。
    止められたら（tree_run.Stopped）捕まえない。launched（dict）を渡せば、起こす前に決めた起こし方を launched["how"] に置く。
    niced が真なら、起こすプロセスの優先度を nice -n 19 と同じだけ下げる（argv・起こし方・起こせなさの証明は変えない）
    （元 works/.shared/core/entry.py:650-677。tree_run.slotted_run を tree_run.run に替え、使い回しの欄は書かない）"""
    cmd = (test_cmd or "").strip()
    if not cmd:
        return {"material": {"status": "not_run", "reason": "テストのコマンド（test_cmd）が空で、走らせる物が無い"}}
    log_path = pathlib.Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    argv, how = tree_run.command_argv(cmd)
    launched = {} if launched is None else launched
    launched["how"] = how
    with open(log_path, "wb") as f:
        try:
            code = tree_run.run(argv, env=tree_run.outside_env(os.environ), stdin=subprocess.DEVNULL,
                                stdout=f, stderr=subprocess.STDOUT, cwd=str(repo),
                                **({"preexec_fn": _nice19} if niced else {}))
        except OSError as e:
            return {"material": {"status": "not_run", "reason": f"{_launched(argv, how)} でテストのコマンドを起こせない: {e}"}}
    return _cmd_material(code, log_path, argv, how)


def _nice19() -> None:
    """子の中で exec の前に呼ぶ（Popen の preexec_fn）: nice -n 19 と同じだけ優先度を下げる（元 works/.shared/core/entry.py:680-682）"""
    os.nice(19)


def _launched(argv: list, how: str) -> str:
    """元 works/.shared/core/entry.py:685-686"""
    return f"{shlex.join(argv)}（起こし方 {how}{'。' + tree_run.DIRECT_HINT if how == 'direct' else ''}）"


def _cmd_material(code: int | None, log_path: pathlib.Path, argv: list, how: str) -> dict:
    """走らせ終えた test_cmd の終了コードとログから素材を組む。argv・how は起こした時に決めた値（読む時に規則で作り直さない）。
    分け方は tree_run.launch_kind: 起こせない（exit None）は not_run（元 works/.shared/core/entry.py:689-703）"""
    argv = list(argv)
    tail = _tail(log_path.read_bytes())
    kind = tree_run.launch_kind(code)
    if kind == "broken":
        return {"material": {"status": "not_run",
                             "reason": f"{_launched(argv, how)} でテストのコマンドを起こせない（exit None。ログ {log_path}）"}}
    ran = f"{shlex.join(argv)}（起こし方 {how}）を対象の根で走らせた: exit {code}（ログ {log_path}）"
    if kind == "clean":
        return {"material": {"status": "clean", "count": 0, "checked": ran, "detail": tail}}
    return {"material": {"status": "found", "count": 1,
                         "detail": f"{ran} ／ 末尾: {tail} ／ {gatemarks.BASELINE_UNVERIFIED}（test_cmd は shell の文字列で、試験の報告を宣言できない）"}}


def _same_step(steps: list, argv: list, how: str) -> str | None:
    """test_cmd を直に起こす形（how が direct）の argv が宣言の段の argv と同じなら、その段の名（同じコマンドを
    2 度走らせない）。シェルを通す test_cmd は宣言の段（シェルを通さない）と同じにならない（元 works/.shared/core/entry.py:742-747）"""
    if how != "direct":
        return None
    return next((s.get("name") for s in steps if list(s.get("argv") or []) == argv), None)


def _with_test_cmd(runner, test_cmd: str, note: dict):
    """runner (steps, cwd, log_dir) -> runs を包み、宣言の段の後に test_cmd の段を 1 つ足す。runner は steps + [test_cmd の段] で
    1 度だけ呼ぶ（ログは段の番号で分かれる）。test_cmd が宣言の段と同じコマンドなら足さず、note["same_as"] にその段の名を置く。
    test_cmd が空なら足さない。段の起こし方 how は起こす前に決め（足す段は tree_run.command_argv の値、宣言の段はシェルを
    通さないので direct）、走った行に写す（元 works/.shared/core/entry.py:750-765。既定の runner を tree_runner に替えた）"""
    cmd = (test_cmd or "").strip()
    argv, how = tree_run.command_argv(cmd) if cmd else (None, None)

    def run(steps, cwd, log_dir):
        note["same_as"] = _same_step(steps, argv, how) if cmd else None
        extra = [{"name": TEST_CMD_STEP, "argv": argv, "how": how}] if cmd and not note["same_as"] else []
        hows = ["direct"] * len(steps) + [s["how"] for s in extra]
        rows = (runner or tree_runner)(list(steps) + extra, cwd, log_dir)
        return [{**r, "how": h} for r, h in zip(rows, hows)]
    return run


# ---------------------------------------------------------------- 一式の結末の読み方
def env_only_red(tests: dict | None) -> bool:
    """最後のテストの赤が、全部起こせなかった段（tree_run.launch_kind の broken）だけから来ているか（元 works/.shared/core/entry.py:768-772）"""
    kinds = [_suite_kind(s) for s in (tests or {}).get("suites") or []]
    bad = [k for k in kinds if k != "clean"]
    return bool(bad) and all(k == "broken" for k in bad)


def _suite_kind(s: dict) -> str:
    """段 {name, exit, how?, launch?} の分類（tree_run.launch_kind。exit None は broken、他は clean・red）。前の版の記録に残る
    launch の値は読まない（分類は終了コードだけで決まる）（元 works/.shared/core/entry.py:775-778）"""
    return tree_run.launch_kind(s.get("exit"))


def suites_line(tests: dict | None, *, role_status: str | None = None) -> str:
    """最後のテスト（{suites, by, test_cmd_same_as, test_cmd_how, skipped_steps}）が走らせた一式・環境で起こせなかった段・
    走らせなかった物（範囲の外で回さなかった段を名と範囲で含む）の 1 行。起こし方（段の how か、test_cmd の段なら test_cmd_how の direct・shell）が在れば添える。
    role_status は任せ先の CI の役が渡した素材の status。走らせたと書くのは素材が clean・found の時だけ（not_run などは走らせなかった側に）
    （元 works/.shared/core/entry.py:819-855。board.scope_word を checkscope.scope_word に替えた）"""
    tests = tests or {}
    by = tests.get("by")
    suites = tests.get("suites") or []
    same = tests.get("test_cmd_same_as")
    kinds = [_suite_kind(s) for s in suites]

    def how(s):
        got = s.get("how") or (tests.get("test_cmd_how") if s.get("name") == TEST_CMD_STEP else None)
        return f"・{got}" if got else ""

    ran = [f"{s.get('name')}（exit {s.get('exit')}{how(s)}）" for s, k in zip(suites, kinds) if k != "broken"]
    broken = [f"{s.get('name')}（起こせない{how(s)}）" for s, k in zip(suites, kinds) if k == "broken"]
    direct_broken = any(k == "broken" and s.get("how") == "direct" for s, k in zip(suites, kinds))
    if same:
        ran.append(f"{TEST_CMD_STEP}（宣言の段 {same} と同じコマンドなので 1 度だけ走らせた）")
    unrun = [f"範囲の外で回さなかった段 {checkscope.scope_word(s)}" for s in tests.get("skipped_steps") or []]
    if by == "engine" and not suites:
        unrun.append(f"宣言の段・{TEST_CMD_STEP}（宣言が読めないので engine が走らせなかった）")
    elif by == "engine" and not same and not any(s.get("name") == TEST_CMD_STEP for s in suites):
        unrun.append(f"{TEST_CMD_STEP}（渡されていない）")
    elif by == "role":
        ran = ran or [f"{TEST_CMD_STEP}（{tests['test_cmd_how']}）" if tests.get("test_cmd_how") else TEST_CMD_STEP]
        unrun.append("宣言の段（宣言が無いか、engine が任せ先に落ちた）")
    elif by == "role_needed" and role_status in ("clean", "found"):
        ran = [f"任せ先の CI の役 blk-ci が選んだ一式（素材の status {role_status}）"]
    elif by == "role_needed" and role_status is not None:
        unrun.append(f"宣言の段・{TEST_CMD_STEP}（任せ先の CI の役 blk-ci が走らせなかった: 素材の status {role_status or '無い'}）")
    elif by == "role_needed":
        unrun.append(f"宣言の段・{TEST_CMD_STEP}（任せ先の CI の役 blk-ci が走らせる）")
    env = f"／環境で起こせなかった（コードの赤ではない）: {'・'.join(broken)}" if broken else ""
    if direct_broken:
        env += f"（{tree_run.DIRECT_HINT}）"
    return f"走らせた: {'・'.join(ran) or '無い'}{env}／走らせなかった: {'・'.join(unrun) or '無い'}"


# ---------------------------------------------------------------- 宣言の段
def tree_runner(steps: list, cwd, log_dir) -> list:
    """段を 1 つずつ tree_run.run で走らせる: 段の argv は shell を通さない・別のプロセスグループ・期限なし・標準入力は空・uv run の
    環境を外す（tree_run.outside_env）・止められたら木ごと止めて tree_run.Stopped を投げる（ここでは捕まえない）。標準出力・
    標準エラーは log_dir/<段の番号>.out・.err に丸ごと。返りの行は {name, argv, out, err, started, exit, wall_s, tail}（started は
    段を起こした epoch 秒で、試験の報告が今の段の物かを checks_reply が見る。起こせなければ exit None と error）。
    信号で死んだ段の exit は tree_run の 128+信号。同じ run の中の使い回しはしない
    （元 works/.shared/core/board.py:379-433。tree_run.slotted_run を tree_run.run に替え、replay_group・keep_group・note_fields・wait_s を外した）"""
    log_dir = pathlib.Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    env = tree_run.outside_env(os.environ)
    runs = []
    for i, s in enumerate(steps, 1):
        out_path, err_path = log_dir / f"{i}.out", log_dir / f"{i}.err"
        started = time.time()
        row = {"name": s["name"], "argv": list(s["argv"]), "out": str(out_path), "err": str(err_path), "started": started}
        with open(out_path, "wb") as out, open(err_path, "wb") as err:
            try:
                rc = tree_run.run(list(s["argv"]), env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=str(cwd))
            except OSError as e:
                rc = None
                row["error"] = str(e)
                err.write(str(e).encode("utf-8"))
        data = out_path.read_bytes() + b"\n" + err_path.read_bytes()
        row.update(exit=rc, wall_s=round(time.time() - started, 1), tail=_tail(data))
        runs.append(row)
    return runs


def _engine_log(log_path, runs: list, why: str) -> pathlib.Path:
    """走らせた全部の段の標準出力と標準エラーを 1 つのログに並べる（2 段目の赤・標準エラーだけの出力も見えるように。段ごとの元の
    ファイルは runs[].out・err のまま残る）。走らせなかった回（宣言が読めない）は why（素材の理由）を書く
    （元 works/.shared/core/entry.py:716-736。盤面の置き場 b.work と記録の素材 b.record を引数 log_path・why に替えた）"""
    log = pathlib.Path(log_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, r in enumerate(runs, 1):
        how = f"（起こし方 {r['how']}）" if r.get("how") else ""
        parts.append(f"== 段 {i} {r.get('name')}{how}: {json.dumps(r.get('argv'), ensure_ascii=False)} → exit {r.get('exit')}\n")
        if r.get("error"):
            parts.append(f"起こせない: {r['error']}\n")
        for key in ("out", "err"):
            src = r.get(key)
            body = pathlib.Path(src).read_text(encoding="utf-8", errors="replace") if src and pathlib.Path(src).is_file() else ""
            parts.append(f"--- {'標準出力' if key == 'out' else '標準エラー'}（{src}）\n{body}")
            if body and not body.endswith("\n"):
                parts.append("\n")
    if not runs:
        parts.append(f"engine は宣言の段を走らせなかった: {why}\n")
    log.write_text("".join(parts), encoding="utf-8")
    return log


def checks_plan(root) -> dict:
    """走らせる計画: 宣言の段 {steps, sha}・宣言が無ければ任せ先へ {fallback}・宣言の書式の誤りなら走らせずに {blocked}
    （元 works/.shared/core/graphloops/rules/review-loop.py:2199-2208。盤面の外の分）"""
    if not root:
        return {"fallback": "リポジトリのルートが引けない"}
    d = declared.read(root)
    if d is None:
        return {"fallback": f"対象リポジトリに走らせる語の宣言 {DECL_NAME} が無い——任せ先が CI の定義から走らせる（engine は終了コードを見ていない）"}
    if "error" in d:
        return {"blocked": d["error"]}
    return {"steps": d["steps"], "sha": d["sha"]}


def _junit_unran(root, step, row):
    """宣言の段が試験の報告（junit）を持つとき、段が試験を走らせなかった理由（走ったなら None）。見るのは報告の有無・鮮度・件数だけ
    ——実行器の名も終了コードの数値の意味も読まない（ある実行器の終了の値 5 はその実行器だけの意味）
    （元 works/.shared/core/graphloops/rules/review-loop.py:2215-2233）"""
    import xml.etree.ElementTree as ET
    rel = step["junit"]
    path = pathlib.Path(root) / rel if root else None
    if path is None or not path.is_file():
        return f"報告 {rel} が無い"
    if row.get("started") is None or path.stat().st_mtime < row["started"]:
        return f"報告 {rel} が今の段の起動より古い（前の報告は数えない）"
    try:
        cases = list(ET.parse(path).getroot().iter("testcase"))
    except (ET.ParseError, OSError) as e:
        return f"報告 {rel} が XML として読めない（{type(e).__name__}）"
    if not cases:
        return f"報告 {rel} の試験が 0 件"
    if all(c.find("error") is not None for c in cases):
        return f"報告 {rel} の試験 {len(cases)} 件が全部 error（走って落ちた failure でなく、走り始める前に壊れた形）"
    return None


def checks_reply(launch, runs, root, *, after_judge) -> dict:
    """走らせた結果から素材 {status, count?, detail?, checked?, reason?} を組む。走らせられないときは、判定の前（after_judge が偽）なら
    awaiting_human、判定の後なら not_run（人待ちを新しく立てない規則）。
    試験の報告（junit）を宣言した段は、報告の件数で走ったかを見て、走らなかった段を起こせない段と同じ status に落とす。
    報告を宣言していない段の赤は found のまま、走ったかは確かめていないと detail に添える
    （元 works/.shared/core/graphloops/rules/review-loop.py:2236-2271。記録への控え _checks_note と台帳の人待ち _awaiting_origins を外した）"""
    cant = CANT[bool(after_judge)]
    if launch.get("blocked"):
        return {"status": cant, "reason": launch["blocked"]}
    summary = "; ".join(f"{r['name']}: exit {r['exit']}（{r['wall_s']} 秒）" for r in runs)
    broken = [r for r in runs if r["exit"] is None]
    red = [r for r in runs if r["exit"] not in (0, None)]
    decl = {s["name"]: s for s in launch.get("steps") or []}
    unran = {r["name"]: _junit_unran(root, decl[r["name"]], r) for r in runs if r["exit"] is not None and decl.get(r["name"], {}).get("junit")}
    unran = {n: why for n, why in unran.items() if why}
    if broken:
        return {"status": cant, "reason": "宣言の語を起こせない: " + "; ".join(f"{r['name']}: {r.get('error')}" for r in broken)}
    if unran:
        return {"status": cant, "reason": "基準の検査が走らなかった段（コードの赤ではない）: " + "; ".join(f"{n}: {why}" for n, why in unran.items())
                                         + f" ／ 走らせた結果: {summary}"}
    if red:
        unverified = [r["name"] for r in red if not decl.get(r["name"], {}).get("junit")]
        return {"status": "found", "count": len(red),
                "detail": f"engine が宣言 {DECL_NAME} を走らせた: {summary} ／ " + " ／ ".join(f"{r['name']} の末尾: {r['tail'][-600:]}" for r in red)
                          + (f" ／ 走ったかは確かめていない（試験の報告の宣言が無い段: {', '.join(unverified)}）" if unverified else "")}
    return {"status": "clean", "checked": f"engine が宣言 {DECL_NAME}（sha {launch['sha'][:12]}）の {len(runs)} 段を走らせた: {summary}"}


def _skipped_note(skipped: list, material: dict) -> dict:
    """素材の文（clean の checked・found の detail・走らせられない回の reason）の末尾に、範囲の外で回さなかった段を名と範囲で
    足す。回さなかった段が無ければ変えない（元 works/.shared/core/board.py:507-517。返答の包み {"reply": …} を外し、素材を受ける）"""
    key = next((k for k in ("checked", "detail", "reason") if isinstance(material.get(k), str)), None)
    if not skipped or key is None:
        return material
    return {**material, key: f"{material[key]} ／ {checkscope.skipped_text(skipped)}"}


def _junit_reports(root: pathlib.Path, steps: list, runs: list, existed: dict, report_dir) -> tuple:
    """JUnit の報告を宣言して走った段の報告を読み ——（1 件ごとの結末, 段の名, 試験を走らせなかった段の名）。読んだ報告は
    report_dir/<段の名>.xml に写し、走らせる前に無かった報告（existed が偽）は対象の木から消す（未追跡のファイルが増えて
    作業ツリーの指紋が変わり、修正の差分にも紛れるため。前から在った報告は消さない）"""
    decl = {s["name"]: s for s in steps}
    cases, names, unran = [], [], []
    for r in runs:
        step = decl.get(r["name"]) or {}
        if not step.get("junit") or r.get("exit") is None:
            continue
        names.append(r["name"])
        why = _junit_unran(root, step, r)
        if why:
            unran.append(r["name"])
        path = root / step["junit"]
        if not path.is_file():
            continue
        if not why:
            cases += baseline_red.parse_junit(path.read_text(encoding="utf-8", errors="replace"))
        if report_dir is not None:
            pathlib.Path(report_dir).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, pathlib.Path(report_dir) / f"{r['name']}.xml")
        if not existed.get(r["name"]):
            path.unlink()
    return cases, names, unran


def _row(r: dict) -> dict:
    """返りの段の行 {name, exit, how, launch?}（launch は起こせない段だけ broken）"""
    kind = tree_run.launch_kind(r.get("exit"))
    return {"name": r["name"], "exit": r.get("exit"), "how": r.get("how"), **({"launch": kind} if kind == "broken" else {})}


def run_ci(root, *, test_cmd: str, log_dir, changed, after_judge: bool, report_dir=None) -> dict:
    """CI の節を走らせる。返り {by, material, runs, skipped_steps, same_as, log, cases, junit_steps, junit_unran}。
    - 範囲の宣言（checkscope.SCOPE_DECL）が在るのに対象の宣言（DECL_NAME）が無い・範囲の宣言の誤り・宣言に無い段の名は、
      走らせる前に CiRefused（範囲の宣言が黙って効かない形にしない）
    - 宣言が在れば by engine: 範囲の宣言の paths_ignore を changed（変更のパスを返す口。範囲を持つ段が在る時だけ呼ぶ）と照らし、
      変更が全部その下に在る段は回さず skipped_steps に名と範囲で残す。宣言の段の後に test_cmd の段を足し（宣言の段と同じ
      コマンドなら足さず same_as にその段の名）、素材は全部の段から組む——宣言の一式と test_cmd の両方が緑の時だけ clean。
      宣言の書式の誤りは走らせずに走らせられない素材（判定の前は awaiting_human・後は not_run）
    - 宣言が無く test_cmd が在れば by role: test_cmd だけを走らせた素材
    - どちらも無ければ by role_needed: 素材は None（任せ先の CI の役が渡す。前の結果を使ってよい、ではない）
    runs は走った段ごとの {name, exit, how, launch?}。cases は JUnit の報告を宣言して走った段の 1 件ごとの結末（baseline_red.parse_junit
    の形）、junit_steps はその段の名、junit_unran はそのうち試験を走らせなかった段の名。段が対象の木の中に書いた報告は report_dir に
    写し、走らせる前に無かった報告は対象の木から消す。止められたら（tree_run.Stopped）捕まえない
    （元 works/.shared/core/entry.py:858-904 の盤面の外の決まりを、盤面の run_engine の代わりに checks_plan・checkscope・tree_runner・
    checks_reply で組んだ物。scope_changed が足していた依頼の where が名指すパスは持たない——変更は changed だけで受ける）"""
    root = pathlib.Path(root)
    log_dir = pathlib.Path(log_dir)
    if (root / checkscope.SCOPE_DECL).is_file() and not (root / DECL_NAME).is_file():
        raise CiRefused(f"範囲の宣言 {checkscope.SCOPE_DECL} が在るのに、それが段を名指す対象の宣言 {DECL_NAME} が無い"
                        "——範囲の宣言が効かない（宣言を置くか、範囲の宣言を消す）")
    out = {"material": None, "runs": [], "skipped_steps": [], "same_as": None, "log": "", "cases": [], "junit_steps": [],
           "junit_unran": []}
    plan = checks_plan(root)
    if "fallback" in plan:
        if not (test_cmd or "").strip():
            return {**out, "by": "role_needed"}
        log = log_dir / f"{TEST_CMD_STEP}.log"
        return {**out, "by": "role", "material": local_checks_material(root, test_cmd, log)["material"], "log": str(log)}
    steps = plan.get("steps") or []
    launch = {"steps": steps, "sha": plan.get("sha"), "blocked": plan.get("blocked")}
    runs, skipped, note, existed = [], [], {}, {}
    if not launch["blocked"]:
        ignores, why = checkscope.read_scope(root, steps)
        if why:
            raise CiRefused(why)
        skipped = checkscope.skipped_steps(steps, ignores, changed)
        off = {s["name"] for s in skipped}
        todo = [s for s in steps if s["name"] not in off]
        existed = {s["name"]: (root / s["junit"]).exists() for s in todo if s.get("junit")}
        runs = _with_test_cmd(None, test_cmd, note)(todo, root, log_dir)
    material = _skipped_note(skipped, checks_reply(launch, runs, root, after_judge=after_judge))
    cases, junit_steps, junit_unran = _junit_reports(root, steps, runs, existed, report_dir)
    log = _engine_log(log_dir / "checks.log", runs, material.get("reason") or "")
    return {**out, "by": "engine", "material": material, "runs": [_row(r) for r in runs], "skipped_steps": skipped,
            "same_as": note.get("same_as"), "log": str(log), "cases": cases, "junit_steps": junit_steps,
            "junit_unran": junit_unran}


# ---------------------------------------------------------------- 任せ先の役の素材
def material_problems(material, *, mode: str) -> list:
    """任せ先の CI の役が返した素材の欄の決まりに外れた所（人に向けた文の並び。無ければ空）。今の works の受け付け（ci_role.take）が
    写しの graph の schema と post_check に任せていた決まりを書いた物（新しい関数）:
    - 形（MATERIAL_SCHEMA。写しの graph の review-loop.json の p0.local_checks・p4.ci の schema から盤面の欄の carried_over・
      from_round を外した物。YAML の役の節 ci の output_format と同じ物であることは試験が縛る）
    - status ごとに要る欄（検証器の素材の表 review-record.py:140-151 の STATUS）: found は count と detail、clean は checked、
      ほかは reason。要る文の欄は空でない
    - 形（mode）ごとの走らせられない時の status（写しの指示書 p0.local_checks.md・p4.ci.md と、判定の後の工程は人待ちを新しく
      立てない規則 review-loop.py の check_record）: base は awaiting_human（not_run は拒む）、final は not_run（awaiting_human は拒む）
    mode が base・final でなければ ValueError"""
    if mode not in ("base", "final"):
        raise ValueError(f"mode は base か final: {mode!r}")
    probs = validate_schema(material, MATERIAL_SCHEMA, "素材")
    status = material.get("status") if isinstance(material, dict) else None
    if status not in STATUSES:
        return probs
    for k in STATUS_FIELDS[status]:
        if k not in material:
            probs.append(f"素材は {status} なので '{k}' が要る")
        elif k not in NUMERIC_FIELDS and isinstance(material[k], str) and not material[k].strip():
            probs.append(f"素材は {status} なので '{k}' に何を見たかを書け（空）")
    cant = CANT[mode == "final"]
    if status in CANT.values() and status != cant:
        probs.append(f"{mode} の形は走らせられなければ {cant} で書け（{status} は使わない。修正前は緑を仮定せず人待ち、"
                     "修正後は人待ちを新しく立てない）")
    return probs
