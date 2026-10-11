"""人の打つ口（bin/_lib/cli.py）の試験。Archon は偽の関数で、ASF は偽の fetch で取る（網に出ない）。"""
import json
import pathlib
import tempfile
import unittest

from bin._lib import cli

ROOT = pathlib.Path(__file__).resolve().parents[2]


class FakeArchon:
    """呼ばれた引数を記録し、決めた標準出力を返す"""

    def __init__(self, stdout="", on_call=None):
        self.calls = []
        self.stdout = stdout
        self.on_call = on_call

    def __call__(self, argv):
        self.calls.append(argv)
        if self.on_call:
            self.on_call(argv)
        return self.stdout


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.home = self.tmp / "archon-home"
        self.target = self.tmp / "target"
        self.target.mkdir()

    def fetch(self, repo, commit, folder, dest):
        dest.mkdir(parents=True)
        (dest / "archon-x.yaml").write_text("name: archon-x\n", encoding="utf-8")

    def start(self, archon, request="直して"):
        return cli.start(self.target, request, archon, archon_home=self.home, cache=self.tmp / "cache", fetch=self.fetch)

    def test_start_places_then_runs(self):
        placed_when_run = []

        def on_call(argv):
            placed_when_run.append(
                ((self.home / "workflows/works-factory").is_dir(), (self.home / "workflows/asf/archon-x.yaml").is_file())
            )

        archon = FakeArchon(json.dumps({"ok": True, "runId": "run-1"}), on_call)
        run_id = self.start(archon, "issue 3 を直して")

        self.assertEqual(run_id, "run-1")
        self.assertEqual(placed_when_run, [(True, True)])
        argv = archon.calls[0]
        self.assertEqual(argv[:3], ["workflow", "run", "works-factory-line"])
        self.assertEqual(argv[argv.index("--cwd") + 1], str(self.target))
        self.assertEqual(argv[-1], "issue 3 を直して")

    def test_start_places_ours_byte_identical(self):
        self.start(FakeArchon(json.dumps({"ok": True, "runId": "run-1"})))
        ours = ROOT / "workflows"
        placed = self.home / "workflows/works-factory"
        expected = {p.relative_to(ours).as_posix(): p.read_bytes() for p in ours.rglob("*") if p.is_file()}
        actual = {p.relative_to(placed).as_posix(): p.read_bytes() for p in placed.rglob("*") if p.is_file()}
        self.assertEqual(actual, expected)

    def test_start_refuses_ack_without_run_id(self):
        archon = FakeArchon(json.dumps({"ok": False, "error": "no such workflow"}))
        with self.assertRaisesRegex(RuntimeError, "no such workflow"):
            self.start(archon)

    def test_answer_approves_with_text(self):
        archon = FakeArchon(json.dumps({"ok": True, "runId": "run-1", "action": "approve"}))
        cli.answer("run-1", "進めて", archon)
        argv = archon.calls[0]
        self.assertEqual(argv[:3], ["workflow", "approve", "run-1"])
        self.assertEqual(argv[argv.index("--comment") + 1], "進めて")

    def test_answer_refuses_failed_ack(self):
        archon = FakeArchon(json.dumps({"ok": False, "error": "run is not paused"}))
        with self.assertRaisesRegex(RuntimeError, "run is not paused"):
            cli.answer("run-1", "進めて", archon)

    def test_show_prints_archon_state_as_is(self):
        archon = FakeArchon("Run run-1\nStatus: paused\n")
        self.assertEqual(cli.show("run-1", archon), "Run run-1\nStatus: paused\n")
        self.assertEqual(archon.calls, [["workflow", "get", "run-1", "--verbose"]])


if __name__ == "__main__":
    unittest.main()
