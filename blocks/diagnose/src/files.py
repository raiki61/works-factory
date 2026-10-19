"""診断の block の place のファイルの名と語（docs/design/diagnose.md の 1.4・1.5）。名はこのモジュールだけが持つ。

控え（rejects-*・query-examples・out-of-purpose・answer-ties）の名の元は lib/rolekit.py と lib/marks.py で、ここは消す時のために名を写して
並べる（tests/blocks/diagnose/test_files.py が lib の名と突き合わせる）。
"""
from __future__ import annotations

import pathlib

import materialkit   # lib/。素材の欄の全体の表
import rolekit   # lib/。拒否の控えの名
import stopby    # lib/。止めの語

# ---------------------------------------------------------------- 役と節の名
DIAGNOSE_ROLE = "diagnose"          # 拒否の控え rejects-diagnose.json の名・AI の node の id
REJUDGE_ROLE = "rejudge"
REJUDGE_NODE = "p2.rejudge"         # units-before.json と差の行の node に書く今の字
GUARDED = True                      # 受け付けが作業ツリーの写しと比べる欄（accept.status_keys の引数。役は読むだけ）
HYPOTHESIS = "仮説"                 # 前提の実測の kind の語（lib/runreport.py の HYPOTHESIS と同じ字。作り直しの間はここに置く）
JUDGE, REJUDGE = "judge", "rejudge"  # intake の mode の語

# ---------------------------------------------------------------- 両方の道
INTAKE_FILE = "intake.json"
TREE_FILE = "tree.json"
JUDGMENT_FILE = "judgment.json"
STRUCTURE_DROPPED_FILE = "structure-units-dropped.json"
QUERY_EXAMPLES_FILE = "query-examples.json"
PROMPT_ERROR_FILE = "prompt-error.json"

# ---------------------------------------------------------------- 判定の道
VIEW_FILE = "view.json"
DIFF_FILE = "diff.patch"
CHANGED_FILE = "changed-files.txt"
MATERIALS_FILE = "materials.json"
INPUT_FILE = "diagnose-input.json"
PROMPT_GLOB = "diagnose-prompt-*.md"
COUNT_CACHE_FILE = "count-cache.json"
COUNT_BUDGET_FILE = "count-budget.json"
OUT_OF_PURPOSE_FILE = "out-of-purpose.json"
ANSWER_TIES_FILE = "answer-ties.json"

# ---------------------------------------------------------------- 再審の道
FIRST_JUDGMENT_FILE = "first-judgment.json"
UNITS_BEFORE_FILE = "units-before.json"
REJUDGE_PROMPT_GLOB = "rejudge-prompt-*.md"
REJUDGE_FIX_PROMPT_GLOB = "rejudge-fix-prompt-*.md"
REJUDGE_FIX_NODE = "rejudge-fix"   # 拒まれた後の出し直しの役の node の id
REJUDGE_REPLY_FILE = "rejudge-reply.json"
REJUDGE_DIFF_FILE = "rejudge-diff.json"
REJUDGE_EXIT_FILE = "rejudge-exit.json"


def _reject_names(role: str) -> tuple:
    return (rolekit.rejects_path(pathlib.Path(), role).name, rolekit.rejects_text_path(pathlib.Path(), role).name)


COMMON_FILES = (INTAKE_FILE, TREE_FILE, JUDGMENT_FILE, STRUCTURE_DROPPED_FILE, QUERY_EXAMPLES_FILE, PROMPT_ERROR_FILE)
JUDGE_FILES = (VIEW_FILE, DIFF_FILE, CHANGED_FILE, MATERIALS_FILE, INPUT_FILE, *_reject_names(DIAGNOSE_ROLE), COUNT_CACHE_FILE,
               COUNT_BUDGET_FILE, OUT_OF_PURPOSE_FILE, ANSWER_TIES_FILE)
REJUDGE_FILES = (FIRST_JUDGMENT_FILE, UNITS_BEFORE_FILE, *_reject_names(REJUDGE_ROLE), REJUDGE_REPLY_FILE, REJUDGE_DIFF_FILE,
                 REJUDGE_EXIT_FILE, rolekit.candidate_path(pathlib.Path(), REJUDGE_ROLE).name)
PROMPT_GLOBS = (PROMPT_GLOB, REJUDGE_PROMPT_GLOB, REJUDGE_FIX_PROMPT_GLOB)
OWN_FILES = (*COMMON_FILES, *JUDGE_FILES, *REJUDGE_FILES)

# ---------------------------------------------------------------- 素材の観点の返答 → 材料のファイルの鍵（役の名は material.json の role の値）
# 材料のファイル diagnose-input.json の鍵 → (素材の観点の役の名, その返答の中の欄。None は返答まるごと)。hygiene の findings・
# procedure-trace の unmeasured・external-standards の rankings は今も判定役に届いていないので載せない
REPLY_KEYS = {
    "local_findings": ("local-review", "findings"),
    "consistency_findings": ("consistency-bypass", "findings"),
    "bypass_findings": ("consistency-bypass", "bypass_findings"),
    "external_findings": ("external-standards", "findings"),
    "procedure_findings": ("procedure-trace", "findings"),
    "test_double_fidelity": ("test-double-fidelity", None),
    "main_path_observation": ("main-path-observation", None),
    "provenance": ("provenance", None),
    "prior_decisions": ("prior-decisions", None),
    "purpose_review": ("purpose-review", None),
}
PRIOR_DECISIONS_ROLE = "prior-decisions"
PARALLEL_PR_ROLE = "parallel-pr"
# 出どころの節の名に使う役（受け付けが目的の外の行を当てる材料の行の出どころ）。P1 の目だけ。prior-decisions と purpose-review は辿らない
P1_ROLES = ("local-review", "consistency-bypass", "hygiene", "external-standards", "procedure-trace",
            "test-double-fidelity", "main-path-observation", "provenance")

# この block が読む素材の欄。lib/materialkit.MATERIALS から gate_efficacy を外した 14 欄（持ち主の決め 2026-10-19: 重い確かめは判定の種類から
# 外す）。gate-efficacy の block が返す素材は読まない。lib の表は変えない（gate-efficacy の block は単独で回る）
MATERIALS = tuple(name for name in materialkit.MATERIALS if name != "gate_efficacy")

# ---------------------------------------------------------------- 仕様の足した行・止めの語
SPEC_ORIGIN_NOTE = "spec_origin"
JUDGE_STOP = stopby.declare("judge", "受け付けを通った判定が無いままループを抜けた")
MATERIAL_STOP = stopby.declare("material", "素材集めの役の返答を 3 回とも受けられなかった")
REQUEST_STOP = stopby.declare("request", "依頼の型が通らない・始めの記録が読めない")
REJUDGE_STOP = stopby.REJUDGE
REJUDGE_SESSION_STOP = stopby.REJUDGE_SESSION

UNDECIDED_MIN = 10   # 人へ回す問いの先行例の undecided_because の最小の長さ
FACTS_MIN = 20       # 再審の new_facts の最小の長さ

DOWNGRADES = [{"what": "再審は判定役の会話を継がず、保存した返答を読む新しい会話で回す",
               "versus": "review-graph と今の works は判定役の会話を継ぐ"}]
