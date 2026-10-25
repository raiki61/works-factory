# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node writer-pick・ruled-writer-pick（書き手の外の輪の頭）: 注文の在る型を順に 1 つ選び（src/writers.pick）、その型の段の頭（段の頭の木・
除くパスの姿・注文の since）を控え直す。1 回目の段（入力 pass first）は先に tdd の輪が諦めた単位を variant の注文に書き直し、組が no-suite で
止まっていれば型を選ばない。裁定の後の段（pass ruled）は直す裁定が在る時だけ、段の頭で 1 度、裁定の後の直しの注文を書く。
返り {go, writer（選んだ型の書き手の node の名）, done（この型の後に回す型が残らない）}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402

from src import writers  # noqa: E402

NODE = "writer-pick"
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    pass_ = ports.choice(os.environ.get("INPUTS_PASS"), tuple(writers.SEQUENCE))
    return writers.pick(ports.place(), Path.cwd(), pass_, skip=SKIP)


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NODE}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
