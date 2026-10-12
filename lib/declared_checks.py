"""CI の節（修正前の p0.local_checks・修正後の p4.ci）を盤面なしで走らせる口: 対象の宣言（.review-checks.json）の段と test_cmd を
走らせ、素材（material）を組み、任せ先の役の素材の欄の決まりを照らす。名は今の works の CI の節の語 CI_BUILTIN（entry.py:442）。

今の works（版 2aa7c66cf7abe1fe09699ac2942d107123214168）の関数を元の名で写した物（各関数の docstring の末尾に元の `<パス>:<行>`）。
盤面の引数 b・記録への控え（process.checks）・機械全体の試験の枠（tree_run.slotted_run の slotwrap.sh）・台帳の人待ちは外した。
同じ run の中の使い回しは、置き場を呼び手が引数 reuse（tree_run.reuse_place の返り）で渡す形で tree_run.reuse_run に残す。
- 字のまま（継ぎ目の直しだけ）: TEST_CMD_STEP・local_checks_material・_launched・_cmd_material・_same_step・env_only_red・
  _suite_kind・suites_line・CiRefused（InputRefused ごと）・_with_test_cmd・_junit_unran・_tail（TAIL_LINES・TAIL_BYTES ごと）・
  _reused_material・_reused_note
- 書き直し: tree_runner・_engine_log・checks_plan・checks_reply・_skipped_note・run_ci・baseline_line
- 元の盤面の部分を盤面なしで組み直した物: _planned_run・_declaration_moved（宣言の照合）・_fall_back（任せ先へ落とす）
- 新しい関数: material_problems・drop_copy・_cant_status
"""
import contextlib
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
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
ROLE_NEEDED = "role_needed"   # 走らせ方の語のうち、engine が走らせず任せ先の CI の役が素材を書いた（自己申告）物
# 自己申告の緑・走らせなかった CI を人に見せる時の次の手（T41。最後の関所と報告が同じ字を出す）
SELF_REPORTED_NOTE = (f"最後のテストは engine が走らせた結果ではない（任せ先の申告）。走らせる語を宣言 {DECL_NAME} に"
                      "書けば次の run から engine が走らせる")
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
MODES = ("base", "final")   # 形: 判定の前・修正の後
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
                          niced: bool = False, reuse: dict | None = None) -> dict:
    """任せ先に落ちた CI の節に渡す素材 {"material": …} を組む。
    test_cmd を tree_run.command_argv の形（direct か shell）で tree_run.reuse_run に走らせ（対象の根で・標準入力は空・環境は
    tree_run.outside_env。標準出力と標準エラーを log_path に）、終了コード 0 なら clean（checked が要る）、他は found・count 1。
    detail はログの末尾（宣言の段の末尾と同じ切り方）。起こせなければ（shell の先頭の語が tree_run.prove_launchable の証明を
    通らない回も）not_run。test_cmd が空なら走らせずに not_run。
    止められたら（tree_run.Stopped）捕まえない。launched（dict）を渡せば、起こす前に決めた起こし方を launched["how"] に置き、
    reuse_run の note にも使う（reuse（tree_run.reuse_place の返り）を渡した回は、同じ run の中の控えから使い回すと launched["reused"] に
    出どころが、使い回せなかった回は launched["reuse_off"] に理由が入る。出どころは素材の checked にその句が付く）。
    niced が真なら、起こすプロセスの優先度を nice -n 19 と同じだけ下げる（baseline_red.lowered。argv・起こし方・起こせなさの証明は変えない）
    （元 works/.shared/core/entry.py:650-677。tree_run.slotted_run を tree_run.reuse_run に替えた）"""
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
            code = tree_run.reuse_run(argv, tree_run.outside_env(os.environ), place=reuse, note=launched,
                                      stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, cwd=str(repo),
                                      **(baseline_red.lowered()[0] if niced else {}))
        except OSError as e:
            return {"material": {"status": "not_run", "reason": f"{_launched(argv, how)} でテストのコマンドを起こせない: {e}"}}
    return _reused_material(_cmd_material(code, log_path, argv, how), launched)


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


