# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node route-go（組の形。組の頭の後・振り分けの loop の前）: 振り分けの段の AI を起こすか（src/route）。入力 routes が
auto で、元の結末が取れていて（base.json の taken）、振る単位（計画の語 static・tidy・pin の単位と消す名の在る単位を除いた物）が
在る時だけ、振り分けの状態を段 route で place の route.json に置く（輪の状態は置かない。orders が振り分けの後に作る）。起動スクリプトが
壊れたままの組と、組の頭が実行器の無い・走らない組として止めた組（no_suite）は止める。
返り {route, stop}。振り分けの状態を置けない時は標準エラーに 1 行で 1（黙って振り分けを飛ばし、tdd の単位を variant に回さない）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    from src import basecase, board, intake, route, runvals
    place, repo = ports.place(), Path.cwd()
    started = board.read_json(place / board.TDD_START_FILE) or {}
    if started.get("suite_broken") is True or started.get("no_suite") is True:
        return {"route": False, "stop": True}
    values = runvals.read(place)
    base = basecase.read(place)
    keys = [str(k) for k in (intake.load(place).get("group") or {}).get("unit_ids") or []]
    placed = route.read(place)
    if str(values.get("routes") or "auto") != "auto" or not (base and base.get("taken")) or started.get("state_file") or placed:
        return {"route": placed.get("phase") == "route" and not started.get("state_file"), "stop": False}
    to_route = route.route_keys(keys, route.plan_words(place, keys), route.plan_removes(place, keys))
    if not to_route:
        return {"route": False, "stop": False}
    light = [k for k in values.get("skip_rerun") or [] if k in keys]
    route.open_route(place, repo, str(basecase.path(place)), keys, to_route=to_route, owed=set(keys), light=light)
    return {"route": True, "stop": False}


if __name__ == "__main__":
    try:
        result = compute()
    except Exception as e:   # 輪の状態を置けない（元の結末の控えが読めない・欄の控えが食い違う）: 黙って振り分けを飛ばさない
        import oneline
        print(f"route-go: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
