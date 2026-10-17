# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""メイングラフの頭のノード testcmd（docs/design.md の「メイングラフ」の「順と承認ノード」の 0）。

入力 test_cmd が run の作業ツリーの直しでなく対象の手元を試す形（lib/testcmd_check.py。決まりはそちら）なら、出力 {stop, reason} の
stop を真にし、次の cancel のノード testcmd-stop が reason を理由に、AI を起こす前に run を止める。形を知った上で回す人の許し
（ALLOW_ENV が 1）が在れば止めず、reason に形を残す。確かめそのものが落ちた時も、手元を試す形を除けないので同じに
止める（許しが在れば止めない）。

対象の手元は run の作業ツリーの主の作業ツリー（Archon が run の作業ツリーを切った元の clone）。test_cmd を走らせる環境は、
試験と同じく lib/tree_run.outside_env（利用者の HOME・XDG に戻し、uv が足した物を外した写し）で見る。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import testcmd_check
    import tree_run

# lib/testcmd_check.py の ALLOW_ENV の写し（lib を読めない時の fallback も引く。tests/workflows/test_testcmd_head.py が突き合わせる）
ALLOW_ENV = "WORKS_FACTORY_ALLOW_TESTCMD"
STOP_HEAD = "止める（test_cmd）: "
ALLOWED_HEAD = "注意（test_cmd）: "


def allowed() -> bool:
    return os.environ.get(ALLOW_ENV) == "1"


def check(cmd: str, cwd: Path) -> dict:
    if not cmd.strip():
        return {"stop": False, "reason": ""}
    boundary.aim_user_env()
    root = testcmd_check.primary_checkout(cwd)
    found = testcmd_check.stops(root, cmd, tree_run.outside_env(os.environ))
    if not found:
        return {"stop": False, "reason": ""}
    if allowed():
        return {"stop": False, "reason": "\n".join([*(ALLOWED_HEAD + f for f in found),
                                                    f"{ALLOW_ENV}=1 なので止めずに進める（上の形は作業ツリーの直しでなく"
                                                    "対象の手元を試しうる）"])}
    return {"stop": True, "reason": "\n".join([*(STOP_HEAD + f for f in found),
                                               f"test_cmd が対象の手元（{root}）を走らせる形なので、AI を起こす前に run を止めた（run の"
                                               "試験が直しでなく手元のコードを試し、直しの正誤に関わらず緑になりうる）。作業ツリーの中で"
                                               "環境を作る形にして打ち直す。形を知った上で回すなら"
                                               f" {ALLOW_ENV}=1 を前に付ける（README.md の「test_cmd と作業ツリー」）"])}


def fallback(reason: str) -> dict:
    if allowed():
        return {"stop": False, "reason": f"test_cmd の形の確かめ（lib/testcmd_check.py）が落ちた（{reason}）。"
                                         f"{ALLOW_ENV}=1 なので確かめずに進める"}
    return {"stop": True, "reason": f"test_cmd の形の確かめ（lib/testcmd_check.py）が落ち（{reason}）、対象の手元を走らせる形かを"
                                    "確かめられないので、AI を起こす前に run を止めた。確かめずに回すなら"
                                    f" {ALLOW_ENV}=1 を前に付ける"}


if __name__ == "__main__":
    boundary.run(lambda: check(os.environ.get("INPUTS_TEST_CMD", ""), Path.cwd()), fallback)
