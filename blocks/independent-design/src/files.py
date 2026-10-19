"""独立設計の block の place のファイルの名と、却下の控えの役の名（docs/design/independent-design.md の 1.4）。名はこのモジュールだけが持つ。

- intake.json: port を読んだ値と {due, status, reason}
- design-tree.json: 役を起こす前の作業ツリーの姿（accept.tree_state）
- design-prompt-<n>.md・design-system-<n>.md: 組んだ指示と system prompt（prompt.emit が書く）
- design-premises.json: 貼った前提の控え {node, given, withheld, seen, claims}
- design.json: 受け付けを通った返答
- rejects-r2.design.json: 却下の控え（lib/rolekit が名を組む）
- design-crash.json: prep・accept の node が落ちた時の {step, why}（出口が設計の無い訳に使う）
- finish.json: 出口の返りの写し
"""
import pathlib

import rolekit   # lib/

NODE = "r2.design"            # 却下の控えの名（lib/design.py の NODE と同じ字）。AI の node の id は AI_NODE
AI_NODE = "design"            # AI の node の id（prompts/design.md・prompts/design.system.md）
INTAKE = "intake.json"
TREE = "design-tree.json"
PREMISES = "design-premises.json"
DESIGN = "design.json"
FINISH = "finish.json"
CRASH = "design-crash.json"
REJECTS = rolekit.rejects_path(pathlib.Path(), NODE).name
# 入口が消す物: この block が名を持つファイルだけ（名で引く。広い形で消さない）
OWN_FILES = (INTAKE, TREE, PREMISES, DESIGN, FINISH, CRASH, REJECTS)
OWN_PROMPTS = (f"{AI_NODE}-prompt-*.md", f"{AI_NODE}-system-*.md")
