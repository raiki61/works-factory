"""事前審査の受け付け（docs/design/plan-review.md の 9.1〜9.3。src/take.py・scripts/review_accept.py）を、script を子のプロセスで回して
確かめる。始めの記録の無い使い捨ての run directory と git のリポジトリ（tests/e2e/target-seed/ を写した物）で、port の値だけを渡し、
intake → review_prep → 台本の返答 → review_accept → finish と回す。

写した元は tests/workflows/test_plan_review.py の ReviewAcceptCase・ConvergeCase・ReplanCase・ResultCase・PortedMaterialCase と、
lib/tests/test_boardview.py・lib/tests/test_blk_plan.py の受け付けの場面（試験ごとの docstring に元の名を書く）。往復の記録に足す所は
line へ移ったので、2 往復目は pass.json を converge.add_pass で足した記録を port prior に渡して回す（Flow.carry。line の使い方の見本）。

Flow と組み立ての助け（frow・item・fields・face・review・answer・synergy・summary）は test_tree.py と test_gate.py も使う。
"""
import copy
import json
import pathlib
import shutil
import unittest

from tests.bin.gitkit import committed_copy
from tests.blocks import kit

BLOCK = "plan-review"
SEED = kit.ROOT / "tests" / "e2e" / "target-seed"
UNIT_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
UNIT_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
PURPOSE_MARK = "PURPOSE-MARK-7731"
FRAMING_MARK = "FRAMING-MARK-2208"
ONE_SHOT_MARK = "ONESHOT-MARK-5150"
RIPPLE_MARK = "RIPPLE-MARK-9902"
PLAN_MARK = "PLAN-MARK-6060"
CHECKED = "項目の案を stats.py と test_stats.py で読み、呼び出し元と試験の期待を確かめた"
NO_EFFECT = "上限の枝の外の値か、直した後の値だけを断言していて期待は変わらない"
SUMMARY_REASON = "項目ごとの下請けの答えのファイルを受け、項目ごとの判定をまとめた"
DESIGN_TEXT = "上限は入口 1 箇所で掛け、各所では掛け直さない。平均は定義どおりに割る"
DESIGN_OK = {"question_stands": True, "reason": "問いは立っている", "design": DESIGN_TEXT,
             "elements": [{"id": "D1", "adds": ["上限の入口"], "removes": []}]}
PRECEDENTS = [{"key": UNIT_MEAN, "source": "https://docs.python.org/3/library/statistics.html#statistics.mean",
               "verdict": "adopt", "reason": "空の列の平均の扱いを公式に合わせる", "problem": "空の列の平均の扱い"},
              {"key": UNIT_CLAMP, "source": "https://numpy.org/doc/stable/reference/generated/numpy.clip.html",
               "verdict": "adapt", "reason": "上限を超えた値の扱いを合わせる", "problem": "上限を超えた値の扱い"}]
RIPPLE = {"items": [{"item": 1, "unit_keys": [UNIT_MEAN], "names": [], "uncovered": []},
                    {"item": 2, "unit_keys": [UNIT_CLAMP],
                     "names": [{"name": "clamp", "files": 2, "code": ["stats.py:12"],
                                "tests": ["test_stats.py::TestStats::test_clamp_above_range"]}],
                     "uncovered": [{"id": "h1", "kind": "test", "at": "test_stats.py::TestStats::test_clamp_above_range",
                                    "name": "clamp"}]}],
          "overlaps": [{"at": "stats.py", "items": [1, 2]}]}
ROW_TEXT = "式と戻り値を 1 か所ずつ直すだけで足りる"
STUCK_NOTE = "{key} を項目 1 の修正の中で直す範囲で通す"
# 較正の 2 件で役が挙げた穴の形（#427）: 対象のテストの docstring を持ち主の方針と読んだ
SEED_DOCSTRING = "tests/calibration/seed/test_stats.py:1"


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def frow(path, *adds, op="modify", removes=(), **extra) -> dict:
    """修正案の項目の files の 1 行（adds は足す symbol の名、removes は消す symbol の名）。home・considered は照らしに当たらない既定"""
    gone = [{"name": n, "change": "remove", "why": "呼び手は新しい名に寄せたので要らない"} for n in removes]
    return {"path": path, "op": op, "responsibility": "この行の受け持ち",
            "home": {"concept": f"{path} の考え（{'・'.join(adds) or op}）", "why": "この行の path が住処だから"},
            "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}],
            "symbols": [{"name": n, "change": "add"} for n in adds] + gone, **extra}


def item(unit, n=1, **extra) -> dict:
    """修正案の項目の行（修正案の役の返答の plan[] の 1 行。unit_keys は単位の名）"""
    return {"unit_keys": [unit], "approach": f"{PLAN_MARK} 項目 {n} の直し: {unit} を直す",
            "files": [frow("stats.py", f"helper_{n}")], "shrink_first": "要らない", "narrows": [], **extra}


def fields(unit=None, **extra) -> dict:
    """修正案の項目の works の欄（port fields の fields[] の 1 行）"""
    return {"route": "direct", "route_why": "1 行の直しで済む", "tests": [], "rewrite_tests": [], "refactor": "無い",
            "allowed_paths": ["stats.py"], "out_of_scope": [], "structure": [], **extra}


def face(key, unit=UNIT_MEAN, kind="contract_drift", severity="block", reach="breaks_fix", **extra) -> dict:
    """事前審査の穴の行（unit_keys は単位の名か no の整数）"""
    return {"key": key, "unit_keys": [unit], "kind": kind, "where": "stats.py mean",
            "why": f"{key} の穴になる筋道を 20 字以上で書いた行", "severity": severity, "reach": reach, **extra}


def review(*faces, **extra) -> dict:
    out = {"faces": list(faces), "shrink": [], "reason": "案を全部読み、写し・入口・契約のずれを確かめた"}
    if not faces:
        out["faces_none"] = "写し・入口・契約のずれ・死んだ道・範囲の膨張・後退・方針を全部確かめて穴が無い"
    return {**out, **extra}


def uncovered(doc, n) -> list:
    for it in (doc or {}).get("items") or []:
        if it.get("item") == n:
            return list(it.get("uncovered") or [])
    return []


def answer(n, doc=RIPPLE, faces=(), resolved=(), why=NO_EFFECT, **extra) -> dict:
    """項目 n の下請けの答え（覆っていない当たりは全部 no_effect）"""
    return {"item": n, "checked": CHECKED, "faces": list(faces), "shrink": [], "resolved": list(resolved),
            "hits": [{"id": h["id"], "answer": "no_effect", "why": why} for h in uncovered(doc, n)], **extra}


def synergy(faces=()) -> dict:
    return {"why": "2 つの項目は stats.py の別の関数を直し、順番の依存も重複も無い", "faces": list(faces)}


def summary(verdicts, **extra) -> dict:
    """束ね役の返答（項目ごとの判定の要約だけ。verdicts は {項目: [block の key]}）"""
    return {"reason": SUMMARY_REASON,
            "items": [{"item": n, "verdict": "block" if keys else "clean",
                       "blocks": [{"key": k, "why": "下請けが挙げた穴"} for k in keys]} for n, keys in verdicts.items()], **extra}


