# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返し spec-in（docs/design/judge-eyes.md の 1.3 の 4）: 仕様の段を挟まないか spec が承認で終われば go。仕様が足した受け入れ条件の行を
依頼の行の後ろに積んだ依頼を place に書き、後の段（並行 PR・前提の実測・世界の解・先行議論の突合）へ pointer で渡す。落ちない"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


RECEIVED = ("got", "why")   # 受け皿の返りの欄（受け皿の output_format の required の全部）


def _got(raw):
    whole = ports.picked(raw, RECEIVED)
    return whole["got"] if whole is not None else None


def compute():
    import jsonfile
    from src import feed, files
    got = _got(os.environ.get("INPUTS_SPEC_OUT"))
    gate = feed.spec_gate(ports.flag(os.environ.get("INPUTS_SPEC")), got)
    added = []
    if gate["go"] and isinstance(got, dict) and got.get("added_rows"):
        added = ports.json(json.dumps(got["added_rows"]), "shared:request.schema.json")
        if not isinstance(added, list):
            raise ValueError("仕様が足した行のファイルが行の配列でない")
    request = feed.merged(ports.json(os.environ.get("INPUTS_REQUEST") or "[]", "shared:request.schema.json"), added)
    path = jsonfile.write(ports.place() / files.REQUEST, request)
    return {**gate, "request": ports.pointer(path, "json(shared:request.schema.json)"), "spec": (got or {}).get("spec") if gate["go"] else None,
            "added_rows": got.get("added_rows") if added else None, "added_origin": str(got.get("added_origin") or "") if added else ""}


def fallback(why: str) -> dict:
    spec_on = ports.text(os.environ.get("INPUTS_SPEC")).strip() == "true"
    return {"go": False, "stop_reason": "works:spec" if spec_on else "works:request",
            "reason": f"仕様の段の後の返しが落ちた（{why}）", "request": None, "spec": None, "added_rows": None, "added_origin": ""}


ports.run(compute, fallback)
