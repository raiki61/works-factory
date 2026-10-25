# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node group-start（組の形の頭）: 親の姿の木を自分の作業ツリーに写し（from_tree）、入力を自分の place に写し（out_dir の在る子は
親の place の写しと values.json を board.adopt_inputs で、単独の run は board.prep で）、git が無視するファイルの控えと始めの木を取り、
元の結末を取って base.json に書く（src/basecase.take。輪の状態は振り分けの route-go か注文の orders が置く）。
- 親の作業ツリーで 1 つずつ回る子（out_dir が在り from_tree が空）は、前の組の子が使える結果を残さずに落ちていれば、何も書かずに
  1 で止まる（#576）。自分の組の分は始めの木に戻してから始める（board.drop_unreturned）
- 軽量の単位（port skip_rerun）は緑の後に test_cmd を走らせない（輪の状態を置く tdd.open_state の light。route-go・orders が渡す）
- 走らせ方が決まらない対象（test_cmd が空で、対象の根に走らせる段の宣言が無い。related.applies）は、輪の頭の元の結末を関わる試験だけにする
  （basecase.take の narrow。持ち主の決め related-tests-only）
- 実行器が工場の書いた物（values の suite_made）なら、元の結末の回で起動スクリプトの壊れを確かめる（basecase.take の suite_made。
  docs/design/fix.md の 19 節）。壊れていれば取り置きから捨て（suitewrite.drop_runner）、返りの suite_broken を真にして、後ろの
  suite-fix-prep・suite-fix・suite-fix-try が書き直させる。壊れていなければ、走らせて結末が取れた実行器を test_cmd の字で取り置く
  （suitewrite.keep_runner。直す前には走らせないので、取り置くのはここ）
- 実行器が無い・走らない組で、計画の語が static でない単位が在れば、返りの no_suite を真にして組を止める（orders.no_suite_why。
  下書き docs/plans/2026-10-24-fix-weapons.md の 3.9。route-go と orders が tdd-start.json の no_suite を読む。static だけの組は止めない）
返り {tdd（元の結末が取れた）, units, reason, suite_broken, no_suite}。入力が読めない・前の組が止まっている・git が効かない・輪の頭が壊れた: 標準エラーに 1 行で 1"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import groups  # noqa: E402
import leftovers  # noqa: E402
import oneline  # noqa: E402
import writelog  # noqa: E402

from src import basecase, board, intake, orders, runvals, suitefix  # noqa: E402

NO_UNITS = "組に単位が無い——TDD のループを回さない"
HALTED = "前の組 {groups} の子の run が結果を書かずに止まっている——親を resume すればその子が続きから回る"


def main() -> dict:
    place = ports.place()
    doc = intake.load(place)
    group = doc["group"]
    from_tree, out_dir = doc["from_tree"], doc["out_dir"]
    in_order = bool(out_dir) and not from_tree
    if in_order:
        halted = board.halted_groups(out_dir, group["group_id"])
        if halted:
            raise RuntimeError(HALTED.format(groups="・".join(halted)))
    repo = Path.cwd()
    writelog.open_here()
    if from_tree:
        groups.adopt_tree(repo, from_tree)
    if out_dir:
        board.adopt_inputs(Path(out_dir).parent, place, repo)
        if in_order:
            board.drop_unreturned(repo, Path(out_dir) / group["group_id"], (ports.RUNTIME_COPY_PREFIX,))
    else:
        board.prep(place, repo, doc)
    leftovers.record_ignored(place, repo)
    start_tree = groups.end_tree(repo)
    board.write_json(place / board.GROUPS_FILE,
                     {"groups": [group], "count": 1, "par": False, "start_tree": start_tree,
                      "out_dir": out_dir or str(place / "groups")})
    board.write_json(board.group_dir(place, out_dir, group["group_id"]) / board.GROUP_START_FILE,
                     {"group": group, "from_tree": from_tree, "out_dir": out_dir, "start_tree": start_tree})
    values = runvals.read(place)
    keys = [str(k) for k in group["unit_ids"]]
    suite = str(values["tdd_suite"] or "")
    if not keys:
        out = {"go": False, "reason": NO_UNITS, "suite": suite, "state_file": "", "summary_file": ""}
    else:
        reuse = suitefix.reuse_of(values)
        ports.drop_runner_env(values["user_env_dir"])   # 対象のテストに Archon の変数を継がせない（place・repo・reuse は先に取った）
        out = suitefix.begin(place, repo, values, keys, reuse)
        suitefix.settle_kept(values, repo, out)
    board.write_json(place / board.TDD_START_FILE, out)
    why = orders.no_suite_why(place) if keys else ""
    if why:   # 実行器が無い・走らない組で、static でない単位が在る（下書き 3.9 の止め方の 1。route-go と orders が読んで止める）
        out = {**out, "no_suite": True, "reason": why}
        board.write_json(place / board.TDD_START_FILE, out)
    taken = bool((basecase.read(place) or {}).get("taken"))   # 元の結末が取れた（振り分けと TDD の輪を回せる）
    return {"tdd": taken, "units": len(keys), "reason": str(out.get("reason") or ""),
            "suite_broken": out.get("suite_broken") is True, "no_suite": out.get("no_suite") is True}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（入力が読めない・前の組が止まっている・置き場が無い・git が効かない・輪の頭が壊れた）
        print(f"group-start: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
