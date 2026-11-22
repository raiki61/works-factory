"""公式の文書を登録なしの口で引く（lib/libdocs_web.py）の検査。網には出ない（HTTP の口は偽物を渡す）。

- Python: PyPI の JSON（版つき、無ければ版なし）の info.description（その版の README）と、project_urls の docs の場所の
  llms-full.txt・llms.txt（docs の場所の下、次に host の根。`# ` で始まる文書だけを受け、HTML は捨てる）
- JS: npm の registry（版つき、無ければ latest）の readme と homepage の llms*.txt。readme が無く手元にも README が無ければ、
  repository が GitHub の時だけ raw.githubusercontent.com の v<版>・<版> の tag の README.md
- 送る URL はライブラリの名・版と registry の答えに在った URL だけ（使う名もコードの字も送らない）。鍵は付けない。https だけ
- 断片には切らない（持ち主 2026-10-09。量の上限が無くなり、libdocs が文書を丸ごとファイルで盤面に控える）
"""
import json
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import libdocs_web  # noqa: E402

README = ("# Requests\n\nRequests is an elegant and simple HTTP library.\n\n## Installing\n\npip install requests\n\n"
          "## Sessions\n\nUse a Session to persist cookies: `s = requests.Session()`.\n")
PYPI = {"info": {"name": "requests", "version": "2.32.3", "description": README,
                 "description_content_type": "text/markdown",
                 "project_urls": {"Documentation": "https://requests.readthedocs.io/en/latest/",
                                  "Source": "https://github.com/psf/requests"},
                 "home_page": "https://requests.readthedocs.io"}}
LLMS = "# Requests\n\n> HTTP for Humans.\n\n## Docs\n\n- [Quickstart](https://requests.readthedocs.io/q.md): first steps\n"


class Http:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        if url in self.routes:
            code, body = self.routes[url]
            return code, body if isinstance(body, bytes) else (json.dumps(body) if isinstance(body, dict) else body).encode()
        return 404, b"Not Found"

    def urls(self):
        return [u for u, _ in self.calls]


def pylib(version="2.32.3"):
    return {"name": "requests", "search": "requests", "lang": "python", "uses": ["requests.Session"], "version": version}


