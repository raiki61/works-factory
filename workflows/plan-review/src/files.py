"""事前審査の block の place のファイルの名と、受け付けの名、型の読み口（docs/design/plan-review.md の 1.4・1.5）。名はこのモジュールだけが
持つ（lib のモジュールが名を組む物は、そのモジュールの名のまま）。

place は ports.place()（単独の run では run の置き場の直下、line から include された時はその下の include の道のフォルダ）。
"""
from __future__ import annotations

import pathlib

import yaml    # PyYAML（node_schema を呼ぶ script は uv で PyYAML を宣言する）

import ports

import converge     # lib/
import design       # lib/
import planmarks    # lib/
import reads       # lib/
import structmark   # lib/
import worldmark    # lib/

REVIEW_NODE = "p2.plan_review"          # 審査の受け付けの名（却下の控えの名）
TEXT_NODE = "p2.plan_review.text"       # 形 text の受け付けの名
THEME_NODE = "p2.plan_review.theme"     # 形 theme の受け付けの名
# 審査の役（review）と束ね役（review-tree）の答えに要る根の欄。役の型（YAML の output_format）は出し直しの役と同じ形にするので
# 根の欄を要ると書かず、受け付けが rolekit.resubmitted で確かめる（#832）
REVIEW_REQUIRED = ("faces", "shrink", "reason")
TREE_REQUIRED = ("reason", "items")
PLAN_NODE = planmarks.NODE
REVIEW_MD = ports.SHARED / "prompts" / "REVIEW.md"    # 観点の正本（工場の物。lib は経由しない）
MINIMAL_HEAD = "最小性:"                # 範囲の膨張の穴のうち最小性の穴の why の頭（md と読み手が同じ字を持つ）
SHORT_HEAD = "足りない: "               # 入力が足りない時の faces_none・reason の頭

# ---------------------------------------------------------------- place のファイル
INTAKE = "intake.json"
INTAKE_ERROR = "intake-error.json"
THEME_COPY = "theme-design.md"          # 形 theme で審査する設計の案の md の写し（入力 theme_doc から入口が写す）
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
# 読んだ証拠（lib/reads が名を組む。役の名は形 plan・replan の審査の役と形 text・theme の役。形 replan は reads.role_key で頭に replan-）
READS_ROLE = "plan-review"
TEXT_READS_ROLE = "plan-review-text"
THEME_READS_ROLE = "plan-review-theme"
READS_FILES = tuple(reads.evidence_name(reads.role_key(role, again)) for role, again in
                    ((READS_ROLE, False), (READS_ROLE, True), (TEXT_READS_ROLE, False), (THEME_READS_ROLE, False)))
READS_INDEXES = (reads.index_name(READS_ROLE), reads.index_name(READS_ROLE, True))
# 読んだ証拠を集める node が落ちた時に lib/reads.guarded が置く記録（名に時刻が入るので、名の型で引く）
READS_FAILED = tuple(name.removesuffix(".json") + "-failed-*.json" for name in READS_FILES)
# 組んだ指示（prompt.emit が書く）の node の id
PROMPT_NODES = ("review", "review-fix", "review-tree", "review-tree-fix", "review-text", "review-theme", "review-theme-fix")
OWN_FILES = (INTAKE, INTAKE_ERROR, THEME_COPY, JUDGMENT, EXCLUDED, DESIGN, RIPPLE, FIELDS, TRACE, CONVERGE, PRECEDENT_CHECKS, TREE_STATE,
             REVIEW, FACE_MARKS, PASS, REPLAN, REPLAN_GAVE_UP, CRASH, FINISH, worldmark.COPY_STATE, worldmark.COPY_MEANS, structmark.COPY_FILE,
             WORLD_COPY, STRUCTURE_ROWS, *READS_FILES, *READS_INDEXES)
OWN_DIRS = (ITEMS_DIR, ANSWERS_DIR, WORLD_DIR, STRUCTURE_DIR)
OWN_GLOBS = tuple(f"{node}-prompt-*.md" for node in PROMPT_NODES) + ("review-material-*.md", *READS_FAILED)

# ---------------------------------------------------------------- 型
# 審査する物の形と往復の記録の形は port の宣言の名（入力 plan の shared:fix-plan.schema.json・入力 prior の shared:plan-converge.schema.json）
# で口が照らす。ここに写しを置かない

YAML = pathlib.Path(__file__).resolve().parents[1] / "works-factory-plan-review.yaml"


def node_schema(node_id: str) -> dict:
    """YAML の node の output_format（YAML として読んだ物。anchor で同じ形を 1 か所にしてよい）。node は YAML の中の入れ子（loop の nodes など）
    も含めて id で引く。下請けの答えのファイルの型が、その faces・shrink を使う"""
    stack = [yaml.safe_load(YAML.read_text(encoding="utf-8"))]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get("id") == node_id and ("script" in item or "prompt" in item or "output_format" in item):
                got = item.get("output_format")
                if not isinstance(got, dict):
                    raise ValueError(f"node {node_id} に output_format が無いか object でない")
                return got
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    raise ValueError(f"YAML に node {node_id} が無い")
