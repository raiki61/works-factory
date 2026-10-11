"""線の script が共に使う口（名前の script ではない。同じフォルダの script が import する）。

- 境の口（boundary）と埋め P2 の部品（skip_value）と lib/ を読めるようにする
- run(compute, fallback): 線の script は節として落ちない。落ちると、それを `{from, if_skipped}` で受ける返しの節が読めず
  （止めた Archon の dag-executor.ts の resolveBindingDirective は落ちた節を if_skipped に落とさない）、報告まで届かないので、
  中の例外は fallback(理由) の返りにして返す
- 線が足す止めの理由の語（lib/stopby.py の declare）と、関所の答えの語
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
import skip_value  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import stopby  # noqa: E402

START_REFUSED = stopby.declare("start-refused", "入口が入力を受けなかった（AI を起こす前に止めた）")
NEEDS_HUMAN = stopby.declare("needs-human", "無人の run で人の関所を開くはずだった（開かずに止めた）")
LINE_SCRIPT = stopby.declare("line-script", "線の script の中で例外が起きた（後ろを飛ばして報告へ進めた）")
HUMAN = "human:"   # 人が関所で止めた時の止めの理由の頭（docs/design.md の「ブロックの返りの約束」。後ろは関所の節の id）
GO_WORDS = ("approve", "continue")
DRY_RUN_APPROVED = "approved"   # 筋書き（workflow test）の関所がいつも返す字。決めの語の approve と読む
STRINGS = ("mode", "red_cause", "stop_reason", "objection", "rejudge_verdict", "hash", "reason")   # JSON として読まない欄


def run(compute, fallback) -> None:
    """compute() の返りを節の返りにする。例外は fallback(理由の 1 行) の返りにする"""
    try:
        out = compute()
    except Exception as error:   # 線の script は落ちない（上の docstring）
        reason = " ".join(f"{type(error).__name__}: {error}".split())
        print(reason, file=sys.stderr)
        out = fallback(reason)
    boundary.returns(out)


def value(raw):
    return skip_value.value(raw)


def field(key: str, raw):
    """ブロックの返りの 1 欄。字の欄（STRINGS）は字のまま、ほかは JSON として読む。飛ばされた節（null）は None"""
    return skip_value.text(raw) if key in STRINGS else skip_value.value(raw)


def text(raw) -> str:
    """字の欄。飛ばされた節（null）と無い欄は空の字"""
    return skip_value.text(raw) or ""


def flag(raw) -> bool:
    return skip_value.value(raw) is True


def items(raw) -> list:
    got = skip_value.value(raw)
    return got if isinstance(got, list) else []
