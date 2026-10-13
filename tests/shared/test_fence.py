"""読むだけの役の claude の包み（workflows/.shared/fence.py。埋め P5）を確かめる。

一覧の組み方・argv の書き換え・main は使い捨ての git の木と偽の claude で確かめる。RealClaudeTest は本物の claude を偽の API で起こし、
sandbox が包みの足した一覧への書き込みを本当に止めることを確かめる（本物の claude か sandbox が無い所では名前つきで見送る）。
"""
import http.server
import importlib.util
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import threading
import unittest
from unittest import mock

from bin._lib import isolate
from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.layers import scan
from tests.workflows import test_test_gate

ROOT = pathlib.Path(__file__).resolve().parents[2]
FENCE = ROOT / "workflows" / ".shared" / "fence.py"


def load_fence():
    # .shared は import の名にならないので、ファイルから読む。Archon が置き場をバイトで照らすので __pycache__ を作らない
    spec = importlib.util.spec_from_file_location("fence", FENCE)
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


fence = load_fence()


def make_tree(tmp: pathlib.Path) -> dict:
    """本体の repo・linked worktree・本体の下の worktree（worktree.path で置き場を替えた形）と、隔離した run の置き場"""
    main = tmp / "main"
    main.mkdir()
    git(main, "init", "-q")
    (main / "f").write_text("x\n", encoding="utf-8")
    git(main, "add", "f")
    git(main, "commit", "-q", "-m", "seed")
    linked = tmp / "linked"
    git(main, "worktree", "add", "-q", "-b", "a", str(linked))
    nested = main / ".worktrees" / "x"
    git(main, "worktree", "add", "-q", "-b", "b", str(nested))
    child = isolate.isolate({}, tmp / "run-home")
    return {"main": main, "linked": linked, "nested": nested, "child": child, "own": [str(tmp / "run-home" / "claude-fence")]}


def settings_with(deny: list) -> str:
    return json.dumps({"sandbox": {"enabled": True, "filesystem": {"allowWrite": ["/"], "denyWrite": deny}}})


class ProtectedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)

    def test_lists_every_tree_of_the_repository(self):
        t = make_tree(self.tmp)
        got = fence.protected(str(t["linked"]), t["child"]["ARCHON_HOME"], t["child"]["CLAUDE_CONFIG_DIR"], t["own"])
        self.assertEqual(got, [*sorted([str(t["linked"]), str(t["main"] / ".git"), str(t["main"]), str(t["nested"]),
                                        t["child"]["ARCHON_HOME"]]),
                               t["child"]["CLAUDE_CONFIG_DIR"], *t["own"]])

    def test_outside_git_lists_only_the_given_paths(self):
        cwd = self.tmp / "plain"
        cwd.mkdir()
        got = fence.protected(str(cwd), "/a", "/c", ["/o"])
        self.assertEqual(got, [*sorted([str(cwd), "/a"]), "/c", "/o"])

    def test_without_git_refuses(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.tmp)}):
            with self.assertRaises(fence.Refused):
                fence.protected(str(self.tmp), "/a", "/c", [])


