"""判定のブロック（workflows/judge/）の YAML の形・筋書き・script の振る舞いの試験（計画 docs/plans/2026-10-12-blocks/judge.md の「試験」）。

- YAML の形: PyYAML で読み、Archon を起こさない。返す節の約束（docs/design.md の「judge の出力」）・関所・輪・役の節の設定の表
- 筋書き: tests/archon.py の使い捨ての木で `archon workflow test` と `archon validate workflows` を回す。源か bun が無ければ見送る
- script の振る舞い: scripts/<名>.py を子のプロセスで走らせる（Archon が渡す INPUTS_<名>・ARTIFACTS_DIR・WORKFLOW_ID と、
  boundary.lib_root() が届く WORKS_FACTORY_ROOT を置く。作業ツリーは tests/e2e/target-seed/ の写し）
"""
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

from tests import archon
from tests.bin import hermetic, trimmed
from tests.bin.gitkit import committed_copy, git
from tests.layers import scan
from tests.workflows.copied import agent_body, assert_is_original, rewritten, role_definition

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "lib"))
import answer  # noqa: E402
import depth  # noqa: E402
import headdepth  # noqa: E402
import judge_accept as ja  # noqa: E402
import launchgroups  # noqa: E402
import prcheck  # noqa: E402
import reads  # noqa: E402
import rolekit  # noqa: E402
import runreport  # noqa: E402
import seat  # noqa: E402
import userenv  # noqa: E402
from engine.schema import validate_schema  # noqa: E402  （judge_accept が写しの engine を sys.path に足す）
from lib.tests import test_judge_accept as TJ  # noqa: E402

BLOCK = ROOT / "workflows" / "judge"
YAML_FILE = BLOCK / "works-factory-judge.yaml"
SCRIPTS = BLOCK / "scripts"
COMMANDS = BLOCK / "commands"
SEED = ROOT / "tests" / "e2e" / "target-seed"
NAME = "works-factory-judge"
NO_DEADLINE = 1728000000
RUN_ID = "run-judge"

# 返す節の欄（docs/design.md の「サブグラフの出力の約束」の judge の返り）
RETURNS = ("ready", "stop_reason", "units", "judgment", "purpose", "world", "spec", "out_of_purpose", "rejudge_verdict", "depth",
           "depth_why")
INPUTS = {"start": "null", "baseline": "null", "objection": "", "prior_failures": "null"}
RUN_OWNED = ("worktree", "container", "evidence_policy", "mutates_checkout")
MATERIALS = tuple(ja.MATERIAL_ROLES)
PUBLIC = ("premises.json", "judge-verify.json", "pr-excluded.json", "materials.json", "purpose-review.json", "depth-head.json")

# 役の節の設定（今の works の旧 YAML の値。works/blk-*/blk-*.yaml と darkfactory/darkfactory.yaml の 174〜400 行・866 行）
BASE = {"enabled": True, "allowUnsandboxedCommands": False}
NO_TREE = {"denyWrite": [scan.NO_TREE_WRITE]}
CLOSED = {**BASE, "failIfUnavailable": True, "excludedCommands": ["works-gh:*"], "network": {"allowedDomains": []},
          "filesystem": NO_TREE}
DELEGATE = {**BASE, "failIfUnavailable": True, "enableWeakerNetworkIsolation": True,
            "network": {"allowedDomains": ["*"], "allowLocalBinding": True}, "filesystem": {"allowWrite": ["/"], **NO_TREE}}
READ = ["Read", "Grep", "Glob"]
WEB = ["WebSearch", "WebFetch"]
INVESTIGATE = [*READ, "Bash", *WEB]
WRITE_TESTS = [*READ, "Edit", "Write", "Bash", *WEB]
# 局所レビューの役が読む Claude Code 同梱の skill と、必須のレンズを持つプラグイン（手元の marketplace の名は bin/_lib/toolset.py の MARKETPLACE）。
# 止めた Archon は節が名指さないプラグインを切る（packages/providers/src/claude/plugins.ts の buildClaudePluginSettings）
LOCAL_REVIEW_SKILLS = ["code-review", "simplify", "security-review"]
LOCAL_REVIEW_PLUGINS = ["pr-review-toolkit@works-local"]
# 節の id → (model, effort, allowed_tools, sandbox, mutates_checkout が false か, context, skills, plugins)
ROLES = {
    "head-depth": ("sonnet", "medium", READ, BASE, True, None, None, None),   # 今の works に元の無い役（issue #441）
    "spec": ("opus", "medium", WRITE_TESTS, BASE, False, None, None, None),
    "spec-review": ("opus", "high", [*READ, *WEB], BASE, True, None, None, None),
    "spec-revise": ("opus", "medium", WRITE_TESTS, BASE, False, None, None, None),
    "pr-check": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None, None, None),
    "premises": ("sonnet", "medium", INVESTIGATE, {**BASE, "filesystem": NO_TREE}, False, None, None, None),
    "purpose": ("sonnet", "medium", [*READ, *WEB], BASE, True, None, None, None),
    "world-classes": ("opus", "high", [], BASE, True, None, None, None),
    "world-judge": ("sonnet", "medium", WEB, BASE, True, None, None, None),
    "prior-decisions": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None, None, None),
    "purpose-review": ("sonnet", "medium", READ, BASE, True, None, None, None),
    "local-review": ("sonnet", "medium", [*INVESTIGATE, "Skill", "Agent"], CLOSED, False, None,
                     LOCAL_REVIEW_SKILLS, LOCAL_REVIEW_PLUGINS),
    "consistency-bypass": ("sonnet", "medium", READ, BASE, True, None, None, None),
    "hygiene": ("sonnet", "medium", [], BASE, True, None, None, None),
    "external-standards": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None, None, None),
    "procedure-trace": ("sonnet", "medium", INVESTIGATE, CLOSED, False, None, None, None),
    "gate-efficacy": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None, None, None),
    "test-double-fidelity": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None, None, None),
    "main-path-observation": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None, None, None),
    "provenance": ("sonnet", "medium", INVESTIGATE, DELEGATE, False, None, None, None),
    "diagnose": ("opus", "high", [*READ, *WEB], BASE, True, None, None, None),
    "judge-verify": ("opus", "high", [*READ, *WEB, "Agent", "Write"], BASE, True, "fresh", None, None),
    "rejudge": ("opus", "high", [*READ, *WEB], BASE, True, None, None, None),
}
# 頭の節（script rejects）が受け付けの拒否の控えの全部を渡す輪（旧 YAML で役が周ごとに新しい会話で起きた仕様の 3 つの輪と再審の輪。
# #571 から全部の輪が会話を続けるが、控えの全部を渡す形は残す）と、結ぶ控え（受け付けの置き場と控えの名。lib/judge_accept の
# spec_accept・rejudge_accept と同じ）
RESUBMIT_ROLES = ("spec", "spec-review", "spec-revise", "rejudge")   # 拒まれた後に <役>-fix が同じ会話の続きで出し直す役（#571）
LEDGER_REJECTS = {"spec-loop": {"board": ja.JUDGE_DIR, "accept": ja.SPEC_ROLES["write"]},
                 "spec-review-loop": {"board": ja.JUDGE_DIR, "accept": ja.SPEC_ROLES["review"]},
                 "spec-revise-loop": {"board": ja.JUDGE_DIR, "accept": ja.SPEC_ROLES["revise"]},
                 "rejudge-loop": {"board": ja.REJUDGE_DIR, "accept": ja.REJUDGE_ROLE}}
# 観点の正本（REVIEW.md）を読む役の指示書（元が {{inputs.review_md}} で読ませていた物）
REVIEW_READERS = ("diagnose", "material-local-review", "material-consistency-bypass", "material-hygiene",
                  "material-external-standards", "material-procedure-trace")


def load() -> dict:
    return yaml.safe_load(YAML_FILE.read_text(encoding="utf-8"))


def walk(nodes):
    for node in nodes:
        yield node
        if "loop_group" in node:
            yield from walk(node["loop_group"]["nodes"])


def nodes() -> dict:
    return {n["id"]: n for n in walk(load()["nodes"])}


def loops() -> dict:
    return {n["id"]: n for n in walk(load()["nodes"]) if "loop_group" in n}


class ParallelPrThroughReadOnlyGhTest(unittest.TestCase):
    """run の中の素の gh は起動が PATH の頭に置く読むだけの口（bin/_lib/no-post-bin/）。並行 PR の数えの gh の打ち方が口の許可の表に
    合うことを縛る（片側だけ変えると、試験は緑のまま run の中だけで口が拒み、人待ちになる）"""

    def test_parallel_pr_scan_passes_the_read_only_gh(self):
        with tempfile.TemporaryDirectory(prefix="works-judge-gh-") as tmp:
            real = pathlib.Path(tmp)
            log = real / "gh.txt"
            (real / "python3").symlink_to(sys.executable)
            gh = real / "gh"
            gh.write_text(f'''#!/bin/sh
printf '%s\\n' "$*" >> "{log}"
case "$1 $2" in
  "pr list") echo '[{{"number": 7, "headRefName": "x", "headRefOid": "theirs"}}]' ;;
  "pr view") echo '{{"files": [{{"path": "a.py"}}]}}' ;;
esac
''', encoding="utf-8")
            gh.chmod(0o755)
            with mock.patch.dict(os.environ, PATH=os.pathsep.join([str(ROOT / "bin" / "_lib" / "no-post-bin"), str(real)])):
                os.environ.pop("WORKS_FACTORY_GH_ACTIVE", None)
                got, why = ja.parallel_pr_scan(real, "o/r", "mine", ["a.py"])
            self.assertEqual(why, "")
            self.assertEqual(got["conflicts"], [{"pr": "7", "files": ["a.py"]}])
            self.assertEqual([line.split()[:2] for line in log.read_text(encoding="utf-8").splitlines()],
                             [["pr", "list"], ["pr", "view"]])


class ReplyTypeCase(unittest.TestCase):
    """役の返答の型の正本は節の output_format だけ（受け付けは型を照らし直さない）。受け付けの型の写しが拒んでいた返答を、節の
    output_format が拒む事と、前後の空白を除いた長さの下限を pattern が持つ事を見る"""
    TYPED = ("diagnose", "rejudge", "premises", "purpose", "pr-check")

    def rejected(self, nid: str, reply) -> list:
        return validate_schema(reply, nodes()[nid]["output_format"])

    def test_trimmed_min_length_kept_by_pattern(self):
        by = nodes()
        for nid in self.TYPED:
            with self.subTest(nid):
                self.assertEqual(trimmed.missing_patterns(by[nid]["output_format"]), [])

    def test_good_replies_fit_the_output_format(self):
        """受け付けの試験の良い返答は節の output_format に合う（型の外の返答で受け付けの試験を組んでいない）"""
        self.assertEqual(self.rejected("diagnose", TJ._judge_ok()), [])
        self.assertEqual(self.rejected("rejudge", TJ._rejudge_reply()), [])
        self.assertEqual(self.rejected("premises", TJ.PremisesCase.GOOD), [])

    def test_diagnose_reply_outside_the_type_is_rejected(self):
        """元 test_judge_accept の test_open_unit_why_chain_must_be_lines と test_question_without_kind_or_status_is_rejected の型の側:
        why_chain の段が文でない・問いに kind と status が無い"""
        reply = TJ._judge_ok()
        reply["units"][0]["why_chain"] = [{"段": 1}]
        self.assertTrue([e for e in self.rejected("diagnose", reply) if "why_chain" in e])
        reply = TJ._judge_ok()
        reply["questions"] = [{"key": "q1", "reason": "決まらない"}]
        errs = " ".join(self.rejected("diagnose", reply))
        self.assertIn("kind", errs)
        self.assertIn("status", errs)

    def test_premises_reply_outside_the_type_is_rejected(self):
        """元 test_judge_accept の PremisesCase.test_reply_outside_the_copied_type_rejected: 欠けた欄・知らない語・知らない欄"""
        for bad in ({"text": "a", "kind": "仮説"}, {"text": "a", "measured_how": "b", "kind": "推測"},
                    {"text": "a", "measured_how": "b", "kind": "仮説", "note": "足した欄"}):
            with self.subTest(bad):
                self.assertTrue(self.rejected("premises", {"constraints": [bad]}))

    def test_rejudge_reply_outside_the_type_is_rejected(self):
        """元 test_judge_accept の RejudgeCase.test_verdict_word_outside_three_rejected: verdict は 3 つの語・欠けた欄"""
        self.assertTrue(self.rejected("rejudge", TJ._rejudge_reply(verdict="保留")))
        self.assertTrue(self.rejected("rejudge", {"verdict": "採る"}))

    def test_pr_check_reply_outside_the_type_is_rejected(self):
        """元 test_judge_accept の PrAcceptCase.test_excluded_checked の型の側: excluded が無い・行の番号が 1 より小さい"""
        good = TJ._PR_OK
        self.assertEqual(self.rejected("pr-check", good), [])
        self.assertTrue(self.rejected("pr-check", {k: v for k, v in good.items() if k != "excluded"}))
        self.assertTrue(self.rejected("pr-check", dict(good, excluded=[dict(good["excluded"][0], start=0)])))

    def test_whitespace_only_text_is_rejected_by_pattern(self):
        """lib の型検査が前後の空白を除いて数えていた下限は、Ajv の素の長さでなく pattern が持つ"""
        fmt = nodes()["premises"]["output_format"]
        field = fmt["properties"]["constraints"]["items"]["properties"]["measured_output"]
        self.assertFalse(trimmed.matches(field["pattern"], "   "))
        self.assertTrue(trimmed.matches(field["pattern"], "$ grep -c x README.md\n3"))


class ReturnsShapeTest(unittest.TestCase):
    def test_verdict_returns_exactly_the_contract(self):
        doc, by = load(), nodes()
        self.assertEqual((doc["returns"], doc["outcome_field"]), ("verdict", "ready"))
        fmt = by["verdict"]["output_format"]
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURNS))
        self.assertEqual(sorted(fmt["required"]), sorted(RETURNS))
        self.assertIs(fmt["additionalProperties"], False)
        self.assertEqual(fmt["properties"]["ready"], {"type": "boolean"})
        self.assertEqual(fmt["properties"]["stop_reason"], {"type": "string"})
        self.assertEqual(by["verdict"]["trigger_rule"], "all_done")
        self.assertNotIn("output_type", by["verdict"])

    def test_rejudge_vocabulary_matches_output_format(self):
        """受け付けの論理が使う再審の答えの語（ja.REJUDGE_VERDICTS）は、再審の役の節の output_format の verdict の enum と同じ。
        型の正本は output_format だけで、lib は語だけを持つ"""
        self.assertEqual(nodes()["rejudge"]["output_format"]["properties"]["verdict"]["enum"], list(ja.REJUDGE_VERDICTS))

    def test_lib_vocabularies_match_output_format(self):
        """受け付けの論理と指示書が使う語（judge_accept・runreport の語の表）は、それを返す役の節の output_format の enum と同じ。
        型の正本は output_format で、lib は語だけを持つ"""
        by = nodes()

        def enum(nid, *path):
            got = by[nid]["output_format"]
            for key in path:
                got = got["items"] if key == "[]" else got["properties"][key]
            return got["enum"]

        material = [(nid, f) for nid, n in by.items() if n.get("output_format")
                    for f, v in n["output_format"].get("properties", {}).items()
                    if isinstance(v, dict) and set(v.get("properties", {}).get("status", {}).get("enum", [])) & set(ja.STATUS)]
        self.assertEqual(len(material), 11, "素材の状態の enum を持つ節の欄")
        rows = [*((f"{nid} label", enum(nid, "units", "[]", "label"), list(ja.LABELS)) for nid in ("diagnose", "rejudge")),
                ("diagnose kind", enum("diagnose", "questions", "[]", "kind"), list(ja.QUESTION_KINDS)),
                ("diagnose status", enum("diagnose", "questions", "[]", "status"), list(ja.QUESTION_STATUS)),
                *((f"{nid} {f}.status", enum(nid, f, "status"), list(ja.STATUS)) for nid, f in material)]
        for name, got, want in rows:
            with self.subTest(name):
                self.assertEqual(got, want)
        self.assertIn(runreport.HYPOTHESIS, enum("premises", "constraints", "[]", "kind"))
        self.assertIn(ja.PURPOSE_UNKNOWN, enum("purpose", "source"))

    def test_inputs_are_the_contract_and_prior_failures(self):
        inputs = load()["inputs"]
        self.assertEqual({k: v["default"] for k, v in inputs.items()}, INPUTS)

    def test_head_keeps_no_run_keys(self):
        """include で差し込まれるブロックは run の持ち物（worktree ほか）と、効かない interactive を書かない（workflows/AGENTS.md の E16）"""
        doc = load()
        self.assertEqual([k for k in (*RUN_OWNED, "interactive") if k in doc], [])


class GateTest(unittest.TestCase):
    def test_spec_gate_is_an_approval_with_the_four_words(self):
        by = nodes()
        gate = by["spec-gate"]["wait"]
        self.assertEqual(gate["form"], "select")
        self.assertEqual([d["id"] for d in gate["options"]], list(answer.GO_WORDS + answer.STOP_WORDS))
        self.assertEqual(gate["attention"], "$spec-ask.output.message")
        self.assertEqual(by["spec-freeze"]["with"]["answer"], {"from": "$spec-gate.output", "if_skipped": None})

    def test_spec_freeze_may_change_the_checkout(self):
        """spec-freeze は人が通した受け入れ条件を作業ツリーで走らせる（lib/judge_accept._spec_run）。走らせた命令がファイルを
        残しても節が落ちないように、作業ツリーを変えない印を持たない"""
        self.assertNotIn("mutates_checkout", nodes()["spec-freeze"])


