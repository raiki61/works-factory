"""書く役の指示書の組み立ての口（裁定 R65）。AI を通さず、機械が決まりのファイルを節に切り、run の値の穴を埋めて繋ぐ。

- CANON: 書く役（コードを直す役はどれも）の決まりの正本 writerules/common.md。ブロックの境を越えて読めるよう core に 1 つだけ置く
  （ほかの置き場に写さない。tests/test_fix_rules.py）。節は core-fix（直し方）・evidence・evidence-<種類>（テストで赤→緑を示せない
  直しの証拠）・core-conflict（食い違いの申し出）・core-keep（守ること）
- sections(path): `<!-- セクション <id> -->` の行で切った {id: 本文}（印の行は指示書に入れない）
- fill: 型の穴 <<名>> を `値`（空は EMPTY）で埋める。穴に値が無い時は Unfilled

指示書の組み立ては prompts/ の md と .shared/prompts/ の口 prompt.py が持つ（ここは決まりの正本の読みと型の穴の埋めだけ）。
"""
import pathlib
import re
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

CANON = _CORE / "writerules" / "common.md"
EMPTY = "（空）"
HOLE = re.compile(r"<<([a-z_]+)>>")
MARK_HEAD = "<!-- セクション"
MARK = re.compile("^" + re.escape(MARK_HEAD) + r" ([a-z0-9-]+) -->$")


class Unfilled(ValueError):
    """型の穴に値が無い・値の名が要る物と違う（回す側の誤り）"""


# ---------------------------------------------------------------- 節
def sections(path) -> dict:
    """決まりのファイルの節 {id: 本文}（ファイルの順。本文の前後の空行は落とす。印の行は入れない）"""
    path = pathlib.Path(path)
    out, cur = {}, None
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = MARK.match(line)
        if m:
            cur = m.group(1)
            if cur in out:
                raise Unfilled(f"{path.name}: セクション {cur} が 2 つ在る")
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
        elif line.strip():
            raise Unfilled(f"{path.name}: セクションの印より前に文が在る: {line[:60]!r}")
    return {k: "\n".join(v).strip("\n") for k, v in out.items()}


def join(texts) -> str:
    """節を繋ぐ: 箇条の行の後に箇条で始まる節が来れば改行 1 つ（同じ箇条を続ける）、ほかは空行 1 つ"""
    out = ""
    for t in texts:
        if not t:
            continue
        if out:
            last = out.rsplit("\n", 1)[-1]
            out += "\n" if t.startswith("- ") and (last.startswith("- ") or last.startswith("  ")) else "\n\n"
        out += t
    return out


def shared() -> str:
    """決まりの正本の全文（全部の節。印の行を除いた字）"""
    return join(sections(CANON).values())


# ---------------------------------------------------------------- 値の穴
def _value(v) -> str:
    v = "" if v is None else str(v)
    return f"`{v}`" if v else EMPTY


def fill(template: str, values: dict) -> str:
    """型の穴 <<名>> を `値`（空は EMPTY）で埋める。1 回の置き換え（埋めた字を読み直さない）"""
    lack = sorted(set(HOLE.findall(template)) - set(values))
    if lack:
        raise Unfilled(f"型の穴に値が無い: {lack}")
    return HOLE.sub(lambda m: _value(values[m.group(1)]), template)


def pick(values: dict, names: tuple) -> dict:
    """run の値から names だけ（欠けは Unfilled）"""
    lack = [k for k in names if k not in values]
    if lack:
        raise Unfilled(f"run の値が無い: {lack}")
    return {k: values[k] for k in names}
