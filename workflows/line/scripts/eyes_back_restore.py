# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立の目から修正の段へ返す輪の、封じる前の戻し eyes-back-restore（docs/design/line.md の 1.3・5.4。作業ツリーを書く node）。

返した段が止まった・落ちた抜け方では、封じるのは返す前に最後の試験と独立の目を通った状態で、その指紋は返す前の作業ツリーの物。
返した段が試験を通っていない書き換えを作業ツリーに残していると、封じと当て（どちらも今の作業ツリーを読む）が返す前の状態を封じられない。
この節は、集め eyes-back の checkpoint（返す前の木）が在る時に、作業ツリーを返す前の木へ戻し、返した段の書き換えを置き場の eyes-back-kept.patch に控える
（決めは src/eyesback.py の restore_before_seal）。checkpoint が null（返さなかった run・返した周が通った run）か、指紋がもう作業ツリーと合う時は、作業ツリーに触らない。
戻せない・合わない時は結末の reason に訳を書き、封じ merge-seal 自身の指紋の照らしが拒む（閉じた側に倒れる）。落ちない。

入力（with:）: fingerprint（集めの指紋）・checkpoint（集めの戻す先。返す前の状態を封じない時は null）
出力: restored（戻して指紋が合った）・kept（控えのパス。書かなければ空）・reason（戻せなかった訳。戻した・触らなかった時は空）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import eyesback, files
    checkpoint, fingerprint = ports.parsed(os.environ.get("INPUTS_CHECKPOINT")), ports.parsed(os.environ.get("INPUTS_FINGERPRINT"))
    return eyesback.restore_before_seal(Path.cwd(), checkpoint, fingerprint, ports.place() / files.BACK_KEPT)


def fallback(reason: str) -> dict:
    return {"restored": False, "kept": "", "reason": reason}


ports.run(compute, fallback)
