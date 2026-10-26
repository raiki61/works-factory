"""指示と照らしの組の照らし（docs/plans/2026-10-24-fix-weapons.md の 11.12 の 3・11.6 の F1 の作る物の 6）。

書き手の返答から組む事実（duties.REPLY_FACTS）を読む義務の関数は、書かせる段落の名を関数の属性 paragraph 1 つで持ち、その段落が
.shared/prompts/writer.md に在る（writer.md の {shared:<名>} の差し込みを解いた字で見る。where_writer は writer-rules.md に在る）。
読むかは関数の本文の f.get("<名>")（と f["<名>"]）を構文木で引いて決め、組の表は別に持たない。表の関数の段落は、writer_slots が
when で真にする名（prompts.DUTY_WHEN）か、型を問わず書き手に載る where_writer のどちらか。照らしの関数（check_unpaired）が赤を出すことは、
属性を持たない関数・md に無い段落を渡して確かめる（照らしを緩めて通さない）。
"""
import ast
import inspect
import textwrap
import unittest

from tests.blocks import kit

duties = kit.load("fix", "duties")
prompts = kit.load("fix", "prompts")
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

    def test_the_functions_reading_reply_facts_are_the_ones_the_plan_names(self):
        """読む関数を構文木で引くので、表の関数が事実を読んでいることを見失わない（引けなければ上の照らしが空振りする）"""
        reading = {fn.__name__ for fn in table_functions() if read_names(fn) & set(duties.REPLY_FACTS)}
        self.assertEqual(reading, {"kinds_rows", "sites_shape", "unit_red", "sites_per_test"})

    def test_a_function_without_the_attribute_or_with_a_paragraph_missing_from_the_md_is_red(self):
        def reads(f):
            return [] if f.get("sites") else ["x"]

        def quiet(f):
            return [] if f.get("added") else ["x"]

        self.assertEqual(len(check_unpaired([reads], {"rules_sites_at"})), 1, "属性が無い")
        reads.paragraph = "rules_sites_at"
        self.assertEqual(check_unpaired([reads], {"rules_sites_at"}), [])
        self.assertEqual(len(check_unpaired([reads], {"rules_sites"})), 1, "段落が md に無い")
        self.assertEqual(check_unpaired([quiet], set()), [], "事実を読まない関数は属性を要らない")
        for fn in table_functions():
            if read_names(fn) & set(duties.REPLY_FACTS):
                with self.subTest(fn=fn.__name__):
                    para = fn.paragraph
                    del fn.paragraph
                    try:
                        self.assertEqual(len(check_unpaired([fn], writer_paragraphs_in_md())), 1)
                    finally:
                        fn.paragraph = para
                    self.assertEqual(len(check_unpaired([fn], writer_paragraphs_in_md() - {para})), 1)

    def test_a_paragraph_of_the_table_is_true_in_the_slots_of_the_weapons_that_have_the_function(self):
        """段落の真偽は表から引かれる: 表に在る関数の段落（DUTY_WHEN の名）は、その関数を持つ型の slots で真、持たない型で偽。
        where_writer は書き手に型を問わず載る段落なので DUTY_WHEN に入れない"""
        for fn in table_functions():
            para = getattr(fn, "paragraph", None)
            if para:
                self.assertIn(para, (*prompts.DUTY_WHEN, "where_writer"), fn.__name__)
        for w in duties.WEAPONS:
            want = {fn.paragraph for fn in duties.table_of(w) if getattr(fn, "paragraph", None) in prompts.DUTY_WHEN}
            got = prompts.writer_paragraphs(w)
            with self.subTest(weapon=w):
                self.assertTrue(want <= {k for k, v in got.items() if v}, (want, got))
                self.assertFalse({k for k in prompts.TABLE_WHEN if got[k]} - want, "表に無い段落は真にしない")


if __name__ == "__main__":
    unittest.main()
