# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 fix-ruled-prep（形 "" の裁定の後の修正の輪の頭）: 直す裁定（fix_test_scope・fix_code_as・replace_query。conflict.ruled_fix）が
無ければ go: false（役を起こさない。組どうしの合わせの申し出 conflict.JOIN_SOURCE への裁定は数えない——その組は戻していないので
直す義務に無く、裁定の後の合わせのループが直す）。在れば段の頭の木を 1 回目に置き場の fix-ruled-head.json に、除くパスの頭 boundary.SKIP の下の姿を
skip-before.json に控え（fixboard.record_skipped。受け付けがその下を変えた返答を拒む）、組の修正役が受け付けた返答を
1 つにまとめた控え（fixboard.group_fix_reply。fix-reply.json）と裁定の文のファイルを読む新しい会話の指示書を組む（fixrules.prep の
ruled。題の次に保存した返答を名指す行を足す。fixboard.ruled_reply_line。docs/plans/2026-10-12-blocks/fix.md の「Archon で書けない所」
の前の役の会話の続きの狭め）。直す義務は戻せた組の fixed でない単位（fixboard.ruled_owed）。凍ったテスト（factchecks.frozen_tests。輪の状態は受け付けと同じ
fixboard.ruled_states）を受け付けと同じ口で引いて指示書に貼る。
返り {prompt_file, go, iteration}。回す側の誤り（判定の写しが無い・控えが壊れた）は標準エラーに 1 行で非 0。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import conflict  # noqa: E402
import factchecks  # noqa: E402
import fixboard  # noqa: E402
import fixrules  # noqa: E402
import groups  # noqa: E402
import oneline  # noqa: E402
import rolekit  # noqa: E402
import rulebook  # noqa: E402
import startrec  # noqa: E402
import writelog  # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules"
rulebook.CANON = RULES / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = RULES
ACCEPT = "fix-ruled-accept"            # 受け付けの節（拒否の控え rejects-<名>.json の名）


def main() -> dict:
    place, repo = boundary.place("fix"), boundary.work_tree()
    prompt = place / (fixrules.PROMPT_NAME[:-len(".md")] + fixrules.RULED_TAIL)
    n = fixrules.iteration_next(prompt)
    if not [r for r in conflict.ruled_fix(place)   # 1 回目の段の裁定（2 回目の段が写した行）は直し直さない。組どうしの合わせの申し出は合わせ役が直す
            if not r.get(conflict.PRIOR) and r.get("source") != conflict.JOIN_SOURCE]:
        return {"prompt_file": "", "go": False, "iteration": n}
    head = place / fixrules.head_file("ruled")
    if not head.is_file():
        fixboard.record_skipped(place, repo, boundary.SKIP)   # 印より先に（落ちて回し直した prep が控えを飛ばさない）
        fixboard.write_json(head, {"tree": groups.end_tree(repo)})
    owed = fixboard.ruled_owed(place)
    start = startrec.read(place)
    saved = fixboard.group_fix_reply(place)
    values = fixboard.fix_values(place, owed, start=start, answer_node=fixrules.answer_node("ruled"))
    state, _ = fixboard.ruled_states(place)
    got = fixrules.prep(place, repo, values, "ruled",
                        owed=owed, items=factchecks.place_items(place), sources=fixboard.brief_sources(place),
                        reject_file=rolekit.reject_file(place, ACCEPT), lang=rolekit.lang_line(start),
                        frozen=factchecks.frozen_tests(place, state, "ruled"), shared=boundary.shared_cache())
    if Path(got["prompt_file"]) == prompt and saved is not None:
        fixboard.ruled_reply_line(prompt, str(saved))
    fixboard.consult_skip(place, boundary.SKIP, writelog.log_here())
    return {"prompt_file": got["prompt_file"], "go": True, "iteration": got["iteration"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"fix-ruled-prep: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
