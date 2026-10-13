# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立設計の支度（boardview.r2_prompt）: 目的の文・実測した制約・人の関所の答え・依頼が名指した設計書の節・対象の地図だけを
組んで役に貼る本文を返す。読む入力は目的・判定（隣の premises.json だけ）・始めの記録・人の関所の答えだけ（独立設計の隔て）"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402


prompt = boardview.r2_prompt(
    Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER, cwd=Path.cwd(),
    purpose=boundary.needed(os.environ["INPUTS_PURPOSE"], "purpose"), judgment=boundary.needed(os.environ["INPUTS_JUDGMENT"], "judgment"),
    start=boundary.pointed(os.environ["INPUTS_START"]), answers=boundary.parsed(os.environ["INPUTS_ANSWERS"]))
boundary.returns({"prompt": prompt})
