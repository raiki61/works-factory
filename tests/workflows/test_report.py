"""報告のブロック（workflows/report/）の試験。

- YAML の形: PyYAML で読み、Archon を起こさない（返す節の約束の欄・入力・役の節の鍵）
- 部品と script: scripts/facts.py の一覧の読みを一時の一覧で回し、facts.py・report_accept.py・collect.py を子のプロセスで走らせる
  （一時の ARTIFACTS_DIR と環境変数。Archon を起こさない）
- 筋書き: tests/archon.py の使い捨ての木で fixtures/ を archon workflow test で回す。Archon の源か bun が無ければ名前つきで見送る
- 本物の run: 同じ使い捨ての木で試しの工程を 1 回だけ本当に回し（dry-run でない）、実行基盤が書いた run の記録と型つきの
  成果物の一覧を読む部品に読ませる
"""
import ast
import importlib.util
import inspect
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

from tests import archon
from tests.bin import hermetic
from tests.workflows import test_plan_review as plan_review
from tests.workflows.copied import assert_is_original, rewritten

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCK = ROOT / "workflows" / "report"
SCRIPTS = BLOCK / "scripts"
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
if str(LIB / "graphloops") not in sys.path:
    sys.path.append(str(LIB / "graphloops"))

import answer  # noqa: E402
import converge  # noqa: E402
import declared_checks  # noqa: E402
import gatemarks  # noqa: E402
import handoff  # noqa: E402
import launchgroups  # noqa: E402
import outcome  # noqa: E402
import report  # noqa: E402
import report_roles  # noqa: E402
import rolekit  # noqa: E402
import runreport  # noqa: E402
import userenv  # noqa: E402
from engine.schema import validate_schema  # noqa: E402
from lib.tests.test_outcome import STAGES, fixed_run  # noqa: E402