MEAN_BLOCK = face("item1-mean-empty-division", UNIT_MEAN, kind="regression")
CLAMP_BLOCK = face("item2-clamp-upper-branch", UNIT_CLAMP)
STUCK_REC = {"answer": "continue", "note": STUCK_NOTE.format(key=MEAN_BLOCK["key"]), "why": "穴は案の項目 1 の直しで閉じられる"}
SEED_DOCSTRING_FACE = {"key": "seed-docstring", "unit_keys": [UNIT_MEAN], "kind": "policy", "where": f"{SEED_DOCSTRING} の docstring",
                       "why": "テストの説明文が「わざと試験しない」と言うので、試験を足す案は持ち主の方針とぶつかる",
                       "severity": "suggest", "reach": "against_policy", "decided_by": "test_stats.py:1"}
ENTRANCE_BARE = face("entrance-without-no-add", kind="entrance")
ENTRANCE_OK = face("entrance-with-no-add", kind="entrance", no_add="柵を足さずに 2 つの入口を 1 つの口にまとめる形")


def full_map() -> list:
    """案→設計の行（項目 1・2 の足す助け手を 1 行ずつ）。要素 D1 は項目 1 の助け手が受け、項目 2 の助け手は設計に対が無い"""
    return [{"item": n, "path": "stats.py", "symbol": f"helper_{n}", "design_ref": "D1" if n == 1 else None,
             "design_quote": None, "why": "設計に対の無い助け手の名だけを足す"} for n in (1, 2)]


def map_row(item_, path, symbol, ref=None, why="設計に対の無い助け手の名だけを足す") -> dict:
    return {"item": item_, "path": path, "symbol": symbol, "design_ref": ref, "design_quote": None, "why": why}


class Flow:
    """1 つの run directory（place は ARTIFACTS_DIR）と対象のリポジトリ。port の値を組み、block の script を子のプロセスで回す。
    往復の記録は line の代わりに試験が持つ（carry）"""

    def __init__(self, case):
        self.run = kit.Run(case, BLOCK)
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, SEED)
        self.place = self.run.artifacts
        self.tmp = self.place.parent
        self.repo = self.run.repo
        self.inputs: dict = {}
        self.prior: dict | None = None
        self.units = [{"key": UNIT_MEAN, "label": "block", "reason": "分母が 1 少ない"},
                      {"key": UNIT_CLAMP, "label": "block", "reason": "上限で lo を返す"}]
        self.judgment()
        self.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)])
        self.ripple({"items": [], "overlaps": [], "note": RIPPLE_MARK})
        self.inputs.update(purpose=f"{PURPOSE_MARK} 統計の関数が正しい値を返す", tree="off")

    # ---- 入力
    def put(self, name: str, doc, raw: bool = False) -> str:
        """port に渡すファイルを run directory の外に書き、そのパスを返す"""
        path = self.tmp / "inputs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if raw else dump(doc), encoding="utf-8")
        return str(path)

    def judgment(self, questions=(), precedents=(), **extra):
        self.inputs["judgment"] = dump({"units": self.units, "questions": list(questions),
                                        "framing": f"{FRAMING_MARK} 分母と上限の 2 つの誤り", "one_shot": f"{ONE_SHOT_MARK} 2 か所を直す",
                                        "precedents": list(precedents), **extra})

    def plan(self, rows, rnd=1, answers=None, field_rows=None):
        doc = {"plan": rows}
        if answers is not None:
            doc["block_answers"] = answers
        self.inputs["proposal"] = dump(doc)
        self.inputs["fields"] = dump({"round": rnd, "fields": field_rows or [fields(r["unit_keys"][0]) for r in rows]})

    def ripple(self, doc):
        self.inputs["ripple"] = self.put("ripple.json", doc)

    def design(self, doc=None):
        self.inputs["design"] = dump(DESIGN_OK if doc is None else doc)

    def world(self, *rows):
        self.inputs["world_rows"] = self.put("world.jsonl", "".join(dump(r) + "\n" for r in rows), raw=True)

    def structure(self, rows=(), status="ok"):
        design = self.put("design-rows.jsonl", "".join(dump(r) + "\n" for r in rows), raw=True)
        self.inputs["structure"] = self.put("structure-state.json", {"status": status, "reason": "", "design_file": design})

    def request(self, doc) -> str:
        self.inputs["request"] = self.put("request.json", doc)
        return self.inputs["request"]

    # ---- 回す
    def script(self, name: str, **inputs) -> dict:
        return self.run.script(name, **{**self.inputs, **inputs})

    def intake(self, **inputs) -> dict:
        if self.prior is not None and "prior" not in inputs:
            inputs["prior"] = self.put("prior.json", self.prior)
        got = self.script("intake", **inputs)
        if not got["due"]:
            raise AssertionError(got["reason"])
        return got

    def prep(self, prev=None) -> dict:
        return self.run.script("review_prep", **({} if prev is None else {"prev": prev}))

    def prompt(self, prev=None) -> str:
        return self.prep(prev)["prompt"]

    def accept(self, reply=None, *, fix=None, tree=None, tree_fix=None, raw=None) -> dict:
        def one(value):
            return "" if value is None else value if isinstance(value, str) else dump(value)
        return self.run.script("review_accept", reply=raw if raw is not None else one(reply), fix_reply=one(fix),
                               tree_reply=one(tree), tree_fix_reply=one(tree_fix), status_guarded="true")

    def finish(self) -> dict:
        return self.run.script("finish")

    def pass_(self, reply, **inputs) -> dict:
        """1 往復（intake → review_prep → review_accept → finish）。返りは finish の返り"""
        self.intake(**inputs)
        self.prep()
        got = self.accept(reply)
        if not got["ok"]:
            raise AssertionError(got["reason"])
        return self.finish()

    # ---- 読む
    def read(self, name: str):
        return json.loads((self.place / name).read_text(encoding="utf-8"))

    def text(self, name: str) -> str:
        return (self.place / name).read_text(encoding="utf-8")

    def intake_doc(self) -> dict:
        return self.read("intake.json")

    def view(self, review_doc=None):
        """この過程で src/view の見え方を組む（lib の照らしの関数を直に呼ぶ時）"""
        view = kit.load(BLOCK, "view")
        return view.view(self.place, self.intake_doc(), review_doc)

    def module(self, name: str):
        return kit.load(BLOCK, name)

    def carry(self) -> dict:
        """line の代わりに、受けた往復の pass.json を往復の記録に足し（converge.add_pass）、次の往復の port prior にする。返りは足した行"""
        converge = kit.load(BLOCK, "take").converge   # lib/
        got = self.read("pass.json")
        prior = copy.deepcopy(self.prior) or {"passes": [], "outcome": None}
        doc = {"round": 1, "passes": prior.get("passes") or [], "plan": got["plan"], "open": {}, "outcome": prior.get("outcome")}
        row = converge.add_pass(doc, got["review"], answers=got["answers"], resolved=got["resolved"], synergy=got["synergy"],
                                hits={int(k): v for k, v in (got["hits"] or {}).items()}, origins=got["origins"],
                                refs={int(k): v for k, v in (got["refs"] or {}).items()}, push=got["push"])
        row["files"] = dict(got["files"])
        row["rejects"] += got["rejects"]
        self.prior = {"passes": doc["passes"], "plan": doc["plan"], "outcome": doc["outcome"],
                      "precedent_checks": got["precedent_checks"]}
        return row


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.flow = Flow(self)
        self.take = kit.load(BLOCK, "take")

    def lines(self, head: str, *rows) -> str:
        return self.take._lines(head, list(rows))


