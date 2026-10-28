"""設計の相談（docs/design/line.md の 3.1 節。issue #822）の計画の往復と、設計の段（3.3 節。issue #862）の設計の往復を、止めた Archon
（a972888a）を bun で直に起こして複数の周で回す。

筋書き（archon workflow test）は until_bash の輪を 1 周で終えたことにし、答えた後の周を回さない（止めた Archon の dry-run.ts の
loopIterationCompletes）。ここでは line の YAML の plan-rounds の node をそのまま写し、AI を起こす 2 つの include（plan・plan-review-run）
だけを、同じ id・同じ when・同じ返りの欄の模擬の script に差し替えた使い捨ての工程を組んで回す。周の頭 design-turn・plan-out・周の
終わり design-talk・関所 gate-design と、輪の後ろの受け皿と修正前の承認ノード ask-before-fix は line の本物の script。輪の外の前の段
（start・依頼の出どころ request-in・判定・owed など）は値を返すだけの script。AI も認証も要らないので CI でも走る。本物の AI の役（計画・事前審査）は回していない。
テーマの run の工程は、同じ組み立てで計画の往復の前に line の theme-rounds を写し（AI を起こす theme・theme-review を同じ形の模擬に差し替え）、
周の頭 theme-turn・theme-out・周の終わり theme-talk・関所 gate-theme・輪の後ろの theme-rounds-out・降りる theme-descend・依頼の出どころ
request-in を line の本物の script で回す（talk・rounds は段の名を引数に取るだけなので、2 つの loop を同じ部品で回す）。

照らす事（#822 の受入確認のうち、本物の Archon の止め・答え・再開・周の数が要る物）:
- 通常の run（design_talk が空）: 止まらずに終わり、関所は飛び、往復の返りは plan-out の返りのまま
- 対話モードの run: 1 周目の止まる周で関所が開いて run が待つ（答えるまで進まない）→ revise と一言で 2 周目の plan が人の block を
  差し込んだ記録と一言を受け、事前審査が照らし直して関所がもう一度開く → approve で輪を終え、修正前の承認ノードは聞き直さずに
  修正へ進む（go 真・合意を agreed に運ぶ）
- stop で輪を終え、修正前の承認ノードは人の止め human:gate-design で止める
- 人の指摘の受け箱（issue #830）: run の置き場の talk/notes.txt に入った指摘は、待たずに 1 周目の plan に依頼の答えの行で届き、
  周の設計の控え talk/round-1.md が書かれ、受け箱に承認の行（承認:）が在るので関所は開かずに、承認を合意として修正前の承認ノードへ運ぶ
- 設計の段（issue #862 の下書きの 11.3）: テーマの run は 1 周目の止まる周で gate-theme が開いて待つ → revise と答えの text の見出しの
  セクションで 2 周目の書き手が人の block を差し込んだ記録と人の答えの行（持ち主の言葉・問いへの答え）を受け、事前審査が照らし直して
  関所がもう一度開く → approve で設計の往復を終え、theme-descend が承認された設計の変える所を依頼の行にし、request-in がその依頼を返し、
  計画の往復の 1 周目の plan が降りた依頼の答え（承認された設計の在りか）を受けて gate-design が開く → approve で修正前の承認ノードへ進む
"""
import copy
import json
import pathlib
import shutil
import tempfile
import textwrap
import unittest

import yaml

from tests import archon
from tests.blocks import kit
from tests.blocks.theme import values as tv
from tests.layers.test_archon_validate import validate

WORKFLOW = "works-factory-talk-probe"
FOLDER = "talk-probe"
LINE = kit.BLOCKS / "line"
REAL_SCRIPTS = ("design_turn", "design_talk", "plan_out", "returned", "ask_before_fix", "theme_turn", "theme_out", "theme_talk",
                "theme_descend", "request_in")
REQUEST_FIELDS = ("request", "request_file", "request_answers", "entry", "request_origin", "request_scope", "prior_rows")
UV_HEAD = "# /// script\n# requires-python = \">=3.12\"\n# dependencies = []\n# ///\n"

