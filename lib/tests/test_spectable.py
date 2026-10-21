"""仕様駆動の道の表の読みと、部品に渡す入力の組み立て（lib/spectable.py。docs/design/spec-driven.md の 2.3・2.5・2.6・6.7）。

表を読む所は 2 か所（block works-factory-spec-driven の入口の script と、起動の殻が表を読む script）で、どちらもこのモジュールを使う。
ここは一時のフォルダに表と設計書を置いて直に呼ぶ。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import spectable  # noqa: E402

DESIGN = """# 設計書: cache

- 何の話か: キャッシュの置き場を利用者の設定に従わせる。
- 決めたこと: 環境変数を 1 つ読む。
- 持ち主に求めること: なし。

## 背景

今はホームの直下に置く。

```md
## Purpose
コードの囲みの中の見出しは見ない
```

## 振る舞い

a1 のとおり。

## TDD で直す所

- 置き場を決める関数
"""

TABLE = """design: docs/design/cache.md
purpose: キャッシュが利用者の思う所に置かれる
acceptance:
  - key: a1
    given: XDG_CACHE_HOME が在る
    when: ツールを起こす
    then: その下に置く
  - key: a2
    when: 何も設定が無い
    then: ~/.cache の下に置く
test_cmd: ""
out_of_scope:
  - glob: docs/**
    why: 文書は直さない
reviews:
"""


def review(part, findings=()):
    return f"  - part: {part}\n    run: run-{part}\n    findings: {json.dumps(list(findings), ensure_ascii=False)}\n"


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        (self.root / "docs" / "design").mkdir(parents=True)
        (self.root / "docs" / "design" / "cache.md").write_text(DESIGN, encoding="utf-8")

    def put(self, text=None) -> pathlib.Path:
        path = self.root / "docs" / "design" / "cache.spec.yaml"
        path.write_text(text if text is not None else TABLE + "".join(review(p) for p in spectable.PARTS), encoding="utf-8")
        return path


class ReadCase(Base):
    def test_good_table_has_no_problems(self):
        spec = spectable.read(self.root, self.put())
        self.assertEqual(spectable.problems(spec), [])
        self.assertEqual((spec.table_rel, spec.design_rel), ("docs/design/cache.spec.yaml", "docs/design/cache.md"))

    def test_shape_problems(self):
        """1: 形（必須の欄・acceptance が 1 件以上で when と then が空でない・handling が accepted で owner_words が空でない）"""
        bad = TABLE.replace("    then: その下に置く\n", "    then: ' '\n") + review(spectable.PARTS[0], [
            {"key": "k", "text": "t", "handling": "rejected", "owner_words": ""}])
        got = spectable.problems(spectable.read(self.root, self.put(bad)))
        self.assertTrue(any("acceptance" in p and "then" in p for p in got), got)
        self.assertTrue(any("handling" in p for p in got), got)
        self.assertTrue(any("owner_words" in p for p in got), got)

    def test_yaml_that_is_not_a_mapping_is_a_problem(self):
        got = spectable.problems(spectable.read(self.root, self.put("- a\n- b\n")))
        self.assertEqual(len(got), 1)
        self.assertIn("表", got[0])

    def test_unreadable_yaml_is_a_problem(self):
        got = spectable.problems(spectable.read(self.root, self.put("a: [\n")))
        self.assertEqual(len(got), 1)
        self.assertIn("YAML", got[0])

    def test_design_must_be_in_the_target(self):
        """2: 設計書が対象に在る"""
        got = spectable.problems(spectable.read(self.root, self.put(TABLE.replace("cache.md", "nope.md")
                                                                     + "".join(review(p) for p in spectable.PARTS))))
        self.assertTrue(any("設計書" in p and "nope.md" in p for p in got), got)

    def test_every_part_once(self):
        """4: reviews に必ず回す 5 つの部品が 1 つずつ在る"""
        text = TABLE + "".join(review(p) for p in spectable.PARTS[1:]) + review(spectable.PARTS[1])
        got = spectable.problems(spectable.read(self.root, self.put(text)))
        self.assertTrue(any(spectable.PARTS[0] in p for p in got), got)
        self.assertTrue(any(spectable.PARTS[1] in p and "2" in p for p in got), got)

    def test_duplicate_acceptance_keys(self):
        text = TABLE.replace("key: a2", "key: a1") + "".join(review(p) for p in spectable.PARTS)
        got = spectable.problems(spectable.read(self.root, self.put(text)))
        self.assertTrue(any("a1" in p for p in got), got)


class HeadingCase(Base):
    def test_table_names_as_headings_are_hits(self):
        """3: 設計書の見出しに表の 4 つの名が無い（ATX・Setext。コードの囲みの中は見ない。頭の番号・# ・` は外す。一部に含むだけは止めない）"""
        text = ("# t\n\n## 2.1 目的\n\nx\n\nAcceptance Criteria\n===\n\n### `test_cmd`\n\n## 目的の外の所見\n\n"
                "```\n## 触らない物\n```\n~~~\n## Non-Goals\n~~~\n")
        self.assertEqual(spectable.heading_hits(text), ["目的", "acceptance criteria", "test_cmd"])
        self.assertEqual(spectable.heading_hits(DESIGN), [])

    def test_hits_are_problems(self):
        (self.root / "docs" / "design" / "cache.md").write_text(DESIGN + "\n## Out of scope\n\nx\n", encoding="utf-8")
        got = spectable.problems(spectable.read(self.root, self.put()))
        self.assertTrue(any("out of scope" in p for p in got), got)


class InputsCase(Base):
    def test_rows(self):
        spec = spectable.read(self.root, self.put())
        head, *sections = spectable.design_rows(spec)
        self.assertEqual(head, {"where": "docs/design/cache.md",
                                "text": "- 何の話か: キャッシュの置き場を利用者の設定に従わせる。\n- 決めたこと: 環境変数を 1 つ読む。"})
        self.assertEqual([s["where"] for s in sections],
                         ["docs/design/cache.md#背景", "docs/design/cache.md#振る舞い", "docs/design/cache.md#TDD で直す所"])
        self.assertIn("## Purpose", sections[0]["text"], "コードの囲みの中は節の本文")
        self.assertEqual(spectable.acceptance_rows(spec), [
            {"where": "docs/design/cache.spec.yaml#a1", "text": "前提: XDG_CACHE_HOME が在る。きっかけ: ツールを起こす。振る舞い: その下に置く。"},
            {"where": "docs/design/cache.spec.yaml#a2", "text": "きっかけ: 何も設定が無い。振る舞い: ~/.cache の下に置く。"}])

    def test_proposal_has_the_design_and_the_table_without_reviews(self):
        spec = spectable.read(self.root, self.put())
        text = spectable.proposal_text(spec)
        self.assertTrue(text.startswith(DESIGN.rstrip()))
        self.assertIn("機械が確かめる表（docs/design/cache.spec.yaml）:", text)
        self.assertIn("purpose: キャッシュが利用者の思う所に置かれる", text)
        self.assertNotIn("reviews", text)

    def test_inputs_of_each_part(self):
        spec = spectable.read(self.root, self.put())
        got = spectable.part_inputs(spec)
        self.assertEqual(list(got), list(spectable.PARTS))
        purpose = "キャッシュが利用者の思う所に置かれる"
        self.assertEqual(got["works-factory-plan-review"], {"purpose": purpose})
        self.assertEqual(got["works-factory-independent-design"], {"purpose": purpose})
        rows = spectable.design_rows(spec)
        self.assertEqual(got["works-factory-premises"], {"request": rows})
        self.assertEqual(got["works-factory-prior-decisions"],
                         {"request": rows, "entry": "仕様を固める会話（docs/design/cache.md と docs/design/cache.spec.yaml）"})
        self.assertEqual(got["works-factory-world"], {"request": [rows[0], *spectable.acceptance_rows(spec)], "purpose": purpose})

    def test_absolute_table_inside_the_root_is_read_as_relative(self):
        spec = spectable.read(self.root, self.put().resolve())
        self.assertEqual(spec.table_rel, "docs/design/cache.spec.yaml")


if __name__ == "__main__":
    unittest.main()