class ReviewAcceptCase(FlowCase):
    """審査役 1 つの受け付け（元 tests/workflows/test_plan_review.py の ReviewAcceptCase。元は tests/test_blk_plan.py の ScriptCase・
    ConvergeReviewCase の事前審査の側）"""

    def prepped(self, **inputs):
        self.flow.intake(**inputs)
        self.flow.prep()

    def test_entrance_needs_no_add(self):
        """元 ReviewAcceptCase.test_entrance_needs_no_add（ScriptCase.test_plan_review_entrance_needs_no_add）"""
        self.prepped()
        got = self.flow.accept(review(ENTRANCE_BARE))
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(self.take.FACE_REJECT), got["reason"])
        self.assertIn("no_add", got["reason"])
        self.assertTrue(self.flow.accept(review(ENTRANCE_OK))["ok"])

    def test_malformed_recommend_rejected(self):
        """元 ReviewAcceptCase.test_malformed_recommend_rejected"""
        self.prepped()
        got = self.flow.accept(review(face("regression-recommend", kind="regression", severity="suggest",
                                           recommend={"answer": "continue", "note": "x", "why": "推す理由を書いた"})))
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(self.take.RECOMMEND_REJECT), got["reason"])

    def test_stuck_recommend_rides_on_the_pass_row(self):
        """元 ReviewAcceptCase.test_stuck_recommend_rides_on_the_pass_row: 返答の一番上の止まった時の推し（stuck_recommend）は、形が
        崩れていれば推しの形の拒みになり、整っていれば通る。review.json には欄が無く、pass.json の push に同じ推しが在る（line が往復の
        行の push に置く）。書かない往復の pass.json の push は null"""
        f = self.flow
        self.prepped()
        for bad in ({**STUCK_REC, "answer": "maybe"}, {**STUCK_REC, "note": "x"}, "通す"):
            with self.subTest(bad=bad):
                got = f.accept(review(MEAN_BLOCK, stuck_recommend=bad))
                self.assertFalse(got["ok"])
                self.assertTrue(got["reason"].startswith(self.take.RECOMMEND_REJECT), got["reason"])
                self.assertIn("stuck_recommend", got["reason"])
        self.assertFalse((f.place / "pass.json").exists(), "拒んだ往復は pass.json を書かない")
        self.assertTrue(f.accept(review(MEAN_BLOCK, stuck_recommend=STUCK_REC))["ok"])
        saved = f.read("review.json")
        self.assertNotIn("stuck_recommend", saved)
        self.assertEqual([x["key"] for x in saved["faces"]], [MEAN_BLOCK["key"]])
        self.assertEqual(f.read("pass.json")["push"], STUCK_REC)
        self.assertEqual(f.carry()["push"], STUCK_REC)
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)], rnd=2,
               answers=[{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足して直した"}])
        f.intake()
        f.prep()
        self.assertTrue(f.accept(review(resolved=[MEAN_BLOCK["key"]]))["ok"])
        self.assertIsNone(f.read("pass.json")["push"])
        self.assertNotIn("push", f.carry())

    def test_faces_none_and_units_and_keys(self):
        """元 ReviewAcceptCase.test_faces_none_and_units_and_keys: 穴も別案も挙げない返答は faces_none が要る。案に無い単位・重複の key は拒む"""
        self.prepped()
        for bad, word in (({"faces": [], "shrink": [], "reason": "写し・入口・契約のずれを全部見て穴が無いと判じた理由"}, "faces_none"),
                          (review(face("unknown-unit-key", unit="判定に無い単位の key")), "判定に無い単位の key"),
                          (review(face("duplicated-key"), face("duplicated-key")), "重複")):
            with self.subTest(word=word):
                got = self.flow.accept(bad)
                self.assertFalse(got["ok"])
                self.assertIn(word, got["reason"])

    def test_block_on_machine_field_rejected(self):
        """元 ReviewAcceptCase.test_block_on_machine_field_rejected（#549）: where で機械の足した欄 removes_tests を名指す block は拒み、
        往復を書かない。仮名・漢字に詰めて書いた名も見逃さない。同じ穴の suggest は受ける"""
        f = self.flow
        self.prepped()
        for flush in ("項目1のremoves_testsが広い", "removes_testsの13件", "修正案の項目 1 の works の removes_tests（13 件）"):
            with self.subTest(where=flush):
                got = f.accept(review(face("removes-tests-unrelated", kind="regression", where=flush)))
                self.assertFalse(got["ok"])
                self.assertIn("removes_tests", got["reason"])
        self.assertFalse((f.place / "pass.json").exists())
        where = "修正案の項目 1 の works の removes_tests（13 件）"
        self.assertTrue(f.accept(review(face("removes-tests-unrelated", kind="regression", severity="suggest", where=where)))["ok"])
        self.assertEqual(f.carry()["blocks"], [])

    def test_reply_by_number_is_named(self):
        """元 ReviewAcceptCase.test_reply_by_number_is_named: unit_keys を no の整数で指してよく、受けた返答では単位の名に戻る"""
        self.prepped()
        self.assertTrue(self.flow.accept(review(face("number-pointed-face", unit=2, kind="regression", severity="suggest")))["ok"])
        self.assertEqual(self.flow.read("review.json")["faces"][0]["unit_keys"], [UNIT_CLAMP])
        self.assertEqual(self.flow.read("pass.json")["review"]["faces"][0]["unit_keys"], [UNIT_CLAMP])

    def test_read_only_tree_changed_rejected(self):
        """元 ReviewAcceptCase.test_read_only_tree_changed_rejected: 役の前後で作業ツリーが変われば拒み、往復を書かない。commit して
        HEAD を動かしても拒む"""
        from tests.bin.gitkit import git
        f = self.flow
        self.prepped()
        (f.repo / "stats.py").write_text("# 変えた\n", encoding="utf-8")
        got = f.accept(review(MEAN_BLOCK))
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(self.take.READONLY_MOVED), got["reason"])
        git(f.repo, "commit", "-qam", "役が commit した")
        got = f.accept(review())
        self.assertFalse(got["ok"])
        self.assertIn("head", got["reason"])
        self.assertFalse((f.place / "review.json").exists())

    def test_tree_state_missing_is_named(self):
        """支度が置く作業ツリーの姿の控えが無ければ、照らさずに控えの名を言って拒む（今の planblk.NO_TREE）"""
        self.prepped()
        (self.flow.place / "review-tree-state.json").unlink()
        got = self.flow.accept(review())
        self.assertFalse(got["ok"])
        self.assertIn("review-tree-state.json", got["reason"])

    def test_unreadable_reply_goes_back_to_the_role(self):
        """元 ReviewAcceptCase.test_unreadable_reply_goes_back_to_the_role: JSON でない返答は拒み、輪は続く"""
        self.prepped()
        got = self.flow.accept(raw="{JSON でない")
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("JSON", got["reason"])

    def test_give_up_at_the_net_reject(self):
        """元 ReviewAcceptCase.test_give_up_at_the_net_reject: 網の回まで拒まれ続けたら done・give_up で輪を抜け、出口は gave_up と網に
        届いた工場の不具合の訳を返す。review.json は諦めの訳を reason に持つ空の返答で、pass.json は無い（足す: 諦めた時に pass.json が無い）"""
        f = self.flow
        rolekit = self.take.rolekit
        self.prepped()
        rows = [f.accept(review(ENTRANCE_BARE)) for _ in range(rolekit.NET_AFTER)]
        self.assertEqual([(g["ok"], g["done"], g["give_up"]) for g in rows],
                         [(False, False, False)] * (rolekit.NET_AFTER - 1) + [(False, True, True)])
        got = f.finish()
        self.assertEqual((got["ok"], got["status"], got["pass"], got["asks"]), (False, "gave_up", None, []))
        self.assertTrue(got["reason"].startswith(self.take.GIVEN_UP_FACES), got["reason"])
        self.assertIn(rolekit.NET_WHY.format(n=rolekit.NET_AFTER), got["reason"])
        saved = f.read(got["holes"]["path"])
        self.assertEqual((saved["faces"], saved["shrink"]), ([], []))
        self.assertIn("no_add", saved["reason"])
        self.assertFalse((f.place / "pass.json").exists())

    def test_pass_after_three_rejects_is_not_given_up(self):
        """元 ReviewAcceptCase.test_pass_after_three_rejects_is_not_given_up: 3 回拒まれた後に通った返答は諦めと読まない"""
        f = self.flow
        self.prepped()
        for _ in range(self.take.rolekit.GIVE_UP_AFTER):
            self.assertFalse(f.accept(review(ENTRANCE_BARE))["done"])
        self.assertTrue(f.accept(review())["ok"])
        got = f.finish()
        self.assertEqual(got["status"], "ok", got)

    def test_pass_rejects_are_only_this_pass_review_rejects(self):
        """足す: pass.json の rejects は、この往復の事前審査の拒否の行（role は p2.plan_review）だけ。前の往復の拒否は次の入口が消すので
        載らない（計画の拒否は line が足す）"""
        f = self.flow
        self.prepped()
        first = f.accept(review(ENTRANCE_BARE))
        self.assertTrue(f.accept(review())["ok"])
        rows = f.read("pass.json")["rejects"]
        self.assertEqual([(r["role"], r["reason"]) for r in rows], [(self.take.REVIEW_NODE, first["reason"])])
        f.carry()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)], rnd=2)
        f.intake()
        f.prep()
        self.assertTrue(f.accept(review())["ok"])
        self.assertEqual(f.read("pass.json")["rejects"], [])

    def test_partial_resubmit_is_merged_with_the_previous_answer(self):
        """元 ReviewAcceptCase.test_partial_resubmit_is_merged_with_the_previous_answer（#571）: 出し直しの役は拒まれた欄だけを返す。
        受け付けは前の答えの控えと合わせて全体を照らし、合わせた答えを review.json に書く"""
        f = self.flow
        self.prepped()
        self.assertFalse(f.accept(review(ENTRANCE_BARE))["ok"])
        got = f.accept(None, fix={"faces": [ENTRANCE_OK]})
        self.assertTrue(got["ok"], got["reason"])
        saved = f.read("review.json")
        self.assertEqual([x["key"] for x in saved["faces"]], ["entrance-with-no-add"])
        self.assertEqual(saved["reason"], review()["reason"])

    def test_empty_resubmit_rechecks_the_previous_answer(self):
        """元 ReviewAcceptCase.test_empty_resubmit_rechecks_the_previous_answer: 空の出し直しは前の答えのまま全体を照らし直す"""
        f = self.flow
        self.prepped()
        first = f.accept(review(ENTRANCE_BARE))
        got = f.accept(None, fix={})
        self.assertEqual((got["ok"], got["reason"]), (False, first["reason"]))

    def test_policy_face_must_name_a_recorded_row(self):
        """元 ReviewAcceptCase.test_policy_face_must_name_a_recorded_row（#427）: kind policy の穴は記録された方針の行を名指す時だけ
        受ける。対象のテストの docstring を名指す穴と、方針の文書の無い run の fences の policy_doc は拒み、記録された方針の行
        （依頼の answers の question・決着済みの論点の名指し）を名指す穴は受ける"""
        f = self.flow
        recorded = [{"source": "answer", "name": "q-mean-empty", "text": "空の列の平均は例外にする"},
                    {"source": "settled", "name": "docs/adr/0002.md", "text": "公開の口を減らさない"}]
        self.prepped(recorded=dump(recorded))
        got = f.accept(review(SEED_DOCSTRING_FACE))
        self.assertFalse(got["ok"], got)
        for want in (SEED_DOCSTRING, "記録された方針に無い"):
            self.assertIn(want, got["reason"])
        got = f.accept(review(face("fenced-without-doc", kind="regression", severity="suggest", fences=["policy_doc"])))
        self.assertFalse(got["ok"], got)
        self.assertIn("policy_doc", got["reason"])
        for named in ("q-mean-empty", "docs/adr/0002.md"):
            with self.subTest(named=named):
                self.assertTrue(f.accept(review({**SEED_DOCSTRING_FACE, "decided_by": named}))["ok"])

    def test_fences_twice_rejected(self):
        """足す: fences に同じ語を 2 つ持つ穴は拒む（役の型の uniqueItems は外した。設計書の 14 節の 12）。重ならなければ受ける"""
        f = self.flow
        self.prepped()
        twice = face("fenced-twice-row", kind="regression", severity="suggest", fences=["irreversible", "irreversible"])
        got = f.accept(review(twice))
        self.assertFalse(got["ok"], got)
        self.assertIn("faces[0]（fenced-twice-row）: fences に同じ語が 2 つ（irreversible）", got["reason"])
        self.assertTrue(f.accept(review({**twice, "fences": ["irreversible", "external_write"]}))["ok"])

    def test_marks_leave_review_json_for_the_marks_file(self):
        """決め手の欄（decided_by・fences・recommend など）は review.json と pass.json の review から外れ、出口の asks が読む
        review-marks.json に穴と同じ並びで在る"""
        f = self.flow
        self.prepped()
        mark = {"decided_by": "https://docs.python.org/3/library/statistics.html#statistics.mean の定義", "undecided_because": "",
                "world": "公式の statistics.mean は空の列で例外を投げる"}
        self.assertTrue(f.accept(review(face("regression-decided", kind="regression", severity="suggest", **mark)))["ok"])
        for doc in (f.read("review.json"), f.read("pass.json")["review"]):
            self.assertFalse(set(mark) & set(doc["faces"][0]))
        self.assertEqual(f.read(self.take.FACE_MARKS), [mark])
        got = f.finish()
        self.assertEqual([(a["node"], a["mark"], a["decided"]) for a in got["asks"]], [(self.take.REVIEW_NODE, mark, True)])


