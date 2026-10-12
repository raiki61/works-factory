"""修正の決まりの正本（workflows/fix/commands/fix-rules/common.md）と、2 つの修正役の指示書の組み立て（lib/fixrules.py。裁定 R65）の検査。

- 決まりの正本は 1 つ: 直す役（fix-prep が組む）と TDD の輪の役（tdd-prep が組む）の両方の指示書が、正本の節をそのまま含む
- 本線から来た決まりの句が正本に在る・「プロジェクトのテストを回せ」の文は RUN_TESTS と一字違わず（直した単位に絞る）・
  変更の種類ごとの直の証拠（決定 C8）が在る
- 節を機械が選ぶ: 本線の核（直し方・守ること）はいつも、証拠の節は単位のファイルと差分に在る種類だけ、TDD の段の約束は今の段だけ
- 指示書は決まりを全部載せた 1 つの形（prompt_file）。どの節を載せたか・なぜかは 1 行目の見出しに在る
- 組み立ては機械だけ（AI を通さない）で、同じ入力からはバイト単位で同じ。値の穴は全部埋まる
- 指示書に人の方針の文書と依頼の文のファイルを載せ、無い時は無いと 1 行ずつ書く
盤面・子のプロセスは使わない（組み立ての関数を直に呼ぶ）。決まりの文の本体は workflows/fix/commands/fix-rules/ に在り、scripts と
同じく import の後に fixrules・rulebook の置き場の名を置き替える。
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

import fixboard  # noqa: E402
import fixrules  # noqa: E402
import rulebook  # noqa: E402

ROOT = LIB.parent
FR = ROOT / "workflows" / "fix" / "commands" / "fix-rules"
# scripts が import の後にする置き替えと同じ（lib/ の字に決まりの置き場のパスを書かない）
rulebook.CANON = FR / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = FR
fixrules.PROMPT_DIRS = frozenset({"commands", "prompts", "agents", "skills", "rules", FR.name})

SHARED = FR / "common.md"
# 本線（graphloops の p3.fix.md）から来た決まりの句。正本に在り、両方の指示書に届く
MAINLINE = ("根本の単位ごとに直せ", "同じ形を全部直せ", "直す前に既製の物で済まないかを確かめろ", "動きを変えたら",
            "テストを消すな・緩めるな", "git commit` するな")
# 書く役の試験の回し方（直した単位に絞る。一式は線の最後のテストの段が回す。裁定 c1-1 で書き換えた文）
RUN_TESTS = ("- **プロジェクトのテストを回せ。** 直した単位に当たる試験だけを絞って回せ（実行器の絞り方——試験の id か名前"
             "で絞る。絞り方はリポジトリの `run.sh`・テストの置き場から探す）。テストの実行器が在る run では、受け付け（"
             "返答を受け取って確かめる機械）が版からの変更に当たる試験を選んで回し、元で赤でなかった試験が赤なら返答を拒み、落ちた試験"
             "を書いた拒否の理由のファイルを、この役を次に起こす時の指示書の頭で名指す（この役が書くファイルではない）——自分で回すな"
             "ら同じく変えたファイルに当たる試験を選べ。リポジトリのテスト一式は原則としてメイングラフの最後のテストの段が回すので、役"
             "は回さない。例外は 1 つで、絞る手（試験の id か名前で選ぶ方法）がリポジトリに無い時だけ、返答の直前に一式を 1 "
             "回だけ回せ。赤が残るなら、どの単位のどこかを直してから出せ。Python は `PYTHONDONTWRITEBYTEC"
             "ODE=1` を立てて回せ。git が無視する生成物（`__pycache__` など）のうち、この役が起きる前に無かっ"
             "た物は後のノードが消す（消した物は人に見せる）。")
VALUES = {"judgment_file": "/b/out/r1/p2.diagnose.json", "open_units": '["a: 分母", "b: 上限"]', "plan_file": "/b/out/r1/p2.fix_plan.json",
          "policy_path": "", "notes_file": "/b/r1/notes.md", "summary_file": "/b/tdd-1/summary.md"}
PHASE_TEXT = "## この段ですること\n\n今の単位だけを直せ。\n\n## 返す JSON\n\n{\"phase\": \"fix\"}"
TITLE = "# TDD の輪の指示書（2 回目・段 fix）"
CORE_IDS = ("core-fix", "core-keep")
KIND_BULLET = {"docs": "- 文書:", "prompts": "- 指示書（プロンプト）:", "config": "- 設定・YAML・workflow:", "code": "- 注記・型:"}
PHASE_BULLET = {"route": "- **route**:", "test": "- **test**:", "fix": "- **fix**:", "refactor": "- **refactor**:"}


def shared_lines():
    return [ln for ln in SHARED.read_text(encoding="utf-8").splitlines() if not fixrules.MARK.match(ln)]


def tdd_values():
    return {k: VALUES[k] for k in fixrules.TDD_VALUES}


def header(text):
    first = text.split("\n", 1)[0]
    assert first.startswith("<!-- works-prompt ") and first.endswith(" -->"), first
    return json.loads(first[len("<!-- works-prompt "):-len(" -->")])


class TestSharedSource(unittest.TestCase):
    def test_source_is_the_one_file(self):
        """正本の全部の節を繋ぐと、ファイルから節の印の行を除いた字そのもの（節で切っても文は変えない）"""
        self.assertEqual(fixrules.shared(), "\n".join(shared_lines()).strip("\n"))
        self.assertEqual(list(fixrules.sections(fixrules.SHARED)),
                         ["core-fix", "evidence", "evidence-docs", "evidence-prompts", "evidence-config", "evidence-code",
                          "core-conflict", "core-keep"])

    def test_conflict_rule_in_both_prompts_and_ruler(self):
        """食い違いの申し出（持ち主 2026-09-28）: 正本の core-conflict の決まりの文が、組んだ修正役・TDD の輪の役の指示書の両方に
        いつも載る（種類を選ばない時も）。裁定役の指示書は持ち主の決まり（principles.md）の全文と返す JSON の形を持つ"""
        rule = "緑にするためにテスト・依頼・コードのどれかを曲げるくらいなら、食い違いとして返せ"
        self.assertIn(rule, fixrules.sections(fixrules.SHARED)["core-conflict"])
        self.assertEqual(sum(ln.count(rule) for ln in shared_lines()), 1, "正本に 1 か所だけ")
        for text in (fixrules.fix_prompt(VALUES, kinds={}),
                     fixrules.tdd_prompt({k: VALUES[k] for k in fixrules.TDD_VALUES}, "route", "## 今の段", title="# t", kinds={})):
            self.assertIn(rule, text)
        ruler = fixrules.ruler_prompt({"conflicts_file": "/b/r1/conflicts.json", "ids": "c1-1", "judgment_file": "/b/j.json",
                                       "request_file": "", "policy_path": ""})
        self.assertIn(fixrules.sections(fixrules.PRINCIPLES)["principles"], ruler)
        for w in ("`c1-1`", "`/b/r1/conflicts.json`", "fix_test_scope", "fix_code_as", "ask_human", "裁定の決まり"):
            self.assertIn(w, ruler)

    def test_questions_for_the_human_go_to_the_conflict_exit(self):
        """人への問い・人にしか決められない疑いは食い違いの出口（which_is_right unknown → 裁定役 → ask_human）へ、rejudge_requested は
        判定のフレーミングへの異議だけ（finaltests の懸念 1: 読み替えが人への問いを rejudge_requested に書かせ、判定への異議と
        混ぜていた。包み無しの run はそこで再審できずに止まる）。組んだ修正役・TDD の輪の役の指示書の両方が言い、正本と読み替えと
        README に、問い・疑い・方針のぶつかりを rejudge_requested へ送る文が残らない"""
        ask = "人に聞きたいこと・人にしか決められない疑いの行き先はここ"
        only = "`rejudge_requested` は判定のフレーミング（単位の切り方・根の見立て・disposition）への異議だけの欄"
        sec = fixrules.sections(fixrules.SHARED)
        self.assertIn(ask, sec["core-conflict"])
        self.assertIn(only, sec["core-fix"])
        self.assertIn("`which_is_right` を unknown", sec["core-conflict"])
        old = re.compile(r"(疑い|疑いの理由|何が要るか|ぶつかるか|人に聞きたいこと)(は|を)\s*`rejudge_requested`\s*に書")
        prompts = {"fix": fixrules.fix_prompt(VALUES, kinds={}),
                   "tdd": fixrules.tdd_prompt({k: VALUES[k] for k in fixrules.TDD_VALUES}, "fix", "## 今の段", title="# t", kinds={})}
        for name, text in prompts.items():
            with self.subTest(name):
                self.assertIn(ask, text)
                self.assertIn(only, text)
                self.assertEqual(old.findall(text), [])

    def test_handoff_to_a_human_goes_to_the_routed_fields(self):
        """人に回す物（書き換えない方針の文書の食い違い・壊すと分かって通す物）は breaks.accepted に書く——機械が人に見せる一覧に
        載せる欄（実の利用者の run 97fd532f: plan_faces を absorbed と答えて how に「人に回す」と書いた食い違いが人に届かなかった）。
        決まりは組んだ修正役・TDD の輪の役の指示書の両方に載り、plan_faces の答え方の行も breaks.accepted を名指す"""
        rule = "人に回す物は `breaks.accepted` に書け。"
        sec = fixrules.sections(fixrules.SHARED)
        self.assertIn(rule, sec["core-fix"])
        self.assertEqual(sum(ln.count(rule) for ln in shared_lines()), 1, "正本に 1 か所だけ")
        line = next(ln for ln in shared_lines() if rule in ln)
        for w in ("方針の文書", "人に見せる一覧", "人に届かない"):
            self.assertIn(w, line)
        for text in (fixrules.fix_prompt(VALUES, kinds={}),
                     fixrules.tdd_prompt({k: VALUES[k] for k in fixrules.TDD_VALUES}, "fix", "## 今の段", title="# t", kinds={})):
            self.assertIn(rule, text)
        # plan_faces は直す役の返答だけの欄なので、その答え方は直す役の決まり（返答の欄の節）に置く
        faces = next(ln for ln in (FR / "direct.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- `plan_faces`:"))
        for w in ("人には届かない", "`breaks.accepted`"):
            self.assertIn(w, faces)

    def test_every_rules_file_is_cut_into_sections(self):
        for name, ids in ((fixrules.DIRECT, ["fix-head", "fix-keep", "fix-ask", "fix-ask-sub", "fix-consult-resume", "fix-overflow-queued", "fix-overflow-resume", "fix-lane", "fix-reply"]), (fixrules.RULER, ["ruler-head", "ruler-reply"]),
                          (fixrules.PRINCIPLES, ["principles"]), (fixrules.BRIEF, ["brief-canon"]),
                          (fixrules.TDD, ["tdd-head", "tdd-remap", "tdd-phase", *(f"tdd-phase-{p}" for p in fixrules.PHASES),
                                          "tdd-phase-all", "tdd-end", "tdd-lane"])):
            with self.subTest(name):
                self.assertEqual(list(fixrules.sections(name)), ids)

    def test_mainline_phrases_in_the_core(self):
        core = "\n".join(fixrules.sections(fixrules.SHARED)[i] for i in CORE_IDS)
        for phrase in MAINLINE:
            with self.subTest(phrase):
                self.assertIn(phrase, core)

    def test_run_tests_sentence_kept(self):
        self.assertEqual([ln for ln in shared_lines() if "プロジェクトのテストを回せ" in ln], [RUN_TESTS])

    def test_direct_evidence_by_change_kind(self):
        """決定 C8: 先にテストを書けない直しの証拠を、変更の種類ごとに（文書・指示書・設定・注記と型）1 節ずつ"""
        sec = fixrules.sections(fixrules.SHARED)
        for kind, words in (("docs", ("パス", "リンク", "冷読")), ("prompts", ("描いて", "写し", "次の run")),
                            ("config", ("validate", "check.sh")), ("code", ("静的な検査",))):
            with self.subTest(kind):
                self.assertTrue(sec[f"evidence-{kind}"].startswith(KIND_BULLET[kind]))
                self.assertNotIn("\n", sec[f"evidence-{kind}"])
                for w in words:
                    self.assertIn(w, sec[f"evidence-{kind}"])

    def test_owed_routing_and_policy_once(self):
        body = shared_lines()
        self.assertEqual(len([ln for ln in body if ln.startswith("- **義務の単位の行き先**: ")]), 1)
        self.assertEqual(len([ln for ln in body if ln.startswith("- 人の方針に反するもの")]), 1)

class TestCompose(unittest.TestCase):
    def fix(self, **kw):
        return fixrules.fix_prompt(VALUES, **kw)

    def tdd(self, phase="fix", **kw):
        return fixrules.tdd_prompt(tdd_values(), phase, PHASE_TEXT, title=TITLE, **kw)

    def test_brief_rule_reaches_fixer_and_tdd_only(self):
        """brief の決まり（brief-canon）は修正役と TDD の役の頭の次にだけ載る。裁定役と手直しの役には載せない"""
        fix = [pid for pid, _, _ in fixrules.fix_parts(VALUES)]
        tdd = [pid for pid, _, _ in fixrules.tdd_parts(tdd_values())]
        self.assertEqual(fix[fix.index("fix-head") + 1], "brief-canon")
        self.assertEqual(tdd[tdd.index("tdd-head") + 1], "brief-canon")
        ruler = [pid for pid, _, _ in fixrules.ruler_parts({k: "/b/x" for k in fixrules.RULER_VALUES})]
        self.assertNotIn("brief-canon", ruler)

    def test_brief_rule_wins_and_names_the_exit(self):
        """brief が要求の正本で判定は背景。誤りと見たら食い違いの申し出で返し、rewrite_tests は最後の人の関所に並ぶ。
        brief の無い run は判定のファイルが正本のまま"""
        sec = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        for w in ("要求の正本", "brief が勝つ", "背景", "食い違いの申し出", "rewrite_tests", "最後の承認ノード", "判定のファイルが正本"):
            self.assertIn(w, sec)

    def test_brief_rule_one_voice_with_brief_background(self):
        """brief と判定が食い違えば brief どおり直す（止めない）。brief そのものを誤りと見た時だけ申し出る。brief のファイルの背景の
        見出し（planbrief.BACKGROUND）も同じ 1 つの決まりを言う"""
        import planbrief
        sec = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        self.assertIn("brief が勝つ", planbrief.BACKGROUND)
        self.assertIn("brief が誤りと見たら申し出よ", planbrief.BACKGROUND)
        self.assertNotIn("自分で解かずに", planbrief.BACKGROUND)
        self.assertIn("単位の切り方（unit）は判定どおり。何をどう直すかは brief", sec)

    def test_brief_rule_names_ruling_and_range_exit(self):
        """裁定を受けた単位は裁定の範囲で brief に勝つ。範囲の申し出の which_is_right の決め方を言う"""
        sec = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        self.assertIn("裁定を受けた単位は、裁定の範囲で裁定が brief に勝つ", sec)
        self.assertIn("範囲の外が要るなら request", sec)
        self.assertIn("query（`correct_lines` 付き）", sec)

    def test_population_query_hitting_right_members_goes_to_the_query_exit(self):
        """population の問いがもう正しい物（直さなくてよい物）にも当たる単位も、query の申し出で問いの置き換えを裁かせる
        （canary の large の run a2fcf33a: 公開関数の全部を数えた問いで、docstring を足す正しい直しが閉じなかった）。
        correct_lines には直さなくてよい物の行を写し、remaining では閉じない、を正本（core-conflict）と brief の決まりの両方が言う"""
        conflict_sec = fixrules.sections(fixrules.SHARED)["core-conflict"]
        for w in ("`population`", "直さなくてよい（もう正しい）物にも当たる", "`correct_lines` にはその直さなくてよい物の行",
                  "`remaining` に書いても閉じない"):
            with self.subTest(w):
                self.assertIn(w, conflict_sec)
        brief = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        self.assertIn("`population` の問いが直さなくてよい物にも当たる", brief)
        # 裁定役が同じ形を replace_query に裁ける（検査を狭める裁きとして ask_human に倒さない）。決まりと返す形の両方が言う
        ruler = fixrules.ruler_prompt({"conflicts_file": "/b/r1/conflicts.json", "ids": "c1-1", "judgment_file": "/b/j.json",
                                       "request_file": "", "policy_path": ""})
        principles = fixrules.sections(fixrules.PRINCIPLES)["principles"]
        for text in (principles, ruler):
            with self.subTest(len(text)):
                self.assertIn("直さなくてよい（もう正しい）物にも当たる", text)
                self.assertIn("検査を狭める裁きではない", text)

    def test_brief_rule_asks_before_scope_needed(self):
        """数え直しが範囲の外を求める時も、範囲の相談の節が在れば申し出の前に相談する（run 249・249b。相談の控えが在ったのに
        申し出の道だけが選ばれた）"""
        sec = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        rule2 = sec[sec.index("2. **"):sec.index("3. **")]
        self.assertIn("8 のとおり先に相談", rule2)
        self.assertLess(rule2.index("8 のとおり先に相談"), rule2.index("`scope_needed`"))

    def test_brief_rule_names_scope(self):
        """brief の allowed_paths の外と out_of_scope は変えない。範囲の外が要るなら食い違いの申し出で返す（依頼 218）"""
        sec = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        for w in ("allowed_paths", "out_of_scope", "範囲の外", "食い違いの申し出"):
            self.assertIn(w, sec)

    def test_rewrite_tests_is_an_exception_to_frozen_tests(self):
        """修正役の頭の「テストのファイルは変えるな」の例外に、修正案の rewrite_tests の名指しが並ぶ"""
        head = fixrules.sections(fixrules.DIRECT)["fix-head"]
        self.assertIn("修正案の `rewrite_tests` の名指しと、裁定 fix_test_scope の範囲だけは例外", head)

    def test_judgment_is_background_in_heads(self):
        """修正役・TDD の役の頭の判定のファイルの行は「全部読め」でなく背景"""
        for name, sid in ((fixrules.DIRECT, "fix-head"), (fixrules.TDD, "tdd-head")):
            line = next(ln for ln in fixrules.sections(name)[sid].splitlines() if "<<judgment_file>>" in ln)
            self.assertNotIn("全部読め", line)
            self.assertIn("背景", line)

    def test_both_prompts_carry_the_shared_source(self):
        """種類を選ばない組み立て（全部の種類）では、正本の全文がそのまま両方に入る"""
        body = fixrules.shared()
        self.assertIn(body, self.fix())
        self.assertIn(body, self.tdd())

    def test_core_always_even_without_kinds(self):
        sec = fixrules.sections(fixrules.SHARED)
        for text in (self.fix(kinds={}), self.tdd(kinds={})):
            for i in CORE_IDS:
                self.assertIn(sec[i], text)
            self.assertNotIn(sec["evidence"], text)
            for b in KIND_BULLET.values():
                self.assertNotIn(b, text)

    def test_evidence_only_for_present_kinds(self):
        kinds = {"code": "判定 stats.py", "config": "差分 a.yaml"}
        for text in (self.fix(kinds=kinds), self.tdd(kinds=kinds)):
            for k, b in KIND_BULLET.items():
                (self.assertIn if k in kinds else self.assertNotIn)(b, text)
            got = {s["id"]: s for s in header(text)["sections"]}
            self.assertEqual(got["evidence-code"]["why"], "判定 stats.py", "選んだ理由（機械の事実）が見出しに在る")
            self.assertNotIn("evidence-docs", got)

    def test_tdd_lane_render_carries_three_phases_and_lane_overrides(self):
        """並べの枝の単位の決まりのファイル（docs/plans/2026-10-07-lane-nodes.md）: 輪の役の決まりの全文・test・fix・refactor の
        約束・枝の役の読み替え（tdd-lane。cwd は単位の worktree・回ごとの指示書は別のファイル）・機械の節。振り分けの段の約束と、
        下請け・段のコマンドの語は載らない（並べは工程の節で、役は JSON を返す）"""
        text = fixrules.tdd_lane_render(tdd_values(), "## この単位の決まり（機械が書いた）", title=TITLE)
        for p, b in PHASE_BULLET.items():
            (self.assertIn if p in fixrules.LANE_PHASES else self.assertNotIn)(b, text)
        for s in ("## 並べの枝の役の読み替え", "## このループでの読み替え", "## この単位の決まり（機械が書いた）", TITLE, "cwd（単位の worktree）",
                  "回ごとの指示書"):
            self.assertIn(s, text)
        for s in ("段のコマンド", "まとめ役", "Agent で起こした"):
            self.assertNotIn(s, text)
        self.assertNotIn("lanes", fixrules.PHASES, "並べの周は輪の役の段でない（枝の輪が回す）")

    def test_tdd_phase_rules_only_for_the_current_phase(self):
        for phase in fixrules.PHASES:
            with self.subTest(phase):
                text = self.tdd(phase=phase)
                for p, b in PHASE_BULLET.items():
                    (self.assertIn if p == phase else self.assertNotIn)(b, text)
                self.assertIn("- この後の単位や direct の単位には", text)

    def test_path_specific_rules(self):
        fix, tdd = self.fix(), self.tdd()
        for s in ("## 修正ごとに書くこと", "## 周の全体に書くこと", "何も変えずに「済んだ」と言うな", "`plan_faces`", "`wrote_refs`"):
            self.assertIn(s, fix)
            self.assertNotIn(s, tdd)
        for s in ("## 今の段の約束", "## このループでの読み替え", "JUnit XML の書き先は作業ツリーの外", PHASE_TEXT, TITLE):
            self.assertIn(s, tdd)
            self.assertNotIn(s, fix)
        self.assertEqual(tdd.split("\n")[1], TITLE, "見出しの次が題")
        self.assertLess(tdd.index(fixrules.shared()), tdd.index(PHASE_TEXT), "今の段は決まりの後（末尾）")
        self.assertIn("- 作業ツリーの外（ホームや /tmp の設定など）を書き換えない。\n- 何も変えずに", fix, "守ることの箇条に続ける")

    def test_run_values_fill_every_hole(self):
        fix, tdd = self.fix(), self.tdd()
        for text in (fix, tdd):
            self.assertNotIn("<<", text)
            self.assertNotIn("$INPUTS", text)
            self.assertNotIn("$LOOP_PREV", text)
            self.assertNotIn("{{", text)
            self.assertNotIn("<!-- 節", text)
        for k in fixrules.FIX_VALUES:
            if VALUES[k]:
                self.assertIn(f"`{VALUES[k]}`", fix, k)
        for k in fixrules.TDD_VALUES:
            if VALUES[k]:
                self.assertIn(f"`{VALUES[k]}`", tdd, k)
        self.assertIn(f"人の方針の文書: {fixrules.EMPTY}", fix, "空の値は空と書く")

    def test_missing_value_is_an_error(self):
        with self.assertRaises(fixrules.Unfilled):
            fixrules.fix_prompt({k: v for k, v in VALUES.items() if k != "plan_file"})
        with self.assertRaises(fixrules.Unfilled):
            fixrules.fill("a <<nope>> b", {})

    def test_values_are_not_rescanned(self):
        """値の中の <<…>>・$… は字のまま（埋めた値をもう一度穴として読まない）"""
        odd = {**VALUES, "notes_file": "/x/<<plan_file>>/$INPUTS.plan_file"}
        self.assertIn("`/x/<<plan_file>>/$INPUTS.plan_file`", fixrules.fix_prompt(odd))

    def test_same_inputs_same_bytes(self):
        self.assertEqual(self.fix().encode(), self.fix().encode())
        self.assertEqual(self.fix().encode(), fixrules.fix_prompt(dict(reversed(list(VALUES.items())))).encode())
        self.assertEqual(self.tdd().encode(), self.tdd().encode())
        self.assertEqual(self.fix(reject_file="/b/r-1.txt").encode(), self.fix(reject_file="/b/r-1.txt").encode())
        self.assertNotEqual(self.fix(), fixrules.fix_prompt({**VALUES, "plan_file": "/other"}))

    def test_reject_line_after_the_header(self):
        """前の回の拒否の理由はファイルのパスで、見出しの次の 1 行（fixboard.REJECT_LINE。元 rolekit と同じ文。理由の文は貼らない。R44）"""
        got = self.fix(reject_file="/b/reject-accept_fix-2.txt")
        self.assertEqual(got.split("\n")[1], fixboard.REJECT_LINE.format(path="/b/reject-accept_fix-2.txt"))
        self.assertNotIn("拒まれた", self.fix())

    def test_tdd_reason_on_top(self):
        got = self.tdd(reason="- 名指しのテストが落ちない")
        head = got.split(fixrules.shared())[0]
        self.assertIn("- 名指しのテストが落ちない", head)

    def test_header_records_sections_and_why(self):
        h = header(self.fix(kinds={"code": "判定 stats.py"}))
        self.assertEqual((h["role"], h["iteration"]), ("fix", 1))
        self.assertEqual([s["id"] for s in h["sections"]],
                         ["fix-head", "brief-canon", "core-fix", "evidence", "evidence-code", "core-conflict", "core-keep",
                          "fix-keep", "fix-reply"])
        self.assertTrue(all(s["why"] for s in h["sections"]))
        self.assertEqual(len(h["rules_sha"]), 64)

    def test_tdd_brief_after_title_before_reason(self):
        """TDD の役の指示書の頭: 題 → brief の節 → 前の回に拒んだ理由"""
        text = fixrules.tdd_prompt(tdd_values(), "fix", PHASE_TEXT, title=TITLE, reason="R", brief="## 要求の正本（brief）\n\nX")
        self.assertLess(text.index(TITLE), text.index("## 要求の正本（brief）"))
        self.assertLess(text.index("## 要求の正本（brief）"), text.index("前の回の返答を機械が拒んだ理由"))


class TestWritePrompt(unittest.TestCase):
    """支度の節が書く指示書（決まりを全部）と、この輪で渡した証拠の種類と回の控え（<名>.delivered.json）"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = pathlib.Path(self._tmp.name)
        judgment = self.dir / "judgment.json"
        judgment.write_text(json.dumps({"units": [
            {"key": "stats.py mean: 分母", "class_query": {"how": {"paths": ["stats.py"]}}},
            {"key": "README.md: 古い説明", "class_query": {"how": {"paths": ["docs/*.md"]}}},
            {"key": "defer.yaml: 後回し"}]}, ensure_ascii=False), encoding="utf-8")
        self.values = {**VALUES, "judgment_file": str(judgment),
                       "open_units": json.dumps(["stats.py mean: 分母", "README.md: 古い説明"], ensure_ascii=False)}
        self.prompt = self.dir / "prompt-p3.fix.md"

    def write(self, n, reject=""):
        def build(kinds):
            return fixrules.render("fix", n, fixrules.fix_parts(self.values, kinds), reject_file=reject)
        fixrules.write_prompt(self.prompt, None, self.values, build, n)
        return self.prompt.read_text(encoding="utf-8")

    def test_first_iteration_writes_the_whole_prompt_only(self):
        text = self.write(1)
        self.assertIn(fixrules.sections(fixrules.SHARED)["core-fix"], text)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         ["judgment.json", "prompt-p3.fix.delivered.json", "prompt-p3.fix.md"], "全文版・差分版の控えを書かない")
        ledger = json.loads(fixrules.beside(self.prompt, fixrules.DELIVERED).read_text(encoding="utf-8"))
        self.assertEqual(ledger, {"kinds": ["code", "docs"], "iterations": [1]})

    def test_kinds_from_open_units_only(self):
        """判定の義務の単位のパス（class_query の paths と key の中のパス）から種類を選ぶ。義務でない単位（defer）は見ない"""
        text = self.write(1)
        self.assertIn(KIND_BULLET["code"], text)
        self.assertIn(KIND_BULLET["docs"], text)
        self.assertNotIn(KIND_BULLET["config"], text)
        self.assertNotIn(KIND_BULLET["prompts"], text)
        why = {s["id"]: s["why"] for s in header(text)["sections"]}
        self.assertIn("stats.py", why["evidence-code"])

    def test_second_iteration_is_whole_and_keeps_kinds(self):
        self.write(1)
        self.values["open_units"] = json.dumps(["stats.py mean: 分母"], ensure_ascii=False)
        text = self.write(2, reject="/b/reject-accept_fix-1.txt")
        self.assertIn(fixboard.REJECT_LINE.format(path="/b/reject-accept_fix-1.txt"), text)
        self.assertIn(fixrules.sections(fixrules.SHARED)["core-fix"], text, "毎回全部")
        self.assertIn(KIND_BULLET["docs"], text, "この輪で前に渡した種類は減らさない")
        self.assertEqual(fixrules.iteration_next(self.prompt), 3)

    def test_unknown_kinds_fall_back_to_all(self):
        self.values["judgment_file"] = str(self.dir / "missing.json")
        text = self.write(1)
        for b in KIND_BULLET.values():
            self.assertIn(b, text)
        self.assertTrue(all("全部載せる" in s["why"] for s in header(text)["sections"] if s["id"].startswith("evidence-")))