# 値を返すだけの script（輪の外の前の段）。INPUTS_VALUE の JSON の中の "@ptr:<相対>" を run directory のファイルの pointer に替え、
# INPUTS_FILES（{相対: 中身}。字の中身はそのまま、ほかは JSON で）を run directory に書いてから返す
EMIT = UV_HEAD + textwrap.dedent('''\
    import json, os, pathlib
    root = pathlib.Path(os.environ["ARTIFACTS_DIR"])
    for rel, body in json.loads(os.environ.get("INPUTS_FILES") or "{}").items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False), encoding="utf-8")
    def walk(v):
        if isinstance(v, str) and v.startswith("@ptr:"):
            return {"type": "archon_artifact", "run_id": os.environ["WORKFLOW_ID"], "path": v[5:]}
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v
    print(json.dumps(walk(json.loads(os.environ["INPUTS_VALUE"])), ensure_ascii=False))
''')

# 計画の模擬: 周の番号は prior の round + 1（plan の block の files.next_round と同じ式）。受けた prior の最後の往復の block と依頼の答えを
# probe/plan/plan-<周>.json に残し、案の控え 2 つを書いて、plan の block の返りの欄で返す
PLAN = UV_HEAD + textwrap.dedent('''\
    import json, os, pathlib
    root = pathlib.Path(os.environ["ARTIFACTS_DIR"])
    def ptr(rel):
        return {"type": "archon_artifact", "run_id": os.environ["WORKFLOW_ID"], "path": rel}
    def load(raw):
        raw = (raw or "").strip()
        if not raw:
            return None
        v = json.loads(raw)
        return json.loads((root / v["path"]).read_text(encoding="utf-8")) if isinstance(v, dict) and "path" in v else v
    prior = load(os.environ.get("INPUTS_PRIOR"))
    k = prior["round"] + 1 if prior else 1
    record = (prior or {}).get("record") or {}
    blocks = record["passes"][-1]["blocks"] if record.get("passes") else []
    def put(rel, doc):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return ptr(rel)
    put(f"probe/plan/plan-{k}.json", {"blocks": blocks, "answers": json.loads(os.environ.get("INPUTS_ANSWERS") or "[]")})
    fix_plan = put(f"plan/r{k}/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "approach": f"周 {k} の案"}]})
    fields = put(f"plan/r{k}/plan-fields.json", {"round": k, "fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "out_of_scope": [], "route": "direct"}]})
    print(json.dumps({"ok": True, "status": "ok", "reason": "", "round": k, "owed": ["u1"], "plan": fields, "fix_plan": fix_plan,
                      "reply": fix_plan, "handoff": None, "ripple": None, "rejects": [], "gave_up": None}, ensure_ascii=False))
''')

