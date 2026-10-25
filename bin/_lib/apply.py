"""封じた差分を対象に当てる口 bin/apply の中身: bin/apply <run-id> [--cwd <対象>] [--allow-delete] [--allow-stopped] [--allow-failed]。

約束は docs/plans/2026-10-13-stage1-walking-skeleton.md の「bin/apply（土台の計画 Task 7）」の 1〜9。run は殻 bin/works-factory の
workflow get で読み（家・隔離・Archon の起こし方は殻の物）、メイングラフか周の鎖の出力ノード result の値（terminal_record.returns.value。
どちらも同じ欄 apply・sealed を持ち、鎖の物は元の基から採る周までの最後の差分）から当てる差分を選ぶ。
hash の正本は Archon の DB の run の記録で、置き場のファイルではない。今の works の確かめ（works/dev/use.sh の apply_checked:
消す行の許し・止まった run の許し・git apply --check）に、封じた hash とポインタの照らし・読み戻しを足す。commit はしない。
封じる前に止まった run の差分は当てず、拒む 1 行に素の git apply で当てる道を書く（docs/plans/2026-10-13-line-wiring.md の M46 の決め）。
メイングラフの出力が読めない run（封じた後のノードが落ちた run など）は、旗 --allow-failed が在れば、封じのノード merge-seal の出力を run の記録の
出来事（workflow get --verbose --events の events）から読んで同じく照らして当てる（#665）。最後の承認ノードの答え（answer-final）が済んでいて
止めの答えなら、--allow-stopped も要る（M44）。封じのノードが済んでいない・その出力や出来事が読めない時は、今どおり拒む 1 行に素の git apply で
当てる道を書く（M45）。R2 が作り直しを言った run は、どちらの旗でも当てない。
承認し直すかの問い（spec-check の問い。メイングラフと周の鎖の出力の spec_questions。鎖の物は最後の差分に入る周の問いの数の和）を
残した run は、断らずに当て、当てた後にそう 1 行で知らせる（断った時は断りの 1 行だけ。今の works の apply_checked も断らない。
人は最後の承認ノードで「承認すると差分は当たる」を読んで答えている）。
result の値から読む欄は表 RETURN_READS の 1 か所に書き（グラフ → (返す値そのもの "", 読む欄の形の form, 読む欄の道)。.shared の形
apply-result.schema.json）、読む前にその形で照らす（.shared の口 ports.shape_errors）。欄の名がずれた値を、置いた差分が無い・止まった run と
読み違えず、形の誤りとして終了の値 2 で止まる。form と道が両方のグラフの returns: が名指すノードの出力に合うかは tests/layers/scan.py の E5（_shell_reads）が照らす。
--allow-failed の道が出来事から読む封じの受け皿・独立の目の受け皿・最後の承認ノードの答えも、同じ表に鍵 (グラフ, ノードの id) の行で書き、
読む前にその form の形で照らして、合わなければ同じく終了の値 2 で止まる（step_read。ノードの出力が form に合うかも E5 が照らす）。
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from bin._lib import launcher, place

LIB = Path(__file__).resolve().parents[2] / "lib"
if str(LIB) not in sys.path:   # lib/ の部品は互いを名だけで import する（merge の script と同じく lib/ を sys.path に置く）
    sys.path.append(str(LIB))

import chain  # noqa: E402  周の鎖の最後の差分の置き場（final-diff と同じ名を 2 か所に持たない）
import seal  # noqa: E402  差分の封印と R2 の語の持ち主（merge の apply と同じ決まりを 2 か所に持たない）
import answer as answers  # noqa: E402  人の答えと無人の run の推しを分ける口（欄 pushed の在る答えは人の答えでない）

NAME = "apply"
SHELL = Path(__file__).resolve().parents[1] / "works-factory"
UNREADABLE = 2
REFUSED = 1
POINTER_TYPE = "archon_artifact"   # merge の出力の diff の型（試験が workflows/merge の output_format と縛る）
# merge が置き場に置く差分の名。置き場（place）は include の道で決まる（merge-seal/sealed.diff・merge-apply/apply.diff など）ので、
# パスは決めず、ポインタの先の名の末尾で照らす（docs/design/merge.md の 1.3。同じく output_format の pattern と縛る）
APPLY_DIFF, SEALED_DIFF = "apply.diff", "sealed.diff"
# メイングラフの出力が読めない run で読む、run の記録のノードの id（試験がメイングラフの YAML と縛る）。封じのノード merge-seal と、merge-apply に
# R2 を渡す独立の目 eyes は、サブグラフの出力を受け皿（出力 {got, stop_reason}）で受けて読む（docs/design/line.md の頭の語「受け皿」）。最後の承認ノードの
# 答えは、merge-apply に答えを渡すメイングラフのノードの出力 {go, answer, stop_reason}
SEAL_STEP, EYES_STEP, ANSWER_STEP = "merge-seal-out", "eyes-out", "answer-final"
GOT = "got"
# workflow get の答えに run の記録の出来事の列を足す旗とその欄・ノードの出力を持つ出来事・ノードの済んだ状態・出来事の出力の欄（型つきの出力・
# 切り詰めの印・素の出力）。読む順も Archon の terminal-record.ts が returns を組む読みと同じ（型つきの出力が在れば切り詰めの印を見ない。
# tests/shared/test_archon_contract.py が縛る）
EVENTS_FLAGS, EVENTS = ("--verbose", "--events"), "events"
OUTPUT_EVENTS, COMPLETED = ("node_completed", "node_skipped_prior_success"), "completed"
OUTPUT_KEYS = STRUCTURED, TRUNCATED, RAW = ("structured_output", "node_output_truncated", "node_output")
# メイングラフと周の鎖の result の値から読む欄の道（. で段を分ける）と、その形（モジュールの docstring）。返す値そのものを読むので欄は ""
LINE, CHAIN = "works-factory-line", "works-factory-chain"
RESULT_FORM = "json(shared:apply-result.schema.json)"
PLACED_OK, PLACED_HASH, PLACED_POINTER = "apply.ok", "apply.hash", "apply.diff"
SEALED_OK, SEALED_HASH, SEALED_POINTER = "sealed.ok", "sealed.hash", "sealed.diff"
OUTCOME, STOP_REASON, R2_STATUS, ANSWER_TEXT, SPEC_QUESTIONS = "outcome", "stop_reason", "r2_status", "final_answer.text", "spec_questions"
RESULT_PATHS = (PLACED_OK, PLACED_HASH, PLACED_POINTER, SEALED_OK, SEALED_HASH, SEALED_POINTER, OUTCOME, STOP_REASON, R2_STATUS,
                ANSWER_TEXT, SPEC_QUESTIONS)
# メイングラフの出力が読めない run で出来事から読むノードの出力の欄（行の鍵は (グラフ, ノードの id)。受け皿は欄 got、承認ノードの答えは出力そのもの ""）
SEAL_FORM, EYES_FORM, ANSWER_FORM = ("json(shared:apply-seal.schema.json)", "json(shared:apply-eyes.schema.json)",
                                     "json(shared:apply-answer.schema.json)")
MODE, OK, HASH, DIFF, REASON = "mode", "ok", "hash", "diff", "reason"
R2_ROW = "r2.status"
GO, ANSWER_ROW, ANSWER_STOP, ANSWER_SAID = "go", "answer", "stop_reason", "answer.text"
SEAL_PATHS, EYES_PATHS, ANSWER_PATHS = (MODE, OK, HASH, DIFF, REASON), (R2_ROW,), (GO, ANSWER_ROW, ANSWER_STOP, ANSWER_SAID)
RETURN_READS = {LINE: ("", RESULT_FORM, RESULT_PATHS), CHAIN: ("", RESULT_FORM, RESULT_PATHS),
                (LINE, SEAL_STEP): (GOT, SEAL_FORM, SEAL_PATHS), (LINE, EYES_STEP): (GOT, EYES_FORM, EYES_PATHS),
                (LINE, ANSWER_STEP): ("", ANSWER_FORM, ANSWER_PATHS)}


class Get(Protocol):
    def __call__(self, run_id: str, target: Path, *flags: str) -> subprocess.CompletedProcess[str]: ...


class Refuse(Exception):
    """対象を変えずに止まる（終了の値つき）"""

    def __init__(self, message: str, code: int = REFUSED):
        super().__init__(message)
        self.code = code


def ask_launcher(run_id: str, target: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    """殻を子のプロセスで起こして run を読む。殻の文（標準エラー）はそのまま利用者へ流す"""
    return subprocess.run([sys.executable, str(SHELL), "workflow", "get", run_id, "--json", *flags, "--cwd", str(target)],
                          stdout=subprocess.PIPE, text=True, encoding="utf-8")


def main(argv: list[str], here: Path | None = None, get: Get = ask_launcher) -> int:
    parser = argparse.ArgumentParser(prog=NAME, description="封じた差分を対象の作業ツリーに当てる（commit しない）")
    parser.add_argument("run_id")
    parser.add_argument("--cwd", help="対象（無ければ打った場所）")
    parser.add_argument("--allow-delete", action="store_true", help="対象のファイルを消す差分も当てる")
    parser.add_argument("--allow-stopped", action="store_true", help="最後の承認ノードで止めた run の封じた差分を当てる")
    parser.add_argument("--allow-failed", action="store_true",
                        help="封じた後のノードが落ちてメイングラフの出力が読めない run の封じた差分を、封じのノードの出力から当てる")
    args = parser.parse_args(argv)
    here = here or Path.cwd()
    try:
        target = launcher.target_root(Path(args.cwd or here), here)
        run = read_run(get(args.run_id, target), args.run_id)
        diff, sealed_hash, notes = pick(run, target, args, get)
        try:
            data = diff.read_bytes()
        except OSError as e:
            raise Refuse(f"差分のファイルを読めない（{e.strerror}: {diff}）") from None
        if seal.digest(data) != sealed_hash:
            raise Refuse(f"封じた hash と合わない（記録 {sealed_hash}・置き場のファイル {seal.digest(data)}: {diff}）。当てない")
        files = put(target, data, args.allow_delete)
    except (launcher.Stop, Refuse) as stop:
        print(f"{NAME}: {one_line(str(stop))}", file=sys.stderr)
        return stop.code
    for note in notes:
        print(f"{NAME}: {one_line(note)}", file=sys.stderr)
    print(f"run {run['terminal_record']['run_id']} の封じた差分を {target} に当てた: {' '.join(files)}")
    print("commit はしていない。試験を回してから commit する")
    return 0


def read_run(done: subprocess.CompletedProcess[str], run_id: str) -> dict:
    """workflow get --json の答え（run の記録の欄と、終わった run の terminal_record）。読めなければ終了の値 2"""
    if done.returncode != 0:
        raise Refuse(f"run {run_id} を読めない（workflow get が終了の値 {done.returncode}）", UNREADABLE)
    try:
        run = json.loads(done.stdout)
        record = run.get("terminal_record")
    except (json.JSONDecodeError, AttributeError):
        raise Refuse(f"run {run_id} を読めない（workflow get の答えが JSON の object でない）", UNREADABLE) from None
    if record is None:
        raise Refuse(f"run {run_id} は終わっていない（terminal_record が null）。終わってから当てる", UNREADABLE)
    return run


def pick(run: dict, target: Path, args: argparse.Namespace, get: Get) -> tuple[Path, str, list[str]]:
    """当てる差分のファイルと、記録の封じた hash と、当てた後に知らせる行"""
    record = run["terminal_record"]
    unread = unreadable(record)
    if unread:
        diff, sealed_hash, note = from_seal(record, target, args, get, unread)
        return diff, sealed_hash, [note]
    value = record["returns"]["value"]
    off = shape_off(value, RESULT_FORM)
    if off:
        raise Refuse(f"run {record['run_id']} のメイングラフの出力が {RESULT_FORM} の形に合わない（{' / '.join(off[:3])}）。"
                     "bin/apply の読む欄の名と、run を回した工場の版の欄の名がずれている。当てない", UNREADABLE)
    diff, sealed_hash, stopped = choose(run, target, args.allow_stopped)
    notes = [f"{stopped}で止まった run。--allow-stopped が在るので当てた"] if stopped else []
    return diff, sealed_hash, notes + [note for note in [respec_note(value)] if note]


def shape_off(value, form: str) -> list[str]:
    """読む値を読む欄の形 form（RETURN_READS の form）で照らした誤り（空なら合う）"""
    ports = place.shared("ports")
    return ports.shape_errors(value, ports.form_of(form)[1])


def at(value: dict, path: str):
    """result の値の読む欄の道 path（RESULT_PATHS）の値。途中が null なら None"""
    for step in path.split("."):
        value = value.get(step) if isinstance(value, dict) else None
    return value


def unreadable(record: dict) -> str:
    """メイングラフの出力が読めない訳と、落ちたノードの名（読めれば空）"""
    returns = record.get("returns") or {}
    if returns.get("availability") != "available":
        why = f"returns.availability が {returns.get('availability')}"
    elif not isinstance(returns.get("value"), dict):
        why = "returns.value が object でない"
    else:
        return ""
    failed = record.get("first_failed_node")
    return (f"run {record['run_id']} のメイングラフの出力が読めない（{why}・"
            f"{f'落ちたノード {failed}' if failed else '落ちたノードは記録に無い'}）")


def from_seal(record: dict, target: Path, args: argparse.Namespace, get: Get, unread: str) -> tuple[Path, str, str]:
    """メイングラフの出力が読めない run の、封じのノードの出力が指す差分と封じた hash と、当てた後に知らせる行"""
    by_hand = unchecked(record, target)
    states = {n.get("node_id"): n.get("state") for n in record.get("nodes") or [] if isinstance(n, dict)}
    if states.get(SEAL_STEP) is None:
        raise Refuse(f"{unread}。この run には封じのノード {SEAL_STEP} が無い{by_hand}", UNREADABLE)
    if states[SEAL_STEP] != COMPLETED:
        raise Refuse(f"{unread}。封じのノード {SEAL_STEP} が済んでいない（状態 {states[SEAL_STEP]}）{by_hand}", UNREADABLE)
    try:
        events = read_events(get(record["run_id"], target, *EVENTS_FLAGS), record["run_id"])
    except Refuse as e:
        raise Refuse(f"{unread}。{e}{by_hand}", e.code) from None
    sealed = step_read(events, SEAL_STEP, unread, by_hand)
    if not (isinstance(sealed, dict) and sealed[MODE] == "seal"):
        raise Refuse(f"{unread}。封じのノード {SEAL_STEP} の出力が読めない{by_hand}", UNREADABLE)
    if sealed[OK] is not True:
        raise Refuse(f"{unread}。封じのノード {SEAL_STEP} が封じていない（{sealed[REASON]}）。封じていない差分は当てない{by_hand}")
    verdict = step_read(events, EYES_STEP, unread, by_hand) if states.get(EYES_STEP) == COMPLETED else None
    if not isinstance(verdict, dict):
        raise Refuse(f"{unread}。独立の目 {EYES_STEP} の出力が読めず、R2 が作り直しを言ったかを照らせない{by_hand}", UNREADABLE)
    if at(verdict, R2_ROW) == seal.REDESIGN:
        raise Refuse(f"R2 が {seal.REDESIGN} を言った run の差分は、--allow-failed でも当てない")
    seen, stopped = final_answer(events, states, unread, by_hand)
    needed = ["--allow-failed", *(["--allow-stopped"] if stopped else [])]
    if not args.allow_failed or (stopped and not args.allow_stopped):
        raise Refuse(f"{unread}。{seen}。封じのノードの出力から封じた差分を当てるなら {' と '.join(needed)} を付けて打ち直す")
    return pointed(record, sealed[DIFF], SEALED_DIFF), sealed[HASH], f"{unread}。{seen}。{' と '.join(needed)} が在るので封じのノードの出力から当てた"


def final_answer(events: list, states: dict, unread: str, by_hand: str) -> tuple[str, bool]:
    """最後の承認ノードで人がどう答えたかの文と、止めの答えか（承認ノードの答えが済んでいなければ、人は見ていない）"""
    if states.get(ANSWER_STEP) != COMPLETED:
        return "最後の承認ノードで人が見るはずだった物を人は見ていない", False
    answer = step_read(events, ANSWER_STEP, unread, by_hand)
    if not isinstance(answer, dict):
        raise Refuse(f"{unread}。最後の承認ノードの答え {ANSWER_STEP} の出力が読めず、人が止めたかを照らせない{by_hand}", UNREADABLE)
    if answer[GO]:
        row = answer[ANSWER_ROW]
        if row is None:
            return "最後の承認ノードは方針で開かず、機械が通した（人は見ていない）", False
        if answers.by_push(row):
            return "無人の run が最後の承認ノードを推しで通した（人の答えではない）", False
        return "最後の承認ノードで人は承認した", False
    parts = [f"止めた所 {answer[ANSWER_STOP]}"] if answer[ANSWER_STOP] else []
    return f"最後の承認ノードで止めた run（{'・'.join(parts + human_said(at(answer, ANSWER_SAID)))}）", True


def step_read(events: list, step: str, unread: str, by_hand: str):
    """メイングラフのノード step の出力から表 RETURN_READS の欄を読み、その form の形で照らした値（出力か欄が無ければ None）。
    形に合わなければ、欄の名のずれとして終了の値 2 で止まる"""
    field, form, _ = RETURN_READS[(LINE, step)]
    out = output_of(events, step)
    value = (out.get(field) if isinstance(out, dict) else None) if field else out
    if value is None:
        return None
    off = shape_off(value, form)
    if off:
        raise Refuse(f"{unread}。ノード {step} の出力{f'の {field} ' if field else ''}が {form} の形に合わない（{' / '.join(off[:3])}）。"
                     f"bin/apply の読む欄の名と、run を回した工場の版の欄の名がずれている。当てない{by_hand}", UNREADABLE)
    return value


def read_events(done: subprocess.CompletedProcess[str], run_id: str) -> list:
    """出来事の列つきの workflow get の答えの events。読めなければ終了の値 2"""
    try:
        events = json.loads(done.stdout).get(EVENTS) if done.returncode == 0 else None
    except (json.JSONDecodeError, AttributeError):
        events = None
    if not isinstance(events, list):
        raise Refuse(f"run {run_id} の記録の出来事を読めない（workflow get {' '.join(EVENTS_FLAGS)} の答えに {EVENTS} の列が無い）",
                     UNREADABLE)
    return events


def output_of(events: list, step: str):
    """ノード step の最後の済んだ出来事の出力（型つきの出力を先に、無ければ素の出力の JSON）。切り詰めた・読めない出力は None"""
    for event in reversed(events):
        if not (isinstance(event, dict) and event.get("step_name") == step and event.get("event_type") in OUTPUT_EVENTS):
            continue
        data = event.get("data")
        try:
            data = json.loads(data) if isinstance(data, str) else data
            if not isinstance(data, dict):
                return None
            if STRUCTURED in data:
                return data[STRUCTURED]
            if data.get(TRUNCATED) is True:
                return None
            return json.loads(data[RAW]) if isinstance(data.get(RAW), str) else None
        except json.JSONDecodeError:
            return None
    return None


def unchecked(record: dict, target: Path) -> str:
    """封じのノードの出力から当てられない run の、置き場に在る差分（周の鎖の親の run なら最後の差分）を確かめずに当てる道（置き場に差分が無ければ空）"""
    root = (record.get("artifacts") or {}).get("root")
    if not isinstance(root, str) or not root:
        return ""
    for path in [*named(Path(root), APPLY_DIFF), *named(Path(root), SEALED_DIFF), Path(root, chain.FINAL)]:
        if path.is_file():
            return f"。置き場の差分 {path} を確かめずに当てるなら {shlex.join(['git', '-C', str(target), 'apply', str(path)])}"
    return ""


def named(root: Path, name: str) -> list[Path]:
    """置き場の根の下の、名が name の差分（include の道ごとの place に在る。並びは決まった順）"""
    return sorted(root.rglob(name)) if root.is_dir() else []


def choose(run: dict, target: Path, allow_stopped: bool) -> tuple[Path, str, str]:
    """当てる差分のファイルと、記録の封じた hash と、止まった run を許しで当てるならその訳（ほかは空）"""
    record = run["terminal_record"]
    value = record["returns"]["value"]
    if at(value, PLACED_OK) is True:
        if at(value, SEALED_HASH) is None or at(value, PLACED_HASH) != at(value, SEALED_HASH):
            raise Refuse(f"置いた差分の hash が封じた hash と合わない（apply {at(value, PLACED_HASH)}・"
                         f"sealed {at(value, SEALED_HASH)}）。当てない")
        return pointed(record, at(value, PLACED_POINTER), APPLY_DIFF), at(value, PLACED_HASH), ""
    why = stopped_why(value)
    nothing = f"置いた差分が無い（{why}）"
    if at(value, SEALED_OK) is not True:
        by_hand = "" if at(value, R2_STATUS) == seal.REDESIGN else from_worktree(run, target)
        raise Refuse(f"{nothing}。封じていない差分は当てない{by_hand}")
    if not allow_stopped:
        raise Refuse(f"{nothing}。最後の承認ノードで止めた run の封じた差分を当てるなら --allow-stopped を付けて打ち直す")
    if at(value, R2_STATUS) == seal.REDESIGN:
        raise Refuse(f"R2 が {seal.REDESIGN} を言った run の差分は、--allow-stopped でも当てない")
    return pointed(record, at(value, SEALED_POINTER), SEALED_DIFF), at(value, SEALED_HASH), why


def stopped_why(value: dict) -> str:
    """結末の語と、止めた所と、最後の承認ノードで人が書いた一言"""
    parts = [f"結末 {at(value, OUTCOME)}"]
    if at(value, STOP_REASON):
        parts.append(f"止めた所 {at(value, STOP_REASON)}")
    return "・".join(parts + human_said(at(value, ANSWER_TEXT)))


def human_said(text) -> list[str]:
    """最後の承認ノードの答え（{decision, text, asked}）の text の人の一言（無ければ空）"""
    if isinstance(text, str) and text.strip():
        return [f"人の一言「{text}」"]
    return []


def respec_note(value: dict) -> str:
    """承認し直すかの問いを残した run（メイングラフか周の鎖の出力の spec_questions が 1 以上）なら、承認し直しを待たずに当てたと言う 1 行（ほかは空）。
    止めの語では決めない: 別の待ち（fix の衝突など）が先に立つと、止めの語は spec-changed にならない"""
    asked = at(value, SPEC_QUESTIONS)
    if asked <= 0:
        return ""
    return (f"{stopped_why(value)}——承認し直すかの問い（{asked} 件）を残した run。承認し直しを待たずに当てた"
            "（承認し直すかは次の run の仕様の段で答える）")


# 封じる前に止まった run の作業ツリーの差分を当てる sh の本文（$1 run の作業ツリー・$2 始めの commit・$3 対象）。修正の段は単位の変更を
# 作業ツリーへ index 無しの git apply で当てる（lib/unittrees.py の apply）ので、新しく作ったファイルは追跡外のまま残り、素の git diff に
# 出ない。一時の index に本物の index を写して add -A し（lib/unittrees.py の _tree_now と同じ。run の作業ツリーの本物の index は動かさない）、
# 始めの commit との差分を --binary で出す。.gitignore に当たる新しいファイルは、修正の段の木（add -A）と同じく入らない
BY_HAND = ('i=$(mktemp) && cp "$(git -C "$1" rev-parse --path-format=absolute --git-path index)" "$i" && '
           'GIT_INDEX_FILE="$i" git -C "$1" add -A -- :/ && '
           'GIT_INDEX_FILE="$i" git -C "$1" diff --cached --binary "$2" | git -C "$3" apply; s=$?; rm -f "$i"; exit $s')


def from_worktree(run: dict, target: Path) -> str:
    """封じる前に止まった run の作業ツリーの差分（追跡外の新しいファイルも）を確かめずに当てる道（作業ツリーか始めの commit が記録に無ければ空）。
    始めの commit は、メイングラフの始めの記録の base_rev（始めのノードが読む HEAD）と同じ、Archon が最初のノードの前に見た checkout"""
    path, start = run.get("working_path"), run.get("checkout_baseline") or {}
    base = start.get("commit") if start.get("kind") == "git" else None
    if not (isinstance(path, str) and path and isinstance(base, str) and base):
        return ""
    return f"。run の作業ツリーの差分を確かめずに当てるなら {shlex.join(['sh', '-c', BY_HAND, 'sh', path, base, str(target)])}"


def pointed(record: dict, ptr, name: str) -> Path:
    """ポインタの先の実のパス。ポインタがこの run の物で、先の名の末尾が name（周の鎖の run なら最後の差分の名）で、置き場の根の実のパスの
    下の在る普通のファイルでなければ止まる"""
    if not isinstance(ptr, dict) or ptr.get("type") != POINTER_TYPE or not isinstance(ptr.get("path"), str):
        raise Refuse(f"差分のポインタが読めない: {json.dumps(ptr, ensure_ascii=False)}")
    if Path(ptr["path"]).name not in (name, Path(chain.FINAL).name):
        raise Refuse(f"差分のポインタの先の名が {name} でない: {ptr['path']}")
    if ptr.get("run_id") != record["run_id"]:
        raise Refuse(f"差分のポインタが別の run {ptr.get('run_id')} を指す（記録の run は {record['run_id']}）")
    root = (record.get("artifacts") or {}).get("root")
    if not isinstance(root, str) or not root:
        raise Refuse("run の置き場の根（artifacts.root）が記録に無い")
    if os.path.isabs(ptr["path"]):
        raise Refuse(f"差分のポインタのパスが相対でない: {ptr['path']}")
    real_root = os.path.realpath(root)
    real = os.path.realpath(os.path.join(root, ptr["path"]))
    if os.path.commonpath([real_root, real]) != real_root:
        raise Refuse(f"差分のポインタが run の置き場の外を指す: {ptr['path']}（{real}）")
    if not os.path.isfile(real):
        raise Refuse(f"差分のポインタの先に普通のファイルが無い: {real}")
    return Path(real)


def put(target: Path, data: bytes, allow_delete: bool) -> list[str]:
    """照らしたバイトの差分を、消す行・当たるかを確かめてから当て、読み戻す。当てたファイルの一覧"""
    try:
        files = list(seal.diff_files(target, data))
    except ValueError as e:
        raise Refuse(f"差分を読めない（{e}）") from None
    summary = git_apply(target, data, "--summary", "-z")
    if summary.returncode != 0:
        raise Refuse(f"差分を読めない（git apply --summary）: {summary.stderr}")
    gone = [line.split(maxsplit=3)[3] for line in summary.stdout.split("\n") if line.startswith(" delete mode ")]
    if gone and not allow_delete:
        raise Refuse(f"差分が対象のファイルを消す（{' '.join(gone)}）。消してよければ --allow-delete を付けて打ち直す")
    check = git_apply(target, data, "--check")
    if check.returncode != 0:
        raise Refuse(f"差分が対象に当たらない（対象の手元の変更とぶつかっていないかを見る）: {check.stderr}")
    done = git_apply(target, data)
    if done.returncode != 0:
        raise Refuse(f"git apply が落ちた: {done.stderr}")
    back = git_apply(target, data, "-R", "--check")
    if back.returncode != 0:
        raise Refuse(f"当てたが読み戻せない（git apply -R --check）: {back.stderr}")
    return files


def one_line(text: str) -> str:
    """拒む文は 1 行（git の標準エラーや人の一言の改行を畳む）"""
    return " ".join(text.split())


def git_apply(target: Path, data: bytes, *flags: str) -> subprocess.CompletedProcess[str]:
    """git apply に差分のバイトを標準入力で渡す（hash を照らした物そのものを当てる）。
    --whitespace=nowarn は、利用者の apply.whitespace の設定で落ちたり封じた物と違う行を当てたりしないため（seal.diff_files と同じ）"""
    done = subprocess.run(["git", "-C", str(target), "apply", "--whitespace=nowarn", *flags, "-"], input=data,
                          capture_output=True)
    return subprocess.CompletedProcess(done.args, done.returncode, done.stdout.decode("utf-8", "replace"),
                                       done.stderr.decode("utf-8", "replace").strip())
