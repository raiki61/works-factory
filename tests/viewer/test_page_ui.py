"""見る道具のページを画面の無い Chromium で開いて押す（viewer/page.tpl.html。docs/design/viewer.md の 6.5・6.7）。

- 「配線も出す」の時、走らなかった段の配線の歩でも、その段の行が開いて今の札が出る
- 板の入れ子の口の字（「<target> の中を閉じる」「<target> の中をここで開く ＋」）は、押した後の開け閉めに合う
- 図を作り直す操作（入れ子の札・入れ子の頭の −・道具の行のチェック・畳んだ段の「開く ＋」）を鍵盤で押しても、手前（フォーカス）は
  body に落ちない（同じ物か、消えた物の代わりの札に戻る）
- 図の道具の行の select（入れ子を探す・根の外の graph）と「⌂ に戻す」を鍵盤で使っても、手前は body に落ちない。板の「中で使う
  graph と block」の札を押しても板は閉じず、手前は押した札に残る
- 終わりの姿では、つまみの ← と ‹ がどちらも最後の歩へ行く
- つまみの読み上げの値（aria-valuetext）は、画面の「n / N」と、終わりの姿かを言う
- run の一覧とログの押せる行は、支援技術に button と、開いているか（aria-expanded）を伝える
- 「入れ子を探して開く」で走っていない層の畳みの中の札を選ぶと、畳みも開いて札が図に出る
- 人が開いた入れ子を、再生の今が中に居る時に閉じると、その鎖を抜けるまで次の歩で開き直さない
- 再生の歩で図を作り直しても、入れ子の中の札・入れ子の頭の「詳しい面」・線の select の手前は body に落ちない
- 札の板の後に「説明」を開くと選んだ札の印が消え、その札を中に持つ入れ子を閉じても graph の板は閉じない
- 再生の帯のボタン・板の ×・入れ子の頭の − は、読み上げの名が記号でない
- 流れの時間の帯は、鍵盤で押せる

見た目（色と形）は縛らない（viewer/AGENTS.md の E25 の 4）。
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
FIND = "#gtools select:has(option:has-text('入れ子を探して開く'))"
OUTER = "#gtools select:has(option:has-text('の外の graph'))"
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
    """段 1（a と入れ子 nest）が走り、段 2（配線 w と b）は配線の w だけが走った（段は飛んだ）終わった run。
    nest の中（inner）は x だけが走り、その後の入れ子 sub（leaf）は走っていない"""
    graphs = {
        "line": {"name": "works-factory-line", "kind": "graph", "nodes": 4, "desc": "", "inputs": [], "subs": ["inner"], "what": None,
                 "items": [item("a", []), item("nest", ["a"], "block", target="inner"), item("w", ["nest"]), item("b", ["w"])]},
        "inner": {"name": "works-factory-inner", "kind": "block", "nodes": 2, "desc": "", "inputs": [], "subs": ["leaf"], "what": None,
                  "items": [item("x", []), item("sub", ["x"], "block", target="leaf")]},
        "leaf": {"name": "works-factory-leaf", "kind": "block", "nodes": 1, "desc": "", "inputs": [], "subs": [], "what": None,
                 "items": [item("z", [])]},
        "outer": {"name": "works-factory-outer", "kind": "graph", "nodes": 1, "desc": "", "inputs": [], "subs": [], "what": None,
                  "items": [item("y", [])]},
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

    def test_the_tool_row_and_the_panel_chips_keep_the_focus(self):
        self.graph()
        self.page.focus(FIND)
        self.page.select_option(FIND, "line/nest")
        self.assertTrue(self.page.locator(FIND).evaluate("el => el === document.activeElement"))
        self.page.focus(OUTER)
        self.page.select_option(OUTER, "outer")
        self.assertTrue(self.page.locator(OUTER).evaluate("el => el === document.activeElement"))
        self.page.focus("#crumb button:has-text('に戻す')")
        self.page.keyboard.press("Enter")
        self.assertEqual(self.page.evaluate("cur"), "line")
        self.assertNotEqual(self.focused(), "BODY")
        self.page.focus("#crumb button:has-text('説明')")
        self.page.keyboard.press("Enter")
        self.page.click("#panel summary:has-text('中で使う')")
        self.page.focus("#panel .chip:has-text('inner')")
        self.page.keyboard.press("Enter")
        self.assertTrue(self.page.is_visible("#panel"))
        self.assertEqual(self.page.evaluate("document.activeElement.textContent"), "inner")

    def test_the_slider_reads_out_the_step_on_screen_and_the_end(self):
        n = self.page.evaluate("STEPS.length")
        self.assertIn("終わりの姿", self.page.get_attribute("#p-pos", "aria-valuetext") or "")
        self.page.evaluate("go(0)")
        self.assertIn(f"1 / {n}", self.page.get_attribute("#p-pos", "aria-valuetext") or "")
        self.page.evaluate(f"go({n - 1})")
        self.assertIn(f"{n} / {n}", self.page.get_attribute("#p-pos", "aria-valuetext"))
        self.assertNotIn("終わりの姿", self.page.get_attribute("#p-pos", "aria-valuetext"))

    def test_at_the_end_the_slider_left_and_the_back_button_go_to_the_last_step(self):
        self.graph()
        last = self.page.evaluate("STEPS.length - 1")
        self.page.focus("#p-pos")
        self.page.keyboard.press("ArrowLeft")
        self.assertEqual(self.page.evaluate("at"), last)
        self.page.click("#p-off")
        self.page.click("#p-prev")
        self.assertEqual(self.page.evaluate("at"), last)
        # 歩の途中からつまみを右の端へ戻すと、終わりの姿（at が -1）
        self.page.evaluate("go(0)")
        self.page.evaluate("(() => { const p = $('p-pos'); p.value = p.max; p.dispatchEvent(new Event('input')); })()")
        self.assertEqual(self.page.evaluate("at"), -1)

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

    def step(self, path, end=False) -> int:
        return self.page.evaluate(f"STEPS.findIndex(s => s.e.path === '{path}' && s.end === {'true' if end else 'false'})")

    def test_finding_a_nest_inside_a_folded_idle_layer_shows_it(self):
        self.graph()
        self.page.focus(FIND)
        self.page.select_option(FIND, "line/nest>inner/sub")
        self.assertEqual(self.page.locator("#world [data-key='line/nest>inner/sub']").count(), 1)

    def test_a_nest_the_person_opened_and_closed_while_the_replay_is_inside_stays_closed(self):
        self.graph()
        self.page.click("#world [data-key='line/nest']")
        self.page.evaluate(f"go({self.step('x')})")
        self.page.click("#world .nestbox .nh button.tw")
        self.page.evaluate(f"go({self.step('x', end=True)})")
        self.assertEqual(self.page.locator("#world .nestbox").count(), 0)

    def test_replay_steps_that_redraw_the_graph_keep_the_focus(self):
        self.graph()
        inside, outside = self.step("x"), self.step("a", end=True)
        for where, back in (("#world [data-key='line/nest>inner/x']", "line/nest"),
                            ("#world .nestbox button:has-text('詳しい面')", "line/nest"),
                            ("#gtools select:has(option:has-text('線: 引かない'))", "SELECT")):
            self.page.evaluate(f"go({inside})")
            self.page.focus(where)
            self.page.evaluate(f"go({outside})")
            self.assertEqual(self.focused(), back, where)

    def test_explaining_the_graph_after_a_node_panel_drops_the_selection(self):
        self.graph()
        self.page.click("#world [data-key='line/nest']")
        self.page.click("#world [data-key='line/nest>inner/x']")
        self.page.click("#crumb button:has-text('説明')")
        self.assertEqual(self.page.locator("#world .sel").count(), 0)
        self.page.click("#world [data-key='line/nest']")
        self.assertTrue(self.page.is_visible("#panel"))

    def test_symbol_buttons_have_names(self):
        self.graph()
        for name in ("1 歩戻る（←）", "再生する（空白）", "1 歩進む（→）", "再生をやめて run の終わりの姿へ"):
            self.assertEqual(self.page.get_by_role("button", name=name, exact=True).count(), 1, name)
        self.page.click("#p-play")
        self.assertEqual(self.page.get_by_role("button", name="止める（空白）", exact=True).count(), 1)
        self.page.click("#p-play")
        self.page.click("#world [data-key='line/nest']")
        self.assertEqual(self.page.get_by_role("button", name="inner の中を閉じる", exact=True).count(), 1)
        self.page.click("#world [data-key='line/a']")
        self.assertEqual(self.page.get_by_role("button", name="板を閉じる", exact=True).count(), 1)

    def test_the_time_band_lanes_can_be_pressed_with_keys(self):
        self.page.click("[data-tab=flow]")
        lane = self.page.locator("#f-band .lane[data-n='2']")
        self.assertEqual(lane.get_attribute("role"), "button")
        lane.focus()
        self.page.keyboard.press("Enter")
        self.assertEqual(self.page.evaluate("at"), self.step("w"))


if __name__ == "__main__":
    unittest.main()
