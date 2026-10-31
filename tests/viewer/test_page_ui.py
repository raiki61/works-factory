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
- 人が開いた入れ子を、再生の今が中に居る時に閉じると、その鎖を抜けるまで次の歩で開き直さない。今が外に居る時に閉じた物
  （札で閉じても「開いた入れ子を全部閉じる」でも）は、後で今が中へ入れば開く。今が中に居る時に「開いた入れ子を全部閉じる」を
  押した物も、次の歩で開き直さない
- 人が開いた二重の入れ子の外を閉じると、今が中に居る時は中の入れ子も開き直さず、今が外に居る時は後で今が中へ入れば開く
- 再生の歩で図を作り直しても、入れ子の中の札・二重の入れ子の中の札（外の入れ子の札へ順に上る）・入れ子の頭の「詳しい面」・
  線の select の手前は body に落ちない
- 札の板の後に「説明」を開くと選んだ札の印が消え、その札を中に持つ入れ子を閉じても graph の板は閉じない
- 再生の帯のボタン・板の ×・入れ子の頭の − は、読み上げの名が記号でない
- 流れの時間の帯は、鍵盤で押せ、帯の最初の絵の歩へ移る。帯に描く歩の無い段（配線の歩だけの段も）の帯は押せる物にしない
- 終わりの姿では、› と → は動かない。▶ は最初の歩から歩き始める
- 落ちた後に走り直して通った札は、終わりの姿でも最後の歩でも落ちたにせず、終わりの姿で「1 度落ちた」を添える
- 前に落ちた出来事の在る札で人が止めると、札は「ここで止めた」だけで、落ちたの縁を付けない
- 口 1（流れの段の箱 → 図と再生のその段の行）・口 2（図の板 → 流れの段の箱）・口 3（無駄の手がかりの行 → 図と再生のその手番の札と
  板の「LLM に入った物」）で移ると、頭の帯に戻る札が出て、押すと元の画面とスクロールに戻り、札が消える。口 2 から戻ると、根の graph・
  人が開いた入れ子の組・選んだ札が開き直る（流れで再生の位置を移した後も）。別の口で移ると戻り先が替わり、タブを押すと戻る札が消える
- 口 3 は根の graph を替えず、再生の位置をその手番の終わりの歩へ移し、その手番の入れ子を開いて札を選ぶ。「その結果を見る」は、板の
  「LLM に入った物」の中のその道具の結果の片を開く。戻っても再生の位置は移したまま
