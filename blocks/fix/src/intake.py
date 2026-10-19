"""port の読みと形ごとの必須（docs/design/fix.md の 1.2・7 節の intake.py）。

read(raw) は {入力の名: 字}（script が INPUTS_<名> を字のまま渡す）から読んだ値の dict を返す。読めない port は
ValueError（「入力 <名>: …」）。空の字は渡されていない（既定）と読む。
"""
from __future__ import annotations

import json
import pathlib

import ports

from src import files

SCHEMAS = {"judgment": "shared:judgment.schema.json", "plan": "plan-fields.schema.json", "fix_plan": "fix-plan.schema.json",
           "answer_ties": "answer-ties.schema.json", "materials": "fix-materials.schema.json",
           "skip_rerun": "skip-rerun.schema.json", "answers": "fix-answers.schema.json",
           "request_answers": "fix-request-answers.schema.json", "plan_review": "fix-plan-review.schema.json",
           "prior": "carry.schema.json", "only_items": "only-items.schema.json", "group": "group.schema.json",
           "excluded": "excluded.schema.json"}
FILES = ("ripple", "baseline", "policy", "request")
FLAGS = {"unattended": False, "parallel": True}
TEXTS = ("notes", "test_cmd", "tdd_suite", "reuse_dir", "reuse_key", "user_env_dir", "from_tree", "out_dir", "lang")
DEFAULTS = {"judgment": None, "plan": None, "fix_plan": None, "answer_ties": None, "materials": None, "skip_rerun": [],
            "answers": None, "request_answers": [], "plan_review": None, "prior": None, "only_items": [], "group": None,
            "excluded": None}
NAMES = ("mode", *SCHEMAS, *FILES, *FLAGS, *TEXTS)
NEEDED = "入力 {name}: {mode} の形には要る"


def _blank(raw) -> bool:
    return ports.text(raw).strip() == ""


def _port(name: str, raw, form):
    try:
        return form(raw)
    except (ValueError, OSError) as error:
        raise ValueError(f"入力 {name}: {error}") from None


def read(raw: dict) -> dict:
    """読んだ値: json の port は値（空は DEFAULTS）、file の port は字のパス（空は ""）、flag は真偽、text は字（前後の空白を
    落とす。test_cmd と notes は字のまま）"""
    mode = "group" if _blank(raw.get("mode")) else _port("mode", raw.get("mode"), lambda r: ports.choice(r, files.MODES))
    out = {"mode": mode}
    for name, schema in SCHEMAS.items():
        out[name] = DEFAULTS[name] if _blank(raw.get(name)) else _port(name, raw.get(name), lambda r, s=schema: ports.json(r, s))
    for name in FILES:
        got = None if _blank(raw.get(name)) else _port(name, raw.get(name), ports.file)
        out[name] = str(got) if got else ""
    for name, default in FLAGS.items():
        out[name] = default if _blank(raw.get(name)) else _port(name, raw.get(name), ports.flag)
    for name in TEXTS:
        text = ports.text(raw.get(name))
        out[name] = text if name in ("notes", "test_cmd") else text.strip()
    out["excluded"] = _port("excluded", out["excluded"], excluded_rows)
    if mode == "whole" and out["judgment"] is None:
        raise ValueError(NEEDED.format(name="judgment", mode=mode))
    if mode == "group":
        if out["group"] is None:
            raise ValueError(NEEDED.format(name="group", mode=mode))
        if not out["out_dir"] and out["judgment"] is None:
            raise ValueError(NEEDED.format(name="judgment", mode="out_dir の無い group"))
    return out


def write(place, doc: dict) -> pathlib.Path:
    path = pathlib.Path(place) / files.INTAKE
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def load(place) -> dict:
    """place の intake.json（intake が書いた物）。無い・読めなければ ValueError（intake が走らなかった）"""
    path = pathlib.Path(place) / files.INTAKE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"place に {files.INTAKE} が無いか読めない（intake が走らなかった。{error}）") from None
    if not isinstance(doc, dict):
        raise ValueError(f"{path} が object でない")
    return doc


def run_values(doc: dict, run_id: str) -> dict:
    """values.json の値（src/runvals.KEYS）。reuse_key が空ならこの run の id"""
    return {"tdd_suite": doc["tdd_suite"], "test_cmd": doc["test_cmd"], "reuse_key": doc["reuse_key"] or run_id,
            "reuse_dir": doc["reuse_dir"], "user_env_dir": doc["user_env_dir"], "lang": doc["lang"], "policy": doc["policy"],
            "request_file": doc["request"], "answers": doc["request_answers"], "unattended": doc["unattended"],
            "parallel": doc["parallel"], "skip_rerun": doc["skip_rerun"], "excluded": excluded_rows(doc.get("excluded"))}


def excluded_rows(got) -> list:
    """port excluded（並行 PR の確かめが外した hunk の控え {excluded: [...]} か、その行の配列。null は外した hunk が無い）の行
    [{pr, file, start, end, why, text?, sha256?}]。形の崩れた行はスキーマが拒むので、ここでは捨てずに start <= end だけ照らし、
    崩れていれば ValueError"""
    rows = got.get("excluded") if isinstance(got, dict) else got
    rows = list(rows or [])
    for i, r in enumerate(rows):
        if r["start"] > r["end"]:
            raise ValueError(f"excluded[{i}]（{r['file']}）: start {r['start']} が end {r['end']} より大きい")
    return rows
