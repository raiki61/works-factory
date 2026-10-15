"""コマンドを木ごと止める殻（.shared/core/tree_run.py）の検査。

- 終了コードをそのまま返す（0・3・信号で死んだら 128+信号）
- 殻が SIGTERM を受けたら、コマンドが背景に起こした孫まで止め、孫は後から作業ツリーに書かない
- SIGTERM を無視する孫は猶予の後に SIGKILL で止める。猶予は実行基盤の cancel の猶予（5 秒）より短く、その内に孫が消える
- コマンドが終わった後に背景に残した孫も止める
- 自分で setsid して別のセッション（= 別のグループ）へ出た孫も、殻が SIGTERM を受けたら止める（SIGTERM を無視しても
  実行基盤の猶予の内に SIGKILL で）
- 名指しの ps そのものが固まっても、ps より前にグループを凍らせ、ps が戻れば消す
- 凍らせたグループは SIGTERM の後に SIGCONT で起こすので、子の SIGTERM の受け手が走る
- 長を回収した後は（番号が再利用されうるので）ps より前に凍らせない
- 生きた仲間の居ないグループ（ゾンビだけ）に惑わされず、別のグループへ出た生きた仲間を止めて、猶予を使い切らずに戻る
- 殻の直下の親（節では uv）が kill -9 で消えたら（親が替わったら）木ごと止める。起きた時に既に孤児（親が 1）なら走らせない
- 終わりを待ち終えた直後に届いた止める信号も落とさない
- pack の中に __pycache__ を作らない（試験が持つ写しの pack で見る）
孫の生死はプロセスグループ（コマンドの sh の pid と同じ番号）が空かで見る。グループの外へ出た孫は、孫が書いた pid で見る。
"""
import itertools
import json
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
TREE_RUN = LIB / "tree_run.py"
sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import tree_run  # noqa: E402
import userenv  # noqa: E402
from tests.bin import gitkit, hermetic  # noqa: E402


def group_gone(pgid, within):
    """within 秒の内にプロセスグループが空になれば True"""
    end = time.monotonic() + within
    while True:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        if time.monotonic() >= end:
            return False
        time.sleep(0.05)


def pid_gone(pid, within):
    end = time.monotonic() + within
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        if time.monotonic() >= end:
            return False
        time.sleep(0.05)


def read_int(path, within=10):
    """コマンドが書く pid のファイルを待って読む"""
    end = time.monotonic() + within
    while time.monotonic() < end:
        try:
            text = path.read_text().strip()
        except FileNotFoundError:
            text = ""
        if text:
            return int(text)
        time.sleep(0.05)
    raise AssertionError(f"{path} が書かれない")


class TreeRunCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 木ごと止める殻はプロセスのグループ（os.killpg・os.setsid。Python の公式文書で Availability: Unix）で孫を見る
        if not (hasattr(os, "killpg") and hasattr(os, "setsid")):
            raise unittest.SkipTest("SKIP process-group: この OS の os に killpg・setsid が無い")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.pidf = self.tmp / "pgid"
        self.marker = self.tmp / "late"
        self.env = {k: v for k, v in hermetic.child_env().items() if k != "PYTHONDONTWRITEBYTECODE"}
        # このテストが起こした物（後片付けで止める Popen・pgid・pid）。pgid・pid は消えたと確かめた時点で外す——
        # 確かめた後に同じ番号が別のプロセスに再利用されても、後片付けで送らない。Popen は回収済みなら送らない
        self.started = []

    def tearDown(self):
        for kind, n in self.started:
            try:
                if kind == "popen":
                    if n.poll() is None:
                        n.kill()
                        n.wait(5)
                else:
                    (os.killpg if kind == "pg" else os.kill)(n, signal.SIGKILL)
            except (OSError, subprocess.SubprocessError):
                pass
        self._tmp.cleanup()

    def group_gone(self, pgid, within):
        """group_gone と同じ。空と確かめたら後片付けの対象から外す"""
        gone = group_gone(pgid, within)
        if gone and ("pg", pgid) in self.started:
            self.started.remove(("pg", pgid))
        return gone

    def pid_gone(self, pid, within):
        """pid_gone と同じ。消えたと確かめたら後片付けの対象から外す"""
        gone = pid_gone(pid, within)
        if gone and ("pid", pid) in self.started:
            self.started.remove(("pid", pid))
        return gone

    def cli(self, *args):
        return [sys.executable, str(TREE_RUN), *args]

    def start(self, cmd, **kw):
        p = subprocess.Popen(self.cli("--", cmd), env=self.env, cwd=str(self.tmp), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        self.started.append(("popen", p))
        return p

    def wait_pgid(self):
        pgid = read_int(self.pidf)
        self.started.append(("pg", pgid))
        return pgid

    def run_cli(self, *args, env=None):
        return subprocess.run(self.cli(*args), env=env or self.env, cwd=str(self.tmp), capture_output=True, text=True, encoding="utf-8",
                              timeout=60)

    # ------------------------------------------------ 終了コード
    def test_exit_codes(self):
        for cmd, want in (("true", 0), ("exit 3", 3), ("kill -KILL $$", 128 + signal.SIGKILL)):
            with self.subTest(cmd):
                self.assertEqual(self.run_cli("--", cmd).returncode, want)

    def test_output_passes_through(self):
        r = self.run_cli("--", "echo 出た; echo 誤り >&2")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "出た\n", "誤り\n"))

    def test_empty_command_is_refused(self):
        for args in ((), ("--",), ("--", "  ")):
            with self.subTest(args=args):
                r = self.run_cli(*args)
                self.assertEqual(r.returncode, 2)
                self.assertTrue(r.stderr)

    # ------------------------------------------------ 木ごと止める
    def test_sigterm_stops_grandchildren(self):
        # 孫 2 つ: 長い sleep と、3 秒後に作業ツリーへ書く物。殻を止めたら両方消え、書き込みは起きない
        p = self.start(f"echo $$ > {self.pidf}; sleep 300 & (sleep 3; echo late > {self.marker}) & wait")
        pgid = self.wait_pgid()
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(10), 128 + signal.SIGTERM)
        self.assertTrue(self.group_gone(pgid, 2), "孫が残った")
        time.sleep(4)
        self.assertFalse(self.marker.exists(), "止めた後に孫が書いた")

    def test_sigint_stops_background_that_ignores_sigint(self):
        # 非対話の sh は背景の子の SIGINT を無視させる。SIGINT を受けても SIGTERM まで送って木を止める
        p = self.start(f"echo $$ > {self.pidf}; sleep 300 & wait")
        pgid = self.wait_pgid()
        t0 = time.monotonic()
        p.send_signal(signal.SIGINT)
        # 木は猶予（KILL_GRACE）より短く消える。猶予まで待ったなら SIGTERM を送っていない。上限は猶予の 3/4: 止める手順は
        # ps を 2 回起こす（数え上げと数え直し）ので、負荷の高い機械（load average 100 前後）では半分の 1 秒を越えることがある。
        # 殻が抜けるのは木が消えてから LINGER 後なので、殻の終わりでなく木の消えた時で計る
        self.assertTrue(self.group_gone(pgid, tree_run.KILL_GRACE * 0.75), "SIGKILL の猶予まで待った（SIGTERM を送っていない）")
        self.assertLess(time.monotonic() - t0, tree_run.KILL_GRACE * 0.75)
        self.assertEqual(p.wait(10), 128 + signal.SIGINT)

    def test_sigterm_ignoring_grandchild_is_killed(self):
        p = self.start(f"echo $$ > {self.pidf}; (trap '' TERM; sleep 300) & wait")
        pgid = self.wait_pgid()
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(15), 128 + signal.SIGTERM)
        self.assertTrue(self.group_gone(pgid, 1), "SIGTERM を無視する孫が残った")

    def test_sigterm_ignoring_grandchild_is_killed_before_host_kills_tree_run(self):
        # 実行基盤の cancel は持ち主のグループへ SIGTERM を送り、5 秒（TERMINATION_GRACE_MS）待って SIGKILL を送る。
        # tree_run の猶予が同じ 5 秒だと、孫へ SIGKILL を送る前に tree_run が殺され、孫が残った（試し P11 の mode=c）。
        # SIGTERM を無視する孫も、実行基盤の猶予より前に消えていること
        host_grace = 5.0
        self.assertLess(tree_run.KILL_GRACE, host_grace)
        p = self.start(f"echo $$ > {self.pidf}; (trap '' TERM; sleep 300) & wait")
        pgid = self.wait_pgid()
        t0 = time.monotonic()
        p.send_signal(signal.SIGTERM)
        self.assertTrue(self.group_gone(pgid, host_grace), "実行基盤の猶予の内に孫が消えなかった")
        self.assertLess(time.monotonic() - t0, host_grace)
        self.assertEqual(p.wait(10), 128 + signal.SIGTERM)

    def test_leftover_background_is_stopped_after_exit(self):
        # コマンドは緑で終わったが背景に孫を残した。殻が戻る時には孫も居ない
        r = self.run_cli("--", f"sleep 300 & echo $! > {self.pidf}; exit 0")
        self.assertEqual(r.returncode, 0)
        pid = read_int(self.pidf)
        self.started.append(("pid", pid))
        self.assertTrue(self.pid_gone(pid, 2), "背景の孫が残った")

    def test_parent_death_stops_tree(self):
        # 殻の親（実行基盤が起こす uv の代わり）が kill -9 で消えたら、殻は親の替わりに気づいて木ごと止める
        cmd = f"echo $$ > {self.pidf}; sleep 300 & (sleep 3; echo late > {self.marker}) & wait"
        wrapper = ("import subprocess, sys, time\n"
                   f"p = subprocess.Popen([sys.executable, {str(TREE_RUN)!r}, '--', {cmd!r}], stdout=subprocess.DEVNULL)\n"
                   "print(p.pid, flush=True)\n"
                   "time.sleep(600)\n")
        w = subprocess.Popen([sys.executable, "-c", wrapper], env=self.env, cwd=str(self.tmp), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, text=True, encoding="utf-8", start_new_session=True)
        self.started.append(("pg", w.pid))
        tree_pid = int(w.stdout.readline())
        self.started.append(("pid", tree_pid))
        pgid = self.wait_pgid()
        w.kill()
        w.wait(5)
        w.stdout.close()
        self.assertTrue(self.group_gone(pgid, 8), "親が消えた後に孫が残った")
        self.assertTrue(self.pid_gone(tree_pid, 8), "殻が残った")
        self.assertTrue(self.group_gone(w.pid, 2), "殻の親のグループが残った")
        time.sleep(3)
        self.assertFalse(self.marker.exists(), "親が消えた後に孫が書いた")

    def test_orphan_at_start_does_not_run(self):
        # 起きた時に既に親が 1（直下の親が先に消えた）なら、親の替わりを待てないので何も走らせずに止まる
        outer = (f"(sleep 0.5; exec {sys.executable} {TREE_RUN} -- 'echo ran > {self.marker}') "
                 ">/dev/null 2>&1 </dev/null & exit 0")
        subprocess.run(["/bin/sh", "-c", outer], env=self.env, cwd=str(self.tmp), timeout=10, check=True)
        time.sleep(3)
        self.assertFalse(self.marker.exists(), "孤児で起きたのにコマンドを走らせた")

    def test_signal_right_after_wait_is_not_dropped(self):
        # 子の終わりを待ち終えた直後（後始末の前）に届いた SIGTERM も、止められたとして Stopped にする
        class LateSignal(subprocess.Popen):
            def wait(self, timeout=None):
                rc = super().wait()
                os.kill(os.getpid(), signal.SIGTERM)
                return rc

        with mock.patch.object(tree_run.subprocess, "Popen", LateSignal):
            with self.assertRaises(tree_run.Stopped) as cm:
                tree_run.run(["/bin/sh", "-c", "exit 0"])
        self.assertEqual(cm.exception.signum, signal.SIGTERM)

    def test_signal_during_launch_proof_stops_without_launching(self):
        # 起こす前の証明（bash の command -v。BASH_ENV を読む）が遅くても、その間に届いた SIGTERM で証明を捨て、コマンドを
        # 起こさずに Stopped にする（証明の待ちが 実行基盤の cancel の猶予の勘定に足されない）
        slow = self.tmp / "slow-env.sh"
        slow.write_text("sleep 4\n")
        env = {**self.env, "BASH_ENV": str(slow)}
        argv = ["bash", "-c", f"touch {self.marker}"]
        launched = []

        class Seen(subprocess.Popen):
            def __init__(self, args, *a, **kw):
                launched.append(list(args))
                super().__init__(args, *a, **kw)

        timer = threading.Timer(0.3, os.kill, (os.getpid(), signal.SIGTERM))
        timer.start()
        self.addCleanup(timer.cancel)
        t0 = time.monotonic()
        with mock.patch.object(tree_run.subprocess, "Popen", Seen), self.assertRaises(tree_run.Stopped) as cm:
            tree_run.run(argv, env=env, cwd=str(self.tmp))
        self.assertEqual(cm.exception.signum, signal.SIGTERM)
        self.assertLess(time.monotonic() - t0, tree_run.POLL + tree_run.LINGER + 1.5, "証明を待ち切ってから止めた")
        self.assertNotIn(argv, launched, "止められたのにコマンドを起こした")

    # ------------------------------------------------ グループの外へ出た孫
    def setsid_sleeper(self, pidf, ignore_term=False):
        """setsid で新しいセッションへ出て、自分の pid を pidf に書いて眠る孫（python。macOS に setsid の道具は無い）"""
        body = ("import os, signal, time\n"
                + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if ignore_term else "")
                + "os.setsid()\n"
                f"open({str(pidf)!r}, 'w').write(str(os.getpid()))\n"
                "time.sleep(300)\n")
        return f"{sys.executable} -c {shlex.quote(body)}"

    def wait_pid(self, path):
        pid = read_int(path)
        self.started.append(("pid", pid))
        return pid

    def test_sigterm_stops_setsid_grandchild(self):
        # 孫が setsid で別のセッション（別のグループ）へ出ても、親子の鎖で拾って止める
        gpidf = self.tmp / "gpid"
        p = self.start(f"echo $$ > {self.pidf}; {self.setsid_sleeper(gpidf)} & wait")
        pgid = self.wait_pgid()
        gpid = self.wait_pid(gpidf)
        self.assertEqual(os.getsid(gpid), gpid, "孫が setsid していない（試験の前提）")
        p.send_signal(signal.SIGTERM)
        self.assertTrue(self.pid_gone(gpid, tree_run.KILL_GRACE + 1), "setsid で出た孫が残った")
        self.assertEqual(p.wait(10), 128 + signal.SIGTERM)
        self.assertTrue(self.group_gone(pgid, 1))

    def test_sigterm_ignoring_setsid_grandchild_is_killed_before_host_kills_tree_run(self):
        # setsid で出て SIGTERM も無視する孫も、実行基盤の cancel の猶予（5 秒）より前に SIGKILL で消える
        host_grace = 5.0
        gpidf = self.tmp / "gpid"
        p = self.start(f"echo $$ > {self.pidf}; {self.setsid_sleeper(gpidf, ignore_term=True)} & wait")
        pgid = self.wait_pgid()
        gpid = self.wait_pid(gpidf)
        t0 = time.monotonic()
        p.send_signal(signal.SIGTERM)
        self.assertTrue(self.pid_gone(gpid, host_grace), "実行基盤の猶予の内に setsid で出た孫が消えなかった")
        self.assertLess(time.monotonic() - t0, host_grace)
        self.assertEqual(p.wait(10), 128 + signal.SIGTERM)
        self.assertTrue(self.group_gone(pgid, 1))

    def test_zombie_only_group_does_not_hide_live_members(self):
        # コマンドの sh（グループ G の長）が緑で終わった時、G に残るのはゾンビ Z だけ。Z の親 A は setpgid で別のグループへ
        # 出て（セッションは G のまま）Z を回収せずに眠る。macOS はゾンビだけのグループへの killpg を EPERM で拒むので、
        # グループだけを見ると A に届かず、猶予を使い切っても A が残る。仲間を数え上げて A を止め、猶予を待たずに戻る
        apidf = self.tmp / "apid"
        body = ("import os, subprocess, time\n"
                "g = os.getpgid(0)\n"
                "os.setpgid(0, 0)\n"
                "z = os.fork()\n"
                "if z == 0:\n"
                "    os.setpgid(0, g)\n"
                "    os._exit(0)\n"
                # Z が終わるまで待つ。回収はしない（ゾンビのまま）。os.waitid（WNOWAIT）は macOS の Python 3.12 以前に無いので ps の状態で見る
                "while not subprocess.run(['ps', '-o', 'stat=', '-p', str(z)], capture_output=True,\n"
                "                         text=True).stdout.strip().startswith('Z'):\n"
                "    time.sleep(0.02)\n"
                f"open({str(apidf)!r}, 'w').write(str(os.getpid()))\n"
                "time.sleep(300)\n")
        p = self.start(f"echo $$ > {self.pidf}; {sys.executable} -c {shlex.quote(body)} & "
                       f"while [ ! -s {apidf} ]; do sleep 0.05; done; exit 0")
        pgid = self.wait_pgid()
        apid = self.wait_pid(apidf)
        t0 = time.monotonic()
        self.assertEqual(p.wait(15), 0)
        self.assertLess(time.monotonic() - t0, tree_run.KILL_GRACE * 1.5, "ゾンビだけのグループで猶予を使い切った")
        self.assertTrue(self.pid_gone(apid, 1), "ゾンビだけのグループの向こうの生きた仲間が残った")
        self.assertTrue(self.group_gone(pgid, 2))

    # ------------------------------------------------ 止めた後に抜ける前の待ち（試し P17 の Ctrl-C の穴）
    def test_stop_budget_is_under_host_grace(self):
        # 信号に気づくまで POLL、SIGKILL まで KILL_GRACE と ps の 1 回、抜けるまで LINGER。期限の無い ps の回の分を残して、
        # 和が 実行基盤の cancel の猶予（5 秒）より短いこと（0.2 + 2 + 1 = 3.2 秒）。ps に期限を置かない（E12）
        host_grace = 5.0
        self.assertGreaterEqual(tree_run.LINGER, 1.0)
        self.assertLess(tree_run.POLL + tree_run.KILL_GRACE + tree_run.LINGER, host_grace)
        self.assertFalse(hasattr(tree_run, "PS_TIMEOUT"))

    def test_ps_is_named_by_path_without_timeout(self):
        # 期限の替わりに、止まらない形を命令の選びで持つ: PATH から引かずに /bin/ps を名指し、期限を渡さない
        with mock.patch.object(tree_run.subprocess, "run", wraps=subprocess.run) as run:
            rows, why = tree_run._ps_all()
        self.assertIsNone(why)
        self.assertIn(os.getpid(), rows)
        call = run.call_args
        self.assertEqual(call.args[0][0], tree_run.PS)
        self.assertEqual(tree_run.PS, "/bin/ps")
        self.assertNotIn("timeout", call.kwargs)

    def test_stopped_run_lingers_before_exit_within_host_grace(self):
        # 止める信号で木を止めた後、殻は LINGER 秒待ってから抜ける（節がすぐ死ぬと 実行基盤の run が running のまま固まる。
        # 1 秒残ると failed になり resume できた——試し P17）。SIGTERM を無視する孫（猶予を使い切る道）でも、殻が抜けるのは
        # 実行基盤の猶予（5 秒）より前
        host_grace = 5.0
        for name, cmd in (("quick", "sleep 300 & wait"), ("ignores-term", "(trap '' TERM; sleep 300) & wait")):
            with self.subTest(name):
                pidf = self.tmp / f"pgid-{name}"
                p = subprocess.Popen(self.cli("--", f"echo $$ > {pidf}; {cmd}"), env=self.env, cwd=str(self.tmp),
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.started.append(("popen", p))
                pgid = read_int(pidf)
                self.started.append(("pg", pgid))
                t0 = time.monotonic()
                p.send_signal(signal.SIGTERM)
                self.assertTrue(self.group_gone(pgid, host_grace), "木が消えなかった")
                t_gone = time.monotonic()
                self.assertEqual(p.wait(host_grace), 128 + signal.SIGTERM)
                t_exit = time.monotonic()
                # 木が消えたと見えた時刻 t_gone は見張りの間隔と負荷の分だけ遅れる（CI の macOS で 0.88 秒の実測）。
                # 守りたいのは「すぐ抜けない」ことなので、LINGER の半分を下限にする
                self.assertGreaterEqual(t_exit - t_gone, tree_run.LINGER / 2, "木を止めた後すぐに抜けた")
                self.assertLess(t_exit - t0, host_grace, "実行基盤の猶予の内に抜けなかった")

    def test_normal_exit_does_not_linger(self):
        # コマンドが自分で終わった回は待たない（LINGER を大きくしても、すぐ戻る）
        with mock.patch.object(tree_run, "LINGER", 30, create=True):
            t0 = time.monotonic()
            self.assertEqual(tree_run.run(["/bin/sh", "-c", "exit 0"]), 0)
            self.assertLess(time.monotonic() - t0, 10)

    # ------------------------------------------------ ps が遅い・壊れている
    def test_hanging_or_failing_ps_still_stops_before_host_kills_tree_run(self):
        # ps が固まる・失敗する場でも、止める手順は 実行基盤の cancel の猶予（5 秒）の内に SIGTERM を無視する孫へ SIGKILL を
        # 届ける。固まる ps は PATH の替え玉で、殻は /bin/ps を名指すので拾わない。失敗する ps（表を読めない）ではグループへ
        # 直ちに送り、以後の回は ps を起こさない
        host_grace = 5.0
        with self.subTest("hanging ps on PATH"):
            fake = self.tmp / "bin-hanging"
            fake.mkdir()
            (fake / "ps").write_text("#!/bin/sh\nexec sleep 300\n")
            (fake / "ps").chmod(0o755)
            env = {**self.env, "PATH": f"{fake}{os.pathsep}{self.env.get('PATH', '')}"}
            p = subprocess.Popen(self.cli("--", f"echo $$ > {self.pidf}; (trap '' TERM; sleep 300) & wait"), env=env,
                                 cwd=str(self.tmp), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            self.started.append(("popen", p))
            pgid = self.wait_pgid()
            t0 = time.monotonic()
            p.send_signal(signal.SIGTERM)
            self.assertTrue(self.group_gone(pgid, host_grace), "PATH に固まる ps が在る場で、実行基盤の猶予の内に孫が消えなかった")
            self.assertEqual(p.wait(host_grace), 128 + signal.SIGTERM)
            self.assertLess(time.monotonic() - t0, host_grace, "PATH に固まる ps が在る場で、実行基盤の猶予の内に抜けなかった")
        with self.subTest("failing ps"):
            fake = self.tmp / "failing-ps"
            fake.write_text("#!/bin/sh\necho 壊れた >&2; exit 1\n")
            fake.chmod(0o755)
            child = self.tmp / "child"
            p = subprocess.Popen(["/bin/sh", "-c", f"(trap '' TERM; echo $$ > {child}; sleep 300) & wait"],
                                 start_new_session=True, stdin=subprocess.DEVNULL, env=hermetic.child_env())
            self.started.extend([("popen", p), ("pg", p.pid)])
            read_int(child)
            t0 = time.monotonic()
            with mock.patch.object(tree_run, "PS", str(fake)):
                why = tree_run.stop_group(p)
            self.assertIn("数え上げられない", why or "")
            self.assertTrue(self.group_gone(p.pid, host_grace), "ps が失敗する場で、実行基盤の猶予の内に孫が消えなかった")
            self.assertLess(time.monotonic() - t0, host_grace)

    def test_group_is_frozen_before_ps_even_if_ps_hangs(self):
        # 名指しの PS そのものが固まっても（期限は置かない。E12）、長が回収前なら ps より前にグループを SIGSTOP で止めるので、
        # グループの子は ps を待つ間も走らない（作業ツリーに書かない）。ps が戻れば SIGTERM と SIGCONT で消える。
        # stop_group は固まった ps を待つので別の糸で呼び、子の状態を本物の /bin/ps で見る
        fake = self.tmp / "hanging-ps"
        ps_pidf = self.tmp / "ps-pid"
        fake.write_text(f"#!/bin/sh\necho $$ > {ps_pidf}\nexec sleep 300\n")
        fake.chmod(0o755)
        child = self.tmp / "child"
        p = subprocess.Popen(["/bin/sh", "-c", f"sleep 300 & echo $! > {child}; wait"], start_new_session=True,
                             stdin=subprocess.DEVNULL, env=hermetic.child_env())
        self.started.extend([("popen", p), ("pg", p.pid)])
        cpid = read_int(child)
        with mock.patch.object(tree_run, "PS", str(fake)):
            stopper = threading.Thread(target=tree_run.stop_group, args=(p,), daemon=True)
            stopper.start()
            ps_pid = None
            try:
                ps_pid = read_int(ps_pidf)
                state = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(cpid)], capture_output=True, text=True,
                                       timeout=30, env=hermetic.child_env()).stdout.strip()
                self.assertTrue(state.startswith("T"), f"ps が固まる間、グループの子が止まっていない（stat {state!r}）")
            finally:
                if ps_pid is not None:
                    os.kill(ps_pid, signal.SIGKILL)
                stopper.join(10)
        self.assertFalse(stopper.is_alive(), "固まった ps を殺した後も stop_group が戻らない")
        self.assertTrue(self.pid_gone(cpid, 1), "ps が戻った後、止めたグループの子が消えない")
        self.assertTrue(self.group_gone(p.pid, 1))

    def test_frozen_group_is_continued_so_its_sigterm_handler_runs(self):
        # 凍らせたグループへは SIGTERM の後に SIGCONT を送るので、子の SIGTERM の受け手が走る（後始末ができる）。
        # SIGCONT が無いと子は凍ったまま SIGKILL で消え、受け手は走らない
        ready, handled = self.tmp / "ready", self.tmp / "handled"
        p = subprocess.Popen(["/bin/sh", "-c", f"(trap 'echo 1 > {handled}; exit 0' TERM; echo 1 > {ready}; "
                                               "while :; do sleep 0.05; done) & wait"],
                             start_new_session=True, stdin=subprocess.DEVNULL, env=hermetic.child_env())
        self.started.extend([("popen", p), ("pg", p.pid)])
        read_int(ready)
        self.assertIsNone(tree_run.stop_group(p))
        self.assertTrue(handled.exists(), "凍らせたグループの子の SIGTERM の受け手が走らなかった")
        self.assertTrue(self.group_gone(p.pid, 1))

    def test_group_is_not_frozen_after_leader_is_reaped(self):
        # 長を回収した後は番号が再利用されうるので、ps より前に凍らせない（数えてから送る）。固まる ps を待つ間、
        # 長が残した子は止まっていない。ps が戻れば子は消える
        fake = self.tmp / "hanging-ps"
        ps_pidf = self.tmp / "ps-pid"
        fake.write_text(f"#!/bin/sh\necho $$ > {ps_pidf}\nexec sleep 300\n")
        fake.chmod(0o755)
        child = self.tmp / "child"
        p = subprocess.Popen(["/bin/sh", "-c", f"sleep 300 & echo $! > {child}; exit 0"], start_new_session=True,
                             stdin=subprocess.DEVNULL, env=hermetic.child_env())
        self.started.extend([("popen", p), ("pg", p.pid)])
        cpid = read_int(child)
        self.started.append(("pid", cpid))
        p.wait(10)
        with mock.patch.object(tree_run, "PS", str(fake)):
            stopper = threading.Thread(target=tree_run.stop_group, args=(p,), daemon=True)
            stopper.start()
            ps_pid = None
            try:
                ps_pid = read_int(ps_pidf)
                state = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(cpid)], capture_output=True, text=True,
                                       timeout=30, env=hermetic.child_env()).stdout.strip()
                self.assertFalse(state.startswith("T"), f"回収した長のグループを ps より前に凍らせた（stat {state!r}）")
            finally:
                if ps_pid is not None:
                    os.kill(ps_pid, signal.SIGKILL)
                stopper.join(10)
        self.assertFalse(stopper.is_alive(), "固まった ps を殺した後も stop_group が戻らない")
        self.assertTrue(self.pid_gone(cpid, 1), "ps が戻った後、回収した長が残した子が消えない")

    # ------------------------------------------------ pack を汚さない
    def test_no_bytecode_in_pack(self):
        # 共有の作業ツリーを見ると別の実行が残した __pycache__ を拾うので、この試験だけが持つ写しで起こす。
        # core ごと写す（tree_run.py は隣の slotwrap.sh を __file__ から引く）
        core = self.tmp / "core"
        shutil.copytree(TREE_RUN.parent, core, ignore=shutil.ignore_patterns("__pycache__"))
        r = subprocess.run([sys.executable, str(core / "tree_run.py"), "--", "true"], env=self.env, cwd=str(self.tmp),
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(core.rglob("__pycache__")), [])



