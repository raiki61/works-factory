"""報告の本文のブロック（workflows/report-write/。書き手のループ）の試験。

- YAML の形: PyYAML で読み、Archon を起こさない（返す節の約束の欄・入力・役の節の鍵）
- 役の指示書: 元の works の指示書の文に台帳の直しだけを当てた写し
- script: reject.py・cold_prep.py・report_accept.py・written.py を子のプロセスで走らせる（一時の ARTIFACTS_DIR と環境変数。
  Archon を起こさない。test_report.Run を使う）
- 筋書き: tests/archon.py の使い捨ての木で fixtures/ を archon workflow test で回す。Archon の源か bun が無ければ名前つきで見送る
"""
import json
import pathlib
import re
import unittest

import yaml

from tests import archon
from tests.workflows.copied import assert_is_original, rewritten
from tests.workflows.test_report import RUN, Run

import gatemarks  # noqa: E402  test_report が lib/ を sys.path に足す
import handoff  # noqa: E402
import launchgroups  # noqa: E402
import report_roles  # noqa: E402
import rolekit  # noqa: E402
import runreport  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "report-write"
WRITE_SCRIPTS = BLOCK / "scripts"
WORKFLOW = yaml.safe_load((BLOCK / "works-factory-report-write.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in WORKFLOW["nodes"]}
BODY = {n["id"]: n for n in NODES["write-loop"]["loop_group"]["nodes"]}
INPUTS = ("facts_file", "outcome", "stop_reason", "lang_line")
SANDBOX = {"enabled": True, "allowUnsandboxedCommands": False}
TOP_KEYS_DROPPED_ON_INCLUDE = ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout")

# 役の指示書の元: 今の works（raiki61/claude-plugins の 2aa7c66cf7abe1fe09699ac2942d107123214168）の works/blk-report/commands/ の
# 2 本の sha256 と、許した直し（元の字, 写しの字, 訳）。元に無い字の差し込みは前後の元の字を錨にした組にする
REPORT_EDITS = [
    ("1. まず指示書 `$report-write-prep.output.prompt_file` を Read で読み、その指示に従え。記録の置き場・問いの台帳・根本の単位・盤面の状態・検証器の結果・"
     "判定者の生の返答は全部そこに在る（graphloops の最終報告の指示書を、この run の盤面の値で描いた物）。\n"
     "2. 数の出どころは `$report-write-prep.output.facts_file`（盤面から機械が組んだ事実。線 A の機械の報告が在ればそれ）。これも Read で読め。報告に書く数"
     "は、このファイルに在る物はこのファイルと同じ値にしろ。このファイルは報告の最後に機械がそのまま付けるので、同じ一覧を本文に並べ直さない。本文はその事実の上に、何が起きたか・何を決めればよいかを足す。\n"
     "3. 指示書の頭に「前の回の受け付けが拒んだ理由」の節が在れば、お前の前の返答は受け付けで拒まれている。そこに書かれた理由のところを直した本文を丸ごと出し直せ（直した所だけを返すな）。1 回目にはこの"
     "節は無い。\n"
     "4. お前は読むだけの役。道具は Read・Grep・Glob と web を引く WebSearch・WebFetch だけで、作業ツリーを 1 文字も変えてはいけない（受け付けは、起こす前に取った"
     "作業ツリーの写しと今を比べ、変わっていれば拒む）。\n"
     "5. 報告の 1 行目の来歴（ライン・run の番号・周・graph と表の版）は機械が刻む。自分で書き写すな。この行は冒頭 3 行に数えない。\n",
     "この run の結末の語は **$facts.output.outcome**（止めた段と理由の語: `$facts.output.stop_reason`）。機械が決めた語で、書き換えない。\n"
     "\n"
     "1. まず機械の事実のファイル `$ARTIFACTS_DIR/$facts.output.facts_file` を Read で読め（ブロックの返りと run の記録から機械が組んだ報告。結末・止"
     "めた段・人が決めることの件数・段ごとの結末・TDD の単位の行・緑の認証・独立の目・費用が在る）。その「5. 見る所」に並ぶファイル（判定・目的・計画・事前審査・独立設計・差分・試験の記録・直した後の"
     "構造ほか）も、書く節ごとに要る物を Read で読め。\n"
     "2. 報告に書く数は、機械の事実のファイルに在る物はそのファイルと同じ値にしろ。そのファイルに無い数を書くなら、どのファイルのどの欄から数えたかを添えろ。このファイルは報告の最後に機械がそのまま付ける"
     "ので、同じ一覧を本文に並べ直さない。本文はその事実の上に、何が起きたか・何を決めればよいかを足す。\n"
     "3. 前の回の拒否の訳のファイルの、run の置き場からの相対のパス（無ければ空）: `$write-reject.output.reason`。空でなければ、お前の前の返答は受け付けで拒まれている。"
     "そのファイル（`$ARTIFACTS_DIR/` の下のそのパス）を Read で読み、書かれた理由のところを直した本文を丸ごと出し直せ（直した所だけを返すな）。1 回目は空。\n"
     "4. お前は読むだけの役。道具は Read・Grep・Glob と web を引く WebSearch・WebFetch だけで、作業ツリーを 1 文字も変えてはいけない（変えれば実行基盤がこの節を落"
     "とす）。\n"
     "5. 報告の 1 行目の来歴（工程・run の番号・周・工程の版）は機械が刻む。自分で書き写すな。この行は冒頭 3 行に数えない。\n",
     "盤面の指示書（report-write-prep）が無いので、結末の語と機械の事実のファイル・拒否の訳のファイルを名指す"),
    ("\n"
     "## 書式の決まり（読み手のための決まり。指示書と食い違う所はこちらを採る）\n",
     "\n"
     "## 構成（読む所は上の機械の事実のファイルと、そこに並ぶファイル）\n"
     "\n"
     "報告は依頼の言語で書く。ファイルの中身が違う言語でも揃える（コード識別子・パス・エラー文はそのまま）。\n"
     "\n"
     "1. **冒頭 3 行は「人が決めること」だけ**——機械の事実の「1. 人が決めること」に並ぶ物（修正前の問い・独立の目 R4 の問い・保留にしたままの問い・人に回した食い違いの申し出・守りのパスに"
     "当たった差分・許したテストの変更・直す義務に戻せなかった単位・前提の検算が人に上げた物・人が確かめる物・直しきれずに残った物）。結末が止め札か関所の止め（stopped_by_request・stop"
     "ped_by_human）なら、止めた所・理由の本文・答えないまま残った問いを 1 項として必ず入れる——続けるなら新しい run を始めること、止めた後の段は走っていないことも添える。無ければ「人が"
     "決めることは無い」と 1 行。判定の役が自分で決めた問い（判定のファイルの問いの台帳で resolved / decided の物）は「判定の役が自分で決めたこと」として根拠つきで冒頭の直後に。\n"
     "   人に聞くところは、run を見ていない人が初見で読んで決められる形に: ①急ぐものと後でよいものを分け、件数を先に言う ②1 件ずつ独立して読める ③1 件につき、何を決めるのか・なぜこれが出て"
     "きたか（きっかけの実物）・選択肢ごとに何が起きるか・決めないと何が止まるか ④選ぶ側の材料を出す——ただし書いてよいのは判定の役が書いた選択肢と理由（問いの文の「推し」の尾・判定のファイルの台帳の o"
     "ptions と reason）だけで、writer が新たに 1 つを推すな。**内部の語彙（[block]・do-now・defer・零処方・R1〜R4・素材名・安定キー）で書かれた問いは、それだ"
     "けでは決められない。**\n"
     "2. この run の入口と依頼（冒頭 3 行と人が決めることの後ろに置く。冒頭 3 行の前に置かない）:\n"
     "   - 判定から入った run（機械の事実の「2. 入口・段・決めた人」の入口の行が言う）なら、1 行で「判定から入った run（出どころ）。依頼の外を見る役は、修正が入るまで起こしていない」と書く"
     "。依頼の外を見る目が欠けた周があったことを、収束の見た目に埋もれさせない。\n"
     "   - 依頼が積まれた run（入口の行と始めの記録の依頼の件数）なら、1 行で出どころと件数を並べる。人の依頼と機械の線を『人の依頼』と一括りに書くな。どの依頼も報告から落とさない。\n"
     "3. 判断材料として、機械の事実の「3. 止めたか」の結末と止めた段をそのまま貼る。\n"
     "4. 各根本の単位の「ラベル・対応内容／対応不要の理由」（判定のファイルと修正の結末の単位の行）。defer の台帳。\n"
     "5. R1・R2・R3・R4 それぞれの判定と理由（機械の事実の「独立の目」）。R1 は削ったコメント・残した why も。\n"
     "6. 問いの台帳——各問いの状態と、決めた根拠（resolved にした問いの resolution）か人へ回した理由。\n"
     "7. 判定の生の返答（判定のファイル。要約で丸めず、根本の単位のキーの集合と判定と理由はそのまま転記する）・元の目的の出典・直す前の版（始めの記録の元の版）。\n"
     "8. 主経路の実行観測: 何をどこで動かし何を観測したか（「テストが緑」を観測として書くな）。\n"
     "9. 新設機構の棚卸し: この差分が導入する機構・配管（ビルド設定・環境変数・CI ジョブ・テンプレートのノブ・スクリプト等）を、判定抜きで一覧する。\n"
     "10. 前提のドリフトがあれば、測り直した制約と前の制約が偽になった理由（収束せずに止まった run の held / escalate は 1 の人が決めることにまとめる）。\n"
     "\n"
     "## 書式の決まり（読み手のための決まり。上の構成と食い違う所はこちらを採る）\n",
     "元の指示書 prompts/review-loop/report.md（COPIED_FROM の手直しを当てた物）の構成の節を、盤面の欄を機械の事実のファイルの節に読み替えて差し込む"),
    ("（指示書の「人が決めることは無いと 1 行」",
     "（構成の「人が決めることは無い」と 1 行",
     "差し込んだ指示書の文を構成の節と呼ぶ"),
    ("（指示書の ①〜④ を広げた物）",
     "（構成の ①〜④ を広げた物）",
     "差し込んだ指示書の文を構成の節と呼ぶ"),
    ("判定の役が台帳の options・reason に書いた推しだけを",
     "判定の役が書いた推しだけを",
     "推しの出どころ（問いの文の推しの尾と台帳の欄）は構成の ④ が名指す"),
    ("お前はレビューの最終報告を書く役（writer）。",
     "$facts.output.lang_line\n\nお前はレビューの最終報告を書く役（writer）。",
     "役の文の頭に言語の 1 行を足す（元は包みが rolekit.lang_line を役の文に足した: works/.shared/core/rolekit.py 147-150 行。L-E37）"),
    ("1 行目: 何が起きたか（結末を専門語なしで）。2 行目:",
     "1 行目: 何が起きたか（結末を専門語なしで）。機械の事実の冒頭の「起きたこと」に、工場の中で試験が走っていない・走ったと確かめられていない・試験の関門の script が落ちたの句や、AI が書いた試験のコードを利用者の資格に届く環境で走らせたの句が在れば、"
     "その句をそのまま 1 行目に入れる。2 行目:",
     "#492: 試験が走らなかった run と、対象のコマンドを利用者の資格に届く環境で走らせた run を冒頭で名指す"),
    ("工場の中で試験が走っていない・走ったと確かめられていない",
     "工場の中で試験が走っていない・試験の段の一部しか走らせられていない・走ったと確かめられていない",
     "#514: 試験の段の一部だけ起こせた run の句も冒頭に入れる"),
    ("試験の段の一部しか走らせられていない・",
     "試験の段の一部しか走らせられていない（後ろの括弧の段の名まで）・",
     "#514: 一部しか走らせられていない句は、受け付けが段の名の括弧まで求める"),
]
COLD_CHECK_EDITS = [
    ("機械が盤面から組んだ事実の節（数・置き場・状態の一覧。見出しは「機械が盤面から組んだ事実（AI は書き換えていない）」）",
     "機械が組んだ事実の節（数・置き場・状態の一覧。見出しは「機械が各段の返りと run の記録から組んだ事実（AI は書き換えていない）」）",
     "盤面が無いので、機械の事実の見出しを report_roles.MACHINE_HEADING の字に"),
    ("下の区切りの間が、お前が読む指示と本文の全部である。\n",
     "お前は文脈を持たない初見の読み手。ラウンドの経緯・記録・差分は一切渡されていない。次の本文（レビューの最終報告のうち、人に決めてもらうところ）だけを読め。\n",
     "区切りの間に指示書ごと渡さないので、元の指示書 prompts/review-loop/report.cold_check.md の頭の文を差し込む"),
    ("$report-write-cold-prep.output.prompt\n",
     "$cold-prep.output.body\n",
     "区切りの間に渡すのは報告の頭の本文だけ（節 cold-prep）"),
    ("返すのは上の JSON Schema に合う JSON だけ。\n",
     "①どこで意味が取れず止まったか（stops）②何を推測で埋めたか（guessed）③この本文だけで決められるか（decidable）を返せ。止まった箇所か推測が 1 つでもあれば verdict=re"
     "design-needed、無ければ pass。\n"
     "\n"
     '返すのは JSON `{"verdict": "pass" | "redesign-needed", "stops": ["<文>"], "guessed": ["<文>"], "decidable"'
     ": true | false}` だけ。\n",
     "元の指示書 report.cold_check.md の返す物の文を差し込み、Schema を区切りの間で渡さないので返す形を名指す"),
]
COPIED = {"report.md": ("report-write.md", "dd402ea917dfc83fa32e41442b3bc0f5262c6f93ad9c07a7d78f076e693773a8", REPORT_EDITS),
          "cold-check.md": ("report-write-cold.md", "1de61b6025023f62f99fc20c196f1f87e69fed4fbd5c49232224d366c6eb3815",
                            COLD_CHECK_EDITS)}


class ShapeCase(unittest.TestCase):
    def test_name_and_returns(self):
        self.assertEqual(WORKFLOW["name"], "works-factory-report-write")
        self.assertEqual(WORKFLOW["returns"], "written")
        self.assertEqual(WORKFLOW["outcome_field"], "ok")
        schema = NODES["written"]["output_format"]
        self.assertEqual(set(schema["required"]), {"ok", "ai"})
        self.assertEqual(schema["properties"]["ok"]["type"], "boolean")
        self.assertEqual(NODES["written"]["depends_on"], ["write-loop"])

    def test_inputs_are_the_contract(self):
        self.assertEqual(tuple(WORKFLOW["inputs"]), INPUTS)
        self.assertTrue(all(v["default"] == "" for v in WORKFLOW["inputs"].values()))

    def test_no_top_keys_dropped_on_include(self):
        for key in TOP_KEYS_DROPPED_ON_INCLUDE:
            self.assertNotIn(key, WORKFLOW)

    def test_every_node_leaves_the_checkout_alone(self):
        for nid, node in {**NODES, **BODY}.items():
            if "loop_group" in node:
                continue
            with self.subTest(nid):
                self.assertIs(node.get("mutates_checkout"), False)

    def test_roles(self):
        write, cold = BODY["write"], BODY["cold"]
        self.assertEqual(write["allowed_tools"], ["Read", "Grep", "Glob", "WebSearch", "WebFetch"])
        self.assertEqual(cold["allowed_tools"], [])
        self.assertEqual(cold["context"], "fresh")
        for node in (write, cold):
            self.assertEqual(node["settingSources"], ["user"])
            self.assertEqual(node["sandbox"], SANDBOX)
            self.assertEqual(launchgroups.default_of(node["model"]), ("sonnet", "medium"))
        self.assertEqual(write["output_format"], {k: v for k, v in report_roles.TEXT_SCHEMA.items()})
        self.assertEqual(cold["output_format"], runreport.COLD_SCHEMA)

    def test_writer_receives_the_reject_file_through_the_reject_node(self):
        """前の周の拒否の訳のファイルと前の答えの控えは、ループの頭の節 write-reject（script reject）の with: に $LOOP_PREV で結び、書き手の
        指示書は今の周のその節の返り $write-reject.output.reason・$write-reject.output.prev で受ける。書き手の節に with: を書かない（線が include すると、止めた Archon は輪の中の
        節の with: の名を楯にせず「入力が無い」で止める。packages/workflows/src/include-expander.ts:566・627）"""
        reject, write = BODY["write-reject"], BODY["write"]
        self.assertEqual((reject["script"], reject["runtime"], reject["with"]),
                         ("reject", "uv", {"reason": "$LOOP_PREV.accept.output.reason_file", "prev": "$LOOP_PREV.accept.output.prev_file"}))
        self.assertEqual(reject["output_format"]["required"], ["reason", "prev", "handoff"])
        self.assertEqual(reject["output_format"]["properties"]["handoff"], {"type": "string"})
        self.assertIn("prev_file", NODES["write-loop"]["loop_group"]["nodes"][-1]["output_format"]["required"])
        self.assertNotIn("with", write)
        self.assertEqual(write["depends_on"], ["write-reject"])
        text = (BLOCK / "commands" / "report.md").read_text(encoding="utf-8")
        self.assertIn("`$write-reject.output.reason`", text)
        self.assertIn("`$write-reject.output.prev`", text)
        self.assertIn("$write-reject.output.handoff", text)
        self.assertEqual(sorted(set(re.findall(r"\$INPUTS\.(\w+)", text))), sorted(INPUTS), "入力はこのブロックの inputs: の名だけ")
        self.assertNotIn("$LOOP_PREV", text)
        self.assertNotIn("$facts.", text)

    def test_cold_reader_is_told_the_machine_heading(self):
        """初見の読み手の決まりが名指す機械の事実の見出しは、AI の報告が付ける見出しの字そのまま"""
        text = (BLOCK / "commands" / "cold-check.md").read_text(encoding="utf-8")
        self.assertIn(f"「{report_roles.MACHINE_HEADING.removeprefix('## ')}」", text)

    def test_loop_gives_up_with_the_roles_count(self):
        self.assertEqual(NODES["write-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)


class CopiedTextsCase(unittest.TestCase):
    def test_every_command_is_its_original_with_only_ledgered_edits(self):
        """役の指示書は元の works の指示書の文のまま: 台帳の直しを逆に当てると元のバイトに戻る"""
        self.assertEqual({p.name for p in (BLOCK / "commands").glob("*.md")}, set(COPIED))
        self.assertLessEqual(rewritten(BLOCK / "commands"), set(COPIED))
        for name, (original, sha, edits) in COPIED.items():
            with self.subTest(name, original=original):
                assert_is_original(self, BLOCK / "commands" / name, sha, edits)

    def test_writer_names_factory_things_in_graph_and_user_words(self):
        """#495: 書き手の書式の決まりが、工場の中の物をグラフの語（サブグラフ・ノード）で名指し、ほかを利用者の語に言い換えさせる"""
        text = (BLOCK / "commands" / "report.md").read_text(encoding="utf-8")
        rule = [line for line in text.splitlines() if line.startswith("- 工場の中の物はグラフの語で名指す")]
        self.assertEqual(len(rule), 1)
        for word in ("サブグラフ", "ノード", "承認ノード", "利用者の語", "terms"):
            self.assertIn(word, rule[0])


class AcceptScriptCase(Run):
    REPLY = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)
    REDESIGN = json.dumps({"verdict": "redesign-needed", "stops": ["2 行目"], "guessed": [], "decidable": False}, ensure_ascii=False)
    PASS = json.dumps({"verdict": "pass", "stops": [], "guessed": [], "decidable": True})

    def accept(self, reply, cold):
        code, out = self.run_script("report_accept", WRITE_SCRIPTS, INPUTS_REPLY=reply, INPUTS_COLD=cold)
        self.assertEqual(code, 0)
        return out

    def test_cold_redesign_three_times(self):
        self.assertIs(self.accept(self.REPLY, self.REDESIGN)["done"], False)
        second = self.accept(self.REPLY, self.REDESIGN)
        self.assertIs(second["done"], False)
        self.assertEqual(second["reason_file"], f"{runreport.OUT_DIR}/rejects-report.md", "機械の事実のファイルと同じく run の置き場からの相対")
        text = (self.artifacts / second["reason_file"]).read_text(encoding="utf-8")
        self.assertIn("2 行目", text)
        self.assertIn("1 回目の拒否:", text)
        self.assertIn("2 回目の拒否:", text, "1・2 回目の拒否が古い順に全部在る")
        third = self.accept(self.REPLY, self.REDESIGN)
        self.assertIs(third["done"], True)
        ai = json.loads((self.artifacts / runreport.OUT_DIR / runreport.AI_FILE).read_text(encoding="utf-8"))
        self.assertTrue(ai["accepted"])
        self.assertTrue(ai["not_passed"])
        self.unusable_ledger_is_a_done_reject_not_a_failed_script()

    def unusable_ledger_is_a_done_reject_not_a_failed_script(self):
        """拒否の控え rejects-report.json が読めなくても report_accept は非 0 で落ちず、done 真・ok 偽（reason_file は空）で返り、
        受け取れなかった訳（accepted: false と『拒否の控えが扱えない』）を AI_FILE に残す"""
        out_dir = self.artifacts / runreport.OUT_DIR
        (out_dir / "rejects-report.json").unlink()
        (out_dir / "rejects-report.json").mkdir()
        got = self.accept(self.REPLY, self.REDESIGN)
        self.assertEqual((got["done"], got["ok"], got["reason_file"]), (True, False, ""))
        self.assertIn("拒否の控えが扱えない", got["reason"])
        ai = json.loads((out_dir / runreport.AI_FILE).read_text(encoding="utf-8"))
        self.assertFalse(ai["accepted"])
        self.assertIn("拒否の控えが扱えない", ai["reason"])

    def test_rejected_round_names_the_previous_answer_relative(self):
        note = {"read": [{"path": "lib/runreport.py", "lines": "1", "why": "確かめた"}], "decided": ["訳"],
                "rejected": [{"option": "案", "why": "訳"}], "doubts": ["迷い"]}
        reply = json.dumps({**json.loads(self.REPLY), "handoff": note}, ensure_ascii=False)
        out = self.accept(reply, self.REDESIGN)
        self.assertTrue(out.get("prev_file"))
        self.assertEqual(out["prev_file"], f"{runreport.OUT_DIR}/candidate-report.json")
        kept = json.loads((self.artifacts / out["prev_file"]).read_text(encoding="utf-8"))
        self.assertEqual(kept, {"text": json.loads(reply)["text"], "terms": []})
        saved = self.artifacts / runreport.OUT_DIR / runreport.NOTE_ROUND.format(n=1) / "handoff.json"
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), note)
        self.assertEqual(self.accept(self.REPLY, self.PASS)["prev_file"], "")

    def test_cells_and_terms_rejected_first_time(self):
        cell = json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |"}, ensure_ascii=False)
        self.assertEqual(self.accept(cell, self.PASS)["kind"], "format")
        terms = json.dumps({"text": "x", "terms": [{"term": "a"}]})
        self.assertEqual(self.accept(terms, self.PASS)["kind"], "answer")


class RejectScriptCase(Run):
    def test_previous_answer_passes_through(self):
        for reason, prev in (("", ""), ("2 行目", "report/candidate-report.json")):
            with self.subTest(prev=prev):
                code, out = self.run_script("reject", WRITE_SCRIPTS, INPUTS_REASON=reason, INPUTS_PREV=prev)
                self.assertEqual(code, 0)
                self.assertEqual(out, {"reason": reason, "prev": prev, "handoff": handoff.ASK})

    def test_reject_hands_the_ask_and_every_prior_note(self):
        """ループの頭の節の出力の欄 handoff に、住処の頼み handoff.ASK と、使い方 handoff.USE と、前の周までの report/r<n>/handoff.json の
        パスが古い順に在る（今の周の分は無い）。メモを書かなかった周は無いと名指す"""
        redesign = AcceptScriptCase.REDESIGN
        note = {"read": [{"path": "a.py", "lines": "1", "why": "読んだ"}], "decided": ["aの訳"],
                "rejected": [{"option": "aの案", "why": "訳"}], "doubts": []}
        replies = [json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": [], "handoff": note}, ensure_ascii=False),
                   json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)]
        for reply in replies:
            code, _ = self.run_script("report_accept", WRITE_SCRIPTS, INPUTS_REPLY=reply, INPUTS_COLD=redesign)
            self.assertEqual(code, 0)
        code, out = self.run_script("reject", WRITE_SCRIPTS, INPUTS_REASON="x", INPUTS_PREV="y")
        self.assertEqual(code, 0)
        part = out["handoff"]
        folder = self.artifacts / runreport.OUT_DIR
        self.assertTrue(part.startswith(handoff.ASK))
        self.assertIn(handoff.HEAD, part)
        self.assertIn(handoff.USE, part)
        first, second = str(handoff.path_of(folder / "r1")), str(handoff.path_of(folder / "r2"))
        self.assertIn(first, part)
        self.assertNotIn(second, part, "メモを書かなかった周のパスは名指さない")
        self.assertLess(part.index(handoff.USE), part.index(first))
        self.assertLess(part.index(first), part.index(handoff.NONE))
        self.assertNotIn("r3", part, "今の周の分は無い")
        self.assertNotIn(note["decided"][0], part, "中身は貼らずパスで名指す")