class LoopTest(unittest.TestCase):
    def test_every_loop_retries_three_times_until_its_accept_is_done(self):
        for lid, loop in loops().items():
            with self.subTest(loop=lid):
                body = loop["loop_group"]
                accept = body["nodes"][-1]["id"]
                self.assertTrue(accept.endswith("-accept"), accept)
                self.assertEqual(body["max_iterations"], 3)
                self.assertEqual(body["until_bash"], f'done=${accept}.output.done; test "$done" = true')
                self.assertEqual(loop["timeout"], NO_DEADLINE)
                self.assertIs(body["fresh_context"], False)

    def test_roles_receive_the_reject_reason_through_the_loop_head(self):
        """拒否の理由は、輪の頭の節（<役>-reject＝script reject。素材の輪では <役>-prep＝script material_prep）の with: に $LOOP_PREV で結び、
        役の指示書は今の周のその節の返り $<役>-reject.output.reason（素材の輪では $<役>-prep.output.reason）で受け、rolekit.with_reject の
        見出しと文で出す（1 周目の $LOOP_PREV は空の字）。素材の輪には <役>-reject の節が無く、<役>-prep の返りが reason・lang_line を持つ。
        控えの全部を渡す輪（LEDGER_REJECTS）は script rejects の節で、$LOOP_PREV でなく受け付けの拒否の控えと前の周の受け付けの ok を結ぶ（#345・#571）。
        役の節には with: を書かず、指示書には $INPUTS も $LOOP_PREV も書かない: 線が include すると、止めた Archon は輪の中の節が
        自分の with: で結んだ名を楯にせず「入力が無い」で止める（packages/workflows/src/include-expander.ts:566・627。楯は輪の節の
        束縛だけを見る）。ブロックの入力に宣言すると読み込みの時に既定の値で字が埋まり、周ごとの理由が消える。指示書の $LOOP_PREV は
        include した時だけ解け、単独の run では字のまま役に届く"""
        lead = rolekit.with_reject("", "").split("\n\n")[1].removesuffix(":")
        for lid, loop in loops().items():
            body = {n["id"]: n for n in loop["loop_group"]["nodes"]}
            accept = loop["loop_group"]["nodes"][-1]["id"]
            for role in (n for n in body.values() if "command" in n):
                with self.subTest(role=role["id"]):
                    material = role["id"] in MATERIALS
                    reject = f"{role['id']}-{'prep' if material else 'reject'}"
                    if material:
                        self.assertNotIn(f"{role['id']}-reject", body)
                        node = body[reject]
                        self.assertEqual((node["script"], node["runtime"], node["timeout"], node["mutates_checkout"]),
                                         ("material_prep", "uv", NO_DEADLINE, False))
                        self.assertEqual(node["with"], {"role": role["id"], "reason": f"$LOOP_PREV.{accept}.output.reason"})
                        self.assertEqual(node["output_format"]["required"],
                                         ["brief_file", "brief", "review_md", "repo_review_md", "reason", "lang_line"])
                        self.assertEqual(role["depends_on"], [reject])
                    else:
                        node = body[reject]
                        self.assertEqual((node["script"], node["runtime"], node["timeout"], node["mutates_checkout"]),
                                         ("rejects" if lid in LEDGER_REJECTS else "reject", "uv", NO_DEADLINE, False))
                        want = ({**LEDGER_REJECTS[lid], "prev": f"$LOOP_PREV.{accept}.output.ok"} if lid in LEDGER_REJECTS
                                else {"reason": f"$LOOP_PREV.{accept}.output.reason"})
                        self.assertEqual(node["with"], want)
                        self.assertEqual(node["output_format"]["required"], ["reason", "lang_line"])   # 言語の 1 行は BriefCase
                    self.assertIn("reason", node["output_format"]["properties"])
                    self.assertNotIn("with", role)
                    self.assertIn(reject, role["depends_on"])
                    text = (COMMANDS / f"{role['command']}.md").read_text(encoding="utf-8")
                    self.assertNotIn("$LOOP_PREV", text)
                    self.assertNotIn("$INPUTS", text)
                    section = text.partition(f"{rolekit.REJECT_HEADING}\n\n")[2]
                    self.assertTrue(section.startswith(lead), section[:80])
                    self.assertIn(f"```text\n${reject}.output.reason\n```", section)

    def test_reject_script_returns_the_reason_as_is(self):
        """reject は受けた理由を 1 字も変えずに返す（1 周目は空の字。改行・引用符・バッククォートも残す）。言語の 1 行も返す（BriefCase）"""
        r = Run(self)
        for reason in ("", '一行目 "引用" `x`\n二行目'):
            with self.subTest(reason=reason):
                self.assertEqual(r.returned("reject", reason=reason), {"reason": reason, "lang_line": rolekit.lang_line({})})

    def test_third_fresh_spec_role_reads_every_reject_of_the_loop(self):
        """仕様の役が 2 回拒まれた後の 3 回目: rejects の返りの reason に 1 回目と 2 回目の拒否が古い順に在る（#345）。
        1 周目は空の字。言語の 1 行も reject と同じに返す"""
        r = Run(self)
        r.returned("intake")
        self.assertEqual(r.returned("rejects", **LEDGER_REJECTS["spec-loop"]),
                         {"reason": "", "lang_line": rolekit.lang_line({}), "resubmit": False, "brief": ""})
        reasons = [r.returned("spec_accept", role="write", reply=reply)["reason"]
                   for reply in ({"requirements": []}, {"acceptance": []})]
        self.assertTrue(all(reasons) and reasons[0] != reasons[1], reasons)
        got = r.returned("rejects", **LEDGER_REJECTS["spec-loop"])["reason"]
        self.assertEqual(got, rolekit.rejects_text(reasons))
        self.assertLess(got.index(reasons[0]), got.index(reasons[1]))

    def test_spec_resubmit_returns_only_the_rejected_fields(self):
        """#571: 拒まれた周の次（prev が前の周の受け付けの ok の false）は、rejects が出し直しの役の短い指示書（最後の拒否の文・
        受け付けが合わせた前の答えの控え）を書いて resubmit: true を返す。受け付けは出し直しの返答（直す欄だけ）を前の答えの控えと
        欄ごとに合わせてから照らし、通った答えは 1 回で書いた答えと同じ。resume で輪が 1 周目から回り直した時（prev が空）は
        1 回目の役（resubmit: false）"""
        r = Run(self)
        r.returned("intake")
        (r.repo / "test_spec_mean.txt").write_text(SPEC_TEST_FILE, encoding="utf-8")
        first = r.returned("spec_accept", role="write", reply={**SPEC, "acceptance": [{**SPEC["acceptance"][0], "name": "無い名"}]})
        self.assertFalse(first["ok"])
        head = r.returned("rejects", **LEDGER_REJECTS["spec-loop"], prev="false")
        self.assertIs(head["resubmit"], True)
        brief = pathlib.Path(head["brief"]).read_text(encoding="utf-8")
        self.assertIn(first["reason"], brief)
        self.assertIn(str(rolekit.candidate_path(r.judge, ja.SPEC_ROLES["write"])), brief)
        self.assertIs(r.returned("rejects", **LEDGER_REJECTS["spec-loop"], prev="")["resubmit"], False)
        got = r.returned("spec_accept", role="write", reply="null", fix_reply={"acceptance": SPEC["acceptance"]})
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual(json.loads((r.judge / f"{ja.SPEC_ROLES['write']}.json").read_text(encoding="utf-8")), SPEC)

    def test_spec_resubmit_after_fixing_only_the_file_returns_nothing(self):
        """受け入れテストのファイルが読めない拒否は、役がファイルを書けば直る。欄を直さない出し直しの {} は前の答えのまま全体を
        照らし直して通る（出し直しの回を空で使わない）"""
        r = Run(self)
        r.returned("intake")
        first = r.returned("spec_accept", role="write", reply=SPEC)
        self.assertFalse(first["ok"])
        self.assertIn("読めない", first["reason"])
        (r.repo / "test_spec_mean.txt").write_text(SPEC_TEST_FILE, encoding="utf-8")
        got = r.returned("spec_accept", role="write", reply="null", fix_reply={})
        self.assertTrue(got["ok"], got["reason"])
        self.assertEqual(json.loads((r.judge / f"{ja.SPEC_ROLES['write']}.json").read_text(encoding="utf-8")), SPEC)

    def test_materials_are_eleven_loops_one_per_command(self):
        material_loops = sorted(lid.removesuffix("-loop") for lid in loops() if lid.removesuffix("-loop") in MATERIALS)
        self.assertEqual(material_loops, sorted(MATERIALS))
        commands = sorted(p.stem.removeprefix("material-") for p in COMMANDS.glob("material-*.md"))
        self.assertEqual(commands, sorted(MATERIALS))
        by = nodes()
        for name in MATERIALS:
            with self.subTest(material=name):
                self.assertEqual(by[name]["command"], f"material-{name}")
                self.assertEqual(by[f"{name}-loop"]["when"], f"$material-route.output.{ja.route_key(name)} == true")

    def test_material_role_continues_its_previous_round(self):
        """素材の役の出し直し（J81「同じ会話で 3 回まで」）: fresh_context: false の loop_group は前の周の会話を次の周の体の AI の節へ
        渡すが（dag-executor.ts の lastSequentialSession）、並んだ層（2 つ以上の節の層）では渡さない。だから体の最初の層は
        支度の script 1 本で、役はその後の層に 1 本で置き、context: fresh を持たない。周をまたぐ会話は筋書きで渡らない（K6）ので、
        ここは形だけを縛る（修正の tdd-loop の試験と同じ）"""
        by = loops()
        for name in MATERIALS:
            with self.subTest(material=name):
                loop = by[f"{name}-loop"]["loop_group"]
                self.assertIs(loop["fresh_context"], False)
                body = {n["id"]: n for n in loop["nodes"]}
                first = [nid for nid, n in body.items() if not set(n.get("depends_on", ())) & set(body)]
                self.assertEqual(first, [f"{name}-prep"], "最初の層に 2 本以上を置くと Archon は会話を切る")
                role = body[name]
                self.assertEqual(role["depends_on"], [f"{name}-prep"])
                self.assertNotIn("context", role, "2 周目の役は前の周の自分の会話を継ぐ")

    def test_role_names_are_the_libs(self):
        """役の名の持ち主は lib（MATERIAL_ROLES・SPEC_ROLES）。YAML の route の欄と with: の role がそれに合う"""
        by = nodes()
        route = by["material-route"]["output_format"]
        keys = {ja.route_key(r) for r in ja.MATERIAL_ROLES} | {"reason"}
        self.assertEqual((set(route["required"]), set(route["properties"])), (keys, keys))
        for script, table in (("material_prep", ja.MATERIAL_ROLES), ("material_accept", ja.MATERIAL_ROLES),
                              ("spec_accept", ja.SPEC_ROLES)):
            with self.subTest(script=script):
                roles = [n["with"]["role"] for n in by.values() if n.get("script") == script]
                self.assertEqual(sorted(roles), sorted(table))

    def test_stub_brief_files_are_the_libs(self):
        """stub の fixture が手で書く素材の役の材料のファイルの名（<役>-prep の brief_file）が持ち主 material_brief_file と同じ字"""
        seen = []
        for path in sorted((BLOCK / "fixtures").glob("*.stubs.yaml")):
            stubs = yaml.safe_load(path.read_text(encoding="utf-8"))
            for role in ja.MATERIAL_ROLES:
                if f"{role}-prep" in stubs:
                    seen.append(role)
                    with self.subTest(fixture=path.name, role=role):
                        self.assertEqual(pathlib.PurePath(stubs[f"{role}-prep"]["brief_file"]).name,
                                         ja.material_brief_file(role))
        self.assertTrue(seen, "照らす stub が 1 つも無い")


class RoleSettingsTest(unittest.TestCase):
    def test_roles_keep_the_old_settings(self):
        by = nodes()
        roles = {nid for nid, n in by.items() if any(k in n for k in scan.ROLE_KINDS)}
        self.assertEqual(sorted(roles), sorted([*ROLES, *(f"{r}-fix" for r in RESUBMIT_ROLES)]))   # 出し直しの役の形は test_loop_sessions
        for nid, (model, effort, tools, sandbox, read_only, context, skills, plugins) in ROLES.items():
            n = by[nid]
            with self.subTest(role=nid):
                self.assertEqual(launchgroups.default_of(n["model"]), (model, effort))
                self.assertNotIn("effort", n)
                self.assertEqual(n["settingSources"], ["user"])
                self.assertEqual(n["allowed_tools"], tools)
                self.assertEqual(n["sandbox"], sandbox)
                self.assertEqual(n.get("context"), context)
                self.assertEqual((n.get("skills"), n.get("plugins")), (skills, plugins))
                self.assertEqual(n.get("mutates_checkout"), False if read_only else None)
                self.assertEqual(n["idle_timeout"], NO_DEADLINE)
                self.assertTrue((COMMANDS / f"{n['command']}.md").is_file(), n["command"])

    def test_purpose_role_does_not_see_the_prior_run(self):
        """目的の役に前の run の判断（前の失敗の行・前の判定）を見せない（持ち主の決め premises-purpose の当て方）"""
        role = nodes()["purpose"]
        text = (COMMANDS / "purpose.md").read_text(encoding="utf-8") + json.dumps(role.get("with", {}), ensure_ascii=False)
        for word in ("prior_failures", "prior-failures", "judgment", "PRIOR"):
            self.assertNotIn(word, text)

    def test_roles_that_reach_outside_carry_the_query_rule(self):
        """外へ問い合わせられる役（Bash か web の道具を持つ役）の指示書は、検索語の規律（元 adapter.query_rule が lib/agents/judge.md の
        写しから切り出して system prompt に足した塊）を字のまま持つ"""
        lines = (ROOT / "lib" / "agents" / "judge.md").read_text(encoding="utf-8").splitlines()
        start = next(i for i, line in enumerate(lines) if line.startswith("- **検索語に対象の名前を載せるな。**"))
        end = next(i for i in range(start + 1, len(lines) + 1) if i == len(lines) or not lines[i].startswith("  - "))
        rule = "\n".join(lines[start:end])
        by = nodes()
        for nid, (_, _, tools, *_rest) in ROLES.items():
            if {"Bash", *WEB} & set(tools):
                with self.subTest(role=nid):
                    self.assertIn(rule, (COMMANDS / f"{by[nid]['command']}.md").read_text(encoding="utf-8"))

    def test_dropped_sentences_are_back(self):
        """元の役の指示書から落ちていた文: 仕様の審査役の前付け（judge）・局所レビューの無人の読み替え（元 rolekit.skill_overlay が
        末尾に載せた全文）。仕様の役の実装に触れない決まりは tests/workflows/prompt_contracts.json が照らす"""
        judge = agent_body("judge")
        self.assertIn(judge, (COMMANDS / "spec-review.md").read_text(encoding="utf-8"))
        unattended = (ROOT / "bin" / "_lib" / "borrow" / "unattended.md").read_text(encoding="utf-8")
        self.assertTrue((COMMANDS / "material-local-review.md").read_text(encoding="utf-8").endswith(unattended),
                        "局所レビューの指示書の末尾に bin/_lib/borrow/unattended.md の全文")

    def test_viewpoint_readers_read_review_md(self):
        for name in REVIEW_READERS:
            with self.subTest(command=name):
                self.assertIn(".output.review_md", (COMMANDS / f"{name}.md").read_text(encoding="utf-8"))


class ModelGroupsRunTest(unittest.TestCase):
    """役のノードは `model: '@wf-<群>'` で群を指し、呼ぶ人の `--model @wf-<群>=<別名>` はその群のノードだけの模型と effort を替える。
    止めた Archon の `workflow run --dry-run` の trace が、ノードごとに解いた模型と effort を言う。源か bun が無ければ見送る"""

    GROUP = "@wf-judge-core"
    TO = "@wf-judge-materials"

    @classmethod
    def resolved(cls, *extra: str) -> dict:
        """仕様の段に入る筋書き spec-on の stub で judge を dry-run し、ノードの id → (模型, effort)（解いた物がある節だけ）"""
        fixture = yaml.safe_load((BLOCK / "fixtures" / "spec-on.stubs.yaml").read_text(encoding="utf-8"))
        with archon.tree(["judge"]) as tree:
            stubs = tree.parent / "spec-on.stubs.yaml"
            stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")}, allow_unicode=True),
                             encoding="utf-8")
            done = archon.archon(tree, "workflow", "run", NAME, "--dry-run", "--exec-code", "--stubs", str(stubs), "--json", *extra,
                                 "--cwd", str(tree))
        trace = json.JSONDecoder().raw_decode(done.stdout.lstrip())[0]["trace"]
        return {n["nodeId"]: (n["resolution"].get("model"), n["resolution"].get("effort")) for n in trace if "resolution" in n}

    @classmethod
    def setUpClass(cls):
        try:
            cls.default = cls.resolved()
            cls.rebound = cls.resolved("--model", f"{cls.GROUP}={cls.TO}")
        except unittest.SkipTest as skip:
            cls.skipped = str(skip)
            return
        cls.skipped = ""

    def test_named_group_rebinds_only_its_nodes(self):
        if self.skipped:
            self.skipTest(self.skipped)
        group_of = {nid: n["model"] for nid, n in nodes().items() if "model" in n}
        reached = {nid: group for nid, group in group_of.items() if nid in self.default}
        self.assertIn(self.GROUP, reached.values())
        self.assertGreaterEqual(len(set(reached.values())), 3, reached)
        for nid, group in reached.items():
            with self.subTest(node=nid, group=group):
                self.assertEqual(self.default[nid], launchgroups.default_of(group))
                self.assertEqual(self.rebound[nid], launchgroups.default_of(self.TO if group == self.GROUP else group))