class OutsideEnvCase(unittest.TestCase):
    """uv run の外の環境（tree_run.outside_env。blk-tests の run_tests と盤面の tree_runner が使う。台帳 R23）"""

    def test_strips_path_front_inside_uv(self):
        """uv run の中（UV_RUN_RECURSION_DEPTH が在る）: PATH の頭のこの python の bin を 1 度だけ外し、後ろの同じフォルダは残す。
        sys.prefix を指す VIRTUAL_ENV・UV_RUN_RECURSION_DEPTH・UV_NO_CONFIG を外し、PYTHONDONTWRITEBYTECODE=1 を立てる"""
        ours = os.path.dirname(sys.executable)
        env = tree_run.outside_env({"PATH": os.pathsep.join([ours, "/usr/bin", ours]), "UV_RUN_RECURSION_DEPTH": "1",
                                    "VIRTUAL_ENV": sys.prefix, "UV_NO_CONFIG": "1", "HOME": "/h"})
        self.assertEqual(env, {"PATH": os.pathsep.join(["/usr/bin", ours]), "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/h"})

    def test_keeps_foreign_venv_and_outside_uv(self):
        """sys.prefix でない VIRTUAL_ENV（利用者の物）は残す。uv run の外なら PATH も VIRTUAL_ENV も触らない（UV_NO_CONFIG は外す）"""
        ours = os.path.dirname(sys.executable)
        env = tree_run.outside_env({"PATH": ours, "UV_RUN_RECURSION_DEPTH": "1", "VIRTUAL_ENV": "/elsewhere"})
        self.assertEqual(env, {"PATH": "", "VIRTUAL_ENV": "/elsewhere", "PYTHONDONTWRITEBYTECODE": "1"})
        env = tree_run.outside_env({"PATH": ours, "VIRTUAL_ENV": sys.prefix, "UV_NO_CONFIG": "1"})
        self.assertEqual(env, {"PATH": ours, "VIRTUAL_ENV": sys.prefix, "PYTHONDONTWRITEBYTECODE": "1"})

    def test_does_not_touch_given_mapping(self):
        src = {"UV_RUN_RECURSION_DEPTH": "1", "PATH": ""}
        tree_run.outside_env(src)
        self.assertEqual(src, {"UV_RUN_RECURSION_DEPTH": "1", "PATH": ""})

    def test_user_record_restores_home_and_xdg(self):
        """起動の殻の控え（userenv.RECORD）は外し、値の在る名は戻し null の名は外す。uv run の中でも外でも同じ"""
        record = json.dumps({"HOME": "/u", "XDG_CONFIG_HOME": None})
        for uv in ({}, {"UV_RUN_RECURSION_DEPTH": "1"}):
            with self.subTest(uv=uv), tempfile.TemporaryDirectory() as top:
                env = tree_run.outside_env({"HOME": "/run/home", "XDG_CONFIG_HOME": "/run/xdg", "CLAUDE_CONFIG_DIR": "/run/c",
                                            userenv.RECORD: record, userenv.RAN_DIR_ENV: top, **uv})
                self.assertEqual({k: env[k] for k in env if k != "PATH"},
                                 {"HOME": "/u", "CLAUDE_CONFIG_DIR": "/run/c", "PYTHONDONTWRITEBYTECODE": "1",
                                  userenv.MARK: str(pathlib.Path(top) / userenv.RAN_FILE)})
                self.assertFalse(userenv.ran(top))

    def test_user_env_marker_only_after_the_child_started(self):
        """#504: 戻した env の印（userenv.MARK）は子に渡さず、子が起きた時だけ残す。起こせなかったコマンドは印を残さず、前に起きた
        コマンドの印は消さない"""
        record = json.dumps({"HOME": "/u"})
        with tempfile.TemporaryDirectory() as top:
            env = tree_run.outside_env(hermetic.child_env(**{userenv.RECORD: record, userenv.RAN_DIR_ENV: top}))
            with self.assertRaises(OSError):
                tree_run.run([os.path.join(top, "no-such-tool")], env=env)
            self.assertFalse(userenv.ran(top))
            seen = pathlib.Path(top) / "seen"
            rc = tree_run.run([sys.executable, "-c", f"import os; open({str(seen)!r}, 'w').write(os.environ.get({userenv.MARK!r}, ''))"],
                              env=env)
            self.assertEqual((rc, seen.read_text()), (0, ""))
            self.assertTrue(userenv.ran(top))
            with self.assertRaises(OSError):
                tree_run.run([os.path.join(top, "no-such-tool")], env=env)
            self.assertTrue(userenv.ran(top))

    def test_user_env_marker_is_dropped_whatever_the_launch_error(self):
        """#538: 起こせなかったのが OSError でなくても（引数の中の NUL による ValueError）、この呼び出しが置いた印を残さない"""
        record = json.dumps({"HOME": "/u"})
        with tempfile.TemporaryDirectory() as top:
            env = tree_run.outside_env(hermetic.child_env(**{userenv.RECORD: record, userenv.RAN_DIR_ENV: top}))
            with self.assertRaises(ValueError):
                tree_run.run([sys.executable, "-c", "pass\0"], env=env)
            self.assertFalse(userenv.ran(top))

    def test_user_env_marker_that_cannot_be_written_starts_nothing(self):
        """#514: 印を置けなければ、利用者の HOME・XDG でコマンドを起こさず、MARK_FAILED を名指した OSError（起こせなかった）にする。
        起こしてから置けないと、利用者の環境で走らせたのを報告の冒頭が言い漏らす"""
        record = json.dumps({"HOME": "/u"})
        with tempfile.TemporaryDirectory() as top:
            env = tree_run.outside_env(hermetic.child_env(**{userenv.RECORD: record, userenv.RAN_DIR_ENV: top}))
            missing = pathlib.Path(top) / "missing" / userenv.RAN_FILE
            env[userenv.MARK] = str(missing)
            seen = pathlib.Path(top) / "seen"
            with self.assertRaises(OSError) as raised:
                tree_run.run([sys.executable, "-c", f"open({str(seen)!r}, 'w')"], env=env)
            self.assertIn(tree_run.MARK_FAILED, str(raised.exception))
            self.assertFalse(seen.exists())
            self.assertFalse(missing.exists())

    def test_inherited_user_env_marker_is_not_written_without_record(self):
        """#514: 起こした殻から継いだ userenv.MARK は、道を付けていない（RECORD の無い）run では外れ、印を書かない"""
        with tempfile.TemporaryDirectory() as top:
            mark = pathlib.Path(top) / userenv.RAN_FILE
            env = tree_run.outside_env(hermetic.child_env(**{userenv.MARK: str(mark)}))
            self.assertNotIn(userenv.MARK, env)
            self.assertEqual(tree_run.run([sys.executable, "-c", "pass"], env=env), 0)
            self.assertFalse(mark.exists())

    def test_without_user_record_home_stays(self):
        self.assertEqual(tree_run.outside_env({"HOME": "/run/home"}), {"HOME": "/run/home", "PYTHONDONTWRITEBYTECODE": "1"})

    def test_malformed_user_record_is_refused(self):
        for raw in ("not json", "[]", json.dumps({"HOME": 1})):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                tree_run.outside_env({userenv.RECORD: raw})