class DesignAcceptCase(FlowCase):
    """独立設計が立つ時の引用と design_map の照らし（元 ReviewAcceptCase の設計の 7 本。keep-essence の 9 の読み手の守り）"""

    KEYLESS_WHY = "設計の上限の入口は項目 1 の stats.py の modify の行が受ける"

    def designed(self, rows=None, doc=None) -> str:
        f = self.flow
        if rows is not None:
            f.plan(rows)
        f.design(doc)
        f.intake()
        return f.prompt()

    def test_design_drift_face_needs_quotes_in_both(self):
        """元 ReviewAcceptCase.test_design_drift_face_needs_quotes_in_both"""
        f = self.flow
        self.designed([item(UNIT_MEAN, 1, shrink_first=ROW_TEXT), item(UNIT_CLAMP, 2)])
        design = self.take.design
        drift = lambda why, head: face("design-drift-mean-split", why=head + why)  # noqa: E731
        cases = (("設計と継ぎ目の置き方が違う、という穴だ", "引用が無い"),
                 (f"設計の「上限は入口 2 箇所で掛け」に対し案の「{ROW_TEXT}」は食い違う", "設計の引用の字が 1 つ違う"),
                 (f"設計の「上限は入口 1 箇所で掛け」に対し案の「{ROW_TEXT[:-1]}ぬ」は食い違う", "案の行の引用の字が違う"),
                 ("設計の「上限は入口 1 箇所で掛け」を引いただけで案の行を引かない", "案の行の引用が無い"),
                 (f"案の「{ROW_TEXT}」を引いただけで設計の行を引かない", "設計の引用が無い"))
        for head in (design.DRIFT_HEAD, design.UNPAIRED_HEAD):
            for why, label in cases:
                with self.subTest(head=head, case=label):
                    got = f.accept(review(drift(why, head), design_map=full_map()))
                    self.assertFalse(got["ok"], got)
                    self.assertTrue(got["reason"].startswith(self.take.DESIGN_QUOTE_REJECT), got["reason"])
                    self.assertIn("design-drift-mean-split", got["reason"])
        good = f"設計の「上限は入口 1 箇所で掛け」に対し案の「{ROW_TEXT}」は継ぎ目の置き方が違う"
        self.assertTrue(f.accept(review(drift(good, design.UNPAIRED_HEAD), design_map=full_map()))["ok"])

    def keyless(self) -> None:
        self.designed([item(UNIT_MEAN, 1, files=[frow("stats.py"), frow("docs/notes.md")]), item(UNIT_CLAMP, 2, files=[frow("stats.py")])])

    def test_keyless_row_ref_is_not_coverage(self):
        """元 ReviewAcceptCase.test_keyless_row_ref_is_not_coverage（#747）: 鍵の無い files の行を指す案→設計の行は余りで照らさず、その
        design_ref も網羅に数えない（D1 の漏れで拒む）。設計→案の行だけの design_map は 1 回目で通る"""
        self.keyless()
        got = self.flow.accept(review(design_map=[map_row(1, "stats.py", None, "D1", self.KEYLESS_WHY)]))
        self.assertFalse(got["ok"], got)
        self.assertIn("独立設計の要素 D1", got["reason"])
        self.assertTrue(self.flow.accept(review(design_map=[map_row(None, None, None, "D1", self.KEYLESS_WHY)]))["ok"])

    def test_design_map_must_cover_every_added_name(self):
        """元 ReviewAcceptCase.test_design_map_must_cover_every_added_name: 対応表が files の足す symbol の (項目, path, symbol) を欠く・
        2 行書く・設計に無い字を引く返答は拒み、全部を 1 行ずつ持つ返答は受ける。受けた返答に design_map は残らない"""
        f = self.flow
        self.designed()
        row = {"item": 1, "path": "stats.py", "symbol": "helper_1", "design_ref": "D1", "design_quote": "上限は入口 1 箇所で掛け",
               "why": "設計の上限の掛け方に案の助け手が当たる"}
        other = full_map()[1]
        for label, bad in (("欠ける", [other]), ("設計に無い字", [{**row, "design_quote": "上限は入口 2 箇所で掛け"}, other]),
                           ("2 行", [row, row, other])):
            with self.subTest(label):
                got = f.accept(review(design_map=bad))
                self.assertFalse(got["ok"], got)
                self.assertTrue(got["reason"].startswith(self.take.DESIGN_QUOTE_REJECT), got["reason"])
                self.assertRegex(got["reason"], r"(stats.py::helper_1|design_quote)")
        self.assertTrue(f.accept(review(design_map=[row, other]))["ok"])
        self.assertNotIn("design_map", f.read("review.json"))
        self.assertEqual(f.read("pass.json")["refs"], {"1": ["D1"], "2": []})

    def test_design_quote_pasted_from_elements_or_plan_rows_names_the_source(self):
        """元 ReviewAcceptCase.test_design_quote_pasted_from_elements_or_plan_rows_names_the_source（#568）: design_quote に本文でなく要素の
        一覧の行か案の行の字を貼った答えは拒み、拒みの行がどちらを貼ったかと引き元の本文を言う。どちらにも無い字は null を勧める"""
        f = self.flow
        design = self.take.design
        self.designed([item(UNIT_MEAN, 1, shrink_first=ROW_TEXT), item(UNIT_CLAMP, 2)])
        row, other = full_map()
        cases = (("D1: 足す: 上限の入口／消す: 無し", design.QUOTE_FROM_ELEMENTS + "を貼った"),
                 ("D1: 足す: 上限の入口 ／ 消す: 無し", design.QUOTE_FROM_ELEMENTS + "を貼った"),
                 (ROW_TEXT, "修正案の行の字を貼った"),
                 ("上限は入口 2 箇所で掛け", design.QUOTE_NONE))
        for quote, want in cases:
            with self.subTest(quote=quote):
                got = f.accept(review(design_map=[{**row, "design_quote": quote}, other]))
                self.assertFalse(got["ok"], got)
                self.assertTrue(got["reason"].startswith(self.take.DESIGN_QUOTE_REJECT), got["reason"])
                self.assertIn(f"design_quote「{quote}」が独立設計の文に字のまま無い（{want}", got["reason"])
                self.assertEqual(design.QUOTE_FROM in got["reason"], want != design.QUOTE_NONE, got["reason"])
                self.assertIn(design.QUOTE_NONE, got["reason"])

    def test_design_map_keys_by_path_and_symbol_both_ways(self):
        """元 ReviewAcceptCase.test_design_map_keys_by_path_and_symbol_both_ways: 同じ名 helper を a.py と b.py に足す項目は 2 行要る。同じ
        (item, path, symbol) の 2 行は拒む。設計→案の行は受ける"""
        f = self.flow
        self.designed([item(UNIT_MEAN, 1, files=[frow("a.py", "helper"), frow("b.py", "helper")]), item(UNIT_CLAMP, 2)])
        two = full_map()[1]
        got = f.accept(review(design_map=[map_row(1, "a.py", "helper", "D1"), two]))
        self.assertFalse(got["ok"], got)
        self.assertIn("b.py::helper", got["reason"])
        self.assertNotIn("a.py::helper", got["reason"].replace("design_map の項目 1 の a.py", ""), "a.py の行は在る")
        twice = [map_row(1, "a.py", "helper", "D1"), map_row(1, "a.py", "helper"), map_row(1, "b.py", "helper"), two]
        got = f.accept(review(design_map=twice))
        self.assertFalse(got["ok"], got)
        self.assertIn("2 行ある", got["reason"])
        self.assertTrue(f.accept(review(design_map=[map_row(1, "a.py", "helper", "D1"), map_row(1, "b.py", "helper"), two]))["ok"])

    def test_design_map_covers_removals_and_every_design_element(self):
        """元 ReviewAcceptCase.test_design_map_covers_removals_and_every_design_element: change=remove の symbol の行の無い design_map・
        どの行の design_ref にも出ない要素 D2・要素に無い design_ref・op=delete の行の欠けは拒む。全部が揃えば受かる"""
        f = self.flow
        elements = [*DESIGN_OK["elements"], {"id": "D2", "adds": ["丸めの口"], "removes": []}]
        self.designed([item(UNIT_MEAN, 1, files=[frow("stats.py", "helper_1", removes=["old_mean"]),
                                                 frow("old.py", op="delete", why="呼び手は stats に寄せたので要らない")]),
                       item(UNIT_CLAMP, 2)], {**DESIGN_OK, "elements": elements})
        why = "設計に対の無い名だけを足す"
        full = [map_row(1, "stats.py", "helper_1", "D1", why), map_row(1, "stats.py", "old_mean", why=why),
                map_row(1, "old.py", None, why=why), map_row(2, "stats.py", "helper_2", why=why), map_row(None, None, None, "D2", why)]
        no_element = [x for x in full if x["item"] is not None]
        for label, bad, word in (("消す側の行が無い", [x for x in full if x["symbol"] != "old_mean"], "stats.py::old_mean"),
                                 ("要素 D2 が漏れる", no_element, "D2"),
                                 ("要素に無い design_ref", [*no_element, map_row(None, None, None, "D9", why)], "D9"),
                                 ("op=delete の行が無い", [x for x in full if x["path"] != "old.py"], "old.py")):
            with self.subTest(label):
                got = f.accept(review(design_map=bad))
                self.assertFalse(got["ok"], got)
                self.assertTrue(got["reason"].startswith(self.take.DESIGN_QUOTE_REJECT), got["reason"])
                self.assertIn(word, got["reason"])
        self.assertTrue(f.accept(review(design_map=full))["ok"])

    def test_closed_items_refs_are_counted(self):
        """元 ReviewAcceptCase.closed_items_refs_are_counted: 審査役 1 つの往復でも、独立設計の要素の網羅は閉じた項目が前の往復で受けた
        design_ref（往復の記録の refs。port prior で受ける）を合わせて数える"""
        f = self.flow
        elements = [{"id": "D1", "adds": ["上限の入口"], "removes": []}, {"id": "D2", "adds": ["丸めの口"], "removes": []}]
        self.designed(doc={**DESIGN_OK, "elements": elements})
        row = lambda n, ref: map_row(n, "stats.py", f"helper_{n}", ref)  # noqa: E731
        self.assertTrue(f.accept(review(CLAMP_BLOCK, design_map=[row(1, "D1"), row(2, "D2")]))["ok"])
        self.assertEqual([it.get("refs") for it in f.carry()["items"]], [["D1"], ["D2"]])
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach=f"{PLAN_MARK} 直した項目 2")], rnd=2,
               answers=[{"key": CLAMP_BLOCK["key"], "handled": "fixed", "how": "上限の枝を hi に直し、境の値の扱いを書いた"}])
        self.assertEqual(f.intake()["form"], "plan")
        f.prep()
        fixed = [CLAMP_BLOCK["key"]]
        got = f.accept(review(design_map=[row(2, None)], resolved=fixed))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.DESIGN_QUOTE_REJECT), got["reason"])
        self.assertIn("D2", got["reason"])
        self.assertNotIn("D1", got["reason"], "閉じた項目 1 が受けた D1 は数える")
        self.assertTrue(f.accept(review(design_map=[row(2, "D2")], resolved=fixed))["ok"])

    def test_design_quotes_not_checked_without_design(self):
        """元 ReviewAcceptCase.test_design_quotes_not_checked_without_design"""
        f = self.flow
        f.intake()
        f.prep()
        design = self.take.design
        self.assertTrue(f.accept(review(face("design-drift-no-design", why=design.DRIFT_HEAD + "設計と継ぎ目の置き方が違う、という穴だ")))["ok"])


