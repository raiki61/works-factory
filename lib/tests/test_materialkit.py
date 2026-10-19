"""素材の観点の族の共通の部品（lib/materialkit）の試験（docs/design/materials.md の 8 節）。

今の lib/tests/test_judge_accept.py の MaterialCase・DueCase が judge の置き場の上で確かめていた場面を、観点の宣言（試験の中の
小さな宣言 Viewpoint）と place のフォルダで写した。各試験の docstring に元の試験の名を書く。
"""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import materialkit as mk  # noqa: E402
import rolekit  # noqa: E402
from engine.util import Reject  # noqa: E402
from tests.bin import gitkit  # noqa: E402


class Viewpoint:
    """試験の観点の宣言（materials.md の 5.1 の名を全部持つ）。返答の material を素材 sample に写し、条件は欄で差し替える"""
    NAME = "sample"
    MATERIALS = ("sample",)
    GUARDED = False
    NA = "never"
    NA_REASON = ""
    NA_PARAGRAPH = True

    def __init__(self, **over):
        self.run, self.applies_to, self.judged, self.before_why, self.after_why = True, (True, "当たる"), False, None, None
        self.from_findings, self.fill_with, self.after_seen = False, None, []
        for key, value in over.items():
            setattr(self, key, value)

    def due(self, view, values):
        return mk.Due(True, "いつも回す") if self.run else mk.Due(False, "回さない訳")

    def fill(self, view, values, due):
        return self.fill_with if self.fill_with is not None else {"sample": mk.fill_na("当たらない", due.why)}

    def applies(self, view, values):
        if self.NA == "never":
            raise NotImplementedError
        return mk.Due(*self.applies_to)

    def judged_na(self, view, values):
        return self.judged

    def values(self, view, values):
        return {"repo": str(view.repo)}

    def when(self, view, values):
        return {"spawns": False}

    def before(self, view, values, reply, place):
        return (self.before_why, reply, True) if self.before_why else (None, reply, False)

    def after(self, view, values, reply, place):
        from engine import util
        self.after_seen.append(util.GIT_CWD)   # 後の照らしは accept.in_repo の中で呼ばれる（git が対象に向く）
        return self.after_why

    def after_accept(self, reply, place):
        assert not (pathlib.Path(place) / mk.ACCEPTED).exists(), "受けた記録は観点の控えの後に書く"
        (pathlib.Path(place) / "after-accept.json").write_text("{}", encoding="utf-8")

    def materials_of(self, reply):
        if self.from_findings:
            return {"sample": mk.material_from_findings(reply)}
        return {"sample": reply["material"]} if isinstance(reply.get("material"), dict) else {}

    def report_lines(self, doc):
        return ["  - 足した行"]


CLEAN = {"material": {"status": "clean", "checked": "README を見た"}}


def pointer(path):
    return {"pointer": pathlib.Path(path).name}   # 出力の pointer の口の代わり（形は呼び手の口が決める）


class _RepoCase(unittest.TestCase):
    """対象のリポジトリ（commit 1 つ）と観点の place を一時の場所に組む"""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = pathlib.Path(td.name).resolve()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        gitkit.git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "README.md").write_text("# 対象\n\n件数は 3 件\n", encoding="utf-8")
        (self.repo / "app.txt").write_text("一行目\n二行目\n", encoding="utf-8")
        gitkit.git(self.repo, "add", "-A")
        gitkit.git(self.repo, "commit", "-q", "-m", "seed")
        self.head = gitkit.git(self.repo, "rev-parse", "HEAD").strip()
        self.place = self.tmp / "artifacts"
        self.place.mkdir()

    def intake(self, vp=None, **values):
        vp = vp or Viewpoint()
        return mk.intake(vp, self.place, self.repo, {"base": "", "lang": "", **values})

    def take(self, reply, vp=None):
        return mk.accept(vp or Viewpoint(), self.place, self.repo, json.dumps(reply, ensure_ascii=False))

    def read(self, name):
        return json.loads((self.place / name).read_text(encoding="utf-8"))