class LaunchProofShapeCase(unittest.TestCase):
    """起こす前の証明（tree_run.prove_launchable）が、bash では走るコマンドを見つからないと読まないこと"""

    def test_runnable_shapes_pass_the_proof(self):
        for cmd in ("true; echo done", "true|cat", "true&&true", "# note\ntrue", "FOO=1 true", "2>/dev/null true",
                    "2>&1 true", "10<&0 true", ">/dev/null true", "time true"):
            with self.subTest(cmd=cmd):
                self.assertEqual(subprocess.run(["bash", "-c", cmd], stdout=subprocess.DEVNULL, env=hermetic.child_env()).returncode, 0)
                tree_run.prove_launchable(["bash", "-c", cmd])

    def test_slow_proof_is_waited_out_without_deadline(self):
        # 証明が何回 POLL を数えても、時計が何時間進んでも、期限で捨てて起こさず、command -v の答えを待つ（E12）。
        # 回数・monotonic・壁時計のどの形の上限でも、BASH_ENV が放されるより前に捨てて戻り、この試験は赤になる
        polls = 1000
        with tempfile.TemporaryDirectory() as tmp:
            release = pathlib.Path(tmp) / "release"
            slow = pathlib.Path(tmp) / "slow-env.sh"
            slow.write_text(f"while [ ! -e {shlex.quote(str(release))} ]; do sleep 0.01; done\n")
            env = hermetic.child_env(BASH_ENV=str(slow))
            calls = itertools.count(1)

            def halted():
                if next(calls) == polls:
                    release.touch()
                return False

            clock = itertools.count(0, 3600)

            def leap():
                return float(next(clock))

            with mock.patch.object(tree_run, "POLL", 0.001), mock.patch.object(tree_run.time, "monotonic", leap), \
                    mock.patch.object(tree_run.time, "time", leap), self.assertRaises(FileNotFoundError):
                tree_run.prove_launchable(["bash", "-c", "no-such-command-xyz"], env=env, halted=halted)
            self.assertGreaterEqual(next(calls) - 1, polls)
        self.assertFalse(hasattr(tree_run, "PROOF_TIMEOUT"))


