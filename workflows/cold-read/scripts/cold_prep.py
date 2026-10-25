# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""初見の読み手の支度: 本文のファイルを読み、読み手の指示を prompts/cold.md から組む。読めない・空なら due を偽にして訳を返す。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import prompt  # noqa: E402


def compute():
    import oneline  # lib/
    from src import files, reply
    place = ports.place()
    for name in files.OWN_FILES:   # 自分の名のファイルだけ消す（world の intake と同じ。ほかの物は消さない）
        (place / name).unlink(missing_ok=True)
    raw = os.environ.get("INPUTS_TEXT")
    try:
        path = ports.file(raw, "file")
        if path is None:
            raise ValueError("本文のファイルが渡されていない")
        body = path.read_text(encoding="utf-8")
    except (ValueError, OSError) as e:   # UnicodeDecodeError は ValueError の子
        return {"due": False, "prompt": "", "reason": oneline.one_line(
            f"入力 text: 読ませる本文のファイルを読めない（{ports.text(raw).strip()[:80]}: {type(e).__name__}）")}
    if not body.strip():
        return {"due": False, "prompt": "", "reason": "読ませる本文が空"}
    lang = ports.text(os.environ.get("INPUTS_LANG")).strip()
    values = {"text": body.rstrip("\n"), "passed": reply.PASSED, "redesign": reply.REDESIGN, "lang": lang}
    return {"due": True, "prompt": prompt.emit("cold", values, {"lang_given": bool(lang)}, prompt.round_of("cold"))["prompt"],
            "reason": ""}


def fallback(why: str) -> dict:
    return {"due": False, "prompt": "", "reason": why}


ports.run(compute, fallback)