class FixtureTest(unittest.TestCase):
    """筋書き（fixtures/）を Archon の workflow test で回す。配線だけを見る（振る舞いは下の子のプロセスの試験）"""

    @classmethod
    def setUpClass(cls):
        try:
            with archon.tree(["judge"]) as tree:
                done = archon.archon(tree, "workflow", "test", NAME, "--json")
                checked = archon.archon(tree, "validate", "workflows", "--json", "--cwd", str(tree))
        except unittest.SkipTest as skip:
            cls.skipped = str(skip)
            return
        cls.skipped = ""
        text = done.stdout
        cls.results = {pathlib.PurePosixPath(r["fixture"]).name.removesuffix(".stubs.yaml"): r
                       for r in json.JSONDecoder().raw_decode(text[text.index("{"):])[0]["results"]}
        validated = json.loads(checked.stdout)["results"]
        cls.issues = {r["workflowName"]: [issue for issue in r["issues"] if archon.counted(issue)] for r in validated}

    def check(self, name):
        if self.skipped:
            self.skipTest(self.skipped)
        result = self.results[name]
        self.assertTrue(result["pass"], result)
        self.assertEqual((result["missingStubs"], result["unusedStubs"]), ([], []), result)

    def test_validate_has_no_issue(self):
        if self.skipped:
            self.skipTest(self.skipped)
        self.assertEqual(self.issues.get(NAME), [])

    def test_every_fixture_has_a_test(self):
        if self.skipped:
            self.skipTest(self.skipped)
        self.assertEqual(sorted(self.results), sorted(name.removeprefix("test_fixture_").replace("_", "-")
                                                      for name in dir(self) if name.startswith("test_fixture_")))

    def test_fixture_pass(self):
        self.check("pass")

    def test_fixture_bad_request(self):
        self.check("bad-request")

    def test_fixture_judge_gave_up(self):
        self.check("judge-gave-up")

    def test_fixture_no_open_units(self):
        self.check("no-open-units")

    def test_fixture_spec_on(self):
        self.check("spec-on")

    def test_fixture_world_offline(self):
        self.check("world-offline")

    def test_fixture_material_peer_stop(self):
        self.check("material-peer-stop")

    def test_fixture_rejudge(self):
        self.check("rejudge")


# ---------------------------------------------------------------- script の振る舞い（子のプロセス）
KEY = "stats.py mean: 分母が len(xs) - 1"
REQUEST = [{"where": "stats.py", "text": "mean([1, 2, 3]) が 2 でなく 3 を返す。test_mean_of_three が赤"}]


def empty_reply(**over) -> dict:
    """開いた単位の無い判定役の返答（judge_output の規則の全部を空で通る形）"""
    return {"units": [], "questions": [], "framing": "依頼の行は 1 つの根に当たる", "one_shot": "直す物は無い",
            "materials_missing": [], "carried_r1": [], "one_shot_closes": [], "precedents": [], **over}


def open_reply(**over) -> dict:
    """開いた単位 1 つ（KEY）の判定役の返答（judge_output の規則を通る形）"""
    unit = {"key": KEY, "label": "block", "disposition": "do-now",
            "reason": f"事実: {KEY}。反証: 意図の取り違えを当たったが、関数名とテストが逆を期待する",
            "origin_analysis": "写し間違いの形", "why_chain": ["テストが境界の値を試していない"],
            "class_query": {"how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
                            "counts": "defects", "total": 1}}
    precedent = {"key": KEY, "problem": "数列の算術平均を求める", "source": "Python の statistics.mean の文書の節",
                 "verdict": "adopt", "reason": "分母はデータ点の数 len(xs)"}
    return empty_reply(units=[unit], framing="依頼の行は stats.py の mean の分母の取り違え", one_shot="mean の分母を len(xs) に直す",
                       one_shot_closes=[KEY], precedents=[precedent], **over)