class TestKinds(unittest.TestCase):
    def test_kind_of(self):
        for path, kind in (("README.md", "docs"), ("docs/guide.rst", "docs"), ("blk-x/commands/fix.md", "prompts"),
                           ("CLAUDE.md", "prompts"), ("skills/a/SKILL.md", "prompts"), ("a/b.yaml", "config"),
                           (".github/workflows/ci.yml", "config"), ("pyproject.toml", "config"), ("stats.py", "code"),
                           ("src/x.ts", "code"), ("*.py", "code"), ("docs/**", None), ("LICENSE", None)):
            with self.subTest(path):
                self.assertEqual(fixrules.kind_of(path), kind)

    def test_canon_is_a_prompt(self):
        """正本の置き場を移しても、正本を直す run の証拠は指示書の節（描いて穴が埋まる・写しが揃う）のまま"""
        self.assertEqual(fixrules.kind_of(str(SHARED.relative_to(ROOT.parent))), "prompts")

    def test_select_kinds_names_the_source(self):
        got = fixrules.select_kinds({"判定": ["stats.py"], "差分": ["README.md", "stats.py"]})
        self.assertEqual(set(got), {"code", "docs"})
        self.assertIn("判定 stats.py", got["code"])
        self.assertIn("差分 README.md", got["docs"])
        self.assertEqual(set(fixrules.select_kinds({"判定": ["LICENSE"], "差分": []})), set(fixrules.KINDS))


