"""ライブラリの文書（lib/libdocs.py。手元の版・公式の 2 つの出どころを機械が引いて指示書に貼る）の検査。

網には出ない（HTTP の口は偽物を渡す）。盤面は周の置き場（dir・work）だけを持つ偽物。
- 見つけ方: 単位のファイルの import（Python・JS/TS）から標準ライブラリとリポジトリの中の物を除き、依存の宣言
  （pyproject.toml・requirements*.txt・package.json）から版を引く。宣言のファイル自体が単位なら宣言の全部が対象
- 控え: 公式の取れた物と見つからない物はライブラリ＋版の鍵で渡された控えの置き場に書き、同じ置き場を渡す間は網に出ない
  （前の周の置き場は読まない。周をまたぐのは run をまたぐ控え）
- 数で言う: 取れなかった・見つからない・上限で取らない物は節の頭に数と名前で出す（黙って落とさない）
- 標準ライブラリだけの対象は何も取らず、取らないことを書く。WORKS_LIBDOCS_WEB=off も網に出ないことを書く
- 組み立て: 修正案の役の頭（planblk.head）に節が入る（ComposerCase）
- 出どころ（SourcesCase。設計 works/docs/plans/2026-10-08-libdocs-sources.md）: 手元の版 → 公式の順に並べる。手元で読んだ版で
  公式に問う。どこからも取れなかった物は名指して役に自分で引けと言う。off でも手元は読む。公式の取れた物と見つからない物は
  盤面と run をまたぐ控えに控える（取れなかった物は控えない）
- 文書はファイルで渡す（FilesCase。持ち主 2026-10-09）: 量の上限（BUDGET）は無い。手元と公式の文書はライブラリごとに今の周の
  libdocs/<名>@<版>/ にファイルで丸ごと控え、節にはライブラリごとの名・入っている版・出どころ・ファイルのパスと短い要点だけを
  並べる（本文は貼らない）。役は要る時にそのファイルを Read で読む（読むべき物には数えない）
- Context7 はやめた（持ち主 2026-10-09）: 網の問いは公式の口にだけ出る。前の版が run をまたぐ控えに残した Context7 の控え（問いの digest の名・
  名と版だけの名・枠切れの印 _quota.json）は読まない（NoContext7Case）
"""
import json
import pathlib
import re
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import libdocs  # noqa: E402
import webget  # noqa: E402


class FakeBoard:
    """周の置き場だけを持つ盤面（DiskBoard.work と同じ形: <dir>/r<N>/<name>）"""

    def __init__(self, d, rnd=1):
        self.dir = pathlib.Path(d)
        self.round = rnd

    def work(self, name):
        p = self.dir / f"r{self.round}" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


PYPI = {"info": {"name": "requests", "version": "2.32.3",
                 "description": "# Requests\n\nHTTP for Humans.\n\n## Sessions\n\nUse `requests.Session` to keep cookies.\n",
                 "project_urls": {"Documentation": "https://requests.readthedocs.io/en/latest/"}}}
PYPI_ROUTE = "pypi.org/pypi/requests/2.32.3/json"
PYPI_PAGE = "https://pypi.org/project/requests/2.32.3/"
REQ_SP = ".venv/lib/python3.12/site-packages"


class FakeHttp:
    def __init__(self, routes=None):
        self.calls = []
        self.routes = routes or {}

    def __call__(self, url, headers):
        self.calls.append(url)
        for key, (code, doc) in self.routes.items():
            if key in url:
                return code, (doc if isinstance(doc, str) else json.dumps(doc)).encode()
        return 404, json.dumps({"message": "Not Found"}).encode()


