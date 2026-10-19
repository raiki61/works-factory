"""事前審査の block の材料のファイルと、指示（prompts/review.md と断片）の組み立ての試験（docs/design/plan-review.md の 2 節・3.3・15.3）。

script（intake → review_prep）を子のプロセスで回し、place に書かれた材料のファイル review-material-<n>.md と組んだ指示
review-prompt-<n>.md を読む。材料は機械が貼る行と英語の短い札だけ、指示の文は md だけが持つ。写した元の試験の名は各試験の
docstring に書く（tests/workflows/test_plan_review.py・lib/tests/test_boardview.py・lib/tests/test_blk_plan.py）。
2 往復目の往復の記録（port prior）は、line と同じく 1 往復目の place の作業の写しに converge.add_pass で往復の行を足して組む。
"""
import json
import os
import pathlib
import re
import types
import unittest
from unittest import mock

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.plan_review import values as V

material = kit.load("plan-review", "material")
files = material.files
import converge   # noqa: E402  lib/（kit.load が ports を通して sys.path に足した）
import design     # noqa: E402
import planmarks  # noqa: E402
import policy     # noqa: E402
import rolekit    # noqa: E402

PROMPTS = kit.BLOCKS / V.BLOCK / "prompts"
MEAN_BLOCK = V.face("mean-empty-list-block", V.UNIT_MEAN, where="stats.py mean の空の列",
                    why="空の列で分母が 0 になり ZeroDivisionError で落ちる筋道が案に無い")