class ViewCase(_RepoCase):
    def test_view_values(self):
        """元 DueCase.test_view_values: 見方の欄（引いた根・固めた版・差分と変更ファイルのパス・数）と、view.json との往復"""
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        (self.repo / "new.txt").write_text("新しい\n", encoding="utf-8")
        view = mk.take_view(self.place, self.repo, "")
        self.assertEqual(view.base, self.head)
        self.assertNotEqual(view.review_rev, self.head)
        self.assertEqual(view.changed_files, ("app.txt", "new.txt"))
        self.assertFalse(view.empty)
        self.assertEqual(view.commits, 0)
        self.assertEqual(pathlib.Path(view.diff_file), self.place / mk.DIFF)
        self.assertIn("新しい", (self.place / mk.DIFF).read_text(encoding="utf-8"), "未追跡の新しいファイルも入る")
        self.assertEqual((self.place / mk.CHANGED).read_text(encoding="utf-8"), "app.txt\nnew.txt\n")
        self.assertEqual(mk.View.from_dict(self.repo, self.read(mk.VIEW)), view)
        self.assertTrue(mk.take_view(self.place, self.repo, self.head).empty is False)
        gitkit.git(self.repo, "checkout", "-q", "--", "app.txt")
        (self.repo / "new.txt").unlink()
        self.assertTrue(mk.take_view(self.place, self.repo, "").empty)

    def test_commits_from_the_base(self):
        base = self.head
        for n in (1, 2):
            (self.repo / f"c{n}.txt").write_text("x\n", encoding="utf-8")
            gitkit.git(self.repo, "add", "-A")
            gitkit.git(self.repo, "commit", "-q", "-m", f"c{n}")
        view = mk.take_view(self.place, self.repo, base)
        self.assertEqual((view.base, view.commits, view.changed_files), (base, 2, ("c1.txt", "c2.txt")))

    def test_unknown_base_is_a_reject(self):
        with self.assertRaises(Reject):
            mk.take_view(self.place, self.repo, "no-such-rev")

    def test_diff_sees_files_hidden_by_index_marks(self):
        """元 MaterialCase.test_diff_sees_files_hidden_by_index_marks"""
        gitkit.git(self.repo, "update-index", "--assume-unchanged", "README.md")
        gitkit.git(self.repo, "update-index", "--skip-worktree", "app.txt")
        (self.repo / "README.md").write_text("# 対象\n\n件数は 4 件\n", encoding="utf-8")
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        view = mk.take_view(self.place, self.repo, "")
        self.assertEqual(view.changed_files, ("README.md", "app.txt"))
        patch = (self.place / mk.DIFF).read_text(encoding="utf-8")
        self.assertIn("件数は 4 件", patch)
        self.assertIn("直した", patch)
        self.assertTrue(view.stat.startswith("2 files changed"), view.stat)
        self.assertEqual(gitkit.git(self.repo, "ls-files", "-v", "README.md", "app.txt").splitlines(),
                         ["h README.md", "S app.txt"])

    def test_sparse_checkout_out_of_cone_files_are_not_changes(self):
        """元 MaterialCase.test_sparse_checkout_out_of_cone_files_are_not_changes"""
        for name in ("x/a.txt", "y/b.txt"):
            (self.repo / name).parent.mkdir()
            (self.repo / name).write_text("元\n", encoding="utf-8")
        gitkit.git(self.repo, "add", "x", "y")
        gitkit.git(self.repo, "commit", "-q", "-m", "xy")
        gitkit.git(self.repo, "sparse-checkout", "set", "y")
        (self.repo / "y" / "b.txt").write_text("直した\n", encoding="utf-8")
        view = mk.take_view(self.place, self.repo, "")
        self.assertEqual(view.changed_files, ("y/b.txt",))
        self.assertNotIn("x/a.txt", (self.place / mk.DIFF).read_text(encoding="utf-8"))
        self.assertTrue(view.stat.startswith("1 files changed"), view.stat)