def _reused_material(mat: dict, note: dict) -> dict:
    """同じ run の中の控えから使い回した test_cmd（note は tree_run.reuse_run の note か、その欄を写した行）の素材 mat の checked（clean）の
    末尾に、出どころの句を足す。控えは終了コード 0 の回だけなので使い回した素材は clean にしかならない。使い回していない・clean でない
    素材は変えない（元 works/.shared/core/entry.py:706-713）"""
    m = mat["material"]
    text = tree_run.reused_text(note)
    if not text or m.get("status") != "clean":
        return mat
    return {"material": {**m, "checked": f"{m['checked']} ／ {TEST_CMD_STEP} は控えから使った（{text}）"}}


def _same_step(steps: list, argv: list, how: str) -> str | None:
    """test_cmd を直に起こす形（how が direct）の argv が宣言の段の argv と同じなら、その段の名（同じコマンドを
    2 度走らせない）。シェルを通す test_cmd は宣言の段（シェルを通さない）と同じにならない（元 works/.shared/core/entry.py:742-747）"""
    if how != "direct":
        return None
    return next((s.get("name") for s in steps if list(s.get("argv") or []) == argv), None)


def _with_test_cmd(runner, test_cmd: str, note: dict, reuse: dict | None = None):
    """runner (steps, cwd, log_dir) -> runs を包み、宣言の段の後に test_cmd の段を 1 つ足す。runner は steps + [test_cmd の段] で
    1 度だけ呼ぶ（ログは段の番号で分かれる）。test_cmd が宣言の段と同じコマンドなら足さず、note["same_as"] にその段の名を置く。
    test_cmd が空なら足さない。段の起こし方 how は起こす前に決め（足す段は tree_run.command_argv の値、宣言の段はシェルを
    通さないので direct）、走った行に写す。reuse（同じ run の中の使い回しの置き場）は runner に渡す
    （元 works/.shared/core/entry.py:750-765。既定の runner を tree_runner に替えた）"""
    cmd = (test_cmd or "").strip()
    argv, how = tree_run.command_argv(cmd) if cmd else (None, None)

    def run(steps, cwd, log_dir):
        note["same_as"] = _same_step(steps, argv, how) if cmd else None
        extra = [{"name": TEST_CMD_STEP, "argv": argv, "how": how}] if cmd and not note["same_as"] else []
        hows = ["direct"] * len(steps) + [s["how"] for s in extra]
        rows = (runner or tree_runner)(list(steps) + extra, cwd, log_dir, reuse=reuse)
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
    elif by == ROLE_NEEDED and role_status in ("clean", "found"):
        ran = [f"任せ先の CI の役 blk-ci が選んだ一式（素材の status {role_status}）"]
    elif by == ROLE_NEEDED and role_status is not None:
        unrun.append(f"宣言の段・{TEST_CMD_STEP}（任せ先の CI の役 blk-ci が走らせなかった: 素材の status {role_status or '無い'}）")
    elif by == ROLE_NEEDED:
        unrun.append(f"宣言の段・{TEST_CMD_STEP}（任せ先の CI の役 blk-ci が走らせる）")
    env = f"／環境で起こせなかった（コードの赤ではない）: {'・'.join(broken)}" if broken else ""
    if direct_broken:
        env += f"（{tree_run.DIRECT_HINT}）"
    return f"走らせた: {'・'.join(ran) or '無い'}{env}／走らせなかった: {'・'.join(unrun) or '無い'}"


