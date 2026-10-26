"""輪の状態のファイルの名は src/tdd.py の中だけの名（docs/plans/2026-10-24-fix-weapons.md の 11.6 の E1 の縛る試験の 3）:
workflows/fix/ の src/・scripts/ のうち、輪の中の部品（src/tdd.py・scripts/tdd_prep.py・scripts/tdd_step.py）の外は、輪の状態のファイルの名
（"state.json" の字と TDD_STATE_FILE・tdd.STATE の名）を名指さない。輪の外が輪の結果を読む口は輪の記録 record.json（files.RECORD_FILE）で、
route.json など別の置き場の名とは取り違えない（照らすのは上の名だけ）。

輪は修正の block の中に残り（輪を block に出す E2 は取り止めた。#886）、block の形の検査は輪の中と外を分けないので、この試験は残す"""
import pathlib
import re
import unittest

FIX = pathlib.Path(__file__).resolve().parents[3] / "workflows" / "fix"
INSIDE = {FIX / "src" / "tdd.py", FIX / "scripts" / "tdd_prep.py", FIX / "scripts" / "tdd_step.py"}
# 輪の状態のファイルの名を名指す書き方: ファイル名の字・files の定数・tdd.py の中の名（別名 tddloop・common を含む）・名の取り込み
STATE_NAME = re.compile(r"state\.json|TDD_STATE_FILE|\b(?:tdd|tddloop|common)\.STATE\b|\bfrom\s+(?:src\.)?(?:tdd|common)\s+import\b[^\n]*\bSTATE\b")


class StateNameStaysInsideTheLoopCase(unittest.TestCase):
    def sources(self):
        got = [p for d in ("src", "scripts") for p in sorted((FIX / d).rglob("*.py")) if "__pycache__" not in p.parts]
        self.assertTrue(got)
        return got

    def test_the_loop_parts_are_where_the_name_lives(self):
        """照らす先が空振りしない: 輪の中の部品は名を持つ（持たなければ名の読み方が変わっている）"""
        self.assertTrue(all(p.is_file() for p in INSIDE))
        self.assertTrue(STATE_NAME.search((FIX / "src" / "tdd.py").read_text(encoding="utf-8")))

    def test_nothing_outside_the_loop_names_the_state_file(self):
        hits = [f"{p.relative_to(FIX)}:{n}: {line.strip()[:80]}" for p in self.sources() if p not in INSIDE
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if STATE_NAME.search(line)]
        self.assertEqual(hits, [], "輪の状態のファイルの名は src/tdd.py の中だけ（輪の外は record.json を読む）")

    def test_the_pattern_does_not_mix_up_other_places(self):
        """route.json など別の置き場の名と、輪の記録・要約の名は名指しに数えない"""
        for ok in ('ROUTE_FILE = "route.json"', 'RECORD_FILE = "record.json"', "common.RECORD", "consult.STATE", "base.json"):
            self.assertFalse(STATE_NAME.search(ok), ok)
        for bad in ('x / "state.json"', "fixnames.TDD_STATE_FILE", "tdd.STATE", "tddloop.STATE", "common.STATE", "from src.tdd import STATE"):
            self.assertTrue(STATE_NAME.search(bad), bad)
