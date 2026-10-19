"""blocks/.shared/prompt.py の口（docs/design/README.md の 5 節）: md に値を入れて指示を組み、md と値が食い違えば名指して落ちる"""
import sys
import unittest
from unittest import mock

from tests.bin import hermetic
from tests.blocks import kit

sys.dont_write_bytecode = True
sys.path.insert(0, str(kit.SHARED))
import prompt  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.block = hermetic.tmpdir(self) / "demo"
        (self.block / "prompts" / "parts").mkdir(parents=True)

    def md(self, text, name="role"):
        (self.block / "prompts" / f"{name}.md").write_text(text, encoding="utf-8")

    def part(self, name, text):
        (self.block / "prompts" / "parts" / f"{name}.md").write_text(text, encoding="utf-8")

    def render(self, values=None, when=None, name="role"):
        return prompt._compose(self.block, name, values or {}, when)["prompt"]

    def refused(self, word, values=None, when=None):
        with self.assertRaisesRegex(prompt.PromptError, word):
            self.render(values, when)


class SlotCase(Base):
    def test_values_fill_slots_and_braces_stay(self):
        self.md('Hello {name}, {count} items.\nJSON {"a": 1} and {id, url} stay; {{name}} is literal.\n')
        got = self.render({"name": "x{y}", "count": 3})
        self.assertEqual(got, 'Hello x{y}, 3 items.\nJSON {"a": 1} and {id, url} stay; {name} is literal.\n')

    def test_missing_and_unused_values_are_named(self):
        self.md("A {one} B {two}\n")
        self.refused(r"\['two'\] に値が無い", {"one": "1"})
        self.refused(r"値 \['three'\] の差し込み口", {"one": "1", "two": "2", "three": "3"})

    def test_values_are_text_or_integers(self):
        self.md("A {one}\n")
        for bad in (True, ["x"], None):
            with self.subTest(bad=bad):
                self.refused("字でも整数でもない", {"one": bad})

    def test_slots_in_unselected_paragraphs_still_need_values(self):
        """値の有無は選ばれない段落の中も数える（prep は同じ値をいつも渡す。段落の真偽で値の組が変わらない）"""
        self.md("<!-- if extra -->\nX {more}\n<!-- end extra -->\nY\n")
        self.refused(r"\['more'\] に値が無い", {}, {"extra": False})
        self.assertEqual(self.render({"more": "m"}, {"extra": False}), "Y\n")


class ParagraphCase(Base):
    def test_if_and_if_not_select_and_drop_marks(self):
        self.md("Head\n\n<!-- if web -->\nOn\n<!-- end web -->\n<!-- if not web -->\nOff\n<!-- end web -->\n\n\nTail\n")
        self.assertEqual(self.render(when={"web": True}), "Head\n\nOn\n\nTail\n")
        self.assertEqual(self.render(when={"web": False}), "Head\n\nOff\n\nTail\n")

    def test_when_and_md_must_agree(self):
        self.md("<!-- if web -->\nOn\n<!-- end web -->\n")
        self.refused("when に無い", when={})
        self.refused(r"when の名 \['other'\]", when={"web": True, "other": False})
        self.refused("真偽だけ", when={"web": "yes"})

    def test_malformed_marks_are_refused(self):
        cases = {
            "<!-- if a -->\n<!-- if b -->\nx\n<!-- end b -->\n<!-- end a -->\n": "入れ子",
            "<!-- if a -->\nx\n": "閉じていない",
            "<!-- if a -->\nx\n<!-- end b -->\n": "組にならない",
            "text <!-- if a --> x\n<!-- end a -->\n": "1 行に 1 つ",
        }
        for text, word in cases.items():
            with self.subTest(word=word):
                self.md(text)
                self.refused(word, when={"a": True, "b": True})


