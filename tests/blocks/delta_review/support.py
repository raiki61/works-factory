"""差分の審査の block の試験の助け（テストのモジュールではない）。使い捨ての git のリポジトリに数本のファイルを commit し、その版を
base に渡して、作業ツリーのファイルを書き換えてから script を回す。"""
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK_NAME = "delta-review"
CLAIMED = {"changes": [], "not_done": [], "plan_faces": [{"key": "claimed-closed-hole", "handled": "absorbed", "how": "The fix says it closed this hole."}]}
LONG = "x" * 30   # 20 字以上の理由の字


def review_reply(faces=(), checks=(), none="Read the changed files and their callers; nothing new was added.", compliance=None, quality=None, **more):
    """1 回目の審査役の返答。既定は項目の無い run（準拠は not_applicable）で、穴が在れば結ばれない穴なので品質は fail"""
    return {"faces": list(faces), "faces_none": "" if faces else none, "checks": list(checks),
            "compliance": compliance or {"verdict": "not_applicable", "items": [], "read": "There is no approved plan item to check against."},
            "quality": quality or {"verdict": "fail" if faces else "pass", "why": "Looked at the change and tied every hole to a compliance row."},
            **more}


def second_reply(faces=(), checks=(), none="Read the touch-up diff and its callers; nothing new was added."):
    """2 回目の審査役の返答（2 判定は無い）"""
    return {"faces": list(faces), "faces_none": "" if faces else none, "checks": list(checks)}


def check(key="claimed-closed-hole", closed=True):
    return {"key": key, "closed": closed, "why": "Looked at the diff for the claimed hole " + LONG}


def face(key="copy-of-the-rule", where="a.py", cite="alpha", kind="copy", **more):
    return {"key": key, "kind": kind, "where": where, "cite": cite, "why": "The change copies the rule to a second place " + LONG, **more}


def plan_item(n=1, allowed=("a.py",), **more):
    return {"item": n, "unit_keys": [f"unit-{n}"], "approach": "do it", "files": [], "tests": [], "rewrite_tests": [],
            "allowed_paths": list(allowed), "out_of_scope": [], **more}


class Case(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK_NAME)
        repo = self.run.repo
        (repo / "docs").mkdir()
        (repo / "a.py").write_text("alpha = 1\nbeta = 2\n", encoding="utf-8")
        (repo / "b.py").write_text("gamma = 3\n", encoding="utf-8")
        (repo / "docs" / "x.md").write_text("# x\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "seed")
        self.base = git(repo, "rev-parse", "HEAD")

    def write(self, rel, text):
        path = self.run.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def file(self, name, doc):
        """run の置き場に JSON のファイルを置き、port に渡すパスを返す（pointer でなくパスで渡す）"""
        path = self.run.artifacts / "inputs" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def intake(self, **inputs):
        ports = {"base": self.base, "plan": "", "lens_rows": "", "fix_reply": "null", "permits": "[]", "plan_review": "null",
                 "policy": "", "request": "[]", "lang": "", **inputs}
        got = self.run.script("intake", **ports)
        self.seal = got.get("seal")   # 受け付けの node へ with: で渡る入口の印（YAML の seal: $intake.output.seal と同じ）
        return got

    def read(self, name):
        return json.loads((self.run.artifacts / name).read_text(encoding="utf-8"))

    def exists(self, name):
        return (self.run.artifacts / name).exists()

    def review(self, n, reply, **env):
        return self.run.script("review_accept", n=str(n), reply=json.dumps(reply, ensure_ascii=False), seal=json.dumps(self.seal))

    def refix(self, n, reply):
        return self.run.script("refix_accept", n=str(n), reply=json.dumps(reply, ensure_ascii=False), seal=json.dumps(self.seal))

    def step(self, script, n):
        return self.run.script(script, n=str(n))


class Flow(Case):
    """審査 1 回目まで済ませた run: a.py を修正が書き換え、塞いだと言う穴が 1 つ、審査が穴 1 つと塞がっていない検算 1 つを返した"""

    def start(self, plan=None, fix_reply=None, hole_cite="beta = 22", **inputs):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        ports = {"fix_reply": json.dumps(fix_reply or CLAIMED), **inputs}
        if plan is not None:
            ports["plan"] = self.file("plan.json", plan)
        self.assertTrue(self.intake(**ports)["due"])
        compliance = {"verdict": "pass", "items": [], "read": "Read every plan item against the diff of a.py."} if plan is not None else None
        reply = review_reply([face(cite=hole_cite)], [check(closed=False)], compliance=compliance)
        got = self.review(1, reply)
        self.assertTrue(got["ok"], got)
        return self.step("owed", 1)

    def handled(self, *rows):
        return {"handled": list(rows)}

    def answer(self, key, how="Fixed it by closing the second route " + LONG, files=("a.py",), handled="fixed"):
        row = {"key": key, "handled": handled, "how": how}
        if files:
            row["files"] = list(files)
        return row
