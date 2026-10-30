"""見る道具のページを画面の無い Chromium で開いて押す（viewer/page.tpl.html。docs/design/viewer.md の 6.5・6.7）。

- 「配線も出す」の時、走らなかった段の配線の歩でも、その段の行が開いて今の札が出る
- 板の入れ子の口の字（「<target> の中を閉じる」「<target> の中をここで開く ＋」）は、押した後の開け閉めに合う
- 図を作り直す操作（入れ子の札・入れ子の頭の −・道具の行のチェック・畳んだ段の「開く ＋」）を鍵盤で押しても、手前（フォーカス）は
  body に落ちない（同じ物か、消えた物の代わりの札に戻る）
- 終わりの姿では、つまみの ← と ‹ がどちらも最後の歩へ行く
- run の一覧とログの押せる行は、支援技術に button と、開いているか（aria-expanded）を伝える

見た目（色と形）は縛らない（viewer/AGENTS.md の E25 の 4）。色の比は雛形の「比」の行を test_page.py が計る。
試験は小さな作りと run の記録を手で組み、src/page.py でページにする。playwright と Chromium が無ければ名前つきで見送る
（入れ方: uv run --isolated --extra viewer python3 -m playwright install chromium。回し方: uv run --isolated --extra viewer
python3 -m unittest tests.viewer.test_page_ui）。
"""
import tempfile
import unittest
from pathlib import Path

from viewer.src import page

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:   # 外のパッケージの宣言は pyproject.toml の extra viewer
    sync_playwright = None

# 直しの前の雛形でも同じ物を指す（直しが足した印 data-f・data-nest に頼らない）
WIRE = "#gtools label:has-text('配線も出す') input"
NEST_WORD = "#panel p button:has-text('の中')"
RUN = "11111111-0000-0000-0000-000000000000"
OTHER = "22222222-0000-0000-0000-000000000000"


def item(id_, deps, kind="script", **more):
    return {"id": id_, "path": [id_], "deps": deps, "kind": kind, "what": {"line": f"{id_} の 1 行"}, "with": {}, "outs": [], **more}


def event(node, start, end, stage, via=(), graph="line", through=False):
    return {"tokens": [node], "path": node, "run": RUN, "kind": "exec", "start": start, "end": end, "status": "ok", "loop": [],
            "cost": 0.0, "error": "", "at": {"graph": graph, "node": node, "via": list(via)}, "stage": stage, "role": "machine",
            "through": through}


def stage_sum(state, seconds):
    return {"state": state, "seconds": seconds, "wait": 0, "ai": 0, "rounds": 0, "turns": 0, "cost": 0}


def data() -> dict:
    """段 1（a と入れ子 nest）が走り、段 2（配線 w と b）は配線の w だけが走った（段は飛んだ）終わった run"""
    graphs = {
        "line": {"name": "works-factory-line", "kind": "graph", "nodes": 4, "desc": "", "inputs": [], "subs": ["inner"], "what": None,
                 "items": [item("a", []), item("nest", ["a"], "block", target="inner"), item("w", ["nest"]), item("b", ["w"])]},
        "inner": {"name": "works-factory-inner", "kind": "block", "nodes": 1, "desc": "", "inputs": [], "subs": [], "what": None,
                  "items": [item("x", [])]},
    }
    t = "2026-01-01T00:00:{:02d}.000Z".format
    events = [event("a", t(0), t(1), 1), event("x", t(2), t(3), 1, via=[{"graph": "line", "node": "nest"}], graph="inner"),
              event("w", t(4), t(5), 2, through=True)]
    run = {"id": RUN, "graph": "works-factory-line", "status": "completed", "live": False, "waiting": [], "started": t(0), "seconds": 6,
           "cost": 0, "children": [], "events": events, "skipped": [], "checks": [], "missing_logs": [], "unread": {}, "artifacts": {},
           "answer": "", "sessions": {}, "ai_cost": {}}
    row = {"id": RUN, "short": RUN[:8], "graph": "works-factory-line", "status": "completed", "waiting": [], "started": t(0),
           "seconds": 6, "cost": 0, "error": "", "outcome": ""}
    return {"made_at": "now", "commit": "", "target": "/target", "runs": [row, {**row, "id": OTHER, "short": OTHER[:8]}], "run": run,
            "shape_from": "run-copy", "unmatched": [], "texts": {}, "texts_ja": {}, "ja": {},
            "shape": {"graphs": graphs, "problems": []}, "waste": None,
            "stages": {"graph": "works-factory-line", "outcomes": {}, "loose": [], "stop": None, "stop_by": None, "stop_event": None,
                       "table": [{"name": "一", "line": "", "hands": "", "source": "", "nodes": ["a", "nest"], "wiring": []},
                                 {"name": "二", "line": "", "hands": "", "source": "", "nodes": ["w", "b"], "wiring": ["w"]}],
                       "run": [stage_sum("ok", 4), stage_sum("skipped", 0)]}}