class PythonCase(unittest.TestCase):
    def test_pypi_readme_and_llms_txt(self):
        http = Http({"https://pypi.org/pypi/requests/2.32.3/json": (200, PYPI),
                     "https://requests.readthedocs.io/en/latest/llms.txt": (200, LLMS)})
        got = libdocs_web.fetch(pylib(), "2.32.3", http)
        self.assertEqual(got["status"], "ok", got)
        self.assertEqual([(d["kind"], d["url"]) for d in got["docs"]],
                         [("readme", "https://pypi.org/project/requests/2.32.3/"),
                          ("llms", "https://requests.readthedocs.io/en/latest/llms.txt")])
        self.assertEqual(http.urls(), ["https://pypi.org/pypi/requests/2.32.3/json",
                                       "https://requests.readthedocs.io/en/latest/llms-full.txt",
                                       "https://requests.readthedocs.io/en/latest/llms.txt"])
        self.assertTrue(all("Authorization" not in h for _, h in http.calls), "鍵は付けない")
        self.assertTrue(all("Session" not in u for u in http.urls()), "使う名を URL に載せない")

    def test_html_is_not_an_llms_txt(self):
        http = Http({"https://pypi.org/pypi/requests/2.32.3/json": (200, PYPI),
                     "https://requests.readthedocs.io/en/latest/llms-full.txt": (200, "<!doctype html><html>SPA</html>"),
                     "https://requests.readthedocs.io/en/latest/llms.txt": (200, "<html></html>"),
                     "https://requests.readthedocs.io/llms-full.txt": (200, "not a heading\nfoo")})
        got = libdocs_web.fetch(pylib(), "2.32.3", http)
        self.assertEqual([d["kind"] for d in got["docs"]], ["readme"])
        self.assertIn("https://requests.readthedocs.io/llms.txt", http.urls(), "host の根も見る")

    def test_unknown_version_falls_back_to_the_project(self):
        http = Http({"https://pypi.org/pypi/requests/json": (200, PYPI)})
        got = libdocs_web.fetch(pylib("2"), "2", http)
        self.assertEqual(got["status"], "ok")
        self.assertEqual(http.urls()[:2], ["https://pypi.org/pypi/requests/2/json", "https://pypi.org/pypi/requests/json"])
        self.assertIn("版 2 が registry に無い", got["note"])

    def test_not_on_the_registry(self):
        got = libdocs_web.fetch(pylib(None), None, Http({}))
        self.assertEqual(got["status"], "not_found")

    def test_registry_error_is_an_error(self):
        got = libdocs_web.fetch(pylib(), "2.32.3", Http({"https://pypi.org/pypi/requests/2.32.3/json": (503, "busy")}))
        self.assertEqual(got["status"], "error")
        self.assertIn("HTTP 503", got["error"])

        def broken(url, headers):
            raise OSError("nodename nor servname provided")
        got = libdocs_web.fetch(pylib(), "2.32.3", broken)
        self.assertEqual(got["status"], "error")
        self.assertIn("nodename", got["error"])

    def test_plain_http_and_code_hosts_are_not_docs_sites(self):
        doc = json.loads(json.dumps(PYPI))
        doc["info"]["project_urls"] = {"Documentation": "http://insecure.example/docs/", "Source": "https://github.com/psf/requests"}
        doc["info"]["home_page"] = ""
        http = Http({"https://pypi.org/pypi/requests/2.32.3/json": (200, doc)})
        got = libdocs_web.fetch(pylib(), "2.32.3", http)
        self.assertEqual(http.urls(), ["https://pypi.org/pypi/requests/2.32.3/json"])
        self.assertEqual([d["kind"] for d in got["docs"]], ["readme"])

    def test_long_docs_are_kept_bounded(self):
        doc = json.loads(json.dumps(PYPI))
        doc["info"]["description"] = "# Big\n\n" + "x" * (libdocs_web.KEEP_CHARS + 500)
        got = libdocs_web.fetch(pylib(), "2.32.3", Http({"https://pypi.org/pypi/requests/2.32.3/json": (200, doc)}))
        self.assertLessEqual(len(got["docs"][0]["text"]), libdocs_web.KEEP_CHARS)


class NodeCase(unittest.TestCase):
    def jslib(self):
        return {"name": "zod", "search": "zod", "lang": "js", "uses": ["object"], "version": "3.23.8"}

    def test_npm_readme_from_github_tag(self):
        """本物の registry の版の文書（/<名>/<版>・/latest）は readme を持たない（2026-10-08 に zod・express・@types/node で
        確かめた）ので、README は repository が GitHub の時の版の tag（v<版>、次に <版>、次に gitHead の commit）から引く"""
        meta = {"name": "zod", "version": "3.23.8", "homepage": "https://zod.dev",
                "repository": {"type": "git", "url": "git+https://github.com/colinhacks/zod.git"}}
        http = Http({"https://registry.npmjs.org/zod/3.23.8": (200, meta),
                     "https://zod.dev/llms.txt": (200, "# Zod\n\n> schemas\n"),
                     "https://raw.githubusercontent.com/colinhacks/zod/3.23.8/README.md": (200, "# Zod\n\nobject() makes it.\n")})
        got = libdocs_web.fetch(self.jslib(), "3.23.8", http)
        self.assertEqual([(d["kind"], d["url"]) for d in got["docs"]],
                         [("readme", "https://raw.githubusercontent.com/colinhacks/zod/3.23.8/README.md"),
                          ("llms", "https://zod.dev/llms.txt")])
        self.assertIn("https://raw.githubusercontent.com/colinhacks/zod/v3.23.8/README.md", http.urls())

    def test_monorepo_directory_and_git_head(self):
        lib = {"name": "@acme/tools-sdk", "search": "@acme/tools-sdk", "lang": "js", "uses": [], "version": None}
        meta = {"name": "@acme/tools-sdk", "version": "0.2.1", "gitHead": "abc1234",
                "repository": {"type": "git", "url": "https://github.com/acme/tools", "directory": "packages/sdk"}}
        http = Http({"https://registry.npmjs.org/@acme%2Ftools-sdk/latest": (200, meta),
                     "https://raw.githubusercontent.com/acme/tools/abc1234/packages/sdk/README.md": (200, "# SDK\n\nhi\n")})
        got = libdocs_web.fetch(lib, None, http)
        self.assertEqual(got["status"], "ok")
        self.assertEqual(got["docs"][0]["url"], "https://raw.githubusercontent.com/acme/tools/abc1234/packages/sdk/README.md")
        self.assertEqual(len(http.urls()), 4, "registry 1・tag 2・gitHead 1")

    def test_registry_readme_is_used_when_present(self):
        http = Http({"https://registry.npmjs.org/zod/3.23.8": (200, {"version": "3.23.8", "readme": "# Zod\n\nhello\n"})})
        got = libdocs_web.fetch(self.jslib(), "3.23.8", http)
        self.assertEqual(got["docs"][0]["url"], "https://www.npmjs.com/package/zod/v/3.23.8")
        self.assertEqual(http.urls(), ["https://registry.npmjs.org/zod/3.23.8"])