WORKFLOW = yaml.safe_load((BLOCK / "works-factory-report.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in WORKFLOW["nodes"]}
BODY = {n["id"]: n for n in NODES["write-loop"]["loop_group"]["nodes"]}
INPUTS = ("start", "before-tests", "judge", "rejudge", "structure", "plan", "plan-review", "replan", "replan-review-result", "fix", "final-tests",
          "eyes", "sealed-diff", "applied-diff", "start-answer", "before-fix-answer", "replan-answer", "final-answer", "stops",
          "prior-failures", "deferred", "widened", "final-reasons", "spec-changed", "spec-unchecked", "redepth", "optional", "stages", "notices",
          "user-env-dir")
RETURN_FIELDS = {"outcome", "stop_reason", "report", "report_ai", "next_request", "prior_failures", "ok"}
TOP_KEYS_DROPPED_ON_INCLUDE = ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout")
SANDBOX = {"enabled": True, "allowUnsandboxedCommands": False}
RUN = "run-test"

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


def load_script(name: str, scripts: pathlib.Path = SCRIPTS):
    spec = importlib.util.spec_from_file_location(f"{scripts.parent.name}_block_{name}", scripts / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


def env_reads(script: str) -> dict:
    """script の頭の、入力の名 → 読む環境変数の名（RETURNS・GATES・LINE の dict と START の os.environ.get の字）"""
    reads = {}
    for node in ast.parse((SCRIPTS / f"{script}.py").read_text(encoding="utf-8")).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name, value = node.targets[0].id, node.value
        pairs = (zip(value.keys, value.values) if isinstance(value, ast.Dict) and name in ("RETURNS", "GATES", "LINE")
                 else [(ast.Constant("start"), value)] if name == "START" else [])
        for key, call in pairs:
            reads[key.value] = call.args[0].value
    return reads


if str(ROOT / "workflows" / ".shared") not in sys.path:
    sys.path.append(str(ROOT / "workflows" / ".shared"))
facts_script = load_script("facts")


class ShapeCase(unittest.TestCase):
    def test_name_and_returns(self):
        self.assertEqual(WORKFLOW["name"], "works-factory-report")
        self.assertEqual(WORKFLOW["returns"], "report")
        self.assertEqual(WORKFLOW["outcome_field"], "ok")

    def test_return_fields_are_the_contract(self):
        schema = NODES["report"]["output_format"]
        self.assertEqual(set(schema["properties"]), RETURN_FIELDS)
        self.assertEqual(set(schema["required"]), RETURN_FIELDS)
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(tuple(schema["properties"]["outcome"]["enum"]), report.OUTCOMES)
        self.assertEqual(schema["properties"][WORKFLOW["outcome_field"]]["type"], "boolean")

    def test_inputs_are_the_contract(self):
        self.assertEqual(tuple(WORKFLOW["inputs"]), INPUTS)
        self.assertTrue(all(set(v) == {"default", "description"} and v["default"] == "" and str(v["description"]).strip()
                            for v in WORKFLOW["inputs"].values()))

    def test_every_input_describes_its_value_and_no_name_is_a_main_node(self):
        """入力のポートの名は値の形の名で、メイングラフの節の id の字を借りない（結びは線の with: だけが持つ）。どのポートも値の形の説明を持つ
        （型・欄・空や null の時の意味）。段の表を運ぶポート stages が在る"""
        line = yaml.safe_load((ROOT / "workflows" / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))
        main_ids = {n["id"] for n in line["nodes"]}
        for name, spec in WORKFLOW["inputs"].items():
            with self.subTest(name):
                self.assertNotIn(name, {i for i in main_ids if "-" in i}, "メイングラフの節の id と同じ字のポートの名")
                self.assertTrue(isinstance(spec.get("description"), str) and spec["description"].strip(), "値の形の説明が無い")
        self.assertIn("stages", WORKFLOW["inputs"])

    def test_facts_reads_every_input_by_its_own_name(self):
        """facts の読む入力が YAML の inputs と同じで、どれも自分の名の環境変数から読む（印の置き場 user-env-dir は呼ぶ時に読む
        marked_place）。outcome の関所の並びは inputs の -answer"""
        reads = env_reads("facts")
        self.assertEqual(reads, {name: f"INPUTS_{name.upper().replace('-', '_')}" for name in WORKFLOW["inputs"] if name != "user-env-dir"})
        self.assertIn('os.environ.get("INPUTS_USER_ENV_DIR"', inspect.getsource(facts_script.marked_place))
        self.assertEqual(outcome.GATES, tuple(name for name in WORKFLOW["inputs"] if name.endswith("-answer")))

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
        """前の周の拒否の訳のファイルと前の答えの控えは、輪の頭の節 write-reject（script reject）の with: に $LOOP_PREV で結び、書き手の
        指示書は今の周のその節の返り $write-reject.output.reason・$write-reject.output.prev で受ける。書き手の節に with: を書かない（線が include すると、止めた Archon は輪の中の
        節の with: の名を楯にせず「入力が無い」で止める。packages/workflows/src/include-expander.ts の applyInputsMacro・inlineInclude）"""
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
        self.assertNotIn("$INPUTS", text)
        self.assertNotIn("$LOOP_PREV", text)

    def test_return_node_runs_whatever_came_before(self):
        self.assertEqual(NODES["report"]["trigger_rule"], "all_done")
        self.assertEqual(NODES["report"]["depends_on"], ["facts", "write-loop"])

    def test_return_node_names_the_writer_loop_of_this_graph(self):
        self.assertIn("write", [n["id"] for n in NODES[load_script("collect").WRITER]["loop_group"]["nodes"]])

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


class TypedCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def entry(self, node, path, body, loop=None, run=RUN):
        (self.dir / path).parent.mkdir(parents=True, exist_ok=True)
        (self.dir / path).write_text(json.dumps(body), encoding="utf-8")
        row = {"nodeId": node, "outputType": "x", "path": path, "runId": run, "producedAt": "2026-10-12T00:00:00.000Z", "size": 1}
        if loop:
            row["loopGroupPath"] = [{"groupId": g, "iteration": i} for g, i in loop]
        return row

    def listing(self, by_type, errors=(), run=RUN):
        path = self.dir / "listing.json"
        path.write_text(json.dumps({"runId": run, "artifactsByType": by_type, "errors": list(errors)}), encoding="utf-8")
        return str(path)

    def read(self, listing, execution=""):
        return facts_script.listing(listing, str(self.dir), RUN, execution)

    def test_groups_by_include_and_loop_keep_rounds_and_drop_others(self):
        rows = [self.entry("fix__tdd", "nodes/a.md", [{"group_id": "g1"}], loop=[("fix__loop", 1)]),
                self.entry("fix__tdd", "nodes/b.md", [{"group_id": "g1"}], loop=[("fix__loop", 2)]),
                self.entry("refix__tdd", "nodes/c.md", [{"group_id": "g2"}]),
                self.entry("fix__tdd", "nodes/d.md", [], run="other-run"),
                self.entry("report__x", "nodes/e.md", {})]
        got = self.read(self.listing({"tdd-unit": rows}), json.dumps({"path": "report__facts"}))
        units = got["by_type"]["tdd-unit"]
        self.assertEqual([(u["include"], u["loop"]) for u in units],
                         [("fix", [("fix__loop", 1)]), ("fix", [("fix__loop", 2)]), ("refix", [])])
        self.assertEqual(units[0]["body"], [{"group_id": "g1"}])
        self.assertEqual(got["warnings"], [])

    def test_nested_include_drops_only_its_own_rows(self):
        """入れ子の include の節の id は outer__inner__node（Archon の include-expander の名前空間）"""
        rows = [self.entry("outer__fix__tdd", "nodes/a.md", {}), self.entry("outer__report__x", "nodes/b.md", {})]
        got = self.read(self.listing({"k": rows}), json.dumps({"path": "outer__report__facts"}))
        self.assertEqual([u["node"] for u in got["by_type"]["k"]], ["outer__fix__tdd"])

    def test_errors_each_become_a_warning(self):
        errors = [{"path": "nodes/x.meta.json", "kind": "invalid_metadata"}, {"path": "nodes", "kind": "unreadable_directory", "code": "EACCES"}]
        got = self.read(self.listing({}, errors))
        self.assertEqual(len(got["warnings"]), 2)
        self.assertIn("invalid_metadata", got["warnings"][0])
        self.assertIn("EACCES", got["warnings"][1])

    def test_named_limits_without_raising(self):
        cases = {"": "TYPED_ARTIFACTS_FILE が空", str(self.dir / "none.json"): "読めない"}
        bad = self.dir / "bad.json"
        bad.write_text("{壊れた", encoding="utf-8")
        cases[str(bad)] = "読めない"
        cases[self.listing("配列でない")] = "artifactsByType がオブジェクトでない"
        cases[self.listing({"tdd-unit": {"a": 1}})] = "配列でない"
        for listing, word in cases.items():
            with self.subTest(listing=listing):
                got = self.read(listing)
                self.assertEqual(len(got["warnings"]), 1, got)
                self.assertIn(word, got["warnings"][0])

    def test_unreadable_content_is_named(self):
        row = self.entry("eyes__r1", "nodes/r1.md", {})
        (self.dir / "nodes/r1.md").write_text("JSON でない", encoding="utf-8")
        got = self.read(self.listing({"eye-verdict": [row]}))
        self.assertIsNone(got["by_type"]["eye-verdict"][0]["body"])
        self.assertIn("nodes/r1.md", got["warnings"][0])


class Run(unittest.TestCase):
    """script を子のプロセスで走らせる（一時の run の置き場と、Archon が渡すのと同じ名の環境変数）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        self.artifacts = self.dir / "artifacts"
        self.artifacts.mkdir()

    def run_script(self, name: str, **env) -> tuple[int, dict]:
        base = hermetic.child_env(**{"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN, "TYPED_ARTIFACTS_FILE": "", "LOG_DIR": "",
                                     "WORKS_FACTORY_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1",
                                     "INPUTS_USER_ENV_DIR": str(self.artifacts), "INPUTS_STAGES": json.dumps(STAGES, ensure_ascii=False),
                                     **env})
        done = subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py")], env=base, capture_output=True, text=True,
                              encoding="utf-8")
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"JSON 1 つを出す: {done.stdout}{done.stderr}")
        return done.returncode, json.loads(lines[0])

    def pointer(self, rel: str, doc) -> str:
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.dumps({"type": "archon_artifact", "run_id": RUN, "path": rel})


class FactsCase(Run):
    def test_empty_inputs_are_record_invalid_and_exit_zero(self):
        code, out = self.run_script("facts")
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertIs(out["ai_go"], False)
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("始めの記録（入力 start）が届いていない", text)
        self.assertTrue(out["stamp"].endswith(" / メイングラフの版 読めない（始めの記録が読めない）"), out["stamp"])
        self.assertIn("TYPED_ARTIFACTS_FILE が空", text)
        self.assertIn("LOG_DIR", text)

    def test_users_env_sentence_only_with_the_marker(self):
        """#504: 起動の殻を通った run（いつも控えが在る）でも、対象のコマンドを利用者の HOME・XDG に戻して起こした印（入力 user-env-dir の
        置き場の userenv.RAN_FILE）が無ければ、報告の冒頭は利用者の環境で走らせたと言わない（対象のコマンドの前に止まった run）。
        入力が空なら自分の置き場の印を黙って読まない（#681）"""
        opted = {userenv.RECORD: userenv.record({"HOME": "/u"})}
        text = (self.artifacts / self.run_script("facts", **opted)[1]["facts_file"]).read_text(encoding="utf-8")
        self.assertNotIn(userenv.NOTE, text)
        (self.artifacts / userenv.RAN_FILE).touch()
        text = (self.artifacts / self.run_script("facts", **opted)[1]["facts_file"]).read_text(encoding="utf-8")
        self.assertIn(userenv.NOTE, text)
        text = (self.artifacts / self.run_script("facts", **opted, INPUTS_USER_ENV_DIR="")[1]["facts_file"]).read_text(encoding="utf-8")
        self.assertNotIn(userenv.NOTE, text)

    def test_fallen_report_says_users_env_with_the_marker(self):
        """#504: 思わぬ誤りで落ちた報告も、印（userenv.RAN_FILE）が在れば冒頭で利用者の環境で走らせたと言う（起動の 1 行が冒頭を指す）"""
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN, "INPUTS_USER_ENV_DIR": str(self.artifacts)}):
            for marked in (False, True):
                with self.subTest(marked=marked):
                    if marked:
                        (self.artifacts / userenv.RAN_FILE).touch()
                    out = facts_script.fallen(RuntimeError("壊れた"))
                    text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
                    self.assertEqual(userenv.NOTE in text, marked)

    def test_broken_inputs_and_missing_pointer_do_not_fall(self):
        code, out = self.run_script("facts", INPUTS_START=json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "start/none.json"}),
                                    INPUTS_JUDGE="{壊れた", INPUTS_PLAN="[1, 2]", INPUTS_FIX="null", INPUTS_FINAL_ANSWER="",
                                    WORKFLOW_ID=RUN, LOG_DIR=str(self.dir))
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("入力 judge が JSON でない", text)
        self.assertIn("入力 plan が JSON のオブジェクトでない", text)
        self.assertIn("始めの記録を開けない", text)
        self.assertTrue(out["stamp"].endswith(" / メイングラフの版 読めない（始めの記録が読めない）"), out["stamp"])
        self.assertIn(f"run の記録 {self.dir / RUN}.jsonl が読めない", text)
        # 段の表（入力 stages）が空・JSON でない・表の形でない時も、ほかの JSON の入力が壊れた時と同じく結果を名乗らせない。表の無い第 2 の道は置かない
        start = self.pointer("start/start.json", {"run_id": RUN})
        for name, raw, why in (("空", "", "入力 stages が届いていない"), ("JSON でない", "{壊れた", "入力 stages が JSON でない"),
                               ("表の形でない", json.dumps({"nodes": []}), "入力 stages が段の表 {nodes, links} の形でない")):
            with self.subTest(name):
                code, out = self.run_script("facts", INPUTS_START=start, INPUTS_STAGES=raw)
                self.assertEqual((code, out["outcome"], out["stop_reason"]), (0, "record_invalid", "report:record-invalid"))
                self.assertIn(f"結果を名乗れない訳: {why}", (self.artifacts / out["facts_file"]).read_text(encoding="utf-8"))

    def test_unexpected_error_still_returns(self):
        """思わぬ誤り（ここでは run の置き場がファイル）でも 0 で終わり、record_invalid と誤りの 1 行を返す"""
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        code, out = self.run_script("facts", ARTIFACTS_DIR=str(blocker))
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertTrue(out["stop_reason"].startswith("report:報告の事実を組めなかった"))

    def test_lang_line_reaches_the_writer(self):
        """L-E37: 始めの記録の lang が、報告の書き手の役の文の頭に言語の 1 行（rolekit.lang_line。判定・計画・修正・独立の目と同じ口）
        として届く。始めの記録が読めない・思わぬ誤りの時も既定の言語の 1 行を返す"""
        import rolekit
        start = self.pointer("start/start.json", {"run_id": RUN, "lang": "English"})
        code, out = self.run_script("facts", INPUTS_START=start)
        self.assertEqual((code, out["lang_line"]), (0, rolekit.lang_line({"lang": "English"})))
        self.assertIn("English", out["lang_line"])
        self.assertEqual(self.run_script("facts")[1]["lang_line"], rolekit.lang_line({}))
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        self.assertEqual(self.run_script("facts", ARTIFACTS_DIR=str(blocker))[1]["lang_line"], rolekit.lang_line({}))
        first = (BLOCK / "commands" / "report.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "$facts.output.lang_line")
        self.assertIn("lang_line", WORKFLOW["nodes"][0]["output_format"]["required"])

    def test_request_stop_with_dry_run_environment(self):
        start = self.pointer("start/start.json", {"run_id": RUN})
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_FINAL_ANSWER='{"decision":"stop","text":"request: 止め札"}',
                                    WORKFLOW_ID="dry-run")
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"], out["ok"]), ("stopped_by_request", "gate-final:stop", False))

    def test_unknown_answer_word_is_record_invalid_with_its_reason(self):
        start = self.pointer("start/start.json", {"run_id": RUN})
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_FINAL_ANSWER='{"decision":"maybe","text":""}')
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"], out["ok"]), ("record_invalid", "report:record-invalid", False))
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn("結果を名乗れない訳: 承認ノード gate-final の知らない答えの語 'maybe'", text)

    def test_unreadable_or_missing_conflicts_are_record_invalid(self):
        """人に回した申し出が読めない run は結果を名乗らない（読めなければ人に聞いた申し出が無いと数えて fixed に落ちる）"""
        start = self.pointer("start/start.json", {"run_id": RUN})
        broken = self.pointer("fix/conflicts.json", {})
        (self.artifacts / "fix/conflicts.json").write_text("{not json", encoding="utf-8")
        missing = json.dumps({"type": "archon_artifact", "run_id": RUN, "path": "fix/none.json"})
        for name, conflicts, word in (("JSON でない", broken, "申し出と裁定のファイル"), ("先が無い", missing, "ポインタの先")):
            with self.subTest(name):
                fix = json.dumps({"done": True, "units": [], "conflicts": json.loads(conflicts)})
                code, out = self.run_script("facts", INPUTS_START=start, INPUTS_FIX=fix)
                self.assertEqual(code, 0)
                self.assertEqual((out["outcome"], out["stop_reason"]), ("record_invalid", "report:record-invalid"))
                text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
                self.assertIn(f"結果を名乗れない訳: {word}", text)

    def test_stamp_carries_the_plan_round_and_measured_answer_reaches_outcome(self):
        """来歴の行の周は計画（案の直しが在ればそちら）の round、メイングラフの版は始めの記録の versions.works.rev。依頼が命令と出力つきで答えた素材は残りに数えない（始めの記録の
        answers が結末の決め方に届く）"""
        start = self.pointer("start/start.json", {"run_id": RUN, "versions": {"works": {"rev": "c" * 64, "dirty": False}}, "answers": [
            {"question": "ci", "text": "緑", "command": "make ci", "output": "ok"}]})
        judgment = self.pointer("judge/judgment.json", {})
        self.pointer("judge/materials.json", {"ci": {"status": "awaiting_human"}})
        judge = {"ready": True, "stop_reason": "", "units": [{"id": "u1"}], "judgment": json.loads(judgment)}
        env = {"INPUTS_START": start, "INPUTS_JUDGE": json.dumps(judge), "INPUTS_PLAN": '{"ready": true, "round": 1}',
               "INPUTS_REPLAN": '{"ready": true, "round": 2}', "INPUTS_FIX": json.dumps({"done": True, "units": []}),
               "INPUTS_FINAL_TESTS": '{"ok": true, "green": true}', "INPUTS_SEALED_DIFF": '{"ok": true}'}
        code, out = self.run_script("facts", **env)
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "fixed", (self.artifacts / out["facts_file"]).read_text(encoding="utf-8"))
        self.assertRegex(out["stamp"], rf"^works-factory-report / run {RUN} / 周 2 / グラフの版 [0-9a-f]{{12}} / メイングラフの版 cccccccccccc$")

    def test_evidence_rows_stay_one_line_each(self):
        """役の素材の reason の改行は返りの欄と証拠の行を切らず、次の行の頭にも化けない: 修正前のテストの行は reason の終わりまで
        届き、ログの行は本物の置き場のまま。報告は証拠の文を開かずに返りの欄から同じ行を出す"""
        result = load_script("result", ROOT / "workflows" / "test-gate" / "scripts")
        run = {"by": "engine", "log": "/tmp/test.log", "junit_steps": [], "junit_unran": [], "suite": None,
               "fingerprint_before": None, "fingerprint_after": None}
        log, how = result.LOG_ROW, result.RUN_ROW
        base_line = declared_checks.baseline_line({"material": {"status": "not_run", "reason": f"見た物:\n{log}ci/output.txt"}})
        out = {"ok": False, "green": False, "red_cause": "incomplete", **result.gate_fields(run, "一式", base_line, f"訳:\n{log}偽")}
        rows = result.evidence("final", out, run, None, f"落ちた:\n{how}偽").splitlines()
        self.assertEqual([r for r in rows if r.startswith((log, how))], [f"{how}engine・一式", f"{log}/tmp/test.log"])
        self.assertIn(f"- ok: false（訳: {log}偽）", rows)
        returns = {"final-tests": out}
        got = runreport._evidence_lines(returns, STAGES)
        self.assertIn("最後のテスト（test-gate-final）のログ: /tmp/test.log", got)
        self.assertIn("最後のテスト（test-gate-final）の走らせ方: engine・一式", got)
        base = next(x for x in got if x.startswith("最後のテスト（test-gate-final）の修正前のテスト: "))
        self.assertIn(f"見た物: {log}ci/output.txt", base)
        self.assertIn(gatemarks.BASELINE_NOT_RUN, base)
        self.assertIn(f"- {base.removeprefix('最後のテスト（test-gate-final）の')}", rows)
        self.assertIn("最後のテストの一式: engine・一式・ログ /tmp/test.log", runreport._tests_head_lines(returns))

    def final_returned(self, **fields) -> str:
        """test-gate（final）の返りの JSON。証拠の指し札の先のファイルは置かない（報告は返りの欄だけを読む）"""
        return json.dumps({"mode": "final", "ok": True, "green": True, "red_cause": "", "baseline": None, "fingerprint": None,
                           "evidence": {"type": "archon_artifact", "run_id": RUN, "path": "test-gate/final/evidence.md"},
                           "by": "engine", "suites_line": "", "log": "", "baseline_line": "", "reason": "", **fields})

    def green_section(self, final: str) -> str:
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}), INPUTS_FINAL_TESTS=final)
        self.assertEqual(code, 0)
        return (self.artifacts / out["facts_file"]).read_text(encoding="utf-8").split(f"{runreport.GREEN_HEADING}\n\n", 1)[1]

    def test_green_cert_section_reads_the_test_gate_evidence(self):
        """test-gate の返りの走らせ方とログの欄が、証拠の文を開かずに緑の認証の節に届く。ログの無い回は「無い」"""
        suites, log = "一式: run-tests（make test）", str(self.dir / "test.log")
        green = self.green_section(self.final_returned(suites_line=suites, log=log))
        self.assertIn(f"- 最後のテスト（test-gate-final）の走らせ方: engine・{suites}\n", green)
        self.assertIn(f"- 最後のテスト（test-gate-final）のログ: {log}\n", green)
        green = self.green_section(self.final_returned(suites_line=suites))
        self.assertIn(f"- 最後のテスト（test-gate-final）のログ: 無い\n", green)

    def test_green_cert_section_carries_the_baseline_line(self):
        """T35: 最後のテストの返りの修正前のテストの欄（declared_checks.baseline_line）が、緑の認証の節に字のまま届く"""
        base = "修正前のテスト: 緑（元の結末（入力 baseline）の status clean）——最後のテストの赤は修正の後に出た赤でありうる"
        green = self.green_section(self.final_returned(suites_line="一式", baseline_line=base))
        self.assertIn(f"- 最後のテスト（test-gate-final）の{base}\n", green)

    def test_line_values_reach_the_outcome_and_the_report(self):
        """R5b・S48〜S51・S53: 線の collect が渡す線の値が、facts の結末と機械の報告に届く（入力 stops の止めの語が結末に、deferred・
        widened・final-reasons・prior-failures・redepth が報告の節に）。JSON でない線の値は結果を名乗らせない"""
        start = self.pointer("start/start.json", {"run_id": RUN})
        prior = self.pointer("start/prior-failures-in.json", [{"where": "受け付け 計画", "text": "前の run の拒否"}])
        redepth = {"depth": [{"unit_id": "u1", "depth": "標準", "why": "w"}], "skip_optional": "", "raised": ["再審が走った"],
                   "counted": "", "stop_reason": ""}
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_STOPS=json.dumps({"ask-final": "works:needs-human"}),
                                    INPUTS_DEFERRED='["[fork] q1"]', INPUTS_WIDENED='["項目 1: 直した——広げた"]',
                                    INPUTS_FINAL_REASONS='["守りのパスに当たった"]', INPUTS_PRIOR_FAILURES=prior,
                                    INPUTS_REDEPTH=json.dumps(redepth), INPUTS_OPTIONAL='["eyes__"]',
                                    INPUTS_FIX=json.dumps({"done": True, "units": [], "replan_items": ["1"], "refixed": True}))
        self.assertEqual(code, 0)
        self.assertEqual((out["outcome"], out["stop_reason"]), ("needs_human", "ask-final:works:needs-human"))
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        for line in (f"- {runreport.DEFERRED_HEAD}: 1 件\n  - [fork] q1", "  - 案の項目 1: 直した——広げた",
                     f"- {runreport.FINAL_REASONS_HEAD}: 1 件\n  - 守りのパスに当たった", f"- {runreport.PRIOR_IN_HEAD}: 1 件\n  - 受け付け 計画: 前の run の拒否",
                     "  - 標準へ上げた信号: 再審が走った", "- メイングラフのノードの止め: ask-final が works:needs-human"):
            with self.subTest(line=line):
                self.assertIn(line, text)
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_STOPS=json.dumps({"start": "works:start-refused"}))
        self.assertEqual((out["outcome"], out["stop_reason"]), ("stopped_by_line", "start:works:start-refused"))
        code, out = self.run_script("facts", INPUTS_START=start, INPUTS_DEFERRED="{壊れた")
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertIn("入力 deferred が JSON でない", (self.artifacts / out["facts_file"]).read_text(encoding="utf-8"))

    def test_missing_eye_of_a_standard_run_is_not_fixed(self):
        """R14: 直した後の深さが標準（入力 redepth の skip_optional が空）なのに返りの無い目は、結末を fixed にしない（深さで省いた run は数えない）"""
        start = self.pointer("start/start.json", {"run_id": RUN})
        env = {"INPUTS_START": start, "INPUTS_JUDGE": json.dumps({"ready": True, "stop_reason": "", "units": [{"id": "u1"}]}),
               "INPUTS_PLAN": '{"ready": true, "round": 1}', "INPUTS_FIX": json.dumps({"done": True, "units": []}),
               "INPUTS_FINAL_TESTS": '{"ok": true, "green": true}', "INPUTS_SEALED_DIFF": '{"ok": true}',
               "INPUTS_EYES": json.dumps({"ok": True, "r1": {"status": "pass", "reason": ""}, "r2": None, "r3": None, "r4": None})}
        standard = {"depth": [], "skip_optional": "", "raised": [], "counted": "", "stop_reason": ""}
        self.assertEqual(self.run_script("facts", **env, INPUTS_REDEPTH=json.dumps(standard))[1]["outcome"], "round_limit")
        light = {**standard, "skip_optional": "軽量で省いた"}
        self.assertEqual(self.run_script("facts", **env, INPUTS_REDEPTH=json.dumps(light))[1]["outcome"], "fixed")

    def test_returns_with_pointers_reach_the_report(self):
        judgment = self.pointer("judge/judgment.json", {})
        judge = json.dumps({"ready": True, "stop_reason": "", "units": [{"id": "u1"}], "judgment": json.loads(judgment)})
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}), INPUTS_JUDGE=judge)
        self.assertEqual(code, 0)
        self.assertEqual(out["outcome"], "interrupted", "計画の返りが無い")
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn(str(self.artifacts / "judge" / "judgment.json"), text)


