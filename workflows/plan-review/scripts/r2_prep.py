# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立設計の支度（boardview.r2_prompt）: 目的の文・実測した制約・人の関所の答え・依頼が名指した設計書の節・対象の地図だけを
組んで役に貼る本文を返す。読む入力は目的・実測した制約 premises・目的の監査の受けた返答 purpose_review・始めの記録・人の関所の答え
だけ（独立設計の隔て。判定の中身は読まない）"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402


prompt = boardview.r2_prompt(
    Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER, cwd=Path.cwd(),
    purpose=boundary.needed(os.environ["INPUTS_PURPOSE"], "purpose"), premises=boundary.pointed(os.environ.get("INPUTS_PREMISES", "")),
    purpose_review=boundary.pointed(os.environ.get("INPUTS_PURPOSE_REVIEW", "")), start=boundary.pointed(os.environ["INPUTS_START"]), answers=boundary.parsed(os.environ["INPUTS_ANSWERS"]))
boundary.returns({"prompt": prompt})
