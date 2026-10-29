"""structure の place のファイルの名と、出口が返す宣言（docs/design/structure.md の 1.4・1.5）。名の字はこのモジュールだけが持つ。
標準ライブラリだけ（出口の script が lib を読み込めない時にも、同じ名で控えを書くために読む）。"""
UNITS_FILE = "units.json"                # paths の在る単位
SKIPPED_FILE = "skipped-units.json"      # paths の空な単位の id
STRUCTURE_FILE = "structure.json"        # 段 A の実測
VIEW_FILE = "view.json"                  # 目に見せる JSON（根拠の JSON Pointer はこの中を指す）
DESIGN_FILE = "design.jsonl"             # 設計の行（measure が 0 バイトで置き、受け付けが書く）
EYE_FILE = "eye.json"                    # 目の控え {started_at, status, wall_s}
STATE_FILE = "structure-state.json"      # 返す控え
INTENT_FILE = "intent.json"              # 見せた書いた意図 [{path, rev, text, cut, reason}]
AFTER_FILE = "structure-after.json"      # after の段 B の実測（読み手の口 structmark.read_after が持つ字と同じ）
DIFF_FILE = "after.diff"                 # after の差分の全体
SKETCH_FILE = "sketches.json"            # 構造を描く役が受け付けた行 [{unit_id, system, kind}]（before だけ）
GENERAL_FILE = "general.json"            # 一般の構造を描く目が受け付けた行 [{unit_id, kind, structure, why}]（before だけ）
MODES = ("before", "after")
NAME = "structure-eye"                   # 却下の控えの名（rejects-structure-eye.json）と AI の node の id
SKETCH = "system-sketch"                 # 構造を描く役の node の id と却下の控えの名
GENERAL = "general-structure"            # 一般の構造を描く目の node の id と却下の控えの名
ROLES = (SKETCH, GENERAL, NAME)
# measure が消してよい物（この block が名を持つ物だけ。広い形で消さない）
OWN_FILES = (UNITS_FILE, SKIPPED_FILE, STRUCTURE_FILE, VIEW_FILE, EYE_FILE, STATE_FILE, INTENT_FILE, AFTER_FILE, DIFF_FILE,
             SKETCH_FILE, GENERAL_FILE, *(f"rejects-{role}.json" for role in ROLES))
OWN_PROMPTS = (*(f"{role}-prompt-*.md" for role in ROLES), f"{GENERAL}-system-*.md")
# line が、この block の中の node が落ちても先へ進めてよい宣言 [{node, bare}]。node は自分の node の id か、- で終わる頭
OPTIONAL = [{"node": "measure", "bare": False}, {"node": "structure-eye-", "bare": False},
            {"node": "structure-eye", "bare": True}, {"node": "structure-eye-", "bare": True},
            {"node": "system-sketch-", "bare": False}, {"node": "system-sketch", "bare": True}, {"node": "system-sketch-", "bare": True},
            {"node": "sketched", "bare": False},
            {"node": "general-structure-", "bare": False}, {"node": "general-structure", "bare": True},
            {"node": "general-structure-", "bare": True}]
