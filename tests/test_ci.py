"""ASF の試験の段（harness/ci.py）の上限の試験。

全部の試験を 1 つの過程で回すと 600 秒を超えるので（#168）、unit の段には上限を置かず、static の段だけが 600 秒で切る。
"""
import contextlib
import importlib.util
import io
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_ci():
    spec = importlib.util.spec_from_file_location("ci_gate", ROOT / "harness" / "ci.py")
    ci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ci)
    return ci


class TimeoutTest(unittest.TestCase):
    def test_unit_stage_has_no_timeout_and_static_keeps_its_cap(self):
        ci = load_ci()
        timeouts = []

        def fake_run(argv, **kwargs):
            timeouts.append(kwargs["timeout"])
            return subprocess.CompletedProcess(argv, 0, "Ran 3 tests\n", "")

        config = {"static": "s", "unit": "u", "unit_count_pattern": r"Ran (\d+) tests?"}
        with mock.patch.object(ci, "CONFIG", config), mock.patch.object(sys, "argv", ["ci.py", "--quick"]), \
                mock.patch.object(ci.subprocess, "run", fake_run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ci.main(), 0)
        self.assertEqual(timeouts, [600, None])


if __name__ == "__main__":
    unittest.main()
