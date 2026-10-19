# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す node verdict（docs/design/judge-eyes.md の 1.4）: 受け皿の got から止めの語の順の最初の物と line が配る欄を組み、目的の監査の受けた
返答を place の purpose-review.json に写し（受けていなければ {}）、まとめを verdict.json に写す。
落ちない: 中の誤りは全部捕まえて ok: false と works:judge を返す。境の口か lib を読めない時も、標準ライブラリだけの src/fallback で返す"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]


def _got(ports, raw):
    raw = ports.text(raw).strip()
    whole = None if raw in ("", "null") else ports.json(raw)
    return whole.get("got") if isinstance(whole, dict) else None


def _value(ports, raw):
    raw = ports.text(raw).strip()
    return None if raw in ("", "null") else ports.json(raw)


def _has_rows(ports, ptr) -> tuple:
    """(世界の解の行のファイルに行が在るか, 読めない訳)。行の無い段は空のファイルを置くので、行が 0 なら null で返す（今の J29）"""
    if not isinstance(ptr, dict):
        return False, ""
    try:
        text = ports.file(json.dumps(ptr)).read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        return False, f"世界の解の行のファイルが読めない（{error}）"
    return any(line.strip() for line in text.splitlines()), ""


def _review_reply(ports, got) -> tuple:
    """(目的の監査の受けた返答か {}, 読めない訳)。受けていない・読めない時は {}"""
    import materialkit
    if not isinstance(got, dict) or not got.get("material"):
        return {}, ""
    try:
        reply = materialkit.read(ports.file(json.dumps(got["material"]))).get("reply")
    except ValueError as error:
        return {}, f"目的の監査の素材が読めない（{error}）"
    return (reply if isinstance(reply, dict) else {}), ""


def compute(ports):
    import jsonfile
    from src import files, verdict
    received = {
        "head-depth": _got(ports, os.environ.get("INPUTS_HEAD_DEPTH_OUT")),
        "spec": _got(ports, os.environ.get("INPUTS_SPEC_OUT")),
        "spec-in": _value(ports, os.environ.get("INPUTS_SPEC_IN")),
        "parallel-pr": _got(ports, os.environ.get("INPUTS_PARALLEL_PR_OUT")),
        "premises": _got(ports, os.environ.get("INPUTS_PREMISES_OUT")),
        "purpose": _got(ports, os.environ.get("INPUTS_PURPOSE_OUT")),
        "world": _got(ports, os.environ.get("INPUTS_WORLD_OUT")),
        "prior-decisions": _got(ports, os.environ.get("INPUTS_PRIOR_DECISIONS_OUT")),
        "purpose-review": _got(ports, os.environ.get("INPUTS_PURPOSE_REVIEW_OUT")),
        "local-review": _got(ports, os.environ.get("INPUTS_LOCAL_REVIEW_OUT")),
        "consistency-bypass": _got(ports, os.environ.get("INPUTS_CONSISTENCY_BYPASS_OUT")),
        "hygiene": _got(ports, os.environ.get("INPUTS_HYGIENE_OUT")),
        "external-standards": _got(ports, os.environ.get("INPUTS_EXTERNAL_STANDARDS_OUT")),
        "procedure-trace": _got(ports, os.environ.get("INPUTS_PROCEDURE_TRACE_OUT")),
        "test-double-fidelity": _got(ports, os.environ.get("INPUTS_TEST_DOUBLE_FIDELITY_OUT")),
        "main-path-observation": _got(ports, os.environ.get("INPUTS_MAIN_PATH_OBSERVATION_OUT")),
        "provenance": _got(ports, os.environ.get("INPUTS_PROVENANCE_OUT")),
        "diagnose-in": _value(ports, os.environ.get("INPUTS_DIAGNOSE_IN")),
        "diagnose": _got(ports, os.environ.get("INPUTS_DIAGNOSE_OUT")),
        "verify": _got(ports, os.environ.get("INPUTS_VERIFY_OUT")),
    }
    world = received["world"]
    reply, unread = _review_reply(ports, received["purpose-review"])
    rows, unrows = _has_rows(ports, (world or {}).get("rows"))
    out = verdict.build(received, world_on=ports.flag(os.environ.get("INPUTS_WORLD")), world_has_rows=rows,
                        notes=tuple(n for n in (unrows, unread) if n))
    place = ports.place()
    out["purpose_review"] = ports.pointer(jsonfile.write(place / files.PURPOSE_REVIEW, reply))
    json.dumps(out, allow_nan=False)
    jsonfile.write(place / files.VERDICT, out)
    return out


def main():
    try:
        import ports
    except Exception as error:  # noqa: BLE001 — 境の口を読めない時も返す node は落ちない
        from src import fallback
        print(json.dumps(fallback.fallen(f"境の口が読めない: {type(error).__name__}: {error}"), ensure_ascii=False), flush=True)
        return

    def fell(why):
        from src import fallback
        return fallback.fallen(why)

    ports.run(lambda: compute(ports), fell)


main()