# ---------------------------------------------------------------- 宣言の段
def tree_runner(steps: list, cwd, log_dir, *, reuse: dict | None = None) -> list:
    """段を 1 つずつ tree_run.reuse_run で走らせる: 段の argv は shell を通さない・別のプロセスグループ・期限なし・標準入力は空・uv run の
    環境を外す（tree_run.outside_env）・止められたら木ごと止めて tree_run.Stopped を投げる（ここでは捕まえない）。標準出力・
    標準エラーは log_dir/<段の番号>.out・.err に丸ごと。返りの行は {name, argv, out, err, started, exit, wall_s, tail}（started は
    段を起こした epoch 秒で、試験の報告が今の段の物かを checks_reply が見る。起こせなければ exit None と error）。
    信号で死んだ段の exit は tree_run の 128+信号。
    使い回し（reuse。tree_run.reuse_place の返りで、None なら使い回さない）の単位は宣言の一式（段は前の段の副作用に依りうるので、
    一式の中では段ごとには使い回さない）: 全段のログを開いた後に tree_run.replay_group が一式の控えを 1 度だけ引き、全段が同じ run の中で
    同じ木・同じ一式・同じ環境の緑なら、子を起こさず、段の junit（宣言していれば cwd からのパス）を全部書き戻す。1 段でも外れれば全段を
    走らせ（tree_run.reuse_run）、全段が緑で各段の前後の木が同じなら一式を置く（tree_run.keep_group。一式の外の呼び（TDD の輪の頭の
    test_cmd など）が引く段ごとの控えも並べて置く）。段ごとの note の欄（出どころ reused・使い回せなかった理由 reuse_off）は
    tree_run.note_fields で行へ写す
    （元 works/.shared/core/board.py:379-433。tree_run.slotted_run を tree_run.reuse_run に替え、枠を待った秒 wait_s を外した）"""
    log_dir = pathlib.Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    env = tree_run.outside_env(os.environ)
    outputs = [[str(pathlib.Path(cwd) / s["junit"])] if s.get("junit") else [] for s in steps]
    runs = []
    with contextlib.ExitStack() as stack:
        logs = []
        for i in range(len(steps)):
            out_path, err_path = log_dir / f"{i + 1}.out", log_dir / f"{i + 1}.err"
            logs.append((str(out_path), str(err_path), stack.enter_context(open(out_path, "wb")),
                         stack.enter_context(open(err_path, "wb"))))
        group = tree_run.new_group([{"name": s["name"], "argv": list(s["argv"]), "outputs": o} for s, o in zip(steps, outputs)], cwd)
        replay_at = tree_run.file_clock()   # 控えから書き戻した報告が、段の起動より古く見えないように、書き戻す前の時刻を起動に使う
        replayed, why = tree_run.replay_group(group, env, cwd, [(out, err) for _, _, out, err in logs], reuse)
        notes = replayed or [{} for _ in steps]
        for s, o, note, (out_path, err_path, out, err) in zip(steps, outputs, notes, logs):
            started = replay_at if replayed else tree_run.file_clock()
            row = {"name": s["name"], "argv": list(s["argv"]), "out": out_path, "err": err_path, "started": started}
            if replayed:
                rc = 0
            else:
                try:
                    rc = tree_run.reuse_run(list(s["argv"]), env, place=reuse, outputs=o, note=note, skip=why, group=group,
                                            stdin=subprocess.DEVNULL, stdout=out, stderr=err, cwd=str(cwd))
                except OSError as e:
                    rc = None
                    row["error"] = str(e)
                    err.write(str(e).encode("utf-8"))
            out.flush()
            err.flush()
            data = pathlib.Path(out_path).read_bytes() + b"\n" + pathlib.Path(err_path).read_bytes()
            row.update(exit=rc, wall_s=round(time.time() - started, 1), tail=_tail(data))
            runs.append(row)
        if not replayed:
            tree_run.keep_group(group, notes)
    for row, note in zip(runs, notes):
        row.update(tree_run.note_fields(note))
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