class ReplanGiveUpCase(Run):
    """案の直しを終えられなかった項目（計画の役の諦め・事前審査の諦め）は、項目ごとに諦めの訳と裁定の文（字のまま）を前の失敗の行
    （報告と次の run に渡す prior-failures.json）に載せる（元 tests/test_replan.py の test_gave_up_paths_reach_ask_human_verbatim）"""

    def test_gave_up_replan_names_ruling_text_and_reason(self):
        import planblk
        ruling = "RULING-7310 項目 1 の allowed_paths に request_ok.json を足せ"
        why = planblk.PLAN_GAVE_UP_WHY.format(reason="plan の受け付けが 3 回とも拒んだ: 一字も変えずに写す")
        plan = self.pointer("plan/r2/plan-fields.json", {"round": 2, "fields": []})
        judgment = self.pointer("judge/judgment.json", {})
        judge = {"ready": True, "stop_reason": "", "units": [{"id": "u1"}], "judgment": json.loads(judgment)}
        replan = {"ready": False, "round": 2, "plan": json.loads(plan), "gave_up": [{"item": 1, "why": why, "ruling": ruling}]}
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}),
                                    INPUTS_JUDGE=json.dumps(judge), INPUTS_PLAN='{"ready": true, "round": 1}',
                                    INPUTS_REPLAN=json.dumps(replan))
        self.assertEqual(code, 0)
        rows = json.loads((self.artifacts / out["prior_failures"]["path"]).read_text(encoding="utf-8"))
        hit = [r for r in rows if r["where"] == runreport.REPLAN_GAVE_UP_WHERE.format(item=1)]
        self.assertEqual(len(hit), 1, rows)
        self.assertIn(f"裁定の文: {ruling}", hit[0]["text"])
        self.assertIn(why, hit[0]["text"])
        text = (self.artifacts / out["facts_file"]).read_text(encoding="utf-8")
        self.assertIn(ruling, text)