class ColdPrepScriptCase(Run):
    def test_body_is_the_human_head(self):
        """初見の読み手に貼る本文は、入力 facts_file が指す機械の報告の冒頭と書き手の頭を語の表で言い換えた物（#660）"""
        code, facts = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}))
        self.assertEqual(code, 0)
        writer = json.dumps({"text": "承認ノードで止めた。\n\n## 2. 経緯\n\n長い", "terms": []}, ensure_ascii=False)
        code, out = self.run_script("cold_prep", WRITE_SCRIPTS, INPUTS_WRITER=writer, INPUTS_FACTS_FILE=facts["facts_file"])
        self.assertEqual(code, 0)
        self.assertTrue(out["body"].startswith(f"# 報告（run {RUN}）\n\n{gatemarks.HAPPENED}"), out["body"])
        self.assertIn("先へ進めるかを決める所で止めた。", out["body"])
        self.assertNotIn("長い", out["body"])


class WrittenScriptCase(Run):
    SCHEMA = NODES["written"]["output_format"]

    def written(self) -> dict:
        code, out = self.run_script("written", WRITE_SCRIPTS)
        self.assertEqual(code, 0)
        self.assertEqual(validate_schema(out, self.SCHEMA), [], out)
        return out

    def test_points_at_the_answer_the_loop_left(self):
        self.assertEqual(self.written(), {"ok": False, "ai": None})
        runreport.accept(AcceptScriptCase.REPLY, AcceptScriptCase.PASS, out_dir=self.artifacts / runreport.OUT_DIR)
        self.assertEqual(self.written(), {"ok": True, "ai": {"type": "archon_artifact", "run_id": RUN,
                                                              "path": f"{runreport.OUT_DIR}/{runreport.AI_FILE}"}})


class FixtureCase(unittest.TestCase):
    """筋書きを止めた Archon の workflow test で回し、同じ木の validate に誤りも警告も無いことを見る"""

    def test_fixtures_pass_and_validate_is_clean(self):
        with archon.tree(["report-write"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-report-write", "--json", "--cwd", str(tree))
            try:
                got = json.loads(done.stdout)
            except json.JSONDecodeError:
                self.fail(f"workflow test の返りが読めない: {done.stdout}{done.stderr}")
            names = sorted(pathlib.Path(r["fixture"]).name for r in got["results"])
            self.assertEqual(names, sorted(p.name for p in (BLOCK / "fixtures").glob("*.stubs.yaml")))
            self.assertEqual([r for r in got["results"] if not r["pass"]], [], done.stdout)
            self.assertEqual(got["errors"], [])
            checked = archon.archon(tree, "validate", "workflows", "--json", "--cwd", str(tree))
            issues = {r["workflowName"]: r["issues"] for r in json.loads(checked.stdout)["results"]}
            self.assertEqual(issues.get("works-factory-report-write"), [])


if __name__ == "__main__":
    unittest.main()