class TreeCase(_RepoCase):
    def test_material_role_changed_the_tree_rejected(self):
        """元 MaterialCase.test_material_role_changed_the_tree_rejected と test_tree_change_names_the_peer_roles の代わり: ほかの役を
        名指さず、変えたのがこの役とは限らないと言う"""
        self.intake()
        (self.repo / "tmp.out").write_text("x\n", encoding="utf-8")
        got = self.take(CLEAN)
        self.assertFalse(got["ok"])
        self.assertIn(mk.READONLY_MOVED, got["reason"])
        self.assertIn("変えたのがこの役とは限らない", got["reason"])
        self.assertFalse((self.place / mk.ACCEPTED).exists())

    def test_guarded_role_does_not_compare_the_status_lines(self):
        """GUARDED の観点（実行基盤が節の前後の git status を照らす役）は porcelain の欄を比べない"""
        self.intake()
        (self.repo / "tmp.out").write_text("x\n", encoding="utf-8")
        guarded = Viewpoint(GUARDED=True)
        self.assertTrue(mk.moved_since(self.place, self.repo, ("porcelain",)))
        got = self.take(CLEAN, guarded)
        self.assertFalse(got["ok"], "未追跡のファイルは diff_sha256 にも出る")
        self.assertNotIn("git status --porcelain", got["reason"])

    def test_test_caches_count_like_any_change(self):
        """元 MaterialCase.test_test_caches_count_like_any_change"""
        for made in ("__pycache__/x.pyc", ".pytest_cache/v/cache/lastfailed"):
            with self.subTest(made):
                self.setUp()
                self.intake()
                (self.repo / made).parent.mkdir(parents=True)
                (self.repo / made).write_text("{}\n", encoding="utf-8")
                got = self.take(CLEAN)
                self.assertFalse(got["ok"], got)
                self.assertIn(mk.READONLY_MOVED, got["reason"])

    def test_tagged_environment_folder_is_still_watched(self):
        """元 MaterialCase.test_tagged_environment_folder_is_still_watched"""
        for move in ("add", "edit"):
            with self.subTest(move):
                self.setUp()
                (self.repo / ".gitignore").write_text(".venv/\n", encoding="utf-8")
                gitkit.git(self.repo, "add", ".gitignore")
                gitkit.git(self.repo, "commit", "-q", "-m", "ignore")
                site = self.repo / ".venv" / "lib" / "site-packages"
                site.mkdir(parents=True)
                (self.repo / ".venv" / "CACHEDIR.TAG").write_text("Signature: 8a477f597d28d172789f06886806bc55", encoding="utf-8")
                (site / "ok.py").write_text("x = 1\n", encoding="utf-8")
                self.intake()
                if move == "add":
                    (site / "injected.py").write_text("y = 2\n", encoding="utf-8")
                else:
                    (site / "ok.py").write_text("x = 22\n", encoding="utf-8")
                got = self.take(CLEAN)
                self.assertFalse(got["ok"], got)
                self.assertIn(mk.READONLY_MOVED, got["reason"])

    def test_route_keeps_the_first_tree_record(self):
        """元 MaterialCase.test_route_keeps_the_first_tree_record: 入口が走り直しても最初の作業ツリーの姿を残す"""
        self.intake()
        first = self.read(mk.TREE)
        (self.repo / "tmp.out").write_text("役が残した\n", encoding="utf-8")
        self.intake()
        self.assertEqual(self.read(mk.TREE), first)
        self.assertIn("tmp.out", self.take(CLEAN)["reason"])

    def test_missing_snapshot_is_a_reject(self):
        with self.assertRaises(Reject):
            mk.moved_since(self.place, self.repo, ("porcelain",))

    def test_moved_since_lives_in_accept(self):
        """作業ツリーの比べの住処は accept の 1 か所で、materialkit は呼ぶだけ（integration.md 4.4-H）"""
        import accept
        self.assertEqual(mk.TREE, accept.TREE)
        with self.assertRaises(Reject):
            accept.moved_since(self.place, self.repo, ("porcelain",))
        self.intake()
        self.assertEqual(accept.moved_since(self.place, self.repo, ("porcelain",)), [])
        (self.repo / "tmp.out").write_text("x\n", encoding="utf-8")
        got = accept.moved_since(self.place, self.repo, ("porcelain",))
        self.assertTrue(got)
        self.assertEqual(mk.moved_since(self.place, self.repo, ("porcelain",)), got)
        (self.place / accept.TREE).write_text("{", encoding="utf-8")
        with self.assertRaises(Reject):
            accept.tree_snapshot(self.place / accept.TREE)


