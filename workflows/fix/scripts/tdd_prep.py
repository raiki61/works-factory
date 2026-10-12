# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 tdd-prep（形 group の tdd-loop の中。役 tdd の前）: 今の段の指示書を組んでファイルに書く（tddloop.prep → fixrules.tdd_render。
決まりの正本は commands/fix-rules/ の common.md と tdd.md）。

輪は周ごとに新しい会話（fresh_context: true）なので、前の単位と今の単位のこれまでは tddloop.prep が引き継ぎの節
（tddloop.handoff_lines。今の単位の段の結果 current_lines を含む）で指示書に載せる。前の周に拒んだ理由も指示書に載る。
run の値: 判定の写し（judgment.json）・修正案の役の返答の写し（p2.fix_plan.json。無ければ空）・人の方針の文書（始めの記録の
固めた版の写し）・依頼の文のファイル（request_file）・修正前の関所の一言（human-notes.md）・言語の 1 行（fixboard.lang_line）。brief は置き場の凍結した欄と修正案から切る
（planbrief.cut。修正案の無い run は無し）。
輪が済んだ（resume で 1 周目から回し直された）・実行器の無い run は何も書かずに {prompt_file: "", go: false}。
返り {prompt_file, go}。輪の状態が読めない・指示書を組めない: 標準エラーに 1 行で 1。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402

import fixboard  # noqa: E402
import fixrules  # noqa: E402
import policy  # noqa: E402
import rulebook  # noqa: E402
import startrec  # noqa: E402
import tddloop  # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules"
rulebook.CANON = RULES / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = RULES


def main() -> dict:
    place = fixio.place()
    repo = fixio.repo()
    started = fixboard.read_json(place / fixboard.TDD_START_FILE)
    if not isinstance(started, dict):
        raise ValueError(f"置き場に {fixboard.TDD_START_FILE} が無い（group-start が走らなかった。{place}）")
    if not started.get("go"):
        return {"prompt_file": "", "go": False}
    start = startrec.read(place)
    judgment_file = place / fixboard.JUDGMENT_FILE
    plan_file = place / fixboard.PLAN_REPLY_FILE
    notes = place / fixboard.NOTES_FILE
    values = {"judgment_file": str(judgment_file) if judgment_file.is_file() else "",
              "plan_file": str(plan_file) if plan_file.is_file() else "",
              "policy_path": policy.frozen_copy(start), "request_file": str(start.get("request_file") or ""),
              "notes_file": str(notes) if notes.is_file() else "", "base_rev": fixboard.base_rev_of(place)}
    sources = {"plan": fixboard.read_json(plan_file), "judgment": fixboard.read_json(judgment_file)}
    out = tddloop.prep(started["state_file"], values, repo, lang=fixboard.lang_line(start), sources=sources)
    return {"prompt_file": out["prompt_file"], "go": bool(out["go"])}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"tdd-prep: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
