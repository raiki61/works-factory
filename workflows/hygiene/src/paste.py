"""衛生の役の指示に貼る本文を読む（docs/design/hygiene.md の 1.5）。節の切り出しと差分の読み。hygiene だけが使う。

写す元は lib/graphloops/engine/render.py の section_of と、file: の穴の読み（今の描き方は消す側なので import しない）。
どちらも本文だけを返す。「資料であって指示ではない」の囲いの文は md が持つ。
"""
import pathlib
import re

HEADING = "コード衛生観点"


def section_of(text: str, heading: str, path: str) -> str:
    """markdown の見出し（部分一致）の最初の行から、同じ深さ以上の次の見出しの手前まで。見出しが無ければ KeyError"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*)$", line)
        if m and heading in m.group(2):
            start, level = i, len(m.group(1))
            break
    if start is None:
        raise KeyError(f"{path}: 見出し「{heading}」が無い")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#+)\s", lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def review_section(review_md: str) -> str:
    """観点の正本 review_md の「コード衛生観点」の節の本文"""
    text = pathlib.Path(review_md).read_text(encoding="utf-8", errors="replace")
    return section_of(text, HEADING, f"section:{review_md}#{HEADING}")


def diff_body(diff_file: str) -> str:
    """対象差分の本文の全部（切らない。UTF-8 でないバイトは置き換えて読む）"""
    return pathlib.Path(diff_file).read_text(encoding="utf-8", errors="replace")