# 事前審査の模擬（計画の往復の plan-review-run と設計の往復の theme-review が使う。段の名 INPUTS_STAGE で置き場を分ける）: 前の往復の
# 人の block（kind person）は消えたと言い（resolved）、計画の役の答えを往復の行に積む。どの周も決め手の揃わない行を 1 つ人に回す（asks）。
# 受けた記録された方針の行の名を probe/<段>/review-<周>.json に残す
REVIEW = UV_HEAD + textwrap.dedent('''\
    import json, os, pathlib
    root = pathlib.Path(os.environ["ARTIFACTS_DIR"])
    def ptr(rel):
        return {"type": "archon_artifact", "run_id": os.environ["WORKFLOW_ID"], "path": rel}
    raw = (os.environ.get("INPUTS_PRIOR") or "").strip()
    v = json.loads(raw) if raw else None
    record = json.loads((root / v["path"]).read_text(encoding="utf-8")) if isinstance(v, dict) else {"passes": []}
    last = record["passes"][-1] if record.get("passes") else {}
    person = [f["key"] for f in last.get("faces") or [] if f.get("kind") == "person"]
    k = len(record.get("passes") or []) + 1
    def put(rel, doc):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return ptr(rel)
    stage = os.environ["INPUTS_STAGE"]
    put(f"probe/{stage}/review-{k}.json", {"person": person,
                                           "recorded": [r.get("name") for r in json.loads(os.environ.get("INPUTS_RECORDED") or "[]")]})
    passed = put(f"plan-review/{stage}/pass-{k}.json", {
        "plan": [{"id": "u1", "unit_keys": ["u1"], "hash": f"h{k}", "row": {"unit_keys": ["u1"], "approach": f"周 {k}"}}],
        "review": {"faces": []}, "resolved": person,
        "answers": [{"key": p, "handled": "fixed", "how": "人の求めのとおりに直した"} for p in person]})
    holes = put(f"plan-review/{stage}/holes-{k}.json", {"faces": [], "resolved": person})
    ask = {"kind": "regression", "node": "p2.fix_plan", "text": f"周 {k} の案が狭める能力", "units": ["u1"], "mark": {},
           "decided": False, "why": {"obvious": ["決め手の欄が揃わない"]}}
    print(json.dumps({"ok": True, "status": "ok", "round": k, "holes": holes, "blocks": [], "pass": passed, "asks": [ask],
                      "deviations": [], "reason": "", "gave_up": None}, ensure_ascii=False))
''')

# 設計の案の書き手の模擬: 周の番号は受けた往復の記録の往復の数 + 1（theme の block の intake と同じ数え）。受けた記録の最後の往復の block と
# 人の答えの行と前の周の案の有無を probe/theme/theme-<周>.json に残し、INPUTS_DESIGN の設計の案と見せる md を書いて、theme の block の返りの欄で返す
THEME = UV_HEAD + textwrap.dedent('''\
    import json, os, pathlib
    root = pathlib.Path(os.environ["ARTIFACTS_DIR"])
    def ptr(rel):
        return {"type": "archon_artifact", "run_id": os.environ["WORKFLOW_ID"], "path": rel}
    raw = (os.environ.get("INPUTS_PRIOR") or "").strip()
    v = json.loads(raw) if raw else None
    record = json.loads((root / v["path"]).read_text(encoding="utf-8")) if isinstance(v, dict) else {"passes": []}
    k = len(record.get("passes") or []) + 1
    blocks = record["passes"][-1]["blocks"] if record.get("passes") else []
    def put(rel, body):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding="utf-8")
        return ptr(rel)
    put(f"probe/theme/theme-{k}.json", json.dumps({"blocks": blocks, "answers": json.loads(os.environ.get("INPUTS_ANSWERS") or "[]"),
                                                   "prior_design": bool((os.environ.get("INPUTS_PRIOR_DESIGN") or "").strip())},
                                                  ensure_ascii=False))
    design = put(f"theme/r{k}/design.json", os.environ["INPUTS_DESIGN"])
    md = put(f"theme/r{k}/design.md", f"# 周 {k} の設計の案\\n")
    print(json.dumps({"ok": True, "status": "ok", "design": design, "design_md": md, "reason": "", "report": [f"周 {k} の設計の案"]},
                     ensure_ascii=False))
''')

PLAN_KEYS = ("ok", "status", "reason", "round", "owed", "plan", "fix_plan", "reply", "handoff", "ripple", "rejects", "gave_up")
REVIEW_KEYS = ("ok", "status", "round", "holes", "blocks", "pass", "asks", "deviations", "reason", "gave_up")
THEME_KEYS = ("ok", "status", "design", "design_md", "reason", "report")


def _shape(value: dict) -> dict:
    """値の欄を宣言しただけの output_format（入れ子の object は欄も宣言する。後ろの node が $<id>.output.<欄>.<欄> で読む）"""
    def prop(v):
        return ({"type": "object", "required": list(v), "properties": {k: prop(x) for k, x in v.items()}}
                if isinstance(v, dict) and v else {})
    return prop(value)


