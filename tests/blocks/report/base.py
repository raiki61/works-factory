"""報告の block の試験の助け（テストのモジュールではない）。src の部品を 1 組で読み込む（kit.load は呼ぶたびに src を読み直すので、
同じ試験の中で別々の写しを掴まないよう、ここで 1 回に揃える）。"""
import importlib
import json
import pathlib
import types
import unittest

from tests.blocks import kit

BLOCK = kit.BLOCKS / "report"
# head は頭の文面表（workflows/report/src/head.py）。ほかの部品と同じ 1 組で読む
NAMES = ("files", "head", "facts_in", "outcome", "transcript", "machine", "writer", "steps")


def src() -> types.SimpleNamespace:
    """部品を名ごとに読む。まだ無い部品は None にして、その部品に頼る試験が読み込みでなく試験の中の検査で落ちるようにする"""
    kit.load("report", "files")
    parts = {}
    for name in NAMES:
        try:
            parts[name] = importlib.import_module(f"src.{name}")
        except ModuleNotFoundError as err:
            if err.name != f"src.{name}":
                raise
            parts[name] = None
    return types.SimpleNamespace(**parts)


READY = {"start_ok": True, "proved": True}
GOOD_COLD = {"verdict": "pass", "stops": [], "guessed": [], "decidable": True}
# 指摘の line は貼った行の印（W1 は書き手の頭の 1 行目）。印の付け方は writer.marked_parts が決める
BAD_COLD = {"verdict": "redesign-needed", "stops": [{"line": "W1", "text": "何の話か分からない"}],
            "guessed": [{"line": "W1", "text": "PR だと推測した"}], "decidable": False}
NOTE = {"read": [], "kept": [], "set_aside": [], "open": []}


def reply(text="要約です。\n\n## 人が決めること\n\n- 決めることは A", terms=(), note=NOTE) -> str:
    return json.dumps({"text": text, "terms": list(terms), "handoff": note}, ensure_ascii=False)


def read(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


default_reply = reply
INCLUDE = "report__"
LOOP = f"{INCLUDE}write-loop."
SECTIONS = json.dumps([{"title": "直した所", "lines": ["単位 u1: 直した"]}], ensure_ascii=False)
READY_JSON = json.dumps(READY)


class ReportRun(kit.Run):
    """script の環境に足す名（LOG_DIR など）を持てる Run"""
    extra: dict = {}

    def environ(self, include: str = "", **inputs) -> dict:
        return {**super().environ(include, **inputs), **self.extra}


class Flow(unittest.TestCase):
    def setUp(self):
        self.run = ReportRun(self, "report")
        self.run.extra = {}
        self.place = self.run.artifacts / "report"

    def facts(self, sections=SECTIONS, facts=READY_JSON, lang=""):
        return self.run.script("facts", f"{INCLUDE}facts", sections=sections, facts=facts, lang=lang)

    def prep(self):
        return self.run.script("write_prep", LOOP + "write-prep")["prompt"]

    def cold_prep(self, reply):
        return self.run.script("cold_prep", LOOP + "cold-prep", writer=reply)["prompt"]

    def accept(self, reply=None, cold=None):
        return self.run.script("write_accept", LOOP + "write-accept", reply=reply or default_reply(), cold=json.dumps(cold or GOOD_COLD))

    def finish(self):
        return self.run.script("finish", f"{INCLUDE}finish")

    def machine(self) -> str:
        return (self.place / "report.md").read_text(encoding="utf-8")

    def log(self, *rows):
        log_dir = self.run.artifacts.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / f"{kit.RUN_ID}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        self.run.extra = {"LOG_DIR": str(log_dir)}
