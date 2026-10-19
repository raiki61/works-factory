"""keep-essence の 11「直す単位ごとの記録が報告に届く」の、報告に届く半分（docs/design/report.md の 7 節）。fix が単位の行を report の欄に組み、
graph が節にして渡し、report が字を変えずに機械の報告と詳細のファイルに載せる。script を子のプロセスで回して確かめる。"""
import json
import unittest

from tests.blocks import kit
from tests.blocks.report import base

base.src()   # ports を読み込んで lib/ を sys.path に足す
import report  # noqa: E402  lib/

TITLE = "TDD のループの単位ごとの結末"
GROUP_RAN = {"group_id": "g1", "ran": True, "reason": "", "suite": "run-tests", "reused": None,
             "units": [{"unit_key": "u1", "route": "tdd", "why": "", "tests": ["t::a"], "red": "ok", "green": "ok", "refactor": "none",
                        "gave_up": "", "red_quotes": {"t::a": {"quote": "期待 3 が 6", "why": "分母が違う"}}}]}
GROUP_OFF = {"group_id": "g2", "ran": False, "reason": "テストの実行ファイルが無い", "suite": "", "reused": None, "units": []}
INCLUDE = "report__"


def section(title, lines, files=None):
    return {"title": title, "lines": lines, **({"files": files} if files else {})}


class SectionsCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "report")
        self.place = self.run.artifacts / "report"

    def facts(self, sections, facts=None):
        return self.run.script("facts", f"{INCLUDE}facts", sections=json.dumps(sections, ensure_ascii=False),
                               facts=json.dumps(facts or base.READY), lang="")

    def finish(self):
        self.run.script("write_prep", f"{INCLUDE}write-loop.write-prep")
        reply = base.reply()
        self.run.script("cold_prep", f"{INCLUDE}write-loop.cold-prep", writer=reply)
        self.run.script("write_accept", f"{INCLUDE}write-loop.write-accept", reply=reply, cold=json.dumps(base.GOOD_COLD))
        return self.run.script("finish", f"{INCLUDE}finish")

    def test_unit_rows_reach_machine_and_detail_unchanged(self):
        stages = [(f"{report.TDD_STAGES[0]}（組 g1）", GROUP_RAN), (f"{report.TDD_STAGES[0]}（組 g2）", GROUP_OFF)]
        lines = report.tdd_lines(stages)
        self.assertTrue(any(x.startswith("  ") for x in lines) or lines, "見本は字下げの内訳か行を持つ")
        self.facts([section(TITLE, lines)])
        machine = (self.place / "report.md").read_text(encoding="utf-8")
        body = machine.split(f"## {TITLE}\n\n", 1)[1].split("\n## ", 1)[0].rstrip("\n").splitlines()
        self.assertEqual(body, [x if x.startswith("  ") else f"- {x}" for x in lines])
        self.finish()
        detail = (self.place / "report-detail.md").read_text(encoding="utf-8")
        embedded = detail.split("## 機械が各段の出力と run の記録から組んだ事実", 1)[1]
        self.assertIn(f"### {TITLE}\n\n" + "\n".join(body), embedded)
        for quote in ("期待 3 が 6", "分母が違う"):
            self.assertIn(quote, machine)
            self.assertIn(quote, detail)

    def test_sections_keep_their_order(self):
        self.facts([section("三番目", ["c"]), section("一番目", ["a"]), section("二番目", ["b"])])
        text = (self.place / "report.md").read_text(encoding="utf-8")
        titles = [x.removeprefix("## ") for x in text.splitlines() if x.startswith("## ")]
        self.assertEqual([t for t in titles if t in ("三番目", "一番目", "二番目")], ["三番目", "一番目", "二番目"])

    def test_empty_section_is_not_dropped(self):
        self.facts([section("行の無い節", [])])
        text = (self.place / "report.md").read_text(encoding="utf-8")
        self.assertIn("## 行の無い節\n\n- この段は報告の行を返していない\n", text)

    def test_unopenable_file_is_named(self):
        self.facts([section("差分の節", ["x"], [{"label": "差分", "ref": "/no/such/diff.patch"}])])
        text = (self.place / "report.md").read_text(encoding="utf-8")
        line = "差分（差分の節）: 開けない（file の入力のファイル /no/such/diff.patch が無い）"
        self.assertIn(f"## 3. 見る所\n\n- {line}\n", text)
        self.assertIn(f"## 注意（読めなかった物）\n\n- {line}\n", text)

    def test_pointer_ref_is_opened_in_the_same_run(self):
        (self.place).mkdir(parents=True)
        (self.place / "judgment.json").write_text("{}", encoding="utf-8")
        ref = json.loads(self.run.pointer("report/judgment.json"))
        self.facts([section("判定", ["x"], [{"label": "判定", "ref": ref}])])
        text = (self.place / "report.md").read_text(encoding="utf-8")
        self.assertIn(f"- 判定（判定）: {self.place / 'judgment.json'}\n", text)


if __name__ == "__main__":
    unittest.main()
