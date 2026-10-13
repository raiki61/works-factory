# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 fix-prep（形 group の修正の輪の頭）: 修正役の指示書を組んで置き場に書く（fixrules.prep。決まりは commands/fix-rules/）。

直す義務は組の単位（入力 group の unit_ids）のうち判定の直す義務の物（fixboard.group_owed）。義務が残らない（全部が答え待ち・
直さない裁定で外れた）時は go: false（修正役を起こさない）。前の回の拒否の理由のファイル（fix-accept が書いた
reject-fix-accept-<k>.md）を指示書の頭で名指す。段の頭の木（TDD の輪の後の姿）を 1 回目に置き場の fix-head.json に控える
（受け付けの書き込みの出どころと、諦めた単位の戻し先。TDD の輪が書いた物を修正役の物に数えない）。範囲の相談の答えがまだ渡っていない周は、答えのファイルを名指す続きの指示書だけを
書く（fixrules.prep の中の consult の引き）。TDD の輪が緑にした単位（tddloop.green_units）の外の単位には、修正役が項目ごとに
Agent の新しい会話で下請け（実装役・審査役）を起こす節と下請けのファイルを置く（fixrules.g1_values・seat.g1_section）。輪が全部を
緑にした周は借りたスキルの座（seat.section）。相談の控え（consult.json）には除くパスの頭 boundary.SKIP を足す。段の頭の木と
同じ時に、除くパスの頭 boundary.SKIP の下の姿を skip-before.json に控える（fixboard.record_skipped。受け付けがその下を変えた返答を拒む）。
返り {prompt_file, go, iteration}。回す側の誤り（判定の写しが無い・brief の控えが壊れた）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import factchecks  # noqa: E402
import fixboard  # noqa: E402
import fixrules  # noqa: E402
import groups  # noqa: E402
import oneline  # noqa: E402
import rolekit  # noqa: E402
import rulebook  # noqa: E402
import startrec  # noqa: E402
import tddloop  # noqa: E402
import writelog  # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules"
rulebook.CANON = RULES / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = RULES
ACCEPT = "fix-accept"            # 受け付けの節（拒否の理由のファイルの名）
ANSWER_NODE = "consult-answer"   # 範囲の相談に答える役の節


def main() -> dict:
    place, repo = boundary.place("fix"), boundary.work_tree()
    group = boundary.parsed(os.environ.get("INPUTS_GROUP"))
    owed = fixboard.group_owed(place, group["unit_ids"] if group else None)
    if not (place / fixboard.FIX_HEAD_FILE).is_file():
        fixboard.record_skipped(place, repo, boundary.SKIP)   # 印より先に（落ちて回し直した prep が控えを飛ばさない）
        fixboard.write_json(place / fixboard.FIX_HEAD_FILE, {"tree": groups.end_tree(repo)})
    start = startrec.read(place)
    n = fixrules.iteration_next(fixrules.prompt_path(place))
    duty, _ = fixboard.fix_duty(place, owed)
    if not duty:
        return {"prompt_file": "", "go": False, "iteration": n}
    state, summary = fixboard.loop_files(place)
    reject = place / fixboard.REJECT_NAME.format(name=ACCEPT, k=n - 1)
    got = fixrules.prep(place, repo, fixboard.fix_values(place, owed, start=start, state=state, summary=summary,
                                                         answer_node=ANSWER_NODE),
                        "first", owed=owed, items=factchecks.place_items(place), sources=fixboard.brief_sources(place),
                        reject_file=str(reject) if n > 1 and reject.is_file() else "", lang=rolekit.lang_line(start),
                        green=tddloop.green_units(summary), shared=boundary.shared_cache())
    fixboard.consult_skip(place, boundary.SKIP, writelog.log_here())
    return {"prompt_file": got["prompt_file"], "go": True, "iteration": got["iteration"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"fix-prep: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