class FragmentCase(Base):
    def test_shared_and_part_fragments_are_inserted(self):
        self.part("rules", "Rule {limit}.")
        self.md("<!-- if rejected -->\n{shared:rejected}\n<!-- end rejected -->\n\n{part:rules}\n")
        got = self.render({"rejection": "理由 1", "limit": 2}, {"rejected": True})
        self.assertIn("## Why your previous answer was rejected", got)
        self.assertIn("理由 1", got)
        self.assertTrue(got.endswith("Rule 2.\n"), got)
        self.assertEqual(self.render({"rejection": "", "limit": 2}, {"rejected": False}), "Rule 2.\n")

    def test_missing_and_looping_fragments_are_refused(self):
        self.md("{part:absent}\n")
        self.refused("断片 .* が無い")
        self.part("a", "{part:b}")
        self.part("b", "{part:a}")
        self.md("{part:a}\n")
        self.refused("自分を差し込む")

    def test_missing_md_is_named(self):
        with self.assertRaisesRegex(prompt.PromptError, "指示の md"):
            prompt._compose(self.block, "absent", {}, None)
        with self.assertRaisesRegex(prompt.PromptError, "node の id"):
            prompt._compose(self.block, "../x", {}, None)

    def test_every_shared_fragment_expands(self):
        """共通の断片は、どれも差し込めて、断片の中の断片も解ける（.shared の断片は part を持たない）"""
        for path in sorted((kit.SHARED / "prompts").glob("*.md")):
            with self.subTest(fragment=path.name):
                self.md("{shared:%s}\n" % path.stem)
                text = prompt._expand("{shared:%s}" % path.stem, self.block, (), False)
                self.assertNotIn("{shared:", text)
                self.assertNotIn("{part:", text)


class SystemCase(Base):
    """system prompt の文も md に置く（prompts/<node-id>.system.md）。同じ値と when で組み、値の有無は 2 本の和で数える"""

    def test_system_md_is_rendered_with_the_same_values(self):
        self.md("Task {task}\n")
        self.md("You are {who}.\n<!-- if strict -->\nBe strict.\n<!-- end strict -->\n", name="role.system")
        got = prompt._compose(self.block, "role", {"task": "t", "who": "the reviewer"}, {"strict": True})
        self.assertEqual(got, {"prompt": "Task t\n", "system": "You are the reviewer.\nBe strict.\n"})
        with self.assertRaisesRegex(prompt.PromptError, r"\['who'\] に値が無い"):
            prompt._compose(self.block, "role", {"task": "t"}, {"strict": True})

    def test_no_system_md_gives_no_system(self):
        self.md("Task\n")
        self.assertEqual(set(prompt._compose(self.block, "role", {}, None)), {"prompt"})


class CallerCase(Base):
    def test_render_outside_a_block_is_refused(self):
        with self.assertRaisesRegex(ValueError, "block の中に無い"):
            prompt.render("world-classes", {})

    def test_emit_writes_the_prompt_in_the_place(self):
        """emit は呼んだ block の md を組んで place に <node>-prompt-<n>.md を書く（呼び手は world の src）"""
        run = kit.Run(self, "world")
        steps = kit.load("world", "steps")
        with run.env():
            steps.intake(run.artifacts, request='[{"where": "README", "text": "x"}]', purpose="", means="[]", web="on", lang="")
            got = steps.classes_prompt(run.artifacts)
        self.assertEqual((run.artifacts / "world-classes-prompt-1.md").read_text(encoding="utf-8"), got["prompt"])

    def test_lang_default(self):
        self.assertEqual(prompt.lang(""), "the language of the request (the user's language)", "空なら共通の断片の文")
        self.assertEqual(prompt.lang(" Japanese "), "Japanese")


class SubCase(Base):
    """sub: block の prompts/sub/<name>.md（AI の node でない下請けの頼み）を render と同じ決まりで組み、place に書かない"""

    def sub(self, text, values=None, when=None):
        (self.block / "prompts" / "sub").mkdir(exist_ok=True)
        (self.block / "prompts" / "sub" / "helper.md").write_text(text, encoding="utf-8")
        return prompt._compose(self.block, "helper", values or {}, when, folder="sub")["prompt"]

    def test_fragments_paragraphs_and_slots(self):
        self.part("rules", "Rule {x}\n")
        got = self.sub("{template}\n{part:rules}\n<!-- if ask -->\nAsk\n<!-- end ask -->\n", {"template": "T", "x": "1"}, {"ask": False})
        self.assertEqual(got, "T\nRule 1\n")

    def test_missing_value_is_refused(self):
        with self.assertRaisesRegex(prompt.PromptError, r"\['template'\] に値が無い"):
            self.sub("{template}\n")

    def test_sub_writes_nothing_in_the_place(self):
        """fix の prompts/sub/g1-review.md を組んでも place に何も書かない（書くのは呼び手）"""
        run = kit.Run(self, "fix")
        with run.env(), mock.patch.object(prompt.ports, "caller_block", return_value=kit.BLOCKS / "fix"):
            got = prompt.sub("g1-review", {"template": "TEMPLATE"}, {"spawns": False})
        self.assertTrue(got.startswith("TEMPLATE\n"))
        self.assertEqual(list(run.artifacts.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
