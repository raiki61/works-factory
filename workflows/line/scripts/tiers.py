# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""段 → 回す物の表を引く node tiers（docs/design/line.md の 5.1）。判定の後に 1 度。

判定のまとめの段の語 tier を src.tiers の表で引き、{tier, omits, merge, tree, adds, lines, stop_reason} を返す。tree は事前審査の
木の語（features の review_tree の名指し tree_named が on・off ならその語、無ければ段の足す機能と auto の読みで entry.switch）。
段の語が表に無ければ標準と読み、lines に訳を足す。固定材料の run は判定が飛ぶのでここも飛び、fix-in が運んだ段で同じ表を引き直す。
例外の時は標準の形と止めの語 works:line-script（計画の往復へ進めない）。

入力（with:）: tier（$judge.output.tier）・tree_named（$start.output.ports.tree_named）・record（始めの記録の pointer）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    raw_tier, raw_named, raw_record = os.environ.get("INPUTS_TIER"), os.environ.get("INPUTS_TREE_NAMED"), os.environ.get("INPUTS_RECORD")
    from src import tiers
    record = ports.parsed(raw_record)
    record = ports.json(raw_record, "start-record.schema.json") if record is not None else None
    return {**tiers.switches(ports.text(raw_tier), ports.text(raw_named), record), "stop_reason": ""}


def fallback(reason: str) -> dict:
    from src import guard
    return {"tier": "標準", "omits": False, "merge": False, "tree": "auto", "adds": [], "lines": [f"段の表を引けなかった（{reason}）"],
            "stop_reason": guard.LINE_SCRIPT}


ports.run(compute, fallback)
