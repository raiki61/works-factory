"""指示と照らしの組の照らし（docs/design/fix.md の 22.4 の「指示と照らしの組」）。

書き手の返答から組む事実（duties.REPLY_FACTS）を読む義務の関数は、書かせる段落の名を関数の属性 paragraph 1 つで持ち、その段落が
.shared/prompts/writer.md に在る（writer.md の {shared:<名>} の差し込みを解いた字で見る。where_writer は writer-rules.md に在る）。
読むかは関数の本文の f.get("<名>")（と f["<名>"]）を構文木で引いて決め、組の表は別に持たない。
2026-11-10 に代表のこの 1 本だけを残した（属性を消す・md に無い名に替えると、段落の真偽 prompts.TABLE_WHEN は黙って偽になり、
書き手の型の required も prompt.py の照らしも赤にしない。段落の真偽が型ごとに表のとおりかは test_prompts.py の
WriterSlotsCase.test_the_duty_paragraphs_are_drawn_from_the_duty_tables が見る）。
"""
import ast
import inspect
import textwrap
import unittest

from tests.blocks import kit

duties = kit.load("fix", "duties")
import prompt  # noqa: E402  （.shared。kit.load が sys.path に足す）
import ports  # noqa: E402


def read_names(fn) -> set:
    """関数 fn の本文が事実の鍵として読む字（第 1 引数 f の f.get("名")・f["名"]）"""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    func = tree.body[0]
    arg = func.args.args[0].arg
    out = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == arg \
                and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            out.add(node.args[0].value)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == arg \
                and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            out.add(node.slice.value)
    return out


def writer_paragraphs_in_md() -> set:
    """書き手の指示の md（.shared/prompts/writer.md。差し込みを解いた字）に在る段落の名"""
    raw = prompt._read(ports.SHARED / "prompts" / "writer.md", "md")
    text = prompt._expand(raw, ports.SHARED, (), True)
    return {m.group(2) for line in text.split("\n") if (m := prompt.MARK.match(line.strip()))}


def check_unpaired(fns, paragraphs) -> list:
    """表の関数 fns のうち、REPLY_FACTS を読むのに、属性 paragraph が無いか、その段落が paragraphs（md に在る段落の名）に無い物の文"""
    out = []
    for fn in fns:
        if not read_names(fn) & set(duties.REPLY_FACTS):
            continue
        para = getattr(fn, "paragraph", None)
        if not isinstance(para, str) or not para:
            out.append(f"{fn.__name__}: 書き手の返答から組む事実を読むのに、書かせる段落の属性 paragraph が無い")
        elif para not in paragraphs:
            out.append(f"{fn.__name__}: 段落 {para} が .shared/prompts/writer.md に無い")
    return out


def table_functions() -> list:
    return list(dict.fromkeys(fn for w in duties.WEAPONS for fn in duties.table_of(w)))


class DutyParagraphCase(unittest.TestCase):
    def test_every_function_that_reads_a_reply_fact_names_a_paragraph_that_is_in_the_writer_prompt(self):
        self.assertEqual(check_unpaired(table_functions(), writer_paragraphs_in_md()), [])


if __name__ == "__main__":
    unittest.main()