class AcceptScriptCase(Run):
    REPLY = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)
    REDESIGN = json.dumps({"verdict": "redesign-needed", "stops": ["2 行目"], "guessed": [], "decidable": False}, ensure_ascii=False)
    PASS = json.dumps({"verdict": "pass", "stops": [], "guessed": [], "decidable": True})

    def accept(self, reply, cold):
        code, out = self.run_script("report_accept", INPUTS_REPLY=reply, INPUTS_COLD=cold)
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
        note = {"read": [{"path": "lib/runreport.py", "lines": "1", "why": "確かめた"}], "kept": ["訳"],
                "set_aside": [{"option": "案", "why": "訳"}], "open": ["迷い"]}
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
    FELL = runreport.WRITER_FELL.format(error="used up")

    def setUp(self):
        """書き手のループは facts が機械の報告を書いた run でだけ走る（when: ai_go）"""
        super().setUp()
        self.machine = self.artifacts / runreport.OUT_DIR / report.REPORT_FILE
        self.machine.parent.mkdir()
        self.machine.write_text(f"# 報告（run {RUN}）\n\n起きたこと\n\n## 1. 結末\n\n本文\n", encoding="utf-8")

    def test_old_fallen_writer_note_is_dropped_before_the_writer(self):
        """#702: resume で走り直す輪の頭の節は、前の run の返す節が置いた「本文は無い」の行を書き手と初見の読み手より前に外す"""
        before = self.machine.read_text(encoding="utf-8")
        runreport.note_writer_fell(self.machine, {"error": "used up", "quota": True}, run_id=RUN)
        self.assertIn(self.FELL, self.machine.read_text(encoding="utf-8"))
        for _ in range(2):
            code, _ = self.run_script("reject", INPUTS_REASON="", INPUTS_PREV="")
            self.assertEqual(code, 0)
            self.assertEqual(self.machine.read_text(encoding="utf-8"), before)

    def test_previous_answer_passes_through(self):
        for reason, prev in (("", ""), ("2 行目", "report/candidate-report.json")):
            with self.subTest(prev=prev):
                code, out = self.run_script("reject", INPUTS_REASON=reason, INPUTS_PREV=prev)
                self.assertEqual(code, 0)
                self.assertEqual(out, {"reason": reason, "prev": prev, "handoff": handoff.ASK})

    def test_reject_hands_the_ask_and_every_prior_note(self):
        """輪の頭の節の返りの欄 handoff に、住処の頼み handoff.ASK と、使い方 handoff.USE と、前の周までの report/r<n>/handoff.json の
        パスが古い順に在る（今の周の分は無い）。メモを書かなかった周は無いと名指す"""
        redesign = AcceptScriptCase.REDESIGN
        note = {"read": [{"path": "a.py", "lines": "1", "why": "読んだ"}], "kept": ["aの訳"],
                "set_aside": [{"option": "aの案", "why": "訳"}], "open": []}
        replies = [json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": [], "handoff": note}, ensure_ascii=False),
                   json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)]
        for reply in replies:
            code, _ = self.run_script("report_accept", INPUTS_REPLY=reply, INPUTS_COLD=redesign)
            self.assertEqual(code, 0)
        code, out = self.run_script("reject", INPUTS_REASON="x", INPUTS_PREV="y")
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
        self.assertNotIn(str(handoff.path_of(folder / "r3")), part, "今の周の分は無い")
        self.assertNotIn(note["kept"][0], part, "中身は貼らずパスで名指す")


