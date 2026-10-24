"""食い違いの申し出（修正役と TDD の輪の役の出口。持ち主 2026-09-28「おしで」）。

緑にするためにテスト・依頼・コードのどれかを曲げる代わりに、役は「どちらも同時には成り立たない」を証拠つきで返してよい
（ImpossibleBench arXiv 2510.20270: 食い違いを申し出る道を明示すると、テストを曲げる不正が 54% から 9% に減った）。
申し出は拒否に数えず、その単位だけを止め（parked）、ほかの単位は進む。止めた単位は読むだけの裁定役が、持ち主の決まり
（principles）で fix_test_scope・fix_code_as・ask_human・replace_query・fix_plan_item・rejudge のどれかに裁き、ask_human だけが最後の人の
関所に届く。rejudge は組どうしの合わせの申し出（JOIN_SOURCE。持ち主の決め clash-goes-to-ruling）にだけ許す判定のやり直しで、
裁定の文が修正の出力の異議になって再審に渡る（rejudge_texts）。直す裁定でないので、その単位は直す義務から外れる。
fix_plan_item は承認済みの修正案の項目そのものの誤りで、その単位は直す義務から外し、同じ run の中で修正案の役が
その項目だけを直して事前審査と人の関所の決まり（replan-gate）を通ってから、2 回目の修正の段で直す（依頼 226。案を直せなければ
諦めて ask_human の道に合流する）。範囲 limits を持たず、テストの変更の許しを作らない（直す裁定 FIX_DECISIONS に入れない）。
判定者の問い（class_query）が直した後の正しい形にも当たる時は、which_is_right: query と正しい行（correct_lines）で申し出て、
裁定 replace_query が新しい問いを例（hits・misses と correct_lines）で機械に試させてから置き換える（Semgrep の規則の試験の ruleid・ok）。

このモジュールが持つ物（b は fix の run の置き場のフォルダのパス。その作業ファイル FILE {"items": [...]} と置き場の trace.jsonl の行（fixboard.trace）。どのブロック・ラインの名も書かない）:
- ITEM_SCHEMA・CONFLICTS_SCHEMA: 1 件の形（unit_key・between・why_both_cannot_hold・which_is_right・kind。query なら correct_lines も）と、
  修正役の返答の欄 conflicts。kind は食い違いの起きた場面の種類で、DIV_KINDS の 6 つ（brief_vs_judgment・unnamed_test_broke・
  not_red・scope_needed・query_hits_fixed・needs_context）のどれか。which_is_right（どちらが正しいか）とは別の軸で、
  query_hits_fixed は which_is_right query と対、needs_context は which_is_right unknown と対
- WORD: superpowers の実装役の状態の語（NEEDS_CONTEXT・BLOCKED）を読み替える works の語（216 の seams.json の words の値と同じ綴り）。
  この語に読み替えた出口は conflicts[] の 1 件で、kind は役が DIV_KINDS から選ぶ。機械は状態の語から種類を推さない
- problems(items, repo=, board_dir=, owed=, try_query=, briefs=): 機械の確かめ。形・義務の単位か・重なり・名指した所が在るか
  （<パス>:<行>。依頼の行・テストの行・コードの行が現物に在る）・query の申し出の correct_lines に判定者の問いが当たるか・kind が
  DIV_KINDS のどれかで which_is_right と対になるか・brief_vs_judgment ならその単位の brief の行を between に名指すか（briefs は
  planbrief.by_unit_at の形 {unit_key: [{item, file}]}。None と {} は brief の無い run）。文の一覧（空なら通る）
- brief_cite_problem(key, cites, repo, briefs, what, field): brief を誤りと言う物（申し出 brief_vs_judgment・裁定 fix_plan_item の
  grounds）が、その単位の brief の行を名指すかの確かめ（1 つの決まり）
- park(b, items, source=, ruling=None, round_=1): 止めた単位を置き場の作業ファイルに積み、trace に 1 行（同じ申し出は積み増さない）
- clash_claims(unit_ids, between, why)・mark_clash_patch(b, ids, patch): 組どうしの合わせの申し出（JOIN_SOURCE）の行の形と、
  その行に組の直しの控えの差分を置く口（直しの在りかは REVERTED）。積むのは lib/clash.py
- rejudge_texts(rows): 裁定 rejudge の文（修正の出力の異議に足す）
- items(b)・unruled(b)・asked(b)・ruled_fix(b)・replaced_queries(b)・counts(b)・
  kind_counts(b): 読む口。asked・waiting・counts・kind_counts の述語は行の並びを受ける asked_rows(rows)・waiting_rows(rows)・
  counts_of(rows)・kind_counts_of(rows) が持つ（置き場を開かずに読んだ行にも同じ読みを当てる）。decision(row) は裁定の語（裁定が
  dict でない行は None）
- held_by_rulings(b)・ruled_units(row): 直す義務から外す単位と理由。決まりは「直す裁定（FIX_DECISIONS）でない裁定は、それが外す
  単位（申し出の単位と、fix_plan_item ならその項目に載る単位の全部）を直させない」の 1 つ
  （kind の無い前の形の控えの行も読む。種類は「無し」）
- replan_rows(rows, n, unit_keys): 裁定 fix_plan_item の行のうち案の項目 n を名指す物（案の直しの材料が読む 1 つの選び）
- apply_rulings(b, rulings, by=): 裁定を積み、trace に 1 行。裁定の文のファイル（RULINGS_FILE。修正役が Read する）は fix の
  src/rulings.py が書く（約束の文は fix の prompts/parts/ruling-promise.md）。裁定の文と申し出の回の控え（PARKED_REPLY）は今の
  scope の周の置き場の物（2 回目の修正の段は 1 回目と分かれる）。
  fix_plan_item の裁定は、受け付けた機械が欄 plan_items（その単位の brief の項目の番号）と plan_units（その項目に載る単位の全部）を
  足して渡す
- owed_units_but_asked・fix_duty・nothing_owed_but_excused: 盤面の記録を読んだので、値を引数で受ける形に書き直して fixboard に置いた
- test_permits(b, rulings=, source=, skip_ids=, base=): テストの変更の許し（承認済みの修正案の rewrite_tests・範囲の相談の合意・裁定 fix_test_scope の範囲・
  案の直しで直した項目の単位。keep-essence の 3 の 1 本の道）の唯一の元。凍結の検査・事後の関門・範囲の照らし・最後の関所は
  ここから引く。permitted_units(b) はそのうち単位で許す行の単位。source を渡すと、修正案の行の範囲をその木でテストの id から引き直し、
  範囲の相談の合意の行（修正前の版の行。読む木は 1 つ）は base（修正前の版の読み口）を使ってその木の行へ移す。
  skip_ids に並べた id の修正案の行は外す（TDD の輪が赤→緑を確かめた書き換え。輪の後に書き換えさせない）。
  修正案の欄の控え plan-fields.json（置き場の物。周は round_）が凍結の印と食い違えば（planmarks.FieldsBroken）、許しを引かずに
  控えを名指す理由の ValueError（止めるのは呼び手。fields_broken の stop）
- frozen_fields(b): 今の周の凍結した修正案の欄の並び（TDD の輪が単位の約束を組む元）。食い違いは test_permits と同じ 1 か所の
  文で ValueError（止めるのは呼び手）
- ruled_test_doc(b): テストの変更の許し（承認済みの修正案の rewrite_tests と裁定 fix_test_scope の範囲。test_permits）が名指した
  テストのファイルを、守りのファイルの一覧（protect）の形にした物（最後の関所に出す）
- ruled_limits(b, decisions=): 直す裁定の範囲 limits を (申し出の行, 範囲) で並べる唯一の読み口（test_permits と blk-fix の
  planscope が読む）
- edit_permits(b, pass_, round_=): 修正の段の事後の関門が既存のテストの本体の変更を許す名指しの id と範囲（test_permits から引く。修正役の指示書も貼る）
- edit_rulings(b, pass_): edit_permits に裁定 fix_test_scope の範囲が入るか（段 ruled か 2 回目の修正の段）
- ruled_test_limits(b, rulings=, source=, skip_ids=, base=)・parse_limit(lim): テストの変更の許し（承認済みの修正案の rewrite_tests と裁定
  fix_test_scope の範囲。test_permits）の範囲の文字列と、その 1 つの読み（TDD の輪の凍結が範囲の中の直しを通す）
- human_lines(b): 最後の関所と報告に載せる ask_human の行（諦めた fix_plan_item の行も。裁定役の人に回す訳 ASK_WHY と、末尾に案の直しの理由と、単位の直しの
  在りか place_words を添える）
- fix_place(rows)・place_words(rows)・unit_rows(rows, key): 人に回した単位の直しの在りか（IN_DIFF・REVERTED・LEFT・KEPT）を単位の
  行の全部から選ぶ 1 か所と、その言い方。関所の行・直す義務から外す理由・次の依頼・裁定へ回した理由はここから引く
- mark_reverted(b, files, patch, pass_): 機械が files を段の頭へ戻した時、それを名指す query_hits_fixed の行のうち今の段
  pass_ の受け付けが積んだ行（FILED_IN。直しが段の頭より後で、控えに移った）に控えの patch を置く（place_words が「直しは差分に
  在り」でなく控えを名指す。段の頭より前の行の直しは頭の木に在り、戻しても差分に残る）
- 案の直しの状態（依頼 226。裁定 fix_plan_item の行の欄 REPLAN_STATE）: apply_rulings が WAITING に置き、set_replan の 1 か所だけが
  AMENDED（項目を直した。held_by_rulings が外さず直す義務に戻す）か GAVE_UP（諦めた。asked に入り ask_human の行として並ぶ）に
  移す（trace の行 REPLAN_OP）。読む口は replan_state(row)・waiting(b)・amended_keys(b)
- 2 回目の修正の段（同じブロックの 2 度目の差し込み。置き場が分かれる）は、1 回目の段の行を adopt_prior(b, prior, items) で自分の
  置き場に写して読む（元は 1 つの盤面に両方の段の行が在った。second_pass・amended_rows_by_unit・test_permits が
  1 回目の裁定と案を直した行を見る）。写した行は印 PRIOR を持ち、this_pass(b) はそれを外した今の段の行（組の子の結果に載せる行）
標準ライブラリだけ。期限は持たない。
"""
import json
import os
import pathlib
import posixpath
import re
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:   # 写しの engine（engine.util の Reject）
    sys.path.insert(0, str(_CORE / "graphloops"))

