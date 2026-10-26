"""修正の block の試験の助け: 輪を、組の子と同じ順の口で 1 歩進める。振り分けの段は place の route.json（振り分けの状態。src/route.step）、
振り分けが済んだら注文の node orders と同じ口（tdd.open_state に振り分けの結果と数えを渡し、tdd.assign で tdd の単位の並びを置く）で
輪の状態を作り、ほかの段は src/tdd.step。試験が持つ状態のパスは tdd.start が返した route.json のままで、振り分けが済んだ後は resolve が
輪の状態のパスに引き直す"""
import json
import pathlib

LOOPS: dict = {}   # route.json のパス → 振り分けの後に作った輪の状態のパス（試験ごとの一時の置き場なので重ならない）


def _mods():
    """今 sys.modules に在る修正の block の src の tdd・route（試験が kit.load した物と同じ物。差し替え mock.patch が効くように、
    ここで別に読み込まない）"""
    from src import route, tdd
    return tdd, route


def _doc(path) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def resolve(state) -> str:
    """試験が持つ状態のパス（tdd.start が返した route.json か輪の状態）→ 今の物のパス: 振り分けが済んで輪の状態を作った後は輪の状態"""
    if str(state) in LOOPS and _doc(state).get("phase") == "route":   # 同じ置き場に振り分けの状態を置き直した（2 度目の start）
        del LOOPS[str(state)]
    return LOOPS.get(str(state), str(state))


def is_route(state) -> bool:
    """今の物が振り分けの状態か（route.json で、段が route のまま）"""
    return pathlib.Path(state).name == _mods()[1].files.ROUTE_FILE and _doc(state).get("phase") == "route"


def open_loop(route_file, repo) -> str:
    """振り分けが済んだ route.json から、node orders と同じに輪の状態を作り（振り分けの行をそのまま使う tdd.assign）、そのパスを返す"""
    tdd, route = _mods()
    place = pathlib.Path(route_file).parent
    rt = _doc(route_file)
    loop = tdd.open_state(place, repo, rt["base_file"], list(rt["open_units"]), light=rt["light"], routed=rt,
                          counted=route.counted(place, rt))
    st = _doc(loop)
    tdd.assign(loop, repo, {k: u["route"] for k, u in st["units"].items()}, {k: u.get("why", "") for k, u in st["units"].items()})
    LOOPS[str(route_file)] = loop
    return loop


def loop_prep(state, **kw) -> dict:
    """state が振り分けの状態なら route.prep、ほかは tdd.prep（node route-prep と tdd-prep の材料）"""
    tdd, route = _mods()
    state = resolve(state)
    return (route.prep if is_route(state) else tdd.prep)(state, **kw)


def loop_step(state, reply, repo, **kw) -> dict:
    """state が振り分けの状態なら route.step で確かめ、振り分けが済んだら輪の状態を作る（輪の済み done と次の段 phase は輪の状態から
    返す）。ほかは tdd.step"""
    tdd, route = _mods()
    state = resolve(state)
    if not is_route(state):
        return tdd.step(state, reply, repo, **kw)
    out = route.step(state, reply, repo, **kw)
    if not out["done"]:
        return out
    st = _doc(open_loop(state, repo))
    return {**out, "done": st["done"], "phase": "done" if st["done"] else st["phase"]}