class OutDirCase(unittest.TestCase):
    def test_scripts_draw_the_report_folder_from_lib(self):
        """#372: 報告の置き場の名の持ち主は runreport.OUT_DIR だけ。script は名を字で持たない（名を代入する・パスに足す・
        「名/」で始まる字）"""
        name = runreport.OUT_DIR
        for path in sorted(SCRIPTS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            found = [n.lineno for n in ast.walk(tree)
                     if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and n.value.value == name)
                     or (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                         and any(isinstance(x, ast.Constant) and x.value == name for x in (n.left, n.right)))
                     or (isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith(f"{name}/"))]
            with self.subTest(path.name):
                self.assertEqual(found, [])


class ColdPrepScriptCase(Run):
    def test_body_is_the_human_head(self):
        """初見の読み手に貼る本文は、run の置き場の機械の報告の冒頭と書き手の頭を語の表で言い換えた物（#660）"""
        code, facts = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}))
        self.assertEqual(code, 0)
        writer = json.dumps({"text": "承認ノードで止めた。\n\n## 2. 経緯\n\n長い", "terms": []}, ensure_ascii=False)
        code, out = self.run_script("cold_prep", INPUTS_WRITER=writer)
        self.assertEqual(code, 0)
        self.assertTrue(out["body"].startswith(f"# 報告（run {RUN}）\n\n{gatemarks.HAPPENED}"), out["body"])
        self.assertIn("先へ進めるかを決める所で止めた。", out["body"])
        self.assertNotIn("長い", out["body"])