import cite  # noqa: E402
import fixboard  # noqa: E402  （置き場の trace.jsonl への 1 行）
import globs  # noqa: E402
import oneline  # noqa: E402
import planmarks  # noqa: E402  （planmarks は conflict・entry を読まないので輪にならない）
import stopby  # noqa: E402  （L1。止めの理由の住処）
from engine.util import Reject  # noqa: E402  （上の行が写しの engine を sys.path に足す）

FILE = "conflicts.json"                 # 盤面の今の周の作業ファイル {"items": [...]}
ITEMS = "items"                         # FILE の行の並びの欄（報告と結末の読み手が引く）
RULING = "ruling"                       # 行の裁定の欄 {decision, text, limits}
DECISION = "decision"                   # 裁定の語の欄（DECISIONS のどれか）
RULINGS_FILE = "conflict-rulings.md"    # 裁定の文（修正役が 2 回目の起動の 1 行目で Read する。R44）。今の scope の周の置き場（2 回目の修正の段は 1 回目と分かれる）
PARKED_REPLY = "fix-parked-reply.json"  # 申し出を返した回の修正役の返答（裁定の後の出し直しで読む）。同じく今の scope の周の置き場
KIND_FIELD = "kind"                      # 申し出の種類の欄（食い違いの起きた場面。which_is_right とは別の軸）
WHY_FIELD = "why_both_cannot_hold"       # 申し出の理由の欄（なぜ両方は同時に成り立たないか）
WHICH_FIELD = "which_is_right"           # 正しいと見た側の欄（WHICH のどれか）
FIELDS = ("unit_key", "between", WHY_FIELD, WHICH_FIELD, KIND_FIELD)
CORRECT = "correct_lines"               # which_is_right: query の時だけ要る欄（直した後の正しい行の写し）
QUERY = "query"                         # 判定者の class_query が直した後の正しい形にも当たる
REPLACE = "replace_query"               # 問いを置き換える裁定（新しい問いを hits・misses と申し出の correct_lines で試す）
ASK = "ask_human"
ASK_WHY = "ask_why"                     # 裁定役の ask_human の欄 {changes, line}: 人の答えで何が変わるか（ASK_CHANGES）と 1 行の訳
ASK_CHANGES = {"direction": "直しの向き", "scope": "直しの範囲"}   # 人に回してよい訳（人の答えで変わる物）と、関所の行の言い方
NAME_ONLY = "name_only"                 # 名の重なりだけ（字が同じ名）。訳に書けば受け付けが拒み、裁定役が自分で決める
ACCEPT_PARKED_OP = "fix_bound_parked"   # 修正の受け付け（blk-fix）が最後の回に止めた単位の trace の行の語。書くのは accept、読むのは報告と最後の関所
REPLAN = "fix_plan_item"                # 案の項目そのものが誤りと裁く（同じ run の中で案を直して事前審査に掛けてから直す）
REJUDGE = "rejudge"                     # 判定の単位の切り方が誤りと裁く（組どうしの合わせの申し出 JOIN_SOURCE にだけ。裁定の文が修正役の異議になり再審へ）
DECISIONS = ("fix_test_scope", "fix_code_as", ASK, REPLACE, REPLAN, REJUDGE)
FIX_DECISIONS = ("fix_test_scope", "fix_code_as", REPLACE)   # 直す裁定（REPLAN は直さないので入れない）
PLAN_ITEMS = "plan_items"               # 盤面の裁定の行に機械が足す欄（REPLAN の単位の brief の項目の番号）
PLAN_UNITS = "plan_units"               # 同じく機械が足す欄（PLAN_ITEMS の項目に載る単位の全部。held_by_rulings が外す）
MIN_WHY = 10
MIN_CITES = 2
MAX_LINES = 20
# 申し出の種類（kind の値。設計の 4 つと、今の道を残す 2 つ）
BRIEF_VS_JUDGMENT = "brief_vs_judgment"     # brief と、判定・依頼・承認ノードで答えた条件が食い違う
UNNAMED_TEST_BROKE = "unnamed_test_broke"   # 名指していない既存のテストが、直すと落ちる・外すしかない
NOT_RED = "not_red"                         # 受け入れのテスト・名指しの書き換えが、案どおりに書いても赤にならない
SCOPE_NEEDED = "scope_needed"               # brief や案の範囲の外を触らないと緑にならない・問いの数え直しが閉じない
QUERY_HITS_FIXED = "query_hits_fixed"       # 判定の問いが直した後の正しい形にも当たる（which_is_right query と対）
NEEDS_CONTEXT = "needs_context"             # 材料から決められず人か依頼の答えが要る（which_is_right unknown と対）
DIV_KINDS = (BRIEF_VS_JUDGMENT, UNNAMED_TEST_BROKE, NOT_RED, SCOPE_NEEDED, QUERY_HITS_FIXED, NEEDS_CONTEXT)
UNKNOWN = "unknown"                     # which_is_right: どれが正しいか決められない（needs_context の対）
WHICH = ("request", "test", "code", UNKNOWN, QUERY)
UNSET = "unset"                         # kind_counts の鍵: kind の無い前の形の行
WORD = "divergence"                     # superpowers の状態の語を読み替える works の語（216 の seams.json の words と同じ綴り）
KIND = "conflict"                       # process.human_items の行の kinds（申し出の種類 KIND_FIELD とは別物）
HEAD = "食い違いの申し出"                # 最後の関所の文の節の見出し・報告の行の頭
RULED_TEST_ID = "conflict-ruling"       # 裁定が許したテストの変更を守りのファイルの行にする時の id の頭
PLAN_TEST_ID = "plan-rewrite"           # 承認済みの修正案が名指した既存テストの書き換えを守りのファイルの行にする時の id の頭
REMOVES_TEST_ID = "plan-removes"        # 承認済みの修正案の項目の files の change=remove の symbol（消す名）を本体で名指す既存テストの書き換え・消しの許しの行の id の頭
AGREED_TEST_ID = "plan-agreed"         # 範囲の相談で修正案を書いた役が許したテストの書き換えを守りのファイルの行にする時の id の頭
BROKEN_TEST_ID = "broken-before"       # 関わる試験で直す前から壊れていた物（修正役がついでに直してよい。#836）の許しの行の id の頭
BROKEN_TESTS_FILE = "broken-tests.json"  # 置き場のその試験の控え {tests: [{path, ids}]}（fix の TDD の輪の頭が書く。test_permits が読む）
AMENDED_TEST_ID = "plan-amended"        # 案の直しで直した項目の単位の前の輪の受け入れのテストの許しの行の id の頭（範囲の文字列を持たない）
# 範囲の相談（修正役が返答の欄 consult で頼み、修正の輪の答えの節が修正案を書いた役の会話の続きで答える。設計
# docs/plans/2026-10-06-ask-planner.md）の 1 問 1 答の trace の行の語。書くのは修正の輪の確かめの節（sandbox の外の機械）、
# 読むのは agreed（範囲とテストの許し）と報告
ASKED_OP = "plan_scope_asked"
CONSULT_FIELD = "consult"   # 修正役の返答の任意の欄: 範囲の相談の頼み（在れば受け付けはその周を回さず、答えの節が答える）
CONSULT_MIN_WHY = 10        # 頼みの理由（why・blocked）の下限の字数（修正役の返りの形 &fix_reply の consult の minLength と同じ字。試験が結ぶ）
FIELDS_TAMPERED = f"承認済みの修正案の欄の控え（共有ボードの {planmarks.FIELDS_FILE}）が受け付けの後に書き換えられた。"
FIELDS_BROKEN = FIELDS_TAMPERED + "テストの変更の許しを引かずに止めた"   # 修正の段（by stopby.FIX）の止めの文
FIX_SOURCE = "fix"                       # 盤面の行の出どころの欄 source の値: 修正役の申し出（受け付けと修正役の並べが積む）
TDD_SOURCE = "tdd"                       # 同じく: TDD の輪の役の申し出（phase conflict）
GAVE_UP_SOURCE = "tdd-gave-up"           # 同じく: 3 回拒まれて機械が止めた単位の申し出（人が読む理由の文でなく、この値で見分ける）
JOIN_SOURCE = "join-clash"               # 同じく: 組を親の木へ当てて赤になり、合わせ役が直せなかった組の単位の申し出（機械が積む。clash_claims）
SOURCES = (FIX_SOURCE, TDD_SOURCE, GAVE_UP_SOURCE, JOIN_SOURCE)
REPEAT_GAVE_UP = ("案を直して作り直した後に、同じ単位が TDD の確認の上限まで落ちた（案を直した行 {prior}）。機械で回し続けず、"
                  "設計を疑う判断を人に回す")   # 作り直した後の諦めの ask_human の裁定の文