class CommandArgvCase(unittest.TestCase):
    def test_simple_words_are_direct(self):
        for cmd, argv in (("pytest", ["pytest"]), ("pytest -q tests", ["pytest", "-q", "tests"]),
                          ("  python3 -m pytest --x=1 ", ["python3", "-m", "pytest", "--x=1"]),
                          ("uv run pytest -k a-b", ["uv", "run", "pytest", "-k", "a-b"])):
            with self.subTest(cmd=cmd):
                self.assertEqual(tree_run.command_argv(cmd), (argv, "direct"))

    def test_shell_forms_go_through_bash(self):
        for cmd in ("a && b", "a || b", "a | b", "a; b", "a &", "a > log", "2>&1 a", "a < in", "(a)", "a $HOME", "a `b`",
                    "a *.py", "a ?", "a [x]", "a {1,2}", "~/bin/a", "a 'q r'", 'a "q"', "a\\ b", "a#b", "a # note",
                    "a\nb", "a\rb", "! a", "a ^ b", "FOO=1 a", "cd x", ". env", "source env", "command -v a", "exec a",
                    "export A=1", "if true", "for x", "while true", "time a", "echo x", "test -f x", "[ -f x ]",
                    "'unterminated", ""):
            with self.subTest(cmd=cmd):
                self.assertEqual(tree_run.command_argv(cmd), (["bash", "-c", cmd], "shell"))

    def test_direct_argv_means_what_bash_means(self):
        for cmd in ("printf-x a b", "x -q  --y=z", "a:b c,d e@f g+h %i"):
            argv, how = tree_run.command_argv(cmd)
            self.assertEqual(how, "direct")
            words = subprocess.run(["bash", "-c", f'set -- {cmd}; printf "%s\\n" "$@"'],
                                   capture_output=True, text=True, encoding="utf-8", env=hermetic.child_env()).stdout.splitlines()
            self.assertEqual(argv, words)

    def test_launch_kind_reads_126_127_as_red(self):
        self.assertEqual([tree_run.launch_kind(c) for c in (None, 0, 1, 126, 127)],
                         ["broken", "clean", "red", "red", "red"])


