"""素の Windows で入口が部品を読む前に 1 行で止まること（bin/_lib/nativewin.py）と、止める前に読み込みで落ちないことの試験。

素の Windows の機械は無いので、子の Python で sys.platform を win32 などに差し替えて入口を runpy で走らせる。
読み込みで落ちないことは、子の signal から素の Windows に無い SIGHUP を外して、殻の部品を読ませて確かめる。
"""
import json
import pathlib
import subprocess
import sys
import unittest

from tests.bin import hermetic

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENTRIES = {"works-factory": ("workflow", "status"), "apply": ("some-run",)}

# 入口を走らせ、終わった時に読み込んだ bin._lib の部品の名を標準出力へ JSON で出す
RUN_ENTRY = """
import json, runpy, sys
sys.platform = {platform!r}
try:
    runpy.run_path({entry!r}, run_name="__main__")
finally:
    print(json.dumps(sorted(m for m in sys.modules if m.startswith("bin._lib."))))
"""

# 素の Windows の signal に無い SIGHUP を外してから、殻の部品を読む
LOAD_WITHOUT_SIGHUP = """
import signal, sys
del signal.SIGHUP
sys.path.insert(0, {root!r})
sys.path.append({lib!r})
from bin._lib import launcher, apply, recordroot  # noqa: F401
import tree_run
print(sorted(signal.Signals(s).name for s in tree_run.STOP_SIGNALS))
"""


class NativeWindowsStopTest(unittest.TestCase):
    def run_entry(self, name, platform):
        tmp = hermetic.tmpdir(self)
        code = RUN_ENTRY.format(platform=platform, entry=str(ROOT / "bin" / name))
        # 止まらなかった時に殻が利用者の家を読まないよう、HOME も一時の置き場へ向ける
        return subprocess.run([sys.executable, "-c", code, *ENTRIES[name]], env=hermetic.child_env(HOME=str(tmp)), cwd=tmp,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)

    def test_entries_stop_with_one_line_before_loading_parts(self):
        for name in ENTRIES:
            for platform in ("win32", "cygwin", "msys"):
                with self.subTest(entry=name, platform=platform):
                    done = self.run_entry(name, platform)
                    self.assertNotEqual(done.returncode, 0, done.stderr)
                    lines = done.stderr.strip().splitlines()
                    self.assertEqual(len(lines), 1, done.stderr)
                    self.assertTrue(lines[0].startswith(f"{name}: 素の Windows では動かない"), done.stderr)
                    self.assertIn("WSL2", lines[0])
                    loaded = json.loads(done.stdout.strip().splitlines()[-1])
                    self.assertEqual(loaded, ["bin._lib.nativewin"], loaded)

    def test_posix_and_wsl_pass_through(self):
        """WSL2 の中は linux を名乗る。止めずに返る（入口を走らせると殻が利用者の設定を読みに行くので、部品を直に呼ぶ）"""
        from unittest import mock
        from bin._lib import nativewin
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform), mock.patch.object(sys, "platform", platform):
                self.assertIsNone(nativewin.stop("works-factory"))


class LoadWithoutSighupTest(unittest.TestCase):
    def test_parts_load_without_sighup(self):
        code = LOAD_WITHOUT_SIGHUP.format(root=str(ROOT), lib=str(ROOT / "lib"))
        done = subprocess.run([sys.executable, "-c", code], env=hermetic.child_env(), cwd=hermetic.tmpdir(self),
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "['SIGINT', 'SIGTERM']")


if __name__ == "__main__":
    unittest.main()