PARK_OP, RULE_OP = "conflict_parked", "conflict_ruled"   # trace の行
# 案の直しの状態（裁定 REPLAN の行の欄。依頼 226）。WAITING → AMENDED か GAVE_UP の 2 つの移りだけ（set_replan）
REPLAN_STATE = "replan"                 # 裁定の行の欄（apply_rulings が REPLAN の行に必ず置く）
WAITING = "waiting"                     # 案の直しを待つ（単位は直す義務の外）
AMENDED = "amended"                     # 項目を直した（単位は直す義務に戻る）
GAVE_UP = "gave_up"                     # 諦めた（ask_human の行として最後の関所と次の run の依頼に届く）
REPLAN_WHY = "replan_why"               # 移した理由の欄（諦めた理由。human_lines が末尾に添える）
REPLAN_OP = "replan_state"              # trace の行 {id, unit_key, state, why}
HELD_WORK_KEPT = "この run の修正の段で直した分は作業ツリーに残した"   # 諦めた行の直しの在りか（1 回目・2 回目の段のどちらで諦めても。約束・関所・次の依頼）
# 人に回した単位の直しの在りか（fix_place の種と place_words の言い方。関所と次の依頼の行）
IN_DIFF, REVERTED, LEFT, KEPT = "in_diff", "reverted", "left", "kept"
UNFIXED_LEFT = "直さずに残した"
FIX_IN_DIFF = f"{fixboard.FIX_IN_DIFF_CORE}が人の決め待ち"
FIX_REVERTED = UNFIXED_LEFT + "（戻した直しの控え {patch}）"
REVERTED_FIELD = "reverted_to"          # 名指したファイルを機械が段の頭へ戻した query_hits_fixed の行に置く控えの patch（mark_reverted）
FILED_IN = "filed_in"                   # 裁定の後の段の受け付けが積んだ行の印（park の pass_ の ruled だけ。mark_reverted が読む）
PRIOR = "prior_pass"                    # 2 回目の修正の段の置き場に写した 1 回目の段の行の印（adopt_prior が置く。新しい）

ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(FIELDS),
    "properties": {
        "unit_key": {"type": "string", "minLength": 1},
        "between": {"type": "array", "minItems": MIN_CITES, "items": {"type": "string", "minLength": 3}},
        WHY_FIELD: {"type": "string", "minLength": MIN_WHY},
        WHICH_FIELD: {"type": "string", "enum": list(WHICH)},
        KIND_FIELD: {"type": "string", "enum": list(DIV_KINDS)},
        CORRECT: {"type": "array", "minItems": 1, "maxItems": MAX_LINES, "items": {"type": "string", "minLength": 1}},
    },
}
CONFLICTS_SCHEMA = {"type": "array", "items": ITEM_SCHEMA}


# ---------------------------------------------------------------- 名指しの確かめ


def no_requests(requests) -> bool:
    """依頼の行を持たずに始めた run か（依頼の数 requests が 0。値は呼び手〔line〕が始めの記録の入口の入力の形 input.requests から
    渡す。入口の種類は見ない）。依頼を読むブロックの intake はこの run でだけ空の依頼を受ける（ブロックを単独で回した時・依頼の在る
    run・入力の形の無い控え〔None〕の空は今までどおり欠け）。始めの記録は読まない（integration.md 4.3-追加-6）"""
    return requests == 0


def cite_roots(request_file, root) -> list:
    """受け付けが名指しを許す、作業ツリーの外の根（依頼のファイル request_file〔無ければ空〕と、root。値は呼び手が渡す）"""
    return [str(request_file or ""), str(root)]


def _correct_problem(it, try_query) -> str:
    """which_is_right: query の申し出の correct_lines の確かめ（通れば空）。try_query(unit_key, lines) が渡れば、判定者の問いを
    その行に当てた結果の文（当たれば空）を足す"""
    lines = it.get(CORRECT)
    if it[WHICH_FIELD] != QUERY:
        return f"{CORRECT} は {WHICH_FIELD} が {QUERY} の時だけ書く" if CORRECT in it else ""
    if not isinstance(lines, list) or not lines or len(lines) > MAX_LINES \
            or not all(isinstance(x, str) and x.strip() for x in lines):
        return (f"{WHICH_FIELD} が {QUERY} なら {CORRECT} に、判定者の問いが当たってしまう直した後の正しい行を 1〜{MAX_LINES} 行"
                "写す（機械が問いを当てて確かめる）")
    return try_query(it["unit_key"], lines) if try_query else ""


def _kind_problem(it, at) -> str:
    """種類の欄 kind の確かめ（通れば空。外れなら at を頭に入れた仕上がりの文）: DIV_KINDS のどれかで、query_hits_fixed ⇔
    which_is_right query、needs_context なら which_is_right unknown。外れの文は両方の欄を名指す（修正役の受け付けと TDD の輪が
    同じ文を返す）"""
    kind, which = it.get(KIND_FIELD), it.get(WHICH_FIELD)
    if kind not in DIV_KINDS:
        return f"{at} の {KIND_FIELD} は {' / '.join(DIV_KINDS)} のどれか（{kind!r}）"
    if (kind == QUERY_HITS_FIXED) != (which == QUERY):
        return (f"{at}: {KIND_FIELD} {QUERY_HITS_FIXED} と {WHICH_FIELD} {QUERY} は対で書く"
                f"（{KIND_FIELD} {kind}・{WHICH_FIELD} {which}）")
    if kind == NEEDS_CONTEXT and which != UNKNOWN:
        return f"{at}: {KIND_FIELD} {NEEDS_CONTEXT} の {WHICH_FIELD} は {UNKNOWN}（{KIND_FIELD} {kind}・{WHICH_FIELD} {which}）"
    return ""


def brief_cite_problem(key, cites, repo, briefs, what: str, field: str) -> str:
    """brief を誤りと言う物（申し出 brief_vs_judgment・裁定 fix_plan_item）の確かめの 1 つの決まり（通れば空。外れなら what と
    field を名指す文）: 単位 key に brief が在り（briefs は planbrief.by_unit_at の形。None と {} は brief の無い run）、名指しの並び
    cites（欄 field）のどれか 1 つのパスがその単位の brief のファイルのどれかと同じ。名指しの行がファイルに在るかは cite.problem が見る"""
    rows = ((briefs or {}).get(key) or []) if isinstance(key, str) else []
    files = [r["file"] for r in rows if isinstance(r, dict) and isinstance(r.get("file"), str)]
    if not files:
        return f"{what} は brief の在る単位だけ（{key} に brief が無い——修正案の無い run には brief が無い）"
    want = {pathlib.Path(f).resolve() for f in files}
    root = pathlib.Path(repo).resolve()
    for c in cites if isinstance(cites, list) else []:
        m = cite.CITE.match(c.strip()) if isinstance(c, str) else None
        if m:
            raw = pathlib.Path(m["path"])
            if (raw if raw.is_absolute() else root / raw).resolve() in want:
                return ""
    return f"{what} の {field} に、この単位の brief の行（{' か '.join(files)}:<行>）が無い"


def _brief_problem(it, at, repo, briefs) -> str:
    """kind brief_vs_judgment の確かめ（通れば空。外れなら at を頭に入れた仕上がりの文）: between がその単位の brief の行を
    名指す（brief_cite_problem）"""
    if it.get(KIND_FIELD) != BRIEF_VS_JUDGMENT:
        return ""
    bad = brief_cite_problem(it.get("unit_key"), it.get("between"), repo, briefs, f"kind {BRIEF_VS_JUDGMENT}", "between")
    return f"{at}: {bad}" if bad else ""


