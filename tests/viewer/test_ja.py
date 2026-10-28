"""日本語の写し（viewer/src/ja.py。docs/design/viewer.md の照らしの 6）。

- 取り込みの口は、今の木の md の段落の鍵の訳だけを viewer/ja/ に書き、ほかの段落の訳は利用者のキャッシュに書く（持ち主の決め viewer-in-repo の 4）。
  差し込み口か印の字を英語と同じに持たない訳は、どちらにも書かない
- 写しは、run の値の記録から、工場の組み立ての口（prompt.compose）で、段落を訳に差し替えた md の木を組んで作る。訳の無い段落と合わない訳は
  英語のまま残る
- viewer/ja/ の訳のうち今の木の md の段落に当たる物は、どれも英語の段落と同じ差し込み口と印の字を持つ（組み立てが英語と同じ値と段落の選びで
  通る）。md を直して古くなった鍵は赤にしない（英語で出るだけ。消すのは --ja-prune）

試験は一時のフォルダに木と控えと置き場を組み、本物の viewer/ja/ と利用者のキャッシュに書かない。
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from viewer.src import ja

HEAD = "Read the {file} carefully and write down every finding you have about it."
TAIL = "Answer in the language of the request, never in any other one."
OTHER = "This paragraph is not in any md of the factory tree, it came from the conversation."


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.pack = self.tmp / "pack"
        self.write("demo/prompts/role.md", f"{HEAD}\n\n<!-- if web -->\nYou may search the web for anything that helps with the file.\n<!-- end web -->\n{{shared:tail}}\n")
        self.write(".shared/prompts/tail.md", f"<!-- required-for-tools: Agent -->\n{TAIL}\n")
        self.env = {"HOME": str(self.tmp), "XDG_CACHE_HOME": str(self.tmp / "cache")}
        self.repo = self.tmp / "repo" / "paragraphs.json"
        for name, value in (("REPO", self.repo), ("TREE", self.pack)):
            patch = mock.patch.object(ja, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def write(self, rel: str, text: str) -> None:
        (self.pack / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.pack / rel).write_text(text, encoding="utf-8")

    def cache(self) -> dict:
        path = self.tmp / "cache" / "works-factory" / ja.CACHE
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


class TakeCase(Base):
    def test_only_tree_paragraphs_go_to_the_repo(self):
        """束の訳を取り込むと、今の木の md の段落の訳は viewer/ja/ に、会話の段落の訳はキャッシュに入る。差し込み口を落とした訳は拒む"""
        todo = {ja.key(HEAD): HEAD, ja.key(OTHER): OTHER, ja.key(TAIL): TAIL}
        self.assertEqual(ja.export(todo, self.tmp / "b"), 1)
        (self.tmp / "b" / "batch-0.ja.txt").write_text(
            f"%%% {ja.key(HEAD)}\n{{file}} を注意して読み、見つけた物を全部書く。\n"
            f"%%% {ja.key(OTHER)}\nこの段落は工場の木の md に無く、会話から来た。\n"
            f"%%% {ja.key(TAIL)}\n依頼の言語で答える {{lang}}。\n", encoding="utf-8")
        to_repo, to_cache, refused = ja.take(self.tmp / "b", self.env)
        self.assertEqual((to_repo, to_cache), (1, 1))
        self.assertEqual(json.loads(self.repo.read_text(encoding="utf-8")), {ja.key(HEAD): "{file} を注意して読み、見つけた物を全部書く。"})
        self.assertEqual(self.cache(), {ja.key(OTHER): "この段落は工場の木の md に無く、会話から来た。"})
        self.assertEqual(len(refused), 1, refused)
        self.assertIn(ja.key(TAIL), refused[0])

    def test_prune_drops_keys_the_tree_no_longer_has(self):
        self.repo.parent.mkdir(parents=True)
        self.repo.write_text(json.dumps({ja.key(HEAD): "訳", "0" * 16: "古い訳"}), encoding="utf-8")
        self.assertEqual(ja.prune(), 1)
        self.assertEqual(list(json.loads(self.repo.read_text(encoding="utf-8"))), [ja.key(HEAD)])


class ComposeCase(Base):
    def test_copy_is_composed_by_the_factory_mouth_from_the_kept_values(self):
        """値の記録（<node>-viewer-values-<n>.json）の値と段落の選びで、訳に差し替えた md の木を工場の組み立ての口で組む。訳の無い段落と、
        差し込み口を落とした訳は英語のまま"""
        place = self.tmp / "artifacts" / "demo"
        place.mkdir(parents=True)
        (place / "role-viewer-values-1.json").write_text(json.dumps({"node": "role", "block": "demo", "md": {"prompt": "prompts/role.md"},
                                                                     "values": {"file": "a.md"}, "when": {"web": False}}), encoding="utf-8")
        (place / "role-prompt-1.md").write_text("英語の指示\n", encoding="utf-8")
        self.repo.parent.mkdir(parents=True)
        self.repo.write_text(json.dumps({ja.key(HEAD): "{file} を注意して読む。", ja.key(TAIL): "依頼の言語で答える。{dropped}"}), encoding="utf-8")
        event = {"artifacts": str(self.tmp / "artifacts"), "path": "demo__role", "tokens": ["demo", "role"], "run": "r"}
        data = {"shape": {"graphs": {}}, "run": {"events": [event], "sessions": {}}, "texts": {}}
        missing = ja.attach(data, self.pack, self.env)
        self.assertEqual(event["prompts"], [{"md": "role", "n": 1, "ja": {"prompt": f"a.md を注意して読む。\n\n{TAIL}\n"},
                                             "error": ""}])
        self.assertEqual(sorted(missing.values()), [TAIL, "You may search the web for anything that helps with the file."])
        self.assertEqual(data["ja"], {"md": 2, "texts": 0})

    def test_the_kept_values_are_picked_by_the_prompt_sent_in_the_conversation(self):
        """出来事の会話の記録が在れば、place の英語の指示の字が会話に入った物の記録を引く（md の名がノードの id と違っても当たる）。
        会話に入っていない回は引かない"""
        place = self.tmp / "artifacts" / "demo"
        place.mkdir(parents=True)
        for n, file in ((1, "a.md"), (2, "b.md")):
            (place / f"role-viewer-values-{n}.json").write_text(json.dumps({"node": "role", "block": "demo", "md": {"prompt": "prompts/role.md"},
                                                                             "values": {"file": file}, "when": {"web": True}}), encoding="utf-8")
            (place / f"role-prompt-{n}.md").write_text(f"sent {file}\n", encoding="utf-8")
        event = {"artifacts": str(self.tmp / "artifacts"), "path": "demo__ask", "tokens": ["demo", "ask"], "run": "r", "session": "s"}
        data = {"shape": {"graphs": {}}, "run": {"events": [event], "sessions": {"s": {"system": [], "inject": [], "seq": [["user", "m"]]}}},
                "texts": {"m": "sent b.md"}}
        ja.attach(data, self.pack, self.env)
        self.assertEqual([(p["md"], p["n"], p["error"]) for p in event["prompts"]], [("role", 2, "")])
        self.assertIn("b.md", event["prompts"][0]["ja"]["prompt"])


class RepoCase(unittest.TestCase):
    def test_repo_translations_of_the_tree_keep_slots_and_marks(self):
        """viewer/ja/ の訳のうち、今の木の md の段落に当たる物は、どれも英語と同じ差し込み口と印の字を持つ"""
        got = json.loads(ja.REPO.read_text(encoding="utf-8")) if ja.REPO.is_file() else {}
        english = {}
        for path in ja._md_files(ja.TREE):
            english.update(ja.translate(path.read_text(encoding="utf-8"), {})[1])
        bad = sorted(mark for mark, text in got.items() if mark in english and not ja.fits(english[mark], text))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
