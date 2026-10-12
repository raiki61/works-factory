# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""線の script が共に使う口（名前の script ではない。同じフォルダの script が import する）。

- 境の口（boundary）と、Archon が渡した字を値に戻す部品（skip_value）と lib/ を読めるようにする
- run(compute, fallback): 線の script は節として落ちない。落ちると、それを `{from, if_skipped}` で受ける節が読めず
  （止めた Archon の dag-executor.ts の resolveBindingDirective は落ちた節を if_skipped に落とさない）、報告まで届かないので、
  中の例外は fallback(理由) の返りにして返す
- guarded_imports(): script の lib/ の import を囲む。import が落ちた訳は run が fallback の返りにする（lib/ の誤りでも節は落ちない）。
  だからこの口は lib/ を import せず、線が足す止めの理由の語も字で持つ（lib/stopby.py の declare の形。試験が突き合わせる）
- 関所の答えの語
"""
import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
import skip_value  # noqa: E402

sys.path.append(str(boundary.lib_root()))

START_REFUSED = "works:start-refused"
NEEDS_HUMAN = "works:needs-human"
LINE_SCRIPT = "works:line-script"
DECLARED = {   # 線が足す止めの理由の語と意味（lib/stopby.py の declare に渡す物）
    START_REFUSED: "入口が入力を受けなかった（AI を起こす前に止めた）",
    NEEDS_HUMAN: "無人の run で人の関所を開くはずだった（開かずに止めた）",
    LINE_SCRIPT: "線の script の中で例外が起きた（後ろを飛ばして報告へ進めた）",
}
HUMAN = "human:"   # 人が関所で止めた時の止めの理由の頭（docs/design.md の「ブロックの返りの約束」。後ろは関所の節の id）
GO_WORDS = ("approve", "continue")
REJECT = "reject"   # 今の works の関所の語で、stop と同じ。decisions に無い語の答えを Archon は run の取り消しとして扱う
DRY_RUN_APPROVED = "approved"   # 筋書き（workflow test）の関所がいつも返す字。決めの語の approve と読む
STRINGS = ("mode", "red_cause", "stop_reason", "objection", "rejudge_verdict", "hash", "reason", "unread")   # JSON として読まない欄

_import_error = None


@contextlib.contextmanager
def guarded_imports():
    """lib/ の import を囲む。落ちたら訳を控え、後の run が compute を呼ばずに fallback の返りにする"""
    global _import_error
    try:
        yield
    except Exception as error:   # 線の script は落ちない（上の docstring）
        _import_error = error


def run(compute, fallback) -> None:
    """compute() の返りを節の返りにする。lib/ の import が落ちていた時と compute の例外は fallback(理由の 1 行) の返りにする"""
    try:
        if _import_error is not None:
            raise _import_error
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