def ok_http():
    """requests 2.32.3 の公式の文書（PyPI の README）だけを返す口"""
    return FakeHttp({PYPI_ROUTE: (200, PYPI)})


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.board = FakeBoard(self.tmp / "board")
        self.env = {}

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return rel

    def saved(self, name, board=None, rnd=1):
        """今の周の libdocs/requests@2.32.3/ に控えたファイル（name は glob の形。local-*.md など）の字（無ければ None）"""
        got = sorted(((board or self.board).dir / f"r{rnd}" / libdocs.CACHE_DIR / "requests@2.32.3").glob(name))
        return got[0].read_text(encoding="utf-8") if got else None

    def install(self, base=None):
        base = base or self.repo
        sp = base / REQ_SP
        (sp / "requests").mkdir(parents=True)
        (sp / "requests" / "__init__.py").write_text(
            'raise SystemExit("never import")\nfrom .sessions import Session\n', encoding="utf-8")
        (sp / "requests" / "sessions.py").write_text(
            'class Session:\n    """A Requests session (LOCAL DOCSTRING)."""\n\n    def mount(self, prefix, adapter):\n'
            '        """Registers a connection adapter."""\n', encoding="utf-8")
        (sp / "requests-2.32.3.dist-info").mkdir()
        (sp / "requests-2.32.3.dist-info" / "METADATA").write_text("Name: requests\nVersion: 2.32.3\n", encoding="utf-8")


class DetectCase(Base):
    def test_python_imports_split_into_stdlib_local_and_libraries(self):
        self.write("helper.py", "X = 1\n")
        f = self.write("app.py", "import os, json\nimport helper\nfrom . import sibling\nimport requests\n"
                                 "from yaml import safe_load\n")
        self.write("requirements.txt", "requests==2.32.3\nPyYAML>=6.0\n")
        got = libdocs.detect(self.repo, [f])
        self.assertEqual(sorted(got["libs"]), ["requests", "yaml"])
        self.assertEqual(got["libs"]["requests"]["version"], "2.32.3")
        self.assertEqual(got["libs"]["yaml"]["version"], "6.0")      # 輸入の名 yaml → 配る名 PyYAML
        self.assertEqual(got["libs"]["yaml"]["uses"], ["yaml.safe_load"])
        self.assertEqual(got["counts"]["stdlib"], 2)
        self.assertEqual(got["counts"]["local"], 2)

    def test_nested_own_python_package_is_not_a_library(self):
        self.write("backend/app/__init__.py", "")
        self.write("backend/app/core.py", "V = 1\n")
        f = self.write("backend/tests/test_x.py", "import app\nfrom app.core import V\nimport requests\n")
        self.write("requirements.txt", "requests==2.32.3\n")
        got = libdocs.detect(self.repo, [f])
        self.assertEqual(sorted(got["libs"]), ["requests"], "作業ツリーで定義された app を外のライブラリとして引かない")
        self.assertEqual(got["counts"]["local"], 2)

    def test_own_js_workspace_package_is_not_a_library(self):
        self.write("packages/ui/package.json", json.dumps({"name": "@acme/ui"}))
        f = self.write("web/app.ts", "import { Button } from '@acme/ui';\nimport { z } from 'zod';\n")
        self.write("package.json", json.dumps({"dependencies": {"zod": "^3.23.8"}}))
        got = libdocs.detect(self.repo, [f])
        self.assertEqual(sorted(got["libs"]), ["zod"], "workspace の自分のパッケージ名を外のライブラリとして引かない")
        self.assertEqual(got["counts"]["local"], 1)

    def test_js_imports_and_package_json(self):
        f = self.write("web/app.ts", "import { z } from 'zod';\nimport fs from 'node:fs';\nimport x from './x';\n"
                                     "const r = require(\"@tanstack/query-core\");\nimport path from 'path';\n")
        self.write("package.json", json.dumps({"dependencies": {"zod": "^3.23.8"},
                                               "devDependencies": {"@tanstack/query-core": "~5.0.0"}}))
        got = libdocs.detect(self.repo, [f])
        self.assertEqual(sorted(got["libs"]), ["@tanstack/query-core", "zod"])
        self.assertEqual(got["libs"]["zod"]["version"], "3.23.8")
        self.assertEqual(got["counts"]["stdlib"], 2)
        self.assertEqual(got["counts"]["local"], 1)

    def test_touched_manifest_brings_all_its_dependencies(self):
        f = self.write("pyproject.toml", '[project]\nname = "x"\ndependencies = ["httpx==0.27.0", "rich"]\n')
        got = libdocs.detect(self.repo, [f])
        self.assertEqual(sorted(got["libs"]), ["httpx", "rich"])
        self.assertEqual(got["libs"]["httpx"]["version"], "0.27.0")
        self.assertIsNone(got["libs"]["rich"]["version"])

    def test_unreadable_files_are_counted(self):
        f = self.write("bad.py", "def (:\n")
        got = libdocs.detect(self.repo, [f, "missing.py"])
        self.assertEqual(sorted(u["path"] for u in got["unreadable"]), ["bad.py", "missing.py"])

    def test_detect_records_the_used_names(self):
        f = self.write("app.py", "import requests\nfrom yaml import safe_load\nrequests.get('u')\n")
        got = libdocs.detect(self.repo, [f])
        self.assertEqual(got["libs"]["requests"]["uses"], ["requests.get"])
        self.assertEqual(got["libs"]["yaml"]["uses"], ["yaml.safe_load"])
        self.assertNotIn("symbols", got["libs"]["requests"], "Context7 の問いの名（symbols）はもう持たない")
        g = self.write("web/a.ts", "import { object } from 'zod';\n")
        self.assertEqual(libdocs.detect(self.repo, [g])["libs"]["zod"]["uses"], ["object"])