@unittest.skipIf(sync_playwright is None, "playwright が無い（pyproject.toml の extra viewer）")
class PageUiCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.html = Path(cls.tmp.name) / "page.html"
        cls.html.write_text(page.render(data()), encoding="utf-8")
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except PlaywrightError as err:
            cls.pw.stop(); cls.tmp.cleanup()
            raise unittest.SkipTest(f"Chromium が無い（python3 -m playwright install chromium）: {str(err).splitlines()[0]}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.tmp.cleanup()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1400, "height": 900})
        self.page.set_default_timeout(5000)
        self.errors = []
        self.page.on("pageerror", lambda err: self.errors.append(str(err)))
        self.page.goto(self.html.as_uri())
        self.addCleanup(self.page.close)
        self.addCleanup(lambda: self.assertEqual(self.errors, []))

    def graph(self):
        self.page.click("[data-tab=graph]")

    def focused(self) -> str:
        """手前の物の札の鍵（札）か、道具の行の字（チェック）か、要素の名"""
        return self.page.evaluate("(() => { const a = document.activeElement;"
                                  " return a.dataset.key || (a.type === 'checkbox' ? a.parentElement.textContent.trim() : a.tagName); })()")

    def test_a_wiring_step_of_a_stage_that_did_not_run_shows_the_now_node(self):
        self.graph()
        self.page.check(WIRE)
        self.page.evaluate("go(STEPS.findIndex(s => s.e.path === 'w'))")
        self.assertEqual(self.page.evaluate("document.querySelector('#world .node.now')?.dataset.key ?? null"), "line/w")

    def test_the_panel_nest_word_follows_the_toggle(self):
        self.graph()
        self.page.click("#world [data-key='line/nest']")
        self.page.click("#world .nestbox button:has-text('詳しい面')")
        self.assertEqual(self.page.text_content(NEST_WORD), "inner の中を閉じる")
        self.page.click(NEST_WORD)
        self.assertEqual(self.page.locator("#world .nestbox").count(), 0)
        self.assertEqual(self.page.text_content(NEST_WORD), "inner の中をここで開く ＋")
        self.page.click(NEST_WORD)
        self.assertEqual(self.page.locator("#world .nestbox").count(), 1)
        self.assertEqual(self.page.text_content(NEST_WORD), "inner の中を閉じる")

    def test_keys_that_redraw_the_graph_keep_the_focus(self):
        self.graph()
        self.page.focus("#world [data-key='line/nest']")
        self.page.keyboard.press("Enter")
        self.assertEqual(self.focused(), "line/nest")
        self.page.focus("#world .nestbox .nh button.tw")
        self.page.keyboard.press("Enter")
        self.assertEqual(self.focused(), "line/nest")
        self.page.focus(WIRE)
        self.page.keyboard.press("Space")
        self.assertEqual(self.focused(), "配線も出す")
        self.page.keyboard.press("Space")
        self.page.focus("#world .row.folded button")
        self.page.keyboard.press("Enter")
        self.assertEqual(self.focused(), "line/b")

    def test_at_the_end_the_slider_left_and_the_back_button_go_to_the_last_step(self):
        self.graph()
        last = self.page.evaluate("STEPS.length - 1")
        self.page.focus("#p-pos")
        self.page.keyboard.press("ArrowLeft")
        self.assertEqual(self.page.evaluate("at"), last)
        self.page.click("#p-off")
        self.page.click("#p-prev")
        self.assertEqual(self.page.evaluate("at"), last)

    def test_pressable_rows_say_they_are_buttons_and_whether_they_are_open(self):
        self.page.click("[data-tab=log]")
        row = self.page.locator(".lgr").first
        self.assertEqual([row.get_attribute("role"), row.get_attribute("aria-expanded")], ["button", "false"])
        row.focus()
        self.page.keyboard.press("Enter")
        self.assertEqual(row.get_attribute("aria-expanded"), "true")
        self.page.click("[data-tab=runs]")
        rows = self.page.locator(".rr[role=button]")
        self.assertEqual(rows.count(), 2)
        rows.nth(0).click()
        rows.nth(1).click()
        self.assertEqual([rows.nth(i).get_attribute("aria-expanded") for i in range(2)], ["false", "true"])


if __name__ == "__main__":
    unittest.main()