class TestQueryConflictExit(unittest.TestCase):
    """判定者の問い（class_query）が直した後の正しい形にも当たる、と申し出る出口（which_is_right: query。直した後の正しい行を
    correct_lines に写す）と、問いを置き換える裁定（replace_query。新しい問いを hits・misses と申し出の correct_lines で機械が試す）。
    盤面は使わない（conflict.problems と ruling.problems を直に呼ぶ）"""

    KEY = "stats.py clamp: 上限を超えた値に lo を返す"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        (self.repo / "stats.py").write_text("def clamp(x, lo, hi):\n    if x > hi:\n        return lo\n    return x\n",
                                            encoding="utf-8")
        (self.repo / "test_stats.py").write_text("def test_clamp():\n    assert clamp(11, 0, 10) == 10\n", encoding="utf-8")

    def item(self, **extra):
        return {"unit_key": self.KEY, "between": ["stats.py:3", "test_stats.py:2"],
                "why_both_cannot_hold": "判定者の問い return lo は下限の枝の正しい return lo にも当たり、直しても件数が減らない",
                "which_is_right": "query", "kind": "query_hits_fixed", **extra}

    def test_query_conflict_needs_correct_lines(self):
        import conflict
        self.assertIn("query", conflict.WHICH)
        errs = conflict.problems([self.item()], repo=self.repo, board_dir=self.repo, owed={self.KEY})
        self.assertTrue(any("correct_lines" in e for e in errs), errs)