class RereviewCase(FlowCase):
    """2 往復目の受け付け（元 ConvergeCase の 2 本）。1 往復目の pass.json を往復の記録に足して port prior で渡す"""

    ANSWERS = [{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足して確かめる形に直した"}]

    def second(self):
        f = self.flow
        f.pass_(review(MEAN_BLOCK))
        row = f.carry()
        self.assertEqual(f.prior["outcome"], "again")
        self.assertEqual([it["state"] for it in row["items"]], ["open", "closed"])
        f.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す"), item(UNIT_CLAMP, 2)], rnd=2, answers=self.ANSWERS)
        self.assertEqual(f.intake()["k"], 2)
        f.prep()

    def test_rereview_must_account_for_every_previous_block(self):
        """元 ConvergeCase.test_rereview_must_account_for_every_previous_block: 前の往復の block は resolved か同じ key で挙げ直す。
        通った往復の pass.json は resolved と修正案の役の答えを持ち、line が足すと抜け方は CLEAN"""
        f = self.flow
        self.second()
        got = f.accept(review())
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(self.take.RESOLVED_REJECT), got["reason"])
        self.assertIn(MEAN_BLOCK["key"], got["reason"])
        self.assertTrue(f.accept(review(resolved=[MEAN_BLOCK["key"]]))["ok"])
        got = f.read("pass.json")
        self.assertEqual((got["pass"], got["resolved"], got["answers"]), (2, [MEAN_BLOCK["key"]], self.ANSWERS))
        self.assertEqual(f.read("review.json")["resolved"], [MEAN_BLOCK["key"]])
        row = f.carry()
        self.assertEqual((row["outcome"], row["resolved"], row["answers"]), ("clean", [MEAN_BLOCK["key"]], self.ANSWERS))

    def test_relabel_to_peripheral_needs_a_new_why(self):
        """元 ConvergeCase.test_relabel_to_peripheral_needs_a_new_why: 前の往復で中央だった block を peripheral に付け替える時、why が
        前の往復と同じ字なら拒む。why を書き直せば受ける"""
        f = self.flow
        self.second()
        same = {**MEAN_BLOCK, "reach": "peripheral"}
        got = f.accept(review(same))
        self.assertFalse(got["ok"], got)
        self.assertIn(f"{MEAN_BLOCK['key']} を前の往復の中央", got["reason"])
        moved = {**same, "why": "直しの後は空の列の扱いが試験の材料の言い回しだけに残り、どの害の定義にも当たらない"}
        self.assertTrue(f.accept(review(moved))["ok"])


class ReplanCase(FlowCase):
    """形 replan（案の直しの事前審査。port ruling が空でない。元 ReplanCase の受け付けの側）: 往復を足さず、pass.json を書かない"""

    CONFLICT = {"id": "c-clamp", "unit_key": UNIT_CLAMP, "between": ["項目 2", "test_stats.py"],
                "why_both_cannot_hold": "上限の枝の試験が lo を期待していて案と両立しない", "kind": "plan",
                "which_is_right": "test", "ruling": {"decision": "fix_plan_item", "text": "RULING-MARK-3131 試験の側を正とせよ"}}

    def replan(self, rows=None, field_rows=None, ruled="2", design=None, first=None):
        """形 plan の往復を 1 度通して往復の記録を prior にした後、項目 2 を直した案で形 replan の支度まで回す"""
        f = self.flow
        if design is not None:
            f.design(design)
        self.assertEqual(f.pass_(first or review())["status"], "ok")
        f.carry()
        f.plan(rows or [item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach=f"{PLAN_MARK} 直した項目 2")], rnd=2, field_rows=field_rows)
        f.inputs.update(ruling=dump([ruled]), conflicts=f.put("conflicts.json", {"items": [self.CONFLICT]}))
        got = f.intake()
        self.assertEqual((got["form"], got["tree"], got["k"]), ("replan", False, 0))
        f.prep()

    def test_replan_records_no_pass(self):
        """元 OpenCase.test_replan_form_records_no_pass・ReplanCase.test_replan_is_one_shot の受け付けの側: 形 replan は通っても pass.json を
        書かず、出口の pass は null で、穴の在る返答も 1 回で返る"""
        f = self.flow
        self.replan()
        self.assertEqual(f.intake_doc()["ruled"], [2])
        self.assertTrue(f.accept(review(CLAMP_BLOCK))["ok"])
        self.assertFalse((f.place / "pass.json").exists())
        got = f.finish()
        self.assertEqual((got["status"], got["form"], got["pass"], got["blocks"]), ("ok", "replan", None, [CLAMP_BLOCK["key"]]))

    def test_replan_drift_quotes_checked_and_extra_fields_dropped(self):
        """元 ReplanCase.test_replan_drift_quotes_checked_and_extra_fields_dropped: 壁打ちと束ね役の任意の欄（resolved・items）は外して
        から照らし、独立設計が立つ時は穴の引用と design_map を直した項目の行と照らす"""
        f = self.flow
        self.replan(design=DESIGN_OK, first=review(design_map=full_map()))
        drift = face("clamp-drift-no-quote", UNIT_CLAMP, why=self.take.design.DRIFT_HEAD + "設計と継ぎ目の置き方が違う、という穴だ")
        fresh = [map_row(2, "stats.py", "helper_2")]
        got = f.accept(review(drift, design_map=fresh))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.DESIGN_QUOTE_REJECT), got["reason"])
        self.assertTrue(f.accept(review(design_map=fresh, resolved=[], items=[{"item": 2, "verdict": "clean", "blocks": []}]))["ok"])
        kept = f.read("review.json")
        for key in ("resolved", "items", "design_map"):
            self.assertNotIn(key, kept)

    def test_replan_after_review_reads_the_revised_plan(self):
        """元 ReplanCase.test_replan_after_review_reads_the_revised_plan: 設計が立った往復の後の replan は、直した案の行と照らす（直した案で
        変わった add の名の design_map を受け、前の往復の案の名だけの対応表は拒む）"""
        f = self.flow
        self.replan(rows=[item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp_entry")])], design=DESIGN_OK,
                    first=review(design_map=full_map()))
        got = f.accept(review(design_map=[map_row(2, "stats.py", "helper_2")]))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.DESIGN_QUOTE_REJECT), got["reason"])
        fresh = [{"item": 2, "path": "stats.py", "symbol": "clamp_entry", "design_ref": "D1", "design_quote": "上限は入口 1 箇所で掛け",
                  "why": "設計の入口の上限に案の名が当たる"}]
        self.assertTrue(f.accept(review(design_map=fresh))["ok"])

    def test_replan_review_gave_up_names_each_item(self):
        """元 ReplanCase.test_replan_review_gave_up_names_each_item: 網の回まで拒まれ続けたら、出口は gave_up で、裁かれた項目ごとの諦めの
        訳と裁定の文（字のまま）を gave_up と replan-gave-up.json に置く"""
        f = self.flow
        self.replan()
        for _ in range(self.take.rolekit.NET_AFTER):
            got = f.accept({"faces": "x"})
        self.assertTrue(got["give_up"], got)
        out = f.finish()
        self.assertEqual((out["ok"], out["status"]), (False, "gave_up"))
        self.assertEqual(f.read("replan-gave-up.json"), out["gave_up"])
        self.assertEqual([(x["item"], x["ruling"]) for x in out["gave_up"]], [(2, self.CONFLICT["ruling"]["text"])])
        self.assertIn("事前審査の役の返答が受け付けの網", out["gave_up"][0]["why"])

    def test_replan_without_block_passes(self):
        """元 ReplanCase.test_replan_without_block_passes"""
        f = self.flow
        self.replan()
        self.assertTrue(f.accept(review())["ok"])
        got = f.finish()
        self.assertEqual((got["status"], got["blocks"]), ("ok", []))

    def test_replan_with_unknown_ruling_is_failed(self):
        """元 ReplanCase.test_replan_with_unknown_ruling_asks_human（failed と訳の形に）・ReplanItemsCase.test_ruling_must_be_item_numbers:
        番号でない・案の外の ruling は、入口が訳つきで due: false にし、出口が failed でその訳を返す（黙って 0 項目を審査して通さない）"""
        f = self.flow
        self.assertEqual(f.pass_(review())["status"], "ok")
        f.carry()
        for bad in ("x", "0", "3"):
            with self.subTest(bad):
                got = f.script("intake", ruling=dump(["1", bad]), prior=f.put("prior.json", f.prior))
                self.assertFalse(got["due"])
                self.assertIn(repr(bad), got["reason"])
                out = f.finish()
                self.assertEqual(out["status"], "failed")
                self.assertIn(repr(bad), out["reason"])

    def test_replan_without_an_approved_plan_names_it(self):
        """元 ReplanCase.test_replan_without_an_approved_plan_names_it・ReplanItemsCase.test_no_approved_plan_stops_the_open: port prior に
        承認済みの案の行が無ければ、入口は due: false でその訳を返す"""
        got = self.flow.script("intake", ruling=dump(["1"]))
        self.assertFalse(got["due"])
        self.assertIn(self.flow.module("steps").NO_APPROVED, got["reason"])

    def test_replan_items_carry_old_new_and_rows(self):
        """元 ReplanItemsCase.test_old_new_and_rows_per_ruled_item・test_rows_match_the_plan_brief: 裁かれた項目ごとに承認済みの前の形
        （prior の行）・直した形（narrows の決め手の欄つき）・その項目を名指す fix_plan_item の申し出と裁定の行だけを並べる"""
        f = self.flow
        decided = {"decided_by": "https://docs.python.org/3/library/statistics.html#statistics.mean の定義", "undecided_because": ""}
        narrow = {"what": "空の列の mean", "why": "空の列の平均は 0 割りの例外のまま", **decided}
        rows = [{"id": "c1", "unit_key": UNIT_CLAMP, "ruling": {"decision": "fix_plan_item", "text": "範囲を広げよ"}},
                {"id": "c2", "unit_key": UNIT_CLAMP, "ruling": {"decision": "ask_human", "text": "人に聞け"}},
                {"id": "c3", "unit_key": "ほかの単位", "ruling": {"decision": "fix_plan_item", "plan_items": [2]}}]
        self.assertEqual(f.pass_(review())["status"], "ok")
        f.carry()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach="上限の枝で hi を返す", narrows=[narrow])], rnd=2,
               field_rows=[fields(), fields(allowed_paths=["stats.py", "test_stats.py"])])
        f.intake(ruling=dump(["2"]), conflicts=f.put("conflicts.json", {"items": rows}))
        got = f.intake_doc()["replan_items"]
        self.assertEqual([r["item"] for r in got], [2])
        self.assertEqual((got[0]["old"]["approach"], got[0]["new"]["approach"]), (item(UNIT_CLAMP, 2)["approach"], "上限の枝で hi を返す"))
        self.assertEqual(got[0]["old"]["allowed_paths"], ["stats.py"])
        self.assertEqual(got[0]["new"]["narrows"][0]["decided_by"], decided["decided_by"])
        self.assertEqual([c["id"] for c in got[0]["rows"]], ["c1", "c3"])
        self.assertNotIn("decided_by", f.intake_doc()["plan"]["plan"][1]["narrows"][0], "見え方の案は決め手を外した形")


