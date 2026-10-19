# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node ci-fix-prep: 出し直しの役（1 回目の役の会話の続き）の指示を組む。最後の拒否の文と、受け付けが合わせた前の答えの控えのパスを
prompts/ci-fix.md に渡す。材料とリポジトリは会話に在るので貼らない。出し直しの周（ci-prep の resubmit が真）だけ回る"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import files, prompts  # noqa: E402

place = ports.place()
ports.returns({"prompt": prompts.ci_fix(place, files.intake(place))["prompt"]})
