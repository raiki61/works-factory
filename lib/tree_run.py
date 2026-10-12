"""コマンドを自分のプロセスグループで走らせ、止めるときは木ごと止める殻（標準ライブラリと、同じく標準ライブラリだけの
unittrees・webget）。

実行基盤は節を止める（Ctrl-C・SIGTERM・期限）とき直下の子だけを止め、テストが背景に起こした孫は生き残って
作業ツリーに書き続ける（試作で実測: 期限の 2 分後に孫の subshell がファイルを書いた）。graphloops の
engine/role_run.py（_tree_members・_stop_tree。本線 9f91687 = graphloops 0.21.1 の子の制御の層）と同じ式で塞ぐ:
- コマンドを新しいセッション（= 新しいプロセスグループ）で起こす
- 止めるときは **数え上げ→送る→数え直し**。木の仲間は ps の全プロセスの表から拾う: グループの番号かセッションの番号が
  長の番号のもの（setpgid で出た孫もセッションは抜けない）と、それらと前の回に数えた仲間から親子の鎖で辿れる子孫（setsid で
  別のセッションへ出た孫）。送り先は生きた仲間から作り（ゾンビだけのグループへは送らない——macOS は EPERM で拒む）、
  送った後は数えた生きた仲間が消えるまで待つ。長が回収前なら、数える前にグループを SIGSTOP で凍らせる: ps が固まっても
  グループは走らず（期限は置かない）、凍った仲間は死なないので、数える間に親子の鎖が切れて setsid で出た孫を見失わない
- SIGINT・SIGTERM・SIGHUP を受けたら、受けた信号と SIGTERM を仲間へ送り、KILL_GRACE 秒の内に消えなければ SIGKILL を送る。
  **止めたと数えるのは、数え直して生きた仲間が居ない時**。ps が読めない回はグループへだけ送り、グループが空になるまで待つ
- 殻の直下の親（節では uv）が替わったら（kill -9 で消えて孤児になった）同じく木ごと止める（POLL 秒ごとに見る）。
  起きた時に既に親が 1（直下の親が先に消えた）なら、替わりを待てないので何も起こさずに止まる。
  見るのは直下の親だけ: uv が生きたまま実行基盤だけが kill -9 された回は気づかない（bash の節だった頃と同じ限界）。
  PID 1 の殻（コンテナの sh など）の子として手で起こすと、いつも孤児と見なして走らない
- 止める信号（か親の替わり）で木を止めた後は、すぐ抜けずに LINGER 秒待ってから抜ける。実行基盤は Ctrl-C を受けると
  run を failed と書いてから抜けるが、節がすぐ死ぬとその書き込みが確定する前に CLI が抜け、run が running のまま固まって
  resume できず abandon しか残らなかった（試し P17: すぐ死ぬ節で 3/3、1 秒以上残る節で 5/5 が failed になり resume できた）。
  上限の勘定: 信号に気づくまで POLL、SIGKILL まで KILL_GRACE + ps の 1 回、抜けるまで LINGER で 0.2 + 2 + 1 = 3.2 秒と
  ps の回の分。ps は PS（/bin/ps を名指し、カーネルの表の欄だけを求める）で待ちに止まらないので、実行基盤の cancel の
  猶予 5 秒より前に抜ける。コマンドが自分で終わった回は待たない。起こす前の証明（prove_launchable）の間に
  届いた信号は POLL の内に証明を捨て、コマンドを起こさずに LINGER 待って抜ける（PROOF_TIMEOUT は勘定に入らない）
- コマンドが自分で終わった後も、背景に残した孫を同じ手順で止める（節が終わった後に作業ツリーを書く物を残さない）
抜け道: 数える前に親が消えて親子の鎖が切れ、かつ setsid でセッションも抜けた子孫（二重 fork の daemon 化。コマンドが
終わった後の `setsid … &` もこの形）は拾えない（本線と同じ限界）。止め切れなかった仲間は標準エラーに名指しする。

使い方: `python3 tree_run.py -- <コマンド>`（-- の後の語は空白で繋いで 1 行にし /bin/sh -c で走らせる。
語が無ければ環境変数 INPUTS_CMD）。終了コードはコマンドの終了コード、信号で死んだら 128+信号、殻が止められたら
128+受けた信号（直下の親が消えた回は SIGHUP）、コマンドが空なら 2。関数として使う側は run(argv, **Popen の引数) を呼ぶ。
子に渡す環境は outside_env(os.environ) で uv run の外の形にする（blk-tests の run_tests と盤面の tree_runner。台帳 R23。
決まりを 1 か所に置くのは、線の CI と engine_run の CI で同じ宣言が片方だけ偽の赤になるのを防ぐため）。

同じ run の中の試験の結果の使い回し（reuse_run・replay_group・keep_group。今の works の tree_run.py:425-836 を元の名で写し、機械全体の
試験の枠 slotwrap.sh を外した物）: 同じ作業ツリーの木・同じ argv・同じ環境・同じ道具の緑の結果を、run の置き場の直下 REUSE_SUB に
控え、同じ run の中の次の呼びで子を起こさずに使う。置き場・run の名・旗 RERUN_ENV は呼び手が reuse_place に渡す。
"""
import base64
import collections
import datetime
import errno
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True   # 下の import が（python3 tree_run.py で起こした時に）pack の中へ __pycache__ を作らないように

import unittrees  # noqa: E402
import webget  # noqa: E402


KILL_GRACE = 2    # SIGTERM から SIGKILL までの猶予（秒）。実行基盤の cancel の猶予（SIGTERM → 5 秒 → SIGKILL）より短くする:
                  # 同じ 5 秒だと、SIGTERM を無視する孫へ SIGKILL を送る前に殻が実行基盤に殺され、孫が残った（試し P11）
POLL = 0.2        # 信号と親の替わりを見る間隔（秒）
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
LINGER = 1.0      # 止める信号で木を止めた後、抜ける前に待つ秒数（試し P17 の Ctrl-C の穴。モジュールの説明に上限の勘定）
# 全プロセスの表を読む ps。期限を置かず（E12）、止まらない形を命令の選びで持つ: 絶対パスで名指して PATH の替え玉（対象の道具・
# 試験の偽物）を拾わず、欄はカーネルのプロセスの表から引ける物だけにする（args・command・env のように他のプロセスの記憶を読む欄は、
# 固まったプロセスで ps を待たせる）。無い・起こせない時は表を読めない回（直ちにグループへ送る）を通る
PS = "/bin/ps"
REUSE_SLACK = 2.0   # 開始時刻の読みの誤差（ps の etime は秒の切り捨て）。長を起こした時刻よりこれを超えて後に始まった物は別物
_Proc = collections.namedtuple("_Proc", "pid ppid pgid uid started stat")   # ps の 1 行（started は開始時刻のエポック秒）


