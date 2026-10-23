"""直す前の自己点検（docs/design/test-gate.md の 15 節。持ち主の決め base-selfcheck-only。#828・#836）。

base は直す前の版で全部の試験を回さない。する事は、TDD の実行器（試験の起動スクリプト）を小さな試験の組で 1 回走らせる事だけ:
- 組（plan）: 変更に関わる試験（lib/related.pick。走らせ方の道に依らず引く）が在ればそれ。選べない・関わる試験が無い時は、作業ツリーの
  試験のファイルのうち名に test の字を持つ物の名の順の最初の 1 つ（見本）。試験のファイルが 1 つも無ければ一式（試験の無い対象の一式は軽い）。組は実行器の約束の
  後ろの引数と合図 baseline_red.ONLY_ENV で渡す（解かない実行器は一式を走らせる。同じ事を確かめる）
- 食い違い（#836）: 工場が用意した実行器（取り置き・AI が書いた物）の自己点検が赤で、test_cmd が在る時だけ、test_cmd を単体で 1 回
  走らせる。単体が緑で、組が一式でなければ実行器を一式でも 1 回走らせ（組が test_cmd の外の元からの赤を拾っただけでないかを確かめる）、
  それも赤なら、壊れているのは起動スクリプト（broken）。base はそこで止まり、判定を起こさない。単体も赤なら止めない
  （試験そのものの赤）。人が渡した実行器（port tdd_suite）は人の選びなので、食い違いでは止めない

run.json の欄 selfcheck {plan: {how, files}, ran: {exe, exit, problems, count, log} | None, cases, test_cmd: {status, log} | None, broken,
whole?（一式で確かめた {exit, problems, count, log}）, setup?（宣言の準備が落ちた訳）}
を node run が置き、実行器を用意する輪の suite-try が埋める。返す node はこれだけを読んで直す前の素材を組む。
"""
from __future__ import annotations

import pathlib

RELATED, SAMPLE, WHOLE = "related", "sample", "whole"   # 組の決め方（plan の how）
STEP = "直す前の自己点検の実行器"   # base の ran_steps に載せる段の名


def plan(root, picked: dict) -> dict:
    """組 {how, files}（files は根からの相対）。picked は lib/related.pick の返り"""
    if not picked.get("whole") and picked.get("files"):
        return {"how": RELATED, "files": list(picked["files"])}
    one = sample(root)
    return {"how": SAMPLE, "files": [one]} if one else {"how": WHOLE, "files": []}


def sample(root) -> str:
    """見本の試験のファイル: 作業ツリーの試験のファイル（lib/impact.is_test が module）のうち、名に test の字を持つ物の名の順の最初。
    無ければ試験のファイルの名の順の最初（-suite.sh のような実行器の台本も試験の名の形に入るので、test の字を持つ物を先にする）。
    試験のファイルが無ければ空の字"""
    import impact   # lib/
    root = pathlib.Path(root)
    found = [p for p in impact.tree_files(root) or [] if impact.is_test(p) == "module" and (root / p).is_file()]
    return next((p for p in found if "test" in pathlib.PurePosixPath(p).name.lower()), found[0] if found else "")


def args(root, got: dict) -> tuple[list, bool]:
    """(実行器の後ろに足す引数, 合図 ONLY_ENV を付けるか)。一式は引数なし・合図なし"""
    if got.get("how") == WHOLE or not got.get("files"):
        return [], False
    root = pathlib.Path(root).resolve()
    return [str(root / f) for f in got["files"]], True


def record(got: dict) -> dict:
    """node run が run.json に置く selfcheck の頭（まだ走らせていない）"""
    return {"plan": got, "ran": None, "cases": [], "test_cmd": None, "broken": False}


def red(ran, cases) -> bool:
    """実行器が結末を返し（JUnit XML が出た）、終了コードが 0 でないか落ちた試験が在る。結末が無い回は赤と読まない（実行器の照らしが
    通らず、実行器の無い道を通る）"""
    import baseline_red   # lib/
    if not isinstance(ran, dict) or ran.get("problems") or cases is None:
        return False
    return ran.get("exit") != 0 or any(c.get("outcome") in baseline_red.FAILED for c in cases)


def compare(root, test_cmd: str, log) -> dict:
    """test_cmd を単体で 1 回走らせた {status, log}（lib/declared_checks.local_checks_material の素材の status）"""
    import declared_checks   # lib/
    got = declared_checks.local_checks_material(pathlib.Path(root), test_cmd, pathlib.Path(log))["material"]
    return {"status": got.get("status"), "log": str(log)}


def broken_line(check: dict) -> str:
    """止めた訳の 1 行（報告の冒頭と返りの reason。食い違いが無ければ ""）"""
    if not check.get("broken"):
        return ""
    ran = check.get("whole") or check.get("ran") or {}
    return (f"試験の起動スクリプトが壊れている——test_cmd を単体で走らせると緑（ログ {check['test_cmd']['log']}）なのに、"
            f"起動スクリプト越しだけが赤（終了コード {ran.get('exit')}。ログ {ran.get('log')}）。判定を起こす前に止めた。"
            "起動スクリプトを直すか、JUnit XML を第 1 引数に書く実行器を入力 tdd_suite に渡して起こし直す")
