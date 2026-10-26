"""fix の block の試験が共に使う定数と、型の書き手の block との橋渡し（元 lib/tests/test_blk_fix_tdd.py の SUITE と lib/tests/test_fix_seams.py の SELF_REPORT。
lib/tests は組み込みで消えるので、ここに置く）"""
import json
import pathlib
import subprocess
import sys

from tests.bin import hermetic
from tests.blocks import kit

# 対象リポジトリの根で test_*.py を unittest で回し、JUnit XML を第 1 引数に書く実行器（本線の tdd_suite の約束と同じ形）
SUITE = '''
import sys, unittest, xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
sys.path.insert(0, ".")
out = sys.argv[1]
rows = []
class R(unittest.TestResult):
    def addSuccess(self, t): rows.append((t, None))
    def addFailure(self, t, e): rows.append((t, "failure"))
    def addError(self, t, e): rows.append((t, "error"))
    def addSkip(self, t, r): rows.append((t, "skipped"))
unittest.defaultTestLoader.discover(".", pattern="test_*.py", top_level_dir=".").run(R())
root = ET.Element("testsuite")
for t, kind in rows:
    cls, name = t.id().rsplit(".", 1)
    tc = ET.SubElement(root, "testcase", classname=cls, name=name)
    if kind:
        ET.SubElement(tc, kind)
ET.ElementTree(root).write(out)
sys.exit(0 if all(k in (None, "skipped") for _, k in rows) else 1)
'''

# SUITE と同じ実行器で、赤の行の failure・error の子の message に例外の文を書く物（直す前と当てた後の失敗の文を比べる試験。#837）
SUITE_WITH_MESSAGE = '''
import sys, unittest, xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
sys.path.insert(0, ".")
out = sys.argv[1]
rows = []
class R(unittest.TestResult):
    def addSuccess(self, t): rows.append((t, None, ""))
    def addFailure(self, t, e): rows.append((t, "failure", str(e[1])))
    def addError(self, t, e): rows.append((t, "error", str(e[1])))
    def addSkip(self, t, r): rows.append((t, "skipped", ""))
unittest.defaultTestLoader.discover(".", pattern="test_*.py", top_level_dir=".").run(R())
root = ET.Element("testsuite")
for t, kind, message in rows:
    cls, name = t.id().rsplit(".", 1)
    tc = ET.SubElement(root, "testcase", classname=cls, name=name)
    if kind:
        ET.SubElement(tc, kind, message=message)
ET.ElementTree(root).write(out)
sys.exit(0 if all(k in (None, "skipped") for _, k, _ in rows) else 1)
'''

# 修正役の返答の changes の行の自己申告の欄（recount._reply_shape_problems が照らす）
SELF_REPORT = {"bypass_tried": "修正を残したまま空の並びを渡して破りに行き、例外で止まるのを見た",
               "breaks": {"how": "git grep -n mean", "result": "呼び手は 1 か所で、戻り値の型は変わらない"},
               "precedent": {"problem": "平均の分母の誤り", "verdict": "adopt", "reason": "標準の定義に合わせる",
                             "source": "https://docs.python.org/3/library/statistics.html"},
               "root_or_symptom": {"kind": "root", "why": "分母の式そのものを直した"}}

# 走らせる試験を差分から自分で選ぶ実行器（tests/changed.py の形。#846）: 作業ツリーに HEAD からの差が在れば SUITE_WITH_MESSAGE と同じに
# 全部（-k が在ればその語を id に含む物）を回し、差が無ければ（直す前の版の写し）既定では何も回さない。HEED_NAMED が真なら、差が無くても TDD_SUITE_ONLY=1 の後ろの名指し
# 『<パス>::<クラス>::<名前>』だけを回す
DIFF_SUITE = '''
import os, pathlib, subprocess, sys, unittest, xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
sys.path.insert(0, ".")
HEED_NAMED = {heed}
out, args = sys.argv[1], sys.argv[2:]
named = [a for i, a in enumerate(args) if "::" in a and (i == 0 or args[i - 1] != "-k")]
rows = []
class R(unittest.TestResult):
    def addSuccess(self, t): rows.append((t, None, ""))
    def addFailure(self, t, e): rows.append((t, "failure", str(e[1])))
    def addError(self, t, e): rows.append((t, "error", str(e[1])))
    def addSkip(self, t, r): rows.append((t, "skipped", ""))
loader = unittest.defaultTestLoader
words = [w.strip() for w in args[args.index("-k") + 1].split(" or ")] if "-k" in args else None
def flat(s):
    for t in s:
        yield from (flat(t) if isinstance(t, unittest.TestSuite) else [t])
if subprocess.run(["git", "diff", "--quiet", "HEAD"]).returncode:
    for t in flat(loader.discover(".", pattern="test_*.py", top_level_dir=".")):
        if words is None or any(w in t.id() for w in words):
            t.run(R())
elif HEED_NAMED and os.environ.get("TDD_SUITE_ONLY") == "1":
    for n in named:
        path, _, rest = n.partition("::")
        mod = pathlib.Path(path).resolve().relative_to(pathlib.Path.cwd().resolve()).with_suffix("").as_posix().replace("/", ".")
        loader.loadTestsFromName(mod + "." + rest.replace("::", ".")).run(R())
root = ET.Element("testsuite")
for t, kind, message in rows:
    cls, name = t.id().rsplit(".", 1)
    tc = ET.SubElement(root, "testcase", classname=cls, name=name)
    if kind:
        ET.SubElement(tc, kind, message=message)
ET.ElementTree(root).write(out)
sys.exit(0 if all(k in (None, "skipped") for _, k, _ in rows) else 1)
'''


