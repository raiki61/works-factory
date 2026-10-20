"""3 つの AI の node の指示に渡す値の組み立て（docs/design/test-gate.md の 2.3・3.3・4.3 の差し込み口の一覧）。

指示の文は prompts/<node-id>.md が持ち、ここは値を集めて prompt.emit に渡すだけ。組んだ指示は place の <node-id>-prompt-<n>.md に書く。
"""
from __future__ import annotations

import pathlib

import prompt

import baseline_red      # lib/
import declared_checks   # lib/
import rolekit           # lib/

from src import suite

NO_BASE = "(none)"


def ci(place, intake: dict, snap: dict, root) -> dict:
    """任せ先の CI の役の 1 回目の指示。前の回の拒否が在る回だけ、拒否の段落が入る"""
    rejects = rolekit.rejected(place, declared_checks.CI_ROLE)
    values = {"rejection": rolekit.rejects_text(rejects), "root": str(root), "base": intake["base"] or NO_BASE,
              "copy_dir": snap["copy_dir"], "tmp_dir": snap["tmp_dir"], "mode": intake["mode"], "attempt": len(rejects) + 1,
              "decl_name": declared_checks.DECL_NAME, "lang": prompt.lang(intake["lang"]),
              **{status: status for status in declared_checks.STATUSES}}
    return prompt.emit("ci", values, {"rejected": bool(rejects)}, prompt.round_of("ci"))


def ci_fix(place, intake: dict) -> dict:
    """任せ先の CI の役の出し直しの指示（1 回目の役の会話の続き。最後の拒否の文と、機械が合わせた前の答えの控えのパス）"""
    from src import files
    rejects = rolekit.rejected(place, declared_checks.CI_ROLE)
    values = {"rejection": rejects[-1] if rejects else "", "candidate": str(files.candidate(place)), "lang": prompt.lang(intake["lang"])}
    return prompt.emit("ci-fix", values, None, prompt.round_of("ci-fix"))


def suite_write(place, intake: dict) -> dict:
    """TDD の実行器の書き手の指示。材料（対象の根・宣言が在るか・test_cmd）は指示に直に入れる"""
    root = pathlib.Path.cwd().resolve()
    test_cmd = suite.load(place).get("test_cmd") or ""
    values = {"root": str(root), "decl_name": declared_checks.DECL_NAME, "test_cmd": test_cmd, "fence": fence_of(test_cmd),
              "only_env": baseline_red.ONLY_ENV, "lang": prompt.lang(intake["lang"])}
    when = {"declared": (root / declared_checks.DECL_NAME).is_file(), "test_cmd": bool(test_cmd.strip())}
    return prompt.emit("suite-write", values, when, prompt.round_of("suite-write"))


def fence_of(text: str) -> str:
    """text を囲むバッククォートの柵: 3 つ以上で、text の中のバッククォートの最長の並びより 1 つ長い"""
    longest = run = 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)
