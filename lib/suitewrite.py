"""入力 tdd_suite を省いた run で、修正前のテストの後に TDD の実行器を用意する: 取り置き（test_cmd ごと）から使うか、AI の手番 1 回が
書いた物を置き、その実行器を 1 回走らせた結末で機械が事実だけを照らす（持ち主の決め suite-by-ai。issue #516）。

実行器の約束は人が渡す tdd_suite と同じ: 対象の根を cwd に起こされ、第 1 引数の書き先に試験の 1 件ごとの結末を JUnit XML で書く。
道具の知識は書き手の役の判断の側に置き、ここは事実（本文の頭が #! か・JUnit XML が出たか・試験が 1 件以上か）だけを照らす。
照らしを通った実行器だけを始めの記録の tdd_suite に絶対パスで結ぶので、後ろの読み手（最後のテスト・修正の段の TDD のループ・
報告）は人が渡した実行器と同じ道で使う。通らなければ tdd_suite は空のままで、後ろは実行器の無い run の道を通る。

取り置き: 鍵は test_cmd の字（前後の空白を除く。空なら取り置かない）で、対象をまたいで使い回す。置き場 keep は呼び手が渡す
（対象のリポジトリの外。None は取り置かない）。使う時も毎回照らし、通らなければ取り置きを捨てて書き手に書き直させる。書いた物は
照らしが通った時だけ取り置く。

記録の欄 KEY {from, path, ok, why, dropped, stored}: from は FROM_KEEP（取り置きから）か FROM_AI（書き手の役が書いた）、path は照らす
実行器（run の置き場の中。無ければ ""）、ok は null が照らす前・true が通った・false が作れなかった、why は作れなかった訳、dropped は
照らしを通らず捨てた取り置きの訳（無ければ ""）、stored は書いた物を取り置いたか。人が渡した tdd_suite の run には欄を置かない。

- need(start, mode): 用意するか（形が base・記録の tdd_suite が空・欄 KEY がまだ無い。3 つ目は再開した run で書き直さないため）
- prepare(start_file, folder, keep, root): 1 周の頭。初めの周で取り置きが在れば folder/RUNNER に写して照らす印を置き {write: false}。
  無いか、前の周で取り置きが照らしを通らなかったなら、書き手の材料の文 folder/BRIEF を書き、記録に悲観の印（ok false・why NO_REPLY）
  を置いて {write: true, brief_file}。書き手の役が落ちて place が呼ばれなくても、報告が訳を言える
- place(start_file, folder, reply): 書き手の返り reply（{made, body, why} か None）の本文を folder/RUNNER に実行の印つきで書き、
  照らす印を置く。{made, why}
- pending(start_file): 照らす前の実行器のパス（無ければ ""）
- settle(start_file, ran, keep): 実行器を 1 回走らせた結末 ran（{exe, exit, problems, count} か None）を照らす。終了コードは見ない
  （修正前に赤の試験が在るのは普通）。通れば tdd_suite に結び、書いた物なら取り置く。取り置きが通らなければ捨てる。
  {done, ok, why}（done が偽なら書き直す周が要る）
- adopt(start_file): 照らす前の実行器を走らせずに tdd_suite に結ぶ（印 ok true・checked false）。直す前の版では試験を何も走らせない
  （持ち主の決め base-runs-nothing）ので、照らすのは修正の段の TDD の輪が最初に走らせた所。照らす前の実行器が無ければ印のまま
  {done: true, ok: <結んだか>, why}
- keep_runner(keep, test_cmd, runner): 走らせて結末が取れた実行器を test_cmd の字で取り置く（TDD の輪の頭が呼ぶ。取り置けたか）
- drop_runner(keep, test_cmd, runner): 壊れていた実行器と同じバイトの取り置きを捨てる（TDD の輪の頭が書き直させる前に呼ぶ）
- head_note(start): 報告の冒頭の句。取り置きを使った・書いた・作れなかったのどれか（欄の無い run は空の字）
- GATE_NOTE: 起動の承認ノードの文の 1 行
"""
import hashlib
import os
import pathlib
import sys
import tempfile

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import declared_checks  # noqa: E402
import oneline  # noqa: E402
import jsonfile  # noqa: E402