class CollectScriptCase(Run):
    SCHEMA = NODES["report"]["output_format"]

    def facts(self) -> dict:
        code, out = self.run_script("facts", INPUTS_START=self.pointer("start/start.json", {"run_id": RUN}),
                                    INPUTS_FINAL_ANSWER='{"decision":"stop","text":"止める"}')
        self.assertEqual(code, 0)
        return out

    def collect(self, facts: str, **env) -> dict:
        code, out = self.run_script("collect", INPUTS_FACTS=facts, **env)
        self.assertEqual(code, 0)
        self.assertEqual(validate_schema(out, self.SCHEMA), [], out)
        return out

    def test_without_ai_file_returns_machine_report(self):
        """書き手の輪が落ちた・飛ばされた置き場（report/ai.json が無い）でも機械の報告を返す"""
        facts = self.facts()
        out = self.collect(json.dumps(facts))
        self.assertEqual((out["outcome"], out["ok"]), ("stopped_by_human", False))
        self.assertIsNone(out["report_ai"])
        self.assertEqual(out["report"], facts["report"])

    def test_with_ai_file_returns_ai_report(self):
        """人に向けた報告は機械の冒頭で始まり来歴で終わり、来歴で始まる詳細のファイルが機械の事実を持つ（#660）"""
        facts = self.facts()
        runreport.accept(AcceptScriptCase.REPLY, AcceptScriptCase.PASS, out_dir=self.artifacts / runreport.OUT_DIR)
        out = self.collect(json.dumps(facts))
        self.assertEqual(out["report_ai"]["path"], f"{runreport.OUT_DIR}/{runreport.AI_REPORT_FILE}")
        text = (self.artifacts / out["report_ai"]["path"]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith(f"# 報告（run {RUN}）\n\n{gatemarks.HAPPENED}"), text)
        self.assertRegex(text.splitlines()[-1], rf"^works-factory-report / run {RUN} / 周 — / グラフの版 ")
        self.assertNotIn(report_roles.MACHINE_HEADING, text)
        detail = (self.artifacts / runreport.OUT_DIR / runreport.DETAIL_FILE).read_text(encoding="utf-8")
        self.assertTrue(detail.startswith(f"works-factory-report / run {RUN} / 周 — / グラフの版 "))
        self.assertIn(report_roles.MACHINE_HEADING, detail)

    def test_fallen_writer_is_named_in_the_head_until_resume_rewrites_it(self):
        """#702: 書き手のループ（include の中の節）が使用枠の切れで落ちた run は、機械の報告の冒頭に訳と resume の道が載る。
        resume で書き直した run（記録の最後の行が済んだ行）では、facts が走り直さなくても訳を外し、人に向けた報告を返す"""
        facts = self.facts()
        log = self.dir / "logs" / f"{RUN}.jsonl"
        log.parent.mkdir()
        error = "Loop-group node 'write-loop' failed at iteration 1: 'write': usage or credit limit is used up"
        fell = {"type": "node_error", "step": "report__write-loop", "error": error,
                "execution": {"lifecycle": {"status": "failed", "error": error,
                                            "providerFailure": {"class": "quota_exhausted", "evidence": "e"}}}}
        log.write_text(json.dumps(fell) + "\n", encoding="utf-8")
        env = {"LOG_DIR": str(log.parent), "ARCHON_NODE_EXECUTION": json.dumps({"path": "report__report"})}
        out = self.collect(json.dumps(facts), **env)
        self.assertIsNone(out["report_ai"])
        head = runreport.machine_head((self.artifacts / out["report"]["path"]).read_text(encoding="utf-8"))
        self.assertIn(runreport.WRITER_FELL.format(error=error), head)
        self.assertIn(answer.resume(RUN, env={}), head)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "node_complete", "step": "report__write-loop"}) + "\n")
        runreport.accept(AcceptScriptCase.REPLY, AcceptScriptCase.PASS, out_dir=self.artifacts / runreport.OUT_DIR)
        out = self.collect(json.dumps(facts), **env)
        for got in (out["report"], out["report_ai"]):
            self.assertNotIn("AI が書く報告の本文は無い", (self.artifacts / got["path"]).read_text(encoding="utf-8"))

    def test_ok_is_passed_through_from_facts(self):
        facts = self.facts()
        for ok in (True, False):
            with self.subTest(ok=ok):
                self.assertIs(self.collect(json.dumps({**facts, "ok": ok}))["ok"], ok)

    def test_broken_inputs_are_record_invalid(self):
        good = self.facts()
        cases = {"空": "", "JSON でない": "{壊れた", "欄が欠けた": json.dumps({"report": good["report"]}),
                 "指し札の先が無い": json.dumps({**good, "report": {"type": "archon_artifact", "run_id": RUN, "path": f"{runreport.OUT_DIR}/none.md"}})}
        for name, facts in cases.items():
            with self.subTest(name):
                out = self.collect(facts)
                self.assertEqual((out["outcome"], out["ok"]), ("record_invalid", False))
                self.assertTrue(out["stop_reason"].startswith("report:報告を組めなかった（"))

    def test_fallen_keeps_facts_report_and_carries(self):
        """facts の機械の報告と持ち越しの指し札が在れば、それを指して返る（facts の report.md を上書きしない）"""
        good = self.facts()
        machine = (self.artifacts / good["report"]["path"]).read_text(encoding="utf-8")
        carried = json.loads(self.pointer(f"{runreport.OUT_DIR}/next-request.json", {"findings": []}))
        broken = {**{k: v for k, v in good.items() if k != "stop_reason"}, "next_request": carried}
        out = self.collect(json.dumps(broken))
        self.assertEqual(out["outcome"], "record_invalid")
        self.assertEqual((out["report"], out["next_request"]), (good["report"], carried))
        self.assertEqual((self.artifacts / good["report"]["path"]).read_text(encoding="utf-8"), machine)

    def test_fallen_without_facts_report_writes_another_name(self):
        good = self.facts()
        machine = (self.artifacts / good["report"]["path"]).read_text(encoding="utf-8")
        out = self.collect("{壊れた")
        self.assertEqual(out["report"]["path"], f"{runreport.OUT_DIR}/{runreport.UNWRITTEN}")
        text = (self.artifacts / out["report"]["path"]).read_text(encoding="utf-8")
        self.assertIn("報告を組めなかった", text)
        self.assertNotIn(userenv.NOTE, text)
        self.assertEqual((self.artifacts / good["report"]["path"]).read_text(encoding="utf-8"), machine)
        (self.artifacts / userenv.RAN_FILE).touch()   # #504: 利用者の HOME・XDG で走らせた run は、落ちた報告の冒頭も言う
        self.assertIn(userenv.NOTE, (self.artifacts / self.collect("{壊れた")["report"]["path"]).read_text(encoding="utf-8"))

    def test_without_lib_still_returns(self):
        """lib/ を読めない（入口が渡した根に lib/ が無い）時も、返す節と facts は訳だけのファイルを指して 0 で返る"""
        empty = self.dir / "empty-root"
        empty.mkdir()
        code, out = self.run_script("facts", WORKS_FACTORY_ROOT=str(empty))
        self.assertEqual((code, out["outcome"], out["facts_file"]), (0, "record_invalid", facts_script.LIBLESS))
        self.assertIn("ModuleNotFoundError", (self.artifacts / out["facts_file"]).read_text(encoding="utf-8"))
        out = self.collect("", WORKS_FACTORY_ROOT=str(empty))
        self.assertEqual((out["outcome"], out["report"]["path"]), ("record_invalid", load_script("collect").LIBLESS))

    def test_unwritable_place_is_record_invalid(self):
        good = self.facts()
        blocker = self.dir / "file"
        blocker.write_text("", encoding="utf-8")
        out = self.collect(json.dumps({**good, "report": None}), ARTIFACTS_DIR=str(blocker))
        self.assertEqual(out["outcome"], "record_invalid")