class LocationCase(_RepoCase):
    def test_location_beyond_the_file_is_sent_back_then_marked(self):
        """元 MaterialCase.test_location_beyond_the_file_is_sent_back_then_marked（衛生の写し方の観点で）"""
        vp = Viewpoint(from_findings=True)
        self.intake(vp)
        outside = self.tmp / "outside.txt"
        outside.write_text("1 行\n", encoding="utf-8")

        def hygiene(*wheres):
            return {"findings": [{"where": w, "text": "所見の見本"} for w in wheres], "seen": "差分の全部"}
        self.assertTrue(self.take(hygiene("app.txt:1", f"{outside}:50", "infra/main.tf:184"), vp)["ok"])
        (self.place / mk.ACCEPTED).unlink()
        bad = hygiene("app.txt:1", "app.txt:99")
        for n in range(1, rolekit.GIVE_UP_AFTER):
            with self.subTest(round=n):
                got = self.take(bad, vp)
                self.assertEqual((got["ok"], got["done"]), (False, False), got)
                self.assertIn(mk.LOCATION_HEAD, got["reason"])
                self.assertIn("app.txt:99", got["reason"])
        got = self.take(bad, vp)
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        wheres = [f["where"] for f in self.read(mk.ACCEPTED)["reply"]["findings"]]
        self.assertEqual(wheres, ["app.txt:1", "app.txt:99" + mk.LOCATION_MARK])

    def test_where_rows_need_where_and_text(self):
        reply = {"settled": [{"where": "a:1", "topic": "t"}], "x": [{"where": "b:2", "text": "t"}]}
        self.assertEqual(mk.where_rows(reply), [{"where": "b:2", "text": "t"}])


class RecordCase(unittest.TestCase):
    def test_unmeasured_is_the_blocking_statuses(self):
        """測れていない状態 UNMEASURED は素材の状態の表 STATUS の阻害になる物（blocks が真）から導く 1 つだけ（integration.md 4.2-5）"""
        self.assertEqual(set(mk.UNMEASURED), {k for k, r in mk.STATUS.items() if r.blocks})
        self.assertEqual(set(mk.UNMEASURED), {"not_run", "awaiting_human"})

    def test_accept_rules(self):
        """元 MaterialCase.test_accept_rules と check_record の文（「ノード」を「観点」に、graph への宣言の求めを外した）"""
        cases = (
            ({}, "never", ["観点 v は走ったが素材 'm' が返答に無い"]),
            ({"m": {"status": "carried_over", "from_round": 1, "reason": "前"}}, "never",
             ["素材 'm'（観点 v）は今の周に走ったのに carried_over——自分で見たと主張しない値は走らなかった観点に機械が書く。今の周の判定を書け"]),
            ({"m": {"status": "not_applicable", "reason": "r"}}, "never",
             ["素材 'm'（観点 v）は走ったのに not_applicable——この観点は『条件に当たらない』を名乗れない。今の周の判定を書け"]),
            ({"m": {"status": "not_applicable", "reason": "r"}}, "cond_true",
             ["素材 'm'（観点 v）は条件が真で走ったのに not_applicable——機械が持つ事実と食い違う"]),
            ({"m": {"status": "not_applicable", "reason": "r"}}, "cond_false", []),
            ({"m": {"status": "not_applicable", "reason": "r"}}, "judged", []),
            ({"m": {"status": "odd"}}, "never", ["素材 'm' の status が不正: 'odd'"]),
            ({"m": {"status": "found", "count": "3", "detail": "d"}}, "never", ["素材 'm'（found）の 'count' は数で書け"]),
            ({"m": {"status": "clean", "checked": ""}}, "never", ["素材 'm'（clean）に 'checked' が要る（何を見たかを書け）"]),
            ({"m": {"status": "clean", "checked": ["a"]}}, "never", []),
        )
        for mats, mode, want in cases:
            with self.subTest(mats=mats, mode=mode):
                self.assertEqual(mk.check_record("v", ("m",), mats, mode), want)

    def test_only_wanted_materials_are_checked(self):
        self.assertEqual(mk.check_record("v", ("m",), {"m": CLEAN["material"], "other": {"status": "odd"}}, "never"), [])

    def test_material_from_findings(self):
        self.assertEqual(mk.material_from_findings({"findings": [{"where": "a:2", "text": "名"}], "seen": "差分"}),
                         {"status": "found", "checked": "差分", "count": 1, "detail": "a:2: 名"})
        self.assertEqual(mk.material_from_findings({"findings": [], "seen": "差分"}), {"status": "clean", "checked": "差分"})


