"""事前審査の block の place のファイルの名と、受け付けの名、型の読み口（docs/design/plan-review.md の 1.4・1.5）。名はこのモジュールだけが
持つ（lib のモジュールが名を組む物は、そのモジュールの名のまま）。

place は ports.place()（単独の run では run の置き場の直下、line から include された時はその下の include の道のフォルダ）。
"""
from __future__ import annotations

import json
import pathlib
import re

import ports

import converge     # lib/
import design       # lib/
import planmarks    # lib/
import reads       # lib/
import structmark   # lib/
import worldmark    # lib/

REVIEW_NODE = "p2.plan_review"          # 審査の受け付けの名（却下の控えの名）
TEXT_NODE = "p2.plan_review.text"       # 形 text の受け付けの名
PLAN_NODE = planmarks.NODE
HUMAN_FACE_KINDS = ("regression", "policy")   # 人に回しうる穴の kind（今の fixboard.HUMAN_FACE_KINDS の値。fix へ移るので写す）
REVIEW_MD = ports.SHARED / "prompts" / "REVIEW.md"    # 観点の正本（工場の物。lib は経由しない）
MINIMAL_HEAD = "最小性:"                # 範囲の膨張の穴のうち最小性の穴の why の頭（md と読み手が同じ字を持つ）
SHORT_HEAD = "足りない: "               # 入力が足りない時の faces_none・reason の頭

# ---------------------------------------------------------------- place のファイル
INTAKE = "intake.json"
INTAKE_ERROR = "intake-error.json"
JUDGMENT = "judgment.json"
EXCLUDED = "excluded.json"
WORLD_DIR = "world"
WORLD_COPY = f"{WORLD_DIR}/{worldmark.WORLD_FILE}"
STRUCTURE_DIR = "structure"
STRUCTURE_ROWS = f"{STRUCTURE_DIR}/design-rows.jsonl"
DESIGN = design.DESIGN_FILE
RIPPLE = "ripple.json"
FIELDS = planmarks.FIELDS_FILE
TRACE = planmarks.TRACE_FILE
CONVERGE = converge.RECORD
PRECEDENT_CHECKS = "precedent-checks.json"
LIBDOCS = "libdocs"
MATERIAL = "review-material-{n}.md"
ITEMS_DIR = "items"
ANSWERS_DIR = "answers"
BRIEF = f"{ITEMS_DIR}/brief.md"
SYNERGY_ITEM = f"{ITEMS_DIR}/synergy.md"
ITEM = f"{ITEMS_DIR}/item-{{n}}.md"
ITEM_ANSWER = f"{ANSWERS_DIR}/item-{{n}}.json"
SYNERGY_ANSWER = f"{ANSWERS_DIR}/synergy.json"
TREE_STATE = "review-tree-state.json"
REVIEW = "review.json"
FACE_MARKS = "review-marks.json"   # 受け付けが穴の行から外した決め手の欄（src/take.py が書き src/gate.py が読む）
PASS = "pass.json"
REPLAN = "replan.json"
REPLAN_GAVE_UP = "replan-gave-up.json"
CRASH = "crash.json"
FINISH = "finish.json"
# 読んだ証拠（lib/reads が名を組む。役の名は形 plan・replan の審査の役と形 text の役。形 replan は reads.role_key で頭に replan-）
READS_ROLE = "plan-review"
TEXT_READS_ROLE = "plan-review-text"
READS_FILES = tuple(reads.evidence_name(reads.role_key(role, again)) for role, again in
                    ((READS_ROLE, False), (READS_ROLE, True), (TEXT_READS_ROLE, False)))
READS_INDEXES = (reads.index_name(READS_ROLE), reads.index_name(READS_ROLE, True))
# 読んだ証拠を集める node が落ちた時に lib/reads.guarded が置く記録（名に時刻が入るので、名の型で引く）
READS_FAILED = tuple(name.removesuffix(".json") + "-failed-*.json" for name in READS_FILES)
# 組んだ指示（prompt.emit が書く）の node の id
PROMPT_NODES = ("review", "review-fix", "review-tree", "review-tree-fix", "review-text")
OWN_FILES = (INTAKE, INTAKE_ERROR, JUDGMENT, EXCLUDED, DESIGN, RIPPLE, FIELDS, TRACE, CONVERGE, PRECEDENT_CHECKS, TREE_STATE,
             REVIEW, FACE_MARKS, PASS, REPLAN, REPLAN_GAVE_UP, CRASH, FINISH, worldmark.COPY_STATE, worldmark.COPY_MEANS, structmark.COPY_FILE,
             WORLD_COPY, STRUCTURE_ROWS, *READS_FILES, *READS_INDEXES)
OWN_DIRS = (ITEMS_DIR, ANSWERS_DIR, WORLD_DIR, STRUCTURE_DIR)
OWN_GLOBS = tuple(f"{node}-prompt-*.md" for node in PROMPT_NODES) + ("review-material-*.md", *READS_FAILED)

# ---------------------------------------------------------------- 型
# 審査する物の形（修正案の役の返答。項目の行の plan と、前の往復の穴への答え block_answers を持つ。ほかの欄は許す）
PROPOSAL_SHAPE = {"type": "object", "required": ["plan"], "properties": {"plan": {"type": "array", "minItems": 1},
                                                                         "block_answers": {"type": "array"}}}
# 前の往復までの往復の記録（往復の記録の形に、先行例の出典の確かめの控え precedent_checks を足した物。ほかの欄は許す）
PRIOR_SHAPE = {"type": "object", "required": ["passes"],
               "properties": {"passes": {"type": "array"}, "plan": {"type": "array"}, "outcome": {"type": ["string", "null"]},
                              "precedent_checks": {"type": "object"}}}

YAML = pathlib.Path(__file__).resolve().parents[1] / "works-factory-plan-review.yaml"


def node_schema(node_id: str) -> dict:
    """YAML の node の output_format（JSON の流れの書き方 {…} で書いてある物）。node の行の後の最初の output_format: の値を読む。
    下請けの答えのファイルの型が、その faces・shrink を使う"""
    text = YAML.read_text(encoding="utf-8")
    head = re.search(rf"^\s*- id: {re.escape(node_id)}\s*$", text, re.M)
    if head is None:
        raise ValueError(f"YAML に node {node_id} が無い")
    key = re.compile(r"^\s*output_format:\s*", re.M).search(text, head.end())
    nxt = re.compile(r"^\s*- id: ", re.M).search(text, head.end())
    if key is None or (nxt is not None and nxt.start() < key.start()):
        raise ValueError(f"node {node_id} に output_format が無い")
    try:
        got, _ = json.JSONDecoder().raw_decode(text, key.end())
    except ValueError as error:
        raise ValueError(f"node {node_id} の output_format が JSON の形でない: {error}") from None
    if not isinstance(got, dict):
        raise ValueError(f"node {node_id} の output_format が object でない")
    return got