- 再生をやめて、選んでいた札が自動で開いた入れ子と一緒に消えても、板は閉じずに外の入れ子の札の中身に替わる
- 口を鍵盤で押して移り、戻る札を鍵盤で押して戻ると、手前（フォーカス）は移る前に押した口に戻る（口が作り直しで消えた時は、
  作り直した同じ口）。body に落ちない

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
    """段 1（a と入れ子 nest）が走り、段 2（配線 w と b）は配線の w だけが走った（段は飛んだ）終わった run。段 3（c）は出来事が無い。
    nest の中（inner）は x と入れ子 deep（leaf。中の z が走る）が走り、その後の入れ子 sub（leaf2）は走っていない"""
    graphs = {
        "line": {"name": "works-factory-line", "kind": "graph", "nodes": 5, "desc": "", "inputs": [], "subs": ["inner"], "what": None,
                 "items": [item("a", []), item("nest", ["a"], "block", target="inner"), item("w", ["nest"]), item("b", ["w"]),
                           item("c", ["b"])]},
        "inner": {"name": "works-factory-inner", "kind": "block", "nodes": 3, "desc": "", "inputs": [], "subs": ["leaf", "leaf2"],
                  "what": None,
                  "items": [item("x", []), item("deep", ["x"], "block", target="leaf"), item("sub", ["deep"], "block", target="leaf2")]},
        "leaf": {"name": "works-factory-leaf", "kind": "block", "nodes": 1, "desc": "", "inputs": [], "subs": [], "what": None,
                 "items": [item("z", [])]},
        "leaf2": {"name": "works-factory-leaf2", "kind": "block", "nodes": 1, "desc": "", "inputs": [], "subs": [], "what": None,
                  "items": [item("q", [])]},
        "outer": {"name": "works-factory-outer", "kind": "graph", "nodes": 1, "desc": "", "inputs": [], "subs": [], "what": None,
                  "items": [item("y", [])]},
    }
    t = "2026-01-01T00:00:{:02d}.000Z".format
    events = [event("a", t(0), t(1), 1), event("x", t(2), t(3), 1, via=[{"graph": "line", "node": "nest"}], graph="inner"),
              event("z", t(4), t(5), 1, via=[{"graph": "line", "node": "nest"}, {"graph": "inner", "node": "deep"}], graph="leaf"),
              event("w", t(6), t(7), 2, through=True)]
    run = {"id": RUN, "graph": "works-factory-line", "status": "completed", "live": False, "waiting": [], "started": t(0), "seconds": 8,
           "cost": 0, "children": [], "events": events, "skipped": [], "checks": [], "missing_logs": [], "unread": {}, "artifacts": {},
           "answer": "", "sessions": {}, "ai_cost": {}}
    row = {"id": RUN, "short": RUN[:8], "graph": "works-factory-line", "status": "completed", "waiting": [], "started": t(0),
           "seconds": 8, "cost": 0, "error": "", "outcome": ""}
    return {"made_at": "now", "commit": "", "target": "/target", "runs": [row, {**row, "id": OTHER, "short": OTHER[:8]}], "run": run,
            "shape_from": "run-copy", "unmatched": [], "texts": {}, "texts_ja": {}, "ja": {},
            "shape": {"graphs": graphs, "problems": []}, "waste": None,
            "stages": {"graph": "works-factory-line", "outcomes": {}, "loose": [], "stop": None, "stop_by": None, "stop_event": None,
                       "table": [{"name": "一", "line": "", "hands": "", "source": "", "nodes": ["a", "nest"], "wiring": []},
                                 {"name": "二", "line": "", "hands": "", "source": "", "nodes": ["w", "b"], "wiring": ["w"]},
                                 {"name": "三", "line": "", "hands": "", "source": "", "nodes": ["c"], "wiring": []}],
                       "run": [stage_sum("ok", 6), stage_sum("skipped", 0), stage_sum("skipped", 0)]}}


def fell_data(stop=False) -> dict:
    """data() の a の前に、同じ所（run・道・周）の落ちた出来事を足す。stop なら通った方の a で人が止めた run、でなければ通った方の a は
    落ちた後の走り直し（印 fell）"""
    d = data()
    run = d["run"]
    failed = {**event("a", "2026-01-01T00:00:00.000Z", "2026-01-01T00:00:00.400Z", 1), "status": "failed", "error": "boom"}
    again = {**run["events"][0], "start": "2026-01-01T00:00:00.500Z", **({} if stop else {"fell": True})}
    run["events"][0:1] = [failed, again]
    d["stages"]["run"][0]["fell"] = True
    if stop:
        run["status"] = "cancelled"
        d["stages"].update({"stop": 1, "stop_by": "human", "stop_event": 1})
    return d


def waste_data() -> dict:
    """data() の x を AI の手番（会話 s1。往復 0 で 2 万字の道具の結果を受け取る）にし、無駄の手がかりの数えを足した run"""
    d = data()
    x = d["run"]["events"][1]
    x.update({"kind": "agent", "session": "s1", "cost": 0.5, "role": "ai", "usage": {"input": 10, "output": 1, "cacheRead": 0, "cacheWrite": 0},
              "turns": 2})
    d["shape"]["graphs"]["inner"]["items"][0]["kind"] = "ai"
    d["texts"] = {"m0": "first", "m1": "{}", "m2": "x" * 20000, "m3": "small", "m4": "done"}
    d["run"]["sessions"] = {"s1": {"system": [], "tools": [], "inject": [], "recorded": {}, "cost": None, "unread": {},
                                   "seq": [["user", "m0"], ["turn", 0], ["call", "Read", "m1"], ["result", "m3", False], ["result", "m2", False],
                                           ["turn", 1], ["say", "m4"]],
                                   "turns": [{"usage": {}, "calls": []}, {"usage": {}, "calls": []}]}}
    big = {"session": "s1", "event": 1, "turn": 0, "name": "Read", "chars": 20000}
    d["waste"] = {
        "top": {"rows": [{"event": 1, "tokens": ["x"], "stage": 1, "cost": 0.5, "seconds": 1, "turns": 2, "replies": 2, "tokens4": None,
                          "share": 1}], "cost": 0.5, "odd": []},
        "time": {"run": 8, "wait": 0, "waits": [], "ai": 1, "machine": 3},
        "rounds": [], "idle": {"same": [], "empty": [], "unread": {"ran": [], "nodes": 0, "none": []}},
        "context": {"sessions": 1, "system": [], "tools": [], "inject": [], "pauses": [],
                    "cache": {"input": 10, "output": 1, "cacheRead": 0, "cacheWrite": 0, "read_share": 0}, "reads": {"files": 0, "again": []}},
        "big": {"line": 10000, "calls": 1, "results": [big], "climb": []}, "uncounted": []}
    return d