def _junit_reports(root: pathlib.Path, steps: list, runs: list, report_dir) -> tuple:
    """JUnit の報告を宣言して走った段の報告を読み ——（1 件ごとの結末, 段の名, 試験を走らせなかった段の名）。読んだ報告は
    report_dir/<段の番号>.xml に写す（段の名は対象が書く字で、パスの区切りを含みうる。番号はログの名と同じ）"""
    decl = {s["name"]: s for s in steps}
    cases, names, unran = [], [], []
    for i, r in enumerate(runs, 1):
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
            shutil.copyfile(path, pathlib.Path(report_dir) / f"{i}.xml")
    return cases, names, unran


def _row(r: dict) -> dict:
    """返りの段の行 {name, exit, how, launch?, reused?, reuse_off?}（launch は起こせない段だけ broken。reused・reuse_off は
    tree_run.note_fields の欄）"""
    kind = tree_run.launch_kind(r.get("exit"))
    return {"name": r["name"], "exit": r.get("exit"), "how": r.get("how"), **({"launch": kind} if kind == "broken" else {}),
            **tree_run.note_fields(r)}


def _reused_note(runs: list, material: dict) -> dict:
    """素材に、控えから使った段の出どころを足す。使い回した段（行に reused）が在れば、素材の checked（clean）の末尾に
    『控えから使った段: <段>（<出どころ>）』。控えは全段が緑の一式だけなので、使い回した段の在る素材は clean にしかならない
    （checks_reply は終了コードで赤を決める）。clean でない素材は変えない。修正前のテストの行（baseline_line）は checked を
    そのまま出すので、ここに足せば出どころが報告に載る（元 works/.shared/core/board.py:436-447。返答の包みを外し、素材を受ける）"""
    used = [f"{r['name']}（{text}）" for r in runs if (text := tree_run.reused_text(r))]
    if not used or material.get("status") != "clean" or not isinstance(material.get("checked"), str):
        return material
    return {**material, "checked": f"{material['checked']} ／ 控えから使った段: {'・'.join(used)}"}


def _no_runs() -> dict:
    return {"material": None, "runs": [], "skipped_steps": [], "same_as": None, "test_cmd_how": None, "log": "", "cases": [],
            "junit_steps": [], "junit_unran": []}


def _cant_status(material: dict, after_judge: bool) -> dict:
    """走らせられない素材の status を形に合わせる（判定の前は awaiting_human・後は not_run）。test_cmd の素材は起こせない時に
    形を問わず not_run を返すので、判定の前の素材の決まり（material_problems）に外れないように置き換える"""
    cant = CANT[bool(after_judge)]
    return {**material, "status": cant} if material.get("status") in CANT.values() else material