class SectionCase(Base):
    def section(self, files, http, **kw):
        return libdocs.section(self.board.work(""), self.repo, files, get=http, env=self.env, **kw)

    def test_library_detected_gives_section_with_sources(self):
        f = self.write("app.py", "import requests\n")
        self.write("requirements.txt", "requests==2.32.3\n")
        http = ok_http()
        text = self.section([f], http)
        self.assertTrue(text.startswith("数: 見つけた 1 本"), text)
        self.assertIn("- 公式の文書: 取れた 1 本", text)
        self.assertIn(f"- 公式: {PYPI_PAGE} → ", text)
        self.assertIn("Use `requests.Session` to keep cookies", self.saved("official-1-readme.md"))
        self.assertIn("https://" + PYPI_ROUTE, http.calls)

    def test_network_error_is_declared(self):
        f = self.write("app.py", "import requests\n")

        def broken(url, headers):
            raise webget.FetchError("URLError: nodename nor servname provided")
        text = self.section([f], broken)
        self.assertIn("取れなかった 1 本（requests: ", text)
        self.assertIn("URLError", text)

    def test_stdlib_only_fetches_nothing_and_says_so(self):
        self.write("util.py", "V = 1\n")
        f = self.write("app.py", "import os\nimport util\n")
        http = FakeHttp()
        text = self.section([f], http)
        self.assertEqual(http.calls, [])
        self.assertIn("取る物は無い（0 本）", text)
        self.assertIn("標準 1", text)

    def test_switch_off_is_declared(self):
        f = self.write("app.py", "import requests\n")
        self.assertEqual(libdocs.ENV_SWITCH, "WORKS_LIBDOCS_WEB")
        self.env = {libdocs.ENV_SWITCH: "off"}
        http = FakeHttp()
        text = self.section([f], http)
        self.assertEqual(http.calls, [])
        self.assertIn(f"{libdocs.ENV_SWITCH}=off", text)