class ConvergeLinesCase(unittest.TestCase):
    """事前審査の往復の報告の行（棚卸しの P119。元 works/tests/test_report.py の test_head_lists_converge_lines）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(os.path.realpath(tmp.name))

    def test_head_carries_plan_converge_lines(self):
        """plan-review の返りの gate の先の converge の行（1 回目に出た割合の句を含む頭の行）が、報告の冒頭の決めの節に
        載る。事前審査のブロックの script を本当に回して返りを作る"""
        r = plan_review.Run(self.dir / "plan-review")
        r.start(features_off=["review_tree"])
        got = r.pass_(plan_review.review(plan_review.MEAN_BLOCK))
        lines = converge.lines(r.view())
        self.assertIn("1 回目の block 1 件", lines[0])
        returns = fixed_run(**{"plan-review": {**got, **{name: str(r.pointed(got[name])) for name in ("review", "gate_passes", "gate")}}})
        decided = outcome.decide_outcome(returns, {}, {"start_ok": True, "record_problems": [], "failed": []})
        built = runreport.build(returns, {}, {}, None, *decided, out_dir=self.dir / runreport.OUT_DIR, start={"run_id": RUN}, run_id=RUN)
        text = pathlib.Path(built["report"]).read_text(encoding="utf-8")
        body = text.split(f"{report.DECISIONS_HEADING}\n\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn(f"- {lines[0]}\n", body)
        for line in lines[1:]:
            self.assertIn(f"{line}\n", body)


class FixtureCase(unittest.TestCase):
    """筋書きを止めた Archon の workflow test で回し、同じ木の validate に誤りも警告も無いことを見る"""

    def test_fixtures_pass_and_validate_is_clean(self):
        with archon.tree(["report"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-report", "--json", "--cwd", str(tree))
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
            self.assertEqual(issues.get("works-factory-report"), [])

    def test_all_empty_and_request_stop_reach_their_words(self):
        """exec-code の筋書きの返す節の出力（dry-run の trace）が、それぞれの結末を返す"""
        for name, word in (("start-missing", "record_invalid"), ("stopped-by-request", "stopped_by_request")):
            with self.subTest(name), archon.tree(["report"]) as tree:
                fixture = yaml.safe_load((BLOCK / "fixtures" / f"{name}.stubs.yaml").read_text(encoding="utf-8"))
                stubs = tree.parent / "stubs.yaml"
                stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")},
                                                allow_unicode=True), encoding="utf-8")
                args = [arg for k, v in (fixture["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
                done = archon.archon(tree, "workflow", "run", "works-factory-report", "--dry-run", "--exec-code", "--stubs", str(stubs),
                                     "--json", *args, "--cwd", str(tree))
                trace = {n["nodeId"]: n for n in json.loads(done.stdout)["trace"]}
                self.assertEqual(json.loads(trace["report"]["output"])["outcome"], word, done.stdout)



PROBE_HEAD = '# /// script\n# requires-python = ">=3.12"\n# dependencies = []\n# ///\n'
PROBE = {
    "works-factory-probe.yaml": """name: works-factory-probe
description: report の読み手に本物の run の記録と一覧を渡す試し
nodes:
  - id: make
    script: make
    runtime: uv
    output_type: probe-kind
  - id: boom
    script: boom
    runtime: uv
    depends_on: [make]
  - id: read
    script: read
    runtime: uv
    depends_on: [boom]
    trigger_rule: all_done
""",
    "scripts/make.py": PROBE_HEAD + 'import json\nprint(json.dumps({"a": 1}))\n',
    "scripts/boom.py": PROBE_HEAD + 'import sys\nsys.exit("boom")\n',
    "scripts/read.py": PROBE_HEAD + """import json, os, shutil
out = os.environ["ARTIFACTS_DIR"]
shutil.copy(os.environ["TYPED_ARTIFACTS_FILE"], os.path.join(out, "listing-copy.json"))
keys = ("LOG_DIR", "WORKFLOW_ID", "ARCHON_NODE_EXECUTION")
with open(os.path.join(out, "env.json"), "w", encoding="utf-8") as f:
    json.dump({k: os.environ.get(k, "") for k in keys}, f)
print("{}")
""",
}


class RealRunCase(unittest.TestCase):
    """止めた Archon で本物の run（dry-run でない）を 1 回回し、実行基盤が書いた run の記録と型つきの成果物の一覧を、
    手で組んだ見本でなく本物の出力のまま runreport.transcript_facts と facts.listing に読ませる（欄の名が変われば赤）"""

    def test_readers_read_a_real_run(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        with tempfile.TemporaryDirectory() as tmp:
            flows = pathlib.Path(tmp)
            for rel, text in PROBE.items():
                (flows / "probe" / rel).parent.mkdir(parents=True, exist_ok=True)
                (flows / "probe" / rel).write_text(text, encoding="utf-8")
            with archon.tree(["probe"], workflows=flows) as tree:
                done = archon.archon(tree, "workflow", "run", "works-factory-probe", "--no-worktree", "--cwd", str(tree))
                found = sorted((tree.parent / "archon-home").rglob("env.json"))
                self.assertEqual(len(found), 1, f"{done.stdout}{done.stderr}")
                artifacts = found[0].parent
                env = json.loads(found[0].read_text(encoding="utf-8"))
                lines = (pathlib.Path(env["LOG_DIR"]) / f"{env['WORKFLOW_ID']}.jsonl").read_text(encoding="utf-8").splitlines()
                rows = [json.loads(x) for x in lines if x.strip()]
                facts = runreport.transcript_facts(rows, optional=("boom",))
                self.assertTrue(facts["ok"])
                self.assertEqual(facts["failed"], [])
                self.assertEqual([a["node"] for a in facts["absorbed"]], ["boom"])
                self.assertEqual(runreport.transcript_facts(rows)["failed"], ["boom"], "受け止めると宣言していない段の落ち")
                self.assertIn("boom", facts["errors"]["boom"])
                self.assertLessEqual({"make", "boom", "read"}, set(facts["minutes"]))
                got = facts_script.listing(str(artifacts / "listing-copy.json"), str(artifacts), env["WORKFLOW_ID"],
                                    env["ARCHON_NODE_EXECUTION"])
                self.assertEqual(got["warnings"], [])
                self.assertEqual([(r["node"], r["body"]) for r in got["by_type"]["probe-kind"]], [("make", {"a": 1})])
                self.assertEqual(facts_script.boundary.own_prefix(env["ARCHON_NODE_EXECUTION"]), "")


# 書き手と初見の読み手の役が起こす Claude Code の代わり（Archon の claude provider が話す stream-json の最小の形）。認証のトークンが
# SPENT の時だけ、書き手は使用枠の切れ（SDK の billing_error。Archon は quota_exhausted と読む）で落ちる。ほかは型に合う答えを返す
FAKE_CLAUDE = """import json, os, sys
if sys.argv[1:2] == ["plugin"]:
    print("[]")
    sys.exit(0)
