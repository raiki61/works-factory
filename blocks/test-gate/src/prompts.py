"""3 つの AI の node の指示に渡す値の組み立て（docs/design/test-gate.md の 2.3・3.3・4.3 の差し込み口の一覧）。

指示の文は prompts/<node-id>.md が持ち、ここは値を集めて prompt.emit に渡すだけ。組んだ指示は place の <node-id>-prompt-<n>.md に書く。
"""
from __future__ import annotations

import pathlib

import prompt

import declared_checks   # lib/
import rolekit           # lib/

from src import files


def ci(place, intake: dict, snap: dict, root) -> dict:
    """任せ先の CI の役の 1 回目の指示"""
    rejects = rolekit.rejected(place, declared_checks.CI_ROLE)
    values = {"reject": rolekit.rejects_text(rejects), "root": str(root), "base": intake["base"], "copy_dir": snap["copy_dir"],
              "tmp_dir": snap["tmp_dir"], "mode": intake["mode"], "attempt": len(rejects) + 1}
    return prompt.emit("ci", values, None, prompt.round_of("ci"))


def ci_fix(place) -> dict:
    """任せ先の CI の役の出し直しの指示（1 回目の役の会話の続き。最後の拒否の文と、機械が合わせた前の答えの控えのパス）"""
    rejects = rolekit.rejected(place, declared_checks.CI_ROLE)
    values = {"rejection": rejects[-1] if rejects else "", "candidate": str(files.candidate(place))}
    return prompt.emit("ci-fix", values, None, prompt.round_of("ci-fix"))


def suite_write(brief_file: str) -> dict:
    """TDD の実行器の書き手の指示"""
    return prompt.emit("suite-write", {"brief_file": brief_file}, None, prompt.round_of("suite-write"))
