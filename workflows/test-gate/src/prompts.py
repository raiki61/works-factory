"""AI の node（TDD の実行器の書き手）の指示に渡す値の組み立て（docs/design/test-gate.md の 4.3 の差し込み口の一覧）。

指示の文は prompts/<node-id>.md が持ち、ここは値を集めて prompt.emit に渡すだけ。組んだ指示は place の <node-id>-prompt-<n>.md に書く。
"""
from __future__ import annotations

import pathlib

import prompt

import baseline_red      # lib/
import declared_checks   # lib/
import suitewrite        # lib/

from src import suite


def suite_write(place, intake: dict) -> dict:
    """TDD の実行器の書き手の指示。材料（対象の根・宣言が在るか・test_cmd）は指示に直に入れる"""
    root = pathlib.Path.cwd().resolve()
    test_cmd = suite.load(place).get("test_cmd") or ""
    values = {"root": str(root), "decl_name": declared_checks.DECL_NAME, "test_cmd": test_cmd, "fence": fence_of(test_cmd),
              "only_env": baseline_red.ONLY_ENV, "lang": prompt.lang(intake["lang"])}
    when = {"declared": (root / declared_checks.DECL_NAME).is_file(), "test_cmd": bool(test_cmd.strip())}
    return prompt.emit("suite-write", values, when, prompt.round_of("suite-write"))


def fence_of(text: str) -> str:
    """text を囲むバッククォートの柵（lib/suitewrite.fence。修正の段の書き直しの指示と同じ口）"""
    return suitewrite.fence(text)