class Stopped(Exception):
    """殻が止められ、木ごと止め終えた。signum は受けた信号（直下の親が消えた回は SIGHUP）"""

    def __init__(self, signum):
        super().__init__(signum)
        self.signum = signum


def outside_env(environ):
    """uv run が足した物を外した環境（写し。environ は書き換えない）。PYTHONDONTWRITEBYTECODE=1 は立てる——子（テスト）が
    作業ツリーに __pycache__ を作って修正の差分に紛れ込むのを止める（works の決まり。engine の run_steps は環境をそのまま継ぐ）。
    外すのは:
    - PATH の頭の、この python の bin（dirname(sys.executable) か sys.prefix/bin。実体のパスで比べる）。uv は頭に足すので
      頭だけを見て、同じフォルダは 1 度だけ外す（元の PATH に同じフォルダが在っても後ろの物は残る）
    - UV_RUN_RECURSION_DEPTH と、sys.prefix を指す VIRTUAL_ENV（uv が起こした環境。対象の .venv もここ）
    uv run の外で起こされた（UV_RUN_RECURSION_DEPTH が無い）ときは、下の UV_NO_CONFIG のほかは外さない。
    - UV_NO_CONFIG はいつも外す。利用者が実行基盤の環境に立てていても、テストのコマンド（`uv run <試験の実行器>` など）には対象の
      [tool.uv]（私的な index など）を読ませる。渡すと公開の PyPI から解決して、偽の赤と依存の取り違えの口になる
    実行基盤は script の節を `uv run <ファイル>` で起こし、uv は PATH の頭に自分の python の bin を足し、VIRTUAL_ENV・
    UV_RUN_RECURSION_DEPTH を立てる。そのまま渡すと `python3 -m <試験の実行器>` が uv の python を掴んで偽の赤になる。
    限界: 節に deps: を足すと uv は --with の層の bin も足し、それは外れない（今の節は deps を持たない）"""
    env = dict(environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("UV_NO_CONFIG", None)
    if env.pop("UV_RUN_RECURSION_DEPTH", None) is None:
        return env
    ours = {os.path.realpath(d) for d in (os.path.dirname(sys.executable), os.path.join(sys.prefix, "bin"))}
    parts = env.get("PATH", "").split(os.pathsep)
    while parts and parts[0] and os.path.realpath(parts[0]) in ours:
        ours.discard(os.path.realpath(parts.pop(0)))
    env["PATH"] = os.pathsep.join(parts)
    venv = env.get("VIRTUAL_ENV")
    if venv and os.path.realpath(venv) == os.path.realpath(sys.prefix):
        del env["VIRTUAL_ENV"]
    return env


PROOF_TIMEOUT = 5.0   # 起こす前の証明（command -v）を待つ上限（秒）。超えたら証明できない回として起こす
_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_UNPROVABLE = set("$`*?[{~")   # 展開される語は字面から引けない
# シェルを通す字: 展開（_UNPROVABLE。証明が引けない字と同じ表から作る）に、区切り・向け直し・引用・注釈・履歴と、shlex が bash と
# 違って読む字（改行はコマンドの区切り・# は語の途中でもただの字・\r は普通の字）を足す。GNU make の job.c の sh_chars にならう
_SHELL_CHARS = _UNPROVABLE | set("|&;<>()]}\\\"'#!^\n\r")
# 先頭に来たらシェルを通す語。出どころは bash のマニュアルの節 Reserved Words・Bourne Shell Builtins・Bash Builtin Commands・
# Job Control Builtins・Directory Stack Builtins・Bash History Builtins・Programmable Completion Builtins・The Set Builtin・
# The Shopt Builtin（GNU make の sh_cmds と同じ理由: 外のプログラムとして在るとは限らないか、在っても意味が違う）
_SHELL_WORDS = frozenset((
    "!", "case", "coproc", "do", "done", "elif", "else", "esac", "fi", "for", "function", "if", "in", "select", "then",
    "time", "until", "while", "{", "}", "[[", "]]",
    ":", ".", "break", "cd", "continue", "eval", "exec", "exit", "export", "getopts", "hash", "pwd", "readonly", "return",
    "shift", "test", "[", "times", "trap", "umask", "unset",
    "alias", "bind", "builtin", "caller", "command", "declare", "echo", "enable", "help", "let", "local", "logout",
    "mapfile", "printf", "read", "readarray", "source", "type", "typeset", "ulimit", "unalias",
    "bg", "fg", "jobs", "kill", "wait", "disown", "suspend", "dirs", "pushd", "popd", "history", "fc",
    "compgen", "complete", "compopt", "set", "shopt",
))
DIRECT_HINT = ("直に起こした（シェルを通さない）。BASH_ENV や export -f のシェルの関数に頼るなら bash -c '…' で包んで書く"
               "（bash -c の非対話では alias はもともと展開されない）")


def command_argv(cmd: str) -> tuple[list, str]:
    """コマンドの 1 行 cmd を起こす形 (argv, how)。how は "shell"（["bash", "-c", cmd]）か "direct"（shlex で割った argv を
    シェルを通さずに起こす）。shell にするのは、割れない・語が無い・_SHELL_CHARS の字を含む・代入の前置きで始まる・先頭の語が
    _SHELL_WORDS に在る、のどれかの時。ほかは全部 direct"""
    try:
        words = shlex.split(cmd)
    except ValueError:
        words = []
    if not words or _SHELL_CHARS & set(cmd) or _ASSIGN.match(words[0]) or words[0] in _SHELL_WORDS:
        return ["bash", "-c", cmd], "shell"
    return words, "direct"


def _first_word(cmd: str):
    """シェルのコマンド cmd の先頭の語と、その前の代入の前置き {名: 値}。字面から引けない（割れない・展開を含む・語でなく記号か
    向け直しで始まる）なら None"""
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        words = list(lex)
    except ValueError:
        return None
    assigns = {}
    while words and _ASSIGN.match(words[0]):
        name, _, value = words.pop(0).partition("=")
        if _UNPROVABLE & set(value):
            return None
        assigns[name] = value
    if not words or not words[0] or words[0][0] in lex.punctuation_chars or _UNPROVABLE & set(words[0]):
        return None
    if words[0].isdigit() and words[1:2] and words[1][0] in "<>":   # 2>log のような番号つきの向け直しで始まる
        return None
    return words[0], assigns


def prove_launchable(argv, cwd=None, env=None, halted=lambda: False):
    """bash -c の argv を起こす前に、中のコマンドの先頭の語を bash の command -v（POSIX: 見つからなければ >0 で何も起こさない）で
    引き、引けなければ起こさずに FileNotFoundError（パスの語でファイルは在る時は PermissionError）を上げる。呼ぶ側の OSError の道
    （exit None → broken → not_run）にそのまま乗る。bash -c でない argv は Popen 自身が起こせなさを OSError で上げるので見ない。
    引く間は POLL 秒ごとに halted() を見て、真なら引くのをやめて戻る（止める判断は呼ぶ側。run は証明の待ちを cancel の勘定に足さない）。
    限界: 見るのは先頭の語だけ（パイプの後ろ・&& の後ろ・sh に渡したスクリプトの有無は見ない）。展開を含む語は引かずに起こす"""
    if list(argv[:2]) != ["bash", "-c"] or len(argv) < 3:
        return
    got = _first_word(argv[2])
    if got is None:
        return
    word, assigns = got
    q = subprocess.Popen(["bash", "-c", 'command -v -- "$1" >/dev/null', "_", word], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=cwd, start_new_session=True,
                         env={**(os.environ if env is None else env), **assigns})
    deadline = time.monotonic() + PROOF_TIMEOUT
    while True:
        try:
            rc = q.wait(POLL)
            break
        except subprocess.TimeoutExpired:
            if halted() or time.monotonic() >= deadline:
                try:
                    os.killpg(q.pid, signal.SIGKILL)   # BASH_ENV が起こした子も残さない
                except OSError:
                    pass
                q.wait()
                return
    if rc == 0:
        return
    if "/" in word and os.path.exists(os.path.join(cwd or os.getcwd(), word)):
        raise PermissionError(errno.EACCES, "起こす前の証明（command -v）: 実行できない", word)
    raise FileNotFoundError(errno.ENOENT, "起こす前の証明（command -v）: 見つからない", word)


def launch_kind(code) -> str:
    """段の終了コードの分類: "clean"（0）・"red"（走って落ちた。126・127 もプログラム自身の終了コードとして読む）・"broken"（起こせない。
    exit None。bash -c の先頭の語が prove_launchable の証明を通らなかった回もここ）。
    broken は engine の checks_reply の broken（exit is None）と同じ規則"""
    if code is None:
        return "broken"
    if code == 0:
        return "clean"
    return "red"


def _answers(send, target):
    """信号 0 の問い: 相手が居る（届く・EPERM）なら真、居なければ偽。ほかの誤りは上げる（本線 role_run._answers と同じ）"""
    try:
        send(target, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def parse_etime(s):
    """ps の etime（[[dd-]hh:]mm:ss）を秒に。読めなければ None"""
    try:
        days, _, rest = s.strip().rpartition("-")
        parts = [int(x) for x in rest.split(":")]
        if not 2 <= len(parts) <= 3:
            return None
        h, m, sec = ([0] + parts)[-3:]
        return (int(days) if days else 0) * 86400 + h * 3600 + m * 60 + sec
    except ValueError:
        return None


def _ps_all():
    """全プロセスの表 ——({pid: _Proc}, None)。読めなければ (None, 理由)。開始時刻は ps を起こす**前**の時刻から etime を
    引く（後から引くと ps の遅れが開始時刻に乗り、番号の再利用の見分けを誤る）。本線 role_run._ps_all の写し"""
    now = time.time()
    try:
        r = subprocess.run([PS, "-A", "-o", "pid=,ppid=,pgid=,uid=,etime=,stat="], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"ps を起こせない（{e}）"
    rows = {}
    for line in r.stdout.splitlines():
        f = line.split()
        secs = parse_etime(f[4]) if len(f) >= 6 else None
        if secs is None or not all(x.lstrip("-").isdigit() for x in f[:4]):
            continue
        rows[int(f[0])] = _Proc(int(f[0]), int(f[1]), int(f[2]), int(f[3]), now - secs, f[5])
    if r.returncode != 0 or not rows:
        return None, f"ps が全プロセスの表を返さない（exit {r.returncode}: {r.stderr.strip()[-200:]}）"
    return rows, None


def _tree_members(pgid, known=None, born=None):
    """木の仲間を数え上げる ——({pid: _Proc}, 理由)。表が読めなければ (None, 理由)。本線 role_run._tree_members の写し。
    拾う印は 3 つ: pgid が長の番号・セッションの番号が長の番号（長は setsid で起こしてある）・その 2 つと known（前の回に
    数えた {pid: 開始時刻}。今の表に同じ開始時刻で居るものだけ）から親子の鎖で辿れる子孫（setsid で出た孫）。
    born（長を起こした時刻）より REUSE_SLACK を超えて後に始まったプロセスが長の番号に居れば、番号は再利用されている
    （グループもセッションも在る限り番号は再利用されない）ので、グループとセッションでは拾わない。
    呼んだ自分と自分の祖先は数えない。セッションの番号を読めない同じ利用者のプロセスが在れば、仲間かを決められないと
    理由を返す"""
    rows, why = _ps_all()
    if rows is None:
        return None, why
    uid, sessions, unreadable = os.getuid(), {}, []
    for pid, row in rows.items():
        try:
            sessions[pid] = os.getsid(pid)
        except ProcessLookupError:
            pass
        except PermissionError:
            if row.uid == uid:
                unreadable.append(pid)
    mine, cur = set(), os.getpid()
    while cur in rows and cur not in mine:
        mine.add(cur)
        cur = rows[cur].ppid
    reused = born is not None and pgid in rows and rows[pgid].started > born + REUSE_SLACK
    found = set() if reused else {pid for pid, row in rows.items() if row.pgid == pgid or sessions.get(pid) == pgid}
    found |= {pid for pid, t in (known or {}).items() if pid in rows and abs(rows[pid].started - t) <= REUSE_SLACK}
    children = {}
    for pid, row in rows.items():
        children.setdefault(row.ppid, []).append(pid)
    todo = list(found)
    while todo:
        for c in children.get(todo.pop(), ()):
            if c not in found:
                found.add(c)
                todo.append(c)
    found -= mine
    lost = [pid for pid in unreadable if pid not in found and pid not in mine]
    why = f"セッションの番号を読めないプロセスが在り、木の仲間かを決められない（pid {lost[:5]}）" if lost else None
    return {pid: rows[pid] for pid in found}, why


def _live(members):
    return {pid: m for pid, m in members.items() if not m.stat.startswith("Z")}


def _name(members):
    return ", ".join(f"pid {m.pid}（pgid {m.pgid}・{m.stat}）" for m in list(members.values())[:5])


def stop_group(p, first=signal.SIGTERM, born=None, known=None):
    """p（長）の木を止める。返すのは止め切れなかった理由（None なら止まった・居なかった）。本線 role_run._stop_tree の式
    （数え上げ→送る→数え直し）で、猶予は KILL_GRACE、送る列は (first と SIGTERM) → SIGKILL:
    回ごとに仲間を数え上げ、生きた仲間が居なければ戻る。居れば、生きた仲間が属するグループのうち長が仲間のグループと
    p のグループへは killpg（数えた後に増えた子にも届く）、残りの仲間へは 1 本ずつ送り、数えた生きた仲間が消えるまで
    待つ（長は待つ間に回収する）。SIGKILL の後に数え直して生きた仲間が残れば名指しの理由を返す。
    長が回収前なら、最初に数える前に p のグループへ SIGSTOP を送り、最初の回の送り先へ (first と SIGTERM) の後に SIGCONT を
    送る。ps が固まってもグループは凍って走らない。先に SIGTERM を送らないのは、送ると長（sh）が数える前に死に、setsid で
    出た孫が親子の鎖から外れて拾えなくなるから（凍った仲間は死なない）。ps が固まったまま殻が殺されると、グループは凍ったまま残る。
    回収した後は番号が再利用されうるので凍らせず、数えてから送る（ps が固まれば送らない）。
    **上限**: 最初の回の待ちは止め始めから KILL_GRACE 秒で切る（ps を待った分も含める）。ps は待ちに止まらない形で呼ぶ（PS）。
    1 度でも表を読めなければ（ps を起こせない・表を返さない）、以後の回は ps を起こさずに直ちに送る——送り先は p のグループと、
    前の回に数えて待ち終えても消えたのを見ていない仲間（番号は同じ相手のまま）。これで SIGKILL は止め始めから KILL_GRACE と
    ps の 1 回の内に出る（＋殻が信号に気づくまでの POLL。実行基盤の cancel の 5 秒より前）。表を読めなかった回は、外へ出た
    子孫を確かめていないと返す。
    born は長の番号の再利用の目印で、長を回収した後にだけ効かせる（回収していない子の番号は再利用されない）。
    known は呼ぶ側が前に数えた仲間 {pid: 開始時刻}（_tree_members の known。Claude の包みが走る間の見回りで溜めた物。
    同じ辞書に数えた仲間を足していく）。省けば空から数える"""
    t0 = time.monotonic()

    def wait(done, end):
        while time.monotonic() < end:
            p.poll()
            if done():
                return
            time.sleep(0.05)

    def watch(pids, group=False):
        """待つ間に消えたのを見た番号を pids から外していく done（group なら p のグループが空になるのも待つ）"""
        def done():
            pids.difference_update([pid for pid in list(pids) if not _answers(os.kill, pid)])
            return not pids and not (group and _answers(os.killpg, p.pid))
        return done

    known = {} if known is None else known
    blind, pending = None, set()   # blind: 表を読めなかった理由（以後は ps を起こさない）
    p.poll()
    frozen = p.returncode is None   # 回収前の長のグループの番号は再利用されないので、ps を待たずに送ってよい
    if frozen:
        try:
            os.killpg(p.pid, signal.SIGSTOP)
        except OSError:
            pass
    for i, sigs in enumerate(((first, signal.SIGTERM), (signal.SIGKILL,), ())):   # 空の回は送らずに数え直して判定だけ
        sigs = tuple(dict.fromkeys(sigs))
        end = t0 + KILL_GRACE if i == 0 else None
        if blind is None:
            p.poll()
            members, why = _tree_members(p.pid, known, born if p.returncode is not None else None)
            if members is None:
                blind = why
        if blind is not None:
            if not sigs:
                return f"止める相手を数え上げられない（{blind}）——グループ {p.pid} の外へ出た子孫を確かめていない"
            targets = [(os.killpg, p.pid)] + [(os.kill, pid) for pid in sorted(pending)]
            done = watch(pending, group=True)
        else:
            known.update({pid: m.started for pid, m in members.items()})
            live = _live(members)
            if not live:
                return why
            if not sigs:
                return f"グループ {p.pid} の木が SIGKILL の後も残っている（{_name(live)}）"
            groups = {m.pgid for m in live.values() if m.pgid in members or m.pgid == p.pid}
            targets = [(os.killpg, g) for g in sorted(groups)] + [(os.kill, pid) for pid, m in live.items() if m.pgid not in groups]
            pending = set(live)
            done = watch(pending)
        if i == 0 and frozen:
            sigs += (signal.SIGCONT,)   # 止めた仲間に、溜まった信号を受けさせる
        for sig in sigs:
            for send, target in targets:
                try:
                    send(target, sig)
                except OSError:
                    pass   # 間に消えた・送れない（送れない相手は数え直しで残りとして名指しする）
        wait(done, end if end is not None else time.monotonic() + KILL_GRACE)
    return None   # 届かない（最後の回は必ず返す）


def run(argv, **popen_kw):
    """argv を新しいプロセスグループで起こして終わりを待ち、終了コード（信号で死んだら 128+信号）を返す。bash -c の argv は起こす前に
    prove_launchable で中の先頭の語を引き、引けなければ起こさずに OSError。
    待つ間（後始末の間も）に STOP_SIGNALS を受けたか直下の親が替わったら、木ごと止め、LINGER 秒待ってから Stopped を投げる。
    起きた時に既に孤児（親が 1）なら起こさずに Stopped(SIGHUP)。どの道で抜けても木を止めに行き、止め切れなければ
    標準エラーに名指しする（抜け道はモジュールの説明）"""
    got = []
    old = {s: signal.signal(s, lambda signum, _f: got.append(signum)) for s in STOP_SIGNALS}
    ppid = os.getppid()
    p = None
    stopped = False

    def stop(first=signal.SIGTERM):
        nonlocal stopped
        why = stop_group(p, first, born)
        stopped = True
        if why:
            print(f"tree_run: 木を止め切れない: {why}", file=sys.stderr)

    def stopped_by(signum):
        """木を止め終えた後、LINGER 秒待ってから Stopped を投げる（待つ間に届いた信号は got に溜まるだけ）"""
        time.sleep(LINGER)
        return Stopped(signum)

    try:
        if ppid == 1:
            raise Stopped(signal.SIGHUP)
        prove_launchable(argv, popen_kw.get("cwd"), popen_kw.get("env"), lambda: bool(got) or os.getppid() != ppid)
        if got or os.getppid() != ppid:   # 証明の間に止められたら起こさない
            raise stopped_by(got[0] if got else signal.SIGHUP)
        born = time.time()   # 長の番号の再利用の目印（_tree_members の born）
        p = subprocess.Popen(argv, start_new_session=True, **popen_kw)
        while True:
            if got or os.getppid() != ppid:
                signum = got[0] if got else signal.SIGHUP
                stop(signum)
                raise stopped_by(signum)
            try:
                rc = p.wait(POLL)
                break
            except subprocess.TimeoutExpired:
                continue
        stop()      # 背景に残した孫
        if got:     # 待ち終えた後・後始末の間に届いた止める信号を落とさない
            raise stopped_by(got[0])
        return rc if rc >= 0 else 128 - rc
    finally:
        if p is not None and not stopped:
            stop()
        for s, h in old.items():
            signal.signal(s, h)


# ---------------------------------------------------------------- 同じ run の中の試験の結果の使い回し
NOTE_KEYS = ("reused", "reuse_off")   # reuse_run の note の欄。行へ写す口は note_fields
REUSE_SUB = "test-reuse"              # 試験の結果の控えの置き場の名（run の置き場の直下。同じ run の中でしか引かない）
REUSE_SCHEMA = "works-test-reuse/1"
RERUN_ENV = "GRAPHLOOPS_RERUN_CHECKS"   # 本流の引かずに走らせる旗と同じ名。読むのは呼び手（script）で、子には渡さない
# 指紋から外す環境変数: シェルの状態・接続と端末の識別子・起こした会話の識別子で、結果に効かない物だけ。迷う変数は入れる側に倒す
IGNORED_ENV = frozenset({
    "_", "PWD", "OLDPWD", "SHLVL",
    "SSH_CLIENT", "SSH_CONNECTION", "SSH_TTY", "SSH_AUTH_SOCK",
    "TERM_SESSION_ID", "ITERM_SESSION_ID", "WINDOWID", "TMUX", "TMUX_PANE", "STY", "SESSIONNAME",
    "VSCODE_GIT_IPC_HANDLE", "VSCODE_IPC_HOOK_CLI",
    "CLAUDE_CODE_SESSION_ID", "CLAUDE_PID", "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
})


def file_clock() -> float:
    """ファイルの時刻の時計で読んだ今（空のファイルを作って更新時刻を読む）。起こした時刻を、子が書く報告の更新時刻と比べる呼び手が使う。
    Linux はファイルの時刻を粗い時計（1 tick 遅れうる）で付けるので、time.time() と比べると起こした直後に書いた報告が起こすより古く見える"""
    with tempfile.NamedTemporaryFile() as f:
        return os.fstat(f.fileno()).st_mtime


def reuse_place(top, run: str, *, rerun: bool) -> dict | None:
    """使い回しの置き場 {dir, run, skip}: 控えは top（run の置き場）の直下の REUSE_SUB、run は控えに書いて引く時に照らす run の名、
    skip は引かずに走らせる理由（rerun が真なら旗 RERUN_ENV の文。置くのは続ける）。top か run が空なら None（控えを読まず書かない）。
    置き場・run の名・旗は呼び手が渡す（元 works/.shared/core/tree_run.py:542 `_plan` が環境変数から引いた分と、:661 `_no_reuse_reason`
    の旗の読み）"""
    if not top or not run:
        return None
    return {"dir": pathlib.Path(top) / REUSE_SUB, "run": run,
            "skip": f"旗 {RERUN_ENV} が立っている（引かずに回す。書くのは続ける）" if rerun else ""}


def child_env(env) -> dict:
    """reuse_run が子に渡す環境: 旗 RERUN_ENV を外す。外さないと、旗の有無だけで指紋が割れる。実行基盤が節に立てる変数は呼び手が先に落とす
    （元 works/.shared/core/tree_run.py:452 `child_env` の、実行基盤の名を含まない部分）"""
    return {k: v for k, v in env.items() if k != RERUN_ENV}


def _tool(argv0, cwd, path):
    """argv[0] の解決先の実パス・大きさ・更新時刻。/ を含む語は cwd から、含まない語は PATH から引く（子と同じ引き方）
    （元 works/.shared/core/tree_run.py:462）"""
    found = str(pathlib.Path(cwd) / argv0) if "/" in argv0 else shutil.which(argv0, path=path)
    if not found or not os.path.exists(found):
        return {"argv0": argv0, "missing": True}
    real = os.path.realpath(found)
    st = os.stat(real)
    return {"argv0": argv0, "path": real, "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def reuse_material(argv, env, cwd, outputs, tree) -> dict:
    """結果の使い回しの指紋の材料: 作業ツリーの木の sha（tree）・argv（頭の nice -n N は外す。outputs のパスは <out:i>、cwd の実パスは
    <cwd>）・OS と CPU の種類とカーネルの版・argv[0] を解決した実パスと大きさと更新時刻・子に渡す env の名ごとの sha256
    （IGNORED_ENV を除く。値の中の cwd の字は <cwd>）。env は子に渡す形（child_env の後）。
    引く時は材料の完全一致を見る——鍵（材料の sha256）は置き場の名にだけ使う（元 works/.shared/core/tree_run.py:472。枠の変数を外した）"""
    real = os.path.realpath(cwd)

    def plain(text):
        for i, out in enumerate(outputs):
            for form in {str(out), os.path.realpath(out)}:
                text = text.replace(form, f"<out:{i}>")
        return text.replace(real, "<cwd>").replace(str(cwd), "<cwd>")

    words = list(argv)
    if words[:2] == ["nice", "-n"] and len(words) > 3 and words[2].lstrip("-").isdigit():
        words = words[3:]
    return {"format": 1, "tree": tree, "argv": [plain(w) for w in words],
            "os": platform.system(), "machine": platform.machine(), "kernel": platform.release(),
            "tool": _tool(words[0], cwd, env.get("PATH", "")),
            "env": {k: hashlib.sha256(plain(v).encode("utf-8", "surrogateescape")).hexdigest()
                    for k, v in sorted(env.items()) if k not in IGNORED_ENV}}


def note_fields(note: dict) -> dict:
    """reuse_run の note のうち、行へ写す欄（NOTE_KEYS の在る物）。呼び手は欄の名を知らずにこれを写す
    （元 works/.shared/core/tree_run.py:496）"""
    return {k: note[k] for k in NOTE_KEYS if note.get(k)}


def reused_text(note: dict) -> str:
    """使い回した結果の出どころの句（報告に出す）: run <出どころ>・<控えた時刻>・鍵 <頭 12 字>。
    note（か note_fields を写した行）を受け、reused が無ければ空（元 works/.shared/core/tree_run.py:501）"""
    reused = note.get("reused")
    if not reused:
        return ""
    at = datetime.datetime.fromtimestamp(reused["at"]).astimezone().isoformat(timespec="seconds")
    return f"run {reused['from']}・{at}・鍵 {reused['key'][:12]}"


def _sink(f, which, why):
    """子の標準出力か標準エラーの行き先 f から、控えられる形 (パス, 書き始めの位置) を引く。DEVNULL と STDOUT（標準出力に
    併せる）は控える物が無いので None。引けなければ why に理由を積んで None（元 works/.shared/core/tree_run.py:519）"""
    if f is subprocess.DEVNULL or (which == "stderr" and f is subprocess.STDOUT):
        return None
    name = getattr(f, "name", None)
    if not (hasattr(f, "fileno") and "b" in getattr(f, "mode", "") and isinstance(name, str) and os.path.isfile(name)):
        why.append(f"{which} の行き先が控えられない（バイナリの通常のファイルでない）")
        return None
    f.flush()
    return name, os.fstat(f.fileno()).st_size


def new_group(steps, cwd) -> dict:
    """一式（宣言の段の並び）の使い回しの入れ物。steps は [{name, argv, outputs}]。sha は一式の宣言 [{argv, outputs}] の sha
    （outputs は cwd からのパス）で、各段の材料の欄 group に入る——段を 1 つずつ呼ぶ呼び手の控えと材料が割れ、一式の控えは replay_group だけが引く
    （段を 1 つずつ呼ぶ呼び手が引く控えは、一式を置く時に keep_group が別に置く）。
    pending は走らせた段の控えの下書き、failed は置かない理由。replay_group が木を取って tree に置く（元 works/.shared/core/tree_run.py:532）"""
    decl = [{"argv": list(s["argv"]), "outputs": [os.path.relpath(o, cwd) for o in s["outputs"]]} for s in steps]
    sha = hashlib.sha256(json.dumps(decl, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"sha": sha, "steps": [dict(s) for s in steps], "tree": None, "pending": [], "failed": [], "off": False}


def _plan(argv, env, outputs, popen_kw, note, place, group=None):
    """使い回しの計画 {store, name, material, key, tree, cwd, sinks, run}。place（reuse_place の返り）が None なら None（控えを読まず
    書かず、今どおり走らせる）。使えない理由が在れば note['reuse_off'] に置いて None。
    group（new_group の入れ物）が在れば、木は一式で 1 度だけ取った物（group['tree']）を使い、材料の欄 group に一式の sha を入れる
    （元 works/.shared/core/tree_run.py:542。置き場と run の名を環境変数でなく place から引く）"""
    if place is None:
        if group is not None:
            group["off"] = True
        return None
    cwd = popen_kw.get("cwd") or os.getcwd()
    why, sinks = [], []
    for which in ("stdout", "stderr"):
        f = popen_kw.get(which)
        sinks.append(None if f is not None and which == "stderr" and f is popen_kw.get("stdout") else _sink(f, which, why))
    tree = group["tree"] if group is not None else None
    if tree is None:
        try:
            tree = unittrees.fresh_tree(cwd)
        except (unittrees.UnitTreeError, OSError) as e:
            why.append(f"作業ツリーの木が取れない（{cwd}。git の木でない）: {e}"[:300])
    if why:
        note["reuse_off"] = "; ".join(why)
        if group is not None:
            group["off"] = True
        return None
    if group is not None:
        group["tree"] = tree
    material = {**reuse_material(argv, child_env(env), cwd, outputs, tree), "group": group["sha"] if group is not None else ""}
    key = _key(material)
    return {"store": webget.Store(pathlib.Path(place["dir"]), REUSE_SCHEMA, math.inf), "name": key + ".json",
            "material": material, "key": key, "tree": tree, "cwd": cwd, "sinks": sinks, "run": place["run"]}


def _key(material) -> str:
    """控えの鍵（材料の sha256）。置き場の名にだけ使い、引く時は材料の完全一致を見る（元 works/.shared/core/tree_run.py:578）"""
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _load_entry(plan, outputs):
    """同じ指紋の緑の控えを引いて確かめ、復号する ——（控え, 理由）。控え = {files（outputs ごとの中身か None）, std（標準出力・標準エラー）,
    reused（使い回しの行 {at, took_s（控えた時の実行の秒）, key, entry, from}。from は控えを書いた run の名）}。使えなければ (None, 理由)。
    何も書き戻さない（元 works/.shared/core/tree_run.py:583）"""
    short = f"鍵 {plan['key'][:12]}"
    doc = plan["store"].get(plan["name"], time.time())
    if not doc:
        if (plan["store"].root / plan["name"]).exists():
            return None, f"控えが読めない（壊れた JSON・型の違い・時刻 at の欠け。{short}）"
        return None, f"同じ指紋の控えが無い（{short}）"
    if doc.get("material") != plan["material"]:
        return None, f"控えの材料が今と違う（{short}）"
    if doc.get("exit") != 0:
        return None, f"控えが緑でない（終了コード {doc.get('exit')}。{short}）"
    if doc.get("run") != plan["run"]:
        return None, f"別の run の控えは使わない（控えの run {doc.get('run')}・今の run {plan['run']}。{short}）"
    files = doc.get("files")
    if not isinstance(files, list) or len(files) != len(outputs):
        return None, f"控えの files の長さが outputs と違う（控え {len(files) if isinstance(files, list) else files!r}・今 {len(outputs)}。{short}）"
    try:
        decoded = [None if b is None else base64.b64decode(b, validate=True) for b in files]
        std = [base64.b64decode(doc[k], validate=True) for k in ("out", "err")]
    except (KeyError, TypeError, ValueError) as e:   # binascii.Error は ValueError
        return None, f"控えの中身が壊れている（壊れた base64 か欄の欠け: {type(e).__name__}: {e}。{short}）"[:300]
    return ({"files": decoded, "std": std,
             "reused": {"at": doc["at"], "took_s": doc.get("took"), "key": plan["key"], "entry": str(plan["store"].root / plan["name"]),
                        "from": doc["run"]}}, "")


def _write_back(entries, popen_kws):
    """控えの中身を今の場所へ書き戻す。entries は [(outputs, _load_entry の控え)]、popen_kws は同じ並びの子の起こし方
    （標準出力・標準エラーの行き先 stdout・stderr）。全部を 1 つの try で書き、1 つでも失敗したら書いた outputs を消し、標準出力・標準エラーの
    行き先を書き始めの位置へ戻して（seek と truncate）理由を返す（全部か無し）。成功なら空（元 works/.shared/core/tree_run.py:612）"""
    written, marks = [], {}
    try:
        for (outputs, entry), kw in zip(entries, popen_kws):
            for path, data in zip(outputs, entry["files"]):
                if data is not None:
                    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
                    pathlib.Path(path).write_bytes(data)
                    written.append(path)
            out, err = kw.get("stdout"), kw.get("stderr")
            merged = err is subprocess.STDOUT or (err is not None and err is out)   # 標準エラーを標準出力に併せる呼び手には、控えの標準エラーも標準出力へ
            for data, f in ((entry["std"][0], out), (entry["std"][1], out if merged else err)):
                if data and f is not None and f is not subprocess.DEVNULL:
                    if id(f) not in marks:
                        f.flush()
                        marks[id(f)] = (f, f.tell())
                    f.write(data)
                    f.flush()
    except (KeyError, TypeError, ValueError, OSError) as e:
        stuck = []   # 戻せなかった物（理由に載せる。戻せたと言い切らない）
        for path in written:
            try:
                os.unlink(path)
            except OSError:
                stuck.append(str(path))
        for f, pos in marks.values():
            try:
                f.seek(pos)
                f.truncate()
            except (ValueError, OSError):
                stuck.append(f"ログの行き先 {getattr(f, 'name', '?')}")
        undone = f"戻せなかった: {'・'.join(stuck)}" if stuck else "書いた分は戻した"
        return f"控えの書き戻しに失敗した（{type(e).__name__}: {e}）"[:150] + f"。{undone}"[:300]
    return ""


def _lookup(plan, outputs, popen_kw):
    """同じ指紋の緑の控えを引き、標準出力・標準エラーと outputs のファイルを今の場所へ書き戻して ——（使い回しの行, 理由）。
    使えない・書き戻せないなら (None, 理由)（元 works/.shared/core/tree_run.py:651）"""
    entry, why = _load_entry(plan, outputs)
    if entry is None:
        return None, why
    why = _write_back([(outputs, entry)], [popen_kw])
    return (None, why) if why else (entry["reused"], "")


def replay_group(group, env, cwd, sinks, place):
    """一式（new_group の入れ物）の全段の控えを引き、全段が当たれば全段を 1 つの _write_back で全部か無しで書き戻す ——
    （段ごとの note（reuse_run の note と同じ形。reused に出どころ）, 理由）。外れれば何も書かず (None, どの段がなぜ外れたか。
    旗なら旗の文。呼び手は段ごとの reuse_run の skip に渡す)。place が None の run は (None, "")。
    sinks は段ごとの (標準出力, 標準エラー) の行き先。木はここで 1 度だけ取り、group['tree'] に置く（段ごとの計画も一式の木を使う）。
    一式の控えを引く口はここだけ（段を 1 つずつ呼ぶ reuse_run は group を渡されれば引かない）（元 works/.shared/core/tree_run.py:670）"""
    plans = []
    for step, (out, err) in zip(group["steps"], sinks):
        note = {}
        plan = _plan(step["argv"], env, step["outputs"], {"cwd": str(cwd), "stdout": out, "stderr": err}, note, place, group)
        if plan is None:
            return None, note.get("reuse_off", "")
        plans.append(plan)
    if place is None:
        return None, ""
    if place["skip"]:
        return None, place["skip"]
    entries = []
    for step, plan in zip(group["steps"], plans):
        entry, why = _load_entry(plan, step["outputs"])
        if entry is None:
            return None, f"段 {step['name']}: {why}"
        entries.append((step["outputs"], entry))
    why = _write_back(entries, [{"stdout": out, "stderr": err} for out, err in sinks])
    return (None, why) if why else ([{"reused": e["reused"]} for _, e in entries], "")


def _tree_moved(plan) -> str:
    """走らせた後の木が走らせる前と違えば、その理由（同じなら空）（元 works/.shared/core/tree_run.py:696）"""
    try:
        after = unittrees.fresh_tree(plan["cwd"])
    except (unittrees.UnitTreeError, OSError) as e:
        return f"走らせた後の作業ツリーの木が取れない: {e}"[:300]
    if after != plan["tree"]:
        return f"走らせている間に作業ツリーが変わった（.gitignore の外に物を作るか書き換えた。木 {plan['tree'][:12]} → {after[:12]}）"
    return ""


def _off(note, text):
    """note['reuse_off'] に理由を足す（先の理由が在れば『；』で続ける）（元 works/.shared/core/tree_run.py:707）"""
    note["reuse_off"] = f"{note['reuse_off']}；{text}" if note.get("reuse_off") else text


def _keep(plan, rc, started, wall, outputs, note, group=None):
    """緑（終了コード 0）で、走らせた前後の木が同じ回だけ控えに置く。置かない理由は note['reuse_off']。
    outputs は起こした時刻 started 以後に書かれた物だけを控える（前から残る古い報告は None。控えると書き戻しで新しい時刻を得て、
    報告の鮮度の確かめを通ってしまう）。
    group が在れば置かずに group['pending'] へ積み（置くのは全段が済んだ後の keep_group）、置かない理由は group['failed'] へ
    （一式の段も段ごとに前後の木を見る。途中で木が変わって後の段が戻した一式も置かない）（元 works/.shared/core/tree_run.py:712）"""
    refuse = group["failed"].append if group is not None else lambda text: _off(note, text)
    if rc != 0:
        refuse(f"終了コード {rc}（緑の回だけ控える）")
        return
    moved = _tree_moved(plan)
    if moved:
        refuse(moved)
        return
    enc = lambda b: base64.b64encode(b).decode("ascii")   # noqa: E731
    try:
        std = []
        for sink in plan["sinks"]:
            if sink is None:
                std.append(b"")
                continue
            with open(sink[0], "rb") as f:
                f.seek(sink[1])
                std.append(f.read())
        files = [enc(pathlib.Path(p).read_bytes()) if os.path.isfile(p) and os.stat(p).st_mtime >= started else None for p in outputs]
    except OSError as e:   # 控えの手間で緑の回を起こせなかった扱いにしない（呼び手は OSError を exit None と読む）
        refuse(f"出力が読めない: {e}"[:300])
        return
    doc = {"schema": REUSE_SCHEMA, "at": time.time(), "run": plan["run"], "material": plan["material"], "exit": 0,
           "out": enc(std[0]), "err": enc(std[1]), "files": files, "took": wall}
    if group is not None:
        group["pending"].append((plan, doc))
        return
    bad = plan["store"].put(plan["name"], doc)
    if bad:
        refuse(f"控えに書けない（{bad}）")


def keep_group(group, notes) -> None:
    """一式の全段が済んだ後に呼ぶ。全段が終了コード 0 で、各段の前後の木が同じ時だけ全段の控えを置く。一式の控え（replay_group が
    引く）と並べて、段ごとに一式の外の呼び（材料の欄 group が空。TDD の輪の頭の test_cmd など）が引く控えも置く。段の緑は前の段が
    .gitignore の下に残した物の在る所で取れた物だが、引く呼びは同じ run の中で一式の後に起きるので、その物は普通そのまま在る
    （.gitignore の下の物が鍵に入らないのは、一式の外どうしの控えと同じ限り）。逆に一式の外の控えで一式を埋めることはしない
    （一式を引く回は前の段を走らせずに後の段を使うので、前の段の副作用が無いまま後の段の緑を使うことになる）。置かなかった理由は、段ごとの
    note（reuse_run に渡した物）の reuse_off に足す。置き場の無い run・木が取れなかった run は何も足さない（元 works/.shared/core/tree_run.py:750）"""
    why = _group_unkept(group)
    if why:
        for note in notes:
            _off(note, why)


def _group_unkept(group) -> str:
    """keep_group の本体: 一式を置き、置かなかった理由（置いたら空）を返す（元 works/.shared/core/tree_run.py:763）"""
    if group["off"] or group["tree"] is None:
        return ""
    if group["failed"]:
        return "一式を控えない: " + "；".join(group["failed"])
    if len(group["pending"]) != len(group["steps"]):
        return f"一式を控えない: 起こせなかった段が在る（走った {len(group['pending'])}・宣言 {len(group['steps'])}）"
    puts = []
    for plan, doc in group["pending"]:
        alone = {**plan["material"], "group": ""}
        puts += [(plan["store"], plan["name"], doc), (plan["store"], _key(alone) + ".json", {**doc, "material": alone})]
    bad = [b for b in (store.put(name, doc) for store, name, doc in puts) if b]
    return f"一式を控えない: 控えに書けない（{bad[0]}）" if bad else ""


def reuse_run(argv, env, *, place, outputs=(), note=None, skip="", group=None, **popen_kw) -> int:
    """argv を run で走らせて終了コードを返す。子に渡す環境は child_env(env)。止められたら Stopped が、起こせなければ OSError が上がる。
    **同じ run の中の使い回し**: place（reuse_place の返り）が在れば、その置き場に試験の結果を控える。同じ指紋（reuse_material。
    作業ツリーの木・argv・環境・道具）の緑の控えが在れば、子を起こさずに 0 を返し、標準出力・標準エラー・outputs（試験が書く報告の
    ファイルの絶対パス）の中身を今の場所へ書き戻し、note['reused'] = {at, took_s, key, entry, from（控えを書いた run の名）} を置く。
    別の run の控えは引かない。置くのは終了コード 0 で、走らせた前後の木が同じ回だけ（赤・.gitignore の外に物を作る回は置かず、
    理由を note['reuse_off'] に置く）。使い回せなかった理由（控えが無い・壊れている・別の run の控え・書き戻せない・skip・旗）は
    note['reuse_off'] に置く（欄を行へ写す口は note_fields）。
    skip（理由の文）か place の旗が在れば、引かずに走らせる（置くのは続ける）。group（new_group の入れ物）を渡した呼びは引かない
    （一式の控えは replay_group だけが引く）。控えは置かずに group に積み、全段が済んだ後の keep_group が全段が緑の時だけ置く。
    stdout・stderr はバイナリの通常のファイル（か DEVNULL・STDOUT）の時だけ控えられる
    （元 works/.shared/core/tree_run.py:779 `slotted_run` から、機械全体の試験の枠（slotwrap.sh）と待った秒を外した物。名は枠を
    持たないので変えた）"""
    note = {} if note is None else note
    outputs = [str(o) for o in outputs]
    plan = _plan(argv, env, outputs, popen_kw, note, place, group)
    if plan:
        reason = skip or place["skip"]
        if group is None and not reason:
            reused, reason = _lookup(plan, outputs, popen_kw)
            if reused:
                note["reused"] = reused
                return 0
        if reason:
            _off(note, reason)
    started = file_clock()
    rc = run(argv, env=child_env(env), **popen_kw)
    if plan:
        _keep(plan, rc, started, round(time.time() - started, 1), outputs, note, group)
    return rc


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--"]:
        args = args[1:]
    cmd = " ".join(args) if args else os.environ.get("INPUTS_CMD", "")
    if not cmd.strip():
        print("tree_run: コマンドが空（-- の後か INPUTS_CMD に書く）", file=sys.stderr)
        return 2
    try:
        return run(["/bin/sh", "-c", cmd])
    except Stopped as e:
        return 128 + e.signum


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):   # Windows の既定 cp1252 で日本語の出力が落ちないように
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    sys.exit(main())