def run_ci(root, *, test_cmd: str, log_dir, changed, after_judge: bool, report_dir=None, reuse: dict | None = None) -> dict:
    """CI の節を走らせる。返り {by, material, runs, skipped_steps, same_as, test_cmd_how, log, cases, junit_steps, junit_unran, fell_back?}。
    - 範囲の宣言（checkscope.SCOPE_DECL）が在るのに対象の宣言（DECL_NAME）が無い・範囲の宣言の誤り・宣言に無い段の名は、
      走らせる前に CiRefused（範囲の宣言が黙って効かない形にしない）
    - 宣言が在れば by engine: 範囲の宣言の paths_ignore を changed（変更のパスを返す口。範囲を持つ段が在る時だけ呼ぶ）と照らし、
      変更が全部その下に在る段は回さず skipped_steps に名と範囲で残す。宣言の段の後に test_cmd の段を足し（宣言の段と同じ
      コマンドなら足さず same_as にその段の名）、素材は全部の段から組む——宣言の一式と test_cmd の両方が緑の時だけ clean。
      宣言の書式の誤りは走らせずに走らせられない素材（判定の前は awaiting_human・後は not_run）
    - 走らせた段が宣言を書き換えた（走らせた後の宣言の sha が計画の sha と違う）なら、計画から 1 度だけやり直す（ログは
      log_dir/replan）。やり直しの後も変わっていれば CiRefused
    - engine の素材が素材の欄の決まり（material_problems）に外れれば任せ先に落とし、fell_back に訳を置く: engine が同じ呼び出しで
      test_cmd の段を走らせていれば、その結果から by role の素材を組む（test_cmd を 2 度走らせない）。走らせていなければ test_cmd を
      走らせて by role。test_cmd が無ければ by role_needed
    - 宣言が無く test_cmd が在れば by role: test_cmd だけを走らせた素材と、起こす前に決めた起こし方 test_cmd_how（direct・shell）
    - どちらも無ければ by role_needed: 素材は None（任せ先の CI の役が渡す。前の結果を使ってよい、ではない）
    by role の素材の走らせられない status は形に合わせる（_cant_status）。
    reuse（tree_run.reuse_place の返り）を渡せば、宣言の一式と test_cmd を同じ run の中の控えから使い回し・控える（tree_runner・
    local_checks_material）。使い回した段の出どころは素材の checked と段の行の reused に、使い回さなかった理由は段の行の reuse_off に出る。
    最後のテストの呼び手は渡さない（最後のテストは省かない）。
    runs は走った段ごとの {name, exit, how, launch?, reused?, reuse_off?}。cases は JUnit の報告を宣言して走った段の 1 件ごとの結末（baseline_red.parse_junit
    の形）、junit_steps はその段の名、junit_unran はそのうち試験を走らせなかった段の名。段が対象の木の中に書いた報告は report_dir に
    段の番号で写し、走らせる前に無かった報告は対象の木から消す（止められた時も）。止められたら（tree_run.Stopped）捕まえない
    （元 works/.shared/core/entry.py:858-904 の盤面の外の決まりを、盤面の run_engine の代わりに checks_plan・checkscope・tree_runner・
    checks_reply で組んだ物。scope_changed が足していた依頼の where が名指すパスは、呼び手が changed に足して渡す
    （checkscope.request_files））"""
    root = pathlib.Path(root)
    log_dir = pathlib.Path(log_dir)
    if (root / checkscope.SCOPE_DECL).is_file() and not (root / DECL_NAME).is_file():
        raise CiRefused(f"範囲の宣言 {checkscope.SCOPE_DECL} が在るのに、それが段を名指す対象の宣言 {DECL_NAME} が無い"
                        "——範囲の宣言が効かない（宣言を置くか、範囲の宣言を消す）")
    got, ran, moved = _planned_run(root, test_cmd, log_dir, changed, after_judge, report_dir, reuse)
    if moved:
        got, ran, again = _planned_run(root, test_cmd, log_dir / "replan", changed, after_judge, report_dir, reuse)
        if again:
            raise CiRefused(f"宣言 {DECL_NAME} が計画の後に 2 度変わった（計画し直しても同じ）: {moved}／{again}")
    if got["by"] != "engine":
        return got
    problems = material_problems(got["material"], mode=MODES[bool(after_judge)])
    if not problems:
        return got
    why = "engine が組んだ素材が素材の欄の決まりに外れた: " + "；".join(problems)
    return _fall_back(root, test_cmd, log_dir, after_judge, ran, got["same_as"], why, reuse)