class SourcesCase(Base):
    """2 つの出どころ（手元の版・公式）を順に並べ、量の上限の中で合わせる"""

    def test_two_sources_in_order_with_the_installed_version(self):
        self.install()
        f = self.write("app.py", "from requests import Session\n")
        http = ok_http()
        text = libdocs.section(self.board.work(""), self.repo, [f], get=http, env={})
        self.assertLess(text.index("- 手元の版: " + str(self.repo / ".venv")), text.index(f"- 公式: {PYPI_PAGE}"))
        self.assertIn("LOCAL DOCSTRING", self.saved("local-*.md"))
        self.assertIn("- 手元の版: 読めた 1 本（requests 2.32.3）", text)
        self.assertIn("- 公式の文書: 取れた 1 本", text)
        self.assertIn("https://" + PYPI_ROUTE, http.calls, "宣言が無くても手元の版で公式に問う")
        self.assertIn(str(self.repo / REQ_SP / "requests" / "sessions.py"), self.saved("local-*.md"), "手元の断片の出典はファイル")
        self.assertNotIn("- どこからも文書が無い", text)

    def test_libraries_without_any_docs_are_named_for_the_roles(self):
        f = self.write("app.py", "import requests\nimport flask\n")
        text = libdocs.section(self.board.work(""), self.repo, [f], get=FakeHttp(), env={})
        self.assertIn("- どこからも文書が無い: flask、requests（手元に入っていない。公式から取れなかった", text)
        self.assertNotIn("WebSearch", text, "自分で引けの文は呼び手の md が持つ")
        self.assertIn("- 手元の版: 読めた 0 本／入っていない 2 本（flask、requests）", text)
        self.assertIn("- 公式の文書: 取れた 0 本", text)
        self.assertIn("見つからない 2 本（flask、requests）", text)

    def test_installed_distribution_name_is_what_the_registry_is_asked(self):
        """輸入の名と配る名が違い（import serial・配る名 pyserial）、宣言にも表 PY_DIST にも無い時、手元で読んだ配る名で PyPI に問う
        （輸入の名で問うと別のプロジェクトの README を公式として貼る）"""
        sp = self.repo / REQ_SP
        (sp / "serial").mkdir(parents=True)
        (sp / "serial" / "__init__.py").write_text('"""pySerial."""\n', encoding="utf-8")
        (sp / "pyserial-3.5.dist-info").mkdir()
        (sp / "pyserial-3.5.dist-info" / "METADATA").write_text("Name: pyserial\nVersion: 3.5\n", encoding="utf-8")
        (sp / "pyserial-3.5.dist-info" / "top_level.txt").write_text("serial\n", encoding="utf-8")
        f = self.write("app.py", "import serial\n")
        http = FakeHttp()
        libdocs.section(self.board.work(""), self.repo, [f], get=http, env={})
        pypi = [u for u in http.calls if "pypi.org" in u]
        self.assertEqual(pypi[0], "https://pypi.org/pypi/pyserial/3.5/json")
        self.assertFalse([u for u in pypi if "/pypi/serial/" in u])

    def test_switch_off_still_reads_the_installed_version(self):
        self.install()
        f = self.write("app.py", "from requests import Session\n")
        http = FakeHttp()
        text = libdocs.section(self.board.work(""), self.repo, [f], get=http, env={libdocs.ENV_SWITCH: "off"})
        self.assertEqual(http.calls, [])
        self.assertIn("LOCAL DOCSTRING", self.saved("local-*.md"))
        self.assertIn(f"{libdocs.ENV_SWITCH}=off", text)
        g = self.write("other.py", "import flask\n")
        text = libdocs.section(self.board.work(""), self.repo, [g], get=http, env={libdocs.ENV_SWITCH: "off"})
        self.assertIn("- どこからも文書が無い: flask（手元に入っていない。網には出ていない", text)
        self.assertNotIn("公式から取れなかった", text)

    def test_official_docs_are_cached_on_the_board_and_in_the_home(self):
        self.install()
        f = self.write("app.py", "from requests import Session\n")
        home = self.tmp / "home"
        libdocs.section(self.board.work(""), self.repo, [f], get=ok_http(), env={}, now=1_800_000_000.0, shared=home)
        self.board.round = 2
        http = FakeHttp()
        text = libdocs.section(self.board.work(""), self.repo, [f], get=http, env={}, now=1_800_000_060.0, shared=home)
        self.assertEqual(http.calls, [], "次の周は前の周の置き場を読まず、run をまたぐ控えを読む")
        self.assertIn("Use `requests.Session` to keep cookies", self.saved("official-1-readme.md", rnd=2))
        other = FakeBoard(self.tmp / "board2")
        http = FakeHttp()
        libdocs.section(other.work(""), self.repo, [f], get=http, env={}, now=1_800_000_120.0, shared=home)
        self.assertEqual(http.calls, [], "同じ根のほかの run は run をまたぐ控えを読む")
        self.assertIn("Use `requests.Session` to keep cookies", self.saved("official-1-readme.md", board=other))
        self.assertTrue((home / libdocs.CACHE_DIR / ("requests@2.32.3" + libdocs.OFFICIAL_SUFFIX)).is_file())

    def test_official_failure_is_not_cached(self):
        f = self.write("app.py", "import requests\n")
        text = libdocs.section(self.board.work(""), self.repo, [f], get=FakeHttp({"pypi.org": (503, {"m": "busy"})}), env={})
        self.assertIn("取れなかった 1 本（requests: PyPI: HTTP 503）", text)
        self.assertFalse(list(self.board.dir.glob(f"r*/{libdocs.CACHE_DIR}/*{libdocs.OFFICIAL_SUFFIX}")))

    def test_declared_version_differs_from_the_installed_one(self):
        self.install()
        f = self.write("app.py", "from requests import Session\n")
        self.write("requirements.txt", "requests==2.31.0\n")
        text = libdocs.section(self.board.work(""), self.repo, [f], get=FakeHttp(), env={})
        self.assertIn("requests: 宣言の版 2.31.0 と入っている版 2.32.3 が違う（入っている版で引いた）", text)

    def test_record_keeps_the_version_read_and_no_doc_text(self):
        self.install()
        f = self.write("app.py", "from requests import Session\n")
        libdocs.section(self.board.work(""), self.repo, [f], get=ok_http(), env={})
        rec = json.loads((self.board.dir / "r1" / libdocs.RECORD).read_text(encoding="utf-8"))
        row = rec["rows"][0]
        self.assertEqual(sorted(row), ["files", "lib", "local", "official"], "行は見つけた物と出どころごとの結果と控えたファイル")
        self.assertRegex(pathlib.Path(row["files"][0]).name, r"^local-[0-9a-f]{8}\.md$")
        self.assertEqual(pathlib.Path(row["files"][1]).name, "official-1-readme.md")
        self.assertEqual(row["local"]["version"], "2.32.3")
        self.assertEqual(row["official"]["status"], "ok")
        self.assertNotIn("LOCAL DOCSTRING", json.dumps(rec))