class RegistryEdgesCase(unittest.TestCase):
    """registry の答えの端（JSON が読めない・版の note・README の無い印・docs の場所の選び）"""

    PY = "https://pypi.org/pypi/requests/2.32.3/json"

    def py(self, doc, version="2.32.3", extra=None):
        http = Http({self.PY: (200, doc), **(extra or {})})
        return libdocs_web.fetch(pylib(), version, http), http

    def test_keep_cuts_the_head_and_subdomains_of_code_hosts_are_not_docs_sites(self):
        text = "".join(chr(0x3041 + i % 50) for i in range(libdocs_web.KEEP_CHARS + 10))
        self.assertEqual(libdocs_web._keep(text), text[:libdocs_web.KEEP_CHARS])
        for url in ("https://gist.github.com/x", "https://github.com/x", "https://pypi.org/project/x", "https://www.npmjs.com/package/x"):
            with self.subTest(url=url):
                self.assertEqual(libdocs_web.https_site(url), "")
        self.assertEqual(libdocs_web.https_site("https://Docs.Example.org/a/"), "https://Docs.Example.org/a")

    def test_unreadable_json_and_non_200_are_errors_with_their_own_words(self):
        http = Http({self.PY: (200, "not json")})
        got = libdocs_web.fetch(pylib(), "2.32.3", http)
        self.assertEqual((got["status"], got["error"]), ("error", "PyPI: HTTP 200（JSON が読めない）"))
        got = libdocs_web.fetch(pylib(), "2.32.3", Http({self.PY: (200, "[1]")}))
        self.assertEqual(got["error"], "PyPI: HTTP 200（JSON が読めない）")
        got = libdocs_web.fetch(pylib(), "2.32.3", Http({self.PY: (200, {"info": 3})}))
        self.assertEqual(got["status"], "error")
        got = libdocs_web.fetch(pylib(), "2.32.3", Http({self.PY: (500, "{}")}))
        self.assertEqual(got["error"], "PyPI: HTTP 500")
        got = libdocs_web.fetch(self.js(), "3.23.8", Http({"https://registry.npmjs.org/zod/3.23.8": (200, "nope")}))
        self.assertEqual((got["status"], got["error"]), ("error", "npm: HTTP 200（JSON が読めない）"))
        got = libdocs_web.fetch(self.js(), "3.23.8", Http({"https://registry.npmjs.org/zod/3.23.8": (502, "{}")}))
        self.assertEqual(got["error"], "npm: HTTP 502")
        got = libdocs_web.fetch(self.js(), "3.23.8", Http({"https://registry.npmjs.org/zod/3.23.8": (200, "[1]")}))
        self.assertEqual(got["status"], "error")

    def js(self):
        return {"name": "zod", "search": "zod", "lang": "js", "uses": [], "version": "3.23.8"}

    def test_note_only_when_the_pinned_version_is_missing(self):
        got, _ = self.py(PYPI)
        self.assertEqual(got["note"], "")
        got, _ = self.py(PYPI, version=None)
        self.assertEqual(got["note"], "")
        http = Http({"https://registry.npmjs.org/zod/latest": (200, {"version": "4.0.0", "readme": "# z\n"})})
        got = libdocs_web.fetch(self.js(), "3.23.8", http)
        self.assertIn("版 3.23.8 が registry に無い", got["note"])
        http = Http({"https://registry.npmjs.org/zod/3.23.8": (200, {"version": "3.23.8", "readme": "# z\n"})})
        self.assertEqual(libdocs_web.fetch(self.js(), "3.23.8", http)["note"], "")

    def test_pypi_readme_is_used_unless_blank_or_unknown_and_search_name_wins(self):
        for blank in ("", "   ", "UNKNOWN"):
            with self.subTest(blank=blank):
                doc = {"info": {"version": "1", "description": blank, "project_urls": {}}}
                got, _ = self.py(doc)
                self.assertEqual((got["status"], got["docs"]), ("not_found", []))
        got, _ = self.py({"info": {"version": "", "description": "# d\n"}})
        self.assertEqual(got["docs"][0]["url"], "https://pypi.org/project/requests/")
        lib = {"name": "PyYAML", "search": "pyyaml", "lang": "python", "uses": []}
        http = Http({"https://pypi.org/pypi/pyyaml/json": (200, PYPI)})
        self.assertEqual(libdocs_web.fetch(lib, None, http)["status"], "ok")
        lib = {"name": "pyyaml", "lang": "python", "uses": []}
        http = Http({"https://pypi.org/pypi/pyyaml/json": (200, PYPI)})
        self.assertEqual(libdocs_web.fetch(lib, None, http)["status"], "ok")

    def test_github_repository_forms(self):
        gh = libdocs_web._github
        self.assertEqual(gh("git+https://github.com/a/b.git"), ("a", "b", ""))
        self.assertEqual(gh("github:a/b"), ("a", "b", ""))
        self.assertEqual(gh("a/b"), ("a", "b", ""))
        self.assertEqual(gh({"url": "a/b", "directory": "/pkg/x/"}), ("a", "b", "pkg/x"))
        self.assertEqual(gh({"url": "https://github.com/a/b", "directory": "../x"}), ("a", "b", ""))
        self.assertEqual(gh({"url": "https://github.com/a/b", "directory": "a b"}), ("a", "b", ""))
        self.assertEqual(gh({"url": "https://github.com/a/b", "directory": 3}), ("a", "b", ""))
        self.assertIsNone(gh("https://example.org/a/b"))
        self.assertIsNone(gh("not a repo"))
        self.assertIsNone(gh(None))
        self.assertIsNone(gh({"url": 3}))

    def test_npm_readme_fallbacks(self):
        base = "https://registry.npmjs.org/zod/3.23.8"
        repo = {"url": "https://github.com/a/zod"}
        raw = "https://raw.githubusercontent.com/a/zod/"
        # README が無い印の readme は使わず、tag の README に進む。空の README は次の ref へ
        http = Http({base: (200, {"version": "3.23.8", "readme": "ERROR: No README data found!", "repository": repo}),
                     raw + "v3.23.8/README.md": (200, "  \n"), raw + "3.23.8/README.md": (200, "# real\n")})
        got = libdocs_web.fetch(self.js(), "3.23.8", http)
        self.assertEqual([d["url"] for d in got["docs"]], [raw + "3.23.8/README.md"])
        # 版が無い（got_version が空）時は GitHub へ行かない
        http = Http({"https://registry.npmjs.org/zod/3.23.8": (200, {"repository": repo})})
        self.assertEqual(libdocs_web.fetch(self.js(), "3.23.8", http)["status"], "not_found")
        self.assertEqual(http.urls(), ["https://registry.npmjs.org/zod/3.23.8"])
        # gitHead は 7〜40 桁の 16 進だけ
        for head, n in (("abc1234", 4), ("zzzzzzz", 3), ("abc12", 3)):
            http = Http({base: (200, {"version": "3.23.8", "gitHead": head, "repository": repo})})
            libdocs_web.fetch(self.js(), "3.23.8", http)
            self.assertEqual(len(http.urls()), n, head)
        # 取得の例外は README を諦め、registry の答えは返す（落とさない）
        calls = []

        def flaky(url, headers):
            calls.append(url)
            if url == base:
                return 200, json.dumps({"version": "3.23.8", "repository": repo}).encode()
            raise OSError("down")
        got = libdocs_web.fetch(self.js(), "3.23.8", flaky)
        self.assertEqual((got["status"], len(calls)), ("not_found", 2), "例外で README の探しをやめる（registry 1・README 1）")

    def test_npm_not_found_search_name_and_first_readme_wins(self):
        self.assertEqual(libdocs_web.fetch(self.js(), None, Http({}))["status"], "not_found")
        lib = {"name": "Zod", "search": "zod", "lang": "js", "uses": []}
        http = Http({"https://registry.npmjs.org/zod/latest": (200, {"version": "1", "readme": "# z\n"})})
        self.assertEqual(libdocs_web.fetch(lib, None, http)["docs"][0]["url"], "https://www.npmjs.com/package/zod/v/1")
        lib = {"name": "zod", "lang": "js", "uses": []}
        self.assertEqual(libdocs_web.fetch(lib, None, http)["status"], "ok")
        raw = "https://raw.githubusercontent.com/a/zod/"
        http = Http({"https://registry.npmjs.org/zod/latest": (200, {"version": "1", "repository": "a/zod"}),
                     raw + "v1/README.md": (200, "# one\n"), raw + "1/README.md": (200, "# two\n")})
        got = libdocs_web.fetch({"name": "zod", "lang": "js", "uses": []}, None, http)
        self.assertEqual([d["url"] for d in got["docs"]], [raw + "v1/README.md"])
        self.assertNotIn(raw + "1/README.md", http.urls())

    def test_unexpected_error_text_is_cut_to_200_from_the_head(self):
        def boom(url, headers):
            raise RuntimeError("x" * 500)
        got = libdocs_web.fetch(pylib(), None, boom)
        self.assertEqual(len(got["error"]), 200)
        self.assertTrue(got["error"].startswith("RuntimeError: xx"))


class SafetyCase(unittest.TestCase):
    def test_ip_literal_and_localhost_are_not_docs_sites(self):
        for url in ("https://10.0.0.5/docs", "https://169.254.169.254/latest", "https://localhost/docs", "https://[::1]/x",
                    "https://intranet/docs"):
            with self.subTest(url=url):
                self.assertEqual(libdocs_web.https_site(url), "")
        self.assertEqual(libdocs_web.https_site("https://docs.example.org/en/"), "https://docs.example.org/en")

    def test_redirects_only_to_public_https(self):
        self.assertTrue(libdocs_web.safe_url("https://docs.example.org/llms.txt"))
        for url in ("http://docs.example.org/llms.txt", "https://127.0.0.1/llms.txt", "ftp://x.example/y", "https://localhost/"):
            with self.subTest(url=url):
                self.assertFalse(libdocs_web.safe_url(url))


class NoFragmentsCase(unittest.TestCase):
    def test_docs_are_not_cut_into_fragments(self):
        for name in ("fragments", "CHUNK_MAX"):
            with self.subTest(name):
                self.assertFalse(hasattr(libdocs_web, name))


if __name__ == "__main__":
    unittest.main()
