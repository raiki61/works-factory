"""仕様駆動の道の block（workflows/spec-driven/。docs/design/spec-driven.md の 2.3・2.6・6.4）。

script（pick → intake か check → finish）を子のプロセスで回す。対象の作業ツリーは一時の git の木で、表と設計書をそこに置く。
起動の殻が審査の記録を照らした結果のファイルは、試験が一時のフォルダに置いて環境変数で渡す（殻を通した run と同じ道。照らしそのものは
tests/bin/test_spec_reviews.py）。
"""
import hashlib
import json
import pathlib
import subprocess
import sys
import unittest

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = "spec-driven"
files = kit.load(BLOCK, "files")
import spectable  # noqa: E402  lib/

DESIGN = """# 設計書: cache

- 何の話か: キャッシュの置き場を利用者の設定に従わせる。
- 決めたこと: 環境変数を 1 つ読む。

## 背景

今はホームの直下に置く。

## TDD で直す所

- 置き場を決める関数
"""
TABLE = {"design": "docs/cache.md", "purpose": "キャッシュが利用者の思う所に置かれる",
         "acceptance": [{"key": "a1", "given": "XDG_CACHE_HOME が在る", "when": "ツールを起こす", "then": "その下に置く"}],
         "test_cmd": "", "out_of_scope": [{"glob": "docs/**", "why": "文書は直さない"}],
         "reviews": [{"part": p, "run": f"run-{n}", "findings": []} for n, p in enumerate(spectable.PARTS)]}


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.r = kit.Run(self, BLOCK)
        (self.r.repo / "docs").mkdir()
        (self.r.repo / "docs" / "cache.md").write_text(DESIGN, encoding="utf-8")
        (self.r.repo / "cache.py").write_text("X = 1\n", encoding="utf-8")
        git(self.r.repo, "add", "-A")
        git(self.r.repo, "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "seed")
        self.reviews_file = ""

    def put_table(self, **over) -> pathlib.Path:
        import yaml
        path = self.r.repo / "docs" / "cache.spec.yaml"
        path.write_text(yaml.safe_dump({**TABLE, **over}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def put_result(self, rows=None, **over) -> str:
        """起動の殻が書く照らしの結果（bin/_lib/specreviews.py の形）"""
        table = self.r.repo / "docs" / "cache.spec.yaml"
        doc = {"table": "docs/cache.spec.yaml", "table_sha256": sha(table), "design_sha256": sha(self.r.repo / "docs" / "cache.md"),
               "rows": rows if rows is not None else [{"part": r["part"], "run": r["run"], "ok": True, "why": []} for r in TABLE["reviews"]],
               **over}
        path = self.r.artifacts.parent / "spec-reviews.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.reviews_file = str(path)
        return self.reviews_file

    def script(self, name: str, **inputs) -> dict:
        extra = {files.REVIEWS_ENV: self.reviews_file} if self.reviews_file else {}
        done = subprocess.run([sys.executable, str(self.r.block / "scripts" / f"{name}.py")], cwd=self.r.repo,
                              env=hermetic.child_env(**self.r.environ(**inputs), **extra), capture_output=True, text=True,
                              encoding="utf-8")
        if done.returncode != 0:
            raise AssertionError(f"{name}.py が落ちた: {done.stderr}")
        return json.loads(done.stdout)

    def run_block(self, mode: str, **inputs) -> dict:
        pick = self.script("pick", mode=mode)
        ran = {}
        if pick["entry"]:
            ran["entry_run"] = json.dumps(self.script("intake", mode=mode, **inputs))
        if pick["check"]:
            ran["check_run"] = json.dumps(self.script("check", mode=mode, **inputs))
        return self.script("finish", pick=json.dumps(pick), mode=mode, **ran)

    def read(self, ptr) -> str:
        return (self.r.artifacts / ptr["path"]).read_text(encoding="utf-8")


class EntryCase(Base):
    def test_good_table_builds_the_values(self):
        self.put_table()
        self.put_result()
        got = self.run_block("entry", table="docs/cache.spec.yaml")
        self.assertEqual((got["ok"], got["stop_reason"], got["reason"]), (True, "", ""), got)
        self.assertEqual(got["origin"], "人と固めた仕様（docs/cache.spec.yaml）")
        self.assertEqual(got["spec_files"], ["docs/cache.spec.yaml", "docs/cache.md"])
        self.assertTrue(got["tdd"])
        self.assertEqual(got["out_of_scope"], TABLE["out_of_scope"])
        rows = json.loads(self.read(got["request"]))
        self.assertEqual([r["where"] for r in rows],
                         ["docs/cache.md", "docs/cache.md#背景", "docs/cache.md#TDD で直す所", "docs/cache.spec.yaml#a1"])
        purpose = json.loads(self.read(got["purpose"]))
        self.assertEqual((purpose["purpose_text"], purpose["source_files"]), (TABLE["purpose"], ["docs/cache.spec.yaml", "docs/cache.md"]))
        spec_text = self.read(got["spec"])
        self.assertTrue(spec_text.startswith(DESIGN.rstrip()))
        self.assertNotIn("reviews", spec_text)
        self.assertTrue(got["report"][0].startswith("- 仕様駆動の道の入口: 表 docs/cache.spec.yaml と設計書 docs/cache.md を確かめた"))

    def test_without_the_launcher_result_it_stops_before_any_role(self):
        """殻を通さない run（Archon の命令をそのまま打つ・筋書き）は照らした結果を持たないので、5 で止めて最後まで届く"""
        self.put_table()
        got = self.run_block("entry", table="docs/cache.spec.yaml")
        self.assertEqual((got["ok"], got["stop_reason"]), (False, files.STOP_ENTRY))
        self.assertIn(files.NO_REVIEWS, got["reason"])
        self.assertIsNone(got["request"])
        self.assertFalse((self.r.artifacts / files.REQUEST).exists())

    def test_result_of_another_version_is_refused(self):
        self.put_table()
        self.put_result()
        self.put_table(purpose="別の目的")
        got = self.run_block("entry", table="docs/cache.spec.yaml")
        self.assertFalse(got["ok"])
        self.assertIn("今の表か設計書の物でない", got["reason"])

    def test_result_rows_must_match_the_table_and_be_ok(self):
        self.put_table()
        rows = [{"part": r["part"], "run": r["run"], "ok": True, "why": []} for r in TABLE["reviews"]]
        rows[0] = {**rows[0], "ok": False, "why": ["記録の部品の名が違う"]}
        self.put_result(rows)
        got = self.run_block("entry", table="docs/cache.spec.yaml")
        self.assertIn(f"審査の記録 {spectable.PARTS[0]}（run run-0）が照らしに合わない: 記録の部品の名が違う", got["reason"])
        self.put_result(rows[1:])
        self.assertIn("表の reviews の行と違う", self.run_block("entry", table="docs/cache.spec.yaml")["reason"])

    def test_table_problems_are_all_named(self):
        """1〜5 の欠けを全部名指す（どれか 1 つで止めず、人が 1 度で直せるように）"""
        self.put_table(acceptance=[], reviews=TABLE["reviews"][1:])
        got = self.run_block("entry", table="docs/cache.spec.yaml")
        self.assertFalse(got["ok"])
        for want in ("acceptance", spectable.PARTS[0], files.NO_REVIEWS):
            self.assertIn(want, got["reason"])
        self.assertTrue(all(line.startswith(("- 止めた", "  - ")) for line in got["report"]), got["report"])

    def test_missing_table_is_a_stop(self):
        got = self.run_block("entry", table="docs/nope.yaml")
        self.assertEqual((got["ok"], got["stop_reason"]), (False, files.STOP_ENTRY))
        self.assertIn("nope.yaml", got["reason"])
        got = self.run_block("entry")
        self.assertIn("入力 table が空", got["reason"])


class CheckCase(Base):
    def plan(self, *rows) -> str:
        path = self.r.artifacts / "plan-fields.json"
        path.write_text(json.dumps({"round": 1, "fields": list(rows)}, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def row(self, files_=({"path": "cache.py", "op": "modify"},), out_of_scope=({"glob": "docs/**", "why": "設計書は表の持ち物で計画が触らない"},), route="tdd"):
        """files_ の行は path・op（rename は from）だけを書き、ほかの必須の欄（lib:plan-item-fields.schema.json の files の行）を埋める"""
        filled = [{"responsibility": "受け持ちの物", "symbols": [], "home": {"concept": "cache", "why": "同じ考えの住処"},
                   "considered": [{"path": "other.py", "why_not": "受け持ちの違うファイル"}], **f} for f in files_]
        return {"unit_keys": ["u1"], "files": filled, "allowed_paths": ["cache.py"], "out_of_scope": list(out_of_scope), "route": route}

    def check(self, *rows, **inputs) -> dict:
        base = {"ready": "true", "plan_ok": "true", "plan": self.plan(*rows), "tdd": "true",
                "out_of_scope": json.dumps(TABLE["out_of_scope"], ensure_ascii=False)}
        return self.run_block("check", **{**base, **inputs})

    def test_matching_plan_passes(self):
        got = self.check(self.row([{"path": "cache.py", "op": "modify"}, {"path": "new.py", "op": "create"},
                                   {"path": "moved.py", "op": "rename", "from": "cache.py"}]))
        self.assertEqual((got["ok"], got["mismatches"]), (True, []), got)

    def test_file_rows_against_the_tree(self):
        got = self.check(self.row([{"path": "gone.py", "op": "modify"}, {"path": "cache.py", "op": "create"},
                                   {"path": "x.py", "op": "rename", "from": "nope.py"}, {"path": "gone.py", "op": "delete"}]))
        self.assertEqual((got["ok"], got["stop_reason"]), (False, files.STOP_MISMATCH))
        self.assertEqual(len(got["mismatches"]), 4, got["mismatches"])
        self.assertIn("gone.py は modify だが", got["mismatches"][0])

    def test_table_out_of_scope_must_be_in_the_plan(self):
        got = self.check(self.row(out_of_scope=()))
        self.assertEqual(got["mismatches"], ["表の触らない物 docs/** が、計画の行のどれの out_of_scope にも無い"])

    def test_tdd_marks(self):
        self.assertIn("route が tdd の計画の行が 1 つも無い", self.check(self.row(route="direct"))["reason"])
        self.assertIn("計画の行 1 の route が tdd", self.check(self.row(), tdd="false")["reason"])

    def test_out_of_purpose_rows_stop(self):
        oop = self.r.artifacts / "out-of-purpose.json"
        oop.write_text(json.dumps({"rounds": {"1": [{"source": "依頼の行", "where": "docs/cache.md#9",
                                                             "why_outside": "目的に無い入口の行を設計書が書いている"}]}},
                                  ensure_ascii=False), encoding="utf-8")
        got = self.check(self.row(), out_of_purpose=str(oop))
        self.assertEqual(got["mismatches"], ["判定の役が目的の外とした行: docs/cache.md#9——目的に無い入口の行を設計書が書いている（設計書が表の目的と受け入れの条件の外を書いている）"])

    def test_no_units_or_no_plan_stop(self):
        self.assertIn("直す単位を返さなかった", self.check(ready="false")["reason"])
        self.assertIn("計画の部品が落ちた", self.check(plan_ok="", plan="")["reason"])


class PickCase(Base):
    def test_unknown_mode_is_a_stop_not_a_fall(self):
        got = self.run_block("other")
        self.assertEqual((got["ok"], got["stop_reason"]), (False, files.STOP_ENTRY))
        self.assertIn("mode", got["reason"])


if __name__ == "__main__":
    unittest.main()