class FilesCase(Base):
    """文書はファイルで渡す（持ち主 2026-10-09。量の上限は Context7 の口が tokens を求め、本文を指示書に貼っていたから在った）"""

    def setUp(self):
        super().setUp()
        self.install()
        self.f = self.write("app.py", "from requests import Session\nrequests.get('u')\n")

    def test_no_budget(self):
        for name in ("BUDGET", "SOURCES", "_allocate"):
            with self.subTest(name):
                self.assertFalse(hasattr(libdocs, name))
        self.assertNotIn("budget", libdocs.section.__code__.co_varnames)

    def test_section_lists_files_and_does_not_paste_the_text(self):
        text = libdocs.section(self.board.work(""), self.repo, [self.f], get=ok_http(), env={})
        self.assertNotIn("LOCAL DOCSTRING", text)
        self.assertNotIn("Use `requests.Session` to keep cookies", text)
        self.assertNotIn("トークン", text)
        self.assertNotIn("予算", text)
        local, = (self.board.dir / "r1" / libdocs.CACHE_DIR / "requests@2.32.3").glob("local-*.md")
        official = self.board.dir / "r1" / libdocs.CACHE_DIR / "requests@2.32.3" / "official-1-readme.md"
        block = text[text.index("### requests 2.32.3"):]
        self.assertIn(f"- 手元の版: {self.repo / '.venv'} → {local}", block)
        self.assertIn(f"- 公式: {PYPI_PAGE} → {official}", block)
        self.assertIn("- 公式の要約: HTTP for Humans.", block, "安く取れる要点は数行だけ")
        self.assertIn("requests.Session", block, "単位が使う名を並べる（ファイルの中を探す手がかり）")
        self.assertIn("控えたファイル 2 本", text)
        self.assertIn("LOCAL DOCSTRING", local.read_text(encoding="utf-8"))
        self.assertIn(str(self.repo / REQ_SP / "requests" / "sessions.py"), local.read_text(encoding="utf-8"))
        self.assertIn(PYPI_PAGE, official.read_text(encoding="utf-8"), "公式のファイルは出典の URL を持つ")

    def test_long_docs_are_saved_whole_and_the_section_stays_short(self):
        body = "# Requests\n\nHTTP for Humans.\n\n" + "\n\n".join(f"## Part {i}\n\n" + "word " * 200 for i in range(60))
        http = FakeHttp({PYPI_ROUTE: (200, {"info": {**PYPI["info"], "description": body}})})
        text = libdocs.section(self.board.work(""), self.repo, [self.f], get=http, env={})
        self.assertLess(len(text), 4000, "節は本文の長さに依らない")
        self.assertIn("## Part 59", self.saved("official-1-readme.md"), "切らずに丸ごと控える")

    def test_lanes_with_other_units_do_not_overwrite_each_other(self):
        """並べの枝は同じ周の置き場を分け合う。単位が使う名が違えば手元のファイルは別の名で、互いに上書きしない"""
        g = self.write("other.py", "from requests.sessions import Session\n")
        a = libdocs.section(self.board.work(""), self.repo, [self.f], get=ok_http(), env={})
        b = libdocs.section(self.board.work(""), self.repo, [g], get=ok_http(), env={})
        files = sorted((self.board.dir / "r1" / libdocs.CACHE_DIR / "requests@2.32.3").glob("local-*.md"))
        self.assertEqual(len(files), 2, files)
        self.assertTrue(all(str(p) in a or str(p) in b for p in files))