def say(doc):
    print(json.dumps(doc, ensure_ascii=False), flush=True)
schema = {}
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("type") == "control_request":
        schema = msg["request"].get("jsonSchema") or {}
        say({"type": "control_response", "response": {"subtype": "success", "request_id": msg["request_id"], "response": {}}})
    elif msg.get("type") == "user":
        break
session = "fake-session"
say({"type": "system", "subtype": "init", "session_id": session, "model": "sonnet", "tools": [], "plugins": [], "mcp_servers": []})
cold = "verdict" in schema.get("properties", {})
if not cold and os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") == "SPENT":
    words = "Claude AI usage limit reached"
    say({"type": "assistant", "session_id": session, "error": "billing_error",
         "message": {"model": "<synthetic>", "role": "assistant", "content": [{"type": "text", "text": words}]}})
    say({"type": "result", "subtype": "success", "is_error": True, "session_id": session, "result": words,
         "terminal_reason": "api_error", "num_turns": 1})
    sys.exit(1)
answer = ({"verdict": "pass", "stops": [], "guessed": [], "decidable": True} if cold else
          {"text": "依頼で止めた。\\n直した物は無い。\\n次の run に渡す物は無い。", "terms": [],
           "handoff": {"read": [], "kept": [], "set_aside": [], "open": []}})
say({"type": "result", "subtype": "success", "is_error": False, "session_id": session, "num_turns": 1, "total_cost_usd": 0,
     "result": json.dumps(answer, ensure_ascii=False), "structured_output": answer})
"""
SPENT = "SPENT"
# メイングラフの写し: report を include し、後ろに報告を読むノードを置く（書き手のループの節の id は include の頭つき）
REPORT_LINE = """name: works-factory-report-line
description: report を include したメイングラフの写し
nodes:
  - id: report
    include: works-factory-report
    with:
      final-answer: '{"decision":"stop","text":"request: 止め札"}'
  - id: after
    bash: echo after
    depends_on: [report]
    trigger_rule: all_done
    mutates_checkout: false
"""


class WriterRunCase(unittest.TestCase):
    """#702 の筋書き: 止めた Archon で報告のブロックを include したグラフを本物の run（dry-run でない）で回し、書き手の役を偽の
    Claude Code に替える。書き手が通る筋は人に向けた報告が載る。使用枠の切れで落ちる筋は run が failed で終わり、機械の報告の冒頭に
    訳と resume の道が載り、別のアカウント（別のトークン）で resume すると書き手のループと返す節と後ろが走り直して本文が載る"""

    def setUp(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.fake = pathlib.Path(tmp.name) / "claude"
        self.fake.write_text(f"#!{sys.executable}\n{FAKE_CLAUDE}", encoding="utf-8")
        self.fake.chmod(0o755)
        self.flows = pathlib.Path(tmp.name) / "flows"
        shutil.copytree(BLOCK, self.flows / "report", ignore=shutil.ignore_patterns("__pycache__"))
        (self.flows / "report-line").mkdir()
        (self.flows / "report-line" / "works-factory-report-line.yaml").write_text(REPORT_LINE, encoding="utf-8")

    def drive(self, tree, *args, token):
        return archon.archon(tree, "workflow", *args, "--cwd", str(tree), CLAUDE_BIN_PATH=str(self.fake),
                             CLAUDE_CODE_OAUTH_TOKEN=token)

    def run_line(self, tree, token) -> tuple[dict, list]:
        done = self.drive(tree, "run", "works-factory-report-line", "--no-worktree", token=token)
        return self.state(tree, f"{done.stdout}{done.stderr}")

    def state(self, tree, said="") -> tuple[dict, list]:
        """(run の行, 節の出来事 (種, 節) の並び)"""
        runs = json.loads(archon.archon(tree, "workflow", "runs", "--json", "--cwd", str(tree)).stdout)["runs"]
        self.assertEqual(len(runs), 1, said)
        return runs[0], [(e["event_type"], e["step_name"]) for e in self.events(tree, runs[0]["id"])
                         if e["event_type"].startswith("node_")]

    def events(self, tree, run_id) -> list:
        return json.loads(archon.archon(tree, "workflow", "get", run_id, "--json", "--verbose", "--events",
                                        "--cwd", str(tree)).stdout)["events"]

    def written(self, tree, run_id) -> dict:
        """run の置き場の report/ のファイルの名 → 中身"""
        return {p.name: p.read_text(encoding="utf-8")
                for p in (tree.parent / "archon-home").rglob(f"runs/{run_id}/{runreport.OUT_DIR}/*.md")}

    def test_writer_passes_and_the_human_report_is_written(self):
        with archon.tree(["report", "report-line"], workflows=self.flows) as tree:
            run, events = self.run_line(tree, "FRESH")
            files = self.written(tree, run["id"])
        self.assertEqual(run["status"], "completed", events)
        self.assertIn(("node_completed", "report__write-loop"), events)
        self.assertIn(runreport.AI_REPORT_FILE, files)
        self.assertNotIn("AI が書く報告の本文は無い", files[report.REPORT_FILE])

    def test_quota_fall_fails_the_run_and_resume_with_another_account_writes_the_body(self):
        with archon.tree(["report", "report-line"], workflows=self.flows) as tree:
            run, first = self.run_line(tree, SPENT)
            fallen = self.written(tree, run["id"])
            resumed = self.drive(tree, "resume", run["id"], token="FRESH")
            again, both = self.state(tree, f"{resumed.stdout}{resumed.stderr}")
            files = self.written(tree, run["id"])
            prepped = [json.loads(e["data"]["node_output"])["body"] for e in self.events(tree, run["id"])
                       if (e["event_type"], e["step_name"]) == ("node_completed", "report__write-loop.cold-prep")]
        self.assertEqual(run["status"], "failed", first)
        self.assertIn(("node_failed", "report__write-loop"), first)
        self.assertIn(("node_completed", "report__report"), first, "返す節は書き手が落ちても走る")
        self.assertNotIn(runreport.AI_REPORT_FILE, fallen)
        head = runreport.machine_head(fallen[report.REPORT_FILE])
        self.assertIn("AI が書く報告の本文は無い。書き手のノードが落ちた（Loop-group node 'report__write-loop' failed", head)
        self.assertIn(answer.resume(run["id"], env={}), head)
        self.assertEqual(again["status"], "completed", f"{resumed.stdout}{resumed.stderr}")
        later = both[len(first):]
        for ran in ("report__write-loop", "report__report", "after"):
            self.assertIn(("node_completed", ran), later)
        self.assertNotIn(("node_completed", "report__facts"), later, "facts は走り直さない")
        self.assertEqual(len(prepped), 1, both)
        self.assertNotIn("AI が書く報告の本文は無い", prepped[0], "初見の読み手に貼る本文に前の run の訳を残さない")
        self.assertIn(runreport.AI_REPORT_FILE, files)
        for name in (report.REPORT_FILE, runreport.AI_REPORT_FILE):
            self.assertNotIn("AI が書く報告の本文は無い", files[name], name)


if __name__ == "__main__":
    unittest.main()