KEY = "suite_written"
FROM_KEEP, FROM_AI = "keep", "ai"
RUNNER = "runner"
BRIEF = "writer-brief.md"
USED = "TDD の実行器は取り置きを使った"
WROTE = "TDD の実行器は AI が書いた"
NOT_MADE = "TDD の実行器を作れなかった"
NO_REPLY = "実行器を書く役が返答を返さなかった（役が落ちた）"
NOT_CHECKED = "実行器を照らす前に止まった"
NO_CASES = "JUnit XML に試験が 1 件も無い"
NOT_RUN = "実行器が走らなかった"
NO_SHEBANG = "実行器の本文の頭に #! の行が無い"
NO_WHY = "実行器を書く役が作らなかった（訳を書いていない）"
UNCHECKED = "直す前には走らせていない——修正の段の TDD の輪が最初に走らせて確かめ、壊れていれば書き直させる"
GATE_NOTE = ("TDD の実行器: 入力 tdd_suite が無い——判定の前に、同じ test_cmd で前に照らしを通った取り置きを使い、無ければ "
             "AI の手番 1 回が test_cmd と CI の定義から書く（直す前には走らせない）。修正の段の TDD のループが最初に走らせて確かめ、"
             "起動スクリプト越しにだけ落ちれば書き直させ、直らなければ止めて人に聞く")


def need(start: dict, mode: str) -> bool:
    return mode == "base" and not _suite(start) and KEY not in start


def prepare(start_file, folder, keep, root) -> dict:
    start = jsonfile.read_dict(start_file)
    mark = _mark(start)
    folder = pathlib.Path(folder)
    if _suite(start):
        return {"write": False, "brief_file": ""}
    if not mark:
        kept = _kept(keep, start)
        if kept is not None and kept.is_file():
            runner = _put(folder / RUNNER, kept.read_bytes())
            _save(start_file, start, {"from": FROM_KEEP, "path": runner, "ok": None, "why": "", "dropped": "", "stored": False})
            return {"write": False, "brief_file": ""}
        dropped = ""
    elif mark.get("from") == FROM_KEEP and mark.get("ok") is False:
        dropped = str(mark.get("why") or "")
    else:
        return {"write": False, "brief_file": ""}
    folder.mkdir(parents=True, exist_ok=True)
    brief = folder / BRIEF
    brief.write_text(_brief(str(start.get("test_cmd") or ""), pathlib.Path(root)), encoding="utf-8")
    _save(start_file, start, {"from": FROM_AI, "path": "", "ok": False, "why": NO_REPLY, "dropped": dropped, "stored": False})
    return {"write": True, "brief_file": str(brief.resolve())}


def _brief(test_cmd: str, root: pathlib.Path) -> str:
    fence = "`" * max(3, _longest_tick_run(test_cmd) + 1)
    cmd = f"{fence}text\n{test_cmd}\n{fence}" if test_cmd.strip() else "無い（人が渡していない）"
    decl = "在る" if (root / declared_checks.DECL_NAME).is_file() else "無い"
    return "\n".join(["# 実行器を書く材料", "", f"- 対象の根: {root.resolve()}", f"- 対象の根の宣言 {declared_checks.DECL_NAME}: {decl}",
                      "", "## test_cmd（人が渡したテストのコマンド。字のまま）", "", cmd, ""])


def _longest_tick_run(text: str) -> int:
    longest = run = 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        longest = max(longest, run)
    return longest


def place(start_file, folder, reply) -> dict:
    start = jsonfile.read_dict(start_file)
    mark = _mark(start)
    reply = reply if isinstance(reply, dict) else {}
    body = reply.get("body") if isinstance(reply.get("body"), str) else ""
    if not reply:
        why = NO_REPLY
    elif reply.get("made") is not True:
        why = oneline.one_line(reply.get("why") or "") or NO_WHY
    elif not body.startswith("#!"):
        why = NO_SHEBANG
    else:
        runner = _put(pathlib.Path(folder) / RUNNER, (body if body.endswith("\n") else body + "\n").encode("utf-8"))
        _save(start_file, start, {**mark, "from": FROM_AI, "path": runner, "ok": None, "why": ""})
        return {"made": True, "why": ""}
    _save(start_file, start, {**mark, "from": FROM_AI, "path": "", "ok": False, "why": why})
    return {"made": False, "why": why}


def pending(start_file) -> str:
    mark = _mark(jsonfile.read_dict(start_file))
    return str(mark.get("path") or "") if mark.get("ok", False) is None else ""