class Run:
    """1 run の置き場と作業ツリー。script を子のプロセスで走らせる"""

    def __init__(self, case: unittest.TestCase, request=REQUEST, **start):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        base = pathlib.Path(tmp.name)
        self.repo = base / "repo"
        self.head = committed_copy(self.repo, SEED)
        self.artifacts = base / "artifacts"
        self.artifacts.mkdir()
        (self.artifacts / "entry").mkdir()
        request_file = ""
        if request is not None:
            request_file = str(base / "request.json")
            pathlib.Path(request_file).write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        record = {"run_id": RUN_ID, "base_rev": self.head, "test_cmd": "", "adapter": "", "final_gate": "always", "thickness": "",
                  "request_file": request_file, "features_cut": ["judge_verify"], "answers": [], "gates": "",
                  "input": {"base": {"rev": self.head, "from": "head", "name": "", "label": "HEAD"}, "head_rev": self.head,
                            "diff": {"empty": True, "files": 0, "stat": ""}, "requests": len(request or []),
                            "request_file": request_file, "pr": None, "spec": False}}
        record.update(start)
        (self.artifacts / "entry" / "start.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        self.start = json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "entry/start.json"})
        self.case = case

    @property
    def judge(self) -> pathlib.Path:
        return self.artifacts / "judge"

    def run(self, script: str, *, objection: str = "", start=None, launcher=(sys.executable,), root=ROOT, env=None,
            **inputs) -> subprocess.CompletedProcess:
        """env は試験が意図して子へ渡す名（hermetic.child_env の overrides へ回す。親の環境は継がない）"""
        named = {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN_ID, "WORKS_FACTORY_ROOT": str(root),
                 "PYTHONDONTWRITEBYTECODE": "1", "INPUTS_START": self.start if start is None else start,
                 "INPUTS_BASELINE": "", "INPUTS_OBJECTION": objection, "INPUTS_PRIOR_FAILURES": ""}
        named.update({f"INPUTS_{k.upper()}": v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in inputs.items()})
        env = hermetic.child_env(**{**named, **(env or {})})
        return subprocess.run([*launcher, str(SCRIPTS / f"{script}.py")], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")

    def returned(self, script: str, **kw) -> dict:
        done = self.run(script, **kw)
        self.case.assertEqual(done.returncode, 0, f"{script}: {done.stdout}{done.stderr}")
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        self.case.assertEqual(len(lines), 1, f"{script} の標準出力は JSON 1 行: {done.stdout}")
        return json.loads(lines[0])

    def resolve(self, ptr) -> pathlib.Path:
        self.case.assertEqual((ptr["type"], ptr["run_id"]), ("archon_artifact", RUN_ID))
        return self.artifacts / ptr["path"]


def verdict_shape(case: unittest.TestCase, out: dict) -> None:
    """返す節の返りが output_format に合う（欄がちょうど在り、型が合う）"""
    fmt = nodes()["verdict"]["output_format"]
    case.assertEqual(sorted(out), sorted(fmt["required"]))
    case.assertIsInstance(out["ready"], bool)
    case.assertIsInstance(out["stop_reason"], str)
    case.assertIsInstance(out["units"], list)
    for unit in out["units"]:
        case.assertEqual(sorted(unit), ["id", "paths", "summary"])
    case.assertIn(out["rejudge_verdict"], (None, "採る", "退ける", "一部採る"))


JSON_TYPES = {"boolean": bool, "string": str, "array": list, "object": dict, "null": type(None), "integer": int}


def node_inputs(node: dict) -> dict:
    """節の with: を子のプロセスの入力にする。上流の出力を指す値は空の字、指図（from/if_skipped）は if_skipped の値"""
    inputs = {}
    for key, value in node.get("with", {}).items():
        if isinstance(value, dict):
            inputs[key] = json.dumps(value.get("if_skipped"))
        elif isinstance(value, str) and value.startswith("$"):
            inputs[key] = ""
        else:
            inputs[key] = value
    return inputs


def write_purpose(r: Run) -> None:
    (r.judge / "purpose.json").write_text(json.dumps({"purpose_text": "平均が正しい値を返す", "source": "①PR 説明",
                                                      "known_weaknesses": [], "source_files": []}, ensure_ascii=False), encoding="utf-8")


class ScriptReturnsTest(unittest.TestCase):
    def test_every_script_node_prints_one_line_of_its_output_format(self):
        """output_format を持つ script の節は、それに合う JSON を 1 行出す（出さないと Archon は節を落とし、輪の中なら輪ごと落ちる）。
        YAML の並びで 1 つの置き場に走らせ、上流の出力は空の字で渡す。世界の解の段からは、輪が回る形（止めの控えが無く目的の文が在る）の
        新しい置き場で走らせる"""
        r = Run(self)
        for nid, node in nodes().items():
            if "script" not in node or "output_format" not in node:
                continue
            if nid == "world-intake":
                r = Run(self)
                r.returned("intake")
                write_purpose(r)
            with self.subTest(node=nid):
                fmt = node["output_format"]
                out = r.returned(node["script"], **node_inputs(node))
                self.assertEqual(sorted(set(fmt["required"]) - set(out)), [], out)
                self.assertEqual(sorted(set(out) - set(fmt["properties"])), [], out)
                for key, value in out.items():
                    kinds = fmt["properties"][key].get("type")
                    if kinds is not None:
                        kinds = [kinds] if isinstance(kinds, str) else kinds
                        self.assertIsInstance(value, tuple(JSON_TYPES[k] for k in kinds), key)


class HeadDepthTest(unittest.TestCase):
    """run の頭の深さ（issue #441）: 支度の機械の止め・受け付けの引用の照らし・返す節の欄。根拠が引けない依頼は標準"""

    LIGHT = {"why": "原因と直す行が名指されている",
             "items": [{"item": 1, "unknown": "無し", "cause_quote": "2 でなく 3 を返す", "where": "stats.py:4-5",
                        "code_quote": "return sum(xs) / (len(xs) - 1)"}]}

    def opened(self, **start) -> Run:
        r = Run(self, **{"test_cmd": "./junit-suite.sh", **start})
        self.assertTrue(r.returned("intake")["go"])
        return r

    def record(self, r: Run) -> dict:
        return json.loads((r.judge / headdepth.RECORD).read_text(encoding="utf-8"))

    def test_prep_stops_without_waking_the_role(self):
        for name, start in (("no test command", {"test_cmd": ""}), ("thickness", {"thickness": "標準"}),
                            ("design only", {"design_only": "true"})):
            with self.subTest(name):
                r = self.opened(**start)
                out = r.returned("head_depth_prep")
                self.assertEqual((out["go"], out["brief_file"]), (False, ""), out)
                self.assertEqual(self.record(r)["depth"], "標準")

    def test_prep_writes_the_brief_and_a_standard_record(self):
        r = self.opened()
        out = r.returned("head_depth_prep")
        self.assertTrue(out["go"], out)
        self.assertIn("stats.py", pathlib.Path(out["brief_file"]).read_text(encoding="utf-8"))
        self.assertEqual(self.record(r)["depth"], "標準")

    def test_accept_takes_a_quoted_light_reply(self):
        r = self.opened()
        r.returned("head_depth_prep")
        out = r.returned("head_depth_accept", reply=self.LIGHT)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual(self.record(r)["depth"], "軽量")

    def test_accept_refuses_a_quote_the_code_lacks_and_keeps_standard(self):
        r = self.opened()
        r.returned("head_depth_prep")
        bad = {**self.LIGHT, "items": [{**self.LIGHT["items"][0], "code_quote": "return 0"}]}
        out = r.returned("head_depth_accept", reply=bad)
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertIn("code_quote", out["reason"])
        doc = self.record(r)
        self.assertEqual(doc["depth"], "標準")
        self.assertIn("code_quote", doc["why"])

    def test_accept_records_the_tier_and_row_kinds(self):
        """段は行の一番重い種類から受け付けが引いて控えに書き、行は unknown つきのまま残る。引用の欠けた返答は拒まれ標準のまま"""
        shape = {"item": 2, "unknown": "形", "cause_quote": "どちらの形にするか", "where": "stats.py:4-13",
                 "code_quote": "def clamp(x, lo, hi):"}
        rows = [*REQUEST, {"where": "stats.py", "text": "clamp の戻りをどちらの形にするか決める"}]
        r = Run(self, request=rows, test_cmd="./junit-suite.sh")
        self.assertTrue(r.returned("intake")["go"])
        r.returned("head_depth_prep")
        reply = {"why": "1 行目は直す所が見え、2 行目は形を選ぶ", "items": [self.LIGHT["items"][0], shape]}
        out = r.returned("head_depth_accept", reply=reply)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        doc = self.record(r)
        self.assertEqual((doc["depth"], doc["why"]), ("重厚", reply["why"]))
        self.assertEqual([(it["item"], it["unknown"]) for it in doc["items"]], [(1, "無し"), (2, "形")])
        bad = {**reply, "items": [self.LIGHT["items"][0], {**shape, "cause_quote": "書いていない字"}]}
        out = r.returned("head_depth_accept", reply=bad)
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertIn("cause_quote", out["reason"])
        self.assertEqual(self.record(r)["depth"], "標準")

    def test_accept_records_group_choices_without_changing_the_tier(self):
        """群の選び（groups）は段の照らしが通った後に住処の口で照らして控える。上げ・下げは向きつきで残り、表に無い群の行は既定に
        戻って訳を持つ。groups が外れても段は変わらず（軽量のまま）、引用の外れた返答では段が標準になり groups は空"""
        r = self.opened()
        r.returned("head_depth_prep")
        up = {"group": "@wf-judge-core", "model": "opus", "effort": "max", "why": "多段の根拠を読む"}
        stray = {"group": "@wf-nope", "model": "opus", "effort": "high", "why": "表に無い群"}
        down = {"group": "@wf-fix-writers", "model": "sonnet", "effort": "low", "why": "直す所が一行で見える"}
        out = r.returned("head_depth_accept", reply={**self.LIGHT, "groups": [up, stray, down]})
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        doc = self.record(r)
        self.assertEqual(doc["depth"], "軽量")
        by_group = {g["group"]: g for g in doc["groups"]}
        self.assertEqual(len(doc["groups"]), 3)
        self.assertEqual((by_group["@wf-judge-core"]["direction"], by_group["@wf-judge-core"]["fallback"]), ("上げ", ""))
        self.assertEqual((by_group["@wf-fix-writers"]["direction"], by_group["@wf-fix-writers"]["effort"]), ("下げ", "low"))
        self.assertEqual(by_group["@wf-fix-writers"]["default"], {"model": "sonnet", "effort": "high"})
        self.assertTrue(by_group["@wf-nope"]["fallback"])
        self.assertEqual(by_group["@wf-nope"]["why"], "表に無い群")
        out = r.returned("head_depth_accept", reply={**self.LIGHT, "groups": []})
        self.assertEqual((self.record(r)["depth"], self.record(r)["groups"], out["ok"]), ("軽量", [], True))
        out = r.returned("head_depth_accept", reply={**self.LIGHT, "groups": [up],
                                                    "items": [{**self.LIGHT["items"][0], "code_quote": "return 0"}]})
        self.assertFalse(out["ok"], out)
        doc = self.record(r)
        self.assertEqual((doc["depth"], doc["groups"]), ("標準", []))
        fmt = nodes()["head-depth"]["output_format"]
        self.assertEqual(fmt["required"], ["why", "items", "groups"])
        self.assertFalse(fmt["additionalProperties"])
        self.assertEqual(fmt["properties"]["groups"]["items"]["required"], ["group", "model", "effort", "why"])

    def test_role_kinds_are_the_lib_kinds(self):
        """役の出力の型の unknown の enum が lib/headdepth.py の UNKNOWNS で、head-depth の出力に depth の欄が無い
        （YAML は lib を引けないので、試験が結ぶ）"""
        fmt = nodes()["head-depth"]["output_format"]
        item = fmt["properties"]["items"]["items"]
        self.assertEqual(item["properties"]["unknown"]["enum"], list(headdepth.UNKNOWNS))
        self.assertEqual(item["required"], ["item", "unknown", "cause_quote"])
        self.assertNotIn("depth", fmt["properties"])
        self.assertNotIn("depth", fmt["required"])

    def test_refused_reply_keeps_the_role_why(self):
        """引用の外れた返答を拒んだ後の控えの why に、拒みの訳と役の訳の両方が残る（段は標準）"""
        r = self.opened()
        r.returned("head_depth_prep")
        bad = {**self.LIGHT, "items": [{**self.LIGHT["items"][0], "code_quote": "return 0"}]}
        r.returned("head_depth_accept", reply=bad)
        doc = self.record(r)
        self.assertEqual(doc["depth"], "標準")
        self.assertIn(headdepth.NOT_ACCEPTED.split("（")[0], doc["why"])
        self.assertIn("code_quote", doc["why"])
        self.assertIn(f"役の訳: {self.LIGHT['why']}", doc["why"])

    def test_verdict_returns_the_recorded_depth(self):
        r = self.opened()
        r.returned("head_depth_prep")
        r.returned("head_depth_accept", reply=self.LIGHT)
        out = r.returned("verdict")
        verdict_shape(self, out)
        self.assertEqual((out["depth"], out["depth_why"]), ("軽量", self.LIGHT["why"]))

    def test_verdict_without_record_is_standard(self):
        r = self.opened()
        out = r.returned("verdict")
        self.assertEqual((out["depth"], out["depth_why"]), ("標準", headdepth.NO_RECORD))
        out = r.returned("verdict", objection="分母は正しい")
        self.assertEqual((out["depth"], out["depth_why"]), ("標準", headdepth.REJUDGE_WHY))

    def test_heavy_record_does_not_cut_the_verify(self):
        cut = "機能の切り替えで切"
        r = self.opened()
        self.assertIn(cut, r.returned("verify", stage="prep")["reason"])
        r.returned("head_depth_prep")
        scope = {**self.LIGHT["items"][0], "unknown": "範囲"}
        out = r.returned("head_depth_accept", reply={**self.LIGHT, "items": [scope], "why": "公開の約束を変える"})
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        self.assertEqual(r.returned("verdict")["depth"], "重厚")
        self.assertNotIn(cut, r.returned("verify", stage="prep")["reason"])
        named = self.opened(features_off=["judge_verify"], features_cut=["judge_verify"])
        headdepth.write(named.judge, headdepth.record("重厚", "設計の選びが要る"))
        self.assertIn(cut, named.returned("verify", stage="prep")["reason"])
        light = self.opened()
        headdepth.write(light.judge, headdepth.record("軽量", "x"))
        self.assertIn(cut, light.returned("verify", stage="prep")["reason"])

    def test_verify_waits_on_the_head_depth(self):
        """裏取りの支度は頭の深さの役の終わりを待つ（控えを読む前に走らない）。head-depth-loop が verify-prep の祖先に在る"""
        got = nodes()
        seen, todo = set(), ["verify-prep"]
        while todo:
            for dep in got[todo.pop()].get("depends_on") or []:
                if dep not in seen:
                    seen.add(dep)
                    todo.append(dep)
        self.assertIn("head-depth-loop", seen)
        self.assertIn("head-depth-loop", got["diagnose-prep"]["depends_on"])
        self.assertEqual(got["diagnose-prep"]["trigger_rule"], "all_done")

    def test_prompt_states_the_lib_limits(self):
        """役の指示書が受け付けの引用の字数の下限と where の行の範囲の上限を lib の値のまま書く（指示書は lib を引けない）"""
        text = (ROOT / "workflows" / "judge" / "commands" / "head-depth.md").read_text(encoding="utf-8")
        self.assertIn(f"{headdepth.cite.QUOTE_MIN} 字以上", text)
        self.assertIn(f"{headdepth.WHERE_SPAN} 行まで", text)

    def test_depth_words_are_the_lib_words(self):
        """役の返答と判定の出力の深さの enum、lib を読めない時の判定の返り、計画の単位ごとの深さの enum は lib/depth.py の語
        （YAML と lib を読めない script は lib を引けないので、試験が結ぶ）"""
        words = [depth.LIGHT, depth.STANDARD]
        got = nodes()
        self.assertEqual(got["verdict"]["output_format"]["properties"]["depth"]["enum"], list(depth.HEADS))
        self.assertEqual(list(depth.HEADS), [depth.LIGHT, depth.STANDARD, depth.HEAVY])
        self.assertIn(f'"depth": "{depth.STANDARD}"', (SCRIPTS / "verdict.py").read_text(encoding="utf-8"))
        plan = {n["id"]: n for n in walk(yaml.safe_load((ROOT / "workflows" / "plan" / "works-factory-plan.yaml")
                                                         .read_text(encoding="utf-8"))["nodes"])}
        self.assertEqual(plan["plan"]["output_format"]["properties"]["depth"]["items"]["properties"]["depth"]["enum"], words)


class UvLaunchTest(unittest.TestCase):
    def test_read_only_script_leaves_a_python_project_untouched(self):
        """Archon は runtime: uv の節を作業ツリーで `uv run <script>` で起こす。対象が pyproject.toml を持つと、宣言（# /// script）の
        無い script は uv が対象の環境（.venv・uv.lock）を作業ツリーに作り、mutates_checkout: false の節が落ちる"""
        r = Run(self)
        (r.repo / "pyproject.toml").write_text('[project]\nname = "target"\nversion = "0"\n', encoding="utf-8")
        git(r.repo, "add", "pyproject.toml")
        git(r.repo, "commit", "-q", "-m", "pyproject")
        done = r.run("intake", launcher=("uv", "run", "--quiet"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(git(r.repo, "status", "--porcelain", "--ignored"), "")
        for script in SCRIPTS.glob("*.py"):
            with self.subTest(script=script.name):
                self.assertTrue(script.read_text(encoding="utf-8").startswith("# /// script\n"))


class StopPathFilesMixin:
    def assert_pointers_filled(self, r: Run, out: dict):
        """指し札の先と公開の隣のファイルが在り、空でない（Archon は節の終わりに先が在って空でないかを照らす）"""
        verdict_shape(self, out)
        for field in ("judgment", "purpose", "world", "spec", "out_of_purpose"):
            if out[field] is None:
                continue
            path = r.resolve(out[field])
            self.assertTrue(path.is_file() and path.stat().st_size > 0, f"{field}: {path}")
        folder = r.resolve(out["judgment"]).parent
        for name in PUBLIC:
            path = folder / name
            self.assertTrue(path.is_file() and path.stat().st_size > 0, name)
            json.loads(path.read_text(encoding="utf-8"))
        judgment = json.loads(r.resolve(out["judgment"]).read_text(encoding="utf-8"))
        for key in ("units", "questions", "framing", "one_shot", "materials_missing", "carried_r1", "one_shot_closes", "precedents"):
            self.assertIn(key, judgment)
        purpose = json.loads(r.resolve(out["purpose"]).read_text(encoding="utf-8"))
        self.assertEqual(sorted(purpose), ["known_weaknesses", "purpose_text", "source", "source_files"])


class AcceptLoopTest(unittest.TestCase):
    def test_diagnose_accept_gives_up_on_the_third_reject(self):
        """受け付けが拒めば 3 回まで出し直す: 1・2 回目は done: false、3 回目は done: true で、拒否の控えに 3 行。
        標準出力の done を until_bash の字に入れて走らせると、3 回目だけ終了の値 0"""
        r = Run(self)
        self.assertTrue(r.returned("intake")["go"])
        bad = empty_reply(units=[{"key": KEY, "label": "bogus"}])
        until = nodes()["diagnose-loop"]["loop_group"]["until_bash"]
        exits = []
        for n in (1, 2, 3):
            out = r.returned("diagnose_accept", reply=bad)
            self.assertEqual((out["ok"], out["done"]), (False, n == 3), out)
            self.assertTrue(out["reason"])
            script = until.replace("$diagnose-accept.output.done", shlex.quote(json.dumps(out["done"])))
            exits.append(subprocess.run(["sh", "-c", script], env=hermetic.child_env()).returncode)
        self.assertEqual([e == 0 for e in exits], [False, False, True])
        self.assertEqual(len(json.loads((r.judge / "rejects-diagnose.json").read_text(encoding="utf-8"))), 3)

    def test_accepted_judgment_is_written_with_its_public_neighbours(self):
        r = Run(self)
        r.returned("intake")
        out = r.returned("diagnose_accept", reply=empty_reply())
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        judgment = json.loads((r.judge / "judgment.json").read_text(encoding="utf-8"))
        self.assertEqual(judgment["units"], [])
        returned = r.returned("verdict")
        self.assertEqual(r.resolve(returned["judgment"]), r.judge / "judgment.json")
        for name in PUBLIC:
            self.assertTrue((r.judge / name).is_file(), name)

    def test_judge_that_changed_the_tree_is_refused(self):
        r = Run(self)
        r.returned("intake")
        (r.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        out = r.returned("diagnose_accept", reply=empty_reply())
        self.assertFalse(out["ok"], out)

    def test_cache_left_by_a_material_role_is_not_the_judges(self):
        """素材の役が残したキャッシュ（git が無視するファイル）は、判定役を起こす前の写しに入り、判定役が変えた物と数えない。
        判定役を起こした後に増えた物は拒む"""
        r = Run(self)
        r.returned("intake")
        premises_and_purpose(r)
        r.returned("material_route")
        (r.repo / "__pycache__").mkdir()
        (r.repo / "__pycache__" / "stats.cpython-312.pyc").write_bytes(b"cache")
        self.assertTrue(r.returned("diagnose_prep")["go"])
        out = r.returned("diagnose_accept", reply=empty_reply())
        self.assertTrue(out["ok"], out)
        (r.repo / "__pycache__" / "test_stats.cpython-312.pyc").write_bytes(b"cache")
        out = r.returned("diagnose_accept", reply=empty_reply())
        self.assertFalse(out["ok"], out)


SPEC = {"requirements": [{"key": "R1", "text": "mean は要素の数で割る"}],
        "acceptance": [{"key": "A1", "requirement": "R1", "file": "test_spec_mean.txt", "name": "test_mean_divides_by_count",
                        "run": "grep -q test_mean_divides_by_count test_spec_mean.txt"}],
        "out_of_scope": []}
SPEC_TEST_FILE = "test_mean_divides_by_count\n# Given 1, 2, 3 の並び\n# When mean を呼ぶ\n# Then 2 を返す\n"


REVIEW = {"faces": [], "faces_none": "要件と受け入れ条件の抜け・曖昧さ・範囲の外を見たが無かった",
          "reason": "要件 R1 は受け入れ条件 A1 が試し、範囲の外の物は無い"}


def spec_run(case: unittest.TestCase) -> Run:
    """仕様の段を選んだ run で、仕様を書き・審査し、関所に見せる所まで"""
    r = Run(case)
    record = json.loads((r.artifacts / "entry" / "start.json").read_text(encoding="utf-8"))
    record["input"]["spec"] = True
    (r.artifacts / "entry" / "start.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    case.assertTrue(r.returned("intake")["spec"])
    (r.repo / "test_spec_mean.txt").write_text(SPEC_TEST_FILE, encoding="utf-8")
    case.assertTrue(r.returned("spec_accept", role="write", reply=SPEC)["ok"])
    review = r.returned("spec_accept", role="review", reply=REVIEW)
    case.assertEqual((review["ok"], review["revise"]), (True, False), review)
    case.assertTrue(r.returned("spec_ask")["ask"])
    return r


class SpecFreezeTest(unittest.TestCase):
    spec_run = spec_run

    def test_stop_word_is_a_human_stop(self):
        r = self.spec_run()
        out = r.returned("spec_freeze", answer={"decision": "stop", "text": "要らない"})
        self.assertFalse(out["go"])
        self.assertEqual(r.returned("verdict")["stop_reason"], "human:spec-gate")

    def test_request_flag_is_a_request_stop(self):
        r = self.spec_run()
        out = r.returned("spec_freeze", answer={"decision": "reject", "text": "request: 札"})
        self.assertFalse(out["go"])
        self.assertEqual(r.returned("verdict")["stop_reason"], "request:spec-gate")

    def test_roles_after_approval_take_the_spec_tests_as_given(self):
        """仕様の役が書いた受け入れテストは承認の後の写しに入り、後ろの読むだけの役（前提の実測）が変えた物と数えない"""
        r = self.spec_run()
        self.assertTrue(r.returned("spec_freeze", answer={"decision": "approve", "text": ""})["go"])
        where = "test_spec_mean.txt: test_mean_divides_by_count"
        reply = {"constraints": [{"text": f"{where} は承認の時点で exit 0", "kind": "仮説", "measured_how": "測っていない"}]}
        out = r.returned("premises_accept", reply=reply)
        self.assertTrue(out["ok"], out)

    def test_approval_freezes_hashes_and_exit_codes(self):
        r = self.spec_run()
        out = r.returned("spec_freeze", answer={"decision": "approve", "text": ""})
        self.assertTrue(out["go"], out)
        spec = json.loads((r.judge / "spec.json").read_text(encoding="utf-8"))
        row = spec["acceptance"][0]
        self.assertRegex(row["sha256"], "^[0-9a-f]{64}$")
        self.assertEqual(row["exit_at_approval"], 0)

    def test_approval_in_users_env_leaves_the_marker(self):
        """#504: 利用者が明示した run では、受け入れ条件のコマンドを利用者の HOME・XDG に戻して走らせ、メイングラフの run の置き場に
        印（userenv.RAN_FILE）を残す（印の置き場を立てずに戻すと、戻さずに止まって仕様を固められない）"""
        r = self.spec_run()
        home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        out = r.returned("spec_freeze", answer={"decision": "approve", "text": ""},
                         env={userenv.RECORD: userenv.record({"HOME": str(home), userenv.OPT_IN: "1"})})
        self.assertTrue(out["go"], out)
        spec = json.loads((r.judge / "spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["acceptance"][0]["exit_at_approval"], 0)
        self.assertTrue(userenv.ran(r.artifacts))


class StopPathTest(StopPathFilesMixin, unittest.TestCase):
    def test_bad_request_stops_before_any_role_and_still_fills_pointers(self):
        r = Run(self, request=[{"where": "stats.py"}])
        out = r.returned("intake")
        self.assertFalse(out["go"])
        returned = r.returned("verdict")
        self.assertFalse(returned["ready"])
        self.assertEqual(returned["stop_reason"], "works:request")
        self.assert_pointers_filled(r, returned)

    def test_gave_up_judgment_still_fills_pointers(self):
        r = Run(self)
        r.returned("intake")
        for _ in range(3):
            r.returned("diagnose_accept", reply=empty_reply(units=[{"key": KEY, "label": "bogus"}]))
        returned = r.returned("verdict")
        self.assertEqual((returned["ready"], returned["stop_reason"]), (False, "works:judge"))
        self.assert_pointers_filled(r, returned)

    def test_spec_stop_still_fills_pointers(self):
        r = spec_run(self)
        r.returned("spec_freeze", answer={"decision": "stop", "text": ""})
        returned = r.returned("verdict")
        self.assertEqual(returned["stop_reason"], "human:spec-gate")
        self.assert_pointers_filled(r, returned)

    def test_no_open_units_is_not_a_stop(self):
        r = Run(self)
        r.returned("intake")
        premises_and_purpose(r)
        r.returned("diagnose_accept", reply=empty_reply())
        returned = r.returned("verdict")
        self.assertEqual((returned["ready"], returned["stop_reason"], returned["units"]), (False, "", []))
        self.assert_pointers_filled(r, returned)


class RejudgeTest(unittest.TestCase):
    OBJECTION = "単位 1 は clamp の欠陥と同じ根で、分けると二度直す"

    def test_rejudge_without_a_first_judgment_stops(self):
        r = Run(self)
        out = r.returned("intake", objection=self.OBJECTION)
        self.assertEqual((out["go"], out["mode"]), (True, "rejudge"))
        prep = r.returned("rejudge_prep", objection=self.OBJECTION)
        self.assertFalse(prep["go"])
        returned = r.returned("verdict", objection=self.OBJECTION)
        self.assertEqual(returned["stop_reason"], "works:rejudge-session")

    def test_rejudge_with_a_first_judgment_writes_its_brief(self):
        r = Run(self)
        r.returned("intake")
        r.returned("diagnose_accept", reply=empty_reply())
        r.returned("verdict")
        prep = r.returned("rejudge_prep", objection=self.OBJECTION)
        self.assertTrue(prep["go"], prep)
        self.assertEqual(pathlib.Path(prep["brief_file"]), r.artifacts / "rejudge" / "brief.md")
        self.assertIn(self.OBJECTION, (r.artifacts / "rejudge" / "brief.md").read_text(encoding="utf-8"))

    def test_verify_merge_waits_on_the_judge_mode(self):
        """判定の裏取りのまとめは判定の道（intake の mode が judge）の時だけ走る。再審の道で 1 回目の判定の置き場に触らない守りは
        script の枝でなく YAML の when が持つ。go は見ない（go 偽でも judge の道なら all_done でまとめが走る）"""
        node = nodes()["verify-merge"]
        self.assertEqual(node.get("when"), "$intake.output.mode == 'judge'")
        self.assertEqual(node["trigger_rule"], "all_done")

    def test_diagnose_prep_waits_on_the_judge_mode(self):
        """判定の材料を組む段は判定の道（intake の mode が judge）の時だけ走る。diagnose_prep は入力 objection を読まないので、
        再審の道で判定の材料を組まない守りはこの when だけが持つ"""
        node = nodes()["diagnose-prep"]
        self.assertEqual(node.get("when"), "$intake.output.go == true && $intake.output.mode == 'judge'")
        self.assertEqual(node["trigger_rule"], "all_done")


def premises_and_purpose(r: Run) -> None:
    """前提と目的の段が受け付けた控えを置く（判定の前の段が通った姿）"""
    (r.judge / "premises.json").write_text(json.dumps({"constraints": []}), encoding="utf-8")
    write_purpose(r)


HYGIENE = {"role": "hygiene", "materials": {"hygiene": {"status": "found", "count": 1, "detail": "1 件"}},
           "reply": {"findings": [{"where": "test_stats.py", "text": "使わない import が残る"}]}}
OUTSIDE = [{"source": "衛生", "where": "test_stats.py", "why_outside": "凍結した目的の外の衛生の所見"}]


class JudgedVerdictTest(StopPathFilesMixin, unittest.TestCase):
    def judged(self) -> Run:
        r = Run(self)
        r.returned("intake")
        premises_and_purpose(r)
        (r.judge / ja.material_file(HYGIENE["role"])).write_text(json.dumps(HYGIENE, ensure_ascii=False), encoding="utf-8")
        out = r.returned("diagnose_accept", reply=open_reply(out_of_purpose=OUTSIDE))
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        return r

    def test_open_unit_is_ready_with_its_out_of_purpose_rows(self):
        r = self.judged()
        out = r.returned("verdict")
        self.assertEqual((out["ready"], out["stop_reason"]), (True, ""), out)
        self.assertEqual([u["id"] for u in out["units"]], [KEY])
        self.assertEqual(out["units"][0]["paths"], ["stats.py"])
        self.assertEqual(out["units"][0]["summary"], open_reply()["units"][0]["reason"])
        import judge_accept
        self.assertEqual(json.loads((r.judge / judge_accept.STRUCTURE_DROPPED_FILE).read_text(encoding="utf-8")),
                         {"units": [], "paths": []}, "L-W08: 捨てたパスの記録を判定の置き場に残す")
        self.assertIsNone(out["rejudge_verdict"])
        self.assertEqual(r.resolve(out["out_of_purpose"]), r.judge / "out-of-purpose.json")
        carried = json.loads((r.judge / "out-of-purpose.json").read_text(encoding="utf-8"))
        self.assertEqual(carried["rounds"]["1"][0]["found"][0]["from"], "p1.hygiene")
        self.assert_pointers_filled(r, out)

    def test_world_stage_without_rows_returns_no_world(self):
        """世界の解の段が行を 1 つも出さなかった run は world を null にする（Archon は空のファイルを指す札で節を落とす）"""
        r = self.judged()
        (r.judge / "world.jsonl").write_text("", encoding="utf-8")
        ja.worldmark.write(r.judge, status="ok", reason="", world_file=str(r.judge / "world.jsonl"), classes=0, dropped=0)
        out = r.returned("verdict")
        self.assertIsNone(out["world"])
        self.assert_pointers_filled(r, out)

    def test_world_stage_with_a_broken_row_returns_no_world(self):
        """行が worldmark.rows で読めない world.jsonl は world に渡さない（読み手は渡された行を確かめ直さない）"""
        r = self.judged()
        (r.judge / "world.jsonl").write_text("{]\n", encoding="utf-8")
        ja.worldmark.write(r.judge, status="ok", reason="", world_file=str(r.judge / "world.jsonl"), classes=1, dropped=0)
        out = r.returned("verdict")
        self.assertIsNone(out["world"])
        self.assert_pointers_filled(r, out)

    def test_missing_premises_or_purpose_stops_even_with_an_accepted_judgment(self):
        """前提・目的の段が落ちた run（控えを書く前に終わる）は、受けた判定が在っても ready にしない"""
        for name, word in (("premises.json", "works:premises"), ("purpose.json", "works:purpose")):
            with self.subTest(missing=name):
                r = self.judged()
                (r.judge / name).unlink()
                out = r.returned("verdict")
                self.assertEqual((out["ready"], out["stop_reason"], out["units"]), (False, word, []), out)
                self.assert_pointers_filled(r, out)

    def test_purpose_prep_failure_writes_a_stop(self):
        r = Run(self)
        r.returned("intake")
        (r.judge / "premises.json").write_text(json.dumps({"constraints": []}), encoding="utf-8")
        (r.judge / "start.json").write_text("{broken", encoding="utf-8")
        self.assertFalse(r.returned("purpose_prep")["go"])
        self.assertEqual(json.loads((r.judge / "stop.json").read_text(encoding="utf-8"))["stop_reason"], "works:purpose")


class RejudgedVerdictTest(unittest.TestCase):
    OBJECTION = f"{KEY} は分母でなく呼び手の渡す並びの誤り"
    UNITS = [{"key": KEY, "label": "block", "reason": "異議を当たったが、呼び手の並びは正しく、分母の取り違えが残る"}]

    def test_rejudge_returns_its_own_units_and_keeps_the_first_judgment(self):
        r = Run(self)
        r.returned("intake")
        premises_and_purpose(r)
        self.assertTrue(r.returned("diagnose_accept", reply=open_reply())["ok"])
        self.assertTrue(r.returned("verdict")["ready"])
        first = (r.judge / "judgment.json").read_bytes()
        self.assertTrue(r.returned("rejudge_prep", objection=self.OBJECTION)["go"])
        reply = {"verdict": "退ける", "new_facts": "test_stats.py の呼び手を読み、並び [1, 2, 3] を渡していることを確かめた",
                 "units": self.UNITS, "reason": "異議は呼び手の誤りと言うが、呼び手は正しい"}
        out = r.returned("rejudge_accept", reply=reply)
        self.assertEqual((out["ok"], out["done"]), (True, True), out)
        returned = r.returned("verdict", objection=self.OBJECTION)
        verdict_shape(self, returned)
        self.assertEqual(r.resolve(returned["judgment"]), r.artifacts / "rejudge" / "judgment.json")
        self.assertEqual((returned["ready"], returned["stop_reason"], returned["rejudge_verdict"]), (True, "", "退ける"), returned)
        self.assertEqual([(u["id"], u["summary"]) for u in returned["units"]], [(KEY, self.UNITS[0]["reason"])])
        self.assertEqual((r.judge / "judgment.json").read_bytes(), first, "再審は 1 回目の判定を上書きしない")
        self.assertEqual(json.loads((r.artifacts / "rejudge" / "premises.json").read_text(encoding="utf-8")),
                         json.loads((r.judge / "premises.json").read_text(encoding="utf-8")))


class BaselineTest(unittest.TestCase):
    def test_local_checks_come_from_the_baseline(self):
        """素材 local_checks（元の p0.local_checks）は入力 baseline の先の素材を写す: 修正前のテストが通れば clean、赤なら found。
        baseline の無い run は走っていない（not_run）"""
        clean = {"status": "clean", "count": 0, "checked": "宣言の一式を対象の根で走らせた: exit 0"}
        found = {"status": "found", "count": 1, "detail": "test_mean_of_three が赤"}
        for material in (clean, found, None):
            with self.subTest(status=material and material["status"]):
                r = Run(self)
                r.returned("intake")
                premises_and_purpose(r)
                r.returned("material_route")
                inputs = {}
                if material:
                    rel = "test-gate/base/baseline.json"
                    ja.baseline_red.write_baseline(r.artifacts / rel, suite="", test_cmd="", rev=r.head, exit=0, cases=[],
                                                   material=material)
                    inputs["baseline"] = {"type": "archon_artifact", "run_id": RUN_ID, "path": rel}
                self.assertTrue(r.returned("diagnose_prep", **inputs)["go"])
                got = json.loads((r.judge / "materials.json").read_text(encoding="utf-8"))["local_checks"]
                self.assertEqual(got, material or {"status": "not_run", "reason": "走っていない（どのノードも返していない）"})


class PriorFailuresTest(unittest.TestCase):
    def test_no_prior_failures_reach_intake_as_empty_text(self):
        """前の失敗の持ち越しが無い run: start の出力の null の欄 prior_failures を、止めた Archon は include の入力に空の字で渡す
        （tests/shared/test_archon_contract.py が縛る）。入口はそれを「無い」と読んで進む"""
        r = Run(self)
        self.assertTrue(r.returned("intake", prior_failures="")["go"])

    def test_container_rows_and_the_input_rows_both_reach_the_brief(self):
        """前の失敗の行は入口が 1 度だけ置く: 依頼の容器の prior_failures と入力 prior_failures の行の両方が判定役の材料に届く"""
        from_container = {"where": "受け付け", "text": "容器の側の前の失敗の印"}
        from_input = {"where": "受け付け", "text": "入力の側の前の失敗の印"}
        r = Run(self, request={"findings": REQUEST, "prior_failures": [from_container]})
        (r.artifacts / "prior.json").write_text(json.dumps([from_input], ensure_ascii=False), encoding="utf-8")
        ptr = {"type": "archon_artifact", "run_id": RUN_ID, "path": "prior.json"}
        self.assertTrue(r.returned("intake", prior_failures=ptr)["go"])
        premises_and_purpose(r)
        r.returned("material_route")
        prep = r.returned("diagnose_prep", prior_failures=ptr)
        self.assertTrue(prep["go"], prep)
        text = pathlib.Path(prep["brief_file"]).read_text(encoding="utf-8")
        for row in (from_container, from_input):
            self.assertIn(row["text"], text)


class MaterialGiveUpTest(unittest.TestCase):
    def test_diagnose_prep_builds_the_brief_from_the_remaining_materials(self):
        """素材の 1 本の受け付けが諦めても、支度は残りの素材のファイルで材料を組む（諦めた素材が在るので判定役は起こさない）"""
        r = Run(self)
        r.returned("intake")
        write_purpose(r)
        r.returned("material_route")
        for _ in range(3):
            out = r.returned("material_accept", role="provenance", reply={"not": "a provenance reply"})
            self.assertFalse(out["ok"])
        self.assertTrue(out["done"])
        prep = r.returned("diagnose_prep")
        self.assertFalse(prep["go"])
        self.assertTrue((r.judge / "diagnose-brief.md").is_file())
        self.assertEqual(r.returned("verdict")["stop_reason"], "works:material")


class VerdictNeverFailsTest(unittest.TestCase):
    """返す節は落ちない: 壊れた入力でも終了の値 0 で、output_format に合う ready: false と訳を返す（線は落ちた返す節の先へ進めない）"""

    def test_broken_inputs(self):
        cases = {
            "start が JSON でない": dict(start="{not json"),
            "指し札の先が無い": dict(start=json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "nowhere/start.json"})),
            "judge が空": {},
        }
        for what, kw in cases.items():
            with self.subTest(case=what):
                r = Run(self)
                (r.artifacts / "judge").mkdir(exist_ok=True)
                out = r.returned("verdict", **kw)
                verdict_shape(self, out)
                self.assertFalse(out["ready"])
                self.assertTrue(out["stop_reason"])

    def test_lib_out_of_reach(self):
        """lib を読めなくても、判定と目的の指し札の先を lib と同じ空の形で置いて ready: false を返す"""
        for objection, here, stop in (("", "judge", ja.JUDGE_STOP), ("修正役の異議", "rejudge", ja.stopby.REJUDGE)):
            with self.subTest(here=here):
                r = Run(self)
                out = r.returned("verdict", objection=objection, root=r.artifacts / "no-repository")
                verdict_shape(self, out)
                self.assertEqual((out["ready"], out["stop_reason"]), (False, stop))
                self.assertEqual(json.loads(r.resolve(out["judgment"]).read_text(encoding="utf-8")), ja.EMPTY_JUDGMENT)
                self.assertEqual(json.loads(r.resolve(out["purpose"]).read_text(encoding="utf-8")), ja.EMPTY_PURPOSE)
                self.assertEqual(r.resolve(out["judgment"]).parent.name, here)

    def test_broken_judgment_file(self):
        r = Run(self)
        r.returned("intake")
        (r.judge / "judgment.json").write_text("{broken", encoding="utf-8")
        out = r.returned("verdict")
        verdict_shape(self, out)
        self.assertFalse(out["ready"])
        self.assertTrue(out["stop_reason"])


# ---------------------------------------------------------------- 役の指示書の写しの台帳（issue #119 の直し 6。K9）
# 元: 今の works（raiki61/claude-plugins の 2aa7c66cf7abe1fe09699ac2942d107123214168。pack.json の works.commit）。
# 指示書ごとに、元のパス・元の sha256・持ち主が許した直し（元の字, 写しの字）を持つ。直しは前から当てると元が写しになる順に
# 並べ、試験は後ろから逆に当てる。元の名の指示書の無い役は、元の文を組んだ関数と行を元として書く（issue #119 の D6）。
# 素材集めの 11 本・再審・仕様の 3 本の元は、prep が描いた本線の指示書（graphloops の写し gl-prompts）と blk-spec/prompts/。
# 元の commands/<役>.md の短い指示（「指示書を Read で読め」）は、写しの頭の文に直した直しとして持つ

# 外への問い合わせの決まりの塊。元は包みが system prompt に足した物（works/.shared/core/adapter.py:1538 query_rule_block が
# QUERY_RULE_LEAD（:294）と works/.shared/core/agents/judge.md:16-22 を組む）。写しは役の指示書の頭に字のまま置く（PR #76 の 9）。
# 塊は写しの lib/agents/judge.md から seat.query_rule が切り出す
QUERY_RULE_LEAD = ("外のサービスへ問い合わせる時の決まり（works の包みより。役への直の指示。Agent "
                  "で子を起こすなら、子への指示に下の塊をそのまま含めよ——子にはこの決まりが届かない）:")
QUERY_RULE = seat.query_rule()
QUERY_HEAD = QUERY_RULE_LEAD + "\n" + QUERY_RULE + "\n\n---\n\n"
# 役の定義の本文。元は rolekit.with_role_definition（rolekit.py:208）が描いた指示書の頭に「## お前の役の定義（<役>）」の見出しで置いた
JUDGE_BODY, INVESTIGATOR_BODY, INSPECTOR_BODY, COLD_READER_BODY = (
    agent_body(role) for role in ("judge", "investigator", "inspector", "cold-reader"))


# 拒否の理由の節。元は rolekit.with_reject（works/.shared/core/rolekit.py:219-223）と material.prep（works/blk-material/lib/material.py:388-391）が
# 指示書の頭に置いた段で、写しは輪の頭の拒否の節か、素材の輪では <役>-prep の出力を結ぶ（PR #100）。見出しの後ろの 1 文（下の 4 つ）だけが役ごとに違う
REJECT_LEAD = ("## 前の回の受け付けが拒んだ理由\n\n前の回の返答は受け付けで拒まれた。下の理由のところを直した返答を丸ごと出し直せ"
               "（直した所だけを返すな）。")
FIRST_IS = "下の理由が空なら、これは 1 回目の返答である。"
FIRST_NOT = "下の理由が空なら、これは 1 回目の返答で、拒まれていない。"
FIRST_SKIP = "下の理由が空なら、これは 1 回目の返答で、この節は読み飛ばしてよい:"
FIRST_NOFIX = "下の理由が空なら、これは 1 回目の返答で、直す所は無い。"


def reject_section(node: str, first: str, src: str = "reject") -> str:
    return f"{REJECT_LEAD}{first}\n\n```text\n${node}-{src}.output.reason\n```\n\n---\n\n"


# 素材集めの役の頭: 元の works/blk-material/commands/<役>.md の指示を、材料のファイル（brief_file）を読む形に直した物
MATERIAL_REREAD = ("頭の「前の回の受け付けが拒んだ理由」の節の理由が空でなければ、お前の前の返答は受け付けで拒まれている。"
                   "そこに書かれた理由のところを直した返答を丸ごと出し直せ（直した所だけを返すな）。\n")
TOOLS_READ = "道具は Read・Grep・Glob だけ。"
RO_GH_RULE = ("Bash は sandbox の中で走り、網は閉じている（どの宛先にも出られない）。"
             "GitHub の PR とリポジトリは読むだけの口 `works-gh` を素の名で、1 "
             "つだけのコマンドとして打て（例 `works-gh pr view 12 -R "
             "OWNER/REPO`）。通るのは pr list・pr view・pr diff（-R "
             "<OWNER/REPO> 付き）と repo view <OWNER/REPO> だけで、"
             "この形だけが sandbox の外で走る。`gh` の名や変数に入れた口のパス、"
             "パイプ・`&&`・`;`・`$(…)`、前に置く変数の代入を付けると sandbox "
             "の中で走り、網に出られない。issue・検索・Web のページは "
             "WebFetch・WebSearch で読め。書く gh は包みが止める。")
TOOLS_GH = "道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。" + RO_GH_RULE
TOOLS_TMP = ("道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。"
            "Bash は sandbox の中で走り、写しは一時の置き場（mktemp -d）に作れ。"
            "対象の作業ツリーへの書き込みは包みが止める。")
KEEP_TREE = ("対象の作業ツリー・HEAD・枝・git が無視するファイルを 1 "
            "文字も変えるな（受け付けは、起こす前に取った作業ツリーの姿と今の姿を比べ、"
            "変わっていれば拒む。同じ時に別の素材集めの役も走っている）。\n")


def material_head(role: str, who: str, node: str, tools: str, *more: str, review: bool = True) -> str:
    """素材集めの役の写しの頭（材料を読め・拒否の理由・道具・観点の正本・本線の指示書の見出し）"""
    head = (f"お前は{who}。graphloops の節 {node} を、下の本線の指示書のとおりに行う。\n\n"
            f"1. まず材料 `${role}-prep.output.brief_file` を Read で読め。下の指示書の「［材料: 〜］」は、そのファイルの同じ名の節の値"
            "（対象差分・変更ファイルの一覧・観点の正本のパスと、この run の値。engine と同じ描き方で機械が描いた物）。"
            "末尾の『条件に当たらない』の節も読め。\n"
            + "2. " + MATERIAL_REREAD + "3. " + tools + KEEP_TREE + "".join(f"{n}. {m}\n" for n, m in enumerate(more, 4)) + "\n")
    if review:
        head += (f"---\n\n観点の正本: `${role}-prep.output.review_md` を Read せよ（対象リポジトリ側: `${role}-prep.output.repo_review_md`。"
                 "空でなければそれも Read せよ）。ラベルと観点はここが正本。\n\n")
    return head + f"---\n\n## 本線の指示書（graphloops の節 {node}）\n\n"


def slots(*names: str) -> list:
    """engine の差し込みの印 {{名}}（{{?名}} は在れば）を、材料のファイルの節の名 ［材料: 名］ に（値は材料のファイルが持つ）"""
    return [("{{" + n + "}}", f"［材料: {n.lstrip('?')}］") for n in names]


# 所見の場所の書き方（works/blk-material/lib/material.py:160 LOCATION_NOTE。prep が :396 で全部の素材の役の末尾に足した）
LOCATION_NOTE = ("## 所見の場所の書き方（works の受け付けより）\n"
                "\n"
                "所見の場所（`where`）の `<パス>:<行>` は、"
                "作業ツリーの今のファイルの行番号で書け。差分のファイル（patch）"
                "の中の行番号を書くな——差分の行はファイルの行と違い、人が場所を開けない。"
                "差分で見つけた所見は、ファイルを読める役ならそのファイルをRead "
                "して行を確かめてから書け（読めない役は、"
                "確かめられない行番号を書かずにパスと関数名などで書け）。受け付けは、"
                "在るファイルの行の外を指す場所を拒んで出し直させる。")
# 必須のレンズの読み替え 2 つ（material.py:129 LENS_RETRY_NOTE・:142 LENS_FORK_NOTE。prep が :395 で局所レビューだけに足した）
LENS_RETRY_NOTE = ("## 必須のレンズの呼び出しの失敗（works の受け付けより。上の指示書の読み替え）\n"
                  "\n"
                  "上の『skill の呼び出し自体が失敗したら…material を "
                  "awaiting_human にして理由を書け』は、`required` が false "
                  "のレンズにだけ当てる。`required` が true のレンズの呼び出しが失敗したら、"
                  "この回のうちに起こし直して `invoked: true` を書け。起こせないまま返すなら "
                  "`failed` に理由を書き、material を awaiting_human "
                  f"にするな——受け付けが拒んで同じ会話で起こし直させ、拒みが {rolekit.GIVE_UP_AFTER} 回に届いた時と、"
                  "レンズのプラグインが隔離した設定に無い時だけ人に渡す。\n"
                  "\n"
                  "上の『直前の周から対象差分にロジック変更が無いなら /simplify "
                  "の再実行は持ち越してよい』は狭めて読め: `simplify_carried: true` "
                  "を受けるのは、この周の頭に固めた版が前の周の頭の版と 1 ファイルも違わない周だけ。"
                  "どれかのファイルが変わった周（ロジックでない変更でも）と 1 周目は "
                  "`/simplify` を起こして `invoked: true` を書け。")
LENS_FORK_NOTE = ("## /code-review の返し方（works の受け付けより。上の指示書の読み替え）\n"
                 "\n"
                 "/code-review は別の会話（fork）で走る。所見を本文で返したら、それを "
                 "/code-review の行の `items` に写せ（どの所見も落とさない）。"
                 "Skill の結果が『Skill execution completed』"
                 "だけで所見の本文が無い時は、fork が所見を別の口（返答の道具）"
                 "に書いて親に届かなかった形で、works の受け付けがこの行を『見ていない』と報告に出す。"
                 "どちらでも /code-review を起こし直すな（同じ形で返って、時間だけ掛かる）。"
                 "本文が無かった行は `items` を空、`invoked: true` にして、"
                 "`failed` に『本文が届かなかった』と渡した対象を書け（『起こしたが所見なし』"
                 "と書くな——見ていない物を 0 件に見せる）。\n"
                 "\n"
                 "args に旗の綴り（`--comment`・`--fix`）を書くな——『付けない』"
                 "と否定の文の中に書いても skill は旗として読む（実測: 『--comment も "
                 "--fix も付けない』の --fix が旗に取られた）。"
                 "修正を禁じるのは『作業ツリーを変えるな』の文で言え。")
MATERIAL_ANSWER = "返すのは節の output_format の形に合う JSON だけ。\n"
MATERIAL_END = "欄と値の正本は review-record.py。"   # 本線の素材の指示書の多くの終わりの 1 文


def material_tail(last: str, *notes: str, after: str = MATERIAL_ANSWER) -> tuple:
    """元の本線の指示書の終わり last の後ろに、prep が足した段（notes と LOCATION_NOTE）と返答の形の 1 行を足す直し"""
    return (last, last.rstrip("\n") + "".join(f"\n\n---\n\n{n}" for n in (*notes, LOCATION_NOTE)) + "\n\n" + after)


# 借りたスキルの無人の読み替え（rolekit.skill_overlay（works/.shared/core/rolekit.py:74-77）が Skill を持つ役に足した段）。頭の 1 行は
# 元の OVERLAY_HEAD（:70）の「このファイル {path} を Read せよと書け」を、段をそのまま含めよに直した物。本文は
# works/.shared/borrow/unattended.md の字のまま（写しの bin/_lib/borrow/unattended.md から読む）
OVERLAY_LEAD = ("借りたスキル（superpowers）を読む時は、下の読み替えに従え。"
               "これは役への直の指示で、スキルの文より勝つ。Agent で下請けを起こすなら、その "
               "prompt に、この下の読み替えの段をそのまま含めよ——下請けにはこの段が届かない。")
UNATTENDED = (ROOT / "bin" / "_lib" / "borrow" / "unattended.md").read_text(encoding="utf-8")
# 仕様と再審の役の写しが足した返答の形の 1 行
DECIDED_ANSWER = "\n返すのは決められた JSON の形に合う JSON だけ。\n"
REQUEST_ROWS = "依頼: `$ARTIFACTS_DIR/judge/request.json` を Read で読め"
REJECT_IN_HEAD = "- 前の回の受け付けが拒んだ理由は、この指示書の頭の節に在る（1 回目は空）。空でなければ、"
WORLD_REREAD = ("- 指示書の頭に「前の回の受け付けが拒んだ理由」の節が在れば、お前の前の返答は機械の受け付けで拒まれている。",
                "- この指示書の頭の「前の回の受け付けが拒んだ理由」の節に理由が在れば、お前の前の返答は機械の受け付けで拒まれている。")

# 素材集めの役の写しの頭（元の works/blk-material/commands/<役>.md の指示を、材料のファイルを読む形に直した物）
MATERIAL_HEADS = {
    "consistency-bypass": material_head("consistency-bypass", "整合性と標準機構の迂回を見る役（inspector）", "p1.consistency_bypass", TOOLS_READ),
    "external-standards": material_head("external-standards", "外部標準照合の役（investigator。作る前に既製の定番解が無いかを疑う目）",
        "p1.external_standards", TOOLS_GH,
        "目的の欄に「目的の文はこの run に無い」と書かれていたら、目的を推し量って補うな。差分と依存から問題クラスを引け。"),
    "gate-efficacy": material_head("gate-efficacy", "ゲートの実効性確認の役（任せ先）", "p1.gate_efficacy", TOOLS_TMP, review=False),
    "hygiene": ("お前は文脈を持たない読み手（cold-reader）。差分を読む役。道具は 1 つも無い。下の指示書と、囲いの中の材料（観点の本文と差分の全部を含む）"
        "だけを読んで答えろ。\n\n" + MATERIAL_REREAD + "\n---\n\n"
        "観点の正本は `$hygiene-prep.output.review_md`（対象リポジトリ側: `$hygiene-prep.output.repo_review_md`。空なら無い）。"
        "お前は Read を持たないので、その「コード衛生観点」の節を下の材料に貼ってある。\n\n---\n\n## 本線の指示書（graphloops の節 p1.hygiene）\n\n"),
    "local-review": material_head("local-review", "局所レビューの役（skill と agent のレンズを起こして findings を集める）", "p1.local_review",
        "道具は Read・Grep・Glob・Bash・WebSearch・WebFetch と、skill を起こす Skill・agent を起こす Agent。" + RO_GH_RULE,
        "組み込みの skill（code-review・simplify・security-review）は Skill で、pr-review-toolkit の agent のレンズは Agent で、"
        "指示書が名指す物を 1 本ずつ起こせ。simplify は修正を禁じた形でだけ呼べ（指摘だけを返させる）。"),
    "main-path-observation": material_head("main-path-observation", "主経路の実行観測の役（任せ先）",
        "p1.main_path_observation", TOOLS_TMP, review=False),
    "prior-decisions": material_head("prior-decisions", "先行議論の突合の役（investigator）", "p0.prior_decisions", TOOLS_GH, review=False),
    "procedure-trace": material_head("procedure-trace", "手順トレースの役（investigator）", "p1.procedure_trace", TOOLS_GH),
    "provenance": material_head("provenance", "根拠の出所検査の役（任せ先）", "p1.provenance", TOOLS_TMP, review=False),
    "purpose-review": material_head("purpose-review", "目的の審査の役（inspector）", "p0.purpose_review", TOOLS_READ, review=False),
    "test-double-fidelity": material_head("test-double-fidelity", "代役の忠実性の役（任せ先）", "p1.test_double_fidelity", TOOLS_TMP, review=False),
}

# 今の works に元の無い役の指示書（写しの台帳を持たない）→ 出どころ
OWN_TEXTS = {"head-depth.md": "issue #441 の run の頭の深さの役"}
# 指示書の名 → (元のパス, 元の sha256, 許した直し)。本線の指示書の写しの置き場:
WORKS_GL = "works/.shared/core/gl-prompts/prompts/review-loop/"
COPIED_TEXTS = {
    # 判定役。元の名の指示書 blk-judge/commands/diagnose.md
    "diagnose.md": ("works/blk-judge/commands/diagnose.md", "90d37a8f85819931b05c7185387e00b44309647bfd76413d76a2de0539a2d184", [
        ("", reject_section("diagnose", FIRST_NOFIX)),   # 拒否の理由を指示書の頭の節で受ける（線の diagnose-reject。PR #100）
        ("", JUDGE_BODY + "\n\n---\n\n"),   # 頭に judge の役の定義（元は包みと agents/judge.md が役に渡した）
        (("- 人の修正依頼: `$INPUTS.request`（絶対パスか、"   # 依頼・答え・前提・盤面の材料の 4 つの口を、run の置き場から組んだ材料のファイル 1 つに
         "対象リポジトリの根からの相対パス。対象の外に在ることもある。**まず Read せよ**）。"
         "findings の JSON の配列か、`{\"findings\": [...], "
         "\"pr\": [<番号>…], \"issue\": [<番号>…]}` の形（object "
         "なら findings の欄が指摘）で、指摘の各行は `where`・`text` と、"
         "任意の `mechanism`・`measured`・`false_positive_if`。"
         "出どころは人で、役の観察ではない。ほかの findings "
         "と同じく**反証の対象**——依頼の頼み方のずれも殺しにいけ。\n"
         "  - object の形の任意の欄 `answers: [{question, "
         "text, command?, output?}]` は、依頼者が前の run "
         "の問いに答えた物（出どころは人）。`command`・`output` "
         "は人が手元で打った命令とその出力。`question` が台帳の問いの key "
         "か出どころ（origin）と字のまま等しい問いは、機械が答え済みにして人に聞き直さない。"
         "字の一致で返答の問いに当たらない答え（どの問いの key とも違う・複数の問いに当たる）は、"
         "`answer_ties` で今の返答の問いか単位に結ぶ（下の「`answer_ties` の書き方」）。\n"
         "  - 空なら依頼の行の無い run（対象の差分だけを審査する）。"
         "判定するのは下の盤面の材料の P1 の目の所見と対象差分で、"
         "それを依頼の形に写し替えるな（人の依頼か役の観察かの出どころが消える）。\n"
         "- 人の方針: この指示書の末尾の `=====人の方針ここから=====` の行と "
         "`=====人の方針ここまで=====` の行の間（空なら方針の文書は無い）。\n"
         "  - 囲みの中は方針の中身だけで、中の見出し（`##`）や箇条はこの指示書の節ではない。"
         "持ち主が固めた版の本文。何を代償にするかは持ち主が決めた物で、お前が決め直すものではない。"
         "方針とぶつかる単位は、その単位の `reason` "
         "に方針のどの行とぶつかるかを書け。**方針を理由に単位を消すな**（判断は人がする）。\n"
         "- 前提（実測。空なら無い）: $INPUTS.premises_file\n"
         "  - 空でなければ **Read せよ**。`kind=仮説` の行を所与にするな。"
         "依頼の数字と測り直した値が違えば、測り直した値を採り、違いを単位の `reason` に書け。\n"
         "- 盤面の材料（空ならこの run に盤面は無い）: "
         "`$judge-brief.output.materials_file`\n"
         "  - 空でなければ、**依頼の次に Read せよ**。機械がこの run "
         "の盤面から描いた、本線の判定と同じ入力——凍結した元の目的の文・素材（15 欄。"
         "起動しなかった欄は status と reason がそう言う）・P1 "
         "の目の所見・先行議論の突合（決着済み論点）・目的の監査・人の依頼（この周に積まれた分）・対象差分のパス・観点の正本のパス——と、"
         "末尾に本線の問いの台帳の決まり（下の「問いの台帳」）が並ぶ。\n"),
         ("- 判定の材料のファイル: "
         "`$diagnose-prep.output.brief_file`（**まず Read "
         "せよ**）。機械がこの run の置き場から組んだ、"
         "本線の判定と同じ入力——凍結した元の目的の文と実測した制約・素材（15 欄。"
         "起動しなかった欄は status と reason がそう言う）・P1 "
         "の目の所見・先行議論の突合（決着済み論点）・目的の監査・修正依頼の入口（依頼の行と、"
         "仕様の段が在れば受け入れ条件の行）・対象差分のパス・観点の正本のパス——と、"
         "頭に世界の解の行の節（在る時）、末尾に本線の問いの台帳の決まり（下の「問いの台帳」）、"
         "依頼と PR の題と本文（在る時）、依頼の answers（在る時）、前の run の行（在る時）が並ぶ。\n"
         "  - 修正依頼の入口の行は findings の型で、各行は "
         "`where`・`text` と、任意の "
         "`mechanism`・`measured`・`false_positive_if`。"
         "出どころは人で、役の観察ではない。ほかの findings "
         "と同じく**反証の対象**——依頼の頼み方のずれも殺しにいけ。\n"
         "  - 依頼の行が無い run は、対象の差分だけを審査する。判定するのは材料の P1 "
         "の目の所見と対象差分で、それを依頼の形に写し替えるな（人の依頼か役の観察かの出どころが消える）。\n"
         "  - 材料の「依頼の answers」の節は、依頼者が前の run "
         "の問いに答えた物（出どころは人。各行は `{question, text, "
         "command?, output?}`）。`command`・`output` "
         "は人が手元で打った命令とその出力。`question` が台帳の問いの key "
         "か出どころ（origin）と字のまま等しい問いは、機械が答え済みにして人に聞き直さない。"
         "字の一致で返答の問いに当たらない答え（どの問いの key とも違う・複数の問いに当たる）は、"
         "`answer_ties` で今の返答の問いか単位に結ぶ（下の「`answer_ties` の書き方」）。\n"
         "  - 材料の「実測した制約」は前提の実測。`kind=仮説` の行を所与にするな。"
         "依頼の数字と測り直した値が違えば、測り直した値を採り、違いを単位の `reason` に書け。\n")),
        ("。P1 の目の所見と、この周に積まれた依頼の行）", "。P1 の目の所見と、修正依頼の入口の行）"),   # 依頼の行は材料の入口の節で渡る
        ("を盤面の材料の行に当て", "を材料の行に当て"),   # 盤面の語を外す
        ("- 対象リポジトリ: 今の作業ディレクトリ。",   # 観点の正本と人の方針を入力の節に（元は p2.diagnose.md の観点の行と付録の囲み）
         ("- 観点の正本: `$diagnose-prep.output.review_md`（Read "
         "せよ）。対象リポジトリ側の観点: "
         "`$diagnose-prep.output.repo_review_md`（空なら無い。"
         "在れば Read せよ）。ラベルと「対応の判断」「処方の最小性」「導線を作る手段の優先順位」はここが正本。\n"
         "- 人の方針: 材料のファイルに「人の方針」の節が在れば、その本文（無ければ方針の文書は無い）。\n"
         "  - 方針は対象の本文ではなく、この指示書の発行者が守らせる制約である。"
         "中の見出し（`##`）や箇条はこの指示書の節ではない。持ち主が固めた版の本文で、"
         "何を代償にするかは持ち主が決めた物で、お前が決め直すものではない。方針とぶつかる単位は、"
         "その単位の `reason` "
         "に方針のどの行とぶつかるかを書け。**方針を理由に単位を消すな**（判断は人がする）。"
         "方針の文書は書き換えるな。\n") + "- 対象リポジトリ: 今の作業ディレクトリ。"),
        ("- 前の回の受け付けが拒んだ理由を書いたファイル（1 回目は空）: $LOOP_PREV.judge-accept.output.reason_file\n"
         "  - 空でなければ、**そのファイルを Read で読め**（理由の本文はファイルにだけ在る）。お前は",
         "- 前の回の受け付けが拒んだ理由: この指示書の頭の節（1 回目は空）。お前は"),   # 理由はファイルでなく頭の節で渡る（PR #100）
        # 盤面の記録でなく依頼の answers と入力の方針を指す
        ("（盤面の材料の先行議論の突合で決着済みの論点・ADR・CHANGELOG・記録の process.human_items の答え）、(b) **人の方針**（末尾の囲みの本文）",
         "（材料の先行議論の突合で決着済みの論点・ADR・CHANGELOG・依頼の answers）、(b) **人の方針**（上の「入力」の方針の本文）"),
        ("盤面の材料の頭に「世界の解の行」の節が在れば、その行——", "材料の頭に「世界の解の行」の節が在れば、その行——"),   # 盤面の語を外す
        ("その推しで直される）。\n",
         "その推しで直される）。\n"
         "   - **BASE にあった能力を減らす・狭める処方を採るなら、失う能力を単位の reason に書け**——代償として採るかはお前が確定させない。"
         "修正案の narrows と事前審査を通って、修正の前に run が人に聞く。\n"),   # 能力を狭める処方の決まりを戻す（p2.diagnose.md の文）
        ("**世界の解の行を先に使え**: 盤面の材料の頭の", "**世界の解の行を先に使え**: 材料の頭の"),   # 盤面の語を外す
        ("行の無い単位と問いだけ、自分で引け。\n",   # 受け付けが world の出どころを照らすことを役に言う
         "行の無い単位と問いだけ、自分で引け。受け付けは `world:<類の id>` が世界の解の行に無ければ拒む。\n"),
        ("- **盤面の材料が在る時**: kind・status・書ける欄の決まりは、材料のファイルの末尾の「問いの台帳」の段（本線の判定の指示書を盤面から描いた物。"
         "検証器の表から描いた kind の全部と、",
         "- kind・status・書ける欄の決まりは、材料のファイルの「問いの台帳」の段（本線の判定の指示書の同じ段を、検証器の表から描いた物。"
         "kind の全部と、"),   # 盤面の無い道が無くなったので、材料が在る時の 1 本に
        ("受け付けは本線と同じ規則で盤面が数える。\n- **盤面の材料が無い時**（ブロックを単独で回した）は下の箇条のとおり。\n",
         "受け付けは本線と同じ規則で数える。\n"),   # 同上（盤面の材料が無い時の 1 句を外す）
        ("- kind: fork（origin", "- kind の要点: fork（origin"),   # 下の箇条は材料の段の要約になった
        ("盤面の材料が無い時は、出どころになる素材も R1〜R4 も無いので premise・unverifiable・awaiting は使わない。",
         "awaiting（origin は素材名）・premise・unverifiable（origin は R1〜R4）は材料の段のとおり。"),   # 材料はいつも在るので 3 つの kind も使える
        ("- **問いは阻害要因を消さない**",
         "- 素材が awaiting_human なら、その素材を origin にする kind=awaiting の問いを必ず載せろ（受け付けは無い返答を拒む）。\n"
         "- **問いは阻害要因を消さない**"),   # 受け付けが拒む決まりを役に言う
        ("`materials_missing` は、盤面の材料が無いか、材料の全部の欄", "`materials_missing` は、材料の全部の欄"),   # 盤面の無い道を外す
        ("`carried_r1` は空の配列にせよ。\n\n## 付録: 人の方針（囲みの中が本文。上の「入力」の決まりで読め）\n\n"
         "=====人の方針ここから=====\n$INPUTS.policy_paste\n=====人の方針ここまで=====\n",
         "`carried_r1` は空の配列にせよ。\n"),   # 方針は材料のファイルの「人の方針」の節で渡る（PR #76 の 6）
    ]),
    # 判定の裏取りの束ね役。元の名の指示書は無い。元は works/blk-judge/blk-judge.yaml:313 の節 judge-verify の prompt の値（と行末の改行）
    "judge-verify.md": ("works/blk-judge/blk-judge.yaml:313", "f5ac6c890ba88e38059ec2cdc166888e1df0bfb7c4078cac2aa3c617bfcec782", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
    ]),
    # 素材集めの 11 本。元の名の指示書は blk-material/commands/<役>.md の短い指示だけで、役が読む本文は prep（material.py:376-405）が
    # 本線の指示書（gl-prompts の p0・p1）から描いた。その本線の指示書を元とし、prep が足した段と元の短い指示を直しとして持つ
    "material-consistency-bypass.md": (WORKS_GL + "p1.consistency_bypass.md", "464aa8023cab8a9c65511ccbac2557d51f96ad07bc669bf7706cca547f102f57", [
        ("", role_definition("inspector", INSPECTOR_BODY)),   # 頭に役の定義（rolekit.with_role_definition）
        ("", reject_section("consistency-bypass", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["consistency-bypass"]),   # 元の commands/consistency-bypass.md の指示を材料を読む形に
        # 差し込みの印を材料の節の名に
        *slots("loop.diff_file", "record.base", "loop.changed_files", "inputs.cwd", "inputs.review_rev", "inputs.review_md",
               "?inputs.repo_review_md"),
        material_tail("同じ版を数える。\n"),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-external-standards.md": (WORKS_GL + "p1.external_standards.md", "cb1c148f374e16868188d9688fc303669ee84352fcb64ac048bebff778f75d1d", [
        ("", role_definition("investigator", INVESTIGATOR_BODY)),   # 頭に役の定義（rolekit.with_role_definition）
        ("", reject_section("external-standards", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["external-standards"]),   # 元の commands/external-standards.md の指示を材料を読む形に
        # 差し込みの印を材料の節の名に
        *slots("loop.diff_file", "loop.changed_files", "inputs.cwd", "out.p0.purpose.purpose_text", "out.p0.purpose.known_weaknesses",
               "inputs.review_md"),
        material_tail(MATERIAL_END),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-gate-efficacy.md": (WORKS_GL + "p1.gate_efficacy.md", "025cd10531b664e19c2d38b7217cbbac3541b7b05402d842ed063b9935720ad0", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("gate-efficacy", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["gate-efficacy"]),   # 元の commands/gate-efficacy.md の指示を材料を読む形に
        *slots("loop.diff_file", "loop.changed_files_file", "record.base", "inputs.cwd", "loop.mutation_decl.text"),   # 差し込みの印を材料の節の名に
        material_tail(MATERIAL_END),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-hygiene.md": (WORKS_GL + "p1.hygiene.md", "e8847b1b1d66c5a1962f6d2898e7dd521d14d1436e7851f441ac462e60f91327", [
        ("", role_definition("cold-reader", COLD_READER_BODY)),   # 頭に役の定義（rolekit.with_role_definition）
        ("", reject_section("hygiene", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["hygiene"]),   # 元の commands/hygiene.md の指示を材料を読む形に
        *slots("section:inputs.review_md#コード衛生観点", "file:loop.diff_file"),   # 差し込みの印を材料の節の名に
        material_tail("欠陥ではない）。\n",   # 末尾に prep が足した段（所見の場所）と、材料を貼る囲いと返答の形（道具の無い役）
                      after="---\n\n=====材料ここから=====\n$hygiene-prep.output.brief\n=====材料ここまで=====\n\n" + MATERIAL_ANSWER),
    ]),
    "material-local-review.md": (WORKS_GL + "p1.local_review.md", "963bdd993d7c3f849b5884af3488aba5422105f1002539d54dda3968db50a2c3", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("local-review", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["local-review"]),   # 元の commands/local-review.md の指示を材料を読む形に
        *slots("record.base", "loop.changed_files_file", "inputs.review_md", "?inputs.repo_review_md",
               "node.skills"),   # 差し込みの印を材料の節の名に
        ("対象差分: {{loop.diff_file}}", "対象差分: ［材料: loop.diff_file］"),   # 同上（同じ印が 2 か所に在る）
        ("`{{loop.diff_file}}` をそのまま渡す", "`［材料: loop.diff_file］` をそのまま渡す"),   # 同上
        material_tail(MATERIAL_END + "\n", LENS_RETRY_NOTE, LENS_FORK_NOTE,   # 末尾に prep が足した段（レンズの読み替え 2 つ・所見の場所）
                      after=MATERIAL_ANSWER + "\n---\n\n" + OVERLAY_LEAD + "\n\n" + UNATTENDED),   # と返答の形と借りたスキルの読み替え
    ]),
    "material-main-path-observation.md": (WORKS_GL + "p1.main_path_observation.md", "e5a0c6fc7d907610f59a970aaf6b85440365ec166d89011b5831e88fb99e8123", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("main-path-observation", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["main-path-observation"]),   # 元の commands/main-path-observation.md の指示を材料を読む形に
        *slots("loop.diff_file", "loop.changed_files_file", "inputs.cwd"),   # 差し込みの印を材料の節の名に
        material_tail(MATERIAL_END),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-prior-decisions.md": (WORKS_GL + "p0.prior_decisions.md", "8a2ee67bd45607d808337299f604a6c9d16ce9b03b81256d04aa91dbee7bddf8", [
        ("", role_definition("investigator", INVESTIGATOR_BODY)),   # 頭に役の定義（rolekit.with_role_definition）
        ("", reject_section("prior-decisions", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["prior-decisions"]),   # 元の commands/prior-decisions.md の指示を材料を読む形に
        *slots("inputs.cwd", "record.base", "loop.changed_files", "loop.request_wheres"),   # 差し込みの印を材料の節の名に
        material_tail(MATERIAL_END),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-procedure-trace.md": (WORKS_GL + "p1.procedure_trace.md", "1eed8dc4ab7bdebcffbbe895c097f84478f956b523a792fba9031d28ee38a04d", [
        ("", role_definition("investigator", INVESTIGATOR_BODY)),   # 頭に役の定義（rolekit.with_role_definition）
        ("", reject_section("procedure-trace", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["procedure-trace"]),   # 元の commands/procedure-trace.md の指示を材料を読む形に
        *slots("loop.diff_file", "loop.changed_files", "inputs.cwd", "inputs.review_md"),   # 差し込みの印を材料の節の名に
        material_tail(MATERIAL_END),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-provenance.md": (WORKS_GL + "p1.provenance.md", "a973ef69ef00eb0d918f67e2a1762d0431484001fb75929c049efb596afe0a06", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("provenance", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["provenance"]),   # 元の commands/provenance.md の指示を材料を読む形に
        *slots("loop.diff_file", "record.base", "inputs.cwd"),   # 差し込みの印を材料の節の名に
        material_tail(MATERIAL_END),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-purpose-review.md": (WORKS_GL + "p0.purpose_review.md", "bf736d08a0e647a8bb1e2c81379fbec4291ceeb66127bc8b40a4f823e555f317", [
        ("", role_definition("inspector", INSPECTOR_BODY)),   # 頭に役の定義（rolekit.with_role_definition）
        ("", reject_section("purpose-review", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["purpose-review"]),   # 元の commands/purpose-review.md の指示を材料を読む形に
        *slots("out.p0.purpose.purpose_text", "inputs.cwd", "inputs.review_rev"),   # 差し込みの印を材料の節の名に
        material_tail("同じ版を数える。\n"),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    "material-test-double-fidelity.md": (WORKS_GL + "p1.test_double_fidelity.md", "1a7c246902fcba7f1ffc21a9173b7a32091e191a34d9f7a5bb2058ba181a3cc9", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("test-double-fidelity", FIRST_NOT, src="prep")),   # 拒否の理由を頭の節で（material.prep:388-391。PR #100）
        ("", MATERIAL_HEADS["test-double-fidelity"]),   # 元の commands/test-double-fidelity.md の指示を材料を読む形に
        *slots("loop.diff_file", "loop.changed_files_file", "inputs.cwd"),   # 差し込みの印を材料の節の名に
        material_tail(MATERIAL_END),   # 末尾に prep が足した段（所見の場所の書き方）と返答の形
    ]),
    # 並行 PR の任せ先の役。元の名の指示書 blk-pr/commands/pr-check.md
    "pr-check.md": ("works/blk-pr/commands/pr-check.md", "a8cd72d17da5ae7d7b4637227d8366fea6b7f8977de4a59a6184344e500bd373", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("pr-check", FIRST_IS)),   # 拒否の理由を頭の節で受ける（線の pr-check-reject。PR #100）
        ("`$pr-snap.output.brief_file`（Read せよ。JSON）", "`$ARTIFACTS_DIR/judge/pr-brief.json`（Read せよ。JSON）"),   # 材料は run の置き場の pr-brief.json
        ("網に出られない。素の `gh` は包みが拒む。`command -v", "網に出られない。`command -v"),   # 包みの無い run でも同じ文で済むように包みの語を外す
        ("（reason に「包みの読む口が無い」）", "（reason に「読むだけの口が無い」）"),   # 同上
        ("`base`: BASE（周の頭で固めた版）", "`base`: 差分の根（始めの記録で固めた版）"),   # 周の語でなく、run の始めの記録が固めた根
        # engine と parallel-pr.py でなく lib の機械の読み。落ちる場合を 1 つ足す
        ("engine は 1〜5 段を同梱の parallel-pr.py で済ませようとして、交差が在った・gh が無いのどれかで",
         "機械は 1〜5 段を gh の読みだけで済ませようとして、交差が在った・gh が無い・remote から owner/repo を導けないのどれかで"),
        ("機械が run の初めに条件外", "機械が条件外"),   # 条件外にするのは並行 PR の節の機械（run の初めではない）
        ("届くのは、engine が 1〜5 段", "届くのは、機械が 1〜5 段"),   # engine の語を外す
        ("書き込みの gh は包みが拒む——gh で打ってよいのは読むだけの口の `works-gh",
         "書き込みの gh は読むだけの口が拒む——gh で打ってよいのは `works-gh"),   # 拒むのは包みでなく読むだけの口
        ("拒まれる）。欄と値の正本は review-record.py。\n\n## 前の返答が拒まれたとき\n\n"
         "前の回の受け付けが拒んだ理由を書いたファイル（1 回目は空）: $LOOP_PREV.pr-accept.output.reason_file\n\n"
         "空でなければ、**そのファイルを Read で読め**（理由の本文はファイルにだけ在る）。そこに挙がった所だけを直して、同じ型でもう一度返せ。\n",
         "拒まれる）。\n"),   # 理由は頭の節で渡る。review-record.py は写しに無い
    ]),
    # 前提の役。元の名の指示書 blk-premises/commands/premises.md
    "premises.md": ("works/blk-premises/commands/premises.md", "1a6663b687d1ecc22175615c94e99827f0f5684d0cc0f132f729de2c47e17dbe", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("premises", FIRST_NOT)),   # 拒否の理由を頭の節で受ける（線の premises-reject。PR #100）
        ("作業ツリーの写しと今の作業ツリー", "作業ツリーの姿と今の作業ツリー"),   # 受け付けが比べるのはファイルの写しでなく作業ツリーの姿
        # 依頼は入口が容器を解いて run の置き場に置いた行の配列
        ("- 人の修正依頼: `$INPUTS.request`（絶対パスか、対象リポジトリの根からの相対パス。対象の外に在ることもある。**まず Read せよ**）。"
         "findings の JSON の配列か、`{\"findings\": [...], \"pr\": [<番号>…], \"issue\": [<番号>…]}` の形（object なら findings の欄が指摘）で、指摘の各行は",
         "- 人の修正依頼の行: `$ARTIFACTS_DIR/judge/request.json`（入口が型を確かめた依頼の行の JSON の配列。**まず Read せよ**）。各行は"),
        ("空なら依頼の行の無い run", "空の配列なら依頼の行の無い run"),   # 同上（空はファイルの無しでなく空の配列）
        ("- 前の回の受け付けが拒んだ理由のファイル（1 回目は空）: $LOOP_PREV.premises-accept.output.reason_file\n"
         "  - 空でなければ、お前は同じ会話の続きで起きている。**そのファイルを Read せよ。** 前の返答",
         REJECT_IN_HEAD + "お前は同じ会話の続きで起きている。前の返答"),   # 理由はファイルでなく頭の節で渡る（PR #100）
        ("拒んだ理由のファイルのパスが次の回の上に届く。", "拒んだ理由が次の回の指示書の頭に届く。"),   # 同上
    ]),
    # 目的の役。元の名の指示書 blk-purpose/commands/purpose.md
    "purpose.md": ("works/blk-purpose/commands/purpose.md", "21b974734fadaed9f3bc5db88fea242447feeccf9d629e27f6da87dd41e73237", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("purpose", FIRST_NOT)),   # 拒否の理由を頭の節で受ける（線の purpose-reject。PR #100）
        ("受け付けは盤面に目的の文", "受け付けは run の置き場に目的の文"),   # 盤面の語を置き場の語に
        ("- 依頼: `$intake.output.request`（絶対パスか、対象リポジトリの根からの相対パス。対象の外に在ることもある。**まず Read せよ**）。"
         "空なら依頼の行の無い run（対象の差分だけを審査する）で、",
         "- 材料: `$purpose-prep.output.brief_file`（**まず Read せよ**）。機械が組んだ物で、次の 3 つが在る:\n"
         "  - 依頼（依頼のファイルの写し。findings の JSON の配列か、`{\"findings\": [...], \"pr\": [...], \"issue\": [...]}` の形）。"
         "依頼の行の無い run なら空で、"),   # 依頼・PR・前提の 3 つの口を、支度が組む材料のファイル 1 つに
        ("探せ。前の run の判断は機械が外してから渡している（目的の文は前の run の判断を知らない別の目の入力になる）。目的の出典",
         "探せ。目的の出典"),   # 前の run の判断はこの材料に来ない（支度が初めから載せない）
        ("- PR の説明: `$INPUTS.pr_file`（PR の番号・題・本文を書いたファイル。空なら PR の無い run）。空でなければ Read せよ。",
         "  - PR の説明（PR の番号・題・本文。PR の無い run はそう書いてある）。"),   # 材料の節の 1 つに
        ("- 前提の実測: `$INPUTS.constraints_file`（空なら前提の実測は無い）。空でなければ Read せよ。`constraints` の各行は",
         "  - 前提の実測（`constraints` の各行は"),   # 同上
        ("（実行したコマンドとその出力）を持つ。", "（実行したコマンドとその出力））。"),   # 同上（括弧を閉じる）
        ("- 前の回の受け付けが拒んだ理由を書いたファイル（1 回目は空）: $LOOP_PREV.purpose-accept.output.reason_file\n"
         "  - 空でなければ、**そのファイルを Read で読め**（理由の本文はファイルにだけ在る）。",
         REJECT_IN_HEAD),   # 理由はファイルでなく頭の節で渡る（PR #100）
        ("（盤面に書いた名前は", "（書いた名前は"),   # 盤面の語を外す
    ]),
    # 再審の役。元の名の指示書 blk-rejudge/commands/rejudge.md は短い指示だけで、役が読む本文は本線の p2.rejudge.md
    "rejudge.md": (WORKS_GL + "p2.rejudge.md", "5f68952b5f931221b2d740dcc7a39332e0dd2a4ced979b5c980dd1a223a4d0da", [
        ("", JUDGE_BODY + "\n\n---\n\n"),   # 頭に judge の役の定義
        ("", ("お前は判定役（judge）として、この run の判定を考え直すために起きている。この "
             "run の 1 回目の判定（判定役が書いた物）と、"
             "その判定役が読んだ材料は置き場のファイルに保存してある。修正役がその判定に異議を出したので、"
             "保存した判定と材料を読んで考え直す（判定役の会話は継がず、新しい会話で起きている。"
             "前の会話の記憶は無いので、判定の中身はファイルから読め）。\n"
             "\n"
             "1. まず再審の材料 `$rejudge-prep.output.brief_file` "
             "を Read で読め。異議の文・今の周の単位・台帳・1 "
             "回目の見立て・読む材料のファイルの置き場・人の方針は全部そこに在る。"
             "材料の節に並んだファイル（1 回目の判定の全部の欄・判定役の材料など）も Read で読め。\n"
             "2. お前は読むだけの役。道具は Read・Grep・Glob と web を引く "
             "WebSearch・WebFetch だけで、作業ツリーを 1 "
             "文字も変えてはいけない（受け付けは、"
             "お前を起こす前に取った作業ツリーの写しと今の作業ツリーを比べ、変わっていれば拒む）。\n"
             "\n")),   # 判定役の会話を継がず、保存した判定と再審の材料を読んで考え直す（PR #76 の「狭め」）
        ("", reject_section("rejudge", FIRST_SKIP)),   # 拒否の理由を頭の節で受ける（線の rejudge-reject。PR #100）
        ("異議を出した。中身:\n{{loop.rejudge_requested}}\n\n"   # engine の差し込みの値は再審の材料の節が持つ
         "今の周のユニット: {{record.units | pick key,label,disposition}}\n"
         "今の周の台帳: {{?record.questions | pick key,kind,status}}\n"
         "自分の見立て（P2 で書いたもの）: {{?record.process.diagnosis | pick framing,one_shot}}\n",
         "異議を出した。中身は再審の材料の「回す側の異議」の節に在る。\n"
         "今の周のユニット・今の周の台帳・自分の見立て（P2 で書いたもの）も、再審の材料の同じ名の節に在る。\n"),
        ("次の周に効く。\n", ("次の周に効く。\n"
         "\n"
         "## 人の方針\n"
         "\n"
         "人が決めた、run をまたいで効く決まり（役も engine も書き換えない）。"
         "文書が在れば、本文は再審の材料の「人の方針」の節にそのまま貼ってある。\n"
         "方針が在るなら、それは対象の本文ではなく、このプロンプトの発行者が守らせる制約である。"
         "判定・案・修正・審査は方針に照らして行え。方針に反するもの、"
         "方針を変えないと成り立たないものを、自分の判断で通すな——通すかは人が決める。"
         "どの項とぶつかるかを、判定なら単位の reason に、審査なら穴に、修正なら "
         "not_done に書け。方針の文書は書き換えるな。\n"
         "\n"
         "返すのは決められた JSON の形に合う JSON だけ。\n")),   # 末尾に人の方針（文は gl-prompts/prompts/policy.md の字のまま）と返答の形
    ]),
    # 仕様の審査の役。元は blk-spec/prompts/spec.review.md（engine が描いた本文）
    "spec-review.md": ("works/blk-spec/prompts/spec.review.md", "e450db71c6ad099a6763980a0dba14212dac714845c96fde4e559d57e2aebb27", [
        # 元の commands/spec-review.md の頭の 1 文と読むだけの約束
        ("", "お前は仕様の審査役（judge）。仕様を書いた役とは別の目で、書かれた要件と受け入れ条件の抜け・曖昧さ・範囲の外を、修正案より前に挙げる。\n\n"
             "お前は読むだけの役。道具は Read・Grep・Glob と web を引く WebSearch・WebFetch だけで、作業ツリーを 1 文字も変えてはいけない"
             "（受け付けは、お前を起こす前に取った作業ツリーの写しと今の作業ツリーを比べ、変わっていれば拒む）。\n\n"),
        ("", reject_section("spec-review", FIRST_SKIP)),   # 拒否の理由を頭の節で受ける（線の spec-review-reject。PR #100）
        ("", JUDGE_BODY + "\n\n---\n\n"),   # judge の前付け（PR #76 の 9）
        ("依頼: {{inputs.request}}\n人の修正依頼（init の直後に積まれた分）: {{?record.process.request_findings}}\n"
         "writer が書いた仕様（要件と、受け入れ条件のテストの置き場）: {{out.spec.write}}\nリポジトリ: {{inputs.cwd}}（",
         REQUEST_ROWS + "（依頼の行の並び。人の修正依頼もここに在る）\n"
         "writer が書いた仕様（要件と、受け入れ条件のテストの置き場）: `$ARTIFACTS_DIR/judge/spec-write.json` を Read で読め\n"
         "リポジトリ: 今の作業ディレクトリ（"),   # engine の差し込みの値を run の置き場のファイルで渡す
        ("仕様を承認する。\n", "仕様を承認する。\n" + DECIDED_ANSWER),   # 末尾に返答の形
    ]),
    # 仕様を直す役。元は blk-spec/prompts/spec.revise.md
    "spec-revise.md": ("works/blk-spec/prompts/spec.revise.md", "8385832dc15b4d1b7c8ab199544ea890ad6cc8b7e18cfb5ab832366aa758192c", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        # 元の commands/spec-revise.md の頭の 1 文
        ("", "お前は仕様を直す役（writer）。仕様の審査が挙げた穴に key ごとに 1 度だけ答え、直した仕様の全体を返す。\n\n"),
        ("", reject_section("spec-revise", FIRST_SKIP)),   # 拒否の理由を頭の節で受ける（線の spec-revise-reject。PR #100）
        # engine の差し込みの値を run の置き場のファイルで渡す
        ("最初に書いた仕様: {{out.spec.write}}\n仕様の審査が挙げた穴: {{out.spec.review}}\n依頼: {{inputs.request}}\nリポジトリ: {{inputs.cwd}}\n",
         "最初に書いた仕様: `$ARTIFACTS_DIR/judge/spec-write.json` を Read で読め\n"
         "仕様の審査が挙げた穴: `$ARTIFACTS_DIR/judge/spec-review.json` を Read で読め\n"
         + REQUEST_ROWS + "\nリポジトリ: 今の作業ディレクトリ（対象リポジトリの作業ツリーの根）\n"),
        ("承認の後に `run` を走らせる。\n",   # 元の commands/spec-revise.md の書いてよい物の約束と返答の形
         "承認の後に `run` を走らせる。\n\n作業ツリーに書いてよいのはテストのファイルだけ。実装のファイルは 1 文字も変えるな。\n" + DECIDED_ANSWER),
    ]),
    # 仕様を書く役。元は blk-spec/prompts/spec.write.md
    "spec.md": ("works/blk-spec/prompts/spec.write.md", "751fa48d67b5e76752bea475c98bc25d0e0508cdda0e286717d68674c0fa5ddd", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", "お前は仕様を書く役（writer）。依頼が完成と言える要件を 1 件ずつ書き、要件ごとの受け入れ条件を実行できるテストとして対象リポジトリに書く。"
             "修正（実装）はまだ書かない。\n\n"),   # 元の commands/spec-write.md の頭の 1 文
        # 拒否の理由を頭の節で受ける（元の commands/spec-write.md の 2 の文。PR #100）
        ("", reject_section("spec", "テストのファイルが無い・名前が無い・Given/When/Then が無いと言われたら、"
                                    "先に対象リポジトリのテストのファイルを直してから返せ。" + FIRST_SKIP)),
        # engine の差し込みの値を run の置き場のファイルで渡す
        ("依頼: {{inputs.request}}\n人の修正依頼（init の直後に積まれた分。無ければ「無い」と出る）: {{?record.process.request_findings}}\n"
         "リポジトリ: {{inputs.cwd}}\n",
         REQUEST_ROWS + "（依頼の行の並び。人の修正依頼もここに在る）\nリポジトリ: 今の作業ディレクトリ（対象リポジトリの作業ツリーの根）\n"),
        ("実装はまだ書くな。\n",
         "実装はまだ書くな——実装のファイルは 1 文字も変えるな。受け入れ条件の `run` のコマンドは、承認の前には誰も走らせない"
         "（人が字面を見て承認した後に機械が走らせる）。\n" + DECIDED_ANSWER),   # 元の commands/spec-write.md の 3 の文（PR #76 の 9）と返答の形
    ]),
    # 世界の解の言い直す役。元の名の指示書 blk-world/commands/world-classes.md
    "world-classes.md": ("works/blk-world/commands/world-classes.md", "54a5f00af282aa8f91e0384555f99394a61bd69370b4c5a426b05fcbe00af13b", [
        ("", reject_section("world-classes", FIRST_IS)),   # 拒否の理由を頭の節で受ける（線の world-classes-reject。PR #100）
        WORLD_REREAD,   # 理由は頭の節にいつも在り、空なら 1 回目
        ("$world-classes-prep.output.prompt", "$world-intake.output.prompt"),   # 指示書を描く節の名が world-intake
    ]),
    # 世界の解の web の役。元の名の指示書 blk-world/commands/world-judge.md
    "world-judge.md": ("works/blk-world/commands/world-judge.md", "4a1f99e4146aff139394727da6e3423ae6c915a2ec25711f67461503ff2a4e35", [
        ("", QUERY_HEAD),   # 頭に外への問い合わせの決まり（PR #76 の 9）
        ("", reject_section("world-judge", FIRST_IS)),   # 拒否の理由を頭の節で受ける（線の world-judge-reject。PR #100）
        WORLD_REREAD,   # 理由は頭の節にいつも在り、空なら 1 回目
        ("$world-judge-prep.output.prompt", "$world-plan.output.prompt"),   # 指示書を描く節の名が world-plan
    ]),
}


