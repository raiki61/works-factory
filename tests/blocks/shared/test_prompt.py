"""workflows/.shared/prompt.py の口（docs/design/README.md の 5 節）: md に値を入れて指示を組み、md と値が食い違えば名指して落ちる"""
import json
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

    def from_block(self, code: str) -> dict:
        """block の src/ のモジュールとして code を回す（ports.caller_block が呼び手の在る block を解く道を通す）"""
        names = {"prompt": prompt}
        with mock.patch.object(prompt.ports, "PACK", self.block.parent):
            exec(compile(code, str(self.block / "src" / "brief.py"), "exec"), names)
        return names

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
        self.refused(r"値 \['three'\] の置き換えの印", {"one": "1", "two": "2", "three": "3"})

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


class PartCase(Base):
    def test_part_is_composed_like_a_prompt(self):
        self.part("brief", "Read {file}.\n<!-- if later -->\nAgain.\n<!-- end later -->\n")
        got = prompt._compose(self.block, "brief", {"file": "a.md"}, {"later": True}, part=True)["prompt"]
        self.assertEqual(got, "Read a.md.\nAgain.\n")
        with self.assertRaisesRegex(prompt.PromptError, "に値が無い"):
            prompt._compose(self.block, "brief", {}, {"later": False}, part=True)
        with self.assertRaisesRegex(prompt.PromptError, "が無い"):
            prompt._compose(self.block, "absent", {}, {}, part=True)

    def test_render_part_reads_the_parts_of_the_caller_block(self):
        """render_part は呼んだ block の prompts/parts/ を読む。名は node の id の字だけ（ほかの字は prompts/parts/ の外を指しうるので拒む）。
        呼び手が block の外なら名指して落ちる"""
        self.part("brief", "Read {file}.\n")
        got = self.from_block("out = prompt.render_part('brief', {'file': 'a.md'})\n")
        self.assertEqual(got["out"], "Read a.md.\n")
        for bad in ("my_brief", "../role", "parts/brief"):
            with self.subTest(bad=bad), self.assertRaisesRegex(prompt.PromptError, "断片 の id の形でない"):
                self.from_block(f"prompt.render_part({bad!r}, {{}})\n")
        with self.assertRaisesRegex(ValueError, "block の中に無い"):
            prompt.render_part("brief", {"file": "a.md"})


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
        """共通の断片は、どれも差し込めて、断片の中の断片も解ける（.shared の断片は part を持たない）。断片の名の形でない md
        （REVIEW.md。観点の役がパスで読む正本）は差し込まない"""
        for path in sorted((kit.SHARED / "prompts").glob("*.md")):
            if not prompt.FRAGMENT.fullmatch("{shared:%s}" % path.stem):
                continue
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


class SharedCase(Base):
    """render_shared は pack の .shared/prompts/<名>.md を、render と同じ決まりで組む（呼んだ block を問わない）"""

    def shared_dir(self, **files) -> mock._patch:
        """試験用の .shared の置き場（prompts/<名>.md）に替える"""
        root = hermetic.tmpdir(self) / "shared"
        (root / "prompts").mkdir(parents=True)
        for name, text in files.items():
            (root / "prompts" / f"{name.replace('_', '-')}.md").write_text(text, encoding="utf-8")
        return mock.patch.object(prompt.ports, "SHARED", root)

    def test_it_composes_a_shared_fragment_like_a_prompt(self):
        """差し込み口・段落・断片の中の断片・頭の印の落とし方が render と同じ。呼んだ block が何かは見ない（block の外からも呼べる）"""
        with self.shared_dir(g1_demo="<!-- required-for-tools: Agent -->\nRead {file}.\n<!-- if later -->\nAgain.\n<!-- end later -->\n{shared:inner}\n",
                             inner="Inner {file2}.\n"):
            got = prompt.render_shared("g1-demo", {"file": "a.md", "file2": "b.md"}, {"later": True})
            self.assertEqual(got, "Read a.md.\nAgain.\nInner b.md.\n")
            self.assertEqual(prompt.render_shared("g1-demo", {"file": "a.md", "file2": "b.md"}, {"later": False}), "Read a.md.\nInner b.md.\n")

    def test_it_refuses_what_render_refuses(self):
        """値の欠け・使われない値・when と md の段落の食い違い・無い断片・block の断片（{part:）・自分を差し込む断片・名の形でない物は名指して落ちる"""
        with self.shared_dir(g1_demo="Read {file}.\n<!-- if later -->\nAgain.\n<!-- end later -->\n", bad="{part:x}\n", loop="{shared:loop}\n"):
            with self.assertRaisesRegex(prompt.PromptError, r"\['file'\] に値が無い"):
                prompt.render_shared("g1-demo", {}, {"later": True})
            with self.assertRaisesRegex(prompt.PromptError, r"値 \['more'\] の置き換えの印"):
                prompt.render_shared("g1-demo", {"file": "a", "more": "b"}, {"later": True})
            with self.assertRaisesRegex(prompt.PromptError, "when に無い"):
                prompt.render_shared("g1-demo", {"file": "a"}, {})
            with self.assertRaisesRegex(prompt.PromptError, "が無い"):
                prompt.render_shared("absent", {})
            with self.assertRaisesRegex(prompt.PromptError, "part を持たない"):
                prompt.render_shared("bad", {})
            with self.assertRaisesRegex(prompt.PromptError, "自分を差し込む"):
                prompt.render_shared("loop", {})
            for name in ("../x", "my_brief", "parts/brief"):
                with self.subTest(name=name), self.assertRaisesRegex(prompt.PromptError, "断片 の id の形でない"):
                    prompt.render_shared(name, {})

    def test_it_reads_the_real_shared_fragments(self):
        """本物の .shared/prompts の断片も組める（呼んだ block が無くても）"""
        self.assertEqual(prompt.render_shared("brief-head", {"brief_rows": "- row"}).splitlines()[:3], ["## The requirement (briefs)", "", "- row"])


