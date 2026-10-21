# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""仕様駆動の道の表を読み、会話で回す部品に渡す入力を組む（docs/design/spec-driven.md の 2.5・2.6 の 2・6.7）。

起動の殻（bin/_lib/specreviews.py）は、表を読む所だけをこの script で uv に起こす（殻の素の Python は PyYAML を持たない。持ち主の決め
others-may-use）。仕様を固める会話の AI も、部品を単独で回す前に同じ命令で入力を組む（殻が照らす入力と同じ字になる）:

    uv run --script bin/_lib/spec-inputs.py <対象の根> <表のパス> [--proposal-dir <方針の文を書くフォルダ>]

標準出力に JSON 1 つ: {ok, problems, table, design, table_sha256, design_sha256, proposal_sha256, reviews, inputs, args}。
- problems: 入口の確かめの 1〜4 の欠け（lib/spectable.problems。在れば ok は偽で、ほかの欄は空）
- reviews: 表の reviews の行（{part, run, findings}）
- inputs: 部品ごとに組んだ入力の値（字か JSON の値）。args は部品ごとの `--input <名>=<字>` の字の並び。計画の審査は方針の文を
  ファイルで渡す（--proposal-dir のフォルダに、中身の sha256 を名に持つファイル spectable.proposal_name を書き、args の
  `proposal_file=<パス>` で渡す。殻はその run の記録に残ったファイルの名で、審査した版が今の版かを照らす）
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import spectable  # noqa: E402


def build(root: pathlib.Path, table: str, proposal_dir: str = "") -> dict:
    spec = spectable.read(root, table)
    problems = spectable.problems(spec)
    if problems:
        return {"ok": False, "problems": problems, "table": spec.table_rel, "design": spec.design_rel, "table_sha256": "",
                "design_sha256": "", "proposal_sha256": "", "reviews": [], "inputs": {}, "args": {}}
    proposal = spectable.proposal_text(spec)
    proposal_out = str(pathlib.Path(proposal_dir) / spectable.proposal_name(proposal)) if proposal_dir else ""
    if proposal_out:
        pathlib.Path(proposal_out).write_text(proposal, encoding="utf-8")
    inputs = spectable.part_inputs(spec)
    args = {part: [f"{name}={spectable.input_text(value)}" for name, value in named.items()] for part, named in inputs.items()}
    if proposal_out:
        args[spectable.PLAN_REVIEW].append(f"proposal_file={proposal_out}")
    return {"ok": True, "problems": [], "table": spec.table_rel, "design": spec.design_rel,
            "table_sha256": spectable.sha256((root / spec.table_rel).read_text(encoding="utf-8")),
            "design_sha256": spectable.sha256(spec.design), "proposal_sha256": spectable.sha256(proposal),
            "reviews": list(spec.table.get("reviews") or []), "inputs": inputs, "args": args}


def main(argv: list) -> int:
    if len(argv) not in (2, 4) or (len(argv) == 4 and argv[2] != "--proposal-dir"):
        print("使い方: spec-inputs.py <対象の根> <表のパス> [--proposal-dir <フォルダ>]", file=sys.stderr)
        return 2
    print(json.dumps(build(pathlib.Path(argv[0]), argv[1], argv[3] if len(argv) == 4 else ""), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