class ProtectedPathsCopiedTest(unittest.TestCase):
    """写した protected_paths を縛る、今の works（raiki61/claude-plugins@2aa7c66cf7ab）の試験の写し: graphloops/tests/simulate.py の
    test_tooled_launch_fence の守る場所の 2 つの check と、graphloops/tests/py/test_role_run_stop.py の
    test_protected_paths_is_undecided_when_git_answers_partly（pytest の parametrize を subTest に直した）"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)

    def test_tooled_launch_fence(self):
        repo, other, board = self.tmp / "repo", self.tmp / "wt2", self.tmp / "board"
        board.mkdir()
        for args in (["init", "-q", str(repo)], ["-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                                                      "--allow-empty", "-m", "x"], ["-C", str(repo), "worktree", "add", "-q", str(other)]):
            subprocess.run(["git", *args], capture_output=True, check=True)
        real = os.path.realpath
        want_deny = sorted({real(repo), real(repo / ".git"), real(other), real(board)})
        self.assertEqual(fence.protected_paths(repo, board), want_deny,
                         "書き込みを止める場所は、自分を含む作業ツリーの根の全部・共有の .git・盤面の置き場")
        plain_dir = self.tmp / "plain"
        plain_dir.mkdir()
        self.assertEqual(fence.protected_paths(plain_dir, board), sorted({real(plain_dir), real(board)}),
                         "git の作業ツリーでない場所では cwd と盤面だけを守る")

    def test_protected_paths_is_undecided_when_git_answers_partly(self):
        """共有の .git か作業ツリーの一覧のどちらかが引けなければ、守る場所は決まらない（None——sandbox の形を選ばない）"""
        for name, worktrees in (("worktree-list-fails", (False, [], "失敗")), ("no-common-dir", (True, ["worktree /w"], ""))):
            with self.subTest(name):
                common = (True, [], "") if worktrees[0] else (True, [str(self.tmp / ".git")], "")
                with mock.patch.object(fence, "_git", lambda cwd, *args: common if "rev-parse" in args else worktrees):
                    self.assertIsNone(fence.protected_paths(self.tmp))


class FencedArgvTest(unittest.TestCase):
    HOME = "/h/home"
    ARCHON = "/h/archon-home"
    PATHS = ["/w", "/w/.git"]

    def fenced(self, argv):
        with mock.patch.dict(os.environ, {"HOME": self.HOME}):
            return fence.fenced_argv(argv, self.ARCHON, lambda: self.PATHS)

    def test_marked_settings_get_the_list_in_both_spellings(self):
        settings = settings_with(["/w", scan.NO_TREE_WRITE])
        for argv, at in ((["-p", "x", "--settings", settings, "--model", "m"], 3),
                         (["-p", "x", f"--settings={settings}", "--model", "m"], 2)):
            with self.subTest(argv=argv[at - 1:at + 1]):
                got = self.fenced(argv)
                self.assertEqual(len(got), len(argv))
                self.assertEqual(got[-2:], ["--model", "m"])
                value = got[at].removeprefix("--settings=")
                fs = json.loads(value)["sandbox"]["filesystem"]
                self.assertEqual(fs["denyWrite"], ["/w", scan.NO_TREE_WRITE, "/w/.git"])
                self.assertEqual(fs["allowWrite"], ["/"])

    def test_unmarked_launches_are_unchanged(self):
        writer = json.dumps({"sandbox": {"enabled": True, "allowUnsandboxedCommands": False}})
        for argv in (["-p", "x", "--settings", writer],
                     ["-p", "x", "--settings", settings_with(["~/../other"])],
                     ["--settings=" + settings_with(["/elsewhere"])],
                     ["--version"]):
            with self.subTest(argv=argv):
                self.assertIs(self.fenced(argv), argv)

    def test_undecidable_settings_are_refused(self):
        marked = settings_with([scan.NO_TREE_WRITE])
        for argv in (["--settings", marked, "--settings", marked], ["--settings", "{not json"], ["--settings"],
                     ["--settings", "/path/to/settings.json"], ["--settings=[]"]):
            with self.subTest(argv=argv):
                with self.assertRaises(fence.Refused):
                    self.fenced(argv)

    def test_mark_is_the_yaml_value_under_the_isolated_home(self):
        """YAML が読むだけの役に書く値（scan.NO_TREE_WRITE）は、起動が隔離した HOME の下で印になる"""
        child = isolate.isolate({}, hermetic.tmpdir(self))
        with mock.patch.dict(os.environ, {"HOME": child["HOME"]}):
            self.assertTrue(fence.marks(scan.NO_TREE_WRITE, child["ARCHON_HOME"]))
            self.assertFalse(fence.marks("~/../other", child["ARCHON_HOME"]))


FAKE_REAL = f"""#!{sys.executable}
import json, os, sys
with open(os.environ["FAKE_REAL_LOG"], "w", encoding="utf-8") as f:
    json.dump(sys.argv[1:], f)