class OpenAndFinishCase(FlowCase):
    """入口と出口の受け付けの側（元 ResultCase の 2 本）"""

    def test_tampered_fields_reason_reaches_the_return(self):
        """元 ResultCase.test_tampered_fields_reason_reaches_the_return・ReviewAcceptCase.test_tampered_fields_stop_the_prep: 入口の後に
        欄の控えが書き換わった往復は、支度が控えを名指して落ち、crash.json の訳を出口が failed の reason で返す"""
        f = self.flow
        f.intake()
        p = f.place / "plan-fields.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["fields"][0]["route"] = "tdd"
        p.write_text(dump(doc), encoding="utf-8")
        self.assertIn("plan-fields.json", self.flow.run.failing("review_prep"))
        self.assertEqual(f.read("crash.json")["step"], "review-prep")
        got = f.finish()
        self.assertEqual((got["status"], got["holes"], got["pass"]), ("failed", None, None))
        self.assertIn("plan-fields.json", got["reason"])

    def test_open_refuses_fields_count_apart_from_plan_rows(self):
        """元 ResultCase.test_open_refuses_fields_count_apart_from_plan_rows: 修正案の項目の数と欄の数が違えば、入口は訳つきで due: false"""
        f = self.flow
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2)], field_rows=[fields(UNIT_MEAN)])
        got = f.script("intake")
        self.assertFalse(got["due"])
        self.assertIn("修正案の項目の数 2", got["reason"])

    def test_accept_crash_is_named(self):
        """受け付けの中の誤り（入口の控えが無い）は crash.json に訳を書き、done・give_up で返す（落ちない）"""
        got = self.flow.accept(review())
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, True))
        self.assertEqual(self.flow.read("crash.json")["step"], "review-accept")