class HomeBase(Base):
    """run をまたぐ控えの根（呼ぶ側が shared で渡す）を持つ run の節"""
    T = 1_800_000_000.0

    def setUp(self):
        super().setUp()
        self.home = self.tmp / "shared-root"
        self.shared = self.home
        self.env = {}
        self.f = self.write("app.py", "import requests\n")
        self.write("requirements.txt", "requests==2.32.3\n")

    def run_section(self, board_name, http, now):
        board = FakeBoard(self.tmp / board_name)
        return board, libdocs.section(board.work(""), self.repo, [self.f], get=http, env=self.env, now=now,
                                      shared=self.shared)


class SharedCacheCase(HomeBase):
    """run をまたぐ控え（呼ぶ側が渡す根の下 libdocs/）: 同じ根のほかの run が取った公式の文書を TTL の間は網に出ずに使う"""

    def test_later_run_uses_the_shared_cache_without_the_network(self):
        self.run_section("run1", ok_http(), self.T)
        http = FakeHttp()
        board, text = self.run_section("run2", http, self.T + 3600)
        self.assertEqual(http.calls, [])
        self.assertIn("ほかの run 1 本", text)
        self.assertIn("Use `requests.Session` to keep cookies", self.saved("official-1-readme.md", board=board))
        self.assertTrue((board.dir / "r1" / libdocs.CACHE_DIR / ("requests@2.32.3" + libdocs.OFFICIAL_SUFFIX)).is_file(),
                        "使った物は盤面の周の置き場にも写す（run の中で同じ物を読む）")

    def test_shared_cache_expires_after_the_ttl(self):
        self.run_section("run1", ok_http(), self.T)
        http = ok_http()
        _, text = self.run_section("run2", http, self.T + libdocs.SHARED_TTL + 1)
        self.assertTrue(http.calls, "TTL を過ぎた控えは使わずに取り直す")
        self.assertIn("ほかの run 0 本", text)

    def test_no_root_no_shared_cache(self):
        self.shared = None
        self.run_section("run1", ok_http(), self.T)
        http = ok_http()
        self.run_section("run2", http, self.T + 60)
        self.assertTrue(http.calls, "根が無ければ run ごとの控えだけ")
        self.assertFalse(self.home.exists())

    def test_shared_cache_root_is_an_argument(self):
        self.env = {"WORKS_ADAPTER_HOME": str(self.home)}
        self.shared = None
        self.run_section("run1", ok_http(), self.T)
        self.assertFalse(self.home.exists(), "根は環境変数から読まない")
        self.shared = self.home
        self.run_section("run1b", ok_http(), self.T)
        http = FakeHttp()
        self.run_section("run2", http, self.T + 60)
        self.assertEqual(http.calls, [], "渡した根の控えを後の run が網に出ずに使う")

    def test_failures_are_not_shared(self):
        self.run_section("run1", FakeHttp({"pypi.org": (500, {"error": "boom"})}), self.T)
        http = ok_http()
        _, text = self.run_section("run2", http, self.T + 60)
        self.assertTrue(http.calls)
        self.assertIn("取れた 1 本", text)

    def test_broken_shared_entry_is_ignored(self):
        self.run_section("run1", ok_http(), self.T)
        for p in (self.home / libdocs.CACHE_DIR).glob("requests@*.json"):
            p.write_text("{not json", encoding="utf-8")
        http = ok_http()
        _, text = self.run_section("run2", http, self.T + 60)
        self.assertTrue(http.calls)
        self.assertIn("取れた 1 本", text)