def band_data() -> dict:
    """data() の段 2 で、配線の w の後に b も走った run（段 2 の最初の歩は配線の歩）"""
    d = data()
    d["run"]["events"].append(event("b", "2026-01-01T00:00:08.000Z", "2026-01-01T00:00:09.000Z", 2))
    d["stages"]["run"][1] = stage_sum("ok", 3)
    return d


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

    def open(self, made: dict):
        html = Path(self.tmp.name) / f"{self.id().rsplit('.', 1)[-1]}.html"
        html.write_text(page.render(made), encoding="utf-8")
        self.page.goto(html.as_uri())

    def card(self, key) -> tuple[list, str]:
        el = self.page.locator(f"#world [data-key='{key}']")
        return sorted(el.get_attribute("class").split()), el.locator(".s").text_content()

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

    def test_a_nest_the_person_closed_while_the_replay_is_outside_opens_when_the_replay_goes_inside(self):
        self.graph()
        for close in ("#world [data-key='line/nest']", "#gtools button:has-text('開いた入れ子を全部閉じる')"):
            self.page.evaluate(f"go({self.step('a', end=True)})")
            self.page.click("#world [data-key='line/nest']")
            self.page.click(close)
            self.assertEqual(self.page.locator("#world .nestbox").count(), 0, close)
            self.page.evaluate(f"go({self.step('x')})")
            self.assertEqual(self.page.locator("#world .nestbox").count(), 1, close)

    def test_closing_all_while_the_replay_is_inside_keeps_the_nest_the_person_opened_closed(self):
        self.graph()
        self.page.evaluate(f"go({self.step('a', end=True)})")
        self.page.click("#world [data-key='line/nest']")
        self.page.evaluate(f"go({self.step('x')})")
        self.page.click("#gtools button:has-text('開いた入れ子を全部閉じる')")
        self.page.evaluate(f"go({self.step('x', end=True)})")
        self.assertEqual(self.page.locator("#world .nestbox").count(), 0)

    def test_closing_a_nest_shuts_the_inner_nest_the_person_opened_only_while_the_replay_is_inside(self):
        """deep を手で開いて nest を閉じる。今が中（z）なら、nest を手で開き直しても deep は開かない。
        今が外（a）なら、今が z へ入ると nest も deep も開く"""
        for where, then, boxes in (("z", "z", 1), ("a", None, 2)):
            self.page.reload()
            self.graph()
            self.page.evaluate(f"go({self.step('a', end=True)})")
            self.page.click("#world [data-key='line/nest']")
            self.page.click("#world [data-key='line/nest>inner/deep']")
            self.page.evaluate(f"go({self.step(where, end=where == 'a')})")
            self.page.click("#world [data-f='line/nest −']")
            if then:
                self.page.evaluate(f"go({self.step(then, end=True)})")
                self.page.click("#world [data-key='line/nest']")
            else:
                self.page.evaluate(f"go({self.step('z')})")
            self.assertEqual(self.page.locator("#world .nestbox").count(), boxes, where)

    def test_replay_steps_that_redraw_the_graph_keep_the_focus(self):
        self.graph()
        inside, outside = self.step("x"), self.step("a", end=True)
        for where, back in (("#world [data-key='line/nest>inner/x']", "line/nest"),
                            ("#world [data-key='line/nest>inner/deep>leaf/z']", "line/nest"),
                            ("#world .nestbox button:has-text('詳しい面')", "line/nest"),
                            ("#gtools select:has(option:has-text('線: 引かない'))", "SELECT")):
            self.page.evaluate(f"go({self.step('z') if 'leaf/z' in where else inside})")
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
        lane = self.page.locator("#f-band .lane[data-n='1']")
        self.assertEqual(lane.get_attribute("role"), "button")
        lane.focus()
        self.page.keyboard.press("Enter")
        self.assertEqual(self.page.evaluate("at"), self.step("a"))
        # 段 2 は配線の w だけが走り、帯に絵が無い。段 3 は歩が無い
        for n in ("2", "3"):
            empty = self.page.locator(f"#f-band .lane[data-n='{n}']")
            self.assertEqual([empty.get_attribute("role"), empty.get_attribute("tabindex"), empty.get_attribute("aria-label")],
                             [None, None, None], n)

    def test_the_time_band_lane_goes_to_the_first_drawn_step_not_a_wiring_step(self):
        self.open(band_data())
        self.page.click("[data-tab=flow]")
        self.page.locator("#f-band .lane[data-n='2']").focus()
        self.page.keyboard.press("Enter")
        self.assertEqual(self.page.evaluate("at"), self.step("b"))

    def test_at_the_end_next_and_the_right_key_do_not_move(self):
        self.graph()
        self.page.click("#p-next")
        self.assertEqual(self.page.evaluate("at"), -1)
        self.page.focus("#crumb button:has-text('説明')")
        self.page.keyboard.press("ArrowRight")
        self.assertEqual(self.page.evaluate("at"), -1)
        self.page.click("#p-play")
        self.page.wait_for_function("at === 0")
        self.page.click("#p-play")

    def test_a_node_that_failed_and_then_passed_is_not_shown_as_failed(self):
        self.open(fell_data())
        self.graph()
        classes, word = self.card("line/a")
        self.assertNotIn("fail", classes)
        self.assertIn("1 度落ちた", word)
        self.page.evaluate("go(STEPS.length - 1)")
        self.assertNotIn("fail", self.card("line/a")[0])

    def test_a_node_a_person_stopped_after_an_earlier_failure_says_only_stopped(self):
        self.open(fell_data(stop=True))
        self.graph()
        classes, word = self.card("line/a")
        self.assertIn("stopat", classes)
        self.assertNotIn("fail", classes)
        self.assertEqual(word, "ここで止めた")

    def back(self) -> str | None:
        """頭の帯の戻る札の字（出ていなければ None）"""
        return self.page.evaluate("$('backbar').hidden ? null : $('backbar').textContent")

    def tall(self):
        """流れと図が画面より長くなる高さにして、スクロールを戻すかを見られるようにする"""
        self.page.set_viewport_size({"width": 1400, "height": 360})

    def test_the_stage_box_gate_goes_to_the_stage_row_and_back(self):
        self.tall()
        self.page.evaluate("scrollTo(0, 200)")
        y = self.page.evaluate("scrollY")
        self.page.click("#f-stages .st[data-n='1']")
        self.assertEqual(self.page.evaluate("curTab"), "graph")
        self.assertIn("mark", self.page.get_attribute("#world .row[data-n='1']", "class"))
        self.assertEqual(self.back(), "← 流れへ戻る")
        self.page.click("#backbar button")
        self.assertEqual([self.page.evaluate("curTab"), self.page.evaluate("scrollY"), self.back()], ["flow", y, None])
        self.assertEqual(self.page.locator("#world .row.mark").count(), 0)

    def test_the_panel_gate_goes_to_the_stage_box_and_back_reopens_the_graph(self):
        self.tall()
        self.graph()
        self.page.click("#world [data-key='line/nest']")
        self.page.click("#world [data-key='line/nest>inner/x']")
        self.page.evaluate("scrollTo(0, 40)")
        y = self.page.evaluate("scrollY")
        self.page.click("#panel button:has-text('流れの地図で見る')")
        self.assertEqual(self.page.evaluate("curTab"), "flow")
        self.assertIn("mark", self.page.get_attribute("#f-stages .st[data-n='1']", "class"))
        self.assertEqual(self.back(), "← 図と再生へ戻る")
        # 流れで再生の位置を入れ子の外の歩へ移しても、戻ると選んだ札と人が開いた入れ子が開き直る
        self.page.locator("#f-band .lane[data-n='1']").focus()
        self.page.keyboard.press("Enter")
        self.page.click("#backbar button")
        self.assertEqual([self.page.evaluate("curTab"), self.page.evaluate("cur"), self.page.evaluate("selId"), self.back()],
                         ["graph", "line", "line/nest>inner/x", None])
        self.assertTrue(self.page.is_visible("#panel"))
        self.assertEqual(self.page.locator("#world .nestbox").count(), 1)
        self.assertEqual(self.page.evaluate("scrollY"), y)
        self.assertEqual(self.page.locator("#f-stages .st.mark").count(), 0)

    def test_another_gate_replaces_the_way_back_and_a_tab_drops_it(self):
        self.graph()
        self.page.click("#world [data-key='line/a']")
        self.page.click("#panel button:has-text('流れの地図で見る')")
        self.page.click("#f-stages .st[data-n='1']")
        self.assertEqual(self.back(), "← 流れへ戻る")
        self.page.click("#backbar button")
        self.assertEqual(self.page.evaluate("curTab"), "flow")
        self.page.click("#f-stages .st[data-n='1']")
        self.page.click("[data-tab=flow]")
        self.assertIsNone(self.back())

    def test_the_waste_gate_opens_the_turn_in_place_and_goes_back(self):
        self.open(waste_data())
        self.tall()
        self.page.click("[data-tab=waste]")
        self.page.evaluate("scrollTo(0, 100)")
        y = self.page.evaluate("scrollY")
        self.page.click("#waste .rank button:has-text('会話を見る')")
        self.assertEqual([self.page.evaluate("curTab"), self.page.evaluate("cur"), self.page.evaluate("at"), self.page.evaluate("selId")],
                         ["graph", "line", self.step("x", end=True), "line/nest>inner/x"])
        self.assertEqual(self.page.evaluate("[...AUTO]"), ["line/nest"])
        self.assertTrue(self.page.evaluate("$('panel').querySelector('.ev.focus details.llm').open"))
        self.assertEqual(self.back(), "← 無駄の手がかりへ戻る")
        self.page.click("#backbar button")
        self.assertEqual([self.page.evaluate("curTab"), self.page.evaluate("scrollY"), self.page.evaluate("at"), self.back()],
                         ["waste", y, self.step("x", end=True), None])

    def test_the_big_result_gate_opens_that_result_piece(self):
        self.open(waste_data())
        self.page.click("[data-tab=waste]")
        self.page.click("#waste summary:has-text('内訳と往復ごとの積み上がり')")
        self.page.click("#waste button:has-text('その結果を見る')")
        piece = self.page.locator("#panel details.focus")
        self.assertEqual(piece.count(), 1)
        self.assertTrue(piece.evaluate("el => el.open"))
        self.assertIn("20,000 字", piece.locator("summary").text_content())

    def test_stopping_the_replay_keeps_the_panel_on_the_outer_card(self):
        self.graph()
        self.page.evaluate(f"go({self.step('x')})")
        self.page.click("#world [data-key='line/nest>inner/x']")
        self.page.click("#p-off")
        self.assertEqual(self.page.locator("#world .nestbox").count(), 0)
        self.assertTrue(self.page.is_visible("#panel"))
        self.assertEqual(self.page.evaluate("selId"), "line/nest")

    def press_back(self):
        self.page.focus("#backbar button")
        self.page.keyboard.press("Enter")

    def test_going_back_returns_the_focus_to_the_gate(self):
        self.open(waste_data())
        # 口 1: 段の箱は戻る時に作り直されるので、作り直した同じ箱へ
        self.page.focus("#f-stages .st[data-n='1']")
        self.page.keyboard.press("Enter")
        self.press_back()
        self.assertEqual(self.page.evaluate("[curTab, document.activeElement.matches(\"#f-stages .st[data-n='1']\")]"), ["flow", True])
        # 口 2: 板は戻る時に作り直されるので、作り直した板の同じ口へ
        self.graph()
        self.page.click("#world [data-key='line/a']")
        self.page.focus("#panel button:has-text('流れの地図で見る')")
        self.page.keyboard.press("Enter")
        self.press_back()
        self.assertEqual(self.page.evaluate("[curTab, document.activeElement.textContent]"), ["graph", "段 1 一 · 流れの地図で見る →"])
        # 口 3
        self.page.click("[data-tab=waste]")
        self.page.focus("#waste .rank button:has-text('会話を見る')")
        self.page.keyboard.press("Enter")
        self.press_back()
        self.assertEqual(self.page.evaluate("[curTab, document.activeElement.textContent]"), ["waste", "会話を見る →"])


if __name__ == "__main__":
    unittest.main()