def _emit(ident: str, value: dict, files=None, depends=()) -> dict:
    node = {"id": ident, "script": "emit", "runtime": "uv", "mutates_checkout": False,
            "with": {"value": json.dumps(value, ensure_ascii=False), "files": json.dumps(files or {}, ensure_ascii=False)},
            "output_format": _shape(value)}
    if depends:
        node["depends_on"] = list(depends)
    return node


def _stub(node: dict, script: str, inputs: dict, keys) -> dict:
    """include の node を、同じ id・depends_on・when で、block の返りの欄を返す模擬の script に替えた node"""
    out = {k: node[k] for k in ("id", "depends_on", "when") if k in node}
    return {**out, "script": script, "runtime": "uv", "mutates_checkout": False, "with": inputs,
            "output_format": {"type": "object", "required": list(keys), "properties": {k: {} for k in keys}}}


def _stubbed(loop: dict, stubs: dict) -> dict:
    """line の loop の写しの、AI を起こす include を stubs（{id: (script, with, 返りの欄)}）の模擬に替えた物"""
    loop = copy.deepcopy(loop)
    body = loop["loop_group"]["nodes"]
    for i, node in enumerate(body):
        if node["id"] in stubs:
            body[i] = _stub(node, *stubs[node["id"]])
    return loop


def probe(design_talk: bool, notes: str = "", theme: bool = False) -> dict:
    """計画の往復を回す使い捨ての工程。theme が真なら、テーマの run として計画の往復の前に設計の段（theme-rounds から request-in まで）を
    本物の script で回す（偽なら request-in は値を返すだけ）"""
    line = yaml.safe_load((LINE / "works-factory-line.yaml").read_text(encoding="utf-8"))
    top = {n["id"]: n for n in line["nodes"]}
    plan_rounds = _stubbed(top["plan-rounds"], {
        "plan": ("plan_probe", {"prior": "$design-turn.output.plan_prior", "answers": "$design-turn.output.answers"}, PLAN_KEYS),
        "plan-review-run": ("review_probe", {"prior": "$design-turn.output.record", "recorded": "$design-turn.output.recorded",
                                             "stage": "plan"}, REVIEW_KEYS)})
    ports = {"design_talk": design_talk, "unattended": False, "request_answers": [{"question": "q", "text": "依頼の答え"}],
             "policy": "", "takes_push": False, "theme": "", "request": None, "request_file": "", "entry": "", "request_origin": "",
             "request_scope": False, "prior_rows": []}
    files = {"r1/start.json": {"answers": []}, **({"talk/notes.txt": notes} if notes else {})}
    if theme:
        ports.update(theme="theme.md", theme_text=tv.THEME_MD.strip())
        files["theme.md"] = tv.THEME_MD
        source = [
            _emit("answer-start", {"go": True, "answer": None, "stop_reason": ""}, depends=["start"]),
            _emit("theme-world-in", {"rows": None, "stop_reason": ""}, depends=["answer-start"]),
            _emit("theme-design-in", {"design": None, "reason": None, "stop_reason": ""}, depends=["answer-start"]),
            _stubbed(top["theme-rounds"], {
                "theme": ("theme_probe", {"prior": "$theme-turn.output.record", "prior_design": "$theme-turn.output.prior_design",
                                          "answers": "$theme-turn.output.answers", "design": json.dumps(tv.reply(), ensure_ascii=False)},
                          THEME_KEYS),
                "theme-review": ("review_probe", {"prior": "$theme-turn.output.record", "recorded": "$theme-turn.output.recorded",
                                                  "stage": "theme"}, REVIEW_KEYS)}),
            *(copy.deepcopy(top[name]) for name in ("theme-rounds-out", "theme-descend", "request-in")),
        ]
    else:
        source = [_emit("request-in", {"go": True, "stop_reason": "", "reason": "", **{k: ports[k] for k in REQUEST_FIELDS}, "notes": []},
                        depends=["start"])]
    head = [
        _emit("start", {"ok": True, "record": "@ptr:r1/start.json", "ports": ports}, files=files),
        *source,
        _emit("judge", {"ok": True, "ready": True}, depends=["request-in"]),
        _emit("judge-out", {"got": {"judgment": None, "answer_ties": None, "materials": None}}, depends=["judge"]),
        _emit("owed", {"owed": True, "recorded": [{"source": "doc", "name": "p.md", "text": ""}], "stop_reason": ""}, depends=["judge"]),
        _emit("structure-in", {"structure": None, "stop_reason": ""}, depends=["judge"]),
        _emit("design-in", {"design": None, "reason": "", "stop_reason": ""}, depends=["judge"]),
        _emit("tiers", {"tree": "off", "stop_reason": ""}, depends=["judge"]),
    ]
    tail = [copy.deepcopy(top["plan-rounds-out"]), copy.deepcopy(top["ask-before-fix"])]
    return {"name": WORKFLOW, "description": "設計の相談の輪を本物の Archon で回す使い捨ての工程（tests/e2e/test_design_talk_real.py）",
            "nodes": [*head, plan_rounds, *tail]}