class NaModeCase(unittest.TestCase):
    def test_na_note_for_each_kind_of_node(self):
        """元 MaterialCase.test_na_note_for_each_kind_of_node: 文は md の断片 material-na に移したので、扱いの語と理由を照らす"""
        cond = type("Cond", (Viewpoint,), {"NA": "cond"})
        cases = ((Viewpoint(), ("never", "")),
                 (cond(applies_to=(False, "手順書が無い")), ("cond_false", "手順書が無い")),
                 (cond(applies_to=(True, "手順書が 1 件")), ("cond_true", "手順書が 1 件")),
                 (cond(applies_to=(True, "いつも真"), judged=True), ("judged", "いつも真")))
        for vp, want in cases:
            with self.subTest(want=want):
                self.assertEqual(mk.na_mode(vp, None, {}), want)
                self.assertIn(want[0], mk.NA_MODES)

    def test_never_does_not_call_applies(self):
        self.assertEqual(mk.na_mode(Viewpoint(), None, {})[0], "never")   # applies は NotImplementedError を上げる


class FillCase(unittest.TestCase):
    def test_materials_of_an_entry_run_are_not_applicable(self):
        """元 MaterialCase.test_materials_of_an_entry_run_are_not_applicable の埋めの字（出どころと件数）"""
        got = mk.fill_entry("人の依頼（/p/req.json）", 2)
        self.assertEqual(got["status"], "not_applicable")
        self.assertIn("判定から入る run（出どころ: 人の依頼（/p/req.json）。この周の判定に届く人の依頼 2 件）", got["reason"])
        self.assertIn("この周の判定に届く人の依頼の件数は渡されていない", mk.fill_entry("x", None)["reason"])
        self.assertIn("依頼 0 件", mk.fill_entry("x", 0)["reason"])
        self.assertTrue(mk.normal_run("役").run)

    def test_entry_run_is_an_empty_diff_with_an_entry(self):
        """写す元 judge_accept.request_entry: 差分が空で（block が測った事実）、line が入口の出どころを渡した時だけ判定から入る run"""
        empty = mk.View(pathlib.Path("."), "b", "r", "d", (), "c", "", 0)
        diffed = mk.View(pathlib.Path("."), "b", "r", "d", ("a.py",), "c", "", 0)
        self.assertEqual(mk.not_entry_due(empty, {"entry": "e"}, "役"), mk.entry_skip("役"))
        self.assertEqual(mk.not_entry_due(empty, {"entry": ""}, "役"), mk.normal_run("役"))
        self.assertEqual(mk.not_entry_due(diffed, {"entry": "e"}, "役"), mk.normal_run("役"), "修正が入った後は入口の周でない")
        self.assertEqual(mk.fill_na("差分に手順書が無い", "0 件"), {"status": "not_applicable", "reason": "差分に手順書が無い（0 件）"})
        self.assertEqual(mk.fill_not_run("訳"), {"status": "not_run", "reason": "訳"})
        self.assertFalse(mk.entry_skip("局所レビューの役").run)
        self.assertTrue(mk.entry_skip("局所レビューの役").why.endswith("局所レビューの役を起こさない"))


