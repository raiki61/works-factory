"""test_cmd が対象の手元を試す形の見分け（workflows/line/src/testcmd_check.py。元 lib/testcmd_check.py とその試験 lib/tests/test_testcmd_check.py の写し。docs/design/line.md の 1.5 の MOVE）の検査。

run の作業ツリーと単位の作業ツリーは commit から切るので、対象の git が無視する物（.venv・node_modules など）は無い。test_cmd が
対象の手元を絶対パスで指すか、対象を editable で入れた対象の外の環境を使えば、作業ツリーの直しでなく手元のコードを試す（止める形）。
相対の語が作業ツリーに無い物（git が無視する物）を指す形は走らずに落ちるので、止めずに注意にする。
種の git は gitkit の型の写し。子のプロセスは git check-ignore と git worktree だけ。
"""
import json
import os
import pathlib
import tempfile
import unittest

from tests.bin import gitkit, hermetic
from tests.blocks import kit

testcmd_check = kit.load("line", "testcmd_check")

SEED = pathlib.Path(__file__).resolve().parents[3] / "tests" / "e2e" / "target-seed"


class TestCmdCheck(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.repo = pathlib.Path(self._td.name).resolve() / "repo"
        gitkit.committed_copy(self.repo, SEED)
        with open(self.repo / ".gitignore", "a", encoding="utf-8") as f:
            f.write(".venv\nnode_modules/\nbuild/\n")
        py = self.repo / ".venv" / "bin" / "python"
        py.parent.mkdir(parents=True)
        py.write_text("#!/bin/sh\n")
        (py.parent / "pytest").write_text("#!/bin/sh\n")
        (self.repo / "node_modules" / ".bin").mkdir(parents=True)
        (self.repo / "node_modules" / ".bin" / "jest").write_text("#!/bin/sh\n")

    def findings(self, cmd, **env_kw):
        """(止める形の文の並び, 注意の文の並び)。環境は試験の場の物（VIRTUAL_ENV は外す）に env_kw を重ねた物"""
        env = {k: v for k, v in hermetic.child_env().items() if k != "VIRTUAL_ENV"}
        env.update(env_kw)
        return testcmd_check.findings(self.repo, cmd, env)

    def check(self, cmd, **env_kw):
        return self.findings(cmd, **env_kw)[0]

    def notices(self, cmd, **env_kw):
        return self.findings(cmd, **env_kw)[1]

    def stops(self, cmd, **env_kw):
        lines = self.check(cmd, **env_kw)
        self.assertTrue(lines, cmd)
        return lines

    def after_cd(self, cmd, **env_kw):
        """cd <対象の根> && cmd の止める形の文のうち、cd の先（対象の根そのもの）を名指す文の外。根から読む相対の語を、手元を絶対
        パスで指す語として読む形"""
        root = f"test_cmd の {self.repo} は"
        lines = self.check(f"cd {self.repo} && {cmd}", **env_kw)
        self.assertTrue(any(ln.startswith(root) for ln in lines), lines)
        return [ln for ln in lines if not ln.startswith(root)]

    def test_relative_ignored_path_is_a_notice(self):
        """根から読む相対の語が git の無視する物を指す形は、作業ツリーで走らずに落ちるので、止めずに注意にする。絶対パスの cd の後
        なら同じ語が手元を指すので止める"""
        for cmd, path in ((".venv/bin/python -m pytest -q", ".venv/bin/python"),
                          ("./node_modules/.bin/jest --ci", "./node_modules/.bin/jest"),
                          ("PYTHONPATH=src .venv/bin/python -m pytest", ".venv/bin/python"),
                          (".venv/bin/python -m pytest && echo done", ".venv/bin/python")):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd), [])
                notices = self.notices(cmd)
                self.assertEqual(len(notices), 1, notices)
                self.assertTrue(notices[0].startswith(f"test_cmd の {path} は対象の git が無視するパス"), notices)
                self.assertIn("worktree に無い", notices[0])
                lines = self.after_cd(cmd)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn(f"{path}（cd の後の {self.repo}/", lines[0])
                self.assertIn("対象の手元", lines[0])
                self.assertEqual(self.findings(f"cd {self.repo} && {cmd}")[1], [])

    def test_path_through_symlink_and_outside_word_do_not_hide_others(self):
        """リンクの先のパス（git check-ignore が 128 で落ちる形）と根の外のパスが、同じ行のほかの知らせを消さない"""
        outside = self.repo.parent / "outside-venv"
        (outside / "bin").mkdir(parents=True)
        (outside / "bin" / "python").write_text("#!/bin/sh\n")
        (self.repo / ".venv").rename(self.repo.parent / "moved")
        (self.repo / ".venv").symlink_to(outside)
        other = self.repo.parent / "other" / ".venv"
        other.mkdir(parents=True)
        (other / "x").write_text("")
        lines = self.after_cd("./node_modules/.bin/jest ../other/.venv/x .venv/bin/python")
        self.assertEqual(len(lines), 2, lines)
        self.assertIn("./node_modules/.bin/jest", lines[0])
        self.assertIn(".venv/bin/python", lines[1])

    def test_path_in_submodule_does_not_hide_others(self):
        """サブモジュールの中のパス（git check-ignore が 128 で落ちる形）が、同じ行のほかの知らせを消さない"""
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "y").write_text("")
        gitkit.git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},sub")
        lines = self.after_cd("./node_modules/.bin/jest sub/y")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("./node_modules/.bin/jest", lines[0])

    def test_absolute_path_into_target_ignored_dir_stops(self):
        """対象の .venv を絶対パスで指す形は、worktree の直しでなく手元を試し得る（黙った偽の緑）ので止める"""
        link = self.repo.parent / "link"
        link.symlink_to(self.repo)
        for root in (self.repo, link):
            with self.subTest(root=str(root)):
                cmd = f"{root}/.venv/bin/python -m pytest -q"
                lines = self.stops(cmd)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn(f"{root}/.venv/bin/python", lines[0])
                self.assertIn("対象の手元", lines[0])

    def test_quiet_for_tracked_missing_outside_made_or_option_paths(self):
        for cmd in ("python3 -m pytest -q test_stats.py",   # 追跡するファイルは worktree にも在る
                    "make && build/run-tests",              # 無視するが対象に無い（コマンドが作る）
                    "/usr/bin/env python3 -m pytest",       # 対象の外
                    "uv sync && .venv/bin/pytest -q",       # 先の段が worktree の中で作る
                    "npm ci; node_modules/.bin/jest",       # 同じ
                    "pytest --junitxml=node_modules/.bin/jest",  # 旗の値（書き先が多い）は見ない
                    "pytest -q 'unclosed"):                 # 割れない行は空白で割る
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd), [])
                self.assertEqual(self.after_cd(cmd), [])

    def test_cd_first_resolves_the_next_segment_from_the_cd_target(self):
        """前の段が cd だけなら、次の段の語を cd の先から読む（cd /手元 && cd sub && .venv/bin/pytest は /手元/sub/.venv/bin/pytest を
        走らせる）。cd の先そのものも無視するパスなら名指す（/ が無くてもパス）。cd の先が読めない（$・~・-）なら後ろの段は見ない。
        根から読む相対の cd だけなら止めない（作業ツリーの中を読む）"""
        venv = self.repo / "sub" / ".venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "pytest").write_text("#!/bin/sh\n")
        for cmd in ("cd sub && .venv/bin/pytest -q", "cd sub; .venv/bin/pytest -q", "cd ./sub && cd . && .venv/bin/pytest"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd), [])
                notices = self.notices(cmd)
                self.assertEqual(len(notices), 1, notices)
                self.assertIn("（cd の後の sub/.venv/bin/pytest）", notices[0])
                lines = self.after_cd(cmd)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn(f"（cd の後の {self.repo}/sub/.venv/bin/pytest）", lines[0])
        (self.repo / "build").mkdir()
        lines = self.after_cd("cd build && ./run-tests")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("test_cmd の build（", lines[0])
        for cmd in ("cd sub && uv sync && .venv/bin/pytest", 'cd "$X" && .venv/bin/pytest', "cd ~ && .venv/bin/pytest",
                    "cd - && .venv/bin/pytest", "cd node_modules/.. && test_stats.py"):
            with self.subTest(cmd):
                self.assertEqual(self.after_cd(cmd), [])

    def test_absolute_cd_into_target_names_the_local_environment(self):
        """絶対パスで対象の根の中へ cd した後の相対の語は、対象の手元を指す（作業ツリーに無いのでなく、手元の環境を使う）"""
        venv = self.repo / "sub" / ".venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "pytest").write_text("#!/bin/sh\n")
        for cmd in (f"cd {self.repo}/sub && .venv/bin/pytest", f"cd {self.repo} && cd sub && .venv/bin/pytest"):
            with self.subTest(cmd):
                lines = self.stops(cmd)
                hit = [ln for ln in lines if f"{self.repo}/sub/.venv/bin/pytest" in ln]
                self.assertEqual(len(hit), 1, lines)
                self.assertIn("対象の手元", hit[0])

    def test_cd_then_uv_run_is_not_named_for_an_activated_virtualenv(self):
        venv = self.repo.parent / "venvs" / "proj"
        info = self._site(venv) / "stats-0.1.dist-info"
        info.mkdir()
        (info / "direct_url.json").write_text(json.dumps({"url": self.repo.as_uri(), "dir_info": {"editable": True}}))
        path = f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}"
        self.assertEqual(self.check("cd sub && uv run pytest -q", VIRTUAL_ENV=str(venv), PATH=path), [])
        self.assertEqual(len(self.stops("cd sub && pytest -q", VIRTUAL_ENV=str(venv), PATH=path)), 1)

    def test_output_targets_are_not_named_even_when_a_previous_output_exists(self):
        """書き先（リダイレクトの先・書き先を取る旗の空白で分けた値）は、手元に前の出力が在っても名指さない（コマンドが作る）。
        読む側（< の先）は今どおり見る"""
        (self.repo / "build").mkdir()
        for name in ("x.xml", "log.txt", "err", "r.json", "in"):
            (self.repo / "build" / name).write_text("")
        for cmd in ("pytest --junitxml build/x.xml", "pytest --junit-xml build/x.xml", "pytest -q > build/log.txt",
                    "pytest >>build/log.txt 2>build/err", "pytest &> build/log.txt", "pytest >| build/log.txt", "pytest >& build/log.txt",
                    "jest --outputFile build/r.json", "pytest --basetemp build/err -q"):
            with self.subTest(cmd):
                self.assertEqual(self.after_cd(cmd), [])
        lines = self.after_cd("python3 run.py < build/in")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("build/in", lines[0])

    def _site(self, venv):
        site = pathlib.Path(venv) / "lib" / "python3.12" / "site-packages"
        site.mkdir(parents=True, exist_ok=True)
        return site

    def test_activated_virtualenv_with_editable_target_is_named_unless_uv_run(self):
        venv = self.repo.parent / "venvs" / "proj"   # 対象の外の環境（poetry・virtualenvwrapper の形）
        info = self._site(venv) / "stats-0.1.dist-info"
        info.mkdir()
        (info / "direct_url.json").write_text(json.dumps({"url": self.repo.as_uri(), "dir_info": {"editable": True}}))
        path = f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}"
        lines = self.stops("pytest -q", VIRTUAL_ENV=str(venv), PATH=path)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(f"VIRTUAL_ENV（{venv}）", lines[0])
        for cmd in ("uv run pytest -q", "UV_FROZEN=1 uv run pytest -q", "env UV_FROZEN=1 uv run pytest -q",
                    "sh -c 'uv run pytest -q'"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd, VIRTUAL_ENV=str(venv), PATH=path), [])
        self.assertEqual(self.check("pytest -q"), [])

    def test_activated_virtualenv_with_editable_pth_is_named(self):
        venv = self.repo / ".venv"
        (self._site(venv) / "_editable_impl_stats.pth").write_text(f"{self.repo}\n")
        path = f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}"
        self.assertEqual(len(self.stops("python3 -m pytest -q", VIRTUAL_ENV=str(venv), PATH=path)), 1)

    def test_activated_virtualenv_without_target_is_quiet(self):
        """uv run の使い捨ての環境・依存だけの環境は対象の手元のコードを試さない（試験の殻が uv run の下で回る形もこれ）"""
        venv = self.repo.parent / "ephemeral"
        (self._site(venv) / "_virtualenv.pth").write_text("import _virtualenv\n")
        info = self._site(venv) / "pyyaml-6.0.dist-info"
        info.mkdir()
        (info / "direct_url.json").write_text(json.dumps({"url": "https://example.invalid/pyyaml.whl"}))
        path = f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}"
        self.assertEqual(self.check("pytest -q", VIRTUAL_ENV=str(venv), PATH=path), [])

    def test_absolute_reference_to_the_checkout_stops(self):
        """対象の手元（根そのもの・追跡するファイルも）を絶対パスで指す形は、run・単位の worktree からも手元を走らせる（直しの正誤に
        関わらず緑になり得る）ので止める: cd・pushd の先・試験のパス・NAME= と --旗= の値（PYTHONPATH の : 区切りも）。
        書き先の旗の値は見ない"""
        (self.repo / "build").mkdir()
        (self.repo / "build" / "x.xml").write_text("")
        r = self.repo
        for cmd in (f"cd {r} && uv run pytest -q", f"cd {r}; uv run pytest -q", f"pushd {r} && uv run pytest -q",
                    f"cd -P {r} && uv run pytest -q", f"(cd {r} && uv run pytest -q)",
                    f"uv run pytest -q {r}/test_stats.py", f"PYTHONPATH={r} uv run pytest -q",
                    f"PYTHONPATH=/nowhere:{r} uv run pytest -q", f"uv run pytest --rootdir={r} -q"):
            with self.subTest(cmd):
                lines = self.stops(cmd)
                self.assertIn("対象の手元", lines[0])
        for cmd in (f"uv run pytest --junitxml={r}/build/x.xml", f"uv run pytest --junitxml {r}/build/x.xml",
                    f"uv run pytest -q > {r}/build/x.xml", f"cd {r}/nowhere && uv run pytest", "cd /usr && ls"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd), [])

    def test_directory_changing_forms_are_followed(self):
        """所を変える形（pushd・cd -P/-L・make -C・env -C・uv run --directory・npm --prefix・git -C・sh -c '…'・サブシェルの括弧）も
        cd と同じに辿る: 所の先をパスとして見て、後ろの相対の語をその先から読む"""
        venv = self.repo / "sub" / ".venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "pytest").write_text("#!/bin/sh\n")
        for cmd in ("pushd sub && .venv/bin/pytest -q", "cd -P sub && .venv/bin/pytest", "cd -L sub; .venv/bin/pytest",
                    "(cd sub && .venv/bin/pytest)", "env -C sub .venv/bin/pytest", "env --chdir=sub .venv/bin/pytest",
                    "sh -c 'cd sub && .venv/bin/pytest -q'", "bash -lc \"cd sub && .venv/bin/pytest\"",
                    "uv run --directory sub .venv/bin/pytest"):
            with self.subTest(cmd):
                lines = self.after_cd(cmd)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn(f"{self.repo}/sub/.venv/bin/pytest", lines[0])
        r = self.repo
        for cmd in (f"make -C {r} test", f"make --directory={r} test", f"make --directory {r} test", f"env -C {r} pytest",
                    f"uv run --directory {r} pytest", f"uv run --project {r} pytest", f"npm --prefix {r} test",
                    f"git -C {r} status", f"sh -c 'cd {r} && uv run pytest'", f"bash -c '{r}/.venv/bin/pytest -q'",
                    f"env FOO=1 bash -c 'make -C {r} test'"):
            with self.subTest(cmd):
                self.stops(cmd)
        for cmd in ("make -C sub test", "env -C sub uv run pytest", "sh -c 'uv sync && .venv/bin/pytest'",
                    "npm --prefix sub test"):
            with self.subTest(cmd):
                self.assertEqual(self.after_cd(cmd), [])
        lines = self.after_cd("(cd sub) && .venv/bin/pytest")   # 括弧を閉じたら所は戻る: 根の .venv を読む
        self.assertEqual(len(lines), 1, lines)
        self.assertNotIn("sub/.venv", lines[0])
        self.assertIn(".venv/bin/pytest", lines[0])
        (self.repo / "build").mkdir()
        lines = self.after_cd("make -C build test")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("test_cmd の build（", lines[0])

    def test_absolute_reference_in_a_later_segment_stops(self):
        """手元の絶対パスは、前の段が作業ツリーの中に作ることが無いので、後ろの段（&&・;・| の後・後ろの段の sh -c の中）でも止める。
        絶対パスの cd の後の相対の語は最初の段だけ"""
        r = self.repo
        for cmd in (f"set -e; cd {r} && pytest", f"echo run && cd {r} && pytest", f"export CI=1 && cd {r} && pytest",
                    f"npm ci && {r}/node_modules/.bin/jest", f"uv sync && {r}/.venv/bin/pytest",
                    f"uv run true && {r}/.venv/bin/pytest", f"uv sync && PYTHONPATH={r} uv run pytest",
                    f"uv sync && sh -c 'cd {r} && pytest'", f"uv sync && make -C {r} test"):
            with self.subTest(cmd):
                self.stops(cmd)
        for cmd in (f"uv sync && pytest --junitxml {r}/x.xml", f"uv run pytest -q && echo ok > {r}/stats.py",
                    "uv sync && .venv/bin/pytest"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd), [])
        self.assertEqual(self.after_cd("uv sync && .venv/bin/pytest"), [])

    def test_activated_virtualenv_looks_at_every_segment(self):
        """立てた環境の判定は、cd だけの段と動かさない組み込み（echo・export など）を除く全部の段の頭を見る: 頭が uv（pip でなく
        --active でもない）の段だけなら止めず、ほかの段（後ろの pytest・uv run --active・uv pip）が 1 つでも在れば止める"""
        venv = self.repo.parent / "venvs" / "proj"
        info = self._site(venv) / "stats-0.1.dist-info"
        info.mkdir()
        (info / "direct_url.json").write_text(json.dumps({"url": self.repo.as_uri(), "dir_info": {"editable": True}}))
        env = dict(VIRTUAL_ENV=str(venv), PATH=f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}")
        for cmd in ("uv sync && uv run pytest -q", "uv sync --frozen; uv run pytest", "uv --directory sub run pytest",
                    "export CI=1 && uv run pytest", "uv run pytest -q && echo ok", "cd sub && uv sync && uv run pytest"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd, **env), [])
        for cmd in ("uv run pytest && pytest", "uv run --active pytest", "uv pip install -e . && uv run pytest",
                    "uv sync && python3 -m pytest", "uv sync && sh -c 'pytest -q'"):
            with self.subTest(cmd):
                self.assertEqual(len(self.stops(cmd, **env)), 1)

    def test_relative_word_beside_an_activated_virtualenv_stops_for_the_environment(self):
        """根から読む相対の語（走らない形）と立てた環境が並べば、立てた環境で止め、相対の語は注意のまま"""
        venv = self.repo.parent / "venvs" / "proj"
        info = self._site(venv) / "stats-0.1.dist-info"
        info.mkdir()
        (info / "direct_url.json").write_text(json.dumps({"url": self.repo.as_uri(), "dir_info": {"editable": True}}))
        path = f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}"
        lines, notices = self.findings(".venv/bin/python -m pytest", VIRTUAL_ENV=str(venv), PATH=path)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(f"VIRTUAL_ENV（{venv}）", lines[0])
        self.assertEqual(len(notices), 1, notices)
        self.assertIn(".venv/bin/python", notices[0])

    def _editable_venv(self, venv, marker="pyvenv.cfg"):
        """対象を editable で入れた環境（印は pyvenv.cfg か、conda の環境の conda-meta）"""
        info = self._site(venv) / "stats-0.1.dist-info"
        info.mkdir()
        (info / "direct_url.json").write_text(json.dumps({"url": self.repo.as_uri(), "dir_info": {"editable": True}}))
        if marker == "conda-meta":
            (pathlib.Path(venv) / marker).mkdir()
        else:
            (pathlib.Path(venv) / marker).write_text("home = /usr/bin\n")
        return pathlib.Path(venv)

    def test_newline_separates_segments(self):
        """改行は ; と同じ段の区切り（空白に数えると、echo start の段に後ろの pytest が混ざり、組み込みの段として立てた環境を見逃す）。
        行の注（# の後）は改行で閉じる"""
        venv = self.repo.parent / "venvs" / "proj"
        self._editable_venv(venv)
        env = dict(VIRTUAL_ENV=str(venv), PATH=f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}")
        for cmd in ("echo start\npytest -q", "export CI=1\npytest", "uv run true # note\npytest", "cd sub\n\npytest",
                    "bash -c 'echo start\npytest -q'"):
            with self.subTest(cmd):
                self.assertEqual(len(self.stops(cmd, **env)), 1)
        for cmd in ("uv sync\nuv run pytest -q", "echo start &&\n  uv run pytest"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd, **env), [])
        sub = self.repo / "sub" / ".venv" / "bin"
        sub.mkdir(parents=True)
        (sub / "pytest").write_text("#!/bin/sh\n")
        lines = self.after_cd("cd sub\n.venv/bin/pytest -q")   # 改行の前の cd だけの段は所を変える
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(f"{self.repo}/sub/.venv/bin/pytest", lines[0])

    def test_backslash_newline_joins_the_lines(self):
        r"""\ と改行は殻と同じに行を繋ぐ（段の区切りにしない）: uv run pytest \⏎ -q は 1 つの段で立てた環境を使わず、
        bash -lc \⏎ '…' は殻の -c の中を読む。一重引用符の中の \ と改行は字のまま"""
        venv = self.repo.parent / "venvs" / "proj"
        self._editable_venv(venv)
        env = dict(VIRTUAL_ENV=str(venv), PATH=f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}")
        for cmd in ("uv run pytest \\\n  -q", "uv sync && \\\n uv run pytest", "uv run \"pytest\" \\\n -q"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd, **env), [])
        self.assertEqual(len(self.stops("echo start \\\n && pytest -q", **env)), 1)
        r = self.repo
        for cmd in (f"bash -lc \\\n 'cd {r} && uv run pytest'", f"cd \\\n {r} && uv run pytest"):
            with self.subTest(cmd):
                self.stops(cmd)

    def test_shell_c_with_end_of_options_and_option_values(self):
        """殻の -c の前後の旗を飛ばして中を読む: -- （旗の終わり）・-o/+o/-O/+O とその値（-eo pipefail も）・--norc などの長い旗"""
        r = self.repo
        for cmd in (f"bash -c -- 'cd {r} && uv run pytest'", f"bash -o pipefail -c 'cd {r} && uv run pytest'",
                    f"bash -eo pipefail -c 'cd {r} && uv run pytest'", f"bash +o posix -c 'cd {r} && uv run pytest'",
                    f"bash -O extglob -c 'cd {r} && uv run pytest'", f"bash --norc -c 'cd {r} && uv run pytest'",
                    f"bash --rcfile /dev/null -c 'cd {r} && uv run pytest'", f"sh -e -c -- 'cd {r} && uv run pytest'"):
            with self.subTest(cmd):
                self.stops(cmd)
        sub = self.repo / "sub" / ".venv" / "bin"
        sub.mkdir(parents=True)
        (sub / "pytest").write_text("#!/bin/sh\n")
        for cmd in ("bash -o pipefail -c 'cd sub && .venv/bin/pytest'", "bash -c -- 'cd sub && .venv/bin/pytest'"):
            with self.subTest(cmd):
                lines = self.after_cd(cmd)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn(f"{self.repo}/sub/.venv/bin/pytest", lines[0])
        venv = self.repo.parent / "venvs" / "proj"
        self._editable_venv(venv)
        env = dict(VIRTUAL_ENV=str(venv), PATH=f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}")
        for cmd in ("bash -c -- 'uv run pytest'", "bash -o pipefail -c 'uv sync && uv run pytest'"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd, **env), [])

    def test_editable_venv_outside_the_checkout_without_virtual_env_stops(self):
        """VIRTUAL_ENV の無い、対象の外の editable な環境（virtualenvwrapper・poetry・conda）も、絶対パスの語・PATH= の値・起こした
        殻の PATH の段から上へ辿って環境の根（pyvenv.cfg か conda-meta）を見つけ、対象が editable で入っていれば止める"""
        venv = self._editable_venv(self.repo.parent / "venvs" / "proj")
        for cmd in (f"{venv}/bin/pytest -q", f"{venv}/bin/python -m pytest", f"PATH={venv}/bin:$PATH pytest -q",
                    f"uv sync && {venv}/bin/pytest", f"env PATH={venv}/bin pytest", f"bash -c '{venv}/bin/pytest'"):
            with self.subTest(cmd):
                lines = self.stops(cmd)
                self.assertEqual(len(lines), 1, lines)
                self.assertIn(str(venv), lines[0])
        conda = self._editable_venv(self.repo.parent / "conda" / "envs" / "proj", marker="conda-meta")
        path = f"{conda}/bin{os.pathsep}{os.environ.get('PATH', '')}"
        lines = self.stops("pytest -q", PATH=path)   # conda activate は VIRTUAL_ENV を立てない
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(str(conda), lines[0])
        for cmd in ("uv run pytest -q", "uv sync && uv run pytest"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd, PATH=path), [])
        plain = self.repo.parent / "venvs" / "plain"   # 対象の入っていない環境は見ない
        self._site(plain)
        (plain / "pyvenv.cfg").write_text("home = /usr/bin\n")
        for cmd in (f"{plain}/bin/pytest -q", f"PATH={plain}/bin:$PATH pytest"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd), [])
        self.assertEqual(self.check("pytest -q", PATH=f"{plain}/bin{os.pathsep}{os.environ.get('PATH', '')}"), [])

    def test_uv_run_no_project_uses_the_activated_virtualenv(self):
        """uv run --no-project は project の .venv を作らず立てた環境を使うので、--active と同じに数える"""
        venv = self.repo.parent / "venvs" / "proj"
        self._editable_venv(venv)
        env = dict(VIRTUAL_ENV=str(venv), PATH=f"{venv}/bin{os.pathsep}{os.environ.get('PATH', '')}")
        for cmd in ("uv run --no-project pytest -q", "uv run --no-project --with pytest pytest"):
            with self.subTest(cmd):
                self.assertEqual(len(self.stops(cmd, **env)), 1)

    def test_home_forms_are_read_from_the_users_home(self):
        """対象のコマンドは利用者の HOME で走るので、~・$HOME・${HOME} を環境の HOME に展開し、手元を指す形を止める"""
        home = str(self.repo.parent)
        for cmd in ("~/repo/.venv/bin/pytest -q", "$HOME/repo/.venv/bin/pytest -q", "${HOME}/repo/.venv/bin/pytest",
                    "cd ~/repo && .venv/bin/pytest", "PYTHONPATH=~/repo:/x pytest", "sh -c 'cd ~/repo && .venv/bin/pytest'"):
            with self.subTest(cmd):
                self.stops(cmd, HOME=home)
                self.assertEqual(self.check(cmd, HOME=str(self.repo.parent / "elsewhere")), [])
        for cmd in ("$HOMEDIR/repo/.venv/bin/pytest", "a~/repo/.venv/bin/pytest"):
            with self.subTest(cmd):
                self.assertEqual(self.check(cmd, HOME=home), [])

    def test_checkouts_are_every_worktree_but_the_run_tree(self):
        """run の作業ツリー（linked worktree）から、主の作業ツリーと、利用者が git worktree add で作ったほかの作業ツリーを全部引く"""
        run_tree, mine = self.repo.parent / "run-tree", self.repo.parent / "mine"
        for tree in (run_tree, mine):
            gitkit.git(self.repo, "worktree", "add", "-q", "--detach", str(tree))
        for cwd, others in ((run_tree, (self.repo, mine)), (self.repo, (run_tree, mine))):
            with self.subTest(cwd=str(cwd)):
                self.assertEqual(sorted(os.path.realpath(t) for t in testcmd_check.checkouts(cwd)), sorted(map(str, others)))

    def test_empty_command_is_quiet(self):
        self.assertEqual(self.check(""), [])


if __name__ == "__main__":
    unittest.main()