def problems(items, *, repo, board_dir, owed, request_file="", try_query=None, briefs=None) -> list:
    """申し出の一覧の機械の確かめ（受け付けの前）。文の一覧（空なら全部通る）。problems_by_entry の文を順につないだ物"""
    return [t for _, _, lines in problems_by_entry(items, repo=repo, board_dir=board_dir, owed=owed, request_file=request_file,
                                                   try_query=try_query, briefs=briefs) for t in lines]


def problems_by_entry(items, *, repo, board_dir, owed, request_file="", try_query=None, briefs=None) -> list:
    """申し出ごとの機械の確かめ。[(i, 読めた unit_key か None, 文の並び)]（申し出の順。通れば文の並びは空）。key が読めるのは
    dict の申し出の unit_key が str で owed に在る時だけ（欄の崩れ・owed に無い key は None）。配列全体の誤りは [(None, None, [文])]。
    try_query(unit_key, lines) は which_is_right: query の申し出の correct_lines に判定者の問いを当てる口（呼ぶ側が渡す。当たれば空・
    外れれば文）。briefs は今の周の brief の行 {unit_key: [{item, file}]}（planbrief.by_unit_at。None と {} は brief の無い run で、
    brief_vs_judgment を通さない）。名指しを許す作業ツリーの外の根は依頼のファイル request_file（呼び手が値で渡す）と board_dir"""
    if not isinstance(items, list) or not items:
        return [(None, None, ["食い違いの申し出は 1 件以上の配列"])]
    roots = cite_roots(request_file, board_dir)
    seen = set()
    return [(i, *_entry_problems(i, it, repo, roots, owed, seen, try_query, briefs)) for i, it in enumerate(items)]


def _entry_problems(i, it, repo, roots, owed, seen, try_query, briefs) -> tuple:
    """申し出 1 件の (読めた unit_key か None, 文の並び)。seen は今までの申し出の owed の key（2 度申し出た検査）"""
    at = f"食い違い[{i}]"
    if not isinstance(it, dict) or set(it) - {*FIELDS, CORRECT} or any(k not in it for k in FIELDS):
        return None, [f"{at} の欄は {list(FIELDS)}（{WHICH_FIELD} が {QUERY} の時は {CORRECT} も）"]
    out, k = [], it["unit_key"]
    if k not in owed:
        out.append(f"{at} の unit_key {k!r} は今の直す義務の単位に無い（貼られた単位の key を一字も変えずに写す）")
    elif k in seen:
        out.append(f"{at} の unit_key {k!r} を 2 度申し出た（1 単位 1 件。名指しを between に並べる）")
    seen.add(k)
    key = k if isinstance(k, str) and k in owed else None
    if not isinstance(it[WHY_FIELD], str) or len(it[WHY_FIELD].strip()) < MIN_WHY:
        out.append(f"{at} の {WHY_FIELD} が {MIN_WHY} 字に足りない（なぜ両方は同時に成り立たないか）")
    if it[WHICH_FIELD] not in WHICH:
        out.append(f"{at} の {WHICH_FIELD} は {' / '.join(WHICH)} のどれか（{it[WHICH_FIELD]!r}）")
    else:
        bad = _correct_problem(it, try_query)
        if bad:
            out.append(f"{at}: {bad}")
    bad = _kind_problem(it, at) or _brief_problem(it, at, repo, briefs)
    if bad:
        out.append(bad)
    cites = it["between"]
    if not isinstance(cites, list) or len(cites) < MIN_CITES:
        out.append(f"{at} の between は食い違う所を {MIN_CITES} つ以上（依頼の行・テストのファイル:行・コードのファイル:行）")
        return key, out
    out += [f"{at}: {e}" for e in (cite.problem(c, repo, roots) for c in cites) if e]
    return key, out


# ---------------------------------------------------------------- 盤面の作業ファイル
def _path(b) -> pathlib.Path:
    return pathlib.Path(b) / FILE


