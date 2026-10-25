"""port facts の値を、既定を埋めた dict にする（docs/design/report.md の 1.2）。形の違う欄は欄の名を挙げた ValueError で、黙って既定にしない。"""
import copy
import json
import pathlib

import ports

from engine.schema import validate_schema   # lib/graphloops/engine/schema.py

SCHEMA = pathlib.Path(ports.SHARED) / "schemas" / "facts.schema.json"   # 書き手 line と同じ共通の形
DEFAULTS = {
    "start_ok": False, "problems": [], "notes": [], "gates": [], "stops": [], "halts": [],
    "waits": {"conflicts": [], "conflicts_if_closed": [], "others": []}, "cut": None, "optional": [], "returned": [],
    "no_fix": False, "left": [], "proved": False, "head": {"before": [], "stopped": [], "after": [], "notices": []},
    "asks": [], "tallied": {}, "counted_left": [], "decisions": {"before": [], "after": [], "outside": []},
    "apply": {"sealed": False, "placed": False, "redesign": "", "said": "", "pr": None, "commits": []},
    "carry": {"findings": [], "prior": [], "drafts": [], "constraints": []}, "stop_lines": {"before": [], "after": []},
    "outcome_parts": {"gate": "", "eyes": "", "data": ""}, "round": None, "line_rev": "",
}


def read(value) -> dict:
    """facts の値を、欄の形を照らし、既定を埋めた dict に。None は空のオブジェクト（事実が渡されていない）として読む"""
    value = {} if value is None else value
    if not isinstance(value, dict):
        raise ValueError(f"facts が JSON のオブジェクトでない（{type(value).__name__}）")
    shape = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = validate_schema(value, shape)
    if errors:
        raise ValueError(f"facts が形に合わない: {' / '.join(errors[:5])}")
    out = copy.deepcopy(DEFAULTS)
    for key, got in value.items():
        if isinstance(DEFAULTS[key], dict) and key != "tallied" and isinstance(got, dict):
            out[key].update(copy.deepcopy(got))
        else:
            out[key] = copy.deepcopy(got)
    out["left"] = [{**row, "unmeasured": row.get("unmeasured") is True} for row in out["left"]]
    return out


def from_port(raw) -> dict:
    """INPUTS_FACTS の字（値そのもの・ファイルのパス・pointer）を読む。空の字は空のオブジェクト（既定の入力 {}）"""
    if not ports.text(raw).strip():
        return read({})
    return read(ports.json(raw, "shared:facts.schema.json"))
