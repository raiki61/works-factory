"""【1 つ目の commit だけ】組んだ指示と材料のファイルが、今の判定の物と同じ字か（docs/design/purpose-review.md の 2.9 の指示の比べ。
README の 11.4）。2 つ目の commit で英語に替える時に、この試験と src/oldbrief.py を消す。

(a) block の prep が組んだ指示 = 今の workflows/judge/commands/material-purpose-review.md に、同じ入力の値（lang_line・reason・
    brief_file）を入れた物（空白は無視）
(b) block の材料のファイル（src/oldbrief.py）= 同じ試験のリポジトリと置き場で、今の judge_accept.material_prep が書いた物
"""
import json
import pathlib
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

NAME = "purpose-review"
LOOP = f"{NAME}-loop"
OLD = kit.ROOT / "workflows" / "judge" / "commands" / "material-purpose-review.md"
TEXT = "設定の読み込みが空のファイルでも落ちないようにする。{id} や $x のような字が入っても読み直さない"
PURPOSE = {"purpose_text": TEXT, "source": "③writer の要約", "known_weaknesses": [], "source_files": []}


def squeeze(text: str) -> str:
    return "".join(text.split())


class PromptCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "README.md").write_text("# 対象\n\n件数は 3 件\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.run.script("intake", "intake", base="", purpose=json.dumps(PURPOSE, ensure_ascii=False), entry="", lang="")
        sys.path.append(str(kit.ROOT / "lib"))

    def old_prompt(self, **values) -> str:
        text = OLD.read_text(encoding="utf-8")
        for name, value in values.items():
            text = text.replace(f"$purpose-review-prep.output.{name}", value)
        return text

    def prep(self) -> str:
        return self.run.script("role_prep", f"{LOOP}.{NAME}-prep")["prompt"]

    def test_the_prompt_is_the_current_one_filled_with_the_same_values(self):
        import rolekit
        brief = str(self.run.artifacts / "material-purpose-review-brief.md")
        lang_line = (kit.SHARED / "prompts" / "lang-default.md").read_text(encoding="utf-8").strip()
        self.assertEqual(squeeze(self.prep()), squeeze(self.old_prompt(lang_line=lang_line, reason="", brief_file=brief)))
        reply = json.dumps({"verdict": "狭めている", "reason": "x", "findings": []}, ensure_ascii=False)
        self.run.script("role_accept", f"{LOOP}.{NAME}-accept", reply=reply)
        with self.run.env():
            reason = rolekit.rejects_text(rolekit.rejected(self.run.artifacts, NAME))
        self.assertTrue(reason)
        self.assertEqual(squeeze(self.prep()), squeeze(self.old_prompt(lang_line=lang_line, reason=reason, brief_file=brief)))

    def test_the_brief_is_the_one_the_current_prep_writes(self):
        import judge_accept as ja
        self.prep()
        view = json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))
        jdir = pathlib.Path(self.run.artifacts) / "old" / ja.JUDGE_DIR
        jdir.mkdir(parents=True)
        head = git(self.run.repo, "rev-parse", "HEAD").strip()
        ja.write_json(jdir / ja.START_FILE, ja.start_view(
            {"base_rev": head, "input": {"base": {"rev": head}, "diff": {"empty": True}, "requests": 0}}))
        ja.write_json(jdir / ja.MATERIAL_VIEW_FILE, view)
        ja.write_json(jdir / ja.PURPOSE_FILE, PURPOSE)
        old = ja.material_prep(jdir, NAME, self.run.repo, "")["brief"]
        new = (self.run.artifacts / "material-purpose-review-brief.md").read_text(encoding="utf-8")
        self.assertEqual(new, old)


if __name__ == "__main__":
    unittest.main()
