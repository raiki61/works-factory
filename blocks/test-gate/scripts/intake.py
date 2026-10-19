# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""試験の関門の入口: port を読み、この block の前の回のファイルを消して intake.json（port の値）と suite-state.json（TDD の実行器の控え）
を書く。後ろの script は port を読まずに intake.json を読む。port が読めなければ落ちずに ok: false と、読めなかった port と訳を返し、
intake.json には読めなかった訳（failed）と、読めた形を置く（返す node が証拠に名指す）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import requestrows  # noqa: E402

RAW = {"mode": os.environ.get("INPUTS_MODE"), "test_cmd": os.environ.get("INPUTS_TEST_CMD"),
       "tdd_suite": os.environ.get("INPUTS_TDD_SUITE"), "base": os.environ.get("INPUTS_BASE"),
       "request": os.environ.get("INPUTS_REQUEST"), "request_scope": os.environ.get("INPUTS_REQUEST_SCOPE"),
       "baseline": os.environ.get("INPUTS_BASELINE"), "reuse_dir": os.environ.get("INPUTS_REUSE_DIR"),
       "reuse_key": os.environ.get("INPUTS_REUSE_KEY"), "user_env_dir": os.environ.get("INPUTS_USER_ENV_DIR"),
       "lang": os.environ.get("INPUTS_LANG")}


def port(name: str, form, default):
    """空の port は default。読めなければ ValueError（port の名と訳）"""
    if ports.text(RAW[name]).strip() == "":
        return default
    try:
        return form(RAW[name])
    except (ValueError, OSError) as error:
        raise ValueError(f"port {name} が読めない: {error}") from None


def read(modes) -> dict:
    mode = ports.text(RAW["mode"]).strip()
    if mode not in modes:
        raise ValueError(f"mode は {'・'.join(modes)} のどれか: {mode}")
    baseline = port("baseline", ports.file, None) if mode == "final" else None   # base では渡されても読まない
    text = lambda name: ports.text(RAW[name]).strip()   # noqa: E731
    return {"mode": mode, "test_cmd": ports.text(RAW["test_cmd"]), "tdd_suite": text("tdd_suite"), "base": text("base"),
            "request": port("request", requestrows.findings, []), "request_scope": port("request_scope", ports.flag, False),
            "baseline": str(baseline) if baseline else "", "reuse_dir": text("reuse_dir"), "reuse_key": text("reuse_key"),
            "user_env_dir": text("user_env_dir"), "lang": text("lang")}


def compute():
    from src import files, suite
    place = ports.place()
    files.fresh_place(place)
    try:
        doc = read(files.MODES)
    except ValueError as error:
        mode = ports.text(RAW["mode"]).strip()
        (place / files.INTAKE).write_text(json.dumps({"failed": str(error), "mode": mode if mode in files.MODES else ""},
                                                     ensure_ascii=False) + "\n", encoding="utf-8")
        return {"ok": False, "reason": str(error)}
    (place / files.INTAKE).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    suite.write(place, doc["test_cmd"], doc["tdd_suite"])
    return {"ok": True, "reason": ""}


ports.run(compute, lambda why: {"ok": False, "reason": f"入口が落ちた（{why}）"})