LANG = "人が読む文の欄（reason・how・what・why など）は English で書け。"   # 呼び手が渡す言語の 1 行（見本）


class TestLangLine(unittest.TestCase):
    """書く役（修正・TDD の輪・裁定）の文は関所と報告に字のまま載るので、支度が取った言語の 1 行（引数 lang。呼び手が始めの記録から
    組む）を、どの形でも指示書の末尾に置く。見出しの次の 1 行（拒否・裁定のファイル・題）は動かさない"""
    LINE = LANG

    def test_every_writer_prompt_ends_with_the_lang_line(self):
        fix = rulebook.render("fix", 1, fixrules.fix_parts(VALUES), reject_file="/b/r-1.txt", lang=self.LINE)["text"]
        tdd = fixrules.tdd_render(tdd_values(), "fix", PHASE_TEXT, title=TITLE, lang=self.LINE)["text"]
        rule = fixrules.ruler_prompt({k: "/b/x" for k in fixrules.RULER_VALUES}, lang=self.LINE)
        for name, text in (("fix", fix), ("tdd", tdd), ("rule", rule)):
            with self.subTest(name):
                self.assertTrue(text.endswith(self.LINE + "\n"), text[-200:])
        self.assertEqual(fix.split("\n")[1], fixboard.REJECT_LINE.format(path="/b/r-1.txt"))
        self.assertEqual(tdd.split("\n")[1], TITLE)

    def test_no_lang_no_line(self):
        """lang が空なら置かない。置いても本文はそのまま"""
        plain = rulebook.render("fix", 1, fixrules.fix_parts(VALUES))["text"]
        self.assertNotIn("English", plain)
        got = rulebook.render("fix", 1, fixrules.fix_parts(VALUES), lang=self.LINE)["text"]
        self.assertEqual(got, plain.rstrip("\n") + "\n\n" + self.LINE + "\n")