def _planned_run(root: pathlib.Path, test_cmd: str, log_dir: pathlib.Path, changed, after_judge: bool, report_dir, reuse) -> tuple:
    """計画から走らせて素材を組むまでの 1 回 ——（返り, 走った段の行（tree_runner の形）, 宣言が計画の後に変わった訳か ""）"""
    out = _no_runs()
    plan = checks_plan(root)
    if "fallback" in plan:
        if not (test_cmd or "").strip():
            return {**out, "by": ROLE_NEEDED}, [], ""
        log = log_dir / f"{TEST_CMD_STEP}.log"
        launched = {}
        material = _cant_status(local_checks_material(root, test_cmd, log, launched=launched, reuse=reuse)["material"], after_judge)
        return {**out, "by": "role", "material": material, "log": str(log), "test_cmd_how": launched.get("how")}, [], ""
    steps = plan.get("steps") or []
    launch = {"steps": steps, "sha": plan.get("sha"), "blocked": plan.get("blocked")}
    runs, skipped, note, todo = [], [], {}, []
    if not launch["blocked"]:
        ignores, why = checkscope.read_scope(root, steps)
        if why:
            raise CiRefused(why)
        skipped = checkscope.skipped_steps(steps, ignores, changed)
        off = {s["name"] for s in skipped}
        todo = [s for s in steps if s["name"] not in off]
    # 走らせる前に無かった報告は、読み終えたら（止められても）対象の木から消す: 未追跡のファイルが増えて作業ツリーの指紋が変わり、
    # 修正の差分にも紛れ、次の回には「前から在った」と読まれて残り続けるため。前から在った報告は消さない
    new_reports = [root / s["junit"] for s in todo if s.get("junit") and not (root / s["junit"]).exists()]
    try:
        if not launch["blocked"]:
            runs = _with_test_cmd(None, test_cmd, note, reuse)(todo, root, log_dir)
        material = _reused_note(runs, _skipped_note(skipped, checks_reply(launch, runs, root, after_judge=after_judge)))
        cases, junit_steps, junit_unran = _junit_reports(root, steps, runs, report_dir)
    finally:
        for path in new_reports:
            path.unlink(missing_ok=True)
    log = _engine_log(log_dir / "checks.log", runs, material.get("reason") or "")
    got = {**out, "by": "engine", "material": material, "runs": [_row(r) for r in runs], "skipped_steps": skipped,
           "same_as": note.get("same_as"), "log": str(log), "cases": cases, "junit_steps": junit_steps,
           "junit_unran": junit_unran}
    return got, runs, (_declaration_moved(root, launch["sha"]) if runs else "")


def _declaration_moved(root: pathlib.Path, sha: str) -> str:
    """走らせた後の宣言が計画の宣言（sha）と違えば、その訳（同じなら空）。読めない・誤りも違うと数える
    （元 works/.shared/core/graphloops/engine/commands.py:522 engine_run_refusal の宣言の照合）"""
    now = declared.read(root)
    after = (now or {}).get("sha")
    if after == sha:
        return ""
    return f"宣言 {DECL_NAME} が計画の後に変わった（sha {sha[:12]} → {after[:12] if after else (now or {}).get('error') or '無い'}）"


def _fall_back(root: pathlib.Path, test_cmd: str, log_dir: pathlib.Path, after_judge: bool, runs: list, same_as, why: str,
               reuse) -> dict:
    """engine の結果を使えない CI の節を任せ先へ落とす。test_cmd の素材は、engine が同じ呼び出しで走らせた test_cmd の段（名
    TEST_CMD_STEP か same_as の段で、起こせた物）が在ればその終了コードと標準出力・標準エラーと、走った行の argv・how から組み、
    無ければ test_cmd を走らせる（元 works/.shared/core/board.py:1413 _fall_back と works/.shared/core/entry.py:925 _ci_by_cmd。
    印 mark_launched と盤面の done を外し、素材を返りに置く）"""
    out = {**_no_runs(), "fell_back": why}
    if not (test_cmd or "").strip():
        return {**out, "by": "role_needed"}
    log = log_dir / f"{TEST_CMD_STEP}.log"
    ran = next((r for r in runs if r["name"] in (TEST_CMD_STEP, same_as) and r.get("exit") is not None), None)
    if ran:
        log.write_bytes(b"".join(pathlib.Path(ran[k]).read_bytes() for k in ("out", "err")
                                 if ran.get(k) and pathlib.Path(ran[k]).is_file()))
        launched = {"how": ran.get("how")}
        material = _reused_material(_cmd_material(ran["exit"], log, ran["argv"], launched["how"]), ran)["material"]
    else:
        launched = {}
        material = local_checks_material(root, test_cmd, log, launched=launched, reuse=reuse)["material"]
    return {**out, "by": "role", "material": _cant_status(material, after_judge), "log": str(log),
            "test_cmd_how": launched.get("how")}


