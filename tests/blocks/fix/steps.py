"""修正の block の試験の助け: 輪の状態を、組の子と同じ順の口で 1 歩進める（振り分けの段は src/route.step、振り分けの後は
注文の node と同じく tdd.assign で tdd の単位の並びを置く。ほかの段は src/tdd.step）"""
import json
import pathlib



def _mods():
    """今 sys.modules に在る修正の block の src の tdd・route（試験が kit.load した物と同じ物。差し替え mock.patch が効くように、
    ここで別に読み込まない）"""
    from src import route, tdd
    return tdd, route


def loop_prep(state, **kw) -> dict:
    """state の段が route なら route.prep、ほかの段は tdd.prep（node route-prep と tdd-prep の材料）"""
    tdd, route = _mods()
    st = json.loads(pathlib.Path(state).read_text(encoding="utf-8"))
    return (route.prep if st.get("phase") == "route" else tdd.prep)(state, **kw)


def loop_step(state, reply, repo, **kw) -> dict:
    """state の段が route なら route.step で確かめ、振り分けが済んだら振り分けの行の route で tdd.assign する（輪の済み done と
    次の段 phase は輪の状態から返す）。ほかの段は tdd.step"""
    tdd, route = _mods()
    st = json.loads(pathlib.Path(state).read_text(encoding="utf-8"))
    if st.get("phase") != "route":
        return tdd.step(state, reply, repo, **kw)
    out = route.step(state, reply, repo, **kw)
    if not out["done"]:
        return out
    st = json.loads(pathlib.Path(state).read_text(encoding="utf-8"))
    tdd.assign(state, repo, {k: u["route"] for k, u in st["units"].items()},
               {k: u.get("why", "") for k, u in st["units"].items()})
    st = json.loads(pathlib.Path(state).read_text(encoding="utf-8"))
    return {**out, "done": st["done"], "phase": "done" if st["done"] else st["phase"]}