class TestPrepOwedValues(unittest.TestCase):
    def test_open_units_value_is_the_fix_duty_owed(self):
        """指示書の <<open_units>> は受け付けと同じ fixboard.fix_duty の owed: 判定の並びを保ち、答え待ちの単位は載せず、
        関所で答えて戻った単位を後ろに足す（直す義務 owed・問いの台帳の値は呼び手が渡す）"""
        from unittest import mock
        back = "c.py back: 関所で答えて戻した単位"
        with mock.patch.object(fixrules.fixboard, "fix_duty", return_value=({"b: 上限", back}, {"a: 分母": "答え待ちの問い q"})) as duty:
            got = fixrules.owed_values("/b/place", VALUES, owed={"a: 分母", "b: 上限", back}, withheld_by={"a: 分母": "q"})
        self.assertEqual(json.loads(got["open_units"]), ["b: 上限", back])
        self.assertEqual({k: v for k, v in got.items() if k != "open_units"}, {k: v for k, v in VALUES.items() if k != "open_units"})
        self.assertEqual(duty.call_args.args, ("/b/place", {"a: 分母", "b: 上限", back}))
        self.assertEqual(duty.call_args.kwargs, {"withheld_by": {"a: 分母": "q"}, "returned": ()})

    def test_prep_reads_the_duty_before_it_builds_the_prompt(self):
        src = (LIB / "fixrules.py").read_text(encoding="utf-8")
        self.assertLess(src.index("values = owed_values(b, values, owed=owed"), src.index("docs = lib_section(b, repo, values, shared)"))


