"""fix の block の試験が共に使う定数（元 lib/tests/test_blk_fix_tdd.py の SUITE と lib/tests/test_fix_seams.py の SELF_REPORT。
lib/tests は組み込みで消えるので、ここに置く）"""

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
