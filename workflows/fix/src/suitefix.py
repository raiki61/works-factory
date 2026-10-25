"""起動スクリプトの書き直し（docs/design/fix.md の 19 節。持ち主の決め base-runs-nothing・#836）。

工場の書いた実行器（values の suite_made）が、TDD の輪の頭の元の結末の回で関わる試験を中身に届く前に落とし（結末が無いか JUnit の
error）、test_cmd の単体は通る時（tdd.start の _suite_broken）、起動スクリプトを書く役に 1 回だけ書き直させ、同じ輪の頭をやり直す。
直らなければ組を止める（finish が stopby.SUITE_BROKEN を名乗る。輪を回さずに置いたまま、確かめていない直しを書き進めない）。

- reuse_of(values)・begin(place, repo, values, keys, reuse) -> 組の頭の返り（src/basecase.take）: 元の結末（group-start と書き直しの後のやり直しが同じ引数で呼ぶ）
- prompt_values(place, repo, values, started) -> (values, when): 書き直す役の指示（prompts/suite-fix.md）に渡す値
- retry(place, repo, values, keys, reply) -> {tdd, stop, reason}: 書き手の返り reply の本文で実行器を置き換え、輪の頭をやり直す
"""
from __future__ import annotations

import os
import pathlib

import ports

import baseline_red      # lib/
import declared_checks   # lib/
import oneline           # lib/
import suitewrite        # lib/
import tree_run          # lib/

from src import board, tdd

LOG_TAIL = 4000   # 書き手に貼る壊れた回のログの末尾のバイト数（全体はログのファイルを名指す）
NOT_MADE = "起動スクリプトを書き直せなかった（{why}）"
STILL_BROKEN = "書き直した起動スクリプトも壊れている"


def reuse_of(values: dict):
    """同じ run の控えの置き場（tree_run.reuse_place）。Archon の変数を落とす前に取る（ports.drop_runner_env の前）"""
    return tree_run.reuse_place(values["reuse_dir"], str(values["reuse_key"] or ""), rerun=bool(os.environ.get(tree_run.RERUN_ENV)))


def begin(place, repo, values: dict, keys: list, reuse) -> dict:
    """組の頭（src/basecase.take。元の結末を取って base.json を書く）。関わる試験だけ（related.applies）・工場の書いた実行器か
    （suite_made）は values から、計画の語は route.plan_words、起点の版は base_rev_of。reuse は reuse_of の返り"""
    from src import basecase, route
    return basecase.take(place, repo, values, keys, reuse, words=route.plan_words(place, keys), rev=board.base_rev_of(place))


def settle_kept(values: dict, repo, out: dict) -> None:
    """工場の書いた実行器の取り置き: 輪の頭で結末が取れたら test_cmd の字で取り置き、壊れていたら同じバイトの取り置きを捨てる
    （人が渡した実行器は触らない。直す前には走らせないので、取り置くのはここ）"""
    if values["suite_made"] is not True or not out.get("suite"):
        return
    exe = tdd.exe_path(repo, out["suite"])
    if out.get("suite_broken") is True:
        suitewrite.drop_runner(ports.suite_keep(), str(values["test_cmd"] or ""), exe)
    elif out.get("base_file"):
        suitewrite.keep_runner(ports.suite_keep(), str(values["test_cmd"] or ""), exe)


def _tail(path) -> str:
    try:
        data = pathlib.Path(path).read_bytes()
    except OSError as e:
        return f"（ログを読めない: {type(e).__name__}）"
    return data[-LOG_TAIL:].decode("utf-8", "replace")


def prompt_values(place, repo, values: dict, started: dict) -> tuple[dict, dict]:
    """書き直す役の指示に渡す値と段落の選び"""
    import prompt
    root = pathlib.Path(repo).resolve()
    test_cmd = str(values["test_cmd"] or "")
    exe = tdd.exe_path(repo, str(started.get("suite") or values["tdd_suite"] or ""))
    try:
        old = exe.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        old = f"（読めない: {type(e).__name__}）"
    log_tail = _tail(started.get("runner_log") or "")
    vals = {"root": str(root), "decl_name": declared_checks.DECL_NAME, "test_cmd": test_cmd, "fence": suitewrite.fence(test_cmd),
            "cmd_log": str(started.get("cmd_log") or ""), "old_body": old.rstrip("\n"), "body_fence": suitewrite.fence(old),
            "runner_log": str(started.get("runner_log") or ""), "log_tail": log_tail.rstrip("\n"), "log_fence": suitewrite.fence(log_tail),
            "only_env": baseline_red.ONLY_ENV, "lang": prompt.lang(values["lang"])}
    return vals, {"declared": (root / declared_checks.DECL_NAME).is_file(), "spawns": False}


def retry(place, repo, values: dict, keys: list, reply) -> dict:
    """書き手の返り reply（{made, body, why} か None）の本文で実行器を置き換え（suitewrite.put_runner）、輪の頭をやり直して
    tdd-start.json を書き直す。直らない・書けなかった時は、最初の壊れの返り（suite_broken つき）に訳を足して置き、組を止める"""
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    first = board.read_json(place / board.TDD_START_FILE) or {}
    reply = reply if isinstance(reply, dict) else {}
    why = ""
    if reply.get("made") is not True:
        why = NOT_MADE.format(why=oneline.one_line(reply.get("why") or "") or "書き手が返答を返さなかった")
    else:
        try:
            suitewrite.put_runner(tdd.exe_path(repo, str(first.get("suite") or values["tdd_suite"] or "")), reply.get("body") or "")
        except (ValueError, OSError) as e:
            why = NOT_MADE.format(why=oneline.one_line(e))
    if why:
        out = {**first, "go": False, "suite_broken": True, "reason": f"{first.get('reason') or ''}。{why}"}
    else:
        reuse = reuse_of(values)
        ports.drop_runner_env(values["user_env_dir"])   # 対象のテストに Archon の変数を継がせない（group-start と同じ）
        out = begin(place, repo, values, keys, reuse)
        settle_kept(values, repo, out)
        if out.get("suite_broken") is True:
            out = {**out, "reason": f"{STILL_BROKEN}——{out.get('reason') or ''}"}
    board.write_json(place / board.TDD_START_FILE, out)
    return {"tdd": bool(out.get("base_file")), "stop": out.get("suite_broken") is True, "reason": str(out.get("reason") or "")}

