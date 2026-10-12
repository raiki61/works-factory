# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""fix のブロックの script が共に読む、Archon との出入りの助け（置き場の場所・作業ツリー・控えのファイル・入力の写し）。

lib/ は Archon の名を持たない（lib/AGENTS.md の E3）ので、Archon に届く事（ARTIFACTS_DIR・ARCHON_NODE_EXECUTION・
CLAUDE_CONFIG_DIR・入力の指し札）はここと script の側と境（boundary）だけが持ち、lib/ へは値を引数で渡す。節の script ではない
（工程の YAML は名指さない）。読む script は境の置き場を sys.path に足してから import する。lib/ は使う関数の中で読む（頭で
読むと、lib/ を足さない route なども lib/ に頼る）ので、その関数を呼ぶ script は lib/ も足す。
"""
import json
import os
import pathlib
import subprocess

import boundary

# 後始末・変更の確かめ・書き込みの出どころの照らしで数えない・消さないパスの頭（境の工程の写しの置き場）
SKIP = (boundary.RUNTIME_COPY_PREFIX,)
BLOCK_NAME = "fix"
MODES = {"": False, "group": True}   # 入力 mode の語 → 組の子の run か（route が振り分け、collect が返りの形を選ぶ）


def include_name() -> str:
    """この節を差し込んだ include の名（節の実行の path の最初の __ より前）。fix と、案の直しの後の 2 回目の refix とで置き場を
    分ける。include の外（組の子の run・単独の run）は fix"""
    try:
        path = json.loads(os.environ.get("ARCHON_NODE_EXECUTION") or "{}").get("path") or ""
    except ValueError:
        path = ""
    head, sep, _ = path.partition("__")
    return head if sep and head else BLOCK_NAME


def place() -> pathlib.Path:
    """この run の置き場（run の成果物の置き場の下 fix/<include の名>/）。無ければ作る"""
    folder = pathlib.Path(os.environ["ARTIFACTS_DIR"]) / BLOCK_NAME / include_name()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _writes_root() -> pathlib.Path | None:
    import writelog
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    root = writelog.root(config) if config else None
    return root if root is not None and root.is_dir() else None


def writes_log(cwd=None) -> pathlib.Path | None:
    """書き込みの記録のフック（bin/_lib/record-write.py）が作業の場 cwd（既定はこの節の cwd。役の節と同じ run の作業ツリー）の
    Edit・Write を残すファイル（lib/writelog.log_path）。記録の根（起動が隔離した設定 CLAUDE_CONFIG_DIR の下に作る）が無い起動は
    None で、受け付けは記録の無い run の道（writes.NO_RECORD）を通る"""
    import writelog
    root = _writes_root()
    return None if root is None else writelog.log_path(root, os.getcwd() if cwd is None else cwd)


def start_writes_log() -> None:
    """記録の根が在れば、この節の作業の場の記録を空で作る（在れば触らない。前の役の記録を残す）。置き場はフックと同じ
    writelog.open_log で作る（作業の場の控えつき）"""
    import writelog
    root = _writes_root()
    if root is not None:
        writelog.open_log(root, os.getcwd()).touch()


def repo() -> pathlib.Path:
    """作業ツリーの根（script は run の作業ツリーで起きる）"""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return pathlib.Path(top.stdout.strip())


def line_top(out_dir: str) -> pathlib.Path | None:
    """同じ run の中の試験の結果の控えを置く run の置き場（線の run の成果物の置き場）。組の子の run は入力 out_dir（親の置き場の
    <run の置き場>/fix/<include の名>/groups）から 3 つ上、単独の run（out_dir が空）は自分の ARTIFACTS_DIR。形が違えば None（使い回さない）"""
    if not out_dir:
        return pathlib.Path(os.environ["ARTIFACTS_DIR"])
    path = pathlib.Path(out_dir)
    if path.name != "groups" or len(path.parents) < 3 or path.parents[1].name != BLOCK_NAME:
        return None
    return path.parents[2]


_START_DEFAULTS = {"tdd_suite": "", "test_cmd": "", "policy_md": "", "request_file": "", "features_cut": []}


def _value(raw: str, name: str):
    """入力の字を JSON で読む（空・null は None）"""
    if not (raw or "").strip() or raw.strip() == "null":
        return None
    try:
        return json.loads(raw)
    except ValueError as e:
        raise ValueError(f"入力 {name} が JSON として読めない: {e}（頭: {raw[:120]!r}）") from None


def _pointed(raw: str, name: str):
    """入力の指し札の先のパス（空・null は None）"""
    ptr = _value(raw, name)
    return None if ptr is None else boundary.resolve(ptr)


def _read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def prep() -> dict:
    """入力を置き場に写し、始めの記録・git が無視するファイルの控え・始めの木を取り、組を作って返す（置く物と返りの形は節 prep の
    docstring）。節 prep と、単独の run の組の子の頭（節 group-start。指し札は自分の run の物）が同じ写しを置くのに呼ぶ"""
    import baseline_red
    import fixboard
    import groups
    import leftovers
    import planmarks
    import startrec
    folder, worktree = place(), repo()
    start_writes_log()
    start = _read_json(_pointed(os.environ["INPUTS_START"], "start"))
    if not isinstance(start, dict):
        raise ValueError("始めの記録が JSON のオブジェクトでない")
    start = {**_START_DEFAULTS, **{k: v for k, v in start.items() if v is not None}}
    fixboard.write_json(startrec.path(folder), start)
    judgment = _read_json(_pointed(os.environ["INPUTS_JUDGMENT"], "judgment"))
    fixboard.write_json(folder / fixboard.JUDGMENT_FILE, judgment)

    plan_file = _pointed(os.environ.get("INPUTS_PLAN", ""), "plan")
    plan = None
    if plan_file is not None:
        doc = _read_json(plan_file)
        if not isinstance(doc, dict) or not isinstance(doc.get("fields"), list):
            raise ValueError(f"修正案の欄 {plan_file.name} の形が違う（{{round, fields}}）")
        amended = doc.get(planmarks.AMENDED_KEY)
        planmarks.save(folder, 1, doc["fields"], {int(n): c for n, c in amended.items()} if isinstance(amended, dict) else None)
        reply = plan_file.parent / fixboard.PLAN_REPLY_FILE
        if reply.is_file():
            plan = _read_json(reply)
            fixboard.write_json(folder / fixboard.PLAN_REPLY_FILE, plan)
    for name, file in (("ripple", fixboard.RIPPLE_FILE), ("world", fixboard.WORLD_FILE)):
        src = _pointed(os.environ.get(f"INPUTS_{name.upper()}", ""), name)
        if src is not None:
            fixboard.write_json(folder / file, _read_json(src))
    for name, file in (("depth", fixboard.DEPTH_FILE), ("answers", fixboard.ANSWERS_FILE), ("units", fixboard.UNITS_FILE)):
        got = _value(os.environ.get(f"INPUTS_{name.upper()}", ""), name)
        if got not in (None, "", [], {}) or name == "units":
            fixboard.write_json(folder / file, got if got is not None else [])
    only = _value(os.environ.get("INPUTS_ONLY_ITEMS", ""), "only_items") or []
    if not isinstance(only, list):
        raise ValueError("入力 only_items が配列でない")
    fixboard.write_json(folder / fixboard.ONLY_ITEMS_FILE, only)
    base = _pointed(os.environ.get("INPUTS_BASELINE", ""), "baseline")
    if base is not None:
        got = baseline_red.read_baseline(base)
        fixboard.write_json(folder / fixboard.BASELINE_FILE, {"cases": got["cases"], "exit": got["exit"]})

    leftovers.record_ignored(folder, worktree)
    fixboard.record_base_rev(folder, worktree)
    start_tree = groups.end_tree(worktree)
    items = planmarks.approved_items(fixboard.plan_view(folder, plan, judgment)) if plan is not None else None
    fixboard.write_notes(folder)
    grps = fixboard.fix_groups(fixboard.group_owed(folder), items, only)
    out_dir = folder / "groups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = {"groups": grps, "count": len(grps), "par": fixboard.parallel(grps, start.get("features_cut"), worktree),
           "start_tree": start_tree, "out_dir": str(out_dir)}
    fixboard.write_json(folder / fixboard.GROUPS_FILE, out)
    return out