RECORDER = ROOT / "bin" / "_lib" / "record-read.py"


class ReadsTest(unittest.TestCase):
    """読んだ証拠の節 pr-check-reads（lib/judge_accept.pr_reads）: 並行 PR の役が渡し物 judge/pr-brief.json を読んだかを、隔離した
    設定のフック（bin/_lib/record-read.py を実物で起こす）の記録から集める。受け付けの条件にせず、欠けは返りに出す（棚卸し J40）"""

    def setUp(self):
        self.r = Run(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = pathlib.Path(tmp.name) / "claude"
        self.config_env = {"CLAUDE_CONFIG_DIR": str(self.config)}

    def brief(self) -> pathlib.Path:
        self.r.judge.mkdir(parents=True, exist_ok=True)
        path = self.r.judge / prcheck.BRIEF
        path.write_text("{}", encoding="utf-8")
        at = path.stat().st_mtime - 60
        os.utime(path, (at, at))
        return path

    def hook(self, path):
        event = {"session_id": "s-1", "tool_name": "Read", "tool_input": {"file_path": str(path)}, "tool_use_id": "toolu_Read",
                 "cwd": str(self.r.repo), "hook_event_name": "PostToolUse"}
        done = subprocess.run([sys.executable, str(RECORDER), str(self.config / reads.ROOT)], input=json.dumps(event),
                              text=True, encoding="utf-8", capture_output=True, cwd=str(self.r.repo),
                              env=hermetic.child_env(PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(done.returncode, 0, done.stderr)

    def index(self) -> dict:
        return json.loads((self.r.judge / reads.index_name(prcheck.ROLE)).read_text(encoding="utf-8"))

    def test_pr_check_must_read_its_brief(self):
        self.assertEqual(nodes()["pr-check-reads"]["script"], "pr_reads")
        (self.config / reads.ROOT).mkdir(parents=True)
        brief = self.brief()
        self.hook(self.r.repo / "stats.py")
        out = self.r.returned("pr_reads", env=self.config_env)
        self.assertIs(out["ok"], True, out)
        self.assertEqual(out["missing"], [str(brief)])
        self.hook(brief)
        out = self.r.returned("pr_reads", env=self.config_env)
        self.assertEqual(out["missing"], [], out)
        self.assertEqual(out["index_file"], str(self.r.judge / reads.index_name(prcheck.ROLE)))
        doc = json.loads(pathlib.Path(self.index()[prcheck.ROLE]).read_text(encoding="utf-8"))
        self.assertEqual([row["path"] for row in doc["rows"]], [str(brief)])
        self.assertIn(doc["rows"][0]["hook"], reads.HOOK_SEEN)

    def test_pr_reads_returns_the_same_with_or_without_the_parents_config_dir(self):
        """親の CLAUDE_CONFIG_DIR は子へ漏れない: 記録の根の入った置き場を親に向けた時と、親に置き場が無い時で、子の返りは同じ。
        親の HOME は 2 回とも空の一時フォルダに向ける（$HOME/.claude への戻りでも場に左右されない）"""
        (self.config / reads.ROOT).mkdir(parents=True)
        self.brief()
        self.hook(self.r.repo / "stats.py")
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        with mock.patch.dict(os.environ, {"HOME": home.name, "CLAUDE_CONFIG_DIR": str(self.config)}):
            with_config = self.r.returned("pr_reads")
        with mock.patch.dict(os.environ, {"HOME": home.name}):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            without_config = self.r.returned("pr_reads")
        self.assertEqual(with_config, without_config)

    def test_pr_check_reads_runs_after_the_role_on_the_roles_rounds(self):
        """役の輪の後に走り（先に走ると読む前の記録で欠けと言う）、輪が落ちた回も走り、役を起こした回だけ走る"""
        node, role = nodes()["pr-check-reads"], nodes()["pr-check-loop"]
        self.assertIn("pr-check-loop", node["depends_on"])
        self.assertEqual(node["trigger_rule"], "one_success")
        self.assertEqual(node["when"], role["when"])

    def test_pr_check_reads_without_record_does_not_fail(self):
        """記録の根が無い（フックを置いていない起動）時も落ちず、読んでいないとも言わない"""
        self.brief()
        out = self.r.returned("pr_reads", env=self.config_env)
        self.assertEqual((out["ok"], out["missing"]), (True, []), out)
        doc = json.loads(pathlib.Path(self.index()[prcheck.ROLE]).read_text(encoding="utf-8"))
        self.assertEqual(doc["sources"], {"hook": "none", "why": reads.NO_ROOT})


class CopiedTextsCase(unittest.TestCase):
    """役の指示書の写しの台帳（K9）: 全部の指示書が、元の works の文に台帳の直しだけを当てた物"""

    def test_every_command_is_its_original_with_only_ledgered_edits(self):
        """許した直しを逆に当てると元のバイト（元の sha256）に戻る。台帳に無い指示書・指示書の無い台帳の行は赤"""
        on_disk = {p.name for p in COMMANDS.glob("*.md")}
        with self.subTest(ledger="台帳と指示書の一覧"):
            self.assertEqual(sorted([*COPIED_TEXTS, *OWN_TEXTS]), sorted(on_disk))
            self.assertFalse(set(COPIED_TEXTS) & set(OWN_TEXTS))
            self.assertLessEqual(rewritten(COMMANDS), set(COPIED_TEXTS))
        for name in sorted(on_disk & set(COPIED_TEXTS)):
            source, sha256, edits = COPIED_TEXTS[name]
            with self.subTest(command=name, source=source):
                assert_is_original(self, COMMANDS / name, sha256, edits)


if __name__ == "__main__":
    unittest.main()


class BriefCase(unittest.TestCase):
    def lang_source(self, node_id: str) -> str:
        """役の節が言語の 1 行を読む節: 輪の中の役は同じ輪の頭の拒否の節（素材の輪では <役>-prep）、輪の外の判定の裏取りは支度の節"""
        for loop in loops().values():
            ids = [n["id"] for n in loop["loop_group"]["nodes"]]
            if node_id in ids:
                return next((i for i in ids if i.endswith("-reject")), f"{node_id}-prep")
        return "verify-prep"

    def test_lang_line_reaches_judge_roles(self):
        """L-E37: 始めの記録の lang が、判定の全部の役の文の頭に言語の 1 行（rolekit.lang_line。元 works/.shared/core/rolekit.py
        67-68 行・147-150 行）として届く。plan・eyes・fix と同じ口で、写しを作らない"""
        roles = {k: n for k, n in nodes().items() if "command" in n}
        self.assertGreaterEqual(len(roles), 22)
        for key, node in roles.items():
            with self.subTest(role=key):
                source = self.lang_source(key)
                first = (COMMANDS / f"{node['command']}.md").read_text(encoding="utf-8").splitlines()[0]
                self.assertEqual(first, f"${source}.output.lang_line")
                self.assertIn("lang_line", nodes()[source]["output_format"]["required"])
        r = Run(self, lang="English")
        want = rolekit.lang_line({"lang": "English"})
        self.assertIn("English", want)
        self.assertEqual(r.returned("reject", reason="")["lang_line"], want)
        self.assertEqual(r.returned("verify", stage="prep")["lang_line"], want)
        self.assertEqual(Run(self).returned("reject", reason="x"), {"reason": "x", "lang_line": rolekit.lang_line({})})
        broken = r.returned("reject", reason="", start=json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": "no.json"}))
        self.assertIn("ポインタの先が無い", broken["lang_line"])

    def test_material_prep_returns_the_reject_reason_and_lang_line(self):
        """素材の輪の頭の script material_prep は、with: の reason（前の周の拒否の理由）をそのまま、言語の 1 行を始めの記録の lang から
        返す。材料を描けない役（except の枝）でも同じ reason・lang_line を返す"""
        r = Run(self, lang="English")
        want = rolekit.lang_line({"lang": "English"})
        self.assertIn("English", want)
        reason = '前の周の理由 "引用" `x`\n二行目'
        for role in ("hygiene", "no-such-role"):
            got = r.returned("material_prep", role=role, reason=reason)
            with self.subTest(role=role):
                self.assertEqual({k: got.get(k) for k in ("reason", "lang_line")}, {"reason": reason, "lang_line": want})
        self.assertEqual(sorted(r.returned("material_prep", role="hygiene", reason="")),
                         ["brief", "brief_file", "lang_line", "reason", "repo_review_md", "review_md"])
        self.assertEqual(r.returned("material_prep", role="hygiene", reason="")["reason"], "")

    def test_unreadable_start_pointer_degrades_in_every_lang_line_script(self):
        """#367: 始めの記録の指し札が読めない（ほかの run の札・札の形でない）時、言語の 1 行を返す 4 つの script はどれも落ちずに、
        rolekit.pointed_lang_line の同じ 1 行を返す"""
        r = Run(self)
        for start in (json.dumps({"type": "archon_artifact", "run_id": "other-run", "path": "start.json"}), '"札でない"'):
            got = [r.returned("reject", reason="", start=start)["lang_line"],
                   r.returned("rejects", board="judge", accept="purpose", start=start)["lang_line"],
                   r.returned("verify", stage="prep", start=start)["lang_line"],
                   r.returned("material_prep", role="hygiene", reason="", start=start)["lang_line"]]
            with self.subTest(start):
                self.assertEqual(len(set(got)), 1, got)
                self.assertTrue(got[0].startswith(rolekit.lang_line({})), got[0])
                self.assertIn(rolekit.POINTER_UNREAD, got[0])

class CarriedConstraintsCase(unittest.TestCase):
    def test_carried_rows_fit_the_premises_shape(self):
        """seams F5: 報告が次の依頼に書く constraints の行（carry.carried_constraints）は、判定の側が premises.json に足す前提の実測の
        型（節 premises の output_format の constraints の行）にそのまま合う（片方だけ欄を変えると、型の外の行が premises.json に入る）"""
        import carry
        rows = carry.carried_constraints(["上限は config.py:3 の 10", "  ", 3], "run-0")
        self.assertEqual(len(rows), 1)
        self.assertEqual(validate_schema({"constraints": rows}, nodes()["premises"]["output_format"]), [])