class IntakeCase(_RepoCase):
    def test_due_run_writes_view_and_tree(self):
        got = self.intake()
        self.assertEqual(got, {"due": True, "reason": "いつも回す"})
        doc = self.read(mk.INTAKE)
        self.assertEqual((doc["status"], doc["fill"], doc["due"]), (None, None, {"run": True, "why": "いつも回す"}))
        self.assertEqual(doc["view"]["base"], self.head)
        self.assertTrue((self.place / mk.TREE).is_file())

    def test_skipped_fills_without_a_tree(self):
        got = self.intake(Viewpoint(run=False))
        self.assertEqual(got, {"due": False, "reason": "回さない訳"})
        doc = self.read(mk.INTAKE)
        self.assertEqual((doc["status"], doc["fill"]), ("skipped", {"sample": {"status": "not_applicable", "reason": "当たらない（回さない訳）"}}))
        self.assertFalse((self.place / mk.TREE).exists())

    def test_bad_fill_fails(self):
        """回さない時の埋めは宣言の素材を全部、status ごとの要る欄つきで持つ（写す元 _fill_one はいつも全部を埋めた）。外れは failed"""
        for fill, word in (({}, "宣言の素材"), ({"sample": {"status": "not_run"}}, "'reason' が無い"),
                           ({"sample": {"status": "odd"}}, "status が不正"), ({"sample": mk.fill_not_run("x"), "other": mk.fill_not_run("y")}, "宣言の素材")):
            with self.subTest(fill=fill):
                got = self.intake(Viewpoint(run=False, fill_with=fill))
                self.assertFalse(got["due"])
                self.assertIn(word, got["reason"])
                doc = self.read(mk.INTAKE)
                self.assertEqual(doc["status"], "failed")
                self.assertEqual(doc["fill"], {"sample": {"status": "not_run", "reason": got["reason"]}})
        self.assertEqual(mk.fill_problems(Viewpoint(), {"sample": mk.fill_na("r", "w")}), [])

    def test_snapshot_failure_fails(self):
        with mock.patch.object(mk, "snap_tree", side_effect=Reject("HEAD が引けない")):
            got = self.intake()
        self.assertEqual(got["due"], False)
        self.assertTrue(got["reason"].startswith("役を起こす前の作業ツリーの姿が取れない（HEAD が引けない）"), got)
        self.assertEqual(self.read(mk.INTAKE)["status"], "failed")

    def test_unreadable_and_untaken_fail(self):
        got = mk.intake(Viewpoint(), self.place, self.repo, {"base": ""}, "request: 読めない")
        self.assertEqual(got["due"], False)
        self.assertIn("入力が読めない（request: 読めない）", got["reason"])
        self.assertEqual(self.read(mk.INTAKE)["fill"], {"sample": {"status": "not_run", "reason": got["reason"]}})
        got = self.intake(base="no-such-rev")
        self.assertTrue(got["reason"].startswith("対象差分が取れない（"), got)
        self.assertEqual(self.read(mk.INTAKE)["status"], "failed")


class AcceptCase(_RepoCase):
    def test_reply_is_taken_and_written(self):
        self.intake()
        vp = Viewpoint()
        got = self.take(CLEAN, vp)
        self.assertEqual(vp.after_seen, [str(self.repo)], "後の照らしは in_repo の中")
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        self.assertEqual(self.read(mk.ACCEPTED), {"role": "sample", "reply": CLEAN, "materials": {"sample": CLEAN["material"]}})
        self.assertTrue((self.place / "after-accept.json").is_file())

    def test_not_an_object_and_rules_reject(self):
        self.intake()
        got = mk.accept(Viewpoint(), self.place, self.repo, "[1]")
        self.assertFalse(got["ok"])
        got = self.take({"material": {"status": "not_applicable", "reason": "r"}})
        self.assertIn("素材の欄が記録の決まりに合わない", got["reason"])
        got = self.take(CLEAN, Viewpoint(after_why="後の照らしの拒み"))
        self.assertEqual((got["ok"], got["reason"]), (False, "後の照らしの拒み"))

    def test_three_rejections_give_up_and_a_fatal_before_gives_up_at_once(self):
        self.intake()
        bad = {"material": {"status": "carried_over", "from_round": 1, "reason": "前"}}
        got = [self.take(bad)["done"] for _ in range(rolekit.GIVE_UP_AFTER)]
        self.assertEqual(got, [False, False, True])
        self.assertIn("3 回とも受け付けで拒まれた", rolekit.given_up_reason(self.place, "sample"))
        self.setUp()
        self.intake()
        got = self.take(CLEAN, Viewpoint(before_why="レンズのプラグインが無い"))
        self.assertEqual((got["ok"], got["done"], got["reason"]), (False, True, "レンズのプラグインが無い"))