# 試験が手で組む書き手の返答（changes などだけ）を、型の block と受け付けの間の形 shared:writer-reply.schema.json に合う全体にする
# （欠けた必須の欄を中立の値で補う。在る欄は変えない）。受け付け・consult-check は返答を読む時にこの形に照らす（writers.reply_of）
REPLY_DEFAULTS = {"changes": [], "not_done": [], "fix_closure": {"status": "not_applicable"}, "mechanism_changed": False,
                  "premise_drift": False, "gates_changed": False, "seams_changed": False, "security_surface_changed": False,
                  "path_changed": False, "interactions": [], "wrote_refs": [], "plan_faces": []}


def full_reply(reply: dict) -> dict:
    """欠けた必須の欄を中立の値で補う。fix_closure は、修正（changes）が在る返答では found（修正が在るのに黙って通る not_applicable・carried_over は
    受け付けが拒む）、無い返答では not_applicable"""
    given = {k: v for k, v in REPLY_DEFAULTS.items() if k not in reply}
    if reply.get("changes"):
        given["fix_closure"] = {"status": "found", "count": 1, "detail": "試験の返答の既定（閉鎖の状態を測らない）"}
    return {**given, **reply}


def reply_json(reply: dict) -> str:
    import json
    return json.dumps(full_reply(reply), ensure_ascii=False)


# ---------------------------------------------------------------- 型の書き手の block との橋渡し（受け付けと支度の試験が、書き手の返りと指示を block の道で作る）
VARIANT_RETURN_FILE = "reply-variant.json"


def variant_return(env: dict) -> dict:
    """受け付け・consult-check の入力 INPUTS_REPLY_VARIANT を、型 variant の書き手の block の返りの字に替えた環境。試験は書き手の返答の字
    （reply_json の字）をそのまま渡すので、返答を place（ARTIFACTS_DIR）の reply-variant.json に置き、block の返り {ok, reason, reply（pointer）, report}
    に包む。飛んだ block を表す "null"・空・もう block の返りの字の物は替えない"""
    raw = str(env.get("INPUTS_REPLY_VARIANT") or "")
    if raw.strip() in ("", "null"):
        return env
    try:
        doc = json.loads(raw)
    except ValueError:
        return env
    if isinstance(doc, dict) and {"ok", "reply", "report"} <= set(doc):
        return env
    place = pathlib.Path(env["ARTIFACTS_DIR"])
    (place / VARIANT_RETURN_FILE).write_text(raw, encoding="utf-8")
    pointer = {"type": "archon_artifact", "run_id": env["WORKFLOW_ID"], "path": VARIANT_RETURN_FILE}
    return {**env, "INPUTS_REPLY_VARIANT": json.dumps({"ok": True, "reason": "", "reply": pointer, "report": []})}


def writer_prompt(env: dict, out: dict, cwd) -> str:
    """支度 fix_prep・fix_ruled_prep の返り out（writer・order・slots の pointer）を、起こす型の書き手の block（writer の id w-<型>・wr-<型> の
    <型>）の writer_prep.py に渡して組んだ指示（block の place の <型>-prompt-<n>.md にも書かれる）。env は支度を回した環境
    （ARTIFACTS_DIR など）、cwd は作業ツリー"""
    weapon = out["writer"].split("-", 1)[1]
    block = kit.BLOCKS / f"weapon-{weapon}"
    include = f"{out['writer']}__{weapon}-prep"
    full = {**env, "ARCHON_NODE_EXECUTION": json.dumps({"runId": env["WORKFLOW_ID"], "path": include}),
            "INPUTS_ORDER": json.dumps(out["order"]), "INPUTS_SLOTS": json.dumps(out["slots"])}
    done = subprocess.run([sys.executable, str(block / "scripts" / "writer_prep.py")], cwd=cwd, env=hermetic.child_env(**full),
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise AssertionError(f"writer_prep.py が落ちた（{done.returncode}）: {done.stderr}")
    return json.loads(done.stdout)["prompt"]


def slots_of(place, out: dict) -> dict:
    """支度の返り out の slots の pointer が指す slots（型の block に渡った値と段落の真偽）"""
    return json.loads((pathlib.Path(place) / out["slots"]["path"]).read_text(encoding="utf-8"))
