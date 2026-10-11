"""仕様を固めるブロック（blk-spec。本線 ops/blocks/BLOCKS.md の R2「仕様を固める」、差し込み口 spec）の芯。

仕様の道は run の入力 flow=spec が選ぶ（写しの rules の check_inputs・on_init が loop.flow に写し、spec.* の節の条件 spec_flow が
読む。正本は写しの graph a1202d0。本線は review-loop-spec.json へ移す作業を止めている）。節は写しの graph のまま:
- spec.write（writer）→ spec.review（judge。書いた目と別。読むだけ）→ spec.revise（writer。審査が穴を挙げた時だけ。写しの条件
  spec_revise_due）→ spec.approve（機械。周の途中の問い）→ spec.freeze（機械。承認の後に受け入れ条件の run を走らせて記録に固める）
- 受け付けの検査（schema・post_check の spec_write_output・spec_review_output・spec_revise_output）・問いの文（spec_approve）・
  固める中身（spec_freeze）・答えの記録（on_answer_in_round）は全部写しの rules の物を盤面（entry.open_board）越しに呼ぶ。
  ここは写さない・足さない

人の関所は線 A の policy-gate と同じ仕組みを使う（新しい関所の仕組みを作らない）:
- 文: 線 A の関所の境の節（at gate）と同じ手順。止め札（halt.seen）を見て、盤面の問い（pending_human）を関所の文（gate_text）にし、
  ブロックの置き場の r<N>/spec-gate.md にも置く。境の節の中身はライン darkfactory のモジュール（層 L6）に移ったので、ブロック（層 L4）からは呼べない。
  関所の語・止め札の by・文の組み方はここに写して持つ（写しの印「線 A の境の節の写し」。core の関所のモジュールへ 1 つにまとめるのは
  統合の計画 Task 10）
- 答え: 実行基盤の approval（decisions: approve・continue・stop・reject。GATE_GO・GATE_STOP。線 A の境の節と同じ語）の出口を次の
  script の節が with: で受け、盤面の answer に渡す（approve・continue は continue、stop・reject は stop。境の節の policy-gate と
  同じ当て方）。
  continue の後の settle で spec.freeze が走る

口:
- route:    役の輪の前。盤面が止まっていれば go false。止め札が在れば盤面を止めて go false（線 A の境の節と同じ by）。
            書く役の route は、spec.write が na（flow=spec の無い run）・待ちなのに ready でない（依存の CI が済んでいない）なら
            BoardGap（配線の誤り）。返り {go, node, why}
- prep:     指示書を engine と同じ描き方（rolekit.render_body。reads・schema の足し書き）で描き、この節の拒否が在れば最後の拒否の文を頭に
            （$LOOP_PREV で貼らない。R44）。読むだけの役（審査）は 1 回目の前だけ作業ツリーの写しを置く。起こした印を置く
- take:     読むだけの役は作業ツリーを写しと比べる → 盤面の done。拒否は spec-rejects.json に積み、GIVE_UP_AFTER 回目で done・give_up
- refuse:   読めない返答を拒否として数える
- ask:      境の節の at gate と同じ手順（止め札 → 盤面の問い → 文）。問いが spec.approve 以外なら BoardGap（このブロックは
            他の節の問いに答えない）
- answer:   関所の出口を盤面に渡す。問いが無い（再開で呼び直した）なら 2 度答えない
- collect:  出口 {ok, reason, spec_file, tests: [{file, sha}], approved_by, approval_note, frozen_rev, requirements, acceptance,
            faces, handled}。固まっていなければ、止まった理由（人の stop・止め札）か最後の拒否の文で盤面を止めて ok false
- script_main: スクリプトの入口（rolekit.script_main。環境変数の欠け・BoardGap・写しの Reject は終了コード 2）
"""
import json
import os
import pathlib
import subprocess
import sys

sys.dont_write_bytecode = True

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from rolekit import BoardGap  # noqa: E402  （rolekit が写しの engine を sys.path に足す。engine より先に）
from engine.util import Reject, safe_name  # noqa: E402
import gatemarks  # noqa: E402
import rolekit  # noqa: E402

APPROVE = "spec.approve"
SPEC_FILE = "spec.json"                 # 出口が書く record.process.spec の写し（b.work）
NULL = "null"                           # 飛ばされた節の出力（if_skipped: null）が届く字
# 線 A の境の節の写し（darkfactory/lib/line_edge.py・plan.py。層の決まりでブロックからは import できない。統合の計画 Task 10 で
# core の関所のモジュールへ 1 つにまとめる）
GATE_GO = ("approve", "continue")       # approve は continue と、reject は stop と同じ（台帳 R32）
GATE_STOP = ("stop", "reject")
GATE_STOP_NOTE = "関所で止めた"          # stop・reject に一言が無い時の理由
FLAG_BY_PREFIX = "request:"             # 止め札で止めた盤面の state.stop.by は "request:<札の by>"（報告の stopped_by_request）
RUN_ID_HOLE = "<id>"                    # run の id を知らない時の文の穴


def snapshot_name(nid: str) -> str:
    return f"spec-snapshot-{safe_name(nid)}.json"


# ---------------------------------------------------------------- 盤面
def _write_json(path: pathlib.Path, obj) -> pathlib.Path:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _read_json(path: pathlib.Path, default=None):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BoardGap(f"{path} を読めない: {e}") from None


# ---------------------------------------------------------------- accept
parse_reply = rolekit.parse_reply   # 役の返答を dict に。読めなければ (None, 理由)


# ---------------------------------------------------------------- 関所（線 A の policy-gate と同じ仕組み）
def gate_text(asking: dict, *, run_id: str = RUN_ID_HOLE) -> str:
    """盤面の問い {node, kinds, question, items, …} を仕様の関所の文にする（線 A の修正前の関所と同じ組み立て gatemarks.gate_text。
    一言は run の記録の仕様の承認に残る）"""
    return gatemarks.gate_text(asking, run_id=run_id or RUN_ID_HOLE, node=APPROVE, record_name="process.spec.approval")


def parse_gate(raw: str):
    """関所の出口（with: の {from: $spec-gate.output, if_skipped: null}）を dict か None（開かなかった）に。形の誤りは BoardGap"""
    if raw.strip() in ("", NULL):
        return None
    try:
        gate = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BoardGap(f"関所の答えが JSON として読めない（{e}）: {raw[:200]!r}") from None
    if gate is None:
        return None
    if not isinstance(gate, dict):
        raise BoardGap(f"関所の答えが JSON のオブジェクトでない: {type(gate).__name__}")
    decision = gate.get("decision")
    if decision not in GATE_GO + GATE_STOP:
        raise BoardGap(f"関所の答えの語 {decision!r} を知らない（{' / '.join(GATE_GO + GATE_STOP)}）")
    text = gate.get("text")
    if text is None:
        text = ""
    if not isinstance(text, str):
        raise BoardGap(f"関所の一言が文字列でない: {type(text).__name__}")
    return {"decision": decision, "text": text}


# ---------------------------------------------------------------- collect
def _head(repo) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise Reject(f"git rev-parse HEAD が失敗した: {r.stderr.strip()[-300:]}")
    return r.stdout.strip()

