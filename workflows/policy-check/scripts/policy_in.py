# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""方針の文と困り事から依頼の行と解き方を組み、place に request.json を書いて、world と review（事前審査）へ運ぶ値を返す（include の with: へ値を運ぶのはこの node だけ）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

policy = ports.text(os.environ.get("INPUTS_POLICY"))
path = ports.place() / steps.REQUEST_FILE
path.write_text(json.dumps(steps.request(policy, ports.text(os.environ.get("INPUTS_PROBLEM"))), ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
ports.returns({"request": ports.pointer(path, "json(shared:request.schema.json)"), "policy": policy, "means": steps.means(policy), "purpose": ports.text(os.environ.get("INPUTS_PURPOSE")),
               "web": ports.choice(os.environ.get("INPUTS_WEB"), ("on", "off")), "lang": ports.text(os.environ.get("INPUTS_LANG"))})