class ReuseRunCase(unittest.TestCase):
    """reuse_run の結果の使い回しの要（元 test_tree_run.py の SlotReuseCase の test_broken_entry_runs_child_and_says_why・
    test_writeback_failure_restores_log・test_red_or_tree_changing_run_is_not_kept）。本物の git と本物の子のプロセスで試す"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        (self.repo / "a.txt").write_text("1\n", encoding="utf-8")
        gitkit.git(self.repo, "init", "-q")
        gitkit.git(self.repo, "add", "-A")
        gitkit.git(self.repo, "commit", "-q", "-m", "seed")
        self.count = self.tmp / "count"
        self.report = self.tmp / "report.xml"
        self.place = tree_run.reuse_place(self.tmp / "art", "run-a", rerun=False)
        self.n = 0

    def launch(self, argv=None, outputs=None):
        """reuse_run を 1 回呼ぶ ——（終了コード, 出力, note）。argv の既定は count に 1 行足して out を書き、報告を書く sh"""
        argv = argv or ["sh", "-c", f'echo 1 >> {self.count}; echo out; [ -d {self.report} ] || echo "<r/>" > {self.report}']
        note = {}
        self.n += 1
        log = self.tmp / f"log-{self.n}"
        with open(log, "wb") as f:
            rc = tree_run.reuse_run(argv, {"PATH": os.environ["PATH"]}, place=self.place,
                                    outputs=(self.report,) if outputs is None else outputs, note=note,
                                    stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, cwd=str(self.repo))
        return rc, log.read_bytes(), note

    def launched(self):
        return len(self.count.read_text(encoding="utf-8").split()) if self.count.exists() else 0

    def test_broken_entry_runs_child_and_says_why(self):
        self.launch()
        _, _, note = self.launch()
        self.assertEqual(self.launched(), 1)
        pathlib.Path(note["reused"]["entry"]).write_text("{", encoding="utf-8")
        rc, log, note = self.launch()
        self.assertEqual((rc, self.launched(), log), (0, 2, b"out\n"))
        self.assertNotIn("reused", note)
        self.assertIn("控えが読めない", note["reuse_off"])

    def test_writeback_failure_restores_log(self):
        """書き戻しは全部か無し: 書き戻せなければ書いた分を戻して子を起こし、ログに控えの出力を残さない"""
        self.launch()
        self.report.unlink()
        self.report.mkdir()   # 書き戻し先がディレクトリ: IsADirectoryError
        rc, log, note = self.launch()
        self.assertEqual((rc, self.launched(), log), (0, 2, b"out\n"))
        self.assertNotIn("reused", note)
        self.assertIn("書き戻しに失敗した", note["reuse_off"])

    def test_report_written_right_after_launch_is_kept(self):
        """起こした時刻はファイルの時刻の時計で取る: time.time() がファイルの時刻より進んでいても（Linux の粗いファイルの時刻）、
        起こした後に書いた報告を控え、書き戻す"""
        real = time.time
        with mock.patch.object(time, "time", lambda: real() + 5):
            self.launch()
            self.report.unlink()
            _, _, note = self.launch()
        self.assertEqual((self.launched(), self.report.read_text(encoding="utf-8")), (1, "<r/>\n"))
        self.assertIn("reused", note)

    def test_red_or_tree_changing_run_is_not_kept(self):
        red = ["sh", "-c", f"echo 1 >> {self.count}; exit 1"]
        self.assertEqual(self.launch(red, ())[0], 1)
        rc, _, note = self.launch(red, ())
        self.assertEqual((rc, self.launched()), (1, 2))
        self.assertIn("緑の回だけ控える", note["reuse_off"])
        make = ["sh", "-c", f"echo 1 >> {self.count}; echo x > made.txt"]
        _, _, note = self.launch(make, ())
        self.assertIn("作業ツリーが変わった", note["reuse_off"])
        (self.repo / "made.txt").unlink()
        self.launch(make, ())
        self.assertEqual(self.launched(), 4)   # 置かれていれば 2 度目は控えから使われ、子が起きない

    def test_no_place_always_launches(self):
        """置き場の無い呼び（reuse_place が None。top か run が空）は控えを読まず書かず、note に何も置かない"""
        self.assertIsNone(tree_run.reuse_place("", "run-a", rerun=False))
        self.assertIsNone(tree_run.reuse_place(self.tmp, "", rerun=False))
        self.place = None
        notes = [self.launch()[2] for _ in range(2)]
        self.assertEqual((self.launched(), notes), (2, [{}, {}]))


if __name__ == "__main__":
    unittest.main()