def settle(start_file, ran, keep) -> dict:
    start = jsonfile.read_dict(start_file)
    mark = _mark(start)
    if mark.get("ok", False) is not None or not mark.get("path"):
        return {"done": True, "ok": mark.get("ok") is True, "why": str(mark.get("why") or "")}
    why = _fault(ran)
    if not why:
        stored = mark.get("from") == FROM_AI and _store(keep, start, mark["path"])
        _save(start_file, {**start, "tdd_suite": mark["path"]}, {**mark, "ok": True, "why": "", "stored": stored})
        return {"done": True, "ok": True, "why": ""}
    if mark.get("from") == FROM_KEEP:
        _drop(keep, start, mark["path"])
    _save(start_file, start, {**mark, "ok": False, "why": why})
    return {"done": mark.get("from") != FROM_KEEP, "ok": False, "why": why}


def adopt(start_file) -> dict:
    start = jsonfile.read_dict(start_file)
    mark = _mark(start)
    if mark.get("ok", False) is not None or not mark.get("path"):
        return {"done": True, "ok": mark.get("ok") is True, "why": str(mark.get("why") or "")}
    _save(start_file, {**start, "tdd_suite": mark["path"]}, {**mark, "ok": True, "checked": False, "why": "", "stored": False})
    return {"done": True, "ok": True, "why": ""}


def keep_runner(keep, test_cmd: str, runner) -> bool:
    return _store(keep, {"test_cmd": test_cmd}, str(runner))


def drop_runner(keep, test_cmd: str, runner) -> None:
    _drop(keep, {"test_cmd": test_cmd}, str(runner))


def _fault(ran) -> str:
    if not isinstance(ran, dict):
        return NOT_RUN
    if ran.get("problems"):
        return "；".join(str(p) for p in ran["problems"])
    count = ran.get("count")
    if count is None:
        return NOT_RUN
    return NO_CASES if count == 0 else ""


def _kept(keep, start: dict) -> pathlib.Path | None:
    key = str(start.get("test_cmd") or "").strip()
    if keep is None or not key:
        return None
    return pathlib.Path(keep) / hashlib.sha256(key.encode("utf-8")).hexdigest()


def _store(keep, start: dict, runner: str) -> bool:
    kept = _kept(keep, start)
    if kept is None:
        return False
    try:
        _put(kept, pathlib.Path(runner).read_bytes())
    except OSError:
        return False
    return True


def _drop(keep, start: dict, runner: str) -> None:
    """捨てるのは照らした物と同じバイトの取り置きだけ（並んだ run が置き換えた新しい取り置きは残す）"""
    kept = _kept(keep, start)
    try:
        if kept is not None and kept.is_file() and kept.read_bytes() == pathlib.Path(runner).read_bytes():
            kept.unlink()
    except OSError:
        pass


def _put(path: pathlib.Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    tmp = pathlib.Path(name)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        tmp.chmod(0o755)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return str(path.resolve())


def _suite(start: dict) -> str:
    return str(start.get("tdd_suite") or "").strip()


def _mark(start) -> dict:
    mark = start.get(KEY) if isinstance(start, dict) else None
    return mark if isinstance(mark, dict) else {}


def _save(start_file, start: dict, mark: dict) -> None:
    jsonfile.write(start_file, {**start, KEY: mark}, indent=2, parents=True)


def head_note(start) -> str:
    mark = _mark(start)
    if not mark:
        return ""
    dropped = f"（取り置きは照らしを通らず捨てた: {mark['dropped']}）" if mark.get("dropped") else ""
    if mark.get("ok") is True and mark.get("checked") is False:
        made = USED if mark.get("from") == FROM_KEEP else WROTE
        return f"{made}（{UNCHECKED}）{dropped}"
    if mark.get("ok") is True:
        if mark.get("from") == FROM_KEEP:
            return f"{USED}（同じ test_cmd で前の run が照らしを通した物。書く AI の手番は起こしていない）"
        return f"{WROTE}{'・照らしが通ったので取り置いた' if mark.get('stored') else ''}{dropped}"
    why = (mark.get("why") or NO_REPLY) if mark.get("ok") is False else NOT_CHECKED
    return (f"{NOT_MADE}（{why}）{dropped}——TDD のループは回さない。JUnit XML を第 1 引数に書く実行器を入力 tdd_suite に渡せば回す")