def _load(b) -> dict:
    try:
        doc = json.loads(_path(b).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"items": []}
    except (OSError, ValueError) as e:
        raise ValueError(f"食い違いの控え {_path(b)} が読めない: {e}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        raise ValueError(f"食い違いの控え {_path(b)} の形が違う（{{items: [...]}}）")
    return doc


def _write(path: pathlib.Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _save(b, doc) -> None:
    _write(_path(b), json.dumps(doc, ensure_ascii=False, indent=1) + "\n")


def items(b) -> list:
    return list(_load(b)["items"])


def unruled(b) -> list:
    return [i for i in items(b) if i.get("ruling") is None]


def decision(row) -> str | None:
    ruling = row.get(RULING)
    return ruling.get(DECISION) if isinstance(ruling, dict) else None


def asked_rows(rows) -> list:
    """人に諮る行: 直す裁定でない裁定（FIX_DECISIONS の外）の行のうち、案の直しを待つ・直した物でない行（ask_human と、
    諦めた fix_plan_item）。rejudge は人でなく再審に回るので入れない"""
    return [i for i in rows if decision(i) not in (None, REJUDGE, *FIX_DECISIONS) and replan_state(i) not in (WAITING, AMENDED)]


def asked(b) -> list:
    return asked_rows(items(b))


def ruled_fix(b) -> list:
    return [i for i in items(b) if decision(i) in FIX_DECISIONS]


def replan_state(row) -> str | None:
    """裁定が fix_plan_item の行の案の直しの状態（欄 REPLAN_STATE）。ほかの裁定・裁いていない行は None"""
    return row.get(REPLAN_STATE) if decision(row) == REPLAN else None


def waiting_rows(rows) -> list:
    """案の直しを待つ行（状態 WAITING）"""
    return [i for i in rows if replan_state(i) == WAITING]


def waiting(b) -> list:
    return waiting_rows(items(b))


def this_pass(b) -> list:
    """今の段の行（adopt_prior が写した 1 回目の段の行 PRIOR を外す）"""
    return [i for i in items(b) if not i.get(PRIOR)]


def adopt_prior(b, prior, todo) -> list:
    """2 回目の修正の段の置き場 b に、1 回目の段の置き場 prior の申し出と裁定の行を印 PRIOR つきで写し（元 conflict.py:411 の
    second_pass が 1 つの盤面で 1 回目の行を見た形）、案の直しを待つ行（WAITING）のうち 2 回目の段が直す計画の項目 todo（項目の
    番号の字）に載る行を AMENDED へ移す（set_replan。元 replan.answer が採った項目の行を移した所）。項目の番号を持たない行（組の
    項目から数えた行）は todo が空でなければ移す。b に行が在れば写さない（再開で 2 度写さない）。prior に FILE が無ければ何もしない。
    写した行の id を返す。prior の FILE が読めなければ ValueError"""
    if _path(b).is_file() or not _path(prior).is_file():
        return []
    rows = [{**r, PRIOR: True} for r in _load(prior)["items"]]
    _save(b, {"items": rows})
    want = {str(n) for n in todo or []}
    moved = [r["id"] for r in rows if replan_state(r) == WAITING and want
             and (not ruled_items(r) or want & {str(n) for n in ruled_items(r)})]
    if moved:
        set_replan(b, moved, AMENDED)
    return [r["id"] for r in rows]


def second_pass(b) -> bool:
    """今の周が 2 回目の修正の段か: 今の周の裁定の行に案を直した行（状態 AMENDED）が 1 つでも在る（案を直して直す義務に戻った
    単位を直すのは 2 回目の修正の段だけ。1 回目の段の行は WAITING か裁定が fix_plan_item でない）"""
    return any(replan_state(i) == AMENDED for i in items(b))


def amended_rows_by_unit(b) -> dict:
    """項目を直した行（状態 AMENDED）が外していた単位（ruled_units。直す義務に戻った単位）ごとの、その行。同じ単位を外す行が
    複数なら先の行"""
    out: dict = {}
    for i in items(b):
        if replan_state(i) == AMENDED:
            for k in ruled_units(i):
                out.setdefault(k, i)
    return out


def amended_keys(b) -> set:
    """項目を直した行（状態 AMENDED）が外していた単位の全部（直す義務に戻った単位）"""
    return set(amended_rows_by_unit(b))


def set_replan(b, ids, state: str, *, why: str = "") -> None:
    """fix_plan_item の行 ids の案の直しの状態を、WAITING から state（AMENDED か GAVE_UP）へ移す唯一の口。GAVE_UP は why
    （諦めた理由）が要る。在れば why を欄 REPLAN_WHY に置き、移した行ごとに trace の行 REPLAN_OP。同じ状態への移りは何もしない
    （再開で同じ移りが 2 度来る）。知らない id・fix_plan_item でない行・WAITING でない行からの移り・ほかの state は ValueError で、
    1 つでも外れれば何も移さない"""
    why = why.strip() if isinstance(why, str) else ""
    if state not in (AMENDED, GAVE_UP):
        raise ValueError(f"案の直しの状態は {WAITING} から {AMENDED} か {GAVE_UP} にだけ移す（{state!r}）")
    if state == GAVE_UP and not why:
        raise ValueError(f"案の直しを諦める（{GAVE_UP}）には理由 why が要る（{list(ids)}）")
    doc = _load(b)
    by_id = {r.get("id"): r for r in doc["items"]}
    moves, bad = [], []
    for rid in dict.fromkeys(ids):
        row = by_id.get(rid)
        now = replan_state(row) if row is not None else None
        if now is None:
            bad.append(f"{rid}（{'知らない id' if row is None else 'fix_plan_item の裁定の行でない'}）")
        elif now == state:
            continue
        elif now != WAITING:
            bad.append(f"{rid}（{now} から {state} へは移さない）")
        else:
            moves.append(row)
    if bad:
        raise ValueError(f"案の直しの状態を {state} に移せない: {'・'.join(bad)}")
    if not moves:
        return
    for row in moves:
        row[REPLAN_STATE] = state
        if why:
            row[REPLAN_WHY] = why
    _save(b, doc)
    for row in moves:
        fixboard.trace(b, REPLAN_OP, id=row["id"], unit_key=row["unit_key"], state=state, why=why)


def ruled_units(row) -> list:
    """1 件の裁定が外す単位（申し出の単位と、fix_plan_item ならその項目に載る単位 PLAN_UNITS。重ねない・申し出の単位が先）"""
    ruling = row.get(RULING)
    return list(dict.fromkeys([row.get("unit_key"), *((ruling.get(PLAN_UNITS) if isinstance(ruling, dict) else None) or [])]))


def ruled_items(row) -> list:
    """1 件の裁定が誤りとした案の項目の番号（ruling が裁定の中に足す欄 PLAN_ITEMS。無ければ空）"""
    return (row.get("ruling") or {}).get(PLAN_ITEMS) or []


def replan_rows(rows, n: int, unit_keys) -> list:
    """申し出の行 rows のうち、裁定が REPLAN で案の項目 n を名指す物（裁定の PLAN_ITEMS が n を持つか、申し出の単位が項目の
    unit_keys に在る。単位は字で比べる）。案の直しの材料（planfile の brief・boardview の事前審査）が読む 1 つの選び"""
    keys = {str(k) for k in unit_keys or []}
    out = []
    for c in rows or []:
        if isinstance(c, dict) and decision(c) == REPLAN and (
                n in ruled_items(c) or str(c.get("unit_key")) in keys):
            out.append(c)
    return out


def held_by_rulings(b) -> dict:
    """直す義務から外す単位 {unit_key: 理由}。決まりは 1 つ: 直す裁定（FIX_DECISIONS）でない裁定は、それが外す単位（ruled_units。
    fix_plan_item は誤りと裁いた項目の単位の全部）を直させない（ask_human は最後の人の関所で人が決め、fix_plan_item は同じ
    run の中で案の項目を直すのを待つ）。案の項目を直した行（状態 AMENDED）は外さない（その単位は直す義務に戻る）。理由は
    「<decision> の裁定 <id>」に、在れば案の項目を、ask_human の行で単位の直しの在りか（fix_place）が LEFT でなければ place_words を添える。
    1 単位に 2 つ当たれば DECISIONS の順で先の裁定の理由（並べ替えで決める）"""
    rank = {d: n for n, d in enumerate(DECISIONS)}
    rows = sorted((i for i in items(b) if decision(i) not in (None, *FIX_DECISIONS) and replan_state(i) != AMENDED),
                  key=lambda i: rank.get(decision(i), len(rank)))
    out, held = {}, asked(b)
    for i in rows:
        ru = i["ruling"]
        nums = ", ".join(map(str, ruled_items(i)))
        why = f"{ru['decision']} の裁定 {i.get('id') or '（id 無し）'}" + (f"（案の項目 {nums}）" if nums else "") \
            + (f"・{place_words(mine)}" if decision(i) == ASK and fix_place(mine := unit_rows(held, i.get("unit_key"))) != LEFT else "")
        for k in ruled_units(i):
            out.setdefault(k, why)
    return out


def held_units(unit_keys, held: dict) -> dict:
    """案の項目の単位のうち裁定で外れた物 {key: 理由}（held_by_rulings の held に在る物。unit_keys の順）"""
    return {k: held[k] for k in unit_keys or [] if isinstance(k, str) and k in held}


def held_item(unit_keys, held: dict) -> str:
    """案の項目が裁定で外れた項目か（unit_keys の全部が held_units に在る）。外れていれば外した裁定の理由を「・」で
    つないだ文、外れていない・unit_keys が無ければ空。外れた項目は差分の審査で照らさず手直しに直させない（差分の審査の材料（refix）が
    読む 1 つの決まり。修正の受け付けの範囲の照らしはほかの項目と同じに扱う）"""
    keys = [k for k in unit_keys or [] if isinstance(k, str)]
    got = held_units(keys, held)
    if not keys or len(got) != len(set(keys)):
        return ""
    return "・".join(dict.fromkeys(got.values()))


def replaced_queries(b) -> dict:
    """裁定 replace_query が置き換えた問い {unit_key: {id, how, counts, hits, misses}}（閉鎖の数え直しが判定者の問いの代わりに使う）"""
    return {i["unit_key"]: {"id": i["id"], **i["ruling"]["query"]} for i in items(b)
            if decision(i) == REPLACE and isinstance(i["ruling"].get("query"), dict)}


def counts_of(rows) -> dict:
    """{parked（申し出の件数）, fix_test_scope, fix_code_as, ask_human, unruled}。replace_query・fix_plan_item・rejudge は裁いた物が
    在る時だけ足す"""
    out = {"parked": len(rows), "unruled": sum(1 for i in rows if i.get(RULING) is None)}
    for d in DECISIONS:
        n = sum(1 for i in rows if decision(i) == d)
        if n or d not in (REPLACE, REPLAN, REJUDGE):
            out[d] = n
    return out


def counts(b) -> dict:
    return counts_of(items(b))


def kind_counts(b) -> dict:
    return kind_counts_of(items(b))


def kind_counts_of(rows) -> dict:
    """申し出の種類の内訳 {DIV_KINDS の全部: 件数（0 も）}。kind の無い前の形の行が在る時だけ鍵 UNSET を足す"""
    out = {k: sum(1 for r in rows if r.get(KIND_FIELD) == k) for k in DIV_KINDS}
    unset = sum(1 for r in rows if not r.get(KIND_FIELD))
    if unset:
        out[UNSET] = unset
    return out


def park(b, rows, *, source: str, ruling: dict | None = None, round_: int = 1, pass_: str | None = None) -> list:
    """申し出を積む（status parked・ruling は None か渡した物。裁定の後の段の受け付けは pass_ に ruled を渡し、欄 FILED_IN に残す）。同じ単位・同じ名指し・同じ理由の申し出は積み増さない
    （実行基盤の呼び直し。案を直した行（状態 AMENDED）は数えない——作り直した後の同じ申し出は新しい申し出）。trace に 1 行ずつ。
    返りは積んだ・在った行の id。source が SOURCES の外か、pass_ が ruled でも None でもなければ ValueError（1 回目の段の行は
    mark_reverted が照らさないので印を持たない）"""
    if source not in SOURCES:
        raise ValueError(f"申し出の出どころ {source!r} が表 SOURCES {list(SOURCES)} に無い")
    if pass_ not in (None, "ruled"):
        raise ValueError(f"積んだ段の印は ruled だけ: {pass_!r}")
    doc = _load(b)
    ids = []
    for it in rows:
        # 前からの 4 つの欄は必ず在る（受け付けと機械の申し出が確かめてから積む）。kind だけは前の形の行に無いことがある
        body = {**{k: it[k] for k in FIELDS if k != KIND_FIELD}, KIND_FIELD: it.get(KIND_FIELD)}
        same = next((r for r in doc["items"] if replan_state(r) != AMENDED and {k: r.get(k) for k in FIELDS} == body), None)
        if same is not None:
            ids.append(same["id"])
            continue
        n, taken = len(doc["items"]) + 1, {r.get("id") for r in doc["items"]}
        while f"c{round_}-{n}" in taken:   # 写した 1 回目の段の行（adopt_prior）の id と重ねない
            n += 1
        row = {"id": f"c{round_}-{n}", "round": round_, "source": source, **body,
               **({CORRECT: list(it[CORRECT])} if it.get(CORRECT) else {}),
               "status": "ruled" if ruling else "parked", "ruling": ruling, **({FILED_IN: pass_} if pass_ else {})}
        doc["items"].append(row)
        ids.append(row["id"])
        fixboard.trace(b, PARK_OP, id=row["id"], unit_key=row["unit_key"], source=source, which_is_right=row[WHICH_FIELD],
                kind=row.get(KIND_FIELD), between=row["between"], ruled=bool(ruling))
    _save(b, doc)
    return ids


def _repeated_from(row: dict, amended: dict):
    """未送の行 {source, item} が、作り直した後にまた止まった単位の諦めなら、その単位を外していた項目を直した行（無ければ None）。
    機械が諦めた申し出（GAVE_UP_SOURCE）で、その単位が案を直して直す義務に戻った単位（amended_rows_by_unit）の時だけ"""
    return amended.get(row["item"]["unit_key"]) if row["source"] == GAVE_UP_SOURCE else None


def repeat_gave_up(b, rows: list) -> list:
    """rows（未送の行 {source, item}）のうち、作り直した後にまた止まった単位の諦めの行。park_claims がこの行を裁定に回さず積む"""
    amended = amended_rows_by_unit(b)
    return [r for r in rows if _repeated_from(r, amended) is not None]


def park_claims(b, rows: list, *, round_: int = 1) -> list:
    """輪の状態の未送の行 {source, item} を積む。作り直した後にまた止まった単位の諦めの行（repeat_gave_up）は、裁定に回さず
    ask_human つき（by stopby.TDD_REPEAT）で積む。ほかは裁定なし。返りは積んだ・在った行の id"""
    ids = []
    amended = amended_rows_by_unit(b)
    for r in rows:
        prior = _repeated_from(r, amended)
        ruling = (None if prior is None else
                  {"decision": ASK, "text": REPEAT_GAVE_UP.format(prior=prior.get("id")), "limits": [], "by": stopby.TDD_REPEAT})
        ids += park(b, [r["item"]], source=r["source"], ruling=ruling, round_=round_)
    return ids


def clash_claims(unit_ids, between, why: str) -> list:
    """組どうしの合わせの申し出（JOIN_SOURCE。組を親の木へ当てて赤になり、合わせ役が直せなかった組）の行: 組の単位ごとに 1 件
    （held_by_rulings・human_lines が単位で読む）。kind と which_is_right は機械が埋める決まった値（NEEDS_CONTEXT・UNKNOWN。
    見分けは出どころ source）。between は名指し（<パス>:<行>）、why は組・赤の文・直せなかった訳・控えの差分を名指す文"""
    return [{"unit_key": k, "between": list(between), WHY_FIELD: why, WHICH_FIELD: UNKNOWN, KIND_FIELD: NEEDS_CONTEXT}
            for k in unit_ids]


def mark_clash_patch(b, ids, patch: str) -> None:
    """組どうしの合わせの申し出の行 ids に控えの差分 patch を置く（REVERTED_FIELD。組の直しは作業ツリーに無く控えに在る。
    fix_place が直しの在りかに読む）。先に置いた控えは残す"""
    want = set(ids)
    doc = _load(b)
    hit = [r for r in doc["items"] if r.get("id") in want and r.get("source") == JOIN_SOURCE and not r.get(REVERTED_FIELD)]
    for r in hit:
        r[REVERTED_FIELD] = patch
    if hit:
        _save(b, doc)


def rejudge_texts(rows) -> list:
    """裁定 rejudge の行の裁定の文（重ねない・現れた順）。修正の出力の異議 objection に足し、再審が読む"""
    return list(dict.fromkeys(r[RULING]["text"].strip() for r in rows
                              if decision(r) == REJUDGE and isinstance(r[RULING].get("text"), str) and r[RULING]["text"].strip()))


def apply_rulings(b, rulings: dict, *, by: str) -> None:
    """裁定 {id: {decision, text, limits[, grounds, request_searched, query]}} を今の周の申し出に積み（裁かれていない物だけ。
    fix_plan_item の行には案の直しの状態 WAITING を置く）、trace に 1 行ずつ。知らない id は
    ValueError（回す側が確かめてから渡す）"""
    doc = _load(b)
    by_id = {r["id"]: r for r in doc["items"]}
    unknown = sorted(set(rulings) - set(by_id))
    if unknown:
        raise ValueError(f"知らない申し出の id に裁定を積もうとした: {unknown}")
    for rid, ruling in rulings.items():
        row = by_id[rid]
        if row.get("ruling") is not None:
            continue
        row.update(status="ruled", ruling={**ruling, "by": by})
        if ruling["decision"] == REPLAN:
            row[REPLAN_STATE] = WAITING
        fixboard.trace(b, RULE_OP, id=rid, unit_key=row["unit_key"], decision=ruling["decision"], by=by)
    _save(b, doc)


# ---------------------------------------------------------------- 写しの RL の差し替え・最後の関所
NOTHING_OWED = ("直す義務の単位が残っていない——開いた単位は全部、人の答え待ちか ask_human・fix_plan_item で直す義務から外れた"
                "（changes が空なのが正しい返答。ask_human は最後の承認ノードで人が決め、fix_plan_item は同じ run の中で案の項目を"
                "直してから 2 回目の修正の段で直す。直せなければ最後の承認ノードへ）")


def parse_limit(lim: str):
    """裁定の範囲の 1 つ `<パス>` か `<パス>:<行>[-<行>]` → (作業ツリーの根からのパス, (始め, 終わり) か None（ファイル全体）)。
    根の外・根そのものを指す物は None"""
    m = cite.CITE.match(lim.strip())
    path = posixpath.normpath(m["path"] if m else lim.strip())
    if globs.climbs(path):   # `..` は段で見る（`..foo/x.py` は根の中。planmarks.gaps が通す範囲を捨てない）
        return None
    return path, ((int(m["a"]), int(m["b"] or m["a"])) if m else None)


def _plan_limit(r: dict, source):
    """修正案の行の範囲。source（パス → その木での中身。読めなければ None）を渡せば、その木でテストの id の定義の行を引き直す
    （修正案の時の木の行の番号は、後で上に足したテストでずれる）。引けなければ None（許しを捨てる）"""
    if source is None:
        return r["limit"]
    got = parse_limit(r["limit"])
    line = planmarks.line_in(source(got[0]), r["id"]) if got and isinstance(r["id"], str) else None
    return f"{got[0]}:{line}" if line else None


def fields_broken(b, e: Exception, *, by: str = stopby.FIX, stop=None) -> Exception:
    """修正案の欄の控えが壊れた（planmarks.FieldsBroken）時の 1 本の道: stop（止める口 stop(why, by=by)。渡した時だけ）で by の
    印を付けて止め、控えを名指す理由の ValueError を返す（呼ぶ側が raise する。許しや照らしを黙って広げない・黙って捨てない）。文の頭は修正の段
    （by stopby.FIX）なら FIELDS_BROKEN、ほかの段は段を名指さない FIELDS_TAMPERED と「読まずに止めた」"""
    head = FIELDS_BROKEN if by == stopby.FIX else FIELDS_TAMPERED + "控えを読まずに止めた"
    why = f"{head}: {oneline.one_line(e)}"
    if stop is not None:
        try:
            stop(why, by=by)
        except Reject as r:
            why += f"（共有ボードを止められない: {oneline.one_line(r)}）"
    return ValueError(why)


def _plan_rewrites(b, round_: int = 1) -> list[dict]:
    """planmarks.rewrites。控えが凍結の印と食い違えば（FieldsBroken）fields_broken の道（ValueError（止めるのは呼び手））"""
    try:
        return planmarks.rewrites(fixboard.marks_view(b, round_))
    except planmarks.FieldsBroken as e:
        raise fields_broken(b, e) from None


def _plan_removes(b, round_: int = 1) -> list[dict]:
    """planmarks.removes_permits。_plan_rewrites と同じく、控えが食い違えば ValueError（止めるのは呼び手）"""
    try:
        return planmarks.removes_permits(fixboard.marks_view(b, round_))
    except planmarks.FieldsBroken as e:
        raise fields_broken(b, e) from None


def frozen_fields(b, round_: int = 1) -> list | None:
    """今の周の凍結した修正案の欄の並び（planmarks.frozen。控えが無ければ None）。控えが凍結の印と食い違えば、_plan_rewrites と
    同じく ValueError（止めるのは呼び手）（fields_broken の道。TDD の輪の約束を黙って空にしない）"""
    try:
        return planmarks.frozen(fixboard.marks_view(b, round_))
    except planmarks.FieldsBroken as e:
        raise fields_broken(b, e) from None


def plan_asks(b, op: str = ASKED_OP, *, carried: bool = False) -> list[dict]:
    """置き場の trace の範囲の相談の行（既定は ASKED_OP。ほかの語の行も op で引く。古い順。読めない・壊れた行は飛ばす）。
    既定は、この置き場の役が自分で聞いた行だけ。group_id の在る行（戻せた組の子の置き場から親へ写した行。consult.carry_agreed）は
    返さない（写した行は親の範囲とテストの許しに効くだけで、親が聞いた行ではない。関所の条件を出し済みにも、受け付けの聞いた答えにも
    数えない）。carried が真なら写した行も全部返す。自分の行と写した行の見分け（group_id の有無）を持つのはここだけ"""
    try:
        lines = (pathlib.Path(b) / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("op") == op and (carried or "group_id" not in row):
            out.append(row)
    return out


def agreed(b, *, carried: bool = True) -> list[dict]:
    """範囲の相談の合意（plan_asks のうち答えが allow の行）。範囲（blk-fix の planscope）とテストの許し（test_permits）の唯一の
    読み口。既定は写した行（group_id つき）も含む。carried=False はこの置き場の役が自分で聞いた合意だけ（fixboard.overflow_trace）"""
    return [r for r in plan_asks(b, carried=carried) if r.get("status") == "answered" and r.get("decision") == "allow"]


def _in_tree(lim: str, source, base):
    """合意の範囲 lim（行は修正前の版の行。読む木は 1 つ）を、source（パス → 読む木での中身）の木の範囲へ移す。source が無ければ
    そのまま（修正前の版を読む事後の関門）。ファイルだけの指しは木に依らずそのまま。1 行の指し `<パス>:<行>` は base（パス →
    修正前の版の中身）でその行を含む関数の id を引き、読む木でその id の定義の行を引き直す（関数の中身が変わっていても付く。
    関数の外の行は行そのものを planmarks.map_line で移す）。行の範囲 `<行>-<行>` は、途中に足した行も書き換えた行も無い時だけ
    移す（足した行を許しに含めない）。移せない（base が読めない・関数が
    読む木に無い・行が書き換わっている）なら None（許しを捨てる。広げない）"""
    got = parse_limit(lim)
    if got is None or got[1] is None or source is None:
        return lim
    path, (a, b) = got
    old, new = base(path) if base else None, source(path)
    if not isinstance(old, str) or not isinstance(new, str):
        return None
    if cite.CITE.match(lim.strip())["b"]:
        got = planmarks.map_range(old, new, a, b)
        return f"{path}:{got[0]}-{got[1]}" if got else None
    tid = planmarks.id_at(old, path, a)
    line = (planmarks.line_in(new, tid) if tid else None) or planmarks.map_line(old, new, a)
    return f"{path}:{line}" if line else None


def agreed_permits(rows, *, source=None, base=None) -> list[dict]:
    """合意の行の書き換えてよいテストの範囲を test_permits の行の形に（行の順・範囲の順）。範囲の行は修正前の版の行で（相談の頼みも
    答えもそう書く）、source・base の渡し方は _in_tree"""
    out = []
    for r in rows:
        for lim in r.get("granted_tests") or []:
            moved = _in_tree(lim, source, base) if isinstance(lim, str) and parse_limit(lim) else None
            if moved:
                out.append({"limit": moved, "id": f"{AGREED_TEST_ID}-{r.get('item')}",
                            "why": f"範囲の相談 {r.get('id')}（項目 {r.get('item')}）で修正案を書いた役が許したテストの書き換え: {r.get('reason')}"})
    return out


def test_permits(b, *, rulings: bool = True, source=None, skip_ids=(), agreed_rows=None, base=None,
                 round_: int = 1) -> list[dict]:
    """既存のテストの変更の許しの唯一の元（keep-essence の 3。許す元を読むのはここだけで、凍結の検査・事後の関門・範囲の照らし・
    最後の関所はこの行を読む）。許す元は 6 つ（6 つ目は関わる試験で直す前から壊れていた物のファイル〔broken_tests。行は broken: true〕。
    docs/design/fix.md の 19 節）。ほかの 5 つ: 承認済みの修正案の rewrite_tests（いつも。planmarks.rewrites の順）・範囲の相談の
    合意（agreed_permits）・承認済みの修正案の項目の files の change=remove の symbol（消す名）と op=delete の path・op=rename の元のパス from の .py のモジュールの名をコードで使う既存テスト（planmarks.removes_permits。書き換えも関数の
    丸ごとの消しも許す）・rulings が真なら裁定 fix_test_scope の範囲（ruled_fix の順）・案の直しで直した項目の単位（amended_keys。
    前の輪の受け入れのテストの関数を、直した案で書き直してよい）。
    行は {limit: 範囲の文字列, id: 守りのファイルの行の id の頭, why: 許した理由, source: 許しの出どころの語（fixboard.ALLOWED_SOURCES。
    fixboard.allowed_test_rows の行の source）}。修正案の行は名指しのテストの id（test）も持つ
    （id で許す事後の関門が読む）。案の直しの行だけは limit を持たず units（単位の key の並び）を持つ（テストの関数の幅は TDD の輪の
    状態が知る。tddloop.test_spans）。source（パス → 中身か None）を渡すと、修正案の行の範囲をその木でテストの id から
    引き直し、引けない行は捨てる（凍結の検査が読む輪の後の木。tddloop.frozen_source）。skip_ids（修正案の行の id そのまま）に
    在る修正案の行は外す（TDD の輪が赤→緑を確かめた書き換え。tddloop.verified_rewrites）。裁定の行はそのまま。
    範囲の相談の合意（agreed_rows を渡せばその行——盤面にまだ写していない合意を足して見る事前の確かめ）は修正案の行の後にいつも入れる。
    合意の範囲の行は修正前の版の行で、source を渡す読み手には base（パス → 修正前の版の中身）も渡して、その木の行へ移す（_in_tree。
    移せない範囲は捨てる）。裁定の範囲は書いた木のまま。
    修正案の欄の控えが凍結の印と食い違えば、ValueError（止めるのは呼び手）（_plan_rewrites）"""
    plan, consult, ruling, broken = fixboard.ALLOWED_SOURCES
    out = []
    skip = set(skip_ids)
    for r in _plan_rewrites(b, round_):
        lim = _plan_limit(r, source) if r["id"] not in skip else None
        if lim:
            out.append({"limit": lim, "id": f"{PLAN_TEST_ID}-{r['item']}", "test": r["id"], "source": plan,
                        "why": f"承認済みの修正案の項目 {r['item']} が名指した既存テストの書き換え（{r['id']}）: {r['new']}"})
    for r in _plan_removes(b, round_):
        lim = _plan_limit(r, source)
        if lim:
            out.append({"limit": lim, "id": f"{REMOVES_TEST_ID}-{r['item']}", "test": r["id"], "source": plan,
                        "why": f"承認済みの修正案の項目 {r['item']} が消す名を本体で名指す既存テスト（{r['id']}）: 消す仕組みを縛るので書き換え・消しを許す"})
    out += [{**p, "source": consult} for p in agreed_permits(agreed(b) if agreed_rows is None else agreed_rows, source=source,
                                                             base=base)]
    if rulings:
        out += [{"limit": lim, "id": f"{RULED_TEST_ID}-{r['id']}", "source": ruling,
                 "why": f"{HEAD}の裁定 {r['id']}（{r['unit_key']}）が許したテストの変更: {r['ruling']['text']}"}
                for r, lim in ruled_limits(b, decisions=("fix_test_scope",))]
    out += [{"limit": r["path"], "id": f"{BROKEN_TEST_ID}-{n}", "source": broken, "broken": True,
             "why": f"関わる試験で直す前から壊れていた（TDD のループの頭の元の結末で {'・'.join(r['ids'][:5])} が落ちていた）: 修正役が"
                    "直しと一緒に直してよい。最後の承認ノードに「ついでに直した試験」として出る"}
            for n, r in enumerate(broken_tests(b), 1)]
    out += [{"units": sorted(ruled_units(i)), "id": f"{AMENDED_TEST_ID}-{i['id']}",
             "why": f"案の直し {i['id']} で直した項目の単位の、前のループの受け入れのテスト（直した案で書き直してよい）"}
            for i in items(b) if replan_state(i) == AMENDED and ruled_units(i)]
    return out


def permitted_units(b) -> set:
    """テストの変更の許し（test_permits）のうち、単位で許す行（案の直しで直した項目）の単位の key"""
    return {k for p in test_permits(b) for k in p.get("units") or ()}


def ruled_limits(b, *, decisions=FIX_DECISIONS) -> list[tuple[dict, str]]:
    """直す裁定（ruled_fix）のうち decision が decisions に在る行の範囲 limits の並び [(申し出の行, 範囲の文字列)]（ruled_fix の
    順・limits の順）。裁定の範囲の唯一の読み口（テストの変更の許し test_permits は fix_test_scope だけ、blk-fix の案の項目の
    照らし planscope は直す裁定の全部を読む）"""
    return [(r, lim) for r in ruled_fix(b) if r["ruling"]["decision"] in decisions for lim in r["ruling"].get("limits") or []]


def ruled_paths(b) -> list[str]:
    """直す裁定（ruled_limits）の limits のパス（parse_limit。重ねない・並びの順）。裁定が run の全部の項目に足す範囲で（範囲の相談の
    合意 agreed は項目ごとに足す別の口）、blk-fix の planscope と差分の審査・手直しの材料（fixboard.scope_brief）が読む 1 つの口"""
    out = []
    for _, lim in ruled_limits(b):
        got = parse_limit(lim)
        if got and got[0] not in out:
            out.append(got[0])
    return out


def ruled_test_limits(b, *, rulings: bool = True, source=None, skip_ids=(), agreed_rows=None, base=None,
                      round_: int = 1) -> list[str]:
    """テストの変更の許し（test_permits）の範囲の文字列の並び。rulings が偽なら裁定の範囲を含めない（1 回目の受け付け）。
    source・skip_ids・base は test_permits と同じ（凍結の検査は輪の後の木の読み口と、輪が確かめた書き換えの id と、修正前の版の読み口を渡す）"""
    return [p["limit"] for p in test_permits(b, rulings=rulings, source=source, skip_ids=skip_ids, agreed_rows=agreed_rows, base=base,
                                             round_=round_)
            if "limit" in p]


def edit_rulings(b, pass_: str) -> bool:
    """事後の関門の許し（edit_permits）に裁定 fix_test_scope の範囲が入るか: 段 ruled か 2 回目の修正の段（second_pass）"""
    return pass_ == "ruled" or second_pass(b)


def broken_tests(b) -> list:
    """置き場 b の BROKEN_TESTS_FILE の行 [{path, ids}]（関わる試験で直す前から壊れていた物のファイルと落ちていた試験の鍵。fix の TDD の
    輪の頭が書く）。無い・読めない・形の違う行は捨てる"""
    try:
        doc = json.loads((pathlib.Path(b) / BROKEN_TESTS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("tests") if isinstance(doc, dict) else None
    return [{"path": r["path"], "ids": [str(i) for i in r.get("ids") or []]} for r in rows or []
            if isinstance(r, dict) and isinstance(r.get("path"), str) and r["path"].strip()]


def edit_permits(b, pass_: str, *, round_: int = 1) -> dict:
    """修正の段の受け付けの事後の関門（fixgates の test_edits）が、既存のテストの関数の本体の変更・消しを許す物
    {tests: 名指しの id（承認済みの修正案の rewrite_tests と、消す名を名指すテスト。test_permits の行の test）,
     limits: 範囲の文字列（範囲の相談の合意と、裁定 fix_test_scope の範囲と、直す前から壊れていた関わる試験のファイル。test を持たない行の limit）,
     broken: limits のうち直す前から壊れていた関わる試験のファイル（指示書が別の行に出す）}。
    裁定の範囲は edit_rulings で入る。修正役の指示書の「テストの行」（fix の rules.tests_rows）も同じ値を貼る"""
    permits = test_permits(b, rulings=edit_rulings(b, pass_), round_=round_)
    return {"tests": [p["test"] for p in permits if isinstance(p.get("test"), str)],
            "limits": [p["limit"] for p in permits if "limit" in p and "test" not in p],
            "broken": [p["limit"] for p in permits if p.get("broken") is True]}


def ruled_test_doc(b) -> dict | None:
    """テストの変更の許し（承認済みの修正案の rewrite_tests と裁定 fix_test_scope の範囲。test_permits）が名指したテストの
    ファイル（範囲の <パス>[:行]）を、守りのファイルの一覧の形 {rules: [...]} に。無ければ None。
    パスで 1 行（protect.hits は 1 つのパスに最初の行しか返さない）。id は先に並んだ許しの物で、同じパスの許しの理由は
    捨てずに why に " / " でつなぐ（最後の関所に許したテストの変更を全部並べる）"""
    rows, whys = [], {}   # whys: パス → 理由の並び（同じ理由は 1 度だけ。理由の文に " / " が在っても割らない）
    for p in test_permits(b):
        got = parse_limit(p["limit"]) if "limit" in p else None
        path = got[0] if got else None
        if path is None:
            continue
        if path not in whys:
            whys[path] = []
            rows.append({"id": f"{p['id']}-{len(rows) + 1}", "glob": path})
        if p["why"] not in whys[path]:
            whys[path].append(p["why"])
    for row in rows:
        row["why"] = " / ".join(whys[row["glob"]])
    return {"rules": rows} if rows else None


def mark_reverted(b, files, patch: str, pass_: str) -> None:
    """機械が段 pass_ の頭の木へ files を戻して控え patch に移した時、その段の受け付けが積んだ（FILED_IN が pass_。adopt_prior が
    写した PRIOR の行は外す）query_hits_fixed の行で、名指し between がその files に当たる行に控えを置く（REVERTED_FIELD。先に置いた
    控えは残す——直しを持つのは最初に戻した patch）。段の頭より前に積んだ行の直しは頭の木に在り、戻しても差分に残るので置かない。
    fix_place が直しの在りかに読む"""
    files = set(files)
    doc = _load(b)
    hit = [r for r in doc["items"] if r.get(KIND_FIELD) == QUERY_HITS_FIXED and not r.get(REVERTED_FIELD)
           and r.get(FILED_IN) == pass_ and not r.get(PRIOR)
           and any((m := cite.CITE.match(c.strip())) and m["path"] in files for c in r.get("between") or [] if isinstance(c, str))]
    for r in hit:
        r[REVERTED_FIELD] = patch
    if hit:
        _save(b, doc)


def _row_place(row) -> str:
    if row.get(REPLAN_WHY):
        return KEPT
    if row.get("source") == JOIN_SOURCE and row.get(REVERTED_FIELD):
        return REVERTED
    if row.get(KIND_FIELD) != QUERY_HITS_FIXED:
        return LEFT
    return REVERTED if row.get(REVERTED_FIELD) else IN_DIFF


def fix_place(rows) -> str:
    """1 単位の人に回した行（か裁定へ回した行）の全部 rows から、その単位の直しの在りか: 案の直しを諦めた行は KEPT（直した分は
    作業ツリーに残した）、query_hits_fixed は IN_DIFF（直してから申し出る。機械が名指しのファイルを戻した行は REVERTED）、組どうしの
    合わせの申し出（JOIN_SOURCE）で控えの差分を置いた行は REVERTED、ほかは LEFT。KEPT の行が 1 つでも在れば KEPT（修正役に戻すなと
    約束した直しが木に在る。諦めた行の約束）。ほかに行ごとの在りかが
    揃わなければ LEFT（直していない直しを差分に在ると言わない）"""
    got = {_row_place(r) for r in rows}
    if KEPT in got:
        return KEPT
    return got.pop() if len(got) == 1 else LEFT


def place_words(rows) -> str:
    """fix_place の言い方（関所・報告・次の依頼・単位の結末の理由の字）"""
    place = fix_place(rows)
    if place == REVERTED:
        return FIX_REVERTED.format(patch=next(r[REVERTED_FIELD] for r in rows if r.get(REVERTED_FIELD)))
    return {IN_DIFF: FIX_IN_DIFF, LEFT: UNFIXED_LEFT, KEPT: HELD_WORK_KEPT}[place]


def unit_rows(rows, key) -> list:
    """rows のうち単位 key を外す行（ruled_units。裁いていない行は申し出の単位）"""
    return [r for r in rows if key in ruled_units(r)]


def ask_why_words(ruling: dict) -> str:
    """裁定の人に回す訳（ASK_WHY）の関所の言い方「人に回す訳（<変わる物>） <line>・」。訳の無い裁定（機械が人に回した物）は空"""
    why = ruling.get(ASK_WHY)
    if not isinstance(why, dict):
        return ""
    return f"人に回す訳（{ASK_CHANGES.get(why.get('changes'), why.get('changes'))}） {why.get('line')}・"


def human_lines(b) -> list:
    """最後の関所と報告に載せる ask_human の行（1 件 1 行。asked の行で、諦めた fix_plan_item も。裁定の文は字のまま。括弧に裁定役の
    人に回す訳（ASK_WHY）が在れば「人に回す訳（<変わる物>） <line>」、末尾に REPLAN_WHY が在れば「・案の直し: <why>」と、行の単位の
    直しの在りか「・<place_words>」）"""
    rows = asked(b)
    return [f"{r['unit_key']}: {r['ruling']['text']}（名指し {', '.join(r['between'])}・種類 {r.get(KIND_FIELD) or '無し'}・"
            f"正しいと見た側 {r[WHICH_FIELD]}・"
            + (f"依頼で探したこと {r['ruling']['request_searched']}・" if r["ruling"].get("request_searched") else "")
            + ask_why_words(r["ruling"])
            + f"{r['id']}"
            + (f"・案の直し: {r[REPLAN_WHY]}" if r.get(REPLAN_WHY) else "")
            + f"・{place_words(unit_rows(rows, r['unit_key']))}）" for r in rows]