def place_probe(folder: pathlib.Path, design_talk: bool, notes: str = "", theme: bool = False) -> None:
    (folder / "scripts").mkdir(parents=True)
    shutil.copytree(LINE / "src", folder / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(LINE / "schemas", folder / "schemas")   # 本物の script の口が照らす line の形（頭なしの名）
    for name in REAL_SCRIPTS:
        shutil.copyfile(LINE / "scripts" / f"{name}.py", folder / "scripts" / f"{name}.py")
    for name, body in (("emit", EMIT), ("plan_probe", PLAN), ("review_probe", REVIEW), ("theme_probe", THEME)):
        (folder / "scripts" / f"{name}.py").write_text(body, encoding="utf-8")
    (folder / f"{WORKFLOW}.yaml").write_text(yaml.safe_dump(probe(design_talk, notes, theme), allow_unicode=True, sort_keys=False),
                                             encoding="utf-8")


def body_outputs(events: list, node: str, loop: str = "plan-rounds") -> list:
    done = [e for e in events if e["event_type"] == "node_completed" and e["step_name"] == f"{loop}.{node}"]
    return [e["data"].get("structured_output") for e in sorted(done, key=lambda e: e["event_order"])]


def top_output(events: list, node: str):
    done = [e for e in events if e["event_type"] == "node_completed" and e["step_name"] == node]
    return done[-1]["data"].get("structured_output") if done else None


class TalkRoundsCase(unittest.TestCase):
    maxDiff = None

    def tree(self, design_talk: bool, notes: str = "", theme: bool = False):
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        place_probe(work / FOLDER, design_talk, notes, theme)
        return archon.tree([FOLDER], workflows=work)

    def runs(self, root) -> list:
        return json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]

    def detail(self, root, run_id: str) -> dict:
        got = archon.archon(root, "workflow", "get", run_id, "--json", "--verbose", "--events")
        return json.loads(got.stdout)

    def respond(self, root, run_id: str, *words: str):
        done = archon.archon(root, "workflow", "respond", run_id, *words)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_probe_validates(self):
        for design_talk, theme in ((False, False), (True, False), (True, True)):
            with self.subTest(design_talk=design_talk, theme=theme), self.tree(design_talk, theme=theme) as root:
                self.assertEqual(validate(root), {WORKFLOW: []})

    def test_normal_run_does_not_stop_and_returns_the_plan_out(self):
        with self.tree(False) as root:
            done = archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree")
            [run] = self.runs(root)
            detail = self.detail(root, run["id"])
        self.assertEqual((done.returncode, detail["status"]), (0, "completed"), done.stdout + done.stderr)
        events = detail["events"]
        po, talk = body_outputs(events, "plan-out"), body_outputs(events, "design-talk")
        self.assertEqual((len(po), len(talk)), (1, 1))
        self.assertEqual({k: talk[0][k] for k in po[0]}, po[0])
        self.assertFalse(body_outputs(events, "gate-design"))
        before = top_output(events, "ask-before-fix")
        self.assertEqual((before["open"], before["agreed"]), (True, None), "通常の run の修正前の承認ノードは今のまま（人に回す行で開く）")

    def test_dialogue_revises_then_agrees_without_asking_again(self):
        with self.tree(True) as root:
            archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree")
            [run] = self.runs(root)
            self.assertEqual(run["status"], "paused", "1 周目の止まる周で設計の相談の承認ノードが開いて待つ")
            first = body_outputs(self.detail(root, run["id"])["events"], "design-talk")
            self.assertEqual((first[-1]["open"], first[-1]["done"]), (True, False))
            self.assertIn("周 1 の案", first[-1]["text"])
            self.respond(root, run["id"], "revise", "b.py にも直しを入れる")
            [run] = self.runs(root)
            self.assertEqual(run["status"], "paused", "設計し直して事前審査をやり直し、もう一度関所が開いて待つ")
            plan2, review2 = (json.loads(next(root.parent.glob(f"**/probe/plan/{name}-2.json")).read_text(encoding="utf-8"))
                              for name in ("plan", "review"))
            self.respond(root, run["id"], "approve")
            [run] = self.runs(root)
            detail = self.detail(root, run["id"])
        self.assertEqual(plan2["blocks"], ["person-1"], "2 周目の plan は人の block を差し込んだ記録を受けた")
        self.assertEqual(plan2["answers"][-1], {"question": "設計の相談で人が求めた 1 番目の直し", "text": "b.py にも直しを入れる"})
        self.assertEqual(review2["person"], ["person-1"], "事前審査は人の block を照らし直した")
        self.assertIn("設計の相談で人が求めた 1 番目の直し", review2["recorded"])
        self.assertEqual(detail["status"], "completed", json.dumps(detail.get("events", [])[-3:], ensure_ascii=False))
        events = detail["events"]
        talks = body_outputs(events, "design-talk")
        self.assertEqual([(t["open"], t["done"]) for t in talks], [(True, False), (True, False), (False, True)])
        self.assertEqual(len(body_outputs(events, "plan-out")), 2, "合意の周は plan も事前審査も回さない")
        self.assertEqual([t["decision"] for t in talks[-1]["talks"]], ["revise", "approve"])
        before = top_output(events, "ask-before-fix")
        self.assertEqual((before["open"], before["go"]), (False, True), "合意した承認を修正前の承認ノードで聞き直さない")
        self.assertEqual(before["agreed"]["decision"], "approve")
        self.assertEqual(before["agreed"]["asked"], talks[1]["asked"], "合意は 2 周目（新しい設計）で見せた行の物")

    def test_dialogue_stop_stops_before_fix(self):
        with self.tree(True) as root:
            archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree")
            [run] = self.runs(root)
            self.respond(root, run["id"], "stop", "やめる")
            [run] = self.runs(root)
            detail = self.detail(root, run["id"])
        self.assertEqual(detail["status"], "completed")
        before = top_output(detail["events"], "ask-before-fix")
        self.assertEqual((before["open"], before["go"], before["stop_reason"]), (False, False, "human:gate-design"))

    def test_a_note_reaches_the_plan_without_waiting(self):
        with self.tree(True, notes="b.py は触らない\n承認: このまま進めてよい\n") as root:
            done = archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree")
            [run] = self.runs(root)
            detail = self.detail(root, run["id"])
            plan1 = json.loads(next(root.parent.glob("**/probe/plan/plan-1.json")).read_text(encoding="utf-8"))
            shown = list(root.parent.glob("**/talk/round-1.md"))
        self.assertEqual((done.returncode, detail["status"]), (0, "completed"), "受け箱で承認した run は関所で待たない")
        self.assertEqual(plan1["answers"][-1], {"question": "設計の相談で人が入れた 1 番目の指摘", "text": "b.py は触らない"})
        self.assertFalse(body_outputs(detail["events"], "gate-design"))
        talk = body_outputs(detail["events"], "design-talk")[-1]
        self.assertEqual((talk["done"], talk["open"], talk["notes"]), (True, False, ["b.py は触らない", "承認: このまま進めてよい"]))
        self.assertEqual(top_output(detail["events"], "ask-before-fix")["agreed"]["text"], "このまま進めてよい", "承認を合意として運ぶ")
        self.assertEqual(len(shown), 1, "周の設計の控えを書いた")

    def probed(self, root, stage: str, name: str, k: int) -> dict:
        return json.loads(next(root.parent.glob(f"**/probe/{stage}/{name}-{k}.json")).read_text(encoding="utf-8"))

    def test_theme_revises_agrees_and_descends_into_the_plan(self):
        with self.tree(True, theme=True) as root:
            archon.archon(root, "workflow", "run", WORKFLOW, "--no-worktree")
            [run] = self.runs(root)
            self.assertEqual(run["status"], "paused", "1 周目の止まる周で設計の段の承認ノードが開いて待つ")
            first = body_outputs(self.detail(root, run["id"])["events"], "theme-talk", "theme-rounds")
            self.assertEqual((first[-1]["open"], first[-1]["done"]), (True, False))
            self.assertIn("設計の問い Q1", first[-1]["text"])
            self.respond(root, run["id"], "revise", "## 持ち主の言葉\n索引は要らない\n## 問いへの答え\n- Q1: A2\n")
            [run] = self.runs(root)
            self.assertEqual(run["status"], "paused", "設計し直して事前審査をやり直し、もう一度設計の段の関所が開いて待つ")
            theme2, review2 = self.probed(root, "theme", "theme", 2), self.probed(root, "theme", "review", 2)
            self.respond(root, run["id"], "approve", "進めて")
            [run] = self.runs(root)
            self.assertEqual(run["status"], "paused", "降りた計画の往復の 1 周目で設計の相談の関所が開いて待つ")
            plan1 = self.probed(root, "plan", "plan", 1)
            self.respond(root, run["id"], "approve")
            [run] = self.runs(root)
            detail = self.detail(root, run["id"])
        self.assertEqual((theme2["blocks"], theme2["prior_design"]), (["person-1"], True), "2 周目の書き手は人の block と前の案を受けた")
        self.assertEqual([(r["kind"], r.get("pick")) for r in theme2["answers"]],
                         [("note", None), ("owner_words", None), ("ask_answer", "A2")], "答えの text の見出しのセクションが人の答えの行になる")
        self.assertEqual(review2["person"], ["person-1"], "事前審査は人の block を照らし直した")
        self.assertEqual(detail["status"], "completed", json.dumps(detail.get("events", [])[-3:], ensure_ascii=False))
        events = detail["events"]
        talks = body_outputs(events, "theme-talk", "theme-rounds")
        self.assertEqual([(t["open"], t["done"]) for t in talks], [(True, False), (True, False), (False, True)])
        self.assertEqual(len(body_outputs(events, "theme-out", "theme-rounds")), 2, "合意の周は書き手も事前審査も回さない")
        descended, into = top_output(events, "theme-descend"), top_output(events, "request-in")
        self.assertEqual((descended["go"], descended["rows"], descended["answer"]["decision"]), (True, 1, "approve"))
        self.assertEqual((into["go"], into["request_file"], into["request_scope"]), (True, descended["request_file"], True),
                         "判定から後ろは降りた依頼を読む")
        questions = [a["question"] for a in plan1["answers"]]
        self.assertEqual(questions[0], "q", "依頼が先に持っていた答えが先")
        self.assertIn("設計の段で承認された設計", questions, "計画の役は承認された設計の在りかを受けた")
        self.assertIn("設計の段の問い Q1", questions)
        self.assertEqual([t["decision"] for t in body_outputs(events, "design-talk")[-1]["talks"]], ["approve"],
                         "設計の段の答えを計画の段の答えに数えない")
        before = top_output(events, "ask-before-fix")
        self.assertEqual((before["open"], before["go"]), (False, True))


if __name__ == "__main__":
    unittest.main()
