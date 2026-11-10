# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す node verdict（docs/design/judge-eyes.md の 1.4）: include した block の返りから止めの語の順の最初の物と line が配る欄を組み、目的の
監査の受けた返答を place の purpose-review.json に写し（受けていなければ {}）、まとめを verdict.json に写す。
落ちない: 中の誤りは全部捕まえて ok: false と works:judge を返す。境の口か lib を読めない時も、標準ライブラリだけの src/fallback で返す。

入力（with:）: <block>_out（include した block の返りまるごと。飛ばされた block は null。読む欄は下の名の並びで選び、どれも欄 optional を
無くてよい欄として読む）と、返しの spec_in・diagnose_in（返りまるごと）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]

# include した block の返りのうち読む欄（src/verdict.py が読む物。欄 optional はどれも無くてよい欄として足す）
HEAD_DEPTH = ("ok", "status", "reason", "tier", "why", "rows", "record", "report")
SPEC = ("ok", "status", "stop_reason", "reason", "spec", "added_rows", "added_origin", "report")
PARALLEL_PR = ("ok", "status", "stop_reason", "reason", "material", "excluded", "drafts", "reads", "downgrades", "report")
PREMISES = ("ok", "status", "reason", "constraints", "report")
PURPOSE = ("ok", "status", "reason", "purpose", "purpose_text", "source", "means", "report")
WORLD = ("ok", "status", "reason", "rows", "classes", "dropped", "report")
MATERIAL = ("ok", "status", "reason", "material", "report")
DIAGNOSE = ("ok", "status", "mode", "stop_reason", "reason", "ready", "judgment", "units", "questions", "inputs", "brief", "materials",
            "out_of_purpose", "answer_ties", "downgrades", "report")
VERIFY = ("ok", "status", "stop_reason", "reason", "verify", "report")


def _plain(got):
    return None if got is None else dict(got)


def _has_rows(ports, ptr) -> tuple:
    """(世界の解の行のファイルに行が在るか, 読めない訳)。行の無い段は空のファイルを置くので、行が 0 なら null で返す（今の J29）"""
    if not isinstance(ptr, dict):
        return False, ""
    try:
        text = ports.file(json.dumps(ptr), "jsonl(lib:world-row.schema.json)").read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        return False, f"世界の解の行のファイルが読めない（{error}）"
    return any(line.strip() for line in text.splitlines()), ""


def _review_reply(ports, got) -> tuple:
    """(目的の監査の受けた返答か {}, 読めない訳)。受けていない・読めない時は {}"""
    import materialkit
    if not isinstance(got, dict) or not got.get("material"):
        return {}, ""
    try:
        reply = materialkit.read(ports.file(json.dumps(got["material"]), "json(shared:material.schema.json)")).get("reply")
    except ValueError as error:
        return {}, f"目的の監査の素材が読めない（{error}）"
    return (reply if isinstance(reply, dict) else {}), ""


def compute(ports):
    import jsonfile
    from src import files, verdict
    received = {
        "head-depth": _plain(ports.picked(os.environ.get("INPUTS_HEAD_DEPTH_OUT"), HEAD_DEPTH, optional=("optional",))),
        "spec": _plain(ports.picked(os.environ.get("INPUTS_SPEC_OUT"), SPEC, optional=("optional",))),
        "spec-in": ports.parsed(os.environ.get("INPUTS_SPEC_IN")),   # 返しの返りまるごと（Archon が output_format で照らした値）
        "parallel-pr": _plain(ports.picked(os.environ.get("INPUTS_PARALLEL_PR_OUT"), PARALLEL_PR, optional=("optional",))),
        "premises": _plain(ports.picked(os.environ.get("INPUTS_PREMISES_OUT"), PREMISES, optional=("optional",))),
        "purpose": _plain(ports.picked(os.environ.get("INPUTS_PURPOSE_OUT"), PURPOSE, optional=("optional",))),
        "world": _plain(ports.picked(os.environ.get("INPUTS_WORLD_OUT"), WORLD, optional=("optional",))),
        "prior-decisions": _plain(ports.picked(os.environ.get("INPUTS_PRIOR_DECISIONS_OUT"), MATERIAL, optional=("optional",))),
        "purpose-review": _plain(ports.picked(os.environ.get("INPUTS_PURPOSE_REVIEW_OUT"), MATERIAL, optional=("optional",))),
        "local-review": _plain(ports.picked(os.environ.get("INPUTS_LOCAL_REVIEW_OUT"), MATERIAL, optional=("optional",))),
        "consistency-bypass": _plain(ports.picked(os.environ.get("INPUTS_CONSISTENCY_BYPASS_OUT"), MATERIAL, optional=("optional",))),
        "hygiene": _plain(ports.picked(os.environ.get("INPUTS_HYGIENE_OUT"), MATERIAL, optional=("optional",))),
        "external-standards": _plain(ports.picked(os.environ.get("INPUTS_EXTERNAL_STANDARDS_OUT"), MATERIAL, optional=("optional",))),
        "procedure-trace": _plain(ports.picked(os.environ.get("INPUTS_PROCEDURE_TRACE_OUT"), MATERIAL, optional=("optional",))),
        "test-double-fidelity": _plain(ports.picked(os.environ.get("INPUTS_TEST_DOUBLE_FIDELITY_OUT"), MATERIAL, optional=("optional",))),
        "main-path-observation": _plain(ports.picked(os.environ.get("INPUTS_MAIN_PATH_OBSERVATION_OUT"), MATERIAL, optional=("optional",))),
        "provenance": _plain(ports.picked(os.environ.get("INPUTS_PROVENANCE_OUT"), MATERIAL, optional=("optional",))),
        "diagnose-in": ports.parsed(os.environ.get("INPUTS_DIAGNOSE_IN")),
        "diagnose": _plain(ports.picked(os.environ.get("INPUTS_DIAGNOSE_OUT"), DIAGNOSE, optional=("optional",))),
        "verify": _plain(ports.picked(os.environ.get("INPUTS_VERIFY_OUT"), VERIFY, optional=("optional",))),
    }
    world = received["world"]
    reply, unread = _review_reply(ports, received["purpose-review"])
    rows, unrows = _has_rows(ports, (world or {}).get("rows"))
    out = verdict.build(received, world_on=ports.flag(os.environ.get("INPUTS_WORLD")), world_has_rows=rows,
                        notes=tuple(n for n in (unrows, unread) if n))
    place = ports.place()
    out["purpose_review"] = ports.pointer(jsonfile.write(place / files.PURPOSE_REVIEW, reply), "json(shared:purpose-review.schema.json)")
    json.dumps(out, allow_nan=False)
    jsonfile.write(place / files.VERDICT, out)
    return out


def main():
    try:
        import ports
    except Exception as error:  # noqa: BLE001 — 境の口を読めない時も返す node は落ちない
        from src import fallback
        print(json.dumps(fallback.fallen(f"境の口が読めない: {type(error).__name__}: {error}"), ensure_ascii=False, allow_nan=False), flush=True)
        return

    def fell(why):
        from src import fallback
        return fallback.fallen(why)

    ports.run(lambda: compute(ports), fell)


main()