class FinishCase(_RepoCase):
    def finish(self, vp=None, ptr=pointer):
        return mk.finish(vp or Viewpoint(), self.place, ptr)

    def test_six_paths(self):
        """元 MaterialCase.test_materials_mark_not_run_and_given_up の出口の道（読めない入口・failed・skipped・ran・gave_up・記録なし）"""
        got = self.finish()
        self.assertEqual((got["ok"], got["status"]), (False, "failed"))
        self.assertTrue(got["reason"].startswith(f"{mk.INTAKE} が読めない"), got)
        self.assertEqual(self.read(mk.MATERIAL)["materials"]["sample"]["status"], "not_run")

        (self.place / mk.INTAKE).write_text("{", encoding="utf-8")
        self.assertEqual(self.finish()["status"], "failed")

        mk.intake(Viewpoint(), self.place, self.repo, {"base": ""}, "base: 読めない")
        got = self.finish()
        self.assertEqual((got["status"], got["material"]), ("failed", pointer(self.place / mk.MATERIAL)))
        self.assertIn("入力が読めない", self.read(mk.MATERIAL)["materials"]["sample"]["reason"])

        self.intake(Viewpoint(run=False))
        got = self.finish()
        self.assertEqual((got["ok"], got["status"], got["reason"]), (True, "skipped", "回さない訳"))
        self.assertEqual(self.read(mk.MATERIAL)["materials"]["sample"]["status"], "not_applicable")

        self.intake()
        got = self.finish()
        self.assertEqual((got["ok"], got["status"]), (False, "failed"))
        self.assertIn("役の返答を受けた記録が無い", got["reason"])

        for _ in range(rolekit.GIVE_UP_AFTER):
            self.take({"material": {"status": "carried_over", "from_round": 1, "reason": "前"}})
        got = self.finish()
        self.assertEqual((got["ok"], got["status"]), (False, "gave_up"))
        self.assertIn("3 回とも", got["reason"])
        self.assertTrue(self.read(mk.MATERIAL)["materials"]["sample"]["reason"].endswith("——素材集めの役の返答を受けられなかった"))

        mk.jsonfile.write(self.place / mk.ACCEPTED, {"role": "sample", "reply": CLEAN, "materials": {"sample": CLEAN["material"]}})
        got = self.finish()
        self.assertEqual((got["ok"], got["status"], got["reason"]), (True, "ran", ""))
        doc = self.read(mk.MATERIAL)
        self.assertEqual(doc, {"role": "sample", "status": "ran", "reason": "", "reply": CLEAN, "materials": {"sample": CLEAN["material"]},
                               "base": self.head, "commits": 0})
        self.assertEqual(got["report"], ["素材 sample: clean（見た所: README を見た）", "  - 足した行"])

    def test_finish_does_not_fall(self):
        self.intake()

        def broken(path):
            raise OSError("書けない")
        got = self.finish(ptr=broken)
        self.assertEqual((got["ok"], got["status"], got["material"]), (False, "failed", None))
        self.assertIn("material.json が書けない（OSError: 書けない）", got["reason"])

        class Odd(Viewpoint):
            MATERIALS = property(lambda self: (_ for _ in ()).throw(RuntimeError("宣言が壊れた")))
        got = mk.finish(Odd(), self.place, pointer)
        self.assertEqual(got["status"], "failed")

    def test_report_lines(self):
        doc = {"role": "v", "status": "ran", "materials": {
            "a": {"status": "found", "count": 2, "detail": "1 行目\n2 行目"}, "b": {"status": "not_run", "reason": "訳"}}}
        self.assertEqual(mk.report_lines(doc), ["素材 a: found（2 件）: 1 行目 2 行目", "素材 b: not_run（訳）"])
        self.assertEqual(mk.report_lines({"role": "purpose-review", "status": "skipped", "reason": "回さない", "materials": {}}),
                         ["観点 purpose-review: skipped", "回さない"])


class ReadCase(_RepoCase):
    def test_read_checks_the_shape(self):
        path = self.place / mk.MATERIAL
        good = {"role": "v", "status": "ran", "reason": "", "reply": None, "materials": {}}
        mk.jsonfile.write(path, good)
        self.assertEqual(mk.read(path), good)
        for bad, word in (({**good, "role": ""}, "role"), ({**good, "status": "ok"}, "status"),
                          ({**good, "materials": []}, "materials")):
            with self.subTest(word=word):
                mk.jsonfile.write(path, bad)
                with self.assertRaisesRegex(ValueError, word):
                    mk.read(path)
        with self.assertRaisesRegex(ValueError, "無いか"):
            mk.read(self.place / "absent.json")