def replayed(place, node_id: str, n: int, pack=kit.BLOCKS) -> dict:
    """place の <node>-viewer-values-<n>.json の値と段落の選びで指示を組み直し、組んだ物と place の <node>-<key>-<n>.md の字の組を返す"""
    kept = json.loads((place / f"{node_id}-viewer-values-{n}.json").read_text(encoding="utf-8"))
    block = pack / kept["block"]
    for key, rel in kept["md"].items():
        assert (block / rel).is_file(), f"記録の md {rel} が block {kept['block']} に無い"
    again = prompt._compose(block, kept["node"], kept["values"], kept["when"])
    assert sorted(again) == sorted(kept["md"]), f"組み直しの欄 {sorted(again)} が記録の md {sorted(kept['md'])} と違う"
    return {key: (text, (place / f"{node_id}-{key}-{n}.md").read_text(encoding="utf-8")) for key, text in again.items()}


class ViewerValuesCase(Base):
    def test_emit_keeps_values_that_rebuild_the_same_prompt(self):
        """emit は組んだ指示の隣に <node>-viewer-values-<n>.json（工場の外の見る道具のための値と段落の選び）を書き、
        その値と when で組み直すと、place の指示と system が字のまま同じになる"""
        self.md("Hello {name}, {count} items.\n<!-- if web -->\nOn {name}\n<!-- end web -->\n{{literal}}\n")
        (self.block / "prompts" / "role.system.md").write_text("You are {name}.\n", encoding="utf-8")
        place = self.block.parent / "artifacts"
        with mock.patch.dict(prompt.ports.os.environ, {"ARTIFACTS_DIR": str(place)}):
            self.from_block("prompt.emit('role', {'name': 'x{y}$z', 'count': 3}, {'web': False}, 2)\n")
        kept = json.loads((place / "role-viewer-values-2.json").read_text(encoding="utf-8"))
        self.assertEqual(kept, {"node": "role", "block": "demo", "md": {"prompt": "prompts/role.md", "system": "prompts/role.system.md"},
                                "values": {"name": "x{y}$z", "count": 3}, "when": {"web": False}})
        for key, (again, written) in replayed(place, "role", 2, self.block.parent).items():
            with self.subTest(key=key):
                self.assertEqual(again, written)

    def test_when_none_is_kept_as_empty(self):
        self.md("Plain {name}\n")
        place = self.block.parent / "artifacts"
        with mock.patch.dict(prompt.ports.os.environ, {"ARTIFACTS_DIR": str(place)}):
            self.from_block("prompt.emit('role', {'name': 'a'}, None, 1)\n")
        kept = json.loads((place / "role-viewer-values-1.json").read_text(encoding="utf-8"))
        self.assertEqual((kept["md"], kept["when"]), ({"prompt": "prompts/role.md"}, {}))
        for key, (again, written) in replayed(place, "role", 1, self.block.parent).items():
            self.assertEqual(again, written)

    def test_round_of_does_not_count_the_values_file(self):
        self.md("Plain {name}\n")
        place = self.block.parent / "artifacts"
        with mock.patch.dict(prompt.ports.os.environ, {"ARTIFACTS_DIR": str(place)}):
            self.from_block("prompt.emit('role', {'name': 'a'}, None, 1)\n")
            self.assertEqual(self.from_block("n = prompt.round_of('role')\n")["n"], 2)


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
        for key, (again, written) in replayed(run.artifacts, "world-classes", 1).items():
            with self.subTest(key=key):
                self.assertEqual(again, written, "本物の block の指示も、残した値で字のまま組み直せる")

    def test_lang_default(self):
        self.assertEqual(prompt.lang(""), "the language of the request (the user's language)", "空なら共通の断片の文")
        self.assertEqual(prompt.lang(" Japanese "), "Japanese")


if __name__ == "__main__":
    unittest.main()