class PartsCase(FlowCase):
    """受け付けの部品を直に呼ぶ（元 lib/tests/test_boardview.py の RulesCase・UnitNameCase・Owners、lib/tests/test_blk_plan.py の
    QuoteFoldCase、tests/workflows/test_plan_review.py の PortedMaterialCase）"""

    def test_plan_review_output(self):
        """元 RulesCase.test_plan_review_output: 案に無い単位・重複の key・穴も別案も無いのに faces_none が無いを拒む（返答の全体の照らし）。
        穴の行ごとの照らし（no_add の欠け）は face_row_gaps が持つので、ここでは拒まない"""
        self.flow.intake()
        b = self.flow.view()
        view = self.flow.module("view")
        Reject = self.take.Reject
        good = {"faces": [], "shrink": [], "faces_none": "写しと入口と契約のずれを確かめて穴が無い"}
        view.plan_review_output(b, "p2.plan_review", good, None)
        row = {"key": "entrance-key", "unit_keys": [UNIT_MEAN], "kind": "entrance", "where": "stats.py", "why": "w" * 20,
               "severity": "block"}
        for bad, word in (({"faces": [], "shrink": []}, "faces_none"),
                          ({"faces": [{**row, "kind": "copy"}, {**row, "kind": "copy"}]}, "重複"),
                          ({"faces": [{**row, "kind": "copy", "unit_keys": ["判定に無い単位"]}]}, "修正案に無い")):
            with self.subTest(word=word):
                with self.assertRaises(Reject) as cm:
                    view.plan_review_output(b, "p2.plan_review", bad, None)
                self.assertIn(word, str(cm.exception))
        view.plan_review_output(b, "p2.plan_review", {"faces": [row]}, None)

    def test_face_row_gaps_bundles_policy_no_add_and_machine(self):
        """元 RulesCase.test_face_row_gaps_bundles_policy_no_add_and_machine"""
        rows = [{"source": "answer", "name": "q-mean-empty", "text": "空の列の平均は例外にする"}]
        base = {"unit_keys": [UNIT_MEAN], "where": "stats.py", "why": "w" * 20, "severity": "block"}
        faces = [{**base, "key": "ok-policy", "kind": "policy", "decided_by": "q-mean-empty"},
                 {**base, "key": "bare-policy", "kind": "policy"},
                 {**base, "key": "ok-entrance", "kind": "entrance", "no_add": "柵を足さずに 2 つの入口を 1 つの口にまとめる形"},
                 {**base, "key": "bare-entrance", "kind": "entrance", "no_add": "なし"},
                 {**base, "key": "machine", "kind": "regression", "where": "項目 1 の removes_tests が広い"}]
        got = self.take.face_row_gaps(faces, rows)
        self.assertEqual(len(got), 3, got)
        for line, head, word in zip(got, ("faces[1]（bare-policy）", "faces[3]（bare-entrance）", "faces[4]（machine）"),
                                    ("記録された方針", "no_add", "removes_tests")):
            with self.subTest(head=head):
                self.assertTrue(line.startswith(head + ":"), line)
                self.assertIn(word, line)
        self.assertEqual(self.take.face_row_gaps(faces[:1] + faces[2:3], rows), [])
        self.assertEqual(self.take.face_row_gaps([], rows), [])

    def test_unmappable_number_stays_a_number_in_every_check(self):
        """元 UnitNameCase.test_unmappable_number_stays_a_number_in_every_check（#398）: 番号 → 単位の名は unit_name の 1 つ。戻せない
        番号は番号のまま、named もその値を見る"""
        self.flow.intake()
        got = self.take.named(self.flow.view(), {"faces": [{"unit_keys": [1, 9, UNIT_MEAN]}], "shrink": [{"key": "s", "unit_keys": [9]}]})
        self.assertEqual((got["faces"][0]["unit_keys"], got["shrink"][0]["unit_keys"]), ([UNIT_MEAN, 9, UNIT_MEAN], [9]))
        self.assertEqual([self.take.unit_name([UNIT_MEAN], k) for k in (1, 9, UNIT_MEAN)], [UNIT_MEAN, 9, UNIT_MEAN])

    def test_replan_compare_strips_the_gate_fields_in_one_place(self):
        """元 Owners.test_replan_compare_strips_the_gate_fields_in_one_place（#260）: 案の直しの事実（gate.replan）は、項目から決め手の欄を
        外す読みを replan.bare の 1 か所から引き、計画の節の名は planmarks.NODE"""
        from unittest import mock
        gate = self.flow.module("gate")
        self.assertEqual(gate.PLAN_NODE, gate.planmarks.NODE)
        row = {"unit_keys": [UNIT_MEAN], "approach": "分母を直す", "narrows": [{"what": "空の列", "why": "例外のまま", "decided_by": "x"}]}
        seen = []
        with mock.patch.object(gate.replanlib, "bare", lambda it: seen.append(it) or it):
            gate.replan(self.flow.place, {"replan_items": [{"item": 1, "units": [UNIT_MEAN], "old": row, "new": row}]}, {})
        self.assertEqual(seen, [row, row])

    def test_width_and_whitespace_folded_but_one_char_difference_missing(self):
        """元 lib/tests/test_blk_plan.py の QuoteFoldCase.test_width_and_whitespace_folded_but_one_char_difference_missing: 独立設計の引用の
        照らしは両側を NFKC にし空白の並びを畳む。字の 1 つ違いは見逃さない"""
        cite = kit.load(BLOCK, "gate").cite
        source = "上限は入口 1 箇所で掛ける。\n呼び手は値を渡すだけにする"
        self.assertEqual(cite.missing_quotes("「上限は入口 1 箇所で掛ける。 呼び手は値を渡す」", source), [])
        self.assertEqual(cite.missing_quotes("「上限は入口 １ 箇所で掛ける」", source), [])
        self.assertEqual(cite.missing_quotes("「上限は入口 2 箇所で掛ける」", source), ["上限は入口 2 箇所で掛ける"])
        self.assertEqual(cite.missing_quotes("引用の無い文", source), [])
        self.assertEqual(cite.quotes("短い「ab」と「四文字以上の引用」"), ["四文字以上の引用"])

    def test_reply_out_of_the_role_format_is_rejected(self):
        """元 PortedMaterialCase.test_reply_out_of_the_role_format_is_rejected: 型の外の返答（知らない kind）は review の node の
        output_format が拒む（受け付けは型を照らし直さない）"""
        files = self.flow.module("files")
        fmt = files.node_schema("review")
        validate = kit.load(BLOCK, "tree").validate_schema
        self.assertEqual(validate(review(face("good-kind-face")), fmt), [])
        self.assertTrue(validate(review(face("bad-kind-face", kind="taste")), fmt))


if __name__ == "__main__":
    unittest.main()