# ---------------------------------------------------------------- 任せ先の役の素材
CI_ROLE = "ci"                       # 任せ先の CI の役の拒否の控えの名（rolekit.with_done・rolekit.rejected）
COPY_PREFIX = "works-factory-ci-"    # 任せ先の役がテストを走らせる写しの置き場（一時の置き場の直下）の頭


def drop_copy(top) -> None:
    """写しの置き場を消す（一時の置き場の直下の COPY_PREFIX で始まるフォルダだけ。symlink は辿らない）。top は役が書ける
    控えから読むので、ほかの所を指していても消さない"""
    if not top or os.path.islink(top):
        return
    real = os.path.realpath(top)
    if os.path.dirname(real) == os.path.realpath(tempfile.gettempdir()) and os.path.basename(real).startswith(COPY_PREFIX):
        shutil.rmtree(real, ignore_errors=True)


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
    if mode not in MODES:
        raise ValueError(f"mode は {'・'.join(MODES)} のどれか: {mode!r}")
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


# ---------------------------------------------------------------- 修正前のテストの行
def baseline_line(base) -> str:
    """修正前のテスト（base の元の結末。baseline_red.read_baseline の返りの、呼び手の欄 material・exit_codes・skipped_steps）の 1 行。
    final の証拠が最後のテストの行と並べて出す——最後の赤が修正の後に出た赤か、基の版からの赤かを人が見分ける手がかり。修正前の CI と
    最後のテスト（test_cmd の段なども走る）は同じ一式とは限らないので、どちらとも言い切らない。base が None なら記録が無い
    （元 works/.shared/core/entry.py:792-816。盤面の記録 process.baseline_checks と process.checks の skipped_steps の代わりに元の結末を受け、
    段ごとの終了コードを足した）"""
    named = "元の結末（入力 baseline）"
    if base is None:
        return f"修正前のテスト: 記録が無い（{named}）"
    material = base.get("material")
    if material is None:
        return f"修正前のテスト: 素材が無い（{named}。任せ先の CI の役が渡さなかった）——{gatemarks.BASELINE_NOT_RUN}"
    if not isinstance(material, dict) or not isinstance(material.get("status"), str) or not material["status"]:
        return (f"修正前のテスト: 記録が壊れている（{named} の material に文字列の status が無い: "
                f"{json.dumps(material, ensure_ascii=False)[:80]}）")
    status = material["status"]
    word = gatemarks.MATERIAL_WORDS.get(status, "表に無い状態")
    codes = base.get("exit_codes") or {}
    told = (f"{named} の status {status}" + (f"・走らせた物 {material['checked']}" if material.get("checked") else "")
            + (f"・段ごとの終了コード {json.dumps(codes, ensure_ascii=False)}" if codes else ""))
    if status in ("not_run", "awaiting_human"):
        return f"修正前のテスト: {word}（{told}・{material.get('reason') or '理由なし'}）——{gatemarks.BASELINE_NOT_RUN}"
    if status == "clean":
        return (f"修正前のテスト: {word}（{told}）——最後のテストの赤は修正の後に出た赤でありうる"
                "（同じ一式とは限らない。最後のテストの一式と照らして決める）")
    if status == "found":
        skipped = base.get("skipped_steps") or []
        scoped = f"・{checkscope.skipped_text(skipped)}" if skipped else ""
        return (f"修正前のテスト: {word}（{told}{scoped}）——最後のテストの赤は修正前から在りうる"
                "（同じ一式とは限らない。最後のテストの一式と照らして決める）")
    return f"修正前のテスト: {word}（{told}・{material.get('reason') or '理由なし'}）"
