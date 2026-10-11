"""節 fix-prep（形 group の修正の輪の頭）: 修正役の指示書を組んで置き場に書く（fixrules.prep。決まりは commands/fix-rules/）。

直す義務は組の単位（入力 group の unit_ids）のうち判定の直す義務の物（fixboard.group_owed）。義務が残らない（全部が答え待ち・
直さない裁定で外れた）時は go: false（修正役を起こさない）。前の回の拒否の理由のファイル（fix-accept が書いた
reject-fix-accept-<k>.md）を指示書の頭で名指す。段の頭の木（TDD の輪の後の姿）を 1 回目に置き場の fix-head.json に控える
（受け付けの書き込みの出どころと、諦めた単位の戻し先。TDD の輪が書いた物を修正役の物に数えない）。範囲の相談の答えがまだ渡っていない周は、答えのファイルを名指す続きの指示書だけを
書く（fixrules.prep の中の consult の引き）。相談の控え（consult.json）には除くパスの頭 fixio.SKIP を足す。
返り {prompt_file, go, iteration}。回す側の誤り（判定の写しが無い・brief の控えが壊れた）は標準エラーに 1 行で非 0。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402

import factchecks  # noqa: E402
import fixboard  # noqa: E402
import fixrules  # noqa: E402
import groups  # noqa: E402
import rulebook  # noqa: E402
import startrec  # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules"
rulebook.CANON = RULES / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = RULES
ACCEPT = "fix-accept"            # 受け付けの節（拒否の理由のファイルの名）
ANSWER_NODE = "consult-answer"   # 範囲の相談に答える役の節


def main() -> dict:
    place, repo = fixio.place(), fixio.repo()
    raw = os.environ.get("INPUTS_GROUP", "").strip()
    group = json.loads(raw) if raw else None
    owed = fixboard.group_owed(place, group["unit_ids"] if group else None)
    if not (place / fixboard.FIX_HEAD_FILE).is_file():
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
                        reject_file=str(reject) if n > 1 and reject.is_file() else "", lang=fixboard.lang_line(start))
    fixboard.consult_skip(place, fixio.SKIP)
    return {"prompt_file": got["prompt_file"], "go": True, "iteration": got["iteration"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"fix-prep: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