"""


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.tree = make_tree(self.tmp)
        self.real = self.tmp / "real-claude"
        self.real.write_text(FAKE_REAL, encoding="utf-8")
        self.real.chmod(0o755)
        self.log = self.tmp / "argv.json"

    def run_fence(self, *argv, path=None):
        child = self.tree["child"]
        env = hermetic.child_env(HOME=child["HOME"], FAKE_REAL_LOG=str(self.log), **({"PATH": path} if path else {}))
        return subprocess.run([sys.executable, str(FENCE), "--real", str(self.real), "--archon-home", child["ARCHON_HOME"],
                               "--claude-config", child["CLAUDE_CONFIG_DIR"], "--own", self.tree["own"][0], "--", *argv],
                              cwd=self.tree["linked"], env=env, capture_output=True, text=True, encoding="utf-8",
                              timeout=60)

    def test_marked_launch_reaches_claude_with_the_list(self):
        done = self.run_fence("-p", "x", "--settings", settings_with([scan.NO_TREE_WRITE]))
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(self.log.read_text(encoding="utf-8"))
        deny = json.loads(got[3])["sandbox"]["filesystem"]["denyWrite"]
        self.assertIn(str(self.tree["main"] / ".git"), deny)
        self.assertIn(str(self.tree["nested"]), deny)

    def test_unmarked_launch_reaches_claude_unchanged(self):
        argv = ["-p", "x", "--settings", json.dumps({"sandbox": {"enabled": True}})]
        done = self.run_fence(*argv)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(self.log.read_text(encoding="utf-8")), argv)

    def test_without_git_stops_before_claude(self):
        done = self.run_fence("--settings", settings_with([scan.NO_TREE_WRITE]), path=str(self.tmp / "no-tools"))
        self.assertEqual(done.returncode, fence.REFUSED_EXIT, done.stderr)
        self.assertTrue(done.stderr.startswith("works-factory fence: "), done.stderr)
        self.assertFalse(self.log.exists(), "止まるはずが claude が起きた")


def sandbox_available() -> bool:
    if sys.platform == "darwin":
        return shutil.which("sandbox-exec") is not None
    if shutil.which("bwrap") is None or shutil.which("socat") is None:
        return False
    try:
        probe = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--unshare-user", "--unshare-net", "true"],
                               capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def fake_api(command: str, results: list):
    """1 回目の stream の要求に Bash の tool_use を 1 つ返し、受けた tool_result を results に足して終える偽の Anthropic API"""
    asked = threading.Event()

    def sse(w, event, data):
        w.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode())

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
            if not self.path.startswith("/v1/messages") or "count_tokens" in self.path:
                return self.reply_json({"input_tokens": 1})
            last = (body.get("messages") or [{}])[-1].get("content")
            got = [c for c in last if isinstance(c, dict) and c.get("type") == "tool_result"] if isinstance(last, list) else []
            tools = [t.get("name") for t in body.get("tools", [])]
            if got:
                results.extend(got)
                blocks, stop = [{"type": "text", "text": "done"}], "end_turn"
            elif "Bash" in tools and body.get("stream") and not asked.is_set():
                asked.set()
                blocks = [{"type": "tool_use", "id": "toolu_01", "name": "Bash",
                           "input": {"command": command, "description": "probe"}}]
                stop = "tool_use"
            else:
                blocks, stop = [{"type": "text", "text": "ok"}], "end_turn"
            message = {"id": "msg_x", "type": "message", "role": "assistant", "model": body.get("model"),
                       "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}
            if not body.get("stream"):
                return self.reply_json({**message, "content": blocks, "stop_reason": stop})
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("connection", "close")
            self.end_headers()
            w = self.wfile
            sse(w, "message_start", {"type": "message_start", "message": {**message, "content": [], "stop_reason": None}})
            for i, block in enumerate(blocks):
                if block["type"] == "text":
                    sse(w, "content_block_start", {"type": "content_block_start", "index": i,
                                                   "content_block": {"type": "text", "text": ""}})
                    delta = {"type": "text_delta", "text": block["text"]}
                else:
                    sse(w, "content_block_start", {"type": "content_block_start", "index": i,
                                                   "content_block": {**block, "input": {}}})
                    delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
                sse(w, "content_block_delta", {"type": "content_block_delta", "index": i, "delta": delta})
                sse(w, "content_block_stop", {"type": "content_block_stop", "index": i})
            sse(w, "message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                     "usage": {"output_tokens": 1}})
            sse(w, "message_stop", {"type": "message_stop"})
            w.flush()
            self.close_connection = True

        def reply_json(self, data):
            raw = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.send_response(404)
            self.send_header("content-length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)


class RealClaudeTest(unittest.TestCase):
    """本物の claude の sandbox が、包みの足した一覧への Bash の書き込みを止める（#305 の見直しの R2）"""

    @classmethod
    def setUpClass(cls):
        cls.claude = shutil.which("claude")
        if cls.claude is None:
            raise unittest.SkipTest("本物の claude が無い")
        if not sandbox_available():
            raise unittest.SkipTest("sandbox が立たない（macOS の sandbox-exec か、Linux の bwrap と socat が要る）")

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.tree = make_tree(self.tmp)
        self.outside = self.tmp / "outside"
        self.outside.mkdir()
        child = self.tree["child"]
        main = self.tree["main"]
        self.blocked = {
            "作業ツリー（cwd）": self.tree["linked"],
            "共通の .git": main / ".git",
            "共通の .git の worktrees": main / ".git" / "worktrees" / self.tree["linked"].name,
            "本体の作業ツリー": main,
            "置き場を替えた worktree": self.tree["nested"],
            "Archon の家": pathlib.Path(child["ARCHON_HOME"]),
            "Claude の設定": pathlib.Path(child["CLAUDE_CONFIG_DIR"]),
        }
        self.settings = json.dumps({"sandbox": test_test_gate.node("ci")["sandbox"]})

    def probe(self, launcher: list[str]) -> dict[str, str]:
        """launcher で claude を起こし、Bash で各置き場に書かせた結果（置き場 → WROTE か BLOCKED）"""
        places = [*self.blocked.values(), self.outside]
        command = "; ".join(f"if (echo x > {shlex.quote(str(p / 'fence-probe'))}) 2>/dev/null; then echo WROTE {i}; "
                            f"else echo BLOCKED {i}; fi" for i, p in enumerate(places))
        results = []
        server = fake_api(command, results)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        child = self.tree["child"]
        env = hermetic.child_env(HOME=child["HOME"], CLAUDE_CONFIG_DIR=child["CLAUDE_CONFIG_DIR"], NO_PROXY="*",
                                 ANTHROPIC_API_KEY="dummy",
                                 ANTHROPIC_BASE_URL=f"http://127.0.0.1:{server.server_address[1]}")
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
            env.pop(name, None)
        argv = ["-p", "hi", "--model", "claude-haiku-4-5-20251001", "--settings", self.settings,
                "--allowedTools", "Bash", "--permission-mode", "dontAsk"]
        done = subprocess.run([*launcher, *argv], cwd=self.tree["linked"], env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, encoding="utf-8", timeout=180)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        text = "".join(r["content"] if isinstance(r["content"], str) else "".join(c.get("text", "") for c in r["content"])
                       for r in results)
        said = {}
        for line in text.splitlines():
            verdict, _, index = line.partition(" ")
            if verdict in ("WROTE", "BLOCKED"):
                said[index] = verdict
        self.assertEqual(len(said), len(places), text)
        return {str(p): said[str(i)] for i, p in enumerate(places)}

    def test_fenced_role_cannot_write_the_listed_places(self):
        child = self.tree["child"]
        got = self.probe([sys.executable, str(FENCE), "--real", self.claude, "--archon-home", child["ARCHON_HOME"],
                          "--claude-config", child["CLAUDE_CONFIG_DIR"], *(a for o in self.tree["own"] for a in ("--own", o)),
                          "--"])
        for what, place in self.blocked.items():
            with self.subTest(what=what):
                self.assertEqual(got[str(place)], "BLOCKED")
        self.assertEqual(got[str(self.outside)], "WROTE", "柵の外まで書けない（試験の道具が書き込みを試していない）")

    def test_without_the_fence_the_main_tree_is_writable(self):
        got = self.probe([self.claude])
        self.assertEqual(got[str(self.tree["main"])], "WROTE")


if __name__ == "__main__":
    unittest.main()
