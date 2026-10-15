# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""run の頭の深さの役の返答を受け付ける（lib/headdepth.check）。受ければ控え judge/depth-head.json を答えで書き、拒めば標準と訳で
書き直す（拒否は judge/rejects-head-depth.json に積み、3 回目で done。通らないまま終われば標準のまま）。落ちずに {ok, done, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import headdepth  # noqa: E402
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402

ROLE = "head-depth"
jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
facts = headdepth.read(jdir).get("facts") or {}
rows = ja.read_json(jdir / ja.REQUEST_FILE, []) or []


def refuse(why: str) -> dict:
    headdepth.write(jdir, headdepth.record(headdepth.STANDARD, headdepth.NOT_ACCEPTED.format(why=why), facts_doc=facts))
    return {"ok": False, "reason": why}


def take(reply: dict) -> dict:
    gaps = headdepth.check(reply, rows, Path.cwd())
    if gaps:
        return refuse("／".join(gaps))
    headdepth.write(jdir, headdepth.record(reply["depth"], reply["why"].strip(), items=reply.get("items") or [], facts_doc=facts))
    return {"ok": True, "reason": ""}


out = rolekit.accept_round(jdir, ROLE, os.environ.get("INPUTS_REPLY", ""), take, reject=refuse)
boundary.returns({"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])})