class TestBriefCanonEdges(unittest.TestCase):
    """brief の決まり（brief-canon）の端: 人が関所で付けた条件との強さの順と、指示書の頭の節の見出しとの重なり"""

    def test_gate_notes_win_over_brief(self):
        """修正の前に人が答えた条件（notes_file）は brief に勝つ。brief が条件を超えれば条件どおりに直し、超えた所は申し出で返す。
        決まりの文は「関所」の語を使わない（ブロックはほかの段を知らない。test の BLOCK_KNOWN の数え）"""
        sec = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        self.assertIn("修正の前に人が答えた条件（notes_file）は brief に勝つ", sec)
        self.assertIn("brief が条件を超えれば条件どおりに直し、超えた所は食い違いの申し出で返す", sec)

    def test_rule_heading_does_not_overlap_brief_head(self):
        """決まりの節の見出しは、指示書の頭の brief の節の見出し（planbrief.HEAD）を含まない。READ_ALL は決まりの節の名を名指す"""
        import planbrief
        sec = fixrules.sections(fixrules.BRIEF)["brief-canon"]
        self.assertNotIn(planbrief.HEAD, sec)
        heading = next(ln for ln in sec.splitlines() if ln.startswith("## "))
        self.assertIn(f"『{heading[3:]}』", planbrief.READ_ALL)
        for name, sid in ((fixrules.DIRECT, "fix-head"), (fixrules.TDD, "tdd-head")):
            line = next(ln for ln in fixrules.sections(name)[sid].splitlines() if "<<judgment_file>>" in ln)
            self.assertIn(f"「{heading[3:]}」", line)


class TestSeatParts(unittest.TestCase):
    """借りたスキルの座（seat.section の文）は、渡された時だけ節 seat として載る（修正の形 g3。計画 220 Task 2）。
    修正役の座の型の穴の値は implementer_values が盤面と run の値から組む"""

    def test_seat_part_only_when_given(self):
        tdd = [pid for pid, _, _ in fixrules.tdd_parts(tdd_values(), seat="S")]
        self.assertEqual(tdd[tdd.index("tdd-remap") + 1], "seat")
        fix = [pid for pid, _, _ in fixrules.fix_parts(VALUES, seat="S")]
        self.assertEqual(fix[fix.index("fix-reply") - 1], "seat")
        self.assertNotIn("seat", [pid for pid, _, _ in fixrules.fix_parts(VALUES)])
        self.assertNotIn("seat", [pid for pid, _, _ in fixrules.tdd_parts(tdd_values())])

    def test_prompts_pass_the_seat_through(self):
        self.assertIn("座の文 S", fixrules.fix_prompt(VALUES, seat="座の文 S"))
        self.assertIn("座の文 S", fixrules.tdd_prompt(tdd_values(), "fix", PHASE_TEXT, title=TITLE, seat="座の文 S"))
        self.assertEqual(fixrules.fix_prompt(VALUES), fixrules.fix_prompt(VALUES, seat=""))