class NoContext7Case(HomeBase):
    """Context7 はやめた（持ち主 2026-10-09）。網の問いは公式の口にだけ出し、節は Context7 を言わず、前の版が run をまたぐ控えと盤面に残した
    Context7 の控え（名と版の not_found・問いの digest の ok・枠切れの印 _quota.json）は読まない"""

    def leftovers(self, sd):
        sd.mkdir(parents=True, exist_ok=True)
        old = {"schema": libdocs.SCHEMA, "lib": {}, "id": "/psf/requests", "version_note": "", "error": "", "at": self.T}
        (sd / "requests@2.32.3.json").write_text(json.dumps({**old, "status": "not_found", "snippets": []}), encoding="utf-8")
        (sd / "requests@2.32.3-0123456789ab.json").write_text(json.dumps(
            {**old, "status": "ok", "snippets": [{"title": "t", "source": "s", "tokens": 5, "text": "C7 LEFTOVER"}]}),
            encoding="utf-8")
        (sd / "_quota.json").write_text(json.dumps({"schema": libdocs.SCHEMA, "reason": "HTTP 429", "at": self.T,
                                                    "keyed": False}), encoding="utf-8")

    def test_only_the_official_registry_is_asked(self):
        seen = []

        def http(url, headers):
            seen.append((url, dict(headers)))
            return ok_http()(url, headers)
        _, text = self.run_section("run1", http, self.T)
        self.assertTrue(seen)
        self.assertFalse([u for u, _ in seen if "context7" in u], "Context7 の口に問わない")
        self.assertTrue(all("Authorization" not in h for _, h in seen), "鍵の頭はどこにも付けない")
        self.assertNotIn("Context7", text)

    def test_leftover_context7_caches_are_not_read(self):
        self.leftovers(self.home / libdocs.CACHE_DIR)
        self.leftovers(self.tmp / "run2" / "r1" / libdocs.CACHE_DIR)
        http = ok_http()
        _, text = self.run_section("run2", http, self.T + 60)
        self.assertTrue(http.calls, "前の版の枠切れの印で網を止めない")
        self.assertNotIn("C7 LEFTOVER", text)
        self.assertNotIn("Context7", text)
        self.assertNotIn("枠切れ", text)
        self.assertIn("- 公式の文書: 取れた 1 本", text)

    def test_context7_names_are_gone_from_the_module(self):
        for name in ("API", "ENV_KEY", "QUOTA_MARK", "QUOTA_NOTICE", "QUOTA_HOLD", "notice", "fetch"):
            with self.subTest(name):
                self.assertFalse(hasattr(libdocs, name))


if __name__ == "__main__":
    unittest.main()