class AssembleCase(unittest.TestCase):
    def test_assemble_fills_fifteen(self):
        """元 MaterialCase.test_materials_mark_not_run_and_given_up の 15 欄のそろえ（受けた・回さない・諦めた素材は block が埋めて返す）"""
        docs = [{"role": "hygiene", "status": "ran", "materials": {"hygiene": {"status": "clean", "checked": "差分"}}},
                {"role": "provenance", "status": "gave_up", "materials": {"provenance": {"status": "not_run", "reason": "出典が違う"}}},
                {"role": "local-review", "status": "skipped",
                 "materials": {"local_review": mk.fill_entry("人の依頼", 1)}}]
        docs[0].update(base="abc", commits=2)
        got = mk.assemble(docs, local_checks={"status": "clean", "checked": "CI"})
        self.assertEqual(tuple(got), mk.MATERIALS)
        self.assertEqual(got["hygiene"]["status"], "clean")
        self.assertIn("出典が違う", got["provenance"]["reason"])
        self.assertEqual(got["local_review"]["status"], "not_applicable")
        self.assertEqual(got["local_checks"]["checked"], "CI")
        self.assertEqual(got["base_determination"], {"status": "found", "count": 2, "detail": "abc（始めの記録の差分の根。空なら HEAD）"})
        self.assertEqual(got["fix_closure"]["status"], "not_applicable")
        self.assertEqual(got["parallel_pr"], {"status": "not_run", "reason": "走っていない（どのノードも返していない）"})
        self.assertEqual(mk.assemble([])["base_determination"]["status"], "not_run")
        self.assertEqual(mk.assemble([{"materials": {}, "base": "abc", "commits": None}])["base_determination"]["status"], "not_run",
                         "commit の数が無ければ 0 にしない")


class PromptInputsCase(_RepoCase):
    def test_common_values_and_paragraphs(self):
        """拒否の無い回は rejection が空の字で段落 rejected が偽、never の回は na_why が空の字で na_never だけが真（指示を組む口は
        選ばれない段落の中の差し込み口も数えるので、値はいつも渡す）"""
        self.intake(lang="")
        values, when = mk.prompt_inputs(Viewpoint(), self.place, lambda raw: raw or "既定の言語")
        self.assertEqual(values, {"repo": str(self.repo), "lang": "既定の言語", "rejection": "", "na_why": ""})
        self.assertEqual(when, {"spawns": False, "rejected": False, "na_never": True, "na_cond_true": False,
                                "na_cond_false": False, "na_judged": False})
        self.take({"material": {"status": "odd"}})
        cond = type("Cond", (Viewpoint,), {"NA": "cond"})(applies_to=(False, "手順書が無い"))
        values, when = mk.prompt_inputs(cond, self.place, lambda raw: raw or "既定の言語")
        self.assertEqual(values["na_why"], "手順書が無い")
        self.assertTrue(when["na_cond_false"])
        values, when = mk.prompt_inputs(Viewpoint(), self.place, lambda raw: raw or "既定の言語")
        self.assertTrue(when["rejected"])
        self.assertIn("status が不正", values["rejection"])

    def test_viewpoint_without_the_na_paragraph_gets_no_na_values(self):
        """返答が material の欄を持たない観点（NA_PARAGRAPH が偽。md に material-na が無い）には na_why と na_* を渡さない"""
        self.intake()
        bare = type("Bare", (Viewpoint,), {"NA_PARAGRAPH": False})()
        values, when = mk.prompt_inputs(bare, self.place, str)
        self.assertNotIn("na_why", values)
        self.assertEqual(sorted(when), ["rejected", "spawns"])

    def test_clashing_names_are_refused(self):
        self.intake()
        for over in ({"values": lambda v, x: {"lang": "x"}}, {"when": lambda v, x: {"rejected": True}}):
            with self.subTest(over=sorted(over)):
                vp = Viewpoint()
                for k, f in over.items():
                    setattr(vp, k, f)
                with self.assertRaisesRegex(ValueError, "共通の名と重なる"):
                    mk.prompt_inputs(vp, self.place, str)

    def test_without_intake_fails(self):
        with self.assertRaisesRegex(ValueError, "intake.json"):
            mk.prompt_inputs(Viewpoint(), self.place, str)


class ReviewMdCase(_RepoCase):
    def test_review_md_paths(self):
        own, theirs = mk.review_md_paths(self.repo)
        self.assertEqual(own, str(LIB / "REVIEW.md"))
        self.assertEqual(theirs, "")
        (self.repo / "REVIEW.md").write_text("x", encoding="utf-8")
        self.assertEqual(mk.review_md_paths(self.repo)[1], str(self.repo / "REVIEW.md"))
        self.assertEqual(mk.review_md_paths(self.repo, self.tmp)[0], str(self.tmp / "REVIEW.md"))


if __name__ == "__main__":
    unittest.main()
