"""works-factory 自身の考えの住処の柵（地図 docs/concepts.md と表 docs/concepts.json。持ち主の決め `concept-home` と
「同じ機械の関門を CI で通す」）。

考えごとに（住処ありも散らばりも）、その考えの語の形（正規表現）が「知ってよい所」と表の exclude の外の追跡されたファイルに
何行あるかを数え、表の既知の漏れ（ファイル → 件数と理由）とちょうど揃うことを見る。件数が表より増えても・減っても・表に無い
ファイルが出ても赤（減る向きにだけ動かす）。散らばりの柵は知ってよい所が空の数の歯止め。表そのものも、HEAD と origin/main の
分かれ目の表より件数の和が増えず、考え・柵を消す・知ってよい所や exclude・bound を広げる・語の形を変える緩めも、表の loosened に
新しい理由の行が無ければ赤（NotAboveMain）。分かれ目を引けなければ見送らずに赤（CI は全履歴を取る）。
あわせて地図と表の id と状態が揃うこと・どの考えも柵を持つこと・地図に書いたパスが在ることを見る（地図が古くなるのを防ぐ一番安い同期）。
道具は lib/conceptfence.py（run の中の構造の目も同じ道具を対象の表に当てる）。元 works/tests/test_concept_fences.py。
"""
import glob
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "lib"))
import conceptfence as cf  # noqa: E402
from tests.layers.trees import tree  # noqa: E402

MD = (ROOT / "docs" / "concepts.md").read_text(encoding="utf-8")
PATH_HEADS = ("lib/", "workflows/", "bin/", "tests/", ".github/")   # 地図の行のパスの頭（このリポジトリの並べ方）


class MapAndTable(unittest.TestCase):
    """地図と表が揃う"""

    def setUp(self):
        self.table = cf.load(ROOT)

    def test_ids_and_status_agree(self):
        self.assertEqual(cf.map_ids(MD), {k: v["status"] for k, v in self.table["concepts"].items()})

    def test_every_concept_has_fence(self):
        """どの考えも柵を持つ。散らばり（住処が無い）の柵は知ってよい所が空で、今の知る場所を全部既知の漏れに置く数の歯止め"""
        for k, v in self.table["concepts"].items():
            with self.subTest(concept=k):
                self.assertTrue(v["fences"], k)
                if v["status"] == "散らばり":
                    self.assertEqual([f["allowed"] for f in v["fences"]], [[]] * len(v["fences"]), k)
                    self.assertTrue(all(f["known"] for f in v["fences"]), f"{k}: 散らばりの柵が何も数えていない（語の形が今の知る場所に当たらない）")

    def test_allowed_named_in_map(self):
        """表の allowed（柵が照らす知ってよい所）は、地図のその考えの「住処」「約束」「知ってよい所」の行に字で在る（2 か所が食い違わない）"""
        rows = {lab: cf.map_rows(MD, lab) for lab in ("住処", "約束", "知ってよい所")}
        for k, v in self.table["concepts"].items():
            words = {w.rstrip("/") for lab in rows for w in cf.CODE.findall(rows[lab].get(k, ""))}
            for f in v["fences"]:
                for a in f["allowed"]:
                    with self.subTest(concept=k, allowed=a):
                        self.assertIn(a.removesuffix("/**"), words)

    def test_map_paths_exist(self):
        paths = cf.map_paths(MD, PATH_HEADS)
        self.assertTrue(paths)
        missing = [p for p in paths if not (glob.glob(str(ROOT / p)) if "*" in p else (ROOT / p).exists())]
        self.assertEqual(missing, [])

    def test_bound_copies_name_their_binding_test(self):
        """表の形は対象の表と同じ確かめ（check_table）を通り、結んだ写し（bound）の行は、写しを源に縛る試験のファイル by が在り、
        その試験が柵の表の行を読んで縛る数と揃える"""
        cf.check_table(self.table)
        for k, v in self.table["concepts"].items():
            for f in v["fences"]:
                for b in f.get("bound") or []:
                    with self.subTest(concept=k, by=b["by"]):
                        self.assertTrue((ROOT / b["by"]).is_file(), b)
                        self.assertTrue(b["paths"] and b.get("why", "").strip(), b)

    def test_known_rows_have_reason(self):
        for k, v in self.table["concepts"].items():
            for f in v["fences"]:
                for path, (n, why) in f["known"].items():
                    self.assertGreater(n, 0, (k, path))
                    self.assertTrue(why.strip(), (k, path))