class LanesAndItemsCase(unittest.TestCase):
    """修正役の並べの枝の結末（置き場の fix-lanes-out.json・fix-lanes.md）の読み口と、承認済みの項目の範囲（item_ranges）。
    置き場 b は fix の run の置き場のフォルダ（元の盤面の b.work(<名>) は置き場の <名>）"""

    ROWS = [{"item": 1, "unit_keys": ["a: 分母"], "file": "/b/r1/brief-1.md", "sha256": "0" * 64},
            {"item": 2, "unit_keys": ["b: 上限", "c: 外"], "file": "/b/r1/brief-2.md", "sha256": "1" * 64}]

    def place(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return pathlib.Path(tmp.name)

    def test_overlap_line_names_what_the_lanes_merged(self):
        """出し直しの指示書の頭の 1 行は、修正役の並べの枝の締めが記録に残した重なりのファイルと、それを変えた当てた項目を名指す"""
        b = self.place()
        self.assertEqual(fixrules.overlap_line(b), "", "枝の結末が無ければ空")
        rec = b / fixrules.LANES_RECORD
        rec.write_text(json.dumps({"items": [], "shared": []}), encoding="utf-8")
        self.assertEqual(fixrules.overlap_line(b), "", "重なりのファイルが無ければ空")
        rec.write_text(json.dumps({"shared": ["report.py"], "items": [
            {"item": 1, "outcome": "merged", "files": ["report.py"], "changed": ["a"]},
            {"item": 2, "outcome": "merged", "files": ["report.py", "x.py"], "changed": ["b"]},
            {"item": 3, "outcome": "merged", "files": ["y.py"], "changed": ["c"]},
            {"item": 4, "outcome": "serial", "files": [], "changed": []}]}), encoding="utf-8")
        self.assertEqual(fixrules.overlap_line(b), fixrules.OVERLAP_LINE.format(items="1・2", files="report.py"))
        self.assertEqual(fixrules.lanes_merged(b), {"a", "b", "c"}, "当てた項目の直した単位だけ（戻した項目の単位は直す義務のまま）")

    def test_lanes_text_names_the_summary_only_when_the_lanes_ran(self):
        b = self.place()
        self.assertEqual(fixrules.lanes_text(b), "")
        (b / fixrules.LANES_RECORD).write_text(json.dumps({"items": []}), encoding="utf-8")
        self.assertEqual(fixrules.lanes_text(b), "", "本文が無ければ載せない")
        (b / fixrules.LANES_SUMMARY).write_text("# 結末\n", encoding="utf-8")
        text = fixrules.lanes_text(b)
        self.assertIn(str(b / fixrules.LANES_SUMMARY), text)
        self.assertIn("下請けを起こさず", text)
        parts = fixrules.fix_parts(VALUES, lanes=text)
        self.assertEqual([p[0] for p in parts][:3], ["fix-head", "brief-canon", "lanes"], "節 lanes は brief の後")

    def test_item_ranges_read_allowed_paths_and_tests(self):
        """承認済みの項目は値か口で受ける（元は盤面の planmarks.approved_items(b)）。口が控えの壊れを出せば {}"""
        items = [{"item": 1, "allowed_paths": ["a/*.py"], "tests": [{"id": "tests/test_a.py::test_x"}]}, {"item": 2}]
        self.assertEqual(fixrules.item_ranges(items), {1: ["a/*.py", "tests/test_a.py"], 2: None})
        self.assertEqual(fixrules.item_ranges(lambda: items), {1: ["a/*.py", "tests/test_a.py"], 2: None})
        self.assertEqual(fixrules.item_ranges(None), {})

        def broken():
            raise fixrules.planmarks.FieldsBroken("欄の控えが凍結の印と違う")
        self.assertEqual(fixrules.item_ranges(broken), {})
        self.assertEqual(fixrules.test_files(items, [1]), ["tests/test_a.py"])
        self.assertEqual(fixrules.test_files(broken, [1]), [])

    def test_unit_note_is_shared_with_head_text(self):
        import planbrief
        self.assertEqual(planbrief.unit_note(["a", "b"], ["a"]), f"a・{planbrief.NOT_NOW}: b")
        self.assertEqual(planbrief.unit_note(["a", "b"]), "a、b")
        self.assertEqual(planbrief.unit_note(["b"], ["a"]), f"{planbrief.NONE}・{planbrief.NOT_NOW}: b")
        self.assertIn(f"単位 {planbrief.unit_note(['b: 上限', 'c: 外'], ['b: 上限'])}）",
                      planbrief.head_text(self.ROWS[1:], ["b: 上限"]))

    def test_seat_reason_names_no_shape(self):
        """座の節の理由の文は消した修正の形の語を名指さない（修正役と TDD の輪の役で同じ文）"""
        fix = {pid: why for pid, _, why in fixrules.fix_parts(VALUES, seat="S")}["seat"]
        tdd = {pid: why for pid, _, why in fixrules.tdd_parts(tdd_values(), seat="S")}["seat"]
        self.assertEqual((fix, tdd), ("いつも（座）", "いつも（座）"))

    def test_dispatched_leaves_out_green_units(self):
        self.assertEqual(fixrules.dispatched(["a", "b", "c"], {"b"}), ["a", "c"])


class AskPlanPartsCase(unittest.TestCase):
    """範囲の相談と事前の確かめ（設計 docs/plans/2026-10-06-ask-planner.md）: 相談の控えが在る時だけ、修正役の節 ask（返答の欄
    consult で相談し、事前の確かめのコマンドを走らせる）を載せる"""

    def test_ask_part_only_when_given(self):
        fix = [pid for pid, _, _ in fixrules.fix_parts(VALUES, ask="相談の節 A")]
        self.assertLess(fix.index("ask"), fix.index("fix-reply"))
        self.assertNotIn("ask", [pid for pid, _, _ in fixrules.fix_parts(VALUES)])

    def test_ask_text_names_the_reply_field_and_the_check(self):
        text = fixrules.ask_text("/rp/fixing/consult/consult.json", "/py/bin/python3")
        for w in ("/py/bin/python3", "factchecks.py", "/rp/fixing/consult/consult.json", "--reply", "`consult`", "`item`",
                  "`paths`", "`tests`", "`why`"):
            self.assertIn(w, text)
        for w in ("askplan", "--item", "--why"):
            self.assertNotIn(w, text, "相談は返答の欄で（役の Bash から相談のコマンドを走らせない）")

    def test_ask_items_carry_ranges(self):
        import consult
        it = {"item": 2, "unit_keys": ["b: 上限"], "allowed_paths": ["stats.py"],
              "out_of_scope": [{"glob": "legacy.py", "why": "古い"}],
              "tests": [{"id": "test_stats.py::TestStats::test_a"}], "rewrite_tests": []}
        self.assertEqual(consult.items_doc([it]), {"2": {"unit_keys": ["b: 上限"], "allowed_paths": ["stats.py"],
                                                         "out_of_scope": [{"glob": "legacy.py", "why": "古い"}],
                                                         "tests": ["test_stats.py"]}},
                         "out_of_scope は外した理由も持つ（答えの節の指示書が引いて考え直させる）")

    def test_ask_config_writes_the_place_and_needs_items(self):
        """相談の控えは置き場に書く（元は盤面の承認済みの項目を読み、run ごとの置き場へ書いた）。相談の相手の印が空・項目が無い run は
        書かない。波及の一覧のパスが在れば修正役の節の終わりに名指す"""
        import consult
        it = {"item": 1, "unit_keys": ["a: 分母"], "allowed_paths": ["stats.py"], "tests": []}
        with tempfile.TemporaryDirectory() as d:
            place = pathlib.Path(d)
            vals = {**VALUES, "plan_session": "plan", "base_rev": "abc", "ripple_file": "/b/ripple.md"}
            self.assertEqual(fixrules.ask_config(place, place, {**vals, "plan_session": ""}, "first", items=[it]), ("", ""))
            self.assertEqual(fixrules.ask_config(place, place, vals, "first", items=None), ("", ""))
            self.assertFalse((place / consult.CONFIG).exists())
            main, sub = fixrules.ask_config(place, place, vals, "first", items=[it])
            doc = json.loads((place / consult.CONFIG).read_text(encoding="utf-8"))
            self.assertEqual((doc["board"], doc["pass"], doc["base_rev"]), (str(place), "first", "abc"))
            self.assertEqual(doc["items"], consult.items_doc([it]))
            self.assertIn(str(place / consult.CONFIG), main)
            self.assertIn("/b/ripple.md", main)
            self.assertIn(str(place / consult.CONFIG), sub)


class StartValuesCase(unittest.TestCase):
    """始めの記録の値（人の方針の文書 policy_path と依頼の文のファイル request_file）を指示書に載せる。欄が無い・空の時は
    「人の方針の文書は無い」「依頼の文のファイルは無い」と 1 行ずつ書く（黙って抜かない。計画 fix の指示書に始めの記録の値を差し込む所）"""

    def test_empty_values_say_none(self):
        for text in (fixrules.fix_prompt(VALUES), fixrules.tdd_prompt(tdd_values(), "fix", PHASE_TEXT, title=TITLE),
                     fixrules.ruler_prompt({k: "" for k in fixrules.RULER_VALUES})):
            with self.subTest(text[:40]):
                self.assertIn(fixrules.NO_POLICY_LINE, text.splitlines())
                self.assertIn(fixrules.NO_REQUEST_LINE, text.splitlines())

    def test_given_values_are_named(self):
        vals = {**VALUES, "policy_path": "/s/policy.md", "request_file": "/s/request.md"}
        text = fixrules.fix_prompt(vals)
        self.assertIn(fixrules.POLICY_LINE.format(path="/s/policy.md"), text)
        self.assertIn(fixrules.REQUEST_LINE.format(path="/s/request.md"), text)
        self.assertNotIn(fixrules.NO_POLICY_LINE, text)
        self.assertNotIn(fixrules.NO_REQUEST_LINE, text)
        self.assertEqual(fixrules.start_lines({}), [fixrules.NO_POLICY_LINE, fixrules.NO_REQUEST_LINE])
        self.assertEqual(fixrules.start_lines({"policy_path": "  ", "request_file": None}),
                         [fixrules.NO_POLICY_LINE, fixrules.NO_REQUEST_LINE])

    def test_lines_sit_after_the_title_and_before_the_rules(self):
        text = fixrules.tdd_prompt(tdd_values(), "fix", PHASE_TEXT, title=TITLE, reason="- R")
        self.assertEqual(text.split("\n")[1], TITLE)
        self.assertLess(text.index("- R"), text.index(fixrules.NO_POLICY_LINE))
        self.assertLess(text.index(fixrules.NO_REQUEST_LINE), text.index(fixrules.shared()))


class PrepCase(unittest.TestCase):
    """節 fix-prep・fix-ruled-prep の中身（fixrules.prep）を置き場で回す（元は盤面が p3.fix を待っているかを見て起こした印を置いた。
    印と待ちの確かめは実行基盤の輪が持つので外した）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.place = pathlib.Path(tmp.name) / "fix"
        self.place.mkdir()
        self.vals = {**VALUES, "open_units": json.dumps(["a: 分母", "b: 上限"], ensure_ascii=False)}

    def prep(self, pass_="first", **kw):
        return fixrules.prep(self.place, None, self.vals, pass_, owed={"a: 分母", "b: 上限"}, **kw)

    def test_first_prompt_and_iterations(self):
        got = self.prep(lang=LANG)
        path = pathlib.Path(got["prompt_file"])
        self.assertEqual((path, got["iteration"]), (self.place / fixrules.PROMPT_NAME, 1))
        text = path.read_text(encoding="utf-8")
        self.assertIn(fixrules.sections(fixrules.SHARED)["core-fix"], text)
        self.assertTrue(text.endswith(LANG + "\n"))
        self.assertIn(fixrules.NO_POLICY_LINE, text)
        again = self.prep(reject_file="/b/reject-1.txt")
        self.assertEqual(again["iteration"], 2)
        self.assertEqual(path.read_text(encoding="utf-8").split("\n")[1], fixboard.REJECT_LINE.format(path="/b/reject-1.txt"))

    def test_ruled_pass_names_the_rulings_file_and_counts_apart(self):
        rulings = self.place / fixrules.conflict.RULINGS_FILE
        rulings.write_text("# 裁定\n", encoding="utf-8")
        got = self.prep("ruled", reject_file="/b/reject-1.txt")
        self.assertEqual(pathlib.Path(got["prompt_file"]).name, fixrules.PROMPT_NAME[:-len(".md")] + fixrules.RULED_TAIL)
        self.assertEqual(got["iteration"], 1)
        text = pathlib.Path(got["prompt_file"]).read_text(encoding="utf-8")
        self.assertEqual(text.split("\n")[1], fixrules.RULINGS_LINE.format(path=rulings), "裁定の後の 1 回目は拒否でなく裁定の文")

    def test_unknown_pass_and_broken_briefs(self):
        with self.assertRaises(fixrules.Unfilled):
            self.prep("third")
        from unittest import mock
        with mock.patch.object(fixrules.planbrief, "cut", side_effect=fixrules.planbrief.LedgerBroken("控えが違う")):
            with self.assertRaises(ValueError) as e:
                self.prep()
        self.assertIn(fixrules.BRIEF_BROKEN, str(e.exception))
        self.assertFalse((self.place / fixrules.PROMPT_NAME).exists(), "指示書を書かない")

    def test_resume_and_overflow_write_beside_the_place(self):
        path = self.place / fixrules.PROMPT_NAME
        got = fixrules.resume(self.place, path, {"answer_file": "/b/a.md", "left": 3, "turn": 1}, "first", lang=LANG)
        self.assertEqual(got, self.place / fixrules.RESUME_FILE.format(pass_="first", turn=1))
        self.assertTrue(got.read_text(encoding="utf-8").endswith(LANG + "\n"))
        got = fixrules.overflow_queued(self.place, path, "first")
        self.assertEqual(got, self.place / fixrules.OVERFLOW_QUEUED_FILE.format(pass_="first"))
        self.assertIn(str(path), got.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
