"""返す節（boardview.collect）。落ちない: 中の誤りは全部捕まえ、偽の結末と訳を返りの約束の形で返す（boardview.failed）"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402

artifacts = Path(os.environ["ARTIFACTS_DIR"])
folder = artifacts / boardview.FOLDER
try:
    got = boardview.collect(folder)
except Exception as e:
    got = boardview.failed(folder, f"{type(e).__name__}: {e}")
boundary.returns({**got, **{name: boundary.pointer(got[name].relative_to(artifacts).as_posix()) for name in ("review", "design")}})