class FencesHold(unittest.TestCase):
    """本物の木: 住処の外の漏れは表の既知とちょうど揃う"""

    def test_every_fence(self):
        table = cf.load(ROOT)
        paths = cf.tracked(ROOT)
        for k, v in table["concepts"].items():
            for f in v["fences"]:
                with self.subTest(concept=k, what=f["what"]):
                    found = cf.scan(ROOT, paths, f, table["exclude"])
                    self.assertEqual(cf.verdict(found, f["known"]), [], f"{k}: {f['what']}")


    def test_handoff_fence_catches_a_copy_on_each_side(self):
        """考え handoff の柵は、計画側（lib/planfile.py）・報告側（lib/report_roles.py）・YAML 側（workflows/report/works-factory-report.yaml）に
        1 本ずつ注入した型の写しを、それぞれ漏れとして数える。住処 lib/handoff.py の宣言と、結んだ写し（YAML の本物の required の行）は数えない"""
        table = cf.load(ROOT)
        fences = table["concepts"]["handoff"]["fences"]
        bound = " " * 16 + "required: [read, kept, set_aside, open]"
        files = {
            "lib/handoff.py": 'KEYS = ("read", "kept", "set_aside", "open")\nSCHEMA = {}\n',
            "lib/planfile.py": "HANDOFF_SCHEMA = {'type': 'object'}\n",
            "lib/report_roles.py": 'HANDOFF_KEYS = ("read", "kept", "set_aside", "open")\n',
            "workflows/plan/works-factory-plan.yaml": bound.replace("open]", "open ]") + "\n",
            "workflows/report/works-factory-report.yaml": f"{bound}\n" + " " * 8 + "required: [read, kept, set_aside, open]\n",
        }
        with tree(files) as root:
            found: dict = {}
            for fence in fences:
                for path, n in cf.scan(root, sorted(files), fence, table["exclude"]).items():
                    found[path] = found.get(path, 0) + n
        self.assertEqual(found, {"lib/planfile.py": 1, "lib/report_roles.py": 1, "workflows/plan/works-factory-plan.yaml": 1,
                                 "workflows/report/works-factory-report.yaml": 1})
        self.assertEqual(table["concepts"]["handoff"]["status"], "住処あり")
        self.assertTrue(all(f["allowed"] == ["lib/handoff.py"] for f in fences))


class NotAboveMain(unittest.TestCase):
    """表そのものが増えない: 考えごとの既知の漏れは、HEAD と origin/main の分かれ目の表より件数の和が増えず、main に無いパスも
    出ない。考え・柵を消す・allowed・exclude・bound を広げる・pattern を変える緩めは、表の loosened に新しい理由の行が無ければ赤。
    main で柵を持たない考え（柵を初めて掛ける差分。分かれ目に表が無い時も）は比べない"""

    def test_known_not_above_main(self):
        fork = cf.fork_ref(ROOT)
        if fork is None:
            self.fail(f"HEAD と {cf.MAIN_REF} の分かれ目を引けない（浅い clone か ref が無い。手元では git fetch origin main。"
                      f"CI は fetch-depth: 0 で全履歴を取る）")
        main, why = cf.main_table(ROOT, fork)
        if main is None:
            self.fail(f"分かれ目 {fork} の柵の表を引けない: {why}")
        self.assertEqual(cf.growth(main, cf.load(ROOT)), [])

    def test_missing_ref_is_reported_not_raised(self):
        got, why = cf.main_table(ROOT, "refs/heads/no-such-ref-for-concept-fences")
        self.assertIsNone(got)
        self.assertTrue(why)


if __name__ == "__main__":
    unittest.main()
