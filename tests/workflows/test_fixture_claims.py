"""筋書き（pack の <ブロック>/fixtures/*.yaml。pack は tests/archon.py の WORKFLOWS）が、確かめられない周ごとの値を確かめたと言わない（落とし穴 K6）。

`archon workflow test` の筋書きは周を回すが、前の周の出力を渡さない（止めた Archon の packages/workflows/src/dry-run.ts の executeCodeNode の
`loopPrevOutput: ''`・simulateLoopGroup。stub は節ごとに 1 つで毎周同じ値）。周ごとに違う値・前の周の値は本物の run でしか見られない。
- 筋書きの注記（`#` で始まる行）と `fixture.resolved-text-contains` の字に、CLAIMS の言い回しが在れば赤
- 「3 回とも拒んだ」のように同じ値の周の数を言うのは、毎周同じ stub で正しく起きるので赤にしない
- 許す表は持たない（持ち主の決め shape-checks-only。docs/design/README.md の 7.1 の終わり）。dry-run の限りを説明する注記も、
  確かめたと読める言い回しを避けて書く
"""
import pathlib
import re
import tempfile
import unittest

import yaml

from tests.archon import WORKFLOWS

ROUND = r"(?:周|往復|回)"
# 言い回し -> その形が言うこと
CLAIMS = {
    re.compile(ROUND + r"ごとに?[^。]{0,12}?(?:違|異な|替わ|変わ|増え|減)"): "周ごとに違う値",
    re.compile(r"(?:前|直前|ひとつ前|1 つ前)の" + ROUND + r"(?:の|と|で|から)"): "前の周の値",
    re.compile(r"\d+\s*" + ROUND + r"目(?:は|に|と)[^。]{0,40}?\d+\s*" + ROUND + r"目"): "周ごとに違う値",
    re.compile(r"同じ[^。、]{0,12}続け"): "前の周の値と同じこと",
    re.compile(r"\$LOOP_PREV"): "前の周の値",
}

def claims(pack: pathlib.Path) -> dict[tuple[str, object], list[str]]:
    """筋書きごとに、周ごとの値を確かめたと言う所 (筋書き, 行) -> 当たった字。筋書きの名は pack の親からのパス"""
    found: dict[tuple[str, object], list[str]] = {}
    for path in sorted(pack.glob("*/fixtures/*.yaml")):
        name = path.relative_to(pack.parent).as_posix()
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
        self.assertTrue(list(WORKFLOWS.glob("*/fixtures/*.yaml")), "筋書きを 1 つも拾えなければ照らしは空回りする")
        self.assertEqual(claims(WORKFLOWS), {}, "筋書きが確かめられない周ごとの値を言う（dry-run は前の周の出力を渡さない）")

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
            self.assertEqual(claims(root / "workflows"), {
                ("workflows/blk/fixtures/a.stubs.yaml", 1): ["周ごとに違"],
                ("workflows/blk/fixtures/a.stubs.yaml", 2): ["前の周の"],
                ("workflows/blk/fixtures/a.stubs.yaml", 3): ["1 周目は空、2 周目"],
                ("workflows/blk/fixtures/a.stubs.yaml", "resolved-text-contains:role"): ["$LOOP_PREV"],
            })


if __name__ == "__main__":
    unittest.main()
