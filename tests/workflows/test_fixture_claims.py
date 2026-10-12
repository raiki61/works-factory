"""筋書き（workflows/*/fixtures/*.yaml）が、確かめられない周ごとの値を確かめたと言わない（落とし穴 K6）。

`archon workflow test` の筋書きは周を回すが、前の周の出力を渡さない（止めた Archon の packages/workflows/src/dry-run.ts 795 行の
`loopPrevOutput: ''`・1053-1085 行。stub は節ごとに 1 つで毎周同じ値）。周ごとに違う値・前の周の値は本物の run でしか見られない。
- 筋書きの注記（`#` で始まる行）と `fixture.resolved-text-contains` の字に、CLAIMS の言い回しが在れば赤
- 「3 回とも拒んだ」のように同じ値の周の数を言うのは、毎周同じ stub で正しく起きるので赤にしない
- 今の食い違いは表 ALLOWED に行ごとに名指して許す。表の行が今の木に当たらなければ赤
"""
import pathlib
import re
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUND = r"(?:周|往復|回)"
# 言い回し -> その形が言うこと
CLAIMS = {
    re.compile(ROUND + r"ごとに?[^。]{0,12}?(?:違|異な|替わ|変わ|増え|減)"): "周ごとに違う値",
    re.compile(r"(?:前|直前|ひとつ前|1 つ前)の" + ROUND + r"(?:の|と|で|から)"): "前の周の値",
    re.compile(r"\d+\s*" + ROUND + r"目(?:は|に|と)[^。]{0,40}?\d+\s*" + ROUND + r"目"): "周ごとに違う値",
    re.compile(r"同じ[^。、]{0,12}続け"): "前の周の値と同じこと",
    re.compile(r"\$LOOP_PREV"): "前の周の値",
}

# (筋書き, 行) -> 訳。行は注記の行番号か "resolved-text-contains:<節>"
ALLOWED = {
    ("workflows/plan-review/fixtures/stalled.stubs.yaml", 1):
        "stalled: true は返す節 review の stub の値で、筋書きは前の往復と比べていない（前の往復の review は渡らない）。"
        "注記を「stalled を返した後の姿」に直す。区分 P。区分の issue で外す",
}


def claims(root: pathlib.Path) -> dict[tuple[str, object], list[str]]:
    """筋書きごとに、周ごとの値を確かめたと言う所 (筋書き, 行) -> 当たった字"""
    found: dict[tuple[str, object], list[str]] = {}
    for path in sorted((root / "workflows").glob("*/fixtures/*.yaml")):
        name = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        said = [(number, line) for number, line in enumerate(text.splitlines(), 1) if line.lstrip().startswith("#")]
        fixture = (yaml.safe_load(text) or {}).get("fixture") or {}
        said += [(f"resolved-text-contains:{node}", str(value))
                 for node, value in (fixture.get("resolved-text-contains") or {}).items()]
        for where, line in said:
            hits = [hit.group(0) for pattern in CLAIMS for hit in pattern.finditer(line)]
            if hits:
                found[(name, where)] = hits
    return found


class FixtureClaimsCase(unittest.TestCase):
    def test_fixtures_do_not_claim_per_round_values(self):
        found = claims(ROOT)
        self.assertEqual({row: hits for row, hits in found.items() if row not in ALLOWED}, {},
                         "筋書きが確かめられない周ごとの値を言う（dry-run は前の周の出力を渡さない）")
        self.assertEqual(sorted(ALLOWED.keys() - found.keys()), [], "表の行が今の木に当たらない")

    def test_every_allowed_row_has_a_reason(self):
        for row, reason in ALLOWED.items():
            with self.subTest(row=row):
                self.assertTrue(reason.strip())

    def test_claims_are_red_and_counts_are_not(self):
        """周ごとに違う・前の周の理由・1 周目と 2 周目の違い・$LOOP_PREV を拾い、同じ値の周の数と 1 つの周の値は拾わない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "workflows" / "blk" / "fixtures").mkdir(parents=True)
            (root / "workflows" / "blk" / "fixtures" / "a.stubs.yaml").write_text("\n".join([
                "# 拒みの理由が周ごとに違うことを見る",
                "# 2 周目の役は前の周の理由を読む",
                "# 1 周目は空、2 周目は受け付けの reason",
                "# 受け付けが 3 回とも拒んだ後の姿",
                "# 3 周目の値（round: 3）。1 往復目に block の穴が在る",
                "# 前の段が全部落ちた",
                "fixture:",
                "  resolved-text-contains: {role: \"$LOOP_PREV.accept.output.reason\", other: \"3 往復で決着しなかった\"}",
                "accept: {reason: \"# 周ごとに違う は値の中なので注記でない\"}",
            ]) + "\n", encoding="utf-8")
            self.assertEqual(claims(root), {
                ("workflows/blk/fixtures/a.stubs.yaml", 1): ["周ごとに違"],
                ("workflows/blk/fixtures/a.stubs.yaml", 2): ["前の周の"],
                ("workflows/blk/fixtures/a.stubs.yaml", 3): ["1 周目は空、2 周目"],
                ("workflows/blk/fixtures/a.stubs.yaml", "resolved-text-contains:role"): ["$LOOP_PREV"],
            })


if __name__ == "__main__":
    unittest.main()
