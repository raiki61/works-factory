"""place のファイルの名（docs/design/fix.md の 1.4）。

名は、ここと、lib から写したモジュール（src/tdd.py・src/consult.py・src/clash.py・src/ruling.py など。写しは元の定数を字のまま
持つ）だけが持つ。今の lib/fixnames.py・lib/fixbeside.py の名と、lib/fixboard.py の置き場の名の定数（1.5.3）はここに寄せた。
lib/ のモジュールは import しない（返す node が lib を読めない時も名を引けるように）。
"""
from __future__ import annotations

import pathlib

MODES = ("whole", "group")   # port mode の語（docs/design/fix.md の 13.1 の 1）
ROUTES = ("auto", "plan")    # port routes の語（auto は TDD の役が振り分ける。plan は承認済みの案の route をそのまま使う。docs/design/spec-driven.md の 7 章）

# 入口（intake が書く）
INTAKE = "intake.json"   # port を読んだ値
VALUES = "values.json"   # 始めの記録の写しの代わり（src/runvals.py だけが読み書きする）

# 入力の写し（lib/fixboard.py の置き場の名の定数。prep と group-start が書く）
GROUPS_FILE = "groups.json"            # {groups: [{group_id, …}], out_dir, start_tree, …}（prep の返りと同じ）
TDD_UNIT_FILE = "tdd-unit.json"        # 組ごとの TDD の記録（tdd_units の本文。finish が書き、出力 tdd_unit と tdd で返す）
ASSERT_FILE = "assert-changed.json"    # 変更の確かめの結果 {ok, reason}（assert-changed が書き、finish が読む）
RESULT_FILE = "result.json"            # 組の子の結果 <out_dir>/<group_id>/result.json
PLAN_REPLY_FILE = "fix-plan-reply.json"   # 修正案の返りの写し（port fix_plan。{"plan": [...]}。承認済みの項目の unit_keys の出どころ）
PLAN_REVIEW_FILE = "p2.plan_review.json"   # 事前審査の返答の写し（port plan_review。修正役の plan_faces が読む）
JUDGMENT_FILE = "judgment.json"        # 判定の写し
TIES_FILE = "judge-ties.json"          # 判定の結びの写し（port answer_ties）
MATERIALS_FILE = "judge-materials.json"   # 判定の素材の状態の写し（port materials）
JUDGE_COPIES = {"answer_ties": TIES_FILE, "materials": MATERIALS_FILE}   # prep が写す port → 写しの名
CHECKED_COPIES = (TIES_FILE, MATERIALS_FILE)   # 読み手が壊れた JSON を無いと読むので、写す前に読めるかを確かめる写し
RIPPLE_FILE = "ripple.json"            # 波及の一覧の写し
ANSWERS_FILE = "answers.json"          # 人の関所の答えの写し（port answers {decision, text, asked}）
ONLY_ITEMS_FILE = "only-items.json"    # 直す項目の絞り（port only_items。空は全部）
BASELINE_FILE = "baseline.json"        # 直す前の結末 {cases, exit, how}
NOTES_FILE = "human-notes.md"          # 修正前の関所の一言と答えで直す義務に戻った単位の行（修正役と TDD の役の notes_file）
BASE_REV_FILE = "base-rev.json"        # 修正前の版 {rev}（prep が親の作業ツリーの HEAD の sha を控え、組の子が写す）
FIX_REPLY_FILE = "fix-reply.json"      # 組ごとの修正役の返答をまとめた物（出力 reply）

# 今の lib/fixnames.py の名（出力の欄の先）
ALLOWED_TESTS_FILE = "allowed-tests.json"   # 許したテストの変更の訳 [{path, permit, source}]（出力 allowed_tests）
ACCEPT_TRACE_FILE = "accept-trace.json"     # 受け付けが選んだ試験を走らせた回の行の並び（出力 accept_trace）
CLOSURE_FILE = "closure.json"               # 閉鎖の表 {rows, claimed}（出力 closure）
REMOVED_FILE = "fix-removed.json"           # clean が消したパスの全件（lib/leftovers.py が同じ字で書く）
TDD_STATE_FILE = "state.json"               # TDD の輪の状態（tdd-<k>/ の中）

# この block の出力の先（finish が書く）
FROZEN_FILE = "frozen.json"        # 輪ごとの凍ったテストのファイルの hash {loops: [{state, frozen, frozen_tree}]}（出力 frozen）
SCOPE_FILE = "scope.json"          # {plan_items, ruled_paths, agreed}（出力 scope）
CARRY_FILE = "carry.json"          # 次の修正の段への申し送り {conflicts, loops}（出力 carry → port prior）
PRIOR_DIR = "prior"                # port prior の束を置き直すフォルダ（prior/tdd-<k>/state.json・summary.md・conflicts.json）
RULED_REPLY_FILE = "fix-ruled-reply.json"
DIFF_FILE = "fix.diff"
DIFF_NONE_FILE = "fix-diff-none.txt"
PROMPT_ERROR = "prompt-error.json"   # 指示が組めなかった node と訳
COLLECT_ERROR = "fix-collect-error.txt"   # finish の中の誤り
CONFLICTS_DROPPED = "conflicts-dropped.json"
TDD_DELIVERED = "tdd-delivered.json"         # TDD の役に渡した証拠の種類と回の控え（今の tdd-<k>/next.delivered.json の代わり）
FIXER_DELIVERED = "fixer-delivered.json"     # 修正役に渡した証拠の種類と回の控え（今の prompt-p3.fix.delivered.json）
RULED_DELIVERED = "fix-ruled-delivered.json"
