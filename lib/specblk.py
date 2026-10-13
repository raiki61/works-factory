"""仕様の段（元 works/blk-spec/lib/specblk.py）のうち、仕様の関所の語と文の部品。仕様の役の受け付け・関所の文・答えの受け・
固めは lib/judge_accept.py の spec_* が持ち、ここの物を使う。

- APPROVE: 写しの graph の承認の節の名（関所の文と記録の承認の node）
- GATE_STOP・GATE_STOP_NOTE・FLAG_BY_PREFIX: 関所の止める答えの語（reject は stop と同じ。台帳 R32。通す語は answer.GO_WORDS）と、
  一言の無い止めの理由と、止め札の by の頭
- gate_text: 関所に見せる文（線 A の修正前の関所と同じ組み立て gatemarks.gate_text）
- parse_gate: 関所の出口（関所の節の出口〔開かなかった時は null〕を境の口 value が読んだ値）を dict か None（開かなかった）に
- snapshot_name: 読むだけの役（審査）を起こす前の作業ツリーの写しのファイルの名
- SPEC_FILE: 固めた仕様のファイルの名
"""
import pathlib
import sys

sys.dont_write_bytecode = True

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from rolekit import BoardGap  # noqa: E402  （rolekit が写しの engine を sys.path に足す。engine より先に）
from engine.util import safe_name  # noqa: E402
import answer  # noqa: E402
import gatemarks  # noqa: E402

APPROVE = "spec.approve"
SPEC_FILE = "spec.json"                 # 出口が書く record.process.spec の写し（b.work）
GATE_STOP = ("stop", "reject")
GATE_STOP_NOTE = "承認ノードで止めた"          # stop・reject に一言が無い時の理由
FLAG_BY_PREFIX = "request:"             # 止め札で止めた盤面の state.stop.by は "request:<札の by>"（報告の stopped_by_request）
RUN_ID_HOLE = "<id>"                    # run の id を知らない時の文の穴


def snapshot_name(nid: str) -> str:
    return f"spec-snapshot-{safe_name(nid)}.json"


# ---------------------------------------------------------------- 関所（線 A の policy-gate と同じ仕組み）
def gate_text(asking: dict, *, run_id: str = RUN_ID_HOLE) -> str:
    """盤面の問い {node, kinds, question, items, …} を仕様の関所の文にする（線 A の修正前の関所と同じ組み立て gatemarks.gate_text。
    一言は run の記録の仕様の承認に残る）"""
    return gatemarks.gate_text(asking, run_id=run_id or RUN_ID_HOLE, node=APPROVE, record_name="process.spec.approval")


def parse_gate(gate):
    """関所の出口（関所の節の出口〔開かなかった時は null〕を境の口 value が読んだ値）を dict か None（開かなかった）に。
    形の誤りは BoardGap"""
    if gate is None:
        return None
    if isinstance(gate, str):
        raise BoardGap(f"承認ノードの答えが JSON として読めない: {gate[:200]!r}")
    if not isinstance(gate, dict):
        raise BoardGap(f"承認ノードの答えが JSON のオブジェクトでない: {type(gate).__name__}")
    decision = gate.get("decision")
    if decision not in answer.GO_WORDS + GATE_STOP:
        raise BoardGap(f"承認ノードの答えの語 {decision!r} を知らない（{' / '.join(answer.GO_WORDS + GATE_STOP)}）")
    text = gate.get("text")
    if text is None:
        text = ""
    if not isinstance(text, str):
        raise BoardGap(f"承認ノードの一言が文字列でない: {type(text).__name__}")
    return {"decision": decision, "text": text}