ANSWERS = [{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足して確かめる形に直した"}]
CONFLICT = {"id": "c-clamp", "unit_key": V.UNIT_CLAMP, "between": ["項目 2", "test_stats.py"],
            "why_both_cannot_hold": "上限の枝の試験が lo を期待していて案と両立しない", "kind": "plan",
            "which_is_right": "test", "ruling": {"decision": "fix_plan_item", "text": "RULING-MARK-3131 試験の側を正とせよ"}}
POLICY_MD = "# 方針\n- POLICY-MARK-8080 公開の口を減らさない\n"


def md_texts() -> str:
    """この block の指示の md（node の md と断片）の字の全部"""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(PROMPTS.rglob("*.md")))


class _Case(unittest.TestCase):
    def setUp(self):
        self.r = V.Block(self)

    # ---------------------------------------------------------------- 回す
    def intake(self, **over) -> dict:
        got = self.r.intake(**self.r.plan_inputs(**over))
        self.assertTrue(got["due"], got)
        return got

    def prep(self, prev="") -> dict:
        return self.r.script("review_prep", prev=prev)

    def latest(self, pattern: str) -> str:
        got = sorted(self.r.artifacts.glob(pattern), key=lambda p: int(re.search(r"-(\d+)\.md$", p.name).group(1)))
        self.assertTrue(got, pattern)
        return got[-1].read_text(encoding="utf-8")

    def texts(self, **over) -> tuple[str, str]:
        """入口と支度を回し、(組んだ指示, 材料のファイル) の字"""
        self.intake(**over)
        out = self.prep()
        self.assertFalse(out["resubmit"])
        return out["prompt"], self.latest("review-material-*.md")

    def put_policy(self, text=POLICY_MD) -> str:
        return self.r.put("line/policy.md", text, raw=True)

    def reject(self, raw="{JSON でない", reason=None) -> str:
        """受け付けの拒否を 1 つ控えに積む（受け付けの script を使わずに rolekit の口で。返りは拒否の文）"""
        with self.r.env():
            if reason is None:
                got = rolekit.accept_round(self.r.artifacts, files.REVIEW_NODE, raw, lambda reply: {"ok": True, "reason": ""})
            else:
                got = rolekit.accept_parsed(self.r.artifacts, files.REVIEW_NODE, ({}, ""), lambda reply: {"ok": False, "reason": reason})
        self.assertFalse(got["ok"])
        return got["reason"]

    # ---------------------------------------------------------------- 2 往復目と案の直し
    def prior(self, first_review) -> str:
        """1 往復目の place の往復の記録の作業の写しに、受けた返答の往復の行を足した物（line が持つ記録）の pointer"""
        doc = json.loads((self.r.artifacts / files.CONVERGE).read_text(encoding="utf-8"))
        converge.add_pass(doc, first_review, answers=doc["open"].get("answers", []), resolved=[])
        doc["precedent_checks"] = {}
        return self.r.put("line/prior.json", doc)

    def second(self, items=None, first_items=None, ripple=None, **over) -> tuple[str, str]:
        """1 往復目（MEAN_BLOCK が項目 1 に残る）の後の 2 往復目の (指示, 材料)"""
        self.intake(items=first_items, **over)
        prior = self.prior(V.review(MEAN_BLOCK))
        items = items if items is not None else [V.item(V.UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す"),
                                                 V.item(V.UNIT_CLAMP, 2)]
        extra = {"ripple": self.r.put("plan/r2/ripple-x.json", ripple)} if ripple is not None else {}
        return self.texts(items=items, answers=ANSWERS, rnd=2, prior=prior, **extra, **over)

    def replan(self, **over) -> tuple[str, str]:
        """1 往復目を穴なしで通した後、項目 2 を直した案の形 replan の (指示, 材料)"""
        self.intake(**over)
        prior = self.prior(V.review())
        items = [V.item(V.UNIT_MEAN, 1), V.item(V.UNIT_CLAMP, 2, approach=f"{V.PLAN_MARK} 直した項目 2")]
        got = self.r.intake(**self.r.plan_inputs(items, rnd=2, prior=prior, ruling=json.dumps(["2"]),
                                                 conflicts=self.r.put("fix/conflicts.json", {"items": [CONFLICT]}), **over))
        self.assertEqual((got["due"], got["form"], got["tree"]), (True, "replan", False), got)
        out = self.prep()
        return out["prompt"], self.latest("review-material-*.md")


# ---------------------------------------------------------------- 材料の中身
class MaterialCase(_Case):
    def test_material_carries_the_mainline_inputs(self):
        """元 ReviewAcceptCase.test_material_carries_the_mainline_inputs: 指示は役の頭（承認ノードの決め手・狭めない案・既にある物を
        量ったか・人に回す物）と人の方針を、材料は修正案・番号つきの単位・判定者の見立て・先行例・リポジトリと読む版と観点の正本を持つ"""
        judged = self.r.put("judge/judgment-x.json", V.judgment(precedents=V.PRECEDENTS))
        prompt, mat = self.texts(judgment=judged, policy=self.put_policy())
        for want in ("Decision fields for approval-node items", "Add the form that does not narrow",
                     "Check that the plan weighed what already exists", "Raise what a person decides in a person's channel",
                     "## The person's policy", "POLICY-MARK-8080"):
            self.assertIn(want, prompt)
        for want in (V.PLAN_MARK, '"no": 1', V.FRAMING, V.ONE_SHOT, "numpy.clip", f"Repository: {self.r.repo}",
                     str(files.REVIEW_MD), material.MAT_HEADS["machine"]):
            self.assertIn(want, mat)
        self.assertNotIn("{{", prompt)
        self.assertNotIn("POLICY-MARK-8080", mat, "方針の本文は指示の断片に在り、材料には無い")

    def test_repo_line_reads_review_rev_apart_from_base(self):
        """元 ReviewAcceptCase.test_repo_line_reads_review_rev_apart_from_base（P035）: 読む版と BASE を別の値で描く"""
        head = git(self.r.repo, "rev-parse", "HEAD")
        fork = "f0" * 20
        _, mat = self.texts(review_rev=head, diff_base=fork)
        self.assertIn(f"Repository: {self.r.repo} (read version: `{head}`) BASE: `{fork}`", mat)

    def test_repository_line_names_the_run_values(self):
        """元 test_boardview の RulesCase.test_review_body_names_the_run_values: Repository の行は対象・読む版・BASE・観点の正本の
        実物。BASE が空なら読む版"""
        got = material.repository_line("/r", {"review_rev": "abc", "diff_base": "b0"})
        self.assertEqual(got, f"Repository: /r (read version: `abc`) BASE: `b0` canonical rules: {files.REVIEW_MD}")
        self.assertIn("BASE: `abc`", material.repository_line("/r", {"review_rev": "abc", "diff_base": ""}))
        self.assertIn("read version: `HEAD`", material.repository_line("/r", {}))

    def test_material_carries_plan_fields(self):
        """元 ReviewAcceptCase.test_material_carries_plan_fields: 項目ごとの works の欄を JSON で貼り、指示が見る点を頼む"""
        test = {"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均がその真ん中の値になる",
                "path": "本物の経路: stats.mean を本物のまま呼ぶ", "red_kind": "assertion", "red_why": "分母が 1 少ない"}
        rows = [{**V.fields(V.UNIT_MEAN), "route": "tdd", "tests": [test]}, V.fields(V.UNIT_CLAMP)]
        prompt, mat = self.texts(fields=self.r.put("plan/r1/plan-fields-x.json", {"round": 1, "fields": rows}))
        for want in (material.MAT_HEADS["fields"], material.LABELS["fields_item"].format(n=1), '"route": "tdd"', test["id"],
                     "本物の経路: stats.mean を本物のまま呼ぶ", '"allowed_paths"'):
            self.assertIn(want, mat)
        for want in ("## How to read the works fields", "red_kind", "rewrite_tests", "out_of_scope"):
            self.assertIn(want, prompt)

    def test_material_names_machine_permits(self):
        """元 ReviewAcceptCase.test_material_names_machine_permits（#549）: 機械が足した許しの行は役の書いた欄の JSON から外し、
        札の後の別の JSON で貼る。札の意味（役は書いていない・直せない）は指示の段落が 1 回だけ言う"""
        permit = {"id": "test_stats.py::TestStats::test_mean_of_three", "limit": "test_stats.py:8"}
        rows = [{**V.fields(V.UNIT_MEAN), planmarks.MACHINE_KEY: [permit]}, V.fields(V.UNIT_CLAMP)]
        prompt, mat = self.texts(fields=self.r.put("plan/r1/plan-fields-x.json", {"round": 1, "fields": rows}))
        label = material.LABELS["machine_rows"]
        self.assertEqual(mat.count(label), 1)
        self.assertLess(mat.index(label), mat.index(permit["id"]))
        self.assertLess(mat.index(permit["id"]), mat.index(material.LABELS["fields_item"].format(n=2)))
        self.assertIn(f"`{planmarks.MACHINE_KEY}`", prompt)
        self.assertIn("cannot change them", prompt)

    def test_material_lists_deviations(self):
        """元 ReviewAcceptCase.test_material_lists_deviations: 欄 structure の外れの訳を欄の節の前に並べ、世界の解の類には依頼の解き方
        との比べを添える。外れの訳が成り立つかを見よという頼みは指示に在る"""
        world = {**V.WORLD_ROW, "versus": {**V.WORLD_ROW["versus"], "challenge": "WC-8841 定石は分母を要素の数にする"}}
        row_dev = {"row": V.UNIT_MEAN, "deviation": "既存の関数の中で直すと呼び手の約束が変わるので外す（DEV-MARK-1）"}
        world_dev = {"world": world["class_id"], "deviation": "依頼の解き方に従い分母を変えない（https://example.org/a）"}
        rows = [{**V.fields(V.UNIT_MEAN), "structure": [row_dev, world_dev]}, V.fields(V.UNIT_CLAMP)]
        prompt, mat = self.texts(world_rows=self.r.world(world),
                                 fields=self.r.put("plan/r1/plan-fields-x.json", {"round": 1, "fields": rows}))
        at = mat.index(material.MAT_HEADS["deviations"])
        self.assertLess(at, mat.index(material.MAT_HEADS["fields"]))
        self.assertIn("DEV-MARK-1", mat[at:])
        self.assertIn("WC-8841", mat[at:])
        self.assertIn('"Deviations recorded in the plan"', prompt)

    def test_excluded_range_named(self):
        """元 ReviewAcceptCase.test_excluded_range_named: 並行 PR の外した範囲を写し、材料が写しのパスを、指示が読み方を名指す"""
        prompt, mat = self.texts(excluded=self.r.put("judge/pr-excluded.json", {"excluded": ["docs/"]}))
        self.assertIn(f"{material.MAT_HEADS['excluded']}\n\n{self.r.artifacts / files.EXCLUDED}", mat)
        self.assertIn("Ranges of parallel PRs", prompt)
        prompt, mat = self.texts()
        self.assertNotIn(material.MAT_HEADS["excluded"], mat)
        self.assertNotIn("Ranges of parallel PRs", prompt)

    def test_defaults_are_named(self):
        """元 test_boardview の OpenCase.test_defaults_are_named: 既定で読んだ入力（読めない excluded・空の structure と ripple）の訳を
        材料の頭の節に並べ、指示はそれを無いとして読めと言う"""
        prompt, mat = self.texts(excluded=self.r.put("judge/pr-excluded.json", "{壊れた", raw=True), structure="", ripple="")
        self.assertTrue(mat.startswith(material.MAT_HEADS["defaults"]), mat[:200])
        head = mat.split("\n\n## ")[0]
        self.assertIn("excluded", head)
        self.assertIn("structure", head)
        self.assertIn("ripple", head)
        self.assertIn("Read each of those inputs as absent", prompt)

    def test_open_reads_the_fix_plan_from_its_port(self):
        """元 test_boardview の OpenCase.test_open_reads_the_fix_plan_and_rejects_from_inputs の材料の半分（計画の拒否の行は line が
        持つ）: 修正案の役の返答は port proposal の先から読み、置き場の隣を名で開かない"""
        moved = self.r.put("elsewhere/reply.json", V.proposal(V.item(V.UNIT_MEAN, 1, approach="ELSEWHERE-MARK 別の所の返答"),
                                                              V.item(V.UNIT_CLAMP, 2)))
        _, mat = self.texts(proposal=moved)
        self.assertIn("ELSEWHERE-MARK 別の所の返答", mat)
        self.assertNotIn(f"{V.PLAN_MARK} 項目 1 の直し", mat)

    def test_tampered_fields_stop_the_prep(self):
        """元 ReviewAcceptCase.test_tampered_fields_stop_the_prep: place の欄の控えが凍結の印と食い違えば、支度は控えを名指して落ち、
        crash.json に訳を残す（書き換えた欄を審査に見せない）"""
        self.intake()
        p = self.r.artifacts / planmarks.FIELDS_FILE
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["fields"][0]["route"] = "tdd"
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        err = self.r.failing("review_prep", prev="")
        self.assertIn(planmarks.FIELDS_FILE, err)
        crash = json.loads((self.r.artifacts / files.CRASH).read_text(encoding="utf-8"))
        self.assertEqual(crash["step"], "review-prep")
        self.assertIn(planmarks.FIELDS_FILE, crash["why"])

    def test_units_point_by_number(self):
        """元 PortedMaterialCase.test_units_line_is_the_original_instruction_line: 材料の単位は番号 no つきの JSON。「key を写さず no の
        整数で指せ（機械が名前に戻す）」の決まりは指示の md に在る"""
        prompt, mat = self.texts()
        self.assertIn(f'{material.LABELS["units"]} [', mat)
        self.assertIn(f'"no": 2,\n  "key": "{V.UNIT_CLAMP}"', mat)
        self.assertIn("point at units by the integer `no`", prompt)
        self.assertIn("Do not copy the key", prompt)
        self.assertNotIn("key を字のまま", prompt + mat)

    def test_material_carries_policy_base_and_concept_map(self):
        """元 PortedMaterialCase.test_material_carries_policy_base_units_and_concept_map: 人の方針の節（決まりの文つき）は考えの住処の
        地図の節より前。BASE は材料の Repository の行"""
        prompt, mat = self.texts(policy=self.put_policy())
        self.assertIn("BASE: `HEAD`", mat)
        for want in ("## The person's policy", "POLICY-MARK-8080", "Do not rewrite the policy document", "## Map of where concepts live"):
            self.assertIn(want, prompt)
        self.assertLess(prompt.index("Do not rewrite the policy document"), prompt.index("## Map of where concepts live"))

    def test_material_pastes_the_port_copy(self):
        """元 PortedMaterialCase.test_material_pastes_the_frozen_copy: 貼る方針の本文は port policy の写し（line が run の頭で固めた
        版）。対象の木に在る方針の文書の今の字は貼らない"""
        (self.r.repo / "graphloops").mkdir()
        (self.r.repo / "graphloops" / "policy.md").write_text("- POLICY-B-2222 書き換えた\n", encoding="utf-8")
        prompt, _ = self.texts(policy=self.put_policy("- POLICY-A-1111 固めた版\n"))
        self.assertIn("POLICY-A-1111", prompt)
        self.assertNotIn("POLICY-B-2222", prompt)

    def test_no_policy_no_section(self):
        """元 PortedMaterialCase.test_no_policy_no_section"""
        prompt, _ = self.texts()
        self.assertNotIn("## The person's policy", prompt)
        self.assertNotIn("Do not rewrite the policy document", prompt)

    def test_policy_face_example_reaches_the_prompt(self):
        """元 PortedMaterialCase.test_policy_face_example_reaches_prompt_and_item_briefs の木にしない半分（#570）: 記録された方針の
        一覧の最初の名指しで描いた kind policy の穴の例が指示にそのまま載り、受け付けの照らし（policy.face_gaps）を通る"""
        rows = [{"source": "answer", "name": "q-mean-empty", "text": "空の列の平均は例外にする"}]
        prompt, mat = self.texts(recorded=V.dump(rows))
        want = json.dumps({"kind": "policy", "severity": "suggest", "decided_by": "q-mean-empty"}, ensure_ascii=False)
        self.assertIn(want, prompt)
        self.assertEqual(policy.face_gaps([json.loads(want)], rows), [])
        self.assertIn("named `q-mean-empty`", prompt)
        self.assertNotIn("No row can be named", prompt)
        self.assertNotIn("q-mean-empty", mat, "記録された方針の行は指示の断片に在る")

    def test_no_recorded_policy_says_none(self):
        """記録された方針の行が 1 つも名指せなければ、断片の段落 recorded_none と kind policy を挙げない段落が載る"""
        prompt, _ = self.texts()
        self.assertIn("Recorded policy: none", prompt)
        self.assertIn("No row can be named: do not raise holes of kind policy.", prompt)

    def test_policy_document_row_and_fence(self):
        """方針の文書の行が在る run では、記録された方針の行に文書の名指しと行数が載り、policy_doc の柵の段落が載る"""
        prompt, _ = self.texts(policy=self.put_policy())
        self.assertIn(f"- policy document: named `{self.r.artifacts / 'line/policy.md'}:<line>` (lines 1-2", prompt)
        self.assertIn("This run has a row of the policy document", prompt)
        self.assertIn(f"\"decided_by\": \"{self.r.artifacts / 'line/policy.md'}:1\"", prompt)

    def test_prep_passes_state_dir_cache_root(self):
        """元 PortedMaterialCase.test_prep_passes_state_dir_cache_root: 材料のライブラリの文書の節は STATE_DIR の下 works-factory/ の
        run をまたぐ控えを読む（網に出ない）"""
        import libdocs
        from lib.tests.test_libdocs import FakeBoard, ok_http
        (self.r.repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (self.r.repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        git(self.r.repo, "add", "app.py", "requirements.txt")
        git(self.r.repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "app")
        units = [{**V.UNITS[0], "reason": V.UNITS[0]["reason"] + "（app.py の requests）"}, V.UNITS[1]]
        state = self.r.artifacts.parent / "state"
        libdocs.section(FakeBoard(self.r.artifacts.parent / "earlier").work(""), self.r.repo, ["app.py"], get=ok_http(), env={},
                        shared=state / "works-factory")
        self.intake(judgment=self.r.put("judge/judgment-x.json", V.judgment(units)))
        intake = self.r.read(files.INTAKE)
        with self.r.env(), mock.patch.dict(os.environ, {"STATE_DIR": str(state), "https_proxy": "http://127.0.0.1:9",
                                                         "HTTPS_PROXY": "http://127.0.0.1:9"}):
            path, _, _ = material.write_material(self.r.artifacts, intake, self.r.repo, n=1)
        self.assertIn("ほかの run 1 本", path.read_text(encoding="utf-8"))

    def test_libdocs_cache_is_reused_across_passes(self):
        """元 test_boardview の LibDocsCase.test_cache_is_reused_across_passes: ライブラリの文書の控え（place の libdocs/）は入口が
        消さないので、同じ place の次の往復は網に出ずにそれを読む"""
        import libdocs
        from lib.tests import test_libdocs as TL
        (self.r.repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (self.r.repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        self.intake()
        cache = self.r.artifacts / files.LIBDOCS
        libdocs.section(cache, self.r.repo, ["app.py"], get=TL.ok_http(), env={})
        self.intake()
        http = TL.FakeHttp()
        text = libdocs.section(cache, self.r.repo, ["app.py"], get=http, env={})
        self.assertEqual(http.calls, [])
        self.assertIn("requests", text)

    def test_request_file_is_the_port_file(self):
        """元 test_boardview の Owners.test_request_file_is_the_same_file_for_review_and_gate: 依頼のファイルは port request の 1 つから
        読み（決め手の出どころの依頼の引用を照らす元）、置き場の外のファイルを名で探さない"""
        req = self.r.put("start/request.json", "[REQUEST-MARK-1]", raw=True)
        self.intake(request=req)
        got = self.r.read(files.INTAKE)
        self.assertEqual((pathlib.Path(got["request_file"]), got["request"]),
                         (self.r.artifacts / "start/request.json", "[REQUEST-MARK-1]"))


# ---------------------------------------------------------------- 却下と出し直し
class RejectCase(_Case):
    def test_reject_reason_pasted_in_the_next_prompt(self):
        """元 ReviewAcceptCase.test_reject_reason_pasted_in_the_next_material: 拒まれた後の 1 回目の役の指示の頭に却下の段落"""
        self.intake()
        self.prep()
        reason = self.reject()
        prompt = self.prep()["prompt"]
        self.assertTrue(prompt.startswith("## Why your previous answer was rejected"), prompt[:200])
        self.assertIn(reason.splitlines()[0][:40], prompt)
        self.assertNotIn("Why your previous answer was rejected", self.latest("review-material-*.md"))

    def test_third_prompt_pastes_every_reject_of_the_loop(self):
        """元 ReviewAcceptCase.test_third_material_pastes_every_reject_of_the_loop（#345）: 2 回拒まれた後の指示に、却下の全部が古い順"""
        self.intake()
        self.prep()
        reasons = [self.reject(), self.reject(reason="REJECT-MARK-2 二つ目の拒否の理由")]
        self.assertNotEqual(*reasons)
        prompt = self.prep()["prompt"]
        self.assertIn(rolekit.rejects_text(reasons), prompt)

    def test_resubmit_prompt_carries_the_last_reject_and_the_merged_answer(self):
        """元 ReviewAcceptCase.test_resubmit_material_carries_the_last_reject_and_the_merged_answer（#571）: 拒まれた後の周（prev が
        false）で合わせた答えの控えが在れば、review_prep は出し直しの周と返すだけで、出し直しの役の指示（review-fix。review_fix_prep が組む）: 最後の拒否の文を字のまま貼り、控えを名指す。材料は貼らない"""
        self.intake()
        self.prep()
        self.reject()
        last = self.reject(reason="REJECT-MARK-3 最後の拒否")
        candidate = rolekit.candidate_path(self.r.artifacts, files.REVIEW_NODE)
        candidate.write_text(V.dump(V.review()), encoding="utf-8")
        out = self.prep(prev="false")
        self.assertEqual((out["prompt"], out["resubmit"], out["tree"]), ("", True, False))
        self.assertFalse((self.r.artifacts / files.MATERIAL.format(n=2)).exists(), "出し直しの周は材料を書かない")
        out = self.r.script("review_fix_prep")
        self.assertIn(last, out["prompt"])
        self.assertIn(str(candidate), out["prompt"])
        self.assertTrue((self.r.artifacts / "review-fix-prompt-1.md").is_file())
        for absent in (material.LABELS["units"], "## Material", "## Why your previous answer was rejected"):
            self.assertNotIn(absent, out["prompt"])
        self.assertNotIn("new conversation", out["prompt"])

    def test_resubmit_needs_the_merged_answer(self):
        """prev が false でも合わせた答えの控えが無ければ（resume で輪が回り直した）、1 回目の役の指示を組む"""
        self.intake()
        self.prep()
        self.reject()
        out = self.prep(prev="false")
        self.assertFalse(out["resubmit"])
        self.assertTrue(out["prompt"].startswith("## Why your previous answer was rejected"))


# ---------------------------------------------------------------- 独立設計と design_map
class DesignCase(_Case):
    def map_section(self, mat: str) -> str:
        return mat[mat.index(material.MAT_HEADS["map_items"]):].split("\n\n## ")[0]

    def test_design_ask_names_unpaired_mechanisms_and_item_size_gap(self):
        """元 test_blk_plan の ScriptCase.test_design_ask_names_unpaired_mechanisms_and_item_size_gap: 設計が立つ run の指示の突き合わせの
        頼みは、対の無い仕組みも大きさの開きも contract_drift・block で挙げさせ、why の頭は design の 2 つの頭（字のまま）、引用は案の
        行の欄と設計の本文から、design_map の 2 つの向き、束ね役と相乗りは書かない、実装の細部と REUSE で挙げた行は挙げない"""
        prompt, mat = self.texts(design=V.dump(V.DESIGN_OK))
        ask = prompt[prompt.index("## Independent design"):prompt.index("## What to look at")]
        for want in ("kind contract_drift, severity block", design.DRIFT_HEAD, design.UNPAIRED_HEAD, "「…」",
                     *(f"`{k}`" for k in design.ROW_QUOTE_KEYS), "design_map", "Design to plan", "`item`, `path`, and `symbol` null",
                     "and the bundler (the role that starts the sub-agents) do not write it", "use 「」 only for quotes",
                     "Do not raise the implementation details", "Check that the plan weighed what already exists",
                     design.BODY_OPEN, design.BODY_CLOSE, "A point you cannot quote from the design does not count"):
            self.assertIn(want, ask, want)
        self.assertNotIn("kind scope_creep", ask)
        self.assertIn(f"{design.BODY_OPEN}\n{V.DESIGN_TEXT}\n{design.BODY_CLOSE}", mat)
        self.assertIn("- D1: ", mat)

    def test_design_not_stands_and_none(self):
        """問いが立たない設計と設計が無い run は、突き合わせずに審査せよの段落と、材料の訳の 1 行（立たない根拠・port design_why か
        既定の訳）"""
        prompt, mat = self.texts(design=V.dump(V.DESIGN_NOT))
        self.assertIn("does not stand", prompt)
        self.assertNotIn("Compare the plan with the independent design", prompt)
        self.assertIn(V.DESIGN_NOT["premise_invalid_reason"], mat)
        prompt, mat = self.texts(design_why="DESIGN-WHY-MARK 設計の役が落ちた")
        self.assertIn("There is no independent design", prompt)
        self.assertIn("DESIGN-WHY-MARK 設計の役が落ちた", mat)
        _, mat = self.texts()
        self.assertIn("独立設計の返りが渡されていない", mat)
        self.assertNotIn(material.MAT_HEADS["map_items"], mat)

    def test_design_off_the_schema_is_missing(self):
        """元 test_blk_plan の DesignReadCase 2 本: place の design.json は役の型で確かめてから読む。型に合わない控えは設計が無い訳に
        回り、欄を引いて落ちない。型に合う控えは本文を貼る"""
        schema = json.loads((kit.BLOCKS / V.BLOCK / "schemas" / "review-design.schema.json").read_text(encoding="utf-8"))
        tmp = self.r.artifacts.parent / "board"
        tmp.mkdir()
        b = types.SimpleNamespace(dir=tmp, design_schema=schema)
        (tmp / design.DESIGN_FILE).write_text(json.dumps({"missing": "型の外の控え"}, ensure_ascii=False), encoding="utf-8")
        text = material.design_only(b, {})
        self.assertIn(material.MAT_HEADS["design"], text)
        self.assertIn(design.MISSING, text)
        self.assertIn("型が合わない", text)
        (tmp / design.DESIGN_FILE).write_text(json.dumps({"question_stands": True, "reason": "立つ", "design": "DESIGN-本文"},
                                                         ensure_ascii=False), encoding="utf-8")
        self.assertIn("DESIGN-本文", material.design_only(b, {}))

    def test_map_section_lists_the_wanted_keys(self):
        """元 ReviewAcceptCase.test_map_section_lists_the_wanted_keys: 設計が立つ木にしない往復の材料の design_map を書く項目の節に、
        案→設計で要る鍵（design.wanted_lines）の全部の行が載る。op=modify で symbol の無い files の行は鍵に出ない"""
        items = [V.item(V.UNIT_MEAN, 1, files=[V.frow("stats.py", "helper_1"), V.frow("notes.py"), V.frow("old.py", op="delete")]),
                 V.item(V.UNIT_CLAMP, 2)]
        prompt, mat = self.texts(items=items, design=V.dump(V.DESIGN_OK))
        section = self.map_section(mat)
        keys = [json.loads(x) for x in section.splitlines() if x.startswith('{"item"')]
        self.assertEqual(keys, [{"item": 1, "path": "stats.py", "symbol": "helper_1"}, {"item": 1, "path": "old.py", "symbol": None},
                                {"item": 2, "path": "stats.py", "symbol": "helper_2"}])
        self.assertNotIn("notes.py", section)
        self.assertIn("Items: 1・2", section)
        self.assertIn('How to read the section "Items that write design_map"', prompt)

    def test_map_section_without_keys(self):
        """元 ReviewAcceptCase.test_map_section_without_keys_passes_design_rows_first_time（#747）: 案→設計の鍵が無い案では、材料の
        節が札 no keys を持ち、指示が要素を設計→案の行に書けと言う"""
        items = [V.item(V.UNIT_MEAN, 1, files=[V.frow("stats.py"), V.frow("docs/notes.md")]),
                 V.item(V.UNIT_CLAMP, 2, files=[V.frow("stats.py")])]
        prompt, mat = self.texts(items=items, design=V.dump(V.DESIGN_OK))
        section = self.map_section(mat)
        self.assertIn(material.LABELS["no_keys"], section)
        self.assertNotIn('{"item"', section)
        self.assertIn("When it says `no keys`", prompt)

    def test_map_section_only_without_the_tree(self):
        """木の往復の材料は design_map を書く項目の節を持たない（下請けが自分の項目の節を読む）"""
        self.intake(design=V.dump(V.DESIGN_OK), tree="on")
        with self.r.env():
            intake = self.r.read(files.INTAKE)
            text = material.material_text(self.r.artifacts, intake, self.r.repo, kit.load(V.BLOCK, "view").view(self.r.artifacts, intake))
        self.assertTrue(intake["tree"])
        self.assertNotIn(material.MAT_HEADS["map_items"], text)


# ---------------------------------------------------------------- 2 往復目
class SecondPassCase(_Case):
    def test_rereview_material_carries_previous_blocks_and_answers(self):
        """元 ConvergeCase.test_rereview_material_carries_previous_blocks_and_answers: 2 往復目の材料は前の往復の block の行と修正案の役の
        答えを、指示は往復の頼みを持つ"""
        prompt, mat = self.second()
        at = mat.index(material.MAT_HEADS["passes"])
        for want in (material.LABELS["pass_blocks"].format(n=1), MEAN_BLOCK["key"], MEAN_BLOCK["where"], MEAN_BLOCK["why"],
                     material.LABELS["answers"], ANSWERS[0]["how"]):
            self.assertIn(want, mat[at:], want)
        for want in ("## From the second pass on", "Answers to earlier passes", "Origins of new blocks", "How to read the diffs"):
            self.assertIn(want, prompt)

    def test_first_material_has_no_rereview(self):
        """元 ConvergeCase.test_first_material_has_no_rereview"""
        prompt, mat = self.texts()
        self.assertNotIn(material.MAT_HEADS["passes"], mat)
        self.assertNotIn("Answers to earlier passes", prompt)
        self.assertNotIn("Origins of new blocks", prompt)

    def test_second_pass_material_has_only_changed_sentences(self):
        """元 ConvergeCase.test_second_pass_material_has_only_changed_sentences: 2 往復目の材料は修正案の全体の代わりに開いた項目の案の
        文の差分と波及の一覧だけを持つ。変わっていない文・閉じた項目の案・項目の works の欄の節は載らない"""
        prompt, mat = self.second()
        self.assertNotIn(material.LABELS["plan"] + " [", mat)
        self.assertIn(material.LABELS["open_item"].format(n=1, units=V.UNIT_MEAN), mat)
        self.assertIn("+ approach: mean は空の列を先に弾いて分母を直す", mat)
        self.assertIn(f"- approach: {V.PLAN_MARK} 項目 1 の直し: {V.UNIT_MEAN} を直す", mat)
        self.assertIn(material.LABELS["ripple"].format(n=1), mat)
        for unchanged in (f"{V.PLAN_MARK} 項目 2 の直し", "1 行の直しで済む", "helper_2", material.MAT_HEADS["fields"]):
            self.assertNotIn(unchanged, mat, unchanged)
        self.assertIn("A diff row is `<mark> <place>: <sentence>`", prompt)
        first = (self.r.artifacts / files.MATERIAL.format(n=1))
        self.assertFalse(first.exists() and material.LABELS["plan"] + " [" in first.read_text(encoding="utf-8")
                         and "+ approach" in first.read_text(encoding="utf-8"))

    def test_second_pass_material_shows_other_items_scope(self):
        """元 ConvergeCase.test_second_pass_material_shows_other_items_scope: 項目が 2 つ以上なら、波及の一覧の重なりのうち開いた項目に
        当たる行と、ほかの項目の unit_keys・allowed_paths・files の path を貼る（閉じた項目の案の文は貼らない）"""
        items = [V.item(V.UNIT_MEAN, 1, approach="mean の分母を直し、clamp の上限の枝も同じ関数で包む",
                        files=[V.frow("stats.py", "helper_1", "clamp")]), V.item(V.UNIT_CLAMP, 2)]
        prompt, mat = self.second(items=items, ripple=V.RIPPLE)
        cross = mat[mat.index(material.LABELS["cross"]):]
        for want in ("- stats.py: item 1, 2", f"- item 2 ({V.UNIT_CLAMP})", "  - allowed_paths: stats.py", "  - files: stats.py"):
            self.assertIn(want, cross, want)
        self.assertNotIn(f"- item 1 ({V.UNIT_MEAN})", cross, "開いた項目が 1 つなら自分の範囲は差分の側に在る")
        self.assertIn("+ files[stats.py].symbols[clamp].name: clamp", mat, "閉じた項目 2 の名に触る直しの文")
        for unchanged in (f"{V.PLAN_MARK} 項目 2 の直し", "helper_2"):
            self.assertNotIn(unchanged, mat, unchanged)
        self.assertIn("\"Overlaps and other items' scope\"", prompt)

    def test_cross_section_without_ripple_says_the_list_is_missing(self):
        """元 ConvergeCase.test_cross_section_without_ripple_says_the_list_is_missing: 波及の一覧が誤りの時、項目どうしの節の重なりは
        「無い」と言わず、一覧が無い訳を書く"""
        _, mat = self.second(ripple={"error": "RIPPLE-ERR-4410"})
        cross = mat[mat.index(material.LABELS["cross"]):]
        self.assertIn(f"{material.LABELS['overlaps']}\n- " + material.LABELS["ripple_missing"].format(error="RIPPLE-ERR-4410"), cross)
        self.assertNotIn(f"{material.LABELS['overlaps']}\n- none", cross)

    def test_second_pass_material_of_one_item_has_no_cross_section(self):
        """元 ConvergeCase.test_second_pass_material_of_one_item_has_no_cross_section"""
        _, mat = self.second(items=[V.item(V.UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す")],
                             first_items=[V.item(V.UNIT_MEAN, 1)])
        self.assertIn(material.LABELS["open_item"].format(n=1, units=V.UNIT_MEAN), mat)
        self.assertNotIn(material.LABELS["cross"], mat)

    def test_second_pass_with_design_asks_only_the_diff(self):
        """設計が立つ 2 往復目の指示は差分と鍵の一覧だけを突き合わせる段落を持ち、1 往復目は持たない"""
        prompt, _ = self.second(design=V.dump(V.DESIGN_OK))
        self.assertIn("From the second pass on, compare with the design only", prompt)
        prompt, _ = self.texts(design=V.dump(V.DESIGN_OK))
        self.assertNotIn("From the second pass on, compare with the design only", prompt)


# ---------------------------------------------------------------- 形 replan
class ReplanCase(_Case):
    def test_replan_is_one_shot(self):
        """元 ReplanCase.test_replan_is_one_shot の材料の半分: 裁かれた項目ごとに前の形・申し出と裁定・直した形を貼り、指示は案の直しの
        頼みと works の欄の見方を持つ。往復の頼みは無い"""
        prompt, mat = self.replan()
        for want in (material.MAT_HEADS["replan"], material.LABELS["replan_item"].format(n=2), material.LABELS["approved"],
                     material.LABELS["revised"], material.LABELS["objection"].format(id="c-clamp"), "RULING-MARK-3131", "直した項目 2"):
            self.assertIn(want, mat, want)
        self.assertNotIn(material.LABELS["replan_item"].format(n=1), mat)
        for want in ("## Review of a replan", "## How to read the works fields"):
            self.assertIn(want, prompt)
        self.assertNotIn("Answers to earlier passes", prompt)
        self.assertNotIn(material.MAT_HEADS["passes"], mat)

    def test_replan_material_carries_the_independent_design(self):
        """元 ReplanCase.test_replan_material_carries_the_independent_design: 設計の節が裁かれた項目の節より前"""
        prompt, mat = self.replan(design=V.dump(V.DESIGN_OK))
        at = [mat.index(w) for w in (material.MAT_HEADS["design"], V.DESIGN_TEXT, material.MAT_HEADS["replan"],
                                     material.LABELS["replan_item"].format(n=2))]
        self.assertEqual(at, sorted(at))
        self.assertIn("Compare the plan with the independent design", prompt)

    def test_replan_material_shows_only_ruled_items(self):
        """元 ReplanCase.test_replan_material_shows_only_ruled_items: 裁かれた項目だけを見る（直していない項目の案・欄を貼らない）"""
        _, mat = self.replan()
        self.assertIn("直した項目 2", mat)
        self.assertNotIn(f"{V.PLAN_MARK} 項目 1 の直し", mat)
        self.assertNotIn(material.MAT_HEADS["fields"], mat)


# ---------------------------------------------------------------- 木の下請けに届く方針（指示は src/tree.py が組む）
class TreeBriefCase(_Case):
    def brief(self, **over) -> str:
        got = self.intake(tree="on", **over)
        self.assertTrue(got["tree"], got)
        self.prep()
        return (self.r.artifacts / files.BRIEF).read_text(encoding="utf-8")

    def test_item_subagents_get_the_policy(self):
        """元 PortedMaterialCase.test_item_subagents_get_the_policy・test_role_prompts_paste_the_frozen_copy の木の半分: 下請けの指示に
        port policy の本文と人の方針の決まりが載る"""
        text = self.brief(policy=self.put_policy())
        self.assertIn("POLICY-MARK-8080", text)
        self.assertIn("Do not rewrite the policy document", text)

    def test_policy_face_example_reaches_item_briefs(self):
        """元 PortedMaterialCase.test_policy_face_example_reaches_prompt_and_item_briefs の木の半分: 下請けの指示に kind policy の穴の例"""
        rows = [{"source": "answer", "name": "q-mean-empty", "text": "空の列の平均は例外にする"}]
        text = self.brief(recorded=V.dump(rows))
        self.assertIn(json.dumps({"kind": "policy", "severity": "suggest", "decided_by": "q-mean-empty"}, ensure_ascii=False), text)


# ---------------------------------------------------------------- 指示の md と材料の分け
class SplitCase(_Case):
    def test_head_carries_the_ported_rules(self):
        """元 test_blk_plan の ScriptCase.test_head_asks_no_narrow_first・ConceptRuleCase.test_plan_head_has_concept_rule・
        RejectHeadOwnerCase.test_review_head_names_no_board: 審査の役の頭は regression の穴に示せる時だけ狭めない案を添えよと言い
        （修正案の役の「先に探せ」は持たない）、判断の 1 軸と考えの住処の観点を持ち（why の頭は字のまま）、盤面を名指さない"""
        prompt, _ = self.texts()
        self.assertIn("Add the form that does not narrow: on a hole of kind regression", prompt)
        self.assertIn(f"`{material.gatemarks.NO_NARROW}`: that form ({material.gatemarks.NO_NARROW_MIN} characters or more)", prompt)
        self.assertIn("The one axis of judgment", prompt)
        self.assertIn(f'start its `why` with "{material.concepthome.PREFIX}"', prompt)
        self.assertIn(f"`{material.converge.STUCK_PUSH}` at the top of the answer", prompt)
        for board in ("盤面", "共有ボード", "board"):
            self.assertNotIn(board, md_texts())

    def test_fixed_heads_are_the_literals_readers_match(self):
        """頭の決まった字（最小性・足りない・考えの住処・独立設計の 2 つの頭）は言語によらず読み手と同じ字で指示に入る（14 節の 20）"""
        prompt, _ = self.texts(design=V.dump(V.DESIGN_OK), lang="English")
        for head in (files.MINIMAL_HEAD, files.SHORT_HEAD, files.HOME_HEAD, design.DRIFT_HEAD, design.UNPAIRED_HEAD):
            self.assertIn(f'"{head}"', prompt, head)
        self.assertEqual(files.HOME_HEAD, material.concepthome.PREFIX)
        self.assertIn("in English.", prompt)

    def test_material_heads_are_named_by_the_md(self):
        """足す: 材料のファイルの見出しは MAT_HEADS の札で、md が全部を字のまま名指す"""
        text = md_texts()
        for head in material.MAT_HEADS.values():
            self.assertIn(f'"{head[3:]}"', text, head)
        _, mat = self.texts(design=V.dump(V.DESIGN_OK))
        heads = [x for x in mat.splitlines() if x.startswith("## ")]
        self.assertTrue(set(heads) <= set(material.MAT_HEADS.values()), heads)

    def test_material_has_no_instruction_text(self):
        """足す: 材料のファイルは指示の文を持たない（MAT_HEADS と札の外の、今の決まりの文の頭の字も、md の決まりの文も無い）。
        ライブラリの文書の節は lib の libdocs の字のまま（17 節の未確認）なので除いて見る"""
        import boardview
        import planblk
        import ripple
        olds = (planblk.DESIGN_ASK, planblk.DIFF_ASK, planblk.CROSS_ASK, planblk.NO_MAP_KEYS, planblk.DESIGN_NOT_STANDS,
                planblk.REUSE_REVIEW, planblk.HANDOFF_REVIEW, planblk.EXCLUDED_HEAD, planmarks.REVIEW_ASK, planmarks.MACHINE_LABEL,
                converge.REREVIEW_ASK, converge.ORIGIN_ASK, converge.HELD_CITES, boardview.UNITS_LINE, boardview.REVIEW_ASK_REPLAN,
                boardview.DEFAULTS_HEAD, ripple.SCOPE_ASK, policy.RECORDED_RULE, policy.FACE_EXAMPLE_HEAD)
        mats = [self.second(design=V.dump(V.DESIGN_OK), excluded=self.r.put("judge/pr-excluded.json", {"excluded": ["docs/"]}))[1],
                self.texts(design=V.dump(V.DESIGN_OK))[1], self.replan()[1]]
        rules = [line.strip() for line in md_texts().splitlines() if len(line.strip()) > 60 and "{" not in line]
        for mat in mats:
            body = re.sub(r"## Library documents\n\n.*?(?=\n## |\Z)", "", mat, flags=re.S)
            for old in olds:
                self.assertNotIn(old[:14], body, old[:30])
            for rule in rules:
                self.assertNotIn(rule[:50], body, rule[:50])
            for word in ("Read ", "Raise ", "Do not ", "Check "):
                self.assertNotIn(word, body, word)

    def test_every_slot_has_one_producer(self):
        """足す: 指示の md が持つ差し込み口と段落の名は、material の作り手（SLOTS・WHEN）か、その md を組む口だけの値（木の束ね役と
        下請けの口）で、作り手の無い名は fragment_values が名を挙げて拒む"""
        for node in ("review", "review-text"):
            slots, marks = material.names_of([f"node:{node}"])
            self.assertEqual(sorted(slots - set(material.SLOTS)), [], node)
            self.assertEqual(sorted(marks - set(material.WHEN)), [], node)
        with self.assertRaises(KeyError) as got:
            material.fragment_values(["node:review-tree"], self.r.artifacts, {"form": "text"}, self.r.repo)
        self.assertIn("subagent_type", str(got.exception))

    def test_language_line_names_the_lang_port(self):
        """人に見せる欄の言語は port lang（空なら依頼の言語の既定の文）"""
        prompt, _ = self.texts()
        self.assertIn("in the language of the request (the user's language).", prompt)
